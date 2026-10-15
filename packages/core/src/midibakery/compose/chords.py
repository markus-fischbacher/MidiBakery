"""Chord part generator: voice-led voicings over a rhythm."""

from __future__ import annotations

import random
from typing import Literal

from midibakery.compose.harmony import Harmony
from midibakery.compose.notes import Note, dedupe
from midibakery.compose.rhythm import Grid, Meter
from midibakery.compose.theory import voice_lead

ChordRhythm = Literal["sustain", "pulse", "offbeat", "stabs"]
RHYTHMS: tuple[str, ...] = ("sustain", "pulse", "offbeat", "stabs")


def generate_chords(
    harmony: Harmony,
    meter: Meter,
    bars: int,
    rhythm: str,
    rng: random.Random,
    low: int = 52,
    high: int = 76,
    voices: int = 3,
    swing: float = 0.0,
    swing_unit: float = 0.25,
) -> list[Note]:
    grid = Grid(meter, 0.25, swing, swing_unit)
    voicings = voice_lead([s.chord for s in harmony.segments], low, high)
    if voices > 3:
        voicings = [v + (v[0] + 12,) if len(v) == 3 and v[0] + 12 <= high and v[0] + 12 not in v else v for v in voicings]

    stab_steps: list[int] = []
    if rhythm == "stabs":
        candidates = [s for s in range(1, grid.steps_per_bar) if s % 2 == 1 or s % 4 == 2]
        stab_steps = sorted({0} | set(rng.sample(candidates, min(len(candidates), rng.randint(2, 3)))))

    notes: list[Note] = []
    for segment, voicing in zip(harmony.segments, voicings):
        hits: list[tuple[float, float]] = []  # (start, duration)
        if rhythm == "sustain":
            hits.append((segment.start, segment.length))
        else:
            first_bar = int(segment.start // meter.beats_per_bar)
            last_bar = int((segment.end - 1e-9) // meter.beats_per_bar)
            for bar in range(first_bar, last_bar + 1):
                t0 = bar * meter.beats_per_bar
                if rhythm == "pulse":
                    starts = [(t0 + p, meter.pulse_length(i) * 0.85) for i, p in enumerate(meter.pulses)]
                elif rhythm == "offbeat":
                    starts = [(t0 + o, meter.pulse_length(i) * 0.4) for i, o in enumerate(meter.offbeats())]
                else:
                    starts = [(grid.position(bar, s), 0.2) for s in stab_steps]
                hits.extend((t, d) for t, d in starts if segment.start - 1e-9 <= t < segment.end - 1e-9)
        for start, duration in hits:
            accent = meter.accent(grid.offset_in_bar(start))
            velocity = 70 + 25 * accent + rng.uniform(-3, 3)
            for k, pitch in enumerate(voicing):
                # Inner voices a little softer than bass and top voice.
                inner = 0 < k < len(voicing) - 1
                notes.append(Note(pitch, start, min(duration, segment.end - start), velocity - (6 if inner else 0), velocity_deviation=5))
    return dedupe(notes)
