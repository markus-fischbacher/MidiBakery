"""Plan/Apply: turn composition requests into a reviewable diff, then run it as one undo step.

``build_plan`` only *reads* from Live (song, tracks, notes, drum pads) and
returns a :class:`Plan` holding the exact ``clip.create`` / ``notes.apply`` ops
it would run. ``apply_plan`` first checks that the target clips still look as
they did when the plan was made, then sends all ops as one ``batch``, which
Live records as a single undo step.

Steps in one plan see each other: a bass step can follow the kick of a drum
clip planned before it, and harmonic steps without explicit chords reuse the
chords of the first harmonic step.
"""

from __future__ import annotations

import hashlib
import json
import random
import secrets
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from midishower.bridge.client import BridgeError
from midishower.compose import harmony as harmony_mod
from midishower.compose import transform as tf
from midishower.compose.bass import generate_bass
from midishower.compose.chords import generate_chords
from midishower.compose.drums import DrumMap, generate_drums, kick_times, map_pads
from midishower.compose.harmony import Harmony
from midishower.compose.melody import generate_melody
from midishower.compose.notes import Note, fit_to_length
from midishower.compose.rhythm import Grid, Meter
from midishower.compose.specs import (
    BassSpec,
    ChordsSpec,
    ClipLocation,
    DrumsSpec,
    Generate,
    Harmonic,
    MelodySpec,
    Spec,
    SWING_UNITS,
    TransformSpec,
)
from midishower.compose.theory import Scale, pitch_name

Call = Callable[..., Awaitable[Any]]
MAX_BATCH_OPS = 256
PREVIEW_NOTES = 48


def new_seed() -> int:
    return secrets.randbelow(2**31)


def _fingerprint(exists: bool, is_midi: bool, length: float | None, notes: list[dict] | None) -> str:
    payload = [exists, is_midi, length, sorted(tuple(sorted(n.items())) for n in notes or [])]
    return hashlib.sha256(json.dumps(payload, default=str).encode()).hexdigest()[:16]


@dataclass
class ClipState:
    exists: bool
    is_midi: bool = True
    length: float | None = None
    notes: list[dict] | None = None
    planned: bool = False

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self.exists, self.is_midi, self.length, self.notes)


class Session:
    """Read-only view of the open Live set, cached for the lifetime of one plan."""

    def __init__(self, call: Call):
        self._call = call
        self.song: dict[str, Any] = {}
        self.tracks: list[dict[str, Any]] = []
        self.scale = Scale(0)
        self.meter = Meter()
        self.harmony: Harmony | None = None
        self.planned: dict[tuple[int, int], ClipState] = {}
        self._clips: dict[tuple[int, int], ClipState] = {}
        self._pads: dict[tuple[int, int | None], list[dict] | None] = {}

    async def load(self) -> Session:
        self.song = await self._call("song.get", {})
        self.tracks = (await self._call("tracks.list", {}))["tracks"]
        self.scale = Scale.from_song(self.song)
        self.meter = Meter(int(self.song.get("signature_numerator", 4)), int(self.song.get("signature_denominator", 4)))
        return self

    def track(self, index: int) -> dict[str, Any]:
        if not 0 <= index < len(self.tracks):
            raise BridgeError("NOT_FOUND", f"No track {index} (song has {len(self.tracks)})", {"track": index})
        return self.tracks[index]

    async def clip(self, track: int, slot: int, include_planned: bool = True) -> ClipState:
        key = (track, slot)
        if include_planned and key in self.planned:
            return self.planned[key]
        if key in self._clips:
            return self._clips[key]
        info = self.track(track)
        scenes = int(self.song.get("scene_count", slot + 1))
        if slot >= scenes:
            raise BridgeError("NOT_FOUND", f"No clip slot {slot} (song has {scenes} scenes; create a scene first)", {"slot": slot})
        found = next((c for c in info.get("clips", []) if c["slot"] == slot), None)
        if found is None:
            state = ClipState(False)
        elif not found.get("is_midi"):
            state = ClipState(True, False, found.get("length"))
        else:
            notes = (await self._call("notes.get", {"track": track, "slot": slot}))["notes"]
            state = ClipState(True, True, found.get("length"), notes)
        self._clips[key] = state
        return state

    async def drum_pads(self, track: int, device: int | None = None) -> list[dict] | None:
        """Pads of the track's Drum Rack, or None (no rack, or an older Remote Script)."""
        key = (track, device)
        if key not in self._pads:
            params: dict[str, Any] = {"track": track}
            if device is not None:
                params["device"] = device
            try:
                self._pads[key] = (await self._call("drum_rack.pads", params))["pads"]
            except BridgeError as exc:
                if exc.code not in ("NOT_FOUND", "UNSUPPORTED", "UNKNOWN_OP", "INVALID_PARAMS"):
                    raise
                if device is not None and exc.code == "INVALID_PARAMS":
                    raise
                self._pads[key] = None
        return self._pads[key]


@dataclass
class ClipChange:
    track: int
    slot: int
    kind: str
    seed: int | None = None
    create: dict[str, Any] | None = None
    add: list[Note] = field(default_factory=list)
    modify: list[dict[str, Any]] = field(default_factory=list)
    remove: list[int] = field(default_factory=list)
    info: dict[str, Any] = field(default_factory=dict)
    length: float = 0.0  # clip length after the change, in beats
    existing: list[dict[str, Any]] = field(default_factory=list)  # notes in the clip before the change

    @property
    def removes_existing(self) -> bool:
        """True when user notes disappear without being re-created from them (replace, not arpeggiate)."""
        return bool(self.remove) and self.kind != "transform"

    def roll(self) -> dict[str, Any]:
        """Everything a piano-roll view needs to draw before and after, untruncated."""
        return {
            "track": self.track,
            "slot": self.slot,
            "kind": self.kind,
            "length": self.length,
            "existing": [
                [n["note_id"], n["pitch"], n["start_time"], n["duration"], n["velocity"], n.get("probability", 1.0)]
                for n in self.existing
            ],
            "add": [[n.pitch, n.start_time, n.duration, n.velocity, n.probability] for n in (a.clamped() for a in self.add)],
            "modify": self.modify,
            "remove": self.remove,
        }

    @property
    def edits_notes(self) -> bool:
        return bool(self.add or self.modify or self.remove)

    def ops(self) -> list[dict[str, Any]]:
        ops: list[dict[str, Any]] = []
        if self.create:
            ops.append({"op": "clip.create", "params": self.create})
        if self.edits_notes:
            params: dict[str, Any] = {"track": self.track, "slot": self.slot}
            if self.add:
                params["add"] = [n.to_spec() for n in self.add]
            if self.modify:
                params["modify"] = self.modify
            if self.remove:
                params["remove"] = self.remove
            ops.append({"op": "notes.apply", "params": params})
        return ops

    def preview(self) -> dict[str, Any]:
        if self.create:
            action = "create clip"
        elif self.remove and self.add and self.kind != "transform":
            action = "replace notes"
        elif self.edits_notes:
            action = "edit notes"
        else:
            action = "no change"
        data: dict[str, Any] = {
            "track": self.track,
            "slot": self.slot,
            "kind": self.kind,
            "action": action,
            "add": len(self.add),
            "modify": len(self.modify),
            "remove": len(self.remove),
        }
        if self.seed is not None:
            data["seed"] = self.seed
        if self.create:
            data["clip_length"] = self.create["length"]
        if self.add:
            pitches = [n.pitch for n in self.add]
            data["pitch_range"] = [pitch_name(min(pitches)), pitch_name(max(pitches))]
            data["notes"] = [_compact(n) for n in self.add[:PREVIEW_NOTES]]
            if len(self.add) > PREVIEW_NOTES:
                data["notes_truncated"] = len(self.add) - PREVIEW_NOTES
        if self.modify:
            data["changes"] = self.modify[:PREVIEW_NOTES]
        data.update(self.info)
        return data


def _compact(note: Note) -> dict[str, Any]:
    n = note.clamped()
    data: dict[str, Any] = {"pitch": n.pitch, "start": n.start_time, "dur": n.duration, "vel": n.velocity}
    if n.probability < 1:
        data["prob"] = n.probability
    if n.velocity_deviation:
        data["vel_dev"] = n.velocity_deviation
    return data


@dataclass
class Plan:
    id: str
    changes: list[ClipChange]
    fingerprints: dict[tuple[int, int], str]
    scale: str
    meter: str

    def ops(self) -> list[dict[str, Any]]:
        return [op for change in self.changes for op in change.ops()]

    @property
    def removes_existing(self) -> int:
        """Number of existing notes the plan deletes outright (clip replacements)."""
        return sum(len(c.remove) for c in self.changes if c.removes_existing)

    def roll(self) -> dict[str, Any]:
        return {"plan_id": self.id, "scale": self.scale, "time_signature": self.meter, "clips": [c.roll() for c in self.changes]}

    def preview(self) -> dict[str, Any]:
        return {
            "plan_id": self.id,
            "scale": self.scale,
            "time_signature": self.meter,
            "op_count": len(self.ops()),
            "changes": [c.preview() for c in self.changes],
        }


class PlanStore:
    """Recent plans kept in memory until applied (oldest dropped first)."""

    def __init__(self, capacity: int = 32):
        self._plans: OrderedDict[str, Plan] = OrderedDict()
        self._capacity = capacity

    def put(self, plan: Plan) -> None:
        self._plans[plan.id] = plan
        while len(self._plans) > self._capacity:
            self._plans.popitem(last=False)

    def pop(self, plan_id: str) -> Plan:
        try:
            return self._plans.pop(plan_id)
        except KeyError:
            raise BridgeError("NOT_FOUND", f"Unknown or already applied plan '{plan_id}'; call plan_changes again") from None

    def get(self, plan_id: str) -> Plan | None:
        return self._plans.get(plan_id)


# --------------------------------------------------------------------------
# Planning
# --------------------------------------------------------------------------


async def _target(session: Session, spec: Generate) -> tuple[ClipState, float, dict[str, Any] | None, list[int]]:
    """Existing state, clip length, clip.create params and note ids to remove for a generator target."""
    track = session.track(spec.track)
    if track.get("kind") != "midi":
        raise BridgeError("INVALID_PARAMS", f"Track {spec.track} ('{track.get('name')}') is not a MIDI track")
    state = await session.clip(spec.track, spec.slot)
    length = session.meter.beats_per_bar * spec.bars
    if state.planned:
        raise BridgeError("INVALID_PARAMS", f"Clip {spec.track}/{spec.slot} is already written by an earlier step of this plan")
    if not state.exists:
        name = spec.clip_name or spec.kind.title()  # type: ignore[attr-defined]
        return state, length, {"track": spec.track, "slot": spec.slot, "length": length, "name": name}, []
    if not state.is_midi:
        raise BridgeError("INVALID_PARAMS", f"Clip {spec.track}/{spec.slot} is an audio clip")
    if spec.if_exists == "error":
        raise BridgeError(
            "CONFLICT",
            f"Slot {spec.track}/{spec.slot} already has a clip; pass if_exists='replace' or 'merge', or pick an empty slot",
        )
    remove = [n["note_id"] for n in state.notes or []] if spec.if_exists == "replace" else []
    return state, min(length, state.length or length), None, remove


async def _harmony(session: Session, spec: Harmonic, rng: random.Random) -> Harmony:
    meter, scale = session.meter, session.scale
    try:
        if spec.progression:
            result = harmony_mod.from_progression(spec.progression, scale, meter, spec.bars, spec.chords_per_bar)
        elif spec.chords_from is not None:
            source = await session.clip(spec.chords_from.track, spec.chords_from.slot)
            if not source.exists or not source.is_midi:
                raise BridgeError("NOT_FOUND", f"chords_from: no MIDI clip at {spec.chords_from.track}/{spec.chords_from.slot}")
            source_bars = max(1, round((source.length or meter.beats_per_bar) / meter.beats_per_bar))
            result = harmony_mod.detect(source.notes or [], scale, meter, source_bars, spec.chords_per_bar)
            result = result.for_length(meter, spec.bars)
        elif session.harmony is not None:
            result = session.harmony.for_length(meter, spec.bars)
        else:
            sevenths = isinstance(spec, ChordsSpec) and spec.sevenths
            result = harmony_mod.auto(scale, meter, spec.bars, spec.chords_per_bar, rng, sevenths)
    except ValueError as exc:
        raise BridgeError("INVALID_PARAMS", str(exc)) from None
    if session.harmony is None:
        session.harmony = result
    return result


async def _kick(session: Session, location: ClipLocation, length: float) -> tuple[list[float], dict[str, Any]]:
    source = await session.clip(location.track, location.slot)
    if not source.exists or not source.is_midi:
        raise BridgeError("NOT_FOUND", f"follow_kick: no MIDI clip at {location.track}/{location.slot}")
    drum_map = map_pads(await session.drum_pads(location.track))
    kick_pitch = drum_map.note("kick")
    assert kick_pitch is not None
    loop = source.length or length
    onsets = kick_times(source.notes or [], kick_pitch)
    times = sorted({round(t + k * loop, 6) for k in range(int(length // loop) + 1) for t in onsets if t + k * loop < length})
    return times, {"kick_pitch": kick_pitch, "kick_hits": len(times)}


def _finish(session: Session, spec: Generate, kind: str, seed: int, notes: list[Note], target: tuple, info: dict) -> ClipChange:
    state, length, create, remove = target
    notes = fit_to_length(notes, length)
    session.planned[(spec.track, spec.slot)] = ClipState(
        True, True, length if create else state.length, [_as_dict(n) for n in notes], planned=True
    )
    return ClipChange(
        spec.track, spec.slot, kind, seed, create, notes, [], remove, info,
        length=length if create else (state.length or length), existing=list(state.notes or []),
    )


def _as_dict(note: Note) -> dict[str, Any]:
    return {
        "pitch": note.pitch,
        "start_time": note.start_time,
        "duration": note.duration,
        "velocity": note.velocity,
        "mute": note.mute,
        "probability": note.probability,
        "velocity_deviation": note.velocity_deviation,
    }


async def _plan_drums(session: Session, spec: DrumsSpec) -> ClipChange:
    target = await _target(session, spec)
    seed = spec.seed if spec.seed is not None else new_seed()
    pads = await session.drum_pads(spec.track, spec.device)
    drum_map: DrumMap = map_pads(pads)
    notes = generate_drums(
        session.meter, spec.bars, spec.style, random.Random(seed), drum_map,
        density=spec.density, swing=spec.swing, swing_unit=SWING_UNITS[spec.swing_unit], fills=spec.fills,
    )
    info = {
        "style": spec.style,
        "drum_map": drum_map.source,
        "pads": {role: drum_map.notes[role] for role in sorted({_role_of(drum_map, n.pitch) for n in notes} - {None})},
    }
    return _finish(session, spec, "drums", seed, notes, target, info)


def _role_of(drum_map: DrumMap, pitch: int) -> str | None:
    return next((role for role, note in drum_map.notes.items() if note == pitch), None)


async def _plan_bass(session: Session, spec: BassSpec) -> ClipChange:
    target = await _target(session, spec)
    seed = spec.seed if spec.seed is not None else new_seed()
    rng = random.Random(seed)
    harmony = await _harmony(session, spec, rng)
    kick, info = None, {}
    if spec.follow_kick is not None:
        kick, info = await _kick(session, spec.follow_kick, target[1])
        info["kick_relation"] = spec.kick_relation
    notes = generate_bass(
        harmony, session.scale, session.meter, spec.bars, spec.style, rng, spec.octave, kick, spec.kick_relation,
        density=spec.density, swing=spec.swing, swing_unit=SWING_UNITS[spec.swing_unit],
    )
    info = {"style": spec.style, "chords": harmony.describe(), "chords_source": harmony.source, **info}
    return _finish(session, spec, "bass", seed, notes, target, info)


async def _plan_chords(session: Session, spec: ChordsSpec) -> ClipChange:
    target = await _target(session, spec)
    seed = spec.seed if spec.seed is not None else new_seed()
    rng = random.Random(seed)
    harmony = await _harmony(session, spec, rng)
    try:
        notes = generate_chords(
            harmony, session.meter, spec.bars, spec.rhythm, rng, spec.low, spec.high, spec.voices,
            swing=spec.swing, swing_unit=SWING_UNITS[spec.swing_unit],
        )
    except ValueError as exc:
        raise BridgeError("INVALID_PARAMS", str(exc)) from None
    info = {"rhythm": spec.rhythm, "chords": harmony.describe(), "chords_source": harmony.source}
    return _finish(session, spec, "chords", seed, notes, target, info)


async def _plan_melody(session: Session, spec: MelodySpec) -> ClipChange:
    target = await _target(session, spec)
    seed = spec.seed if spec.seed is not None else new_seed()
    rng = random.Random(seed)
    harmony = await _harmony(session, spec, rng)
    notes = generate_melody(
        harmony, session.scale, session.meter, spec.bars, rng, spec.low, spec.high, spec.density,
        swing=spec.swing, swing_unit=SWING_UNITS[spec.swing_unit],
    )
    info = {"chords": harmony.describe(), "chords_source": harmony.source}
    return _finish(session, spec, "melody", seed, notes, target, info)


async def _plan_transform(session: Session, spec: TransformSpec) -> ClipChange:
    if (spec.track, spec.slot) in session.planned:
        raise BridgeError("INVALID_PARAMS", "Cannot transform a clip written earlier in the same plan; apply first, then transform")
    state = await session.clip(spec.track, spec.slot)
    if not state.exists or not state.is_midi:
        raise BridgeError("NOT_FOUND", f"No MIDI clip at {spec.track}/{spec.slot}")
    notes = state.notes or []
    if spec.note_ids is not None:
        known = {n["note_id"] for n in notes}
        unknown = sorted(set(spec.note_ids) - known)
        if unknown:
            raise BridgeError("NOT_FOUND", "Unknown note_id(s) in this clip", {"note_ids": unknown})
        wanted = set(spec.note_ids)
        notes = [n for n in notes if n["note_id"] in wanted]
    seed = spec.seed if spec.seed is not None else new_seed()
    rng = random.Random(seed)
    scale = session.scale
    op = spec.operation
    if op == "humanize":
        diff = tf.humanize(notes, rng, spec.amount)
    elif op == "quantize":
        diff = tf.quantize(notes, Grid(session.meter, spec.grid, spec.swing, SWING_UNITS[spec.swing_unit]), spec.strength)
    elif op == "invert":
        diff = tf.invert(notes, scale, spec.axis)
    elif op == "transpose":
        diff = tf.transpose(notes, scale, spec.steps)
    elif op == "arpeggiate":
        diff = tf.arpeggiate(notes, rng, spec.rate, spec.direction, octaves=spec.octaves)
        diff.add = fit_to_length(diff.add, state.length or float("inf"))
    elif op == "variation":
        diff = tf.variation(notes, rng, scale, spec.amount)
    else:  # pragma: no cover - guarded by the schema
        raise BridgeError("INVALID_PARAMS", f"unknown operation {op!r}")
    uses_seed = op in ("humanize", "variation", "arpeggiate")
    return ClipChange(
        spec.track, spec.slot, "transform", seed if uses_seed else None, None, diff.add, diff.modify, diff.remove,
        {"operation": op, "notes_considered": len(notes)},
        length=state.length or 0.0,
        existing=list(state.notes or []),
    )


_PLANNERS = {
    "drums": _plan_drums,
    "bass": _plan_bass,
    "chords": _plan_chords,
    "melody": _plan_melody,
    "transform": _plan_transform,
}


async def build_plan(call: Call, steps: list[Spec]) -> Plan:
    if not steps:
        raise BridgeError("INVALID_PARAMS", "A plan needs at least one step")
    session = await Session(call).load()
    changes = []
    targets: set[tuple[int, int]] = set()
    for step in steps:
        key = (step.track, step.slot)  # type: ignore[attr-defined]
        if key in targets:
            raise BridgeError("INVALID_PARAMS", f"Two steps target clip {key[0]}/{key[1]}; use one step per clip")
        targets.add(key)
        changes.append(await _PLANNERS[step.kind](session, step))  # type: ignore[attr-defined]
    fingerprints = {}
    for key in targets:
        state = await session.clip(*key, include_planned=False)
        fingerprints[key] = state.fingerprint
    plan = Plan(
        secrets.token_hex(4),
        changes,
        fingerprints,
        session.scale.describe(),
        f"{session.meter.numerator}/{session.meter.denominator}",
    )
    if len(plan.ops()) > MAX_BATCH_OPS:
        raise BridgeError("INVALID_PARAMS", f"Plan needs {len(plan.ops())} ops; split it (max {MAX_BATCH_OPS})")
    return plan


async def apply_plan(call: Call, plan: Plan, verify: bool = True) -> dict[str, Any]:
    """Run the plan as one batch (one undo step) after checking nothing changed underneath it."""
    if verify:
        session = await Session(call).load()
        for (track, slot), expected in plan.fingerprints.items():
            state = await session.clip(track, slot, include_planned=False)
            if state.fingerprint != expected:
                raise BridgeError(
                    "CONFLICT",
                    f"Clip {track}/{slot} changed since plan {plan.id} was made; plan again",
                    {"track": track, "slot": slot},
                )
    ops = plan.ops()
    applied: list[dict[str, Any]] = []
    if ops:
        results = (await call("batch", {"ops": ops, "label": f"MidiShower plan {plan.id}"}))["results"]
        cursor = 0
        for change in plan.changes:
            entry: dict[str, Any] = {"track": change.track, "slot": change.slot, "kind": change.kind}
            for op in change.ops():
                result = results[cursor]
                cursor += 1
                if op["op"] == "notes.apply":
                    entry.update(added_note_ids=result["added"], modified=result["modified"], removed=result["removed"])
                else:
                    entry["created_clip"] = True
            if change.seed is not None:
                entry["seed"] = change.seed
            applied.append(entry)
    return {"plan_id": plan.id, "applied": applied, "op_count": len(ops), "undo": "one undo step reverts the whole plan"}
