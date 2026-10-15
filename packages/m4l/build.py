"""Builds the MidiShower Max for Live devices (.amxd) from the sources in src/.

    uv run python packages/m4l/build.py            # -> packages/m4l/dist/
    uv run python packages/m4l/build.py --install  # also copy into Live's User Library

Devices:
- MidiShower Chat (MIDI Effect): chat with the MidiShower agent in Live's device
  view (jweb shows the API's /ui page). MIDI passes through unchanged.
- MidiShower Generator / MidiShower Transform (MIDI Tools, Live 12.2+): the
  composition engine in the clip view's Generate / Transform panels.

Patchers are generated here instead of hand-saved in Max, so they stay
reviewable in git and every device shares one node helper (src/midishower-node.js).
An .amxd file is a small chunk header followed by the patcher JSON.
"""

from __future__ import annotations

import argparse
import itertools
import json
import shutil
import struct
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SRC = HERE / "src"
DIST = HERE / "dist"
NODE_SCRIPT = "midishower-node.js"
# node.script entry files per device kind; each sets its mode and loads NODE_SCRIPT.
NODE_ENTRIES = ("midishower-chat.js", "midishower-miditool.js")
NODE_FILES = (NODE_SCRIPT, *NODE_ENTRIES)

# Four-character device type codes, as found in Live's own device templates.
DEVICE_TYPES = {"midi_effect": b"mmmm", "generator": b"nagg", "transformation": b"natt"}
INSTALL_DIRS = {
    "midi_effect": Path("Presets/MIDI Effects/Max MIDI Effect/MidiShower"),
    "generator": Path("MIDI Tools/Max Generators"),
    "transformation": Path("MIDI Tools/Max Transformations"),
}

# live.* parameter types and unit styles (Max parameter attributes)
# Max parameter types. INT is "Int (0-255)": anything wider must be FLOAT with an integer unit style.
FLOAT, INT, ENUM = 0, 1, 2
UNIT_INT, UNIT_PERCENT = 0, 5


class Patcher:
    """Collects boxes and patch cords; box ids are assigned in creation order."""

    def __init__(self) -> None:
        self.boxes: list[dict[str, Any]] = []
        self.lines: list[dict[str, Any]] = []
        self.parameters: dict[str, Any] = {}
        self._ids = itertools.count(1)

    def box(self, maxclass: str, rect: tuple[float, float, float, float], *, inlets: int, outlets: list[str],
            text: str | None = None, presentation: tuple[float, float, float, float] | None = None, **attrs: Any) -> str:
        box_id = f"obj-{next(self._ids)}"
        box: dict[str, Any] = {
            "id": box_id,
            "maxclass": maxclass,
            "numinlets": inlets,
            "numoutlets": len(outlets),
            "patching_rect": list(rect),
        }
        if outlets:
            box["outlettype"] = outlets
        if text is not None:
            box["text"] = text
        if presentation is not None:
            box["presentation"] = 1
            box["presentation_rect"] = list(presentation)
        box.update(attrs)
        self.boxes.append({"box": box})
        return box_id

    def obj(self, text: str, x: float, y: float, *, inlets: int = 1, outlets: list[str] | None = None, width: float = 120) -> str:
        return self.box("newobj", (x, y, width, 22), inlets=inlets, outlets=outlets if outlets is not None else [""], text=text)

    def message(self, text: str, x: float, y: float) -> str:
        return self.box("message", (x, y, 60, 22), inlets=2, outlets=[""], text=text)

    def comment(self, text: str, rect, presentation=None, **attrs: Any) -> str:
        return self.box("comment", rect, inlets=1, outlets=[], text=text, presentation=presentation, **attrs)

    def parameter(self, maxclass: str, rect, presentation, *, name: str, short: str, ptype: int,
                  inlets: int, outlets: list[str], varname: str | None = None, **valueof: Any) -> str:
        box_id = self.box(
            maxclass, rect, inlets=inlets, outlets=outlets, presentation=presentation,
            parameter_enable=1, varname=varname or name,
            saved_attribute_attributes={"valueof": {
                "parameter_longname": name, "parameter_shortname": short, "parameter_type": ptype, **valueof,
            }},
        )
        self.parameters[box_id] = [name, short, 0]
        return box_id

    def connect(self, source: str, outlet: int, destination: str, inlet: int = 0) -> None:
        self.lines.append({"patchline": {"source": [source, outlet], "destination": [destination, inlet]}})

    def to_json(self, *, kind: str, title: str, width: float, height: float) -> dict[str, Any]:
        return {"patcher": {
            "fileversion": 1,
            "title": title,
            "appversion": {"major": 9, "minor": 1, "revision": 0, "architecture": "x64", "modernui": 1},
            "classnamespace": "box",
            "rect": [100.0, 100.0, 900.0, 600.0],
            "openrect": [0.0, 0.0, width, height],
            "bglocked": 0,
            "openinpresentation": 1,
            "default_fontsize": 10.0,
            "default_fontface": 0,
            "default_fontname": "Arial Bold",
            "gridonopen": 1,
            "gridsize": [8.0, 8.0],
            "gridsnaponopen": 1,
            "objectsnaponopen": 1,
            "statusbarvisible": 2,
            "toolbarvisible": 1,
            "lefttoolbarpinned": 0,
            "toptoolbarpinned": 0,
            "righttoolbarpinned": 0,
            "bottomtoolbarpinned": 0,
            "toolbars_unpinned_last_save": 0,
            "tallnewobj": 0,
            "boxanimatetime": 500,
            "enablehscroll": 1,
            "enablevscroll": 1,
            "devicewidth": width,
            "description": "MidiShower - AI composition for Ableton Live",
            "digest": "",
            "tags": "",
            "style": "",
            "subpatcher_template": "",
            "assistshowspatchername": 0,
            "platform_compatibility": 0,
            "saved_attribute_attributes": {"default_plcolor": {"expression": ""}},
            "boxes": self.boxes,
            "lines": self.lines,
            "parameters": {**self.parameters, "parameterbanks": {}, "inherited_shortname": 1},
            "dependency_cache": [],
            "latency": 0,
            "is_mpe": 0,
            "minimum_live_version": "12.2",
            "minimum_max_version": "9.1",
            # Max dereferences every one of these keys when loading a device; a missing
            # "searchpath" crashes Live 12.4 (MaxPlugLib project_deserialize_searchpath).
            # Mirrors the project block of Live's own Max device templates.
            "project": {
                "version": 1,
                "creationdate": 3590052493,
                "modificationdate": 3590052493,
                "viewrect": [25.0, 124.0, 300.0, 500.0],
                "autoorganize": 1,
                "hideprojectwindow": 1,
                "showdependencies": 1,
                "autolocalize": 0,
                "contents": {"patchers": {}},
                "layout": {},
                "searchpath": {},
                "detailsvisible": 0,
                "amxdtype": int.from_bytes(DEVICE_TYPES[kind], "big"),
                "readonly": 0,
                "devpathtype": 0,
                "devpath": ".",
                "sortmode": 0,
                "viewmode": 0,
                "includepackages": 0,
            },
            "autosave": 0,
        }}


def write_amxd(path: Path, kind: str, patcher: dict[str, Any]) -> None:
    payload = json.dumps(patcher, indent=1).encode("utf-8") + b"\n\x00"
    header = (
        b"ampf" + struct.pack("<I", 4) + DEVICE_TYPES[kind]
        + b"meta" + struct.pack("<I", 4) + b"\x00\x00\x00\x00"
        + b"ptch" + struct.pack("<I", len(payload))
    )
    path.write_bytes(header + payload)


def read_amxd(path: Path) -> tuple[bytes, dict[str, Any]]:
    """(device type, patcher dict); the inverse of write_amxd, used by the tests."""
    data = path.read_bytes()
    if data[:4] != b"ampf" or data[12:16] != b"meta" or data[24:28] != b"ptch":
        raise ValueError(f"{path} is not an uncompressed .amxd")
    size = struct.unpack("<I", data[28:32])[0]
    return data[8:12], json.loads(data[32:32 + size].rstrip(b"\x00"))


# ----------------------------------------------------------------------------
# Devices
# ----------------------------------------------------------------------------


def _on_press(p: Patcher, button: str, message: str, target: str, x: float, y: float, inlet: int = 0) -> None:
    """Send `message` when a live.text button is pressed; it may output bang or 1/0 depending on mode."""
    route = p.obj("route bang", x, y, outlets=["", ""], width=70)
    sel = p.obj("sel 1", x + 80, y + 30, inlets=2, outlets=["bang", ""], width=50)
    msg = p.message(message, x, y + 60)
    p.connect(button, 0, route)
    p.connect(route, 0, msg)
    p.connect(route, 1, sel)
    p.connect(sel, 0, msg)
    p.connect(msg, 0, target, inlet)


def chat_device() -> dict[str, Any]:
    p = Patcher()
    width, height = 640.0, 169.0
    # MIDI passes through untouched: the device sits on a MIDI track.
    midiin = p.obj("midiin", 20, 20, outlets=["int"], width=50)
    midiout = p.obj("midiout", 20, 60, outlets=[], width=50)
    p.connect(midiin, 0, midiout)

    node = p.obj("node.script midishower-chat.js @autostart 1 @watch 0", 120, 20, outlets=["", ""], width=300)
    route = p.obj("route url status", 120, 60, inlets=1, outlets=["", "", ""])
    web = p.box("jweb", (120, 200, 560, 169), inlets=1, outlets=[""], presentation=(0, 0, 560, height - 22), url="")
    # Live does not pass keystrokes to jweb, so typing happens in a native Max text field.
    # Enter sends "chat_input <words>" to the page (window.max.bindInlet), then clears the field.
    entry = p.box("textedit", (700, 200, 400, 22), inlets=1, outlets=["", "int", "", ""],
                  presentation=(0, height - 20, 560, 20), keymode=1, lines=1, wordwrap=0, fontsize=12.0,
                  bgcolor=[0.165, 0.165, 0.165, 1.0], textcolor=[0.85, 0.85, 0.85, 1.0],
                  bordercolor=[0.3, 0.3, 0.3, 1.0], varname="chat_entry")
    on_text = p.obj("route text", 700, 240, outlets=["", ""], width=70)
    order = p.obj("t b l", 700, 270, outlets=["bang", ""], width=50)
    as_symbol = p.obj("tosymbol", 760, 300, width=60)
    to_page = p.obj("prepend chat_input", 760, 330, width=120)
    clear = p.message("clear", 700, 330)
    p.connect(entry, 0, on_text)
    p.connect(on_text, 0, order)
    p.connect(order, 1, as_symbol)
    p.connect(as_symbol, 0, to_page)
    p.connect(to_page, 0, web)
    p.connect(order, 0, clear)
    p.connect(clear, 0, entry)
    set_url = p.obj("prepend url", 120, 100)
    p.connect(node, 0, route)
    p.connect(route, 0, set_url)
    p.connect(set_url, 0, web)
    # The page reports "loaded" through window.max; node.script stops re-sending the URL.
    loaded = p.obj("route loaded", 120, 400, outlets=["", ""], width=90)
    loaded_msg = p.message("loaded", 120, 440)
    p.connect(web, 0, loaded)
    p.connect(loaded, 0, loaded_msg)
    p.connect(loaded_msg, 0, node)
    other = p.obj("prepend jweb", 220, 440, width=90)
    p.connect(loaded, 1, other)
    p.connect(other, 0, node)
    set_status = p.obj("prepend set", 260, 100)
    status = p.comment("Starting...", (260, 140, 74, 120), presentation=(564, 32, 74, 120),
                       linecount=8, fontsize=9.0, textcolor=[0.6, 0.6, 0.6, 1.0])
    p.connect(route, 1, set_status)
    p.connect(set_status, 0, status)

    popout = p.parameter("live.text", (440, 60, 70, 16), (564, 8, 72, 18), name="Pop out", short="Pop out", ptype=ENUM,
                         inlets=1, outlets=["", ""], parameter_enum=["val1", "val2"], parameter_mmax=1)
    p.boxes[-1]["box"].update({"mode": 0, "text": "Pop out", "texton": "Pop out"})
    _on_press(p, popout, "popout", node, 440, 100)
    return p.to_json(kind="midi_effect", title="MidiShower Chat", width=width, height=height)


def _miditool_core(p: Patcher, mode: str) -> tuple[str, str]:
    """live.miditool.in -> dict.join -> v8.codebox -> live.miditool.out, plus node.script.
    Returns the v8 and node.script box ids."""
    code = f'var MODE = "{mode}";\n' + (SRC / "miditool.js").read_text(encoding="utf-8")
    tool_in = p.obj("live.miditool.in", 20, 20, outlets=["", ""], width=110)
    join = p.obj("dict.join", 20, 60, inlets=2, outlets=["dictionary"], width=70)
    v8 = p.box("v8.codebox", (20, 100, 420, 300), inlets=2, outlets=["", "", "", "", ""], code=code, filename="none",
               fontface=0, fontname="<Monospaced>", fontsize=10.0)
    tool_out = p.obj("live.miditool.out", 20, 420, outlets=[], width=110)
    node = p.obj("node.script midishower-miditool.js @autostart 1 @watch 0", 460, 420, outlets=["", ""], width=300)
    rebang = p.obj("t b", 460, 20, outlets=["bang"], width=40)
    # Context (right outlet) fires first and is stored; notes (left) trigger the join.
    p.connect(tool_in, 1, join, 1)
    p.connect(tool_in, 0, join, 0)
    p.connect(join, 0, v8, 0)
    p.connect(v8, 0, tool_out)
    p.connect(v8, 1, node)
    p.connect(v8, 2, rebang)
    p.connect(rebang, 0, tool_in)
    p.connect(node, 0, v8, 1)
    return v8, node


def _status_and_feedback(p: Patcher, v8: str, presentation) -> dict[str, str]:
    status = p.comment("Connecting...", (460, 120, 250, 36), presentation=presentation, linecount=3,
                       fontsize=9.0, textcolor=[0.6, 0.6, 0.6, 1.0])
    p.connect(v8, 3, status)
    feedback = p.obj("route seed", 460, 180, outlets=["", ""], width=70)
    thispatcher = p.obj("thispatcher", 560, 220, outlets=["", ""], width=80)
    p.connect(v8, 4, feedback)
    p.connect(feedback, 1, thispatcher)
    return {"seed_feedback": feedback}


def _param_to_v8(p: Patcher, box: str, name: str, v8: str, x: float, y: float) -> None:
    prepend = p.obj(f"prepend param {name}", x, y, width=130)
    p.connect(box, 0, prepend)
    p.connect(prepend, 0, v8, 1)


def _seed_controls(p: Patcher, v8: str, feedback: str, numbox_rect, dice_rect, label_rect) -> None:
    seed = p.parameter("live.numbox", (760, 300, 50, 15), numbox_rect, name="Seed", short="Seed", ptype=FLOAT,
                       inlets=1, outlets=["", "float"], parameter_mmin=1, parameter_mmax=9999, parameter_initial=[1],
                       parameter_initial_enable=1, parameter_unitstyle=UNIT_INT)
    _param_to_v8(p, seed, "seed", v8, 760, 330)
    p.connect(feedback, 0, seed)
    dice = p.parameter("live.text", (840, 300, 50, 15), dice_rect, name="New seed", short="Dice", ptype=ENUM,
                       inlets=1, outlets=["", ""], parameter_enum=["val1", "val2"], parameter_mmax=1)
    p.boxes[-1]["box"].update({"mode": 0, "text": "Dice", "texton": "Dice"})
    _on_press(p, dice, "dice", v8, 840, 330, inlet=1)
    p.comment("Seed", (760, 280, 40, 18), presentation=label_rect, fontsize=9.0)


def _menu(p: Patcher, rect, presentation, name: str, short: str, items: list[str], initial: int, **attrs: Any) -> str:
    return p.parameter("live.menu", rect, presentation, name=name, short=short, ptype=ENUM, inlets=1,
                       outlets=["", "", "float"], parameter_enum=items, parameter_mmax=len(items) - 1,
                       parameter_initial=[initial], parameter_initial_enable=1, **attrs)


def _dial(p: Patcher, rect, presentation, name: str, short: str, initial: float) -> str:
    return p.parameter("live.dial", rect, presentation, name=name, short=short, ptype=FLOAT, inlets=1,
                       outlets=["", "float"], parameter_mmin=0.0, parameter_mmax=100.0, parameter_initial=[initial],
                       parameter_initial_enable=1, parameter_unitstyle=UNIT_PERCENT)


# Live's clip-view MIDI Tool panel (Live 12.4): the size of its own Max MIDI Tool templates.
TOOL_WIDTH, TOOL_HEIGHT = 152.0, 147.0
STATUS_RECT = (2, 98, 148, 46)
GENERATOR_STATUS_RECT = (2, 116, 148, 30)  # below the Replace toggle


def generator_device() -> dict[str, Any]:
    """Layout (152 x 147): Part | Style menus; Density, Swing, Chance (drums only) dials; Seed row; status."""
    p = Patcher()
    v8, _ = _miditool_core(p, "generate")
    ui = _status_and_feedback(p, v8, GENERATOR_STATUS_RECT)

    kind = _menu(p, (760, 20, 80, 15), (2, 2, 72, 16), "Part", "Part", ["Drums", "Bass", "Chords", "Melody"], 0)
    _param_to_v8(p, kind, "kind", v8, 760, 44)
    styles = [
        ("drums", "Drum Style", ["House", "Techno", "Hip-Hop", "Trap", "Rock", "Breakbeat"], 0),
        ("bass", "Bass Style", ["Sustained", "Pulse", "Offbeat", "Octave", "Walking", "Syncopated"], 5),
        ("chords", "Chord Rhythm", ["Sustain", "Pulse", "Offbeat", "Stabs"], 0),
    ]
    for i, (key, name, items, initial) in enumerate(styles):
        menu = _menu(p, (760, 80 + i * 50, 110, 15), (78, 2, 72, 16), name, name.split()[-1], items, initial,
                     varname=f"style_{key}")
        p.boxes[-1]["box"]["hidden"] = 0 if key == "drums" else 1
        _param_to_v8(p, menu, key, v8, 880, 80 + i * 50)
    density = _dial(p, (760, 240, 44, 48), (2, 24, 48, 48), "Density", "Density", 50.0)
    _param_to_v8(p, density, "density", v8, 760, 300)
    swing = _dial(p, (820, 240, 44, 48), (52, 24, 48, 48), "Swing", "Swing", 0.0)
    _param_to_v8(p, swing, "swing", v8, 820, 360)
    chance = _dial(p, (880, 240, 44, 48), (102, 24, 48, 48), "Chance", "Chance", 100.0)
    p.boxes[-1]["box"]["varname"] = "chance_dial"
    _param_to_v8(p, chance, "chance", v8, 880, 360)
    _seed_controls(p, v8, ui["seed_feedback"], numbox_rect=(52, 76, 46, 16), dice_rect=(102, 76, 48, 16),
                   label_rect=(2, 77, 46, 14))
    # Replace: clear the time selection before the new notes go in (a Generator can only add).
    replace = p.parameter("live.text", (940, 300, 60, 15), (2, 96, 60, 16), name="Replace", short="Replace", ptype=ENUM,
                          inlets=1, outlets=["", ""], parameter_enum=["off", "on"], parameter_mmax=1,
                          parameter_initial=[1], parameter_initial_enable=1)
    p.boxes[-1]["box"].update({"mode": 1, "text": "Replace", "texton": "Replace"})
    _param_to_v8(p, replace, "replace", v8, 940, 330)
    return p.to_json(kind="generator", title="MidiShower Generator", width=TOOL_WIDTH, height=TOOL_HEIGHT)


def transform_device() -> dict[str, Any]:
    """Layout (152 x 147): Operation menu, Amount dial with Semis and Arp rate beside it, Seed row, status."""
    p = Patcher()
    v8, _ = _miditool_core(p, "transform")
    ui = _status_and_feedback(p, v8, STATUS_RECT)

    operation = _menu(p, (760, 20, 110, 15), (2, 2, 148, 16), "Operation", "Operation",
                      ["Humanize", "Quantize", "Invert", "Arpeggiate", "Variation", "Transpose"], 0)
    _param_to_v8(p, operation, "operation", v8, 760, 44)
    amount = _dial(p, (760, 80, 44, 48), (2, 24, 48, 48), "Amount", "Amount", 50.0)
    _param_to_v8(p, amount, "amount", v8, 760, 140)
    p.comment("Semis", (820, 60, 40, 18), presentation=(52, 24, 46, 14), fontsize=9.0)
    semis = p.parameter("live.numbox", (820, 80, 44, 15), (52, 40, 46, 16), name="Semitones", short="Semis", ptype=FLOAT,
                        inlets=1, outlets=["", "float"], parameter_mmin=-48, parameter_mmax=48, parameter_initial=[12],
                        parameter_initial_enable=1, parameter_unitstyle=UNIT_INT)
    _param_to_v8(p, semis, "semitones", v8, 820, 110)
    p.comment("Arp rate", (900, 60, 50, 18), presentation=(102, 24, 48, 14), fontsize=9.0)
    rate = _menu(p, (900, 80, 60, 15), (102, 40, 48, 16), "Arp Rate", "Rate", ["1/32", "1/16", "1/8", "1/4"], 1)
    _param_to_v8(p, rate, "rate", v8, 900, 110)
    _seed_controls(p, v8, ui["seed_feedback"], numbox_rect=(52, 76, 46, 16), dice_rect=(102, 76, 48, 16),
                   label_rect=(2, 77, 46, 14))
    return p.to_json(kind="transformation", title="MidiShower Transform", width=TOOL_WIDTH, height=TOOL_HEIGHT)


DEVICES = {
    "MidiShower Chat": ("midi_effect", chat_device),
    "MidiShower Generator": ("generator", generator_device),
    "MidiShower Transform": ("transformation", transform_device),
}


def build(out: Path = DIST) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, (kind, factory) in DEVICES.items():
        path = out / kind / f"{name}.amxd"
        path.parent.mkdir(parents=True, exist_ok=True)
        write_amxd(path, kind, factory())
        for name in NODE_FILES:
            shutil.copy2(SRC / name, path.parent / name)
        paths.append(path)
    return paths


def user_library() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Music/Ableton/User Library"
    if sys.platform.startswith("win"):
        return Path.home() / "Documents/Ableton/User Library"
    raise SystemExit("Ableton Live only runs on macOS and Windows")


def install(paths: list[Path], library: Path) -> list[Path]:
    installed = []
    for path in paths:
        kind = path.parent.name
        target_dir = library / INSTALL_DIRS[kind]
        target_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target_dir / path.name)
        # node.script finds its files next to the device.
        for name in NODE_FILES:
            shutil.copy2(path.parent / name, target_dir / name)
        installed.append(target_dir / path.name)
    return installed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--install", action="store_true", help="copy the devices into Live's User Library")
    parser.add_argument("--library", type=Path, help="User Library folder (default: the standard location)")
    args = parser.parse_args(argv)
    paths = build()
    for path in paths:
        print(f"built {path.relative_to(HERE)}")
    if args.install:
        for path in install(paths, args.library or user_library()):
            print(f"installed {path}")
        print("In Live: Chat is under Max for Live > Max MIDI Effect; Generator/Transform in the clip view's Generate/Transform panels.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
