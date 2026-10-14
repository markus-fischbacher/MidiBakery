"""Bass line generator: follows a chord timeline and, optionally, the kick of a drum clip."""

from __future__ import annotations

import random
from typing import Literal

from midishower.compose.harmony import Harmony
from midishower.compose.notes import Note, dedupe
from midishower.compose.rhythm import Grid, Meter
from midishower.compose.theory import Chord, Scale, octave_base

BassStyle = Literal["sustained", "pulse", "offbeat", "octave", "walking", "syncopated"]
STYLES: tuple[str, ...] = ("sustained", "pulse", "offbeat", "octave", "walking", "syncopated")
KickRelation = Literal["lock", "avoid"]

KICK_TOLERANCE = 0.1


def _root(chord: Chord, octave: int) -> int:
    base = octave_base(octave)
    return base + (chord.root - base) % 12


def _chord_tone(chord: Chord, root: int, index: int) -> int:
    """index 0 = root, 1 = third, 2 = fifth, 3 = seventh/octave, above the bass root."""
    intervals = chord.intervals
    if index < len(intervals):
        return root + intervals[index]
    return root + 12


def _onsets(style: str, meter: Meter, grid: Grid, bars: int, harmony: Harmony, rng: random.Random, density: float) -> list[float]:
    bpb = meter.beats_per_bar
    onsets: list[float] = []
    if style == "sustained":
        return [s.start for s in harmony.segments]
    if style in ("pulse", "octave"):
        for bar in range(bars):
            onsets.extend(grid.position(bar, s) for s in range(0, grid.steps_per_bar, 2))
        return onsets
    if style == "offbeat":
        for bar in range(bars):
            onsets.extend(bar * bpb + o for o in meter.offbeats())
        return onsets
    if style == "walking":
        for bar in range(bars):
            onsets.extend(bar * bpb + p for p in meter.pulses)
        return onsets
    if style == "syncopated":
        # One 16th pattern for the clip, so the line grooves instead of wandering.
        favoured = [s for s in range(1, grid.steps_per_bar) if s % 4 in (2, 3)]
        others = [s for s in range(1, grid.steps_per_bar) if s % 4 in (0, 1)]
        pick = 2 + round(3 * density)
        chosen = set(rng.sample(favoured, min(len(favoured), pick - 1)))
        if others and rng.random() < 0.5:
            chosen.add(rng.choice(others))
        pattern = sorted({0} | chosen)
        for bar in range(bars):
            onsets.extend(grid.position(bar, s) for s in pattern)
        return onsets
    raise ValueError(f"unknown bass style {style!r}")


def generate_bass(
    harmony: Harmony,
    scale: Scale,
    meter: Meter,
    bars: int,
    style: str,
    rng: random.Random,
    octave: int = 1,
    kick: list[float] | None = None,
    kick_relation: str = "lock",
    density: float = 0.5,
    swing: float = 0.0,
) -> list[Note]:
    grid = Grid(meter, 0.25, swing)
    length = meter.beats_per_bar * bars
    if kick and kick_relation == "lock":
        onsets = [t for t in kick if t < length]
        # Make sure every chord change is articulated even if the kick skips it.
        for segment in harmony.segments:
            if not any(abs(segment.start - t) < KICK_TOLERANCE for t in onsets):
                onsets.append(segment.start)
    else:
        onsets = _onsets(style, meter, grid, bars, harmony, rng, density)
        if kick and kick_relation == "avoid":
            onsets = [t for t in onsets if all(abs(t - k) >= KICK_TOLERANCE for k in kick)]
    onsets = sorted({round(t, 6) for t in onsets if 0 <= t < length})

    notes: list[Note] = []
    for i, start in enumerate(onsets):
        segment = harmony.at(start)
        chord = segment.chord
        root = _root(chord, octave)
        nxt = onsets[i + 1] if i + 1 < len(onsets) else length
        last_before_change = nxt >= segment.end - 1e-9 and segment.end < length - 1e-9
        first_in_segment = start - segment.start < 1e-6

        if first_in_segment or style == "sustained":
            pitch = root
        elif last_before_change and style in ("walking", "syncopated") and rng.random() < 0.7:
            # Approach the next root from the scale step above or below.
            target = _root(harmony.at(segment.end).chord, octave)
            pitch = scale.step(target, rng.choice((-1, 1)))
        elif style == "octave":
            pitch = root + 12 if round((start - segment.start) / 0.5) % 2 else root
        elif style == "walking":
            pitch = _chord_tone(chord, root, rng.choice((1, 2, 2, 3)))
        elif style == "syncopated":
            pitch = rng.choices((root, _chord_tone(chord, root, 2), root + 12), (0.6, 0.25, 0.15))[0]
        else:
            pitch = root

        if style == "sustained":
            duration = segment.end - start
        else:
            duration = min(nxt - start, segment.end - start)
            duration = min(duration * 0.9, 1.0 if style != "walking" else duration * 0.95)
        accent = meter.accent(grid.offset_in_bar(start))
        velocity = 85 + 30 * accent + rng.uniform(-4, 4)
        notes.append(Note(pitch, start, max(0.1, duration), velocity, velocity_deviation=6))
    return dedupe(notes)
