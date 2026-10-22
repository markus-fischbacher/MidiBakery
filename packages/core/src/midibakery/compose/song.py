"""A whole song in the Arrangement View from a genre template.

``build_song`` reads the Set, maps the roles (drums, bass, chords, lead) to
tracks, generates every section's parts with the existing generators and
returns a :class:`SongPlan`: new tracks, arrangement clips with notes, locators.
Nothing changes in Live until ``apply_song``.

- A ``reference`` (a song the Reference Analyzer device analyzed) sets the section
  order and lengths, snapped to the genre's bar grid; each section plays the genre's
  section of the same kind. With ``set_tempo`` the song takes the reference's tempo and key.
  Without ``start_bar`` it starts under the reference's clip when its tracks are free there.
- Roles go to existing tracks first: drums to a track with a Drum Rack, the
  others by track name (bass/sub/808, chord/pad/keys, lead/melody/synth).
  Missing roles get a new track with the genre's Core Library kit or preset
  (``sounds``), loaded after a native device that stays if the load fails; the
  drum notes then move to the loaded kit's pads.
- One harmony for the song, a second one for breaks. Sections of the same kind
  share their notes; a section with ``variation`` gets its own.
- Drums, bass and chords come from the genre's recipes (grooves.py), the lead from
  hook, arp or acid. Energy sets velocity.
- A session clip can stand in for a role (``clips``): it is copied, looped, into
  every section where that role plays.
- Nothing lands on top of an existing arrangement clip: the plan refuses and
  names the first free bar instead.
- Automation: a role the style filters gets an Auto Filter (the track's last one,
  else a new one at the end of its chain) and every one of its clips an envelope
  of the cutoff, so a sweep never carries over into the next section. A track
  that has an Auto Filter already gets open envelopes where the style has no sweep.
- Mix (``mix``): a Reverb and a Delay return, the Set's own if it has them, else new
  ones set to the genre's decay and delay time. New tracks get the genre's fader
  levels and sends; existing tracks keep their faders and get sends only to returns
  the song creates.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import random
import secrets
from dataclasses import dataclass, field, replace
from typing import Annotated, Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator

from midibakery.bridge.client import BridgeError
from midibakery.compose import harmony as harmony_mod
from midibakery.compose.drums import DrumMap, map_pads
from midibakery.compose.harmony import Harmony
from midibakery.compose.notes import Note, fit_to_length
from midibakery.compose.plan import Call, Session, is_drum_track, new_seed
from midibakery.compose.rhythm import Meter
from midibakery.compose.rollback import batch_steps, completed, restore_locators, undo, undo_batch
from midibakery.compose.bass_templates import BASS_TEMPLATES, BassTemplate, generate_bass_template
from midibakery.compose.grooves import BASS, CHORDS, GROOVE_VARIANTS, GROOVES, Groove, generate_groove, generate_recipe_bass, generate_recipe_chords, seventh_harmony
from midibakery.compose.hook import generate_acid, generate_arp, generate_hook, make_acid, make_arp, make_hook
from midibakery.compose import user_patterns
from midibakery.compose.lead_templates import generate_lead_template
from midibakery.compose.references import find_reference, load_references, reference_scale
from midibakery.compose.techno_templates import generate_techno_drums
from midibakery.compose.structures import FX_ROLES, ROLES, TEMPLATES, Mix, Section, Template, from_reference, parse_segments, sized
from midibakery.compose.theory import Scale, diatonic_chord

NEW_TRACK_DEVICES = {"drums": "Drum Rack", "bass": "Drift", "chords": "Wavetable", "lead": "Operator", "riser": "Operator", "impact": "Operator", "sidechain": "Operator"}
ROLE_WORDS = {
    "bass": ("bass", "sub", "808"),
    "chords": ("chord", "pad", "keys", "piano", "stab"),
    "lead": ("lead", "melody", "synth", "arp", "pluck"),
    "riser": ("riser", "uplift"),
    "impact": ("impact", "boom"),
    "sidechain": ("sidechain", "trigger"),
}
TRIGGER_PITCH = 48  # the sidechain track's notes: a short Operator sine nobody hears
PHRASE = 8  # bars
FILTER_TYPES = {"Low-pass": 0, "High-pass": 1}  # Auto Filter (Live 12) "Filter Type" values
OPEN_HZ = {"Low-pass": 20000.0, "High-pass": 20.0}
EPSILON = 1e-6


class UseClip(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["drums", "bass", "chords", "lead"]
    track: Annotated[int, Field(ge=0)]
    slot: Annotated[int, Field(ge=0)]

    @model_validator(mode="before")
    @classmethod
    def _slot_is_an_index(cls, data):
        if isinstance(data, dict) and isinstance(data.get("slot"), str) and not data["slot"].strip().isdigit():
            raise ValueError(f"clips.slot must be a clip slot index of a Session track, not the name {data['slot']!r}. "
                             "To use the loops of an imported Set, give loops_from (e.g. {\"bass\": \"<Set name>\"}) instead of clips")
        return data


class SongRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    genre: Literal["house", "melodic_techno", "peak_time_techno", "drum_and_bass", "trap"] | None = Field(
        None, description="Required, unless a reference is given: then the reference's genre, or one guessed from its tempo")
    length: Literal["radio", "standard", "extended"] = Field("standard", description="Or minutes for a duration ('3 minutes' -> minutes 3)")
    minutes: Annotated[float, Field(ge=0.5, le=20, description="Target duration; overrides length")] | None = None
    start_bar: Annotated[int, Field(ge=1, description="Arrangement bar to start at (default: after the last clip, or under the reference)")] | None = None
    roles: dict[Literal["drums", "bass", "chords", "lead", "riser", "impact", "sidechain"], Annotated[int, Field(ge=0)]] = Field(
        default_factory=dict, description="Role -> track index; others are found by Drum Rack or track name"
    )
    clips: list[UseClip] = Field(default_factory=list, description="Session clips to use for a role instead of generating it")
    create_missing: bool = Field(True, description="New tracks for roles no track has")
    sounds: bool = Field(True, description="New tracks get the genre's kit and presets; false: empty Drum Rack and native synths")
    mix: bool = Field(True, description="Reverb and Delay returns, sends and fader levels for new tracks")
    fx: bool = Field(True, description="A riser before each drop and an impact on its first beat (needs sounds)")
    sidechain: bool = Field(True, description="Enable silent-trigger ducking; default pumps through kick rests")
    sidechain_mode: Literal["pumping", "follow_kick"] = Field("pumping", description="Continuous genre pulse or planned drum MIDI kick onsets")
    progression: str | None = Field(None, description="Main chords, e.g. 'i VI III VII'; default: generated")
    set_tempo: bool = Field(False, description="Set the genre's tempo (e.g. House 124, D&B 174); with a reference its tempo and key")
    reference: str | None = Field(None, description="Follow the sections of a song from get_reference (part of its name); overrides length")
    loops_from: dict[Literal["drums", "bass", "lead", "chords"], str] = Field(
        default_factory=dict, description="Take a role's loops from another imported Set (part of its name), e.g. {\"bass\": \"Sound as a Pound\"}")
    fill_missing: bool = Field(False, description="With an imported Set: also play roles the Set lacks, from the genre")
    my_loops: bool = Field(False, description="The seed draws loops for the roles from the user's imported Sets")
    seed: Annotated[int, Field(ge=0)] | None = None
    _genre_note: str = PrivateAttr("")

    @model_validator(mode="after")
    def _genre_from_reference(self) -> SongRequest:
        if self.genre:
            return self
        found = find_reference(self.reference) if self.reference else None
        if not found:
            if self.reference:
                raise ValueError(f"No analyzed reference matches '{self.reference}'; get_reference lists them")
            raise ValueError("genre: Field required (or give a reference)")
        self.genre, self._genre_note = _reference_genre(found)
        return self


def _reference_genre(reference: dict[str, Any]) -> tuple[str, str]:
    """The genre of a reference: the one set on it, else a guess from its tempo (an imported Set has none unless chosen)."""
    if reference.get("genre") in TEMPLATES:
        return reference["genre"], ""
    tempo = float(reference.get("tempo") or 0)
    genre = ("drum_and_bass" if tempo >= 165 else "trap" if 138 <= tempo < 152 else "peak_time_techno" if 126 <= tempo < 138
             else "house")
    return genre, f"No genre given: took {genre} from the reference's tempo ({round(tempo)} BPM); name a genre to change it"


@dataclass
class RoleTrack:
    role: str
    index: int
    name: str
    new: bool = False
    device: str | None = None
    sound: tuple[str, ...] | None = None  # browser path loaded onto a new track
    filter: str | None = None  # Auto Filter type the song sweeps
    filter_device: int | None = None  # its index on the track
    filter_new: bool = False
    resonance: bool = False  # the song rides the Auto Filter's resonance too
    throws: tuple[str, ...] = ()  # section kinds with delay throws
    duck: float | None = None  # sidechain: threshold in dB of a Compressor keyed from the kick
    duck_device: int | None = None  # its index on the track
    duck_new: bool = False


@dataclass
class ReturnPlan:
    kind: str  # "reverb" or "delay"
    index: int
    name: str
    new: bool = False


@dataclass
class SongPlan:
    id: str
    template: Template
    sections: tuple[Section, ...]
    starts: list[float]  # beat of each section
    start: float
    end: float
    roles: dict[str, RoleTrack]
    actions: list[dict[str, Any]]
    locators: list[dict[str, Any]]
    tempo: float | None
    seed: int
    scale: str
    meter: str
    beats_per_bar: float
    track_identity: tuple
    bpm: float = 120.0  # the tempo the song will play at (the Set's, or the genre's with set_tempo)
    harmony: dict[str, list[str]] = field(default_factory=dict)
    notes: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    mix: Mix | None = None
    returns: dict[str, ReturnPlan] = field(default_factory=dict)
    return_identity: tuple = ()
    fx: dict[str, dict[str, str]] = field(default_factory=dict)  # section name -> FX role -> what plays
    key: Scale | None = None  # set in Live with the plan (a reference's key with set_tempo)
    reference: str | None = None  # the analyzed song the sections follow
    sidechain_mode: str = "pumping"
    sidechain_source: dict[str, Any] | None = None
    reuse: dict[str, dict[str, Any]] = field(default_factory=dict)  # role -> copied Session clip and how it is placed

    def mix_info(self) -> dict[str, Any]:
        if self.mix is None:
            return {}
        mix = self.mix
        returns = {}
        for kind, r in self.returns.items():
            setting = f"{mix.decay:g} s" if kind == "reverb" else f"{mix.delay_16ths}/16, feedback {round(mix.feedback * 100)} %"
            returns[kind] = f"return index {r.index} '{r.name}'" + (f" (new, {setting})" if r.new else " (the Set's)")
        levels = {}
        for role, t in self.roles.items():
            volume = self._volume(role)
            parts = [f"fader {volume:g} dB"] if t.new and volume is not None else []
            parts += [f"{kind} {db:g} dB" for kind, db in self._sends(role, t)]
            if parts:
                levels[role] = ", ".join(parts)
        return {"mix": {"returns": returns, "levels": levels}}

    def _volume(self, role: str) -> float | None:
        """A new track's fader: the genre's level for its role."""
        assert self.mix is not None
        return self.mix.volume.get(role)

    def _sends(self, role: str, t: RoleTrack) -> list[tuple[str, float]]:
        """(return kind, dB) a role's track sends: a new track to both returns, an existing one only to new returns."""
        assert self.mix is not None
        sends = []
        for kind, levels in (("reverb", self.mix.reverb), ("delay", self.mix.delay)):
            r = self.returns.get(kind)
            if r is not None and role in levels and (t.new or r.new):
                sends.append((kind, levels[role]))
        return sends

    def mix_ops(self) -> list[dict[str, Any]]:
        """New returns with their device settings, then faders and sends: part of the tracks batch."""
        if self.mix is None:
            return []
        ops: list[dict[str, Any]] = []
        for kind, r in sorted(self.returns.items(), key=lambda kv: kv[1].index):
            if not r.new:
                continue
            ops.append({"op": "return.create", "params": {"name": r.name, "device": RETURN_DEVICES[kind]}})
            for parameter, value in _return_params(kind, self.mix):
                ops.append({"op": "device.set_param", "params": {"return_track": r.index, "device": 0, "parameter": parameter, "value": value}})
        for role, t in self.roles.items():
            params: dict[str, Any] = {}
            if t.new and self._volume(role) is not None:
                params["volume_db"] = self._volume(role)
            sends = [{"return_track": self.returns[kind].index, "db": db} for kind, db in self._sends(role, t)]
            if sends:
                params["sends"] = sends
            if params:
                ops.append({"op": "mixer.set", "params": {"track": t.index, **params}})
        return ops

    def preview(self) -> dict[str, Any]:
        bpb = self.beats_per_bar
        sections = []
        for section, start in zip(self.sections, self.starts):
            sections.append({
                "name": section.name,
                "bar": int(start / bpb) + 1,
                "bars": section.bars,
                "energy": section.energy,
                "plays": {**{role: part for role, part in section.parts.items() if role in self.roles}, **self.fx.get(section.name, {})},
            })
        return {
            "plan_id": self.id,
            "genre": self.template.label,
            **({"reference": self.reference} if self.reference else {}),
            "scale": self.scale,
            "time_signature": self.meter,
            "tempo": self.tempo,
            "bpm": self.bpm,
            "duration": _duration((self.end - self.start) / self.bpm * 60),
            "bars": int((self.end - self.start) / bpb),
            "from_bar": int(self.start / bpb) + 1,
            "seed": self.seed,
            "tracks": {r: {"track": t.index, "name": t.name, **({"new": True, "device": _sound_name(t.sound) if t.sound else t.device} if t.new else {}), **_filter_info(t)} for r, t in self.roles.items()},
            **({"sidechain_mode": self.sidechain_mode} if "sidechain" in self.roles else {}),
            **self.mix_info(),
            "sections": sections,
            "harmony": self.harmony,
            "notes": self.notes,
            "clips": len(self.actions),
            **({"reuse": self.reuse} if self.reuse else {}),
            "warnings": self.warnings,
            "next": "apply_plan(plan_id) writes the song to the Arrangement View",
        }


RETURN_DEVICES = {"reverb": "Reverb", "delay": "Delay"}
RETURN_MATCH = {"reverb": ("reverb",), "delay": ("delay", "echo")}


DELAY_16THS = (1, 2, 3, 4, 5, 6, 8, 16)  # Delay's "L 16th" choices


def _return_params(kind: str, mix: Mix) -> list[tuple[str, float]]:
    """Raw values for a new return's device, fully wet (measured in Live 12.4): Reverb's
    Decay Time is 200 ms * 300^value, Delay's Feedback 0-1 is 0-95 %."""
    if kind == "reverb":
        decay = min(1.0, max(0.0, math.log(mix.decay / 0.2) / math.log(300)))
        return [("Dry/Wet", 1.0), ("Decay Time", round(decay, 4))]
    return [("Dry/Wet", 1.0), ("Link", 1.0), ("L Sync", 1.0), ("L 16th", float(DELAY_16THS.index(mix.delay_16ths))),
            ("Feedback", round(min(1.0, mix.feedback / 0.95), 4))]


def _plan_returns(returns: list[dict[str, Any]]) -> dict[str, ReturnPlan]:
    """The Set's first Reverb and Delay (or Echo) returns; new returns, appended, for what it lacks."""
    plans: dict[str, ReturnPlan] = {}
    for kind, words in RETURN_MATCH.items():
        found = next((r for r in returns if any(w in d.lower() for d in r.get("devices", []) for w in words)), None)
        if found is not None:
            plans[kind] = ReturnPlan(kind, found["index"], found.get("name", ""))
    for kind in RETURN_DEVICES:
        if kind not in plans:
            plans[kind] = ReturnPlan(kind, len(returns) + sum(r.new for r in plans.values()), RETURN_DEVICES[kind], new=True)
    return plans


def _duration(seconds: float) -> str:
    minutes, rest = divmod(int(round(seconds)), 60)
    return f"{minutes}:{rest:02d}"


def _sound_name(path: tuple[str, ...]) -> str:
    return path[-1].rsplit(".", 1)[0]


THROW_DB = -4.0
QUIET_DB = -70.0  # stands for -inf: the envelope travels as JSON


def _db(display: str | None) -> float:
    text = (display or "").split(" ")[0]
    try:
        return max(QUIET_DB, float(text))
    except ValueError:
        return QUIET_DB


def _throw_levels(roles: dict[str, RoleTrack], style, returns: dict[str, ReturnPlan], mixer: dict[str, Any]) -> dict[str, tuple[str, float]]:
    """Role -> (its send to the Delay return as a mixer envelope target, the send level between throws):
    what the song sets, or what the track's send already is."""
    delay = returns.get("delay")
    if delay is None:
        return {}
    levels = {}
    for role in style.throws:
        t = roles.get(role)
        if t is None:
            continue
        if t.new or delay.new:
            base = style.mix.delay.get(role, QUIET_DB)
        else:
            sends = next((m["sends"] for m in mixer["tracks"] if m.get("index") == t.index), [])
            base = _db(sends[delay.index].get("display")) if delay.index < len(sends) else QUIET_DB
        levels[role] = (f"Send {chr(ord('A') + delay.index)}", base)
    return levels


def _throw_points(section_bars: int, first: int, until: int, bpb: float, base: float) -> list[list[float]]:
    """The send at `base`, up to THROW_DB on the last beat of every 8 bars of the section."""
    points = [[0.0, base]]
    for end in range(PHRASE, until + 1, PHRASE):
        if end <= first:
            continue
        t1 = (end - first) * bpb
        t0 = t1 - 1.0
        points += [[t0 - 0.01, base], [t0, THROW_DB], [t1 - 0.01, THROW_DB], [t1, base]]
    return points


def _filter_info(t: RoleTrack) -> dict[str, str]:
    info = _automation_info(t)
    if t.duck is not None:
        info["sidechain"] = f"Compressor keyed from the sidechain track, threshold {t.duck:g} dB" + (" (new device)" if t.duck_new and not t.new else "")
    return info


def _automation_info(t: RoleTrack) -> dict[str, str]:
    if t.role == "sidechain":
        return {"plays": "Silent trigger notes (fader -inf); sidechain_mode selects continuous pumping or planned kick onsets; Compressors listen Post FX"}
    if t.filter is None:
        return {"throws": f"delay on the last beat of every {PHRASE} bars in {', '.join(t.throws)}"} if t.throws else {}
    info = {"automation": f"Auto Filter {t.filter} cutoff" + (" and resonance" if t.resonance else "") + (" (new device)" if t.filter_new and not t.new else "")}
    if t.throws:
        info["throws"] = f"delay on the last beat of every {PHRASE} bars in {', '.join(t.throws)}"
    return info


def _fraction(hz: float) -> float:
    """Auto Filter's Frequency: 0-1 is 20 Hz-20 kHz, logarithmic (measured in Live 12.4)."""
    return min(1.0, max(0.0, math.log(max(hz, 20.0) / 20.0) / math.log(1000.0)))


def _sweep(spec: str | None, section_bars: int, first: int, clip_length: float, bpb: float, open_hz: float,
           convert: Callable[[float], float] | None = None) -> dict[str, Any]:
    """Envelope points [beat in clip, 0-1] and shapes from a sweep spec ("20:8,20>300"); open without one.
    A segment "a>b~exp" (or ~log) curves, "a>b~sine/2" (or triangle, saw, square) swings between
    a and b every 2 bars; the Remote Script draws those. convert: value -> envelope value
    (default: Hz -> Auto Filter's 0-1 Frequency)."""
    convert = convert or _fraction
    if not spec:
        return {"points": [[0.0, convert(open_hz)]]}
    points: list[list[float]] = []
    shapes: list[dict[str, Any]] = []
    end: tuple[float, float] | None = None  # time and value where the previous segment ended
    for name, offset, bars in parse_segments(spec, section_bars):
        name, _, shape = name.partition("~")
        start_hz, _, end_hz = name.partition(">")
        a = convert(open_hz if start_hz == "-" else float(start_hz))
        b = a if not end_hz else convert(float(end_hz))
        t0 = min(clip_length, max(0.0, (offset - first) * bpb))
        t1 = min(clip_length, max(0.0, (offset + bars - first) * bpb))
        if t1 <= t0:
            continue
        joined = end is not None and abs(end[0] - t0) < EPSILON
        if joined and abs(end[1] - a) > EPSILON:  # type: ignore[index]
            t0 += 0.01  # a jump: Live keeps one value per time
        if shape:
            kind, _, period = shape.partition("/")
            shapes.append({"type": kind, "start": round(t0, 3), "length": round(t1 - t0, 3), "from_value": round(a, 4),
                           "to_value": round(b, 4), **({"period": float(period) * bpb} if period else {})})
            end = (t1, b if kind in ("exp", "log") else a)  # a wave ends near its start value
            continue
        if not joined or abs(end[1] - a) > EPSILON:  # type: ignore[index]
            points.append([round(t0, 3), round(a, 4)])
        points.append([round(t1, 3), round(b, 4)])
        end = (t1, b)
    envelope: dict[str, Any] = {"points": points} if points else {}
    if shapes:
        envelope["shapes"] = shapes
    return envelope or {"points": [[0.0, convert(open_hz)]]}


def pump_steps(genre: str) -> tuple[int, ...]:
    """16th steps (0-based) of the genre's main kick: where the trigger track plays."""
    lanes = [lane for lane in GROOVES[genre].lanes if lane.role == "kick" and lane.probability >= 1 and lane.cycle == 1]
    return tuple(sorted({step - 1 for lane in lanes for step in lane.steps}))


def _trigger_clip(t: RoleTrack, genre: str, start: float, end: float, bpb: float) -> dict[str, Any]:
    """One clip over the whole song: a 1/16 note on every kick step, also where the kick rests."""
    steps = pump_steps(genre)
    notes = [Note(TRIGGER_PITCH, bar * bpb + step * 0.25, 0.25, 127).to_spec() for bar in range(round((end - start) / bpb)) for step in steps]
    return {"action": "add_clip", "track": t.index, "start": start, "length": end - start, "name": "Sidechain", "notes": notes}


def _kick_trigger_clip(t: RoleTrack, drums: RoleTrack, actions: list[dict[str, Any]], kick: int,
                       source: dict[str, Any] | None, start: float, end: float) -> dict[str, Any]:
    """Follow the final planned drum notes, including pauses, fills and copied Session clips."""
    onsets: set[float] = set()
    for action in actions:
        if action.get("track") != drums.index:
            continue
        copied = action["action"] == "copy_session_clip"
        notes = source["notes"] if copied and source is not None else action.get("notes", [])
        length = source["clip"]["length"] if copied and source is not None else action.get("length", 0)
        for note in notes:
            if note["pitch"] != kick or note.get("mute") or note.get("velocity", 100) <= 0:
                continue
            if note.get("probability", 1) != 1:
                raise BridgeError("UNSUPPORTED", "follow_kick needs deterministic kick notes: remove note probability "
                                  "from the source clip or use sidechain_mode='pumping'")
            time = note["start_time"]
            if 0 <= time < length - EPSILON:
                onsets.add(round(action["start"] + time - start, 6))
    notes = [Note(TRIGGER_PITCH, at, min(0.25, end - start - at), 127).to_spec()
             for at in sorted(onsets) if 0 <= at < end - start - EPSILON]
    return {"action": "add_clip", "track": t.index, "start": start, "length": end - start,
            "name": "Sidechain", "notes": notes}


async def _kick_source(call: Call, track: int, slot: int) -> dict[str, Any]:
    clip = await call("clip.get", {"track": track, "slot": slot})
    if (not clip["is_midi"] or abs(clip["start_marker"]) > EPSILON or abs(clip["loop_start"]) > EPSILON
            or abs(clip["loop_end"] - clip["length"]) > EPSILON):
        raise BridgeError("UNSUPPORTED", "follow_kick needs a MIDI source clip starting at 0 with loop_end=length; "
                          "consolidate the clip first or use sidechain_mode='pumping'")
    return {"track": track, "slot": slot, "clip": clip,
            "notes": (await call("notes.get", {"track": track, "slot": slot}))["notes"]}


def _compressor(track: dict[str, Any]) -> int | None:
    devices = track.get("devices", [])
    return next((d.get("index", i) for i, d in reversed(list(enumerate(devices))) if str(d.get("class_name", "")).startswith("Compressor")), None)


def _duck_params(threshold: float, release: float) -> list[tuple[str, float | str]]:
    """Compressor settings for a pump: fast attack, back up before the next kick."""
    return [("Threshold", threshold), ("Ratio", 4.0), ("Attack", 0.001), ("Release", release), ("S/C EQ On", "Off"), ("S/C On", "On")]


def _auto_filter(track: dict[str, Any]) -> int | None:
    devices = track.get("devices", [])
    return next((d.get("index", i) for i, d in reversed(list(enumerate(devices))) if str(d.get("class_name", "")).startswith("AutoFilter")), None)


def _assign_roles(session: Session, request: SongRequest) -> tuple[dict[str, RoleTrack], list[str]]:
    tracks = session.tracks
    roles: dict[str, RoleTrack] = {}
    used: set[int] = set()
    warnings: list[str] = []
    for role, index in request.roles.items():
        track = session.track(index)
        if track.get("kind") != "midi":
            raise BridgeError("INVALID_PARAMS", f"roles.{role}: track index {index} '{track.get('name')}' is not a MIDI track")
        roles[role] = RoleTrack(role, index, track.get("name", ""))
        used.add(index)
    for clip in request.clips:
        redirected = request.roles.get(clip.role)
        if redirected is not None and redirected != clip.track:
            raise BridgeError(
                "INVALID_PARAMS",
                f"clips: the {clip.role} clip is on track index {clip.track}, but roles.{clip.role} puts {clip.role} on track index {redirected}. "
                f"Copies stay on their source's track: use the same track or leave roles.{clip.role} out.",
            )
        if clip.role not in roles:
            roles[clip.role] = RoleTrack(clip.role, clip.track, session.track(clip.track).get("name", ""))
            used.add(clip.track)
    template = TEMPLATES[request.genre]
    wanted: tuple[str, ...] = ROLES
    if request.fx and any(s.kind == "drop" for s in template.sections):
        if request.sounds:
            wanted += FX_ROLES
        else:
            warnings.append("No riser or impact: they need the genre's presets (sounds=false)")
    if request.sidechain and template.style.mix.duck:
        wanted += ("sidechain",)
    for role in wanted:
        if role in roles:
            continue
        candidates = [t for t in tracks if t["index"] not in used and t.get("kind") == "midi"]
        if role == "drums":
            match = next((t for t in candidates if is_drum_track(t)), None)
        else:
            words = ROLE_WORDS[role]
            match = next((t for t in candidates if not is_drum_track(t) and any(w in t.get("name", "").lower() for w in words)), None)
        if match is not None:
            roles[role] = RoleTrack(role, match["index"], match.get("name", ""))
            used.add(match["index"])
    missing = [r for r in wanted if r not in roles]
    if missing and not request.create_missing:
        warnings.append(f"No track for {', '.join(missing)}: those parts are left out (create_missing=false)")
        return roles, warnings
    devices = {**NEW_TRACK_DEVICES, **template.style.devices}
    for offset, role in enumerate(missing):
        sound = template.style.sounds.get(role) if request.sounds else None
        roles[role] = RoleTrack(role, len(tracks) + offset, role.title(), new=True, device=devices[role], sound=sound)
        if role == "drums" and sound is None:
            warnings.append("The new drum track gets an empty Drum Rack: drop a kit on it")
    return roles, warnings


ANSWER_BEATS = 2.0  # the shortest rest per 4-bar lead phrase that counts as an answer
REST = 1.0  # beats of silence that make a phrase rest


def phrase_rests(notes: list[Note], length: float, min_gap: float = REST) -> list[tuple[float, float]]:
    """Spans of `min_gap` beats or more in which no note sounds and none is about to: the staccato gaps of a
    riff (shorter than `min_gap`) belong to its phrase."""
    spans: list[list[float]] = []
    for n in sorted(notes, key=lambda n: n.start_time):
        if spans and n.start_time - spans[-1][1] < min_gap - EPSILON:
            spans[-1][1] = max(spans[-1][1], n.end_time)
        else:
            spans.append([n.start_time, n.end_time])
    rests, cursor = [], 0.0
    for start, end in spans:
        if start - cursor >= min_gap - EPSILON:
            rests.append((cursor, start))
        cursor = max(cursor, end)
    if length - cursor >= min_gap - EPSILON:
        rests.append((cursor, length))
    return rests


def _answer_space(notes: list[Note], meter: Meter, bars: int, offset_bars: int) -> list[Note]:
    """A lead that plays through a 4-bar phrase (an arp, an acid line) rests in its last bar: a
    call-and-response the ear follows. Phrases that already rest stay."""
    bpb = meter.beats_per_bar
    for last in range(3, bars):
        if (offset_bars + last) % 4 != 3:
            continue
        start, end = (last - 3) * bpb, (last + 1) * bpb
        phrase = [replace(n, start_time=n.start_time - start) for n in notes if start - EPSILON <= n.start_time < end - EPSILON]
        if any(b - a >= ANSWER_BEATS - EPSILON for a, b in phrase_rests(phrase, end - start)):
            continue
        cut = last * bpb
        notes = [replace(n, duration=cut - n.start_time) if n.start_time < cut - EPSILON < n.end_time - EPSILON else n
                 for n in notes if not cut - EPSILON <= n.start_time < end - EPSILON]
    return notes


def _energize(notes: list[Note], energy: float, low: float = 0.85) -> list[Note]:
    """Velocity by section energy: `low` of it at energy 0, all of it at 1 (the grooves give the drums as much range)."""
    factor = low + (1 - low) * energy
    return [replace(n, velocity=max(1.0, min(127.0, n.velocity * factor))) for n in notes]


def _free_from(arrangement: dict[str, Any], track_indices: set[int]) -> float:
    ends = [c["end"] for t in arrangement.get("tracks", []) if t["index"] in track_indices for c in t["clips"]]
    return max(ends + [0.0])


def _overlap(arrangement: dict[str, Any], track: int, start: float, end: float) -> dict[str, Any] | None:
    for t in arrangement.get("tracks", []):
        if t["index"] != track:
            continue
        for clip in t["clips"]:
            if clip["start"] < end - EPSILON and start < clip["end"] - EPSILON:
                return clip
    return None


def _under_reference(reference: dict[str, Any], bpb: float) -> float:
    """The arrangement beat of the reference's first section, on a bar line."""
    first = reference["sections"][0]
    beat = first.get("beat")
    if beat is None:
        beat = (int(reference.get("first_bar") or 1) - 1) * bpb
    return max(0.0, round(float(beat) / bpb) * bpb)


def _check_unwarped(reference: dict[str, Any], tempo: float) -> None:
    """An unwarped reference plays in real time at its own tempo: its bars line up with the song's only
    when the song plays at that tempo too; otherwise the sections drift apart bar by bar."""
    own = reference.get("tempo")
    if reference.get("bar_grid") != "song" or not own or abs(float(own) - tempo) < 0.05:
        return
    beats = (int(reference.get("bars") or 0)) * 4
    drift = abs(beats * 60 / tempo - beats * 60 / float(own))
    raise BridgeError(
        "INVALID_PARAMS",
        f"The reference '{reference.get('name')}' is not warped: it plays at its own {float(own):g} BPM while the song "
        f"would play at {tempo:g} BPM, so the sections drift apart (by {drift:.0f} s at its end). Press Analyze in the "
        "MidiBakery Reference Analyzer device: it warps the clip onto the Set's grid. Or plan with set_tempo=true.",
        {"reference_tempo": float(own), "tempo": tempo},
    )


def _from(harmony: Harmony, start: float, length: float) -> Harmony:
    """The part of a harmony from `start` for `length` beats, shifted to begin at 0."""
    segments = []
    for segment in harmony.segments:
        begin, end = max(segment.start, start), min(segment.end, start + length)
        if end > begin + EPSILON:
            segments.append(harmony_mod.Segment(begin - start, end - begin, segment.chord))
    return Harmony(tuple(segments), harmony.source, harmony.explicit)


SOURCE_TIMING = ("length", "looping", "loop_start", "loop_end", "start_marker", "end_marker")
NOTE_KEYS = ("pitch", "start_time", "duration", "velocity", "probability", "velocity_deviation", "mute")


@dataclass(frozen=True)
class ClipSource:
    """A reused Session clip as the song reads it: its playing window and the notes inside it."""
    track: int
    slot: int
    length: float
    timing: dict[str, Any]
    window: float  # where the playing window starts inside the clip's own time
    notes: tuple[dict[str, Any], ...]  # shifted so the window starts at 0
    has_envelopes: bool | None  # None: the Remote Script cannot say
    start_offset: bool  # it begins playing away from the loop start: copies are not the window's notes

    @property
    def fingerprint(self) -> str:
        payload = json.dumps([self.timing, [[n.get(k) for k in NOTE_KEYS] for n in self.notes]], sort_keys=True, default=str)
        return hashlib.sha1(payload.encode()).hexdigest()[:16]


async def _read_source(call: Call, track: int, slot: int) -> ClipSource:
    clip = await call("clip.get", {"track": track, "slot": slot})
    notes = (await call("notes.get", {"track": track, "slot": slot}))["notes"]
    looping = bool(clip.get("looping", True))
    window = float(clip["loop_start"] if looping else clip["start_marker"])
    # The playing window: the loop for a looping clip, else start to end marker (equal to `length` in Live)
    length = float(clip["loop_end"] - clip["loop_start"] if looping else clip["end_marker"] - clip["start_marker"])
    if length <= EPSILON:
        length = float(clip["length"])
    inside = []
    for n in sorted(notes, key=lambda n: (n["start_time"], n["pitch"])):
        if window - EPSILON <= n["start_time"] < window + length - EPSILON:
            inside.append({k: n[k] for k in NOTE_KEYS if k in n} | {"start_time": round(n["start_time"] - window, 6)})
    start_offset = looping and abs(float(clip["start_marker"]) - float(clip["loop_start"])) > EPSILON
    return ClipSource(track, slot, length, {k: clip.get(k) for k in SOURCE_TIMING}, window, tuple(inside), clip.get("has_envelopes"), start_offset)


def _fragment(source: ClipSource, length: float) -> list[dict[str, Any]]:
    """The first `length` beats of the source's window as notes (cut at the end, never changing the source)."""
    kept = []
    for n in source.notes:
        if n["start_time"] < length - EPSILON:
            kept.append(n | {"duration": round(min(n["duration"], length - n["start_time"]), 6)})
    return kept


def _shift(harmony: Harmony, by: float) -> list[harmony_mod.Segment]:
    return [harmony_mod.Segment(s.start + by, s.length, s.chord) for s in harmony.segments]


def _follow_clip(clip_harmony: Harmony, playing: list[tuple[str, int, int]], meter: Meter, bars: int) -> Harmony:
    """A section's harmony from a copied chord clip: each copied part restarts the clip's chords at its own
    first beat; where no chord clip plays, the clip's chords run on from the section start."""
    bpb = meter.beats_per_bar
    base = clip_harmony.for_length(meter, bars)
    segments: list[harmony_mod.Segment] = []
    cursor = 0
    for _, offset, count in sorted(playing, key=lambda p: p[1]):
        if offset > cursor:
            segments += _shift(_from(base, cursor * bpb, (offset - cursor) * bpb), cursor * bpb)
        segments += _shift(clip_harmony.for_length(meter, count), offset * bpb)
        cursor = offset + count
    if cursor < bars:
        segments += _shift(_from(base, cursor * bpb, (bars - cursor) * bpb), cursor * bpb)
    return Harmony(tuple(segments), clip_harmony.source, clip_harmony.explicit)


def _chord_loop(reference: dict[str, Any] | None, loops_from: dict[str, str]) -> dict[str, Any] | None:
    """The chord loop of the Set that sets the structure (or that loops_from names for chords), if it has one."""
    source = reference
    if "chords" in loops_from:
        source = find_reference(loops_from["chords"])
        if source is None:
            raise BridgeError("NOT_FOUND", f"loops_from.chords: no imported reference matches '{loops_from['chords']}'; get_reference lists them")
    if source is None or source.get("bar_grid") != "als":
        if "chords" in loops_from:
            raise BridgeError("INVALID_PARAMS", f"loops_from.chords: '{source.get('name') if source else ''}' is not an imported Set")
        return None
    entries = [e for e in user_patterns.entries() if e["set"] == source.get("id") and e["kind"] == "chords"]
    if not entries and "chords" in loops_from:
        others = sorted({e["set_name"] for e in user_patterns.entries() if e["kind"] == "chords"})
        raise BridgeError("INVALID_PARAMS", f"loops_from.chords: '{source.get('name')}' has no chord loop (import it again"
                          + (f"; Sets with one: {', '.join(others)}" if others else ", or pick another Set") + ")")
    return entries[0] if entries else None


def _harmonies(request: SongRequest, style, scale: Scale, meter, r: random.Random, chord_loop: dict[str, Any] | None = None) -> tuple[Harmony, Harmony, Harmony | None]:
    """Main loop, break loop and the loop for the second half of a long drop: the request's progression, a Set's
    chord loop, or different genre loops."""
    pool = list(style.progressions["minor" if _is_minor(scale) else "major"]) if len(scale) == 7 else []
    candidates = [harmony_mod.timeline([diatonic_chord(scale, d) for d in degrees], meter, 8, style.chords_per_bar, "progression") for degrees in pool]
    if pool:  # the chord loops of the user's Sets tagged with this genre join the genre's own
        candidates += _genre_chord_loops(request.genre, scale, meter)
    r.shuffle(candidates)
    loops = candidates[:2]
    turn = candidates[2] if len(candidates) > 2 and request.genre != "peak_time_techno" else None  # Peak-Time's drop keeps one home chord (its recipe)
    if not loops:  # pentatonic and other scales: the generic generator
        loops = [harmony_mod.auto(scale, meter, 8, style.chords_per_bar, r) for _ in range(2)]
    if len(loops) == 1:
        loops.append(loops[0])
    if request.progression:
        try:
            loops[0] = replace(harmony_mod.from_progression(request.progression, scale, meter, 8, style.chords_per_bar), explicit=True)
        except ValueError as exc:
            raise BridgeError("INVALID_PARAMS", str(exc)) from None
    elif chord_loop is not None:
        mode = Scale(scale.root, (0, 2, 4, 5, 7, 9, 11) if chord_loop.get("scale") == "major" else (0, 2, 3, 5, 7, 8, 10), "")
        loops[0] = replace(harmony_mod.from_progression(chord_loop["progression"], mode, meter, 8, float(chord_loop.get("chords_per_bar", 1.0))),
                           explicit=True)
    return loops[0], loops[1], turn


# plan_song genre -> the bass templates (bass_templates.py) that suit it besides the genre's own recipe.
BASS_VARIANTS = {
    "house": ("tech_house",),
    "melodic_techno": ("melodic_techno", "progressive"),
    "peak_time_techno": ("peak_time_techno",),
}


def _groove_variant(genre: str, r: random.Random) -> Groove:
    """The genre's drum groove or, by the seed, one of its variants."""
    options = (GROOVES[genre], *GROOVE_VARIANTS.get(genre, ()))
    return options[r.randrange(len(options))]


def _bass_variant(genre: str, tempo: float, r: random.Random) -> BassTemplate | None:
    """The seed picks the song's bass: the genre's own recipe or one of the templates that suit it
    and its tempo (None = the recipe). Without a fitting template the recipe stays."""
    tags = BASS_VARIANTS.get(genre, ())
    pool = [t for t in BASS_TEMPLATES.values() if set(t.genres) & set(tags) and t.bpm[0] - 4 <= tempo <= t.bpm[1] + 4]
    return r.choice([None, *pool]) if pool else None


def _genre_chord_loops(genre: str, scale: Scale, meter) -> list[Harmony]:
    """Chord loops of imported Sets whose genre (set in the Set Importer) is `genre` and whose mode is the song's."""
    minor = "minor" if _is_minor(scale) else "major"
    genres = {r.get("id"): r.get("genre") for r in load_references()}
    out = []
    for e in user_patterns.entries():
        if e["kind"] != "chords" or genres.get(e["set"]) != genre or e.get("scale") != minor:
            continue
        mode = Scale(scale.root, (0, 2, 4, 5, 7, 9, 11) if minor == "major" else (0, 2, 3, 5, 7, 8, 10), "")
        try:
            out.append(harmony_mod.from_progression(e["progression"], mode, meter, 8, float(e.get("chords_per_bar", 1.0))))
        except ValueError:
            continue
    return out


def _is_minor(scale: Scale) -> bool:
    return len(scale.intervals) >= 3 and scale.intervals[2] == 3


def _draw_loops(request: SongRequest, reference: dict[str, Any] | None, seed: int) -> dict[str, str]:
    """role -> the name of an imported Set the seed draws its loops from. Roles that loops_from names, and
    those the reference Set plays with its own loops, are not drawn."""
    own = reference.get("id") if reference is not None and reference.get("bar_grid") == "als" else None
    stored = user_patterns.entries()
    r = random.Random(f"{seed}:my_loops")
    drawn: dict[str, str] = {}
    for role in ROLES:
        if role in request.loops_from or any(e["set"] == own and e["kind"] == role for e in stored):
            continue
        sets = sorted({e["set_name"] for e in stored if e["kind"] == role and e.get("set_name")})
        if sets:
            drawn[role] = r.choice(sets)
    return drawn


def _loops(reference: dict[str, Any] | None, loops_from: dict[str, str]) -> dict[str, tuple[list[dict[str, Any]], bool]]:
    """role -> (the imported Set's loops for it, whether they come from the reference that sets the structure)."""
    out: dict[str, tuple[list[dict[str, Any]], bool]] = {}
    stored = user_patterns.entries()
    for role in ("drums", "bass", "lead"):
        source, same = reference, True
        if role in loops_from:
            source = find_reference(loops_from[role])
            if source is None:
                raise BridgeError("NOT_FOUND", f"loops_from.{role}: no imported reference matches '{loops_from[role]}'; get_reference lists them")
            same = reference is not None and source.get("id") == reference.get("id")
        if source is None or source.get("bar_grid") != "als":
            if role in loops_from:
                raise BridgeError("INVALID_PARAMS", f"loops_from.{role}: '{source.get('name') if source else ''}' is not an imported Set")
            continue
        entries = [e for e in stored if e["set"] == source.get("id") and e["kind"] == role]
        if not entries and role in loops_from:
            raise BridgeError("INVALID_PARAMS", f"loops_from.{role}: '{source.get('name')}' has no {role} loop (import it again, or pick another Set)")
        if entries:
            out[role] = (entries, same)
    return out


def _choose_loop(entries: list[dict[str, Any]], same: bool, index: int, whole: dict[str, Any] | None) -> str:
    """The loop for a section: the one that plays most of the section's own bars in the Set, else the Set's main loop."""
    if not same or whole is None or index >= len(whole.get("sections", [])):
        return entries[0]["name"]
    section = whole["sections"][index]
    first = int(whole.get("set_first_bar") or 1) - 1 + int(section.get("start_bar") or 1) - 1  # the Set's own 0-based bar
    covered = lambda e: sum(max(0, min(first + int(section.get("bars") or 0), o + len(e["bars"])) - max(first, o))  # noqa: E731
                            for o in e.get("occurrences", ()))
    best = max(entries, key=covered)
    return (best if covered(best) > 0 else entries[0])["name"]


def _loop_notes(role: str, name: str, part: str, section: Section, harmony: Harmony, scale: Scale, meter: Meter, bars: int,
                drum_map: DrumMap, kick_pitch: int | None) -> list[Note]:
    """One part of a section from an imported Set's loop: bass and lead follow the song's chords and key."""
    if role == "drums":
        notes = generate_techno_drums(user_patterns.load("drums", name), meter, bars, drum_map)  # type: ignore[arg-type]
        if part == "no_kick":
            notes = [n for n in notes if n.pitch != kick_pitch]
        elif part == "kick_only":
            notes = [n for n in notes if n.pitch == kick_pitch]
        return _energize(notes, section.energy, 0.9)
    if role == "bass":
        parts = generate_bass_template(user_patterns.load("bass", name), harmony, meter, bars)  # type: ignore[arg-type]
        return _energize([n for notes in parts.values() for n in notes], section.energy)
    parts = generate_lead_template(user_patterns.load("lead", name), harmony, scale, meter, bars)  # type: ignore[arg-type]
    notes = [n for notes in parts.values() for n in notes]
    if part in ("tease", "sparse"):
        notes = [replace(n, velocity=max(1.0, n.velocity - 28)) for n in notes]
    return notes


async def build_song(call: Call, request: SongRequest) -> SongPlan:
    session, arrangement, mixer = await asyncio.gather(Session(call).load(), call("arrangement.get", {}), call("mixer.get", {}))
    template = TEMPLATES[request.genre]
    style = template.style
    meter, scale = session.meter, session.scale
    if (meter.numerator, meter.denominator) != (4, 4):
        # The genre grooves are 16-step bars; in another meter they would spill over the bar line.
        raise BridgeError("INVALID_PARAMS", f"plan_song needs 4/4 (the Set is {meter.numerator}/{meter.denominator}); set_song to 4/4 first")
    bpb = meter.beats_per_bar
    tempo = float(session.song.get("tempo", style.tempo))
    new_tempo = style.tempo if request.set_tempo else None
    reference, key = None, None
    if request.reference:
        reference = find_reference(request.reference)
        if reference is None:
            raise BridgeError("NOT_FOUND", f"No analyzed reference matches '{request.reference}'; get_reference lists them")
        if not reference.get("sections"):
            raise BridgeError("INVALID_PARAMS", f"The reference '{reference.get('name')}' has no sections")
        if request.set_tempo:
            new_tempo = float(reference.get("tempo") or style.tempo)
            key = reference_scale(reference.get("key"))
            if key is not None:
                scale = key
    seed = request.seed if request.seed is not None else new_seed()
    drawn = _draw_loops(request, reference, seed) if request.my_loops else {}
    if drawn:
        request = request.model_copy(update={"loops_from": {**drawn, **request.loops_from}})
    if request.set_tempo and reference is None:  # the genre's tempo, a little different each time (+-2 %)
        new_tempo = float(round(style.tempo * (1 + random.Random(f"{seed}:tempo").uniform(-0.02, 0.02))))
    if new_tempo is not None:
        tempo = new_tempo
    if reference is not None:
        _check_unwarped(reference, tempo)
        sections = from_reference(template, reference["sections"], reference.get("bar_grid") == "als",
                                  True if request.fill_missing else frozenset(request.loops_from), frozenset(GROOVES[request.genre].parts))
    else:
        sections = sized(template, request.length, request.minutes, bpb, tempo)

    roles, warnings = _assign_roles(session, request)
    if request._genre_note:
        warnings.append(request._genre_note)
    if request.my_loops:
        warnings.append("my_loops: " + ("; ".join(f"{role} from '{name}'" for role, name in drawn.items()) if drawn
                                         else "no imported loops for the roles: the genre's own patterns"))
    if reference is not None and reference.get("bar_grid") == "als" and not request.fill_missing:
        for role in ROLES:  # the Set's own line-up: a role it never plays gets no track
            if role in roles and role not in request.loops_from and not any(s.parts.get(role) not in (None, "-", "") for s in sections):
                del roles[role]
                sets = sorted({e["set_name"] for e in user_patterns.entries() if e["kind"] == role})
                warnings.append(f"The Set plays no {role}: left out (fill_missing=true plays it from the genre"
                                + (f"; loops_from={{\"{role}\": \"<Set>\"}} takes the {role} of an imported Set: {', '.join(sets)}" if sets else "") + ")")
        for offset, track in enumerate(sorted((t for t in roles.values() if t.new), key=lambda t: t.index)):
            track.index = len(session.tracks) + offset  # a left-out role leaves no gap among the new tracks
    loops = _loops(reference, request.loops_from)
    loop_choice = {(s.name, role): _choose_loop(entries, same, i, reference)
                   for role, (entries, same) in loops.items() for i, s in enumerate(sections)}
    if reference is not None and request.minutes is not None:
        warnings.append("minutes ignored: the reference sets the song's length")
    if reference is not None and reference.get("bar_grid") == "song":
        warnings.append("The reference is not warped: it lines up only at its own tempo. Press Analyze in the Reference "
                        "Analyzer device to warp it; then the tempo can change and its locators stay in place")
    returns = _plan_returns(mixer["returns"]) if request.mix else {}
    throws = _throw_levels(roles, style, returns, mixer)
    for role in throws:
        roles[role].throws = style.throws[role]
    existing = {t.index for t in roles.values() if not t.new}
    length = sum(s.bars for s in sections) * bpb
    under = _under_reference(reference, bpb) if reference is not None and reference.get("bar_grid") != "als" and request.start_bar is None else None
    if request.start_bar is not None:
        start = (request.start_bar - 1) * bpb
    elif under is not None and not any(
            _overlap(arrangement, t.index, under, under + length) for t in roles.values() if not t.new):
        start = under  # under the reference's clip: solo one or the other to compare
    else:
        # After the last clip on any track: songs follow each other, they never play over one another.
        free = _free_from(arrangement, {t["index"] for t in arrangement.get("tracks", [])})
        start = -(-free // bpb) * bpb  # next bar line
        if under is not None:
            warnings.append(f"Not under the reference at bar {int(under / bpb) + 1}: the song's tracks have clips there")
    starts, cursor = [], start
    for section in sections:
        starts.append(cursor)
        cursor += section.bars * bpb
    end = cursor
    for role_track in roles.values():
        if role_track.new:
            continue
        clash = _overlap(arrangement, role_track.index, start, end)
        if clash is not None:
            first_free = -(-_free_from(arrangement, existing) // bpb) + 1
            raise BridgeError(
                "CONFLICT",
                f"Track index {role_track.index} '{role_track.name}' already has '{clash['name'] or 'a clip'}' at beats "
                f"{clash['start']:g}-{clash['end']:g}; start at bar {int(first_free)} or later (or leave start_bar out)",
                {"track": role_track.index, "first_free_bar": int(first_free)},
            )

    def rng(*key: object) -> random.Random:
        return random.Random(":".join(str(k) for k in (seed, *key)))

    main, alt, turn = _harmonies(request, style, scale, meter, rng("harmony"), _chord_loop(reference, request.loops_from))

    drum_map = map_pads(None)
    drums = roles.get("drums")
    if drums is not None and not drums.new:
        drum_map = map_pads(await session.drum_pads(drums.index))
    kick_pitch = drum_map.note("kick")

    use = {c.role: c for c in request.clips}
    sidechain_source = None
    trigger_needed = request.sidechain and request.sidechain_mode == "follow_kick" and "sidechain" in roles
    if trigger_needed:
        if (drums is None or kick_pitch is None or not drums.new and "kick" not in drum_map.detected
                or drums.new and drums.sound is None):
            raise BridgeError("INVALID_PARAMS", "follow_kick needs a drum track with an identifiable kick pad")
        if "drums" in use:
            sidechain_source = await _kick_source(call, use["drums"].track, use["drums"].slot)
    for role, target in roles.items():
        if role in use:
            continue
        kind = style.filters.get(role)
        if kind is None:
            if target.new or _auto_filter(session.track(target.index)) is None:
                continue
            kind = "Low-pass"  # an earlier song's filter would stay where it ended: keep it open
        target.filter = kind
        target.resonance = any(f"{role}.res" in s.sweeps for s in sections)
        if target.new:
            target.filter_device, target.filter_new = 1, True  # after the instrument
        else:
            found = _auto_filter(session.track(target.index))
            target.filter_new = found is None
            target.filter_device = len(session.track(target.index).get("devices", [])) if found is None else found
            if found is not None:
                warnings.append(f"Track index {target.index} '{target.name}': its Auto Filter is set to {kind} for the song's sweeps")
    trigger = roles.get("sidechain")
    if trigger is not None and not trigger.new and not session.track(trigger.index).get("devices"):
        trigger.device = NEW_TRACK_DEVICES["sidechain"]  # an empty track sends no audio to key from
    if trigger is not None:
        for role, threshold in style.mix.duck.items():
            target = roles.get(role)
            if target is None:
                continue
            target.duck = threshold
            after_filter = 1 if target.filter_new else 0
            if target.new:
                target.duck_device, target.duck_new = 1 + after_filter, True  # after the instrument and its filter
            else:
                found = _compressor(session.track(target.index))
                target.duck_new = found is None
                target.duck_device = len(session.track(target.index).get("devices", [])) + after_filter if found is None else found
                if found is not None:
                    warnings.append(f"Track index {target.index} '{target.name}': its Compressor is keyed from the sidechain track for the song")
    loops: dict[str, float] = {}
    sources: dict[str, ClipSource] = {}
    for role, clip in use.items():
        found = next((c for c in session.track(clip.track).get("clips", []) if c["slot"] == clip.slot), None)
        if found is None:
            raise BridgeError("NOT_FOUND", f"clips: no clip in slot index {clip.slot} of track index {clip.track}")
        if found.get("is_midi") is False:
            raise BridgeError("INVALID_PARAMS", f"clips: the clip in slot index {clip.slot} of track index {clip.track} is not a MIDI clip")
        if float(found["length"]) <= EPSILON:
            raise BridgeError("INVALID_PARAMS", f"clips: the clip in slot index {clip.slot} of track index {clip.track} has no length")
        sources[role] = await _read_source(call, clip.track, clip.slot)
        loops[role] = sources[role].length
    reuse: dict[str, dict[str, Any]] = {
        r: {"track": c.track, "slot": c.slot, "clip_beats": loops[r], "copies": 0, "fragments": 0, "uncovered_beats": 0.0,
            "fingerprint": sources[r].fingerprint} for r, c in use.items()}

    clip_harmony: Harmony | None = None
    if "chords" in use:
        source = sources["chords"]
        clip_bars = max(1, math.ceil(source.length / bpb - EPSILON))
        detected, unresolved = harmony_mod.detect_clip(list(source.notes), scale, meter, clip_bars, style.chords_per_bar)
        if len(unresolved) == len(detected.segments):
            warnings.append("clips.chords: no confident chord could be read from the clip (silent or not chordal), "
                            + ("so the given progression drives the bass and lead" if request.progression
                               else "so the bass and lead keep the genre's progression"))
        elif request.progression:
            clash = [i for i, (a, b) in enumerate(zip(detected.segments, main.for_length(meter, clip_bars).segments))
                     if i not in unresolved and a.chord.pitch_classes != b.chord.pitch_classes]
            if clash:
                warnings.append(f"clips.chords plays {', '.join(detected.describe()[i] for i in clash[:4])} where the given progression has "
                                f"{', '.join(main.for_length(meter, clip_bars).describe()[i] for i in clash[:4])}; the progression wins "
                                "for the bass and lead (leave progression out to follow the clip)")
        else:
            clip_harmony = detected
            main = alt = detected
            if unresolved:
                warnings.append(f"clips.chords: no confident chord in segment(s) {', '.join(str(i + 1) for i in unresolved)} of the clip; "
                                "they repeat the previous chord for the bass and lead")

    cache: dict[tuple, list[Note]] = {}
    actions: list[dict[str, Any]] = []
    counts: dict[str, int] = {r: 0 for r in roles}
    groove, bass_pattern, chord_pattern = _groove_variant(request.genre, rng("groove")), BASS[request.genre], CHORDS[request.genre]
    swing = groove.swing
    bass_template = _bass_variant(request.genre, tempo, rng("bass"))
    hook = make_hook(rng("hook"))
    arp = make_arp(rng("arp"))
    acid = make_acid(rng("acid"))

    def part_notes(role: str, part: str, section: Section, harmony: Harmony, bars: int, offset_bars: int) -> list[Note]:
        r = rng(section.kind, section.variation, role, part, bars, offset_bars)
        loop = loop_choice.get((section.name, role))
        if loop is not None and part != "rumble":
            return _loop_notes(role, loop, part, section, harmony, scale, meter, bars, drum_map, kick_pitch)
        if role == "drums":
            return generate_groove(
                groove, part, meter, bars, r, drum_map, section.energy,
                fill_at_end=section.fill and offset_bars + bars == section.bars,
                crash=section.kind == "drop" and offset_bars == 0,
                long_part=bars >= 16 and part == "full",
                phrase_offset=offset_bars,
            )
        if role == "bass":
            if part == "rumble":
                return _rumble(harmony, meter, bars)
            if bass_template is not None:
                return _energize(generate_bass_template(bass_template, harmony, meter, bars)["main"], section.energy)
            return _energize(generate_recipe_bass(bass_pattern, harmony, meter, bars, swing, r), section.energy)
        if role == "chords":
            chords = seventh_harmony(harmony, scale) if chord_pattern.sevenths else harmony
            notes = generate_recipe_chords(chord_pattern, chords, meter, bars, swing, stabs=part in ("stabs", "on", "tease", "accent"), pad=part not in ("tease", "accent"))
            notes = _energize(notes, section.energy)
            if part == "accent":  # one hit to open each phrase (the "signal" in a groove)
                notes = _accents(notes, meter, offset_bars)
            if part == "tease":  # the hook hinted at, quieter (Peak-Time: "die Hook im Intro andeuten")
                notes = [replace(n, velocity=max(1.0, n.velocity - 28)) for n in notes]
            return notes
        low, high = style.lead_range
        tease = part in ("tease", "sparse")
        if style.lead == "arp":
            notes = generate_arp(arp, harmony, scale, meter, bars, swing, low, high, tease, velocity=82 + 12 * section.energy)
        elif style.lead == "acid":
            notes = generate_acid(acid, harmony, meter, bars, low, high, tease, r, lift=section.kind == "drop" and section.variation > 0)
        else:
            flip = section.variation % 2 == 1
            notes = generate_hook(hook, harmony, scale, meter, bars, swing, low, high, tease=tease, velocity=88 + 12 * section.energy, flip=flip)
        return notes if tease else _answer_space(notes, meter, bars, offset_bars)

    section_harmonies: list[Harmony] = []
    for section, at in zip(sections, starts):
        harmony: Harmony = (alt if section.kind == "break" else main).for_length(meter, section.bars)
        if turn is not None and section.kind == "drop" and section.bars >= 16 and section.bars % 2 == 0:  # a long drop turns to other chords for its second half
            half = section.bars // 2
            harmony = Harmony(tuple(main.for_length(meter, half).segments) + tuple(_shift(turn.for_length(meter, half), half * bpb)),
                              main.source, main.explicit)
        if clip_harmony is not None:
            chord_parts = [seg for seg in parse_segments(section.parts.get("chords", ""), section.bars) if seg[0] != "-"] if "chords" in roles else []
            harmony = _follow_clip(clip_harmony, chord_parts, meter, section.bars)
        section_harmonies.append(harmony)
        for role in ROLES:
            spec = section.parts.get(role)
            if spec is None or role not in roles:
                continue
            target = roles[role]
            segments = parse_segments(spec, section.bars)
            playing = [seg for seg in segments if seg[0] != "-"]
            if not playing:
                continue
            first = playing[0][1]
            until = playing[-1][1] + playing[-1][2]  # a part may stop before the section ends
            clip_length = (until - first) * bpb
            if role in use:
                loop, source = loops[role], sources[role]
                for part, offset, bars in playing:
                    span = bars * bpb
                    if section.rest_beats and offset + bars == section.bars:
                        span -= section.rest_beats
                    begin = at + offset * bpb
                    copies = int((span + EPSILON) // loop)
                    for k in range(copies):
                        actions.append({"action": "copy_session_clip", "track": target.index, "slot": use[role].slot, "start": begin + k * loop})
                    reuse[role]["copies"] += copies
                    rest = span - copies * loop
                    if rest <= EPSILON:
                        continue
                    where = f"clips.{role}: the {loop:g}-beat clip would be cut to {rest:g} beats for the end of the {span:g}-beat '{section.name}' part"
                    if source.start_offset:
                        raise BridgeError("UNSUPPORTED", f"{where}, but it starts playing away from its loop start, so the cut's content cannot be "
                                          "determined reliably; set its start marker to its loop start, or pick a clip that divides the span")
                    if source.has_envelopes is not False:
                        raise BridgeError("UNSUPPORTED", f"{where}, but " + ("it has envelopes/automation a cut cannot carry"
                                          if source.has_envelopes else "the Remote Script cannot tell whether it has envelopes (update it)")
                                          + "; use a clip without automation or one whose length divides the span")
                    fragment = _fragment(source, rest)
                    reuse[role]["fragments"] += 1
                    if fragment:
                        actions.append({"action": "add_clip", "track": target.index, "start": begin + copies * loop, "length": rest,
                                        "name": f"{section.name} {role.title()} (cut)", "notes": fragment})
                    message = (f"clips.{role}: the {loop:g}-beat clip is cut to {rest:g} beats for the end of the {span:g}-beat '{section.name}' part")
                    if message not in warnings:
                        warnings.append(message)
                continue
            cache_key = (section.kind, section.variation, section.bars, role, spec, section.pause_every, loop_choice.get((section.name, role)))
            if cache_key not in cache:
                notes: list[Note] = []
                for part, offset, bars in playing:
                    seg_harmony = _from(harmony, offset * bpb, bars * bpb)
                    seg_notes = part_notes(role, part, section, seg_harmony, bars, offset)
                    seg_notes = fit_to_length(seg_notes, bars * bpb)
                    notes += [replace(n, start_time=n.start_time + (offset - first) * bpb) for n in seg_notes]
                if section.pause_every and role in ("drums", "bass"):
                    notes = _breathe(notes, role, section.pause_every, first, bpb, kick_pitch)
                if section.rest_beats and until == section.bars:
                    cut = clip_length - section.rest_beats
                    notes = fit_to_length([n for n in notes if n.start_time < cut - EPSILON], cut)
                cache[cache_key] = fit_to_length(notes, clip_length)
            notes = cache[cache_key]
            counts[role] += len(notes)
            action = {
                "action": "add_clip",
                "track": target.index,
                "start": at + first * bpb,
                "length": clip_length,
                "name": f"{section.name} {role.title()}",
                "notes": [n.to_spec() for n in notes],
            }
            if target.filter is not None:
                envelope = _sweep(section.sweeps.get(role), section.bars, first, clip_length, bpb, OPEN_HZ[target.filter])
                action["envelopes"] = [{"device": target.filter_device, "parameter": "Frequency", **envelope}]
                if any(f"{role}.res" in s.sweeps for s in sections):  # every clip, so no resonance hangs over
                    envelope = _sweep(section.sweeps.get(f"{role}.res"), section.bars, first, clip_length, bpb, 0.0, float)
                    action["envelopes"].append({"device": target.filter_device, "parameter": "Resonance", "unit": "display", **envelope})
            if role in throws and section.kind in style.throws[role]:
                send, base = throws[role]
                action.setdefault("envelopes", []).append(
                    {"parameter": send, "unit": "display", "points": _throw_points(section.bars, first, until, bpb, base)})
            actions.append(action)
    riser = roles.get("riser")
    preset = style.sounds.get("riser")
    riser_macro = riser is not None and preset is not None and (
        riser.sound is not None or not riser.new and [d.get("name") for d in session.track(riser.index).get("devices", [])][:1] == [_sound_name(preset)])
    fx_plays = _fx(actions, counts, roles, sections, starts, bpb, scale, style.mix.volume.get("riser", -12.0), riser_macro)
    if trigger is not None:
        if trigger_needed:
            assert drums is not None and kick_pitch is not None
            trigger_action = _kick_trigger_clip(trigger, drums, actions, kick_pitch, sidechain_source, start, end)
        else:
            trigger_action = _trigger_clip(trigger, request.genre, start, end, bpb)
        actions.append(trigger_action)
        counts["sidechain"] += len(trigger_action["notes"]) if trigger_needed else 1
    locators = [{"action": "set_locator", "time": at, "name": section.name} for section, at in zip(sections, starts)]
    if len(actions) > 256:
        raise BridgeError("INVALID_PARAMS", f"The song needs {len(actions)} clips; use a shorter length or fewer copied clips (max 256)")
    return SongPlan(
        secrets.token_hex(4), template, sections, starts, start, end, roles, actions, locators,
        new_tempo, seed, scale.describe(), f"{meter.numerator}/{meter.denominator}", bpb,
        tuple((t.get("id"), t.get("name"), t.get("kind")) for t in session.tracks),
        tempo,
        {"main": main.describe()[: max(1, round(8 * style.chords_per_bar))], "break": alt.describe()[: max(1, round(8 * style.chords_per_bar))]},
        counts, warnings,
        style.mix if request.mix else None,
        returns,
        tuple(r.get("name") for r in mixer["returns"]),
        fx_plays,
        key,
        str(reference.get("name")) if reference is not None else None,
        request.sidechain_mode,
        sidechain_source,
        {r: {**v, "name": next((c.get("name") for c in session.track(v["track"]).get("clips", []) if c["slot"] == v["slot"]), None)} for r, v in reuse.items()},
    )


RISER_BARS = 8


def _fx(actions: list[dict[str, Any]], counts: dict[str, int], roles: dict[str, RoleTrack], sections: tuple[Section, ...],
        starts: list[float], bpb: float, scale: Scale, riser_db: float, riser_macro: bool) -> dict[str, dict[str, str]]:
    """A riser over the last bars before every drop that follows another kind of section, an impact
    on the drop's first beat. The riser swells: volume from -30 dB and, on its preset, the Filter
    Cutoff macro (riser_macro: the track has the genre's preset), both slow at first. Returns what
    plays per section, for the preview."""
    plays: dict[str, dict[str, str]] = {}
    for i, (section, at) in enumerate(zip(sections, starts)):
        before = sections[i - 1] if i else None
        after = sections[i + 1] if i + 1 < len(sections) else None
        riser = roles.get("riser")
        if riser is not None and after is not None and after.kind == "drop" and section.kind != "drop":
            bars = min(RISER_BARS, section.bars)
            length = bars * bpb - section.rest_beats
            envelopes: list[dict[str, Any]] = [{"parameter": "Volume", "unit": "display", "shapes": [
                {"type": "exp", "length": length, "from_value": -30.0, "to_value": riser_db}]}]
            if riser_macro:
                envelopes.append({"device": 0, "parameter": "Filter Cutoff", "shapes": [{"type": "exp", "length": length, "from_value": 0.15, "to_value": 1.0}]})
            actions.append({"action": "add_clip", "track": riser.index, "start": at + (section.bars - bars) * bpb, "length": length,
                            "name": f"{section.name} Riser", "notes": [Note(60 + scale.root, 0.0, length, 100).to_spec()], "envelopes": envelopes})
            counts["riser"] += 1
            plays.setdefault(section.name, {})["riser"] = f"last {bars} bars"
        impact = roles.get("impact")
        if impact is not None and section.kind == "drop" and before is not None and before.kind != "drop":
            actions.append({"action": "add_clip", "track": impact.index, "start": at, "length": 2 * bpb, "name": f"{section.name} Impact",
                            "notes": [Note(36 + scale.root, 0.0, bpb, 115).to_spec()]})
            counts["impact"] += 1
            plays.setdefault(section.name, {})["impact"] = "first beat"
    return plays


def _rumble(harmony: Harmony, meter: Meter, bars: int) -> list[Note]:
    """A quiet low pulse between the kicks for kick-less breaks: the root on each off-beat 8th."""
    bpb = meter.beats_per_bar
    notes = []
    for beat in range(int(bars * bpb)):
        t = beat + 0.5
        root = 28 + (harmony.at(t).chord.root - 28) % 12
        notes.append(Note(root, t, 0.45, 58))
    return notes


def _accents(notes: list[Note], meter: Meter, offset_bars: int) -> list[Note]:
    """Only the first hit of each 8-bar phrase, louder."""
    bpb = meter.beats_per_bar
    kept = []
    first: dict[int, float] = {}
    for n in notes:
        phrase = int((n.start_time / bpb + offset_bars) // PHRASE)
        first[phrase] = min(first.get(phrase, n.start_time), n.start_time)
    for n in notes:
        phrase = int((n.start_time / bpb + offset_bars) // PHRASE)
        if abs(n.start_time - first[phrase]) < EPSILON and n.start_time / bpb + offset_bars - phrase * PHRASE < 1:
            kept.append(replace(n, velocity=min(127.0, n.velocity + 14), duration=max(n.duration, 0.5)))
    return kept


def _breathe(notes: list[Note], role: str, every: int, first_bar: int, bpb: float, kick_pitch: int | None) -> list[Note]:
    """Take kick and bass out of the last bar of every `every` bars of the section (T78, Spektre)."""
    def paused(n: Note) -> bool:
        bar = first_bar + int(n.start_time // bpb)
        return (bar + 1) % every == 0 and (role == "bass" or n.pitch == kick_pitch)
    return [n for n in notes if not paused(n)]


async def apply_song(call: Call, plan: SongPlan) -> dict[str, Any]:
    """New tracks, returns and mix (one undo step), the kits and presets (one step each), then
    tempo, all clips (one undo step) and locators."""
    follow_kick = plan.sidechain_mode == "follow_kick" and "sidechain" in plan.roles
    listed, arrangement, song, mixer = await asyncio.gather(
        call("tracks.list", {}), call("arrangement.get", {}), call("song.get", {}), call("mixer.get", {}))
    tracks = listed["tracks"]
    if tuple((t.get("id"), t.get("name"), t.get("kind")) for t in tracks) != plan.track_identity:
        raise BridgeError("CONFLICT", f"Tracks changed since song plan {plan.id} was made; plan again")
    if tuple(r.get("name") for r in mixer["returns"]) != plan.return_identity:
        raise BridgeError("CONFLICT", f"Return tracks changed since song plan {plan.id} was made; plan again")
    for role_track in plan.roles.values():
        if not role_track.new and _overlap(arrangement, role_track.index, plan.start, plan.end) is not None:
            raise BridgeError("CONFLICT", f"Track index {role_track.index} '{role_track.name}' has new arrangement clips in the song's range; plan again")
    if plan.sidechain_source is not None:
        source = plan.sidechain_source
        current = await _kick_source(call, source["track"], source["slot"])
        # Playback flags may change without changing the copied notes or their placement.
        timing = ("length", "looping", "loop_start", "loop_end", "start_marker", "end_marker")
        if current["notes"] != source["notes"] or any(current["clip"][k] != source["clip"][k] for k in timing):
            raise BridgeError("CONFLICT", "The copied drum clip changed since the kick-following plan; plan again")
    for role, source in plan.reuse.items():
        current = await call("clip.get", {"track": source["track"], "slot": source["slot"]})
        if not current.get("is_midi", True):
            raise BridgeError("CONFLICT", f"The copied {role} clip changed since the song plan was made; plan again")
        if (await _read_source(call, source["track"], source["slot"])).fingerprint != source["fingerprint"]:
            raise BridgeError("CONFLICT", f"The copied {role} clip's notes or loop/marker settings changed since the song plan was made; plan again")
    _trigger_first(plan)
    undo_steps = 0
    warnings: list[str] = []
    loaded: list[RoleTrack] = []
    actions = plan.actions
    new = [t for t in plan.roles.values() if t.new]
    ops: list[dict[str, Any]] = []
    for t in sorted(new, key=lambda t: t.index):
        ops.append({"op": "track.create", "params": {"kind": "midi", "name": t.name, **({"index": 0} if t.index == 0 else {})}})
        ops.append({"op": "device.insert", "params": {"track": t.index, "name": t.device}})
    for t in plan.roles.values():
        if t.filter is None:
            continue
        if t.filter_new:
            ops.append({"op": "device.insert", "params": {"track": t.index, "name": "Auto Filter"}})
        ops.append({"op": "device.set_param", "params": {"track": t.index, "device": t.filter_device, "parameter": "Filter Type", "value": FILTER_TYPES[t.filter]}})
    ops += _sidechain_ops(plan)
    ops += plan.mix_ops()
    try:
        if ops:
            try:
                await call("batch", {"ops": ops, "label": f"MidiBakery song {plan.id}: tracks"})
            except BridgeError as exc:
                await undo_batch(call, exc, [op["op"] for op in ops])
                raise
            undo_steps += batch_steps([op["op"] for op in ops], len(ops))
        for t in sorted(new, key=lambda t: t.index):
            if t.sound is None:
                continue
            try:
                await call("browser.load", {"track": t.index, "path": list(t.sound)})
            except BridgeError as exc:
                if t.role == "drums" and follow_kick:
                    raise  # do not create a kick-following trigger for an unloaded kit
                if exc.code == "LIVE_ERROR" and exc.message.startswith("Live did not load"):
                    raise  # it may still land later: roll back rather than guess
                if t.role in FX_ROLES:  # a sine instead of a riser: better none
                    actions = [a for a in actions if a.get("track") != t.index]
                    warnings.append(f"{_sound_name(t.sound)} could not be loaded ({exc.message}); track index {t.index} stays empty")
                else:
                    warnings.append(f"{_sound_name(t.sound)} could not be loaded ({exc.message}); track index {t.index} keeps {t.device}")
                continue
            undo_steps += 1
            loaded.append(t)
            if t.role == "drums":
                try:
                    kit = map_pads((await call("drum_rack.pads", {"track": t.index, "device": 0}))["pads"])
                except BridgeError as exc:  # e.g. a kit wrapped in an Instrument Rack
                    if follow_kick:
                        raise
                    warnings.append(f"{_sound_name(t.sound)}: pads not readable ({exc.message}); the drums keep General MIDI notes")
                else:
                    if follow_kick and "kick" not in kit.detected:
                        raise BridgeError("CONFLICT", "The loaded kit has no identifiable kick pad; choose a kit "
                                          "with a named kick or use sidechain_mode='pumping'")
                    actions = _move_to_kit(actions, t.index, kit)
        undo_steps += await _route_sidechains(call, plan, warnings)
        song_set: dict[str, Any] = {"tempo": plan.tempo} if plan.tempo is not None else {}
        if plan.key is not None:
            song_set.update(root_note=plan.key.root, scale_name=plan.key.name)
        if song_set:
            await call("song.set", song_set)
            undo_steps += 1
        result = await call("arrangement.edit", {"actions": actions})
        undo_steps += 1
    except BridgeError as exc:
        if "rolled_back" not in exc.details:
            await undo(call, exc, undo_steps + (1 if completed(exc) else 0))
        raise
    placed: int | str = len(plan.locators) if not song["is_playing"] else "skipped: stop the transport and plan again for locators"
    if not song["is_playing"]:
        try:
            await call("arrangement.locators", {"actions": plan.locators})
        except BridgeError as exc:  # the song is whole; its locators all or none (each is an undo step of its own)
            await restore_locators(call, exc, arrangement["locators"])
            placed = f"not set: {exc.message}"
        if (await call("song.get", {}))["current_song_time"] != song["current_song_time"]:
            await call("song.position", {"beat": song["current_song_time"]})
    return {
        "plan_id": plan.id,
        "song": f"{plan.template.label}, bars {int(plan.start / plan.beats_per_bar) + 1}-{int(plan.end / plan.beats_per_bar)}",
        "clips": len(result["results"]),
        "new_tracks": [{"track": t.index, "name": t.name, "device": _sound_name(t.sound) if t in loaded else t.device} for t in new],
        "automation": {r: f"track index {t.index}, device index {t.filter_device}" for r, t in plan.roles.items() if t.filter is not None},
        **({"sidechain": ducks} if (ducks := {r: f"track index {t.index}, device index {t.duck_device}" for r, t in plan.roles.items() if t.duck is not None}) else {}),
        **plan.mix_info(),
        "locators": placed,
        "undo": f"{undo_steps} undo step(s) for tracks/mix/sounds/tempo/clips; each locator is its own step",
        **({"warnings": warnings} if warnings else {}),
    }


def _trigger_first(plan: SongPlan) -> None:
    """A new sidechain track goes first in the Set, out of the way of the parts. It was planned last: it becomes
    index 0 and every track before it moves down one, in the roles and in the clip actions."""
    trigger = plan.roles.get("sidechain")
    if trigger is None or not trigger.new or trigger.index == 0:
        return
    moved = trigger.index

    def shift(index: int) -> int:
        return 0 if index == moved else index + 1 if index < moved else index

    for t in plan.roles.values():
        t.index = shift(t.index)
    plan.actions = [{**a, "track": shift(a["track"])} if "track" in a else a for a in plan.actions]


def _sidechain_ops(plan: SongPlan) -> list[dict[str, Any]]:
    """The trigger track silent, a Compressor per ducking role keyed from its Post FX (before the fader)."""
    trigger = plan.roles.get("sidechain")
    if trigger is None:
        return []
    ops: list[dict[str, Any]] = []
    if not trigger.new and trigger.device:
        ops.append({"op": "device.insert", "params": {"track": trigger.index, "name": trigger.device}})
    ops.append({"op": "mixer.set", "params": {"track": trigger.index, "volume": 0.0}})
    release = plan.template.style.mix.release
    for t in plan.roles.values():
        if t.duck is None:
            continue
        if t.duck_new:
            ops.append({"op": "device.insert", "params": {"track": t.index, "name": "Compressor"}})
        for parameter, shown in _duck_params(t.duck, release):
            ops.append({"op": "device.set_param", "params": {"track": t.index, "device": t.duck_device, "parameter": parameter, "display": shown}})
    return ops


ROUTING_TRIES = 10  # Live lists a new track as a sidechain source a few ticks after it exists


async def _route_sidechains(call: Call, plan: SongPlan, warnings: list[str]) -> int:
    """Key each ducking Compressor from the trigger track: a batch of its own, once Live lists the
    new track as a source. Its undo steps."""
    trigger = plan.roles.get("sidechain")
    ops = [{"op": "device.routing", "params": {"track": t.index, "device": t.duck_device, "input_track": trigger.index, "channel": "Post FX"}}
           for t in plan.roles.values() if t.duck is not None] if trigger is not None else []
    if not ops:
        return 0
    for attempt in range(ROUTING_TRIES):
        try:
            await call("batch", {"ops": ops, "label": f"MidiBakery song {plan.id}: sidechain"})
            return 1
        except BridgeError as exc:
            if exc.details.get("completed") or "no sidechain source" not in exc.message or attempt == ROUTING_TRIES - 1:
                warnings.append(f"Sidechain not routed ({exc.message}); set the Compressors' sidechain to track index {trigger.index}, Post FX")
                return 1 if exc.details.get("completed") else 0
            await asyncio.sleep(0.2)
    return 0


def _move_to_kit(actions: list[dict[str, Any]], track: int, kit: DrumMap) -> list[dict[str, Any]]:
    """The drum clips were written for General MIDI notes (a new track has no kit while planning):
    move each note to the pad of its role on the loaded kit."""
    roles = {note: role for role, note in map_pads(None).notes.items()}
    moved = []
    for action in actions:
        if action.get("track") == track and "notes" in action:
            notes = [{**n, "pitch": kit.notes.get(roles.get(n["pitch"], ""), n["pitch"])} for n in action["notes"]]
            action = {**action, "notes": notes}
        moved.append(action)
    return moved
