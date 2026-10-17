"""Composition without a Live connection: notes in, notes out.

Used by the MIDI Tool devices in Live's clip view (Max `live.miditool.in/out`),
which hand over the clip's notes plus scale, time signature, selection and
seed, and write the returned note list themselves. The same generators and
transformations as the MCP tools run here.
"""

from __future__ import annotations

import math
import random
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from midibakery.compose import harmony as harmony_mod
from midibakery.compose import transform as tf
from midibakery.compose.drums import map_pads
from midibakery.compose.notes import Note, fit_to_length
from midibakery.compose.parts import generate_part
from midibakery.compose.rhythm import Grid, Meter
from midibakery.compose.specs import PART_SPECS, SWING_UNITS, TransformSpec
from midibakery.compose.theory import MAJOR, Scale


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ScaleIn(_Model):
    root: Annotated[int, Field(ge=0, le=11)] = 0
    intervals: list[Annotated[int, Field(ge=0, le=11)]] = Field(default_factory=lambda: list(MAJOR))
    name: str = ""


class Pad(_Model):
    note: Annotated[int, Field(ge=0, le=127)]
    name: str


class Context(_Model):
    """What Live's MIDI Tool context provides (plus the drum pads, if known)."""

    scale: ScaleIn = Field(default_factory=ScaleIn)
    numerator: Annotated[int, Field(ge=1, le=99)] = 4
    denominator: Literal[1, 2, 4, 8, 16] = 4
    start: Annotated[float, Field(ge=0, description="Time selection start in beats")] = 0.0
    length: Annotated[float, Field(gt=0, le=4096, description="Time selection length in beats")] = 16.0
    seed: int | None = None
    pads: list[Pad] | None = None

    def scale_obj(self) -> Scale:
        return Scale(self.scale.root, tuple(sorted(set([0, *self.scale.intervals]))), self.scale.name)

    def meter(self) -> Meter:
        return Meter(self.numerator, self.denominator)

    def bars(self) -> int:
        return max(1, math.ceil(self.length / self.meter().beats_per_bar - 1e-9))


class NoteIO(_Model):
    note_id: int | None = None
    pitch: Annotated[int, Field(ge=0, le=127)]
    start_time: float
    duration: Annotated[float, Field(gt=0)]
    velocity: Annotated[float, Field(ge=0, le=127)] = 100.0
    mute: bool = False
    probability: Annotated[float, Field(ge=0, le=1)] = 1.0
    velocity_deviation: Annotated[float, Field(ge=-127, le=127)] = 0.0
    release_velocity: Annotated[float, Field(ge=0, le=127)] = 64.0


GENERATORS = PART_SPECS
# Fields that only make sense against a live set.
_SET_ONLY = {"track", "slot", "arrangement_clip", "bars", "seed", "if_exists", "clip_name", "chords_from", "follow_kick", "device", "kind", "note_ids"}


class GenerateRequest(_Model):
    context: Context = Field(default_factory=Context)
    kind: Literal["drums", "bass", "chords", "melody"]
    params: dict[str, Any] = Field(default_factory=dict, description="Same fields as the compose_* tool of this kind")


class TransformRequest(_Model):
    context: Context = Field(default_factory=Context)
    notes: list[NoteIO]
    operation: tf.Operation
    params: dict[str, Any] = Field(default_factory=dict, description="Same fields as transform_notes")


def _spec(model: type[BaseModel], params: dict[str, Any]) -> Any:
    unknown = set(params) & _SET_ONLY
    if unknown:
        raise ValueError(f"not available in a MIDI tool: {', '.join(sorted(unknown))}")
    return model.model_validate({"track": 0, "slot": 0, **params})


def _note_out(note: Note | dict[str, Any], offset: float = 0.0) -> dict[str, Any]:
    if isinstance(note, Note):
        n = note.clamped()
        return {
            "pitch": n.pitch, "start_time": round(n.start_time + offset, 6), "duration": n.duration,
            "velocity": n.velocity, "mute": n.mute, "probability": n.probability,
            "velocity_deviation": n.velocity_deviation, "release_velocity": 64.0,
        }
    return {k: v for k, v in note.items() if k != "note_id" or v is not None}


def run_transform(spec: TransformSpec, notes: list[dict[str, Any]], scale: Scale, meter: Meter, length: float | None, seed: int) -> tf.Diff:
    """The transform_notes operations on plain note dicts (with note_id)."""
    rng = random.Random(seed)
    op = spec.operation
    if op == "humanize":
        return tf.humanize(notes, rng, spec.amount)
    if op == "quantize":
        return tf.quantize(notes, Grid(meter, spec.grid, spec.swing, SWING_UNITS[spec.swing_unit]), spec.strength)
    if op == "invert":
        return tf.invert(notes, scale, spec.axis)
    if op == "transpose":
        return tf.transpose(notes, scale, spec.steps, spec.semitones)
    if op == "arpeggiate":
        diff = tf.arpeggiate(notes, rng, spec.rate, spec.direction, octaves=spec.octaves)
        diff.add = fit_to_length(diff.add, length or float("inf"))
        return diff
    if op == "variation":
        return tf.variation(notes, rng, scale, spec.amount)
    raise ValueError(f"unknown operation {op!r}")


def generate(request: GenerateRequest) -> dict[str, Any]:
    """New notes for the time selection, positioned at its start."""
    ctx = request.context
    spec = _spec(GENERATORS[request.kind], request.params)
    seed = ctx.seed if ctx.seed is not None else random.SystemRandom().randrange(2**31)
    rng = random.Random(seed)
    scale, meter, bars = ctx.scale_obj(), ctx.meter(), ctx.bars()
    info: dict[str, Any] = {}
    if request.kind == "drums":
        drum_map = map_pads([p.model_dump() for p in ctx.pads] if ctx.pads else None)
        notes = generate_part(spec, None, scale, meter, bars, rng, drum_map)
        info["drum_map"] = drum_map.source
    else:
        if spec.progression:
            harmony = harmony_mod.from_progression(spec.progression, scale, meter, bars, spec.chords_per_bar)
        else:
            harmony = harmony_mod.auto(scale, meter, bars, spec.chords_per_bar, rng, getattr(spec, "sevenths", False))
        info["chords"] = harmony.describe()
        notes = generate_part(spec, harmony, scale, meter, bars, rng)
    notes = fit_to_length(notes, ctx.length)
    return {"seed": seed, "notes": [_note_out(n, ctx.start) for n in notes], **info}


def transform(request: TransformRequest) -> dict[str, Any]:
    """The full note list after the transformation (MIDI Tools replace the clip's notes)."""
    ctx = request.context
    spec = _spec(TransformSpec, {"operation": request.operation, **request.params})
    seed = ctx.seed if ctx.seed is not None else random.SystemRandom().randrange(2**31)
    notes = [n.model_dump() for n in request.notes]
    # Live's MIDI Tools address notes by id; plain lists get positional ids.
    for i, n in enumerate(notes):
        if n["note_id"] is None:
            n["note_id"] = -(i + 1)
    ids = [n["note_id"] for n in notes]
    if len(set(ids)) != len(ids):
        raise ValueError("note_id values must be unique")
    # Positions relative to the selection start, like a clip starting there.
    local = [{**n, "start_time": n["start_time"] - ctx.start} for n in notes]
    diff = run_transform(spec, local, ctx.scale_obj(), ctx.meter(), ctx.length, seed)

    changes = {c["note_id"]: c for c in diff.modify}
    removed = set(diff.remove)
    result = []
    for n in local:
        if n["note_id"] in removed:
            continue
        merged = {**n, **{k: v for k, v in changes.get(n["note_id"], {}).items() if k != "note_id"}}
        merged["start_time"] = round(merged["start_time"] + ctx.start, 6)
        if merged["note_id"] < 0:
            merged["note_id"] = None
        result.append(_note_out(merged))
    result += [_note_out(n, ctx.start) for n in diff.add]
    result.sort(key=lambda n: (n["start_time"], n["pitch"]))
    return {
        "seed": seed,
        "notes": result,
        "diff": {"added": len(diff.add), "modified": len(diff.modify), "removed": len(diff.remove)},
    }
