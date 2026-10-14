"""Note value type shared by generators and transformations."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from midishower.compose.theory import clamp_pitch

TIME_DIGITS = 6


@dataclass(frozen=True)
class Note:
    pitch: int
    start_time: float
    duration: float
    velocity: float = 100.0
    probability: float = 1.0
    velocity_deviation: float = 0.0
    mute: bool = False

    def clamped(self) -> Note:
        return replace(
            self,
            pitch=clamp_pitch(self.pitch),
            start_time=round(max(0.0, self.start_time), TIME_DIGITS),
            duration=round(max(1 / 128, self.duration), TIME_DIGITS),
            velocity=float(max(1, min(127, round(self.velocity)))),
            probability=round(max(0.0, min(1.0, self.probability)), 3),
            velocity_deviation=float(max(-127, min(127, round(self.velocity_deviation)))),
        )

    def to_spec(self) -> dict[str, Any]:
        """Payload for ``notes.apply`` ``add`` (NoteIn); defaults are left out."""
        n = self.clamped()
        spec: dict[str, Any] = {"pitch": n.pitch, "start_time": n.start_time, "duration": n.duration, "velocity": n.velocity}
        if n.probability != 1.0:
            spec["probability"] = n.probability
        if n.velocity_deviation:
            spec["velocity_deviation"] = n.velocity_deviation
        if n.mute:
            spec["mute"] = True
        return spec

    @property
    def end_time(self) -> float:
        return self.start_time + self.duration


def fit_to_length(notes: list[Note], length: float) -> list[Note]:
    """Drop notes that start at or after `length`, shorten those that cross it,
    and cut notes that would overlap the next note of the same pitch (Live would
    otherwise shorten or merge them itself, so the clip would differ from the plan)."""
    fitted = []
    next_start: dict[int, float] = {}
    for note in sorted(notes, key=lambda n: (n.start_time, n.pitch), reverse=True):
        if note.start_time >= length - 1e-9:
            continue
        end = min(length, next_start.get(note.pitch, length))
        if note.end_time > end:
            note = replace(note, duration=end - note.start_time)
        if note.duration <= 1e-6:
            continue
        next_start[note.pitch] = note.start_time
        fitted.append(note.clamped())
    return sorted(fitted, key=lambda n: (n.start_time, n.pitch))


def dedupe(notes: list[Note]) -> list[Note]:
    """Live merges notes with the same pitch and start; keep the loudest."""
    best: dict[tuple[int, float], Note] = {}
    for note in notes:
        key = (note.pitch, round(note.start_time, 4))
        if key not in best or note.velocity > best[key].velocity:
            best[key] = note
    return sorted(best.values(), key=lambda n: (n.start_time, n.pitch))
