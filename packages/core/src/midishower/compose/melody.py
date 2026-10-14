"""Melody generator: a seeded motif developed over phrases (A A' A B), anchored on chord tones."""

from __future__ import annotations

import random
from dataclasses import dataclass

from midishower.compose.harmony import Harmony
from midishower.compose.notes import Note, dedupe
from midishower.compose.rhythm import Grid, Meter
from midishower.compose.theory import Chord, Scale

STEP_CHOICES = (-2, -1, -1, 1, 1, 2, 0, 3, -3)


@dataclass(frozen=True)
class Motif:
    steps: tuple[int, ...]  # grid steps inside one bar
    moves: tuple[int, ...]  # scale-step movement before each note (first is ignored)


def _rhythm(grid: Grid, rng: random.Random, density: float) -> tuple[int, ...]:
    meter = grid.meter
    chosen = {0}
    for s in range(1, grid.steps_per_bar):
        weight = meter.accent(s * grid.step)
        if rng.random() < min(0.9, density * (0.25 + weight)):
            chosen.add(s)
    while len(chosen) < 2:
        chosen.add(rng.randrange(1, grid.steps_per_bar))
    return tuple(sorted(chosen))


def _motif(grid: Grid, rng: random.Random, density: float) -> Motif:
    steps = _rhythm(grid, rng, density)
    return Motif(steps, tuple(rng.choice(STEP_CHOICES) for _ in steps))


def _vary(motif: Motif, rng: random.Random) -> Motif:
    """A': same rhythm, new ending."""
    moves = list(motif.moves)
    for i in range(max(1, len(moves) - 2), len(moves)):
        moves[i] = rng.choice(STEP_CHOICES)
    return Motif(motif.steps, tuple(moves))


def _nearest_chord_tone(scale: Scale, chord: Chord, pitch: int, low: int, high: int) -> int:
    candidates = [p for p in range(max(low, pitch - 7), min(high, pitch + 7) + 1) if chord.contains(p) and scale.contains(p)]
    if not candidates:
        candidates = [p for p in range(max(low, pitch - 7), min(high, pitch + 7) + 1) if chord.contains(p)]
    return min(candidates, key=lambda p: (abs(p - pitch), p)) if candidates else pitch


def _keep_in_range(scale: Scale, pitch: int, low: int, high: int) -> int:
    while pitch > high:
        pitch -= 12
    while pitch < low:
        pitch += 12
    return scale.snap(min(high, max(low, pitch)))


def generate_melody(
    harmony: Harmony,
    scale: Scale,
    meter: Meter,
    bars: int,
    rng: random.Random,
    low: int = 60,
    high: int = 84,
    density: float = 0.5,
    swing: float = 0.0,
    swing_unit: float = 0.25,
) -> list[Note]:
    grid = Grid(meter, 0.25, swing, swing_unit)
    a = _motif(grid, rng, density)
    forms = {0: a, 1: _vary(a, rng), 2: a, 3: _motif(grid, rng, density)}
    pitch = scale.snap((low + high) // 2)
    notes: list[Note] = []
    for bar in range(bars):
        motif = forms[bar % 4] if bars >= 4 else (a if bar % 2 == 0 else forms[1])
        phrase_end = bar % 4 == 3 or bar == bars - 1
        bar_start = bar * meter.beats_per_bar
        for i, step in enumerate(motif.steps):
            start = grid.position(bar, step)
            chord = harmony.at(start).chord
            accent = meter.accent(step * grid.step)
            if i == 0:
                pitch = _nearest_chord_tone(scale, chord, pitch, low, high)
            else:
                pitch = _keep_in_range(scale, scale.step(pitch, motif.moves[i]), low, high)
                if accent >= 0.8:
                    pitch = _nearest_chord_tone(scale, chord, pitch, low, high)
            last = i == len(motif.steps) - 1
            next_start = grid.position(bar, motif.steps[i + 1]) if not last else bar_start + meter.beats_per_bar
            if last and phrase_end:
                # Resolve the phrase on a chord root and let it ring.
                roots = [p for p in range(low, high + 1) if p % 12 == chord.root and scale.contains(p)]
                if roots:
                    pitch = min(roots, key=lambda p: abs(p - pitch))
            duration = max(grid.step * 0.9, min(1.5, (next_start - start) * 0.9))
            probability = 1.0
            velocity = 78 + 30 * accent + rng.uniform(-5, 5)
            if accent <= 0.4 and not last and rng.random() < 0.3 + 0.3 * density:
                # Ornamental weak-beat notes sometimes drop out for a less mechanical loop.
                probability = 0.8
                velocity -= 8
            notes.append(Note(pitch, start, duration, velocity, probability, velocity_deviation=8))
    return dedupe(notes)
