"""Note transformations that produce a diff against the clip's existing notes.

Every function takes notes as returned by ``notes.get`` (with ``note_id``) and
returns a :class:`Diff`. Notes that keep their identity are *modified* by id,
so Live keeps their probability, release velocity and undo history; only
arpeggiate replaces notes, because one chord becomes several new notes.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Literal

from midibakery.compose.notes import Note
from midibakery.compose.rhythm import Grid
from midibakery.compose.theory import Scale, clamp_pitch

Operation = Literal["humanize", "quantize", "invert", "arpeggiate", "variation", "transpose"]
OPERATIONS: tuple[str, ...] = ("humanize", "quantize", "invert", "arpeggiate", "variation", "transpose")
ArpDirection = Literal["up", "down", "updown", "random"]

CHORD_TOLERANCE = 0.02


@dataclass
class Diff:
    add: list[Note] = field(default_factory=list)
    modify: list[dict[str, Any]] = field(default_factory=list)
    remove: list[int] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not (self.add or self.modify or self.remove)


def _change(note: dict[str, Any], **fields: Any) -> dict[str, Any] | None:
    """Only the fields that actually change, or None."""
    changed: dict[str, Any] = {}
    for key, value in fields.items():
        if isinstance(value, float):
            value = round(value, 6)
        if note.get(key) != value and not (isinstance(value, float) and abs(note.get(key, 0) - value) < 1e-6):
            changed[key] = value
    return {"note_id": note["note_id"], **changed} if changed else None


def _collect(changes: list[dict[str, Any] | None]) -> Diff:
    return Diff(modify=[c for c in changes if c])


def humanize(notes: list[dict], rng: random.Random, amount: float = 0.5, timing: float = 0.03, velocity: float = 18) -> Diff:
    """Small random timing and velocity offsets. `amount` 0..1 scales both."""
    changes = []
    for n in notes:
        start = max(0.0, n["start_time"] + rng.uniform(-1, 1) * timing * amount)
        vel = max(1.0, min(127.0, round(n["velocity"] + rng.uniform(-1, 1) * velocity * amount)))
        changes.append(_change(n, start_time=start, velocity=float(vel)))
    return _collect(changes)


def quantize(notes: list[dict], grid: Grid, strength: float = 1.0, ends: bool = False) -> Diff:
    changes = []
    for n in notes:
        start = max(0.0, grid.quantize(n["start_time"], strength))
        fields: dict[str, Any] = {"start_time": start}
        if ends:
            end = grid.quantize(n["start_time"] + n["duration"], strength)
            fields["duration"] = max(grid.step / 2, end - start)
        changes.append(_change(n, **fields))
    return _collect(changes)


def invert(notes: list[dict], scale: Scale | None, axis: int | None = None) -> Diff:
    """Mirror pitches around `axis` (default: middle of the used range).

    With a scale the mirror is diatonic, so the result stays in key; notes
    outside the scale are mirrored chromatically.
    """
    if not notes:
        return Diff()
    pitches = [n["pitch"] for n in notes]
    if axis is None:
        axis = (min(pitches) + max(pitches)) // 2
    axis_degree = scale.degree_of(scale.snap(axis)) if scale else None
    changes = []
    for n in notes:
        degree = scale.degree_of(n["pitch"]) if scale else None
        if scale and degree is not None and axis_degree is not None:
            pitch = scale.pitch_of_degree(2 * axis_degree - degree)
        else:
            pitch = 2 * axis - n["pitch"]
        changes.append(_change(n, pitch=clamp_pitch(pitch)))
    return _collect(changes)


def transpose(notes: list[dict], scale: Scale | None, steps: int, semitones: int = 0) -> Diff:
    """Move by scale steps (in key; off-scale notes keep their offset), or by semitones
    without a scale, then by `semitones` chromatically."""
    changes = []
    for n in notes:
        pitch = n["pitch"]
        if steps and scale:
            snapped = scale.snap(pitch)
            pitch = scale.step(snapped, steps) + (pitch - snapped)
        else:
            pitch += steps
        changes.append(_change(n, pitch=clamp_pitch(pitch + semitones)))
    return _collect(changes)


def _groups(notes: list[dict]) -> list[list[dict]]:
    ordered = sorted(notes, key=lambda n: (n["start_time"], n["pitch"]))
    groups: list[list[dict]] = []
    for n in ordered:
        if groups and abs(groups[-1][0]["start_time"] - n["start_time"]) <= CHORD_TOLERANCE:
            groups[-1].append(n)
        else:
            groups.append([n])
    return groups


def arpeggiate(
    notes: list[dict],
    rng: random.Random,
    rate: float = 0.25,
    direction: str = "up",
    gate: float = 0.9,
    octaves: int = 1,
) -> Diff:
    """Turn every chord (2+ notes starting together) into a run over the chord's length."""
    diff = Diff()
    for group in _groups(notes):
        if len(group) < 2:
            continue
        start = group[0]["start_time"]
        end = max(n["start_time"] + n["duration"] for n in group)
        base = sorted({n["pitch"] for n in group})
        pitches = [p + 12 * o for o in range(max(1, octaves)) for p in base if p + 12 * o <= 127]
        if direction == "down":
            cycle = pitches[::-1]
        elif direction == "updown":
            cycle = pitches + pitches[-2:0:-1]
        else:
            cycle = pitches
        velocity = max(n["velocity"] for n in group)
        t, i = start, 0
        while t < end - 1e-9:
            pitch = rng.choice(pitches) if direction == "random" else cycle[i % len(cycle)]
            diff.add.append(Note(pitch, t, min(rate * gate, end - t), velocity - (0 if i == 0 else 8)))
            t += rate
            i += 1
        diff.remove.extend(n["note_id"] for n in group)
    return diff


def variation(notes: list[dict], rng: random.Random, scale: Scale | None, amount: float = 0.5) -> Diff:
    """Seeded variation: neighbour-tone swaps, octave jumps, velocity accents and
    a touch of probability, each note decided independently."""
    changes = []
    for n in notes:
        fields: dict[str, Any] = {}
        roll = rng.random()
        if roll < 0.3 * amount:
            if scale and scale.contains(n["pitch"]):
                fields["pitch"] = clamp_pitch(scale.step(n["pitch"], rng.choice((-1, 1))))
            else:
                fields["pitch"] = clamp_pitch(n["pitch"] + rng.choice((-2, 2)))
        elif roll < 0.38 * amount:
            fields["pitch"] = clamp_pitch(n["pitch"] + rng.choice((-12, 12)))
        if rng.random() < 0.3 * amount:
            fields["velocity"] = float(max(1, min(127, round(n["velocity"] + rng.uniform(-25, 15)))))
        if rng.random() < 0.25 * amount and n.get("probability", 1.0) >= 1.0:
            fields["probability"] = round(rng.uniform(0.6, 0.9), 2)
        changes.append(_change(n, **fields) if fields else None)
    # A slight variation (amount 0.2) of a short phrase often rolled no pitch change at all, and the
    # user heard nothing: at least one note moves to a neighbour tone.
    if amount > 0 and notes and not any(c and "pitch" in c for c in changes):
        i = rng.randrange(len(notes))
        n = notes[i]
        if scale and scale.contains(n["pitch"]):
            pitch = clamp_pitch(scale.step(n["pitch"], rng.choice((-1, 1))))
        else:
            pitch = clamp_pitch(n["pitch"] + rng.choice((-2, 2)))
        changes[i] = _change(n, **{k: v for k, v in (changes[i] or {}).items() if k != "note_id"}, pitch=pitch)
    return _collect(changes)
