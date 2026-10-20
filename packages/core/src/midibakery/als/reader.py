"""Reads an Ableton Live Set (.als: gzip-compressed XML) into plain data, Live 11 and 12.

Only reads: nothing here writes a file. Notes come out the way Live plays them: a clip's loop,
start marker and length decide which notes sound where on the Arrangement (``clip_notes``).
Times are in beats (a quarter note is 1); a bar is ``Song.beats_per_bar`` beats.
"""

from __future__ import annotations

import gzip
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

EPSILON = 1e-6
DEVICE_NAMES = {
    "InstrumentVector": "Wavetable", "OriginalSimpler": "Simpler", "MultiSampler": "Sampler", "UltraAnalog": "Analog",
    "LoungeLizard": "Electric", "StringStudio": "Tension", "DrumGroupDevice": "Drum Rack",
    "InstrumentGroupDevice": "Instrument Rack", "AudioEffectGroupDevice": "Audio Effect Rack",
    "MidiEffectGroupDevice": "MIDI Effect Rack", "Compressor2": "Compressor", "Eq8": "EQ Eight",
}
INSTRUMENT_TAGS = {
    "InstrumentVector", "OriginalSimpler", "MultiSampler", "Operator", "UltraAnalog", "LoungeLizard",
    "StringStudio", "DrumGroupDevice", "InstrumentGroupDevice", "InstrumentImpulse", "Drift", "Meld",
}


class AlsError(ValueError):
    """A file that is not a readable Live Set."""


@dataclass(frozen=True)
class NoteEvent:
    time: float  # beats from the clip's start on the Arrangement (or from the loop start in a pattern)
    pitch: int  # MIDI note, C3 = 60
    duration: float
    velocity: float


@dataclass
class Clip:
    name: str
    start: float  # Arrangement beat
    end: float
    kind: str  # "midi" | "audio"
    notes: list[NoteEvent] = field(default_factory=list)
    file: str = ""  # audio: the sample's file name
    loop_beats: float = 0.0  # midi: the looped length (0: no loop)


@dataclass
class Pad:
    note: int
    name: str


@dataclass
class Device:
    kind: str  # Live's own name where known, else the XML tag
    name: str  # the user's name for it, if any
    pads: list[Pad] = field(default_factory=list)  # Drum Rack


@dataclass
class Track:
    index: int
    id: int
    kind: str  # "midi" | "audio" | "group" | "return"
    name: str
    group_id: int  # -1: not in a group
    devices: list[Device] = field(default_factory=list)
    clips: list[Clip] = field(default_factory=list)  # Arrangement clips
    session_clips: list[Clip] = field(default_factory=list)
    scale: tuple[int, str] | None = None  # (root pitch class, name) from the clips' scale, Live 12


@dataclass
class Locator:
    beat: float
    name: str


@dataclass
class Song:
    path: str
    name: str
    live_version: str
    tempo: float
    beats_per_bar: float
    tracks: list[Track]
    locators: list[Locator]
    main_devices: list[Device] = field(default_factory=list)

    @property
    def live_major(self) -> int:
        digits = self.live_version.removeprefix("Ableton Live").strip().split(".")[0]
        return int(digits) if digits.isdigit() else 0


def _value(el: ET.Element | None, path: str, default: str = "") -> str:
    found = el.find(path) if el is not None else None
    return found.get("Value", default) if found is not None else default


def _number(el: ET.Element | None, path: str, default: float = 0.0) -> float:
    try:
        return float(_value(el, path, str(default)))
    except ValueError:
        return default


def clip_notes(clip: ET.Element, length: float) -> tuple[list[NoteEvent], float]:
    """The notes of a MIDI clip played for ``length`` beats, and the loop length (0: no loop).

    Clip time: playing starts at LoopStart + StartRelative. With the loop on, the clip runs to LoopEnd
    and then repeats LoopStart..LoopEnd; with it off it just runs to LoopEnd.
    """
    loop = clip.find("Loop")
    loop_start, loop_end = _number(loop, "LoopStart"), _number(loop, "LoopEnd")
    looping = _value(loop, "LoopOn") == "true"
    first = loop_start + _number(loop, "StartRelative")
    span = loop_end - loop_start
    raw: list[tuple[float, int, float, float]] = []
    for track in clip.findall("Notes/KeyTracks/KeyTrack"):
        pitch = int(_number(track, "MidiKey", -1))
        if pitch < 0:
            continue
        for note in track.findall("Notes/MidiNoteEvent"):
            if note.get("IsEnabled", "true") != "true":
                continue
            raw.append((float(note.get("Time", 0)), pitch, float(note.get("Duration", 0)), float(note.get("Velocity", 100))))
    raw.sort()
    out: list[NoteEvent] = []

    def add(time: float, pitch: int, duration: float, velocity: float) -> None:
        if -EPSILON <= time < length - EPSILON:
            out.append(NoteEvent(max(0.0, time), pitch, min(duration, length - max(0.0, time)), velocity))

    for time, pitch, duration, velocity in raw:  # the first pass, from the start marker
        if first - EPSILON <= time < loop_end - EPSILON:
            add(time - first, pitch, duration, velocity)
    if looping and span > EPSILON:
        base = loop_end - first
        while base < length - EPSILON:
            for time, pitch, duration, velocity in raw:
                if loop_start - EPSILON <= time < loop_end - EPSILON:
                    add(base + time - loop_start, pitch, duration, velocity)
            base += span
    out.sort(key=lambda n: (n.time, n.pitch))
    return out, (span if looping else 0.0)


def _clips(parent: ET.Element | None, kind: str) -> list[Clip]:
    out = []
    if parent is None:
        return out
    tag = "MidiClip" if kind == "midi" else "AudioClip"
    for el in parent.iter(tag):
        start, end = _number(el, "CurrentStart"), _number(el, "CurrentEnd")
        if end <= start:
            continue
        clip = Clip(_value(el, "Name"), start, end, kind)
        if kind == "midi":
            clip.notes, clip.loop_beats = clip_notes(el, end - start)
        else:
            ref = el.find(".//SampleRef/FileRef")
            clip.file = (_value(ref, "RelativePath") or _value(ref, "Path")).replace("\\", "/").split("/")[-1]
        out.append(clip)
    out.sort(key=lambda c: c.start)
    return out


def _devices(chain: ET.Element | None) -> list[Device]:
    out = []
    if chain is None:
        return out
    for el in chain:
        tag = el.tag
        if tag.endswith("PluginDevice"):
            name = _value(el, ".//PluginDesc//PlugName") or _value(el, ".//PluginDesc//Name") or tag
            out.append(Device(f"{'AU' if tag.startswith('Au') else 'VST'}: {name}", _value(el, "UserName")))
            continue
        device = Device(DEVICE_NAMES.get(tag, tag), _value(el, "UserName"))
        if tag == "DrumGroupDevice":
            for branch in el.findall("Branches/DrumBranch"):
                note = 128 - int(_number(branch.find("ZoneSettings"), "ReceivingNote", 128))  # stored inverted
                device.pads.append(Pad(note, _value(branch, "Name/EffectiveName") or _value(branch, "Name/UserName")))
        out.append(device)
    return out


def _track_scale(clips: list[Clip], track_el: ET.Element) -> tuple[int, str] | None:
    """The scale Live 12 stores on clips that are 'in key' (Root + Name index), when one is set."""
    for el in track_el.iter("MidiClip"):
        if _value(el, "IsInKey") != "true":
            continue
        info = el.find("ScaleInformation")
        if info is not None:
            return int(_number(info, "Root")), _value(info, "Name")
    return None


def _children(el: ET.Element, tag: str) -> list[ET.Element]:
    found = el.find(tag)
    return list(found) if found is not None else []


def read(path: str | Path) -> Song:
    path = Path(path)
    try:
        root = ET.fromstring(gzip.open(path).read())
    except (OSError, EOFError, ET.ParseError) as exc:
        raise AlsError(f"{path.name} is not a readable Live Set ({exc})") from exc
    live = root.find("LiveSet")
    if root.tag != "Ableton" or live is None:
        raise AlsError(f"{path.name} is not a Live Set")
    main = live.find("MainTrack")
    if main is None:
        main = live.find("MasterTrack")  # Live 11 and older
    tempo = _number(main, "DeviceChain/Mixer/Tempo/Manual", 120.0)
    # Live stores the signature as one number: numerator - 1 + 99 * denominator index (201 = 4/4)
    code = int(_number(main, "DeviceChain/Mixer/TimeSignature/Manual", 201))
    beats_per_bar = (code % 99 + 1) * 4 / 2 ** (code // 99)
    tracks: list[Track] = []
    kinds = {"MidiTrack": "midi", "AudioTrack": "audio", "GroupTrack": "group", "ReturnTrack": "return"}  # Live puts returns in Tracks
    for el in _children(live, "Tracks"):
        if el.tag not in kinds:
            continue
        kind = kinds[el.tag]
        track = Track(len(tracks), int(el.get("Id", -1)), kind, _value(el, "Name/EffectiveName"),
                      int(_number(el, "TrackGroupId", -1)))
        track.devices = _devices(el.find("DeviceChain/DeviceChain/Devices"))
        sequencer = el.find("DeviceChain/MainSequencer")
        if kind in ("midi", "audio"):
            arranger = sequencer.find("ClipTimeable/ArrangerAutomation") if sequencer is not None else None
            if arranger is None:  # an audio track keeps its clips in Sample/ArrangerAutomation
                arranger = el.find("DeviceChain/MainSequencer/Sample/ArrangerAutomation")
            track.clips = _clips(arranger, kind)
            slots = sequencer.find("ClipSlotList") if sequencer is not None else None
            track.session_clips = _clips(slots, kind)
        track.scale = _track_scale(track.clips, el) if kind == "midi" else None
        tracks.append(track)
    locators = [Locator(_number(el, "Time"), _value(el, "Name"))
                for el in live.findall("Locators/Locators/Locator")]
    locators.sort(key=lambda loc: loc.beat)
    return Song(str(path), path.stem, root.get("Creator", ""), tempo, beats_per_bar, tracks, locators,
                _devices(main.find("DeviceChain/DeviceChain/Devices") if main is not None else None))
