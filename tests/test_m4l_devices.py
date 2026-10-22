"""The generated Max for Live devices: file format, wiring and JavaScript syntax."""

import importlib.util
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("m4l_build", ROOT / "packages" / "m4l" / "build.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)

MAX_NODE = Path("/Applications/Max.app/Contents/Resources/C74/packages/Node for Max/source/bin/osx/node/node")


@pytest.fixture(scope="module")
def devices(tmp_path_factory):
    out = tmp_path_factory.mktemp("dist")
    return {path.stem: path for path in build.build(out)}


def _boxes(patcher):
    return {b["box"]["id"]: b["box"] for b in patcher["patcher"]["boxes"]}


def test_header_and_project_type_agree(devices):
    for name, path in devices.items():
        kind_code, patcher = build.read_amxd(path)
        kind = build.DEVICES[name][0]
        assert kind_code == build.DEVICE_TYPES[kind]
        assert patcher["patcher"]["project"]["amxdtype"] == int.from_bytes(kind_code, "big")


def test_patch_cords_connect_existing_inlets_and_outlets(devices):
    for path in devices.values():
        _, patcher = build.read_amxd(path)
        boxes = _boxes(patcher)
        for line in patcher["patcher"]["lines"]:
            (src, outlet), (dst, inlet) = line["patchline"]["source"], line["patchline"]["destination"]
            assert outlet < boxes[src]["numoutlets"], (path.name, boxes[src].get("text"), outlet)
            assert inlet < boxes[dst]["numinlets"], (path.name, boxes[dst].get("text"), inlet)


def test_parameters_are_unique_and_registered(devices):
    for path in devices.values():
        _, patcher = build.read_amxd(path)
        boxes = _boxes(patcher)
        names = []
        for box_id, entry in patcher["patcher"]["parameters"].items():
            if box_id.startswith("obj-"):
                assert boxes[box_id]["parameter_enable"] == 1
                names.append(entry[0])
        assert len(names) == len(set(names)), names


def test_int_parameters_fit_maxs_int_type(devices):
    """Max's Int parameter type only holds 0..255; wider ranges must use Float with an int unit style."""
    for path in devices.values():
        _, patcher = build.read_amxd(path)
        for box in _boxes(patcher).values():
            valueof = box.get("saved_attribute_attributes", {}).get("valueof", {})
            if valueof.get("parameter_type") == build.INT:
                assert 0 <= valueof.get("parameter_mmin", 0) and valueof.get("parameter_mmax", 255) <= 255, valueof


def test_chat_device_types_into_a_native_field(devices):
    """Live does not pass keystrokes to jweb; the native textedit forwards them as chat_input."""
    _, patcher = build.read_amxd(devices["MidiBakery Chat"])
    boxes = _boxes(patcher)
    by_text = {b.get("text"): i for i, b in boxes.items()}
    entry = next(i for i, b in boxes.items() if b["maxclass"] == "textedit")
    web = next(i for i, b in boxes.items() if b["maxclass"] == "jweb")
    lines = {(l["patchline"]["source"][0], l["patchline"]["destination"][0]) for l in patcher["patcher"]["lines"]}
    assert boxes[entry]["keymode"] == 0  # the patch decides: Enter sends, Shift+Enter adds a line break
    web_box, entry_box = boxes[web], boxes[entry]
    assert web_box["patching_rect"][2:] == web_box["presentation_rect"][2:]  # jweb renders at one size
    wx, wy, ww, wh = web_box["presentation_rect"]
    assert wx + ww <= entry_box["presentation_rect"][0]  # the text field sits beside the chat, never over it
    assert (by_text["prepend chat_input"], web) in lines
    assert (entry, by_text["route text"]) in lines
    # only Enter (without Shift) or Send sends: textedit also outputs its text when it loses focus (selecting another track)
    full = {(l["patchline"]["source"][0], l["patchline"]["source"][1], l["patchline"]["destination"][0],
             l["patchline"]["destination"][1]) for l in patcher["patcher"]["lines"]}
    gate, ask = by_text["gate 1 0"], by_text["t 0 b 1"]
    assert (by_text["route text"], 0, gate, 1) in full and (gate, 0, by_text["t b l"], 0) in full
    send = next(i for i, b in boxes.items() if b.get("varname") == "send")
    assert (entry, 1, by_text["sel 13 3"], 0) in full  # the key outlet
    assert (by_text["modifiers"], 0, by_text["sel 0"], 0) in full  # Shift held: the line break stays
    assert (by_text["sel 0"], 0, ask, 0) in full
    assert any(src == send for src, _, _, _ in full)
    # Send: open (right outlet fires first), bang the field for its text, close
    assert {(ask, 2, gate, 0), (ask, 1, entry, 0), (ask, 0, gate, 0)} <= full
    assert not any(src == by_text["route text"] and dst == by_text["t b l"] for src, _, dst, _ in full)
    # Native Model menu: the page fills it and gets the pick back as model_index.
    menu = next(i for i, b in boxes.items() if b["maxclass"] == "umenu")
    router = by_text["route menu_clear menu_append menu_select"]
    assert (by_text["route loaded"], router) in lines
    assert (by_text["prepend append"], menu) in lines and (by_text["prepend set"], menu) in lines
    assert (menu, by_text["prepend model_index"]) in lines and (by_text["prepend model_index"], web) in lines
    assert (router, by_text["prepend jweb"]) in lines  # other jweb messages still reach the log
    page = (ROOT / "packages/core/src/midibakery/api/ui/chat.html").read_text()
    assert 'bindInlet("model_index"' in page and 'outlet("menu_append"' in page
    assert 'bindInlet("chat_input"' in page
    assert "body.device #modelSelect { display: none; }" in page  # the HTML dropdown is browser-only


def test_chat_device_passes_midi_through(devices):
    _, patcher = build.read_amxd(devices["MidiBakery Chat"])
    texts = {b.get("text") for b in _boxes(patcher).values()}
    assert {"midiin", "midiout"} <= texts


def test_node_scripts_ship_next_to_every_device(devices):
    """install.json (what `midibakery install` follows) puts every node file beside every device."""
    for path in devices.values():
        for name in build.NODE_FILES:
            assert (path.parent / name).exists()
    out = next(iter(devices.values())).parents[1]
    listing = json.loads((out / build.INSTALL_LIST).read_text())
    assert listing["version"] == build.VERSION
    targets = {e["target"] for e in listing["files"]}
    for name, path in devices.items():
        folder = build.INSTALL_DIRS[build.DEVICES[name][0]]
        assert (folder / path.name).as_posix() in targets
        assert {(folder / n).as_posix() for n in build.NODE_FILES} <= targets
    assert "Presets/MIDI Effects/Max MIDI Effect/MidiBakery/MidiBakery Chat.amxd" in targets
    for entry in listing["files"]:
        assert (out / entry["source"]).is_file()


def test_each_device_starts_the_node_entry_for_its_mode(devices):
    """Node for Max does not pass script arguments in process.argv, so the mode comes from the entry file."""
    expected = {"MidiBakery Bake": "midibakery-bake.js", "MidiBakery Chat": "midibakery-chat.js", "MidiBakery Set Importer": "midibakery-importer.js",
                "MidiBakery Reference Analyzer": "midibakery-reference.js"}
    for name, path in devices.items():
        _, patcher = build.read_amxd(path)
        scripts = [b.get("text", "") for b in _boxes(patcher).values() if b.get("text", "").startswith("node.script")]
        assert scripts == [f"node.script {expected[name]} @autostart 1 @watch 0"]


@pytest.mark.skipif(not MAX_NODE.exists() and shutil.which("node") is None, reason="no Node.js available")
def test_javascript_parses(devices, tmp_path):
    node = str(MAX_NODE) if MAX_NODE.exists() else shutil.which("node")
    sources = [build.SRC / n for n in (*build.NODE_FILES, "reference.js", "reference-view.js")]
    for file in sources:
        result = subprocess.run([node, "--check", str(file)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr


def test_chat_page_has_plan_apply_and_undo():
    """Plan previews get an Apply button and the header an Undo button; both run tools over the chat socket."""
    page = (ROOT / "packages/core/src/midibakery/api/ui/chat.html").read_text()
    assert '<button id="undo"' in page
    assert 'name: "apply_plan", input: { plan_id: roll.plan_id }' in page
    assert 'name: "undo", input: { action: "undo" }' in page
    assert 'case "plan":\n      showPlan(ev);' in page


@pytest.mark.skipif(not MAX_NODE.exists() and shutil.which("node") is None, reason="no Node.js available")
def test_chat_page_script_parses(tmp_path):
    node = str(MAX_NODE) if MAX_NODE.exists() else shutil.which("node")
    page = (ROOT / "packages/core/src/midibakery/api/ui/chat.html").read_text()
    script = page.split("<script>", 1)[1].split("</script>", 1)[0]
    (tmp_path / "chat.js").write_text(script)
    result = subprocess.run([node, "--check", str(tmp_path / "chat.js")], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_importer_device_hands_paths_to_its_page(devices):
    """A file dialog sends "add_path <path>" to the jweb that shows the API's /importer page."""
    _, patcher = build.read_amxd(devices["MidiBakery Set Importer"])
    boxes = _boxes(patcher)
    by_text = {b.get("text"): i for i, b in boxes.items() if b.get("text")}
    web = next(i for i, b in boxes.items() if b["maxclass"] == "jweb")
    lines = {(l["patchline"]["source"][0], l["patchline"]["destination"][0]) for l in patcher["patcher"]["lines"]}
    assert (by_text["prepend add_path"], web) in lines
    assert not any(b["maxclass"] == "live.drop" for b in boxes.values())
    for dialog in ("opendialog fold", "opendialog"):
        assert (by_text[dialog], by_text["prepend add_path"]) in lines
    assert (by_text["midiin"], by_text["midiout"]) in lines  # MIDI passes through
    node = (ROOT / "packages/m4l/src/midibakery-node.js").read_text()
    assert 'importer: "/importer"' in node


@pytest.mark.skipif(not MAX_NODE.exists() and shutil.which("node") is None, reason="no Node.js available")
def test_importer_page_script_parses(tmp_path):
    node = str(MAX_NODE) if MAX_NODE.exists() else shutil.which("node")
    page = (ROOT / "packages/core/src/midibakery/api/ui/importer.html").read_text()
    script = page.split("<script>", 1)[1].split("</script>", 1)[0]
    assert 'bindInlet("add_path"' in script
    (tmp_path / "importer.js").write_text(script)
    result = subprocess.run([node, "--check", str(tmp_path / "importer.js")], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_bake_device_shows_its_page(devices):
    """The Bake page is the API's /bake; MIDI passes through."""
    _, patcher = build.read_amxd(devices["MidiBakery Bake"])
    boxes = _boxes(patcher)
    by_text = {b.get("text"): i for i, b in boxes.items() if b.get("text")}
    lines = {(l["patchline"]["source"][0], l["patchline"]["destination"][0]) for l in patcher["patcher"]["lines"]}
    web = next(i for i, b in boxes.items() if b["maxclass"] == "jweb")
    assert (by_text["prepend url"], web) in lines
    assert (by_text["midiin"], by_text["midiout"]) in lines
    node = by_text["node.script midibakery-bake.js @autostart 1 @watch 0"]
    window = next(i for i, b in boxes.items() if b.get("text") == "p sounds")  # the Sounds... window is a subpatcher
    assert (by_text["pcontrol"], window) in lines  # how Max opens a subpatcher window
    assert (window, node) in lines and (by_text["route url status label"], window) in lines
    sounds = next(i for i, b in boxes.items() if b.get("varname") == "sounds")  # its button opens the window and asks for the labels
    assert sounds and not any(b["maxclass"] == "live.drop" for b in boxes.values())  # no drop zones on the device itself
    inner = {b["box"]["id"]: b["box"] for b in boxes[window]["patcher"]["boxes"]}
    inner_text = {b.get("text"): i for i, b in inner.items() if b.get("text")}
    inner_lines = {(l["patchline"]["source"][0], l["patchline"]["destination"][0]) for l in boxes[window]["patcher"]["lines"]}
    for part in ("drums", "bass", "chords", "lead"):  # a drop zone per part sends "sound <part> <path>" out
        zone = next(i for i, b in inner.items() if b["maxclass"] == "live.drop" and b.get("varname") == f"drop {part}")
        assert (zone, inner_text[f"prepend sound {part}"]) in inner_lines
    node_js = (ROOT / "packages/m4l/src/midibakery-node.js").read_text()
    for handler in ("sounds", "sound", "genre", "labels"):
        assert f'Max.addHandler("{handler}"' in node_js
    assert 'bake: "/bake"' in (ROOT / "packages/m4l/src/midibakery-node.js").read_text()


@pytest.mark.skipif(not MAX_NODE.exists() and shutil.which("node") is None, reason="no Node.js available")
def test_sounds_page_script_parses(tmp_path):
    node = str(MAX_NODE) if MAX_NODE.exists() else shutil.which("node")
    page = (ROOT / "packages/core/src/midibakery/api/ui/sounds.html").read_text()
    script = page.split("<script>")[1].split("</script>")[0]
    (tmp_path / "s.js").write_text(script)
    assert subprocess.run([node, "--check", str(tmp_path / "s.js")], capture_output=True).returncode == 0


@pytest.mark.skipif(not MAX_NODE.exists() and shutil.which("node") is None, reason="no Node.js available")
def test_bake_page_script_parses(tmp_path):
    node = str(MAX_NODE) if MAX_NODE.exists() else shutil.which("node")
    page = (ROOT / "packages/core/src/midibakery/api/ui/bake.html").read_text()
    script = page.split("<script>", 1)[1].split("</script>", 1)[0]
    (tmp_path / "bake.js").write_text(script)
    result = subprocess.run([node, "--check", str(tmp_path / "bake.js")], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


LIVE_TEMPLATES = Path("/Applications/Ableton Live 12 Suite.app/Contents/App-Resources/Misc")


@pytest.mark.skipif(not LIVE_TEMPLATES.exists(), reason="Ableton Live 12 not installed")
def test_patcher_and_project_have_every_key_lives_templates_have(devices):
    """Max dereferences these keys while loading; a missing project.searchpath crashed Live 12.4.6."""
    templates = {
        "midi_effect": LIVE_TEMPLATES / "Max Devices/Max MIDI Effect.amxd",
        "audio_effect": LIVE_TEMPLATES / "Max Devices/Max Audio Effect.amxd",
    }
    for name, path in devices.items():
        kind = build.DEVICES[name][0]
        _, ours = build.read_amxd(path)
        _, template = build.read_amxd(templates[kind])
        missing = set(template["patcher"]) - set(ours["patcher"])
        assert not missing, (name, sorted(missing))
        missing_project = set(template["patcher"]["project"]) - set(ours["patcher"]["project"])
        assert not missing_project, (name, sorted(missing_project))


def test_reference_device_passes_audio_and_embeds_its_code(devices):
    kind, patcher = build.read_amxd(devices["MidiBakery Reference Analyzer"])
    assert kind == b"aaaa"
    boxes = _boxes(patcher)
    by_text = {b.get("text"): i for i, b in boxes.items()}
    lines = {(tuple(l["patchline"]["source"]), tuple(l["patchline"]["destination"])) for l in patcher["patcher"]["lines"]}
    plugin, plugout = by_text["plugin~"], by_text["plugout~"]
    assert ((plugin, 0), (plugout, 0)) in lines and ((plugin, 1), (plugout, 1)) in lines
    view = next(b for b in boxes.values() if b["maxclass"] == "v8ui")
    assert view["textfile"]["embed"] == 1 and "function paint()" in view["textfile"]["text"]
    code = next(b for b in boxes.values() if b["maxclass"] == "v8.codebox")["code"]
    assert "set_or_delete_cue" in code and "warp_markers" in code and "function unlocators()" in code
    assert "add_warp_marker" in code and "function autoWarp(" in code
    labels = sorted(b["text"] for b in boxes.values() if b["maxclass"] == "live.text")
    assert labels == ["About", "Analyze", "Lock", "Remove Locators", "Set Locators"]
    menus = [b for b in boxes.values() if b["maxclass"] == "live.menu"]
    menu = next(b for b in menus if b["saved_attribute_attributes"]["valueof"]["parameter_enum"][0] == "Auto")
    assert len(menus) == 1
    assert not any(b["maxclass"] == "live.dial" for b in boxes.values()) and "function detail(" not in code
    to_v8 = by_text["prepend genre"]
    assert ((next(i for i, b in boxes.items() if b is menu), 0), (to_v8, 0)) in lines
    assert all(b["presentation_rect"][0] + b["presentation_rect"][2] <= build.REFERENCE_WIDTH
               for b in boxes.values() if b.get("presentation"))
    # Sensitivity: a field per band to "band <key>", shown back through route -> prepend set; Lock to "lock"
    fields = {b["varname"]: i for i, b in boxes.items() if b["maxclass"] == "live.numbox"}
    assert sorted(fields) == sorted(f"Sensitivity {label}" for label, _ in build.SENSITIVITY_BANDS)
    route = by_text["route kick low mid high"]
    for n, (label, key) in enumerate(build.SENSITIVITY_BANDS):
        assert ((fields[f"Sensitivity {label}"], 0), (by_text[f"prepend band {key}"], 0)) in lines
        shown = next(dst for (src, dst) in lines if src == (route, n))[0]
        assert boxes[shown]["text"] == "prepend set" and ((shown, 0), (fields[f"Sensitivity {label}"], 0)) in lines
    lock = next(i for i, b in boxes.items() if b.get("varname") == "Sensitivity Lock")
    assert boxes[lock]["mode"] == 1 and ((lock, 0), (by_text["prepend lock"], 0)) in lines
    v8_id = next(i for i, b in boxes.items() if b["maxclass"] == "v8.codebox")
    assert ((v8_id, 2), (route, 0)) in lines and "function band(" in code and "function lock(" in code
    # each field level with its lane in the view (reference-view.js: lanes start below the header and blocks)
    view_js = (build.SRC / "reference-view.js").read_text()
    const = {k: int(re.search(rf"var {k} = (\d+);", view_js).group(1)) for k in ("HEADER", "BLOCKS", "LANE")}
    lanes = re.findall(r'\["(\w+)", "(\w+)", -?\d+, \d+\]', view_js)
    assert [key for _, key in lanes] == [key for _, key in build.SENSITIVITY_BANDS]
    for n, (label, _) in enumerate(build.SENSITIVITY_BANDS):
        top = const["HEADER"] + 2 + const["BLOCKS"] + 4 + const["LANE"] * n
        _, fy, _, fh = boxes[fields[f"Sensitivity {label}"]]["presentation_rect"]
        assert fy + fh / 2 == top + (const["LANE"] - 2) / 2
    # the right column and Lock on the same rows: every control's centre on a row of the lane grid
    for b in boxes.values():
        if b.get("presentation") and b["maxclass"] in ("live.text", "live.menu", "live.numbox"):
            _, y, _, h = b["presentation_rect"]
            assert (y + h / 2 - const["HEADER"] - 2 - const["BLOCKS"] - 4) % const["LANE"] == (const["LANE"] - 2) / 2, b.get("text")
    shown_rects = [b["presentation_rect"] for b in boxes.values() if b.get("presentation")]
    assert not any(_overlap(a, b) for i, a in enumerate(shown_rects) for b in shown_rects[i + 1:])


def _overlap(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


def test_every_device_has_an_about_button_that_asks_its_node_script(devices):
    """About sends "about <version>" to the device's node.script, which answers with the versions line."""
    for name, path in devices.items():
        _, patcher = build.read_amxd(path)
        assert patcher["patcher"]["description"].startswith(f"MidiBakery {build.VERSION} ")
        boxes = _boxes(patcher)
        about = next(i for i, b in boxes.items() if b.get("varname") == "about")
        assert boxes[about]["maxclass"] == "live.text" and boxes[about]["parameter_enable"] == 0  # no automatable parameter
        assert about not in patcher["patcher"]["parameters"]
        node = next(i for i, b in boxes.items() if b.get("text", "").startswith("node.script"))
        message = next(i for i, b in boxes.items() if b.get("text") == f"about {build.VERSION}")
        lines = {(l["patchline"]["source"][0], l["patchline"]["destination"][0]) for l in patcher["patcher"]["lines"]}
        assert (message, node) in lines, name
        rect = boxes[about]["presentation_rect"]
        assert rect[0] + rect[2] <= patcher["patcher"]["devicewidth"], name
        others = [b["presentation_rect"] for i, b in boxes.items() if b.get("presentation") and i != about]
        assert not [r for r in others if _overlap(rect, r)], name


def test_a_rebuild_leaves_no_renamed_device_behind(tmp_path):
    stale = tmp_path / "audio_effect" / "MidiBakery Reference.amxd"
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"old")
    build.build(tmp_path)
    assert not stale.exists()


@pytest.mark.skipif(not MAX_NODE.exists() and shutil.which("node") is None, reason="no Node.js available")
def test_about_line_compares_the_versions(tmp_path):
    """midibakery-about.js against a stand-in API: same versions, a difference, no Live, no API, an update."""
    node = str(MAX_NODE) if MAX_NODE.exists() else shutil.which("node")
    script = tmp_path / "about-test.js"
    script.write_text(f"""
const http = require("http");
const fs = require("fs");
const {{ about, aboutText }} = require({str(build.SRC / "midibakery-about.js")!r});
const out = [];
out.push(aboutText("0.2.0", {{ api: "0.2.0", script: "0.2.0" }}));
out.push(aboutText("0.2.0", {{ api: "0.3.0", script: "0.2.0" }}));
out.push(aboutText("0.2.0", {{ api: "0.2.0", script: null }}));
out.push(aboutText("0.2.0", {{ api: "0.2.0", script: "0.2.0", update: "0.3.0" }}));
out.push(aboutText("0.2.0", {{ api: "0.2.0", script: "0.2.0", license: {{ state: "trial", message: "Trial: 9 days left" }} }}));
out.push(aboutText("0.2.0", {{ api: "0.2.0", script: "0.2.0", license: {{ state: "expired", message: "x" }} }}));
out.push(aboutText("0.2.0", {{ api: "0.2.0", script: "0.2.0", license: {{ state: "licensed", message: "Licensed" }} }}));
const server = http.createServer((req, res) => {{
  const ok = req.url === "/health" && req.headers.authorization === "Bearer secret";
  res.writeHead(ok ? 200 : 401, {{ "content-type": "application/json" }});
  res.end(JSON.stringify(ok ? {{ ok: true, version: "0.2.0", live: {{ bridge: "0.1.9" }}, update: {{ version: "0.3.0" }} }} : {{ error: "UNAUTHORIZED" }}));
}});
server.listen(0, "127.0.0.1", async () => {{
  out.push(await about("0.2.0"));  // no api.json yet
  fs.writeFileSync(process.env.MIDIBAKERY_HOME + "/api.json", JSON.stringify({{ port: server.address().port, token: "secret" }}));
  out.push(await about("0.2.0"));
  server.close();
  console.log(JSON.stringify(out));
}});
""")
    env = {"MIDIBAKERY_HOME": str(tmp_path), "PATH": "/usr/bin:/bin"}
    result = subprocess.run([node, str(script)], capture_output=True, text=True, env=env, timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [
        "MidiBakery 0.2.0 (device, API, Remote Script)",
        "Versions differ: device 0.2.0, API 0.3.0, Remote Script 0.2.0 - reinstall MidiBakery",
        "MidiBakery 0.2.0 (device, API) · Remote Script not connected",
        "MidiBakery 0.2.0 (device, API, Remote Script) · Update 0.3.0 available: Install in the Chat device",
        "MidiBakery 0.2.0 (device, API, Remote Script) · Trial: 9 days left",
        "MidiBakery 0.2.0 (device, API, Remote Script) · License needed: see the Chat device",
        "MidiBakery 0.2.0 (device, API, Remote Script)",
        "MidiBakery 0.2.0 · API not running",
        "Versions differ: device 0.2.0, API 0.2.0, Remote Script 0.1.9 - reinstall MidiBakery"
        " · Update 0.3.0 available: Install in the Chat device",
    ]


def test_shown_texts_follow_lives_theme(devices):
    """A fixed grey was unreadable on a light device background; Live's control colour fits every theme."""
    for name, path in devices.items():
        _, patcher = build.read_amxd(path)
        for box in _boxes(patcher).values():
            if box["maxclass"] == "comment" and box.get("presentation"):
                assert "textcolor" not in box, (name, box["text"])
                expression = box.get("saved_attribute_attributes", {}).get("textcolor", {}).get("expression")
                assert expression in (None, "themecolor.live_control_fg"), (name, box["text"])


def test_web_devices_show_a_loading_page_until_their_page_is_sent(devices):
    import base64

    head, data = build.LOADING_URL.split(",", 1)
    assert head == "data:text/html;charset=utf-8;base64" and " " not in build.LOADING_URL
    assert "Starting MidiBakery" in base64.b64decode(data).decode()
    for name in ("MidiBakery Bake", "MidiBakery Chat", "MidiBakery Set Importer"):
        _, patcher = build.read_amxd(devices[name])
        web = next(b for b in _boxes(patcher).values() if b["maxclass"] == "jweb")
        assert web["url"] == build.LOADING_URL
