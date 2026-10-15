"""The generated Max for Live devices: file format, wiring and JavaScript syntax."""

import importlib.util
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


def test_midi_tool_controls_fit_the_clip_view_panel(devices):
    """Live gives MIDI Tools a small fixed panel; anything outside it is cut off."""
    for name in ("MidiShower Generator", "MidiShower Transform"):
        _, patcher = build.read_amxd(devices[name])
        assert patcher["patcher"]["devicewidth"] == build.TOOL_WIDTH
        rects = [b["presentation_rect"] for b in _boxes(patcher).values() if b.get("presentation")]
        assert rects
        for x, y, w, h in rects:
            assert x >= 0 and y >= 0 and x + w <= build.TOOL_WIDTH and y + h <= build.TOOL_HEIGHT, (name, x, y, w, h)


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
    _, patcher = build.read_amxd(devices["MidiShower Chat"])
    boxes = _boxes(patcher)
    by_text = {b.get("text"): i for i, b in boxes.items()}
    entry = next(i for i, b in boxes.items() if b["maxclass"] == "textedit")
    web = next(i for i, b in boxes.items() if b["maxclass"] == "jweb")
    lines = {(l["patchline"]["source"][0], l["patchline"]["destination"][0]) for l in patcher["patcher"]["lines"]}
    assert boxes[entry]["keymode"] == 1  # Enter sends instead of adding a newline
    web_box, entry_box = boxes[web], boxes[entry]
    assert web_box["patching_rect"][2:] == web_box["presentation_rect"][2:]  # jweb renders at one size
    wx, wy, ww, wh = web_box["presentation_rect"]
    assert wx + ww <= entry_box["presentation_rect"][0]  # the text field sits beside the chat, never over it
    assert (by_text["prepend chat_input"], web) in lines
    assert (entry, by_text["route text"]) in lines
    page = (ROOT / "packages/core/src/midishower/api/ui/chat.html").read_text()
    assert 'bindInlet("chat_input"' in page and "<option" not in page  # dropdowns do not open in jweb


def test_chat_device_passes_midi_through(devices):
    _, patcher = build.read_amxd(devices["MidiShower Chat"])
    texts = {b.get("text") for b in _boxes(patcher).values()}
    assert {"midiin", "midiout"} <= texts


def test_style_menus_have_the_scripting_names_v8_uses(devices):
    _, patcher = build.read_amxd(devices["MidiShower Generator"])
    varnames = {b.get("varname") for b in _boxes(patcher).values()}
    assert {"style_drums", "style_bass", "style_chords"} <= varnames


def test_node_scripts_ship_next_to_every_device(devices, tmp_path):
    for path in devices.values():
        for name in build.NODE_FILES:
            assert (path.parent / name).exists()
    installed = build.install(list(devices.values()), tmp_path)
    for path in installed:
        for name in build.NODE_FILES:
            assert (path.parent / name).exists()
    assert (tmp_path / "MIDI Tools/Max Generators/MidiShower Generator.amxd").exists()


def test_each_device_starts_the_node_entry_for_its_mode(devices):
    """Node for Max does not pass script arguments in process.argv, so the mode comes from the entry file."""
    expected = {"MidiShower Chat": "midishower-chat.js", "MidiShower Generator": "midishower-miditool.js",
                "MidiShower Transform": "midishower-miditool.js"}
    for name, path in devices.items():
        _, patcher = build.read_amxd(path)
        scripts = [b.get("text", "") for b in _boxes(patcher).values() if b.get("text", "").startswith("node.script")]
        assert scripts == [f"node.script {expected[name]} @autostart 1 @watch 0"]


@pytest.mark.skipif(not MAX_NODE.exists() and shutil.which("node") is None, reason="no Node.js available")
def test_javascript_parses(devices, tmp_path):
    node = str(MAX_NODE) if MAX_NODE.exists() else shutil.which("node")
    _, patcher = build.read_amxd(devices["MidiShower Generator"])
    code = next(b["code"] for b in _boxes(patcher).values() if b["maxclass"] == "v8.codebox")
    (tmp_path / "miditool.js").write_text(code)
    for file in (tmp_path / "miditool.js", *(build.SRC / n for n in build.NODE_FILES)):
        result = subprocess.run([node, "--check", str(file)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr


LIVE_TEMPLATES = Path("/Applications/Ableton Live 12 Suite.app/Contents/App-Resources/Misc")


@pytest.mark.skipif(not LIVE_TEMPLATES.exists(), reason="Ableton Live 12 not installed")
def test_patcher_and_project_have_every_key_lives_templates_have(devices):
    """Max dereferences these keys while loading; a missing project.searchpath crashed Live 12.4.6."""
    templates = {
        "midi_effect": LIVE_TEMPLATES / "Max Devices/Max MIDI Effect.amxd",
        "generator": LIVE_TEMPLATES / "Max MIDI Tools/Max MIDI Generator.amxd",
        "transformation": LIVE_TEMPLATES / "Max MIDI Tools/Max MIDI Transformation.amxd",
    }
    for name, path in devices.items():
        kind = build.DEVICES[name][0]
        _, ours = build.read_amxd(path)
        _, template = build.read_amxd(templates[kind])
        missing = set(template["patcher"]) - set(ours["patcher"])
        assert not missing, (name, sorted(missing))
        missing_project = set(template["patcher"]["project"]) - set(ours["patcher"]["project"])
        assert not missing_project, (name, sorted(missing_project))
