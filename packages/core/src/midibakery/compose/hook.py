"""A lead hook as the recipes describe it, instead of a stream of 16ths.

- A 2-bar unit: a *call* (short notes, starting after the downbeat) and a
  *response* (fewer, longer notes that land somewhere else).
- Phrases of 4 bars play call, response, call, response'; every 8 bars the
  response changes a little, so the hook develops instead of looping blindly.
- The rhythm stays, the pitches follow the chords: notes on beats and long
  notes are chord tones, short off-beat notes may pass through the scale.
- 8th grid with the odd 16th pickup; about 3-5 notes per bar; above the chords.
- ``tease`` plays only the call, quieter: for intros and breakdowns.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from midibakery.compose.harmony import Harmony
from midibakery.compose.notes import Note
from midibakery.compose.rhythm import Grid, Meter
from midibakery.compose.theory import Scale


@dataclass(frozen=True)
class Slot:
    offset: float  # beats from the start of the 2-bar unit
    length: float
    target: int  # chord-tone index for strong/long notes (0 root, 1 third, 2 fifth, 3 seventh); -1 = passing step
    step: int = 0  # for passing notes: scale steps from the previous note


def _call(rng: random.Random) -> list[Slot]:
    """Bar 1: 3-4 short notes on 8ths, the downbeat left empty."""
    starts = sorted(rng.sample([0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5], rng.choice([3, 4])))
    slots = []
    for i, t in enumerate(starts):
        on_beat = abs(t - round(t)) < 1e-9
        if on_beat or i == len(starts) - 1:
            slots.append(Slot(t, 0.4, rng.choice([0, 1, 2])))
        else:
            slots.append(Slot(t, 0.3, -1, rng.choice([-1, 1])))
    return slots


def _response(rng: random.Random) -> list[Slot]:
    """Bar 2: 2-3 longer notes; the last one is held and lands on a chord tone other than the call's."""
    patterns = [
        [(4.0, 0.9), (5.0, 0.9), (6.0, 1.8)],
        [(4.5, 0.9), (5.5, 2.2)],
        [(4.0, 0.4), (4.5, 1.4), (6.5, 1.3)],
        [(5.0, 0.9), (6.0, 1.9)],
    ]
    chosen = rng.choice(patterns)
    return [Slot(t, length, rng.choice([1, 2, 3]) if i == len(chosen) - 1 else rng.choice([0, 1, 2])) for i, (t, length) in enumerate(chosen)]


def _vary(response: list[Slot], rng: random.Random) -> list[Slot]:
    """Response': same rhythm, the ending moved to another chord tone."""
    last = response[-1]
    other = [t for t in (0, 1, 2, 3) if t != last.target]
    return response[:-1] + [Slot(last.offset, last.length, rng.choice(other))]


@dataclass
class Hook:
    call: list[Slot]
    response: list[Slot]
    response_b: list[Slot]


def make_hook(rng: random.Random) -> Hook:
    response = _response(rng)
    return Hook(_call(rng), response, _vary(response, rng))


def _chord_tone(scale: Scale, harmony: Harmony, time: float, index: int, previous: int, low: int, high: int) -> int:
    chord = harmony.at(time).chord
    pcs = list(chord.pitch_classes)
    pc = pcs[min(index, len(pcs) - 1)]
    candidates = [p for p in range(low, high + 1) if p % 12 == pc]
    if not candidates:
        candidates = [p for p in range(low, high + 1) if p % 12 in pcs] or [low]
    return min(candidates, key=lambda p: abs(p - previous))


def _passing(scale: Scale, previous: int, step: int, low: int, high: int) -> int:
    pitch = scale.step(previous, step)
    if not low <= pitch <= high:
        pitch = scale.step(previous, -step)
    return pitch


def generate_hook(
    hook: Hook,
    harmony: Harmony,
    scale: Scale,
    meter: Meter,
    bars: int,
    swing: float,
    low: int = 72,
    high: int = 89,
    tease: bool = False,
    velocity: float = 98,
    flip: bool = False,
) -> list[Note]:
    """`flip` starts with the varied response: a later section of the same kind sounds related, not copied."""
    grid = Grid(meter, 0.25, swing, 0.25)
    bpb = meter.beats_per_bar
    notes: list[Note] = []
    previous = scale.snap((low + high) // 2)
    for unit in range(0, bars, 2):
        base = unit * bpb
        slots = list(hook.call)
        if not tease and unit + 1 < bars:
            # 4-bar phrase: call/response, call/response'; every 8 bars the variation leads.
            second = (unit // 2) % 2 == 1
            eighth = ((unit // 8) % 2 == 1) != flip
            slots += hook.response_b if second != eighth else hook.response
        for slot in slots:
            t = base + slot.offset
            if t >= bars * bpb - 1e-9:
                continue
            bar, offset = divmod(t, bpb)
            start = bar * bpb + grid.swung(offset)
            if slot.target >= 0:
                pitch = _chord_tone(scale, harmony, start, slot.target, previous, low, high)
            else:
                pitch = _passing(scale, previous, slot.step, low, high)
            notes.append(Note(pitch, start, slot.length, (velocity - 18) if tease else velocity))
            previous = pitch
    return notes


# --------------------------------------------------------------------------- arpeggio (Melodic Techno)


@dataclass
class Arp:
    steps: tuple[int, ...]  # 16th steps of the 1-bar rhythm
    order: tuple[int, ...]  # chord-tone index per note (3 = root an octave up)


def make_arp(rng: random.Random) -> Arp:
    """NI: a 1-bar rhythm of short notes that stays, repitched to the chord every 2 bars."""
    count = rng.choice([6, 7, 8])
    steps = tuple(sorted(rng.sample(range(1, 17), count)))
    if 1 not in steps:
        steps = (1,) + steps[1:]
    order = tuple(rng.choice([0, 1, 2, 3, 2, 1]) for _ in steps)
    return Arp(steps, order)


def generate_arp(arp: Arp, harmony: Harmony, scale: Scale, meter: Meter, bars: int, swing: float, low: int = 60, high: int = 84, tease: bool = False, velocity: float = 90) -> list[Note]:
    grid = Grid(meter, 0.25, swing, 0.25)
    notes = []
    previous = (low + high) // 2
    for bar in range(bars):
        if tease and bar % 2 == 1:
            continue
        for step, index in zip(arp.steps, arp.order):
            t = grid.position(bar, step - 1)
            pitch = _chord_tone(scale, harmony, t, min(index, 2), previous, low, high)
            if index == 3 and pitch + 12 <= high:
                pitch += 12
            notes.append(Note(pitch, t, 0.2, (velocity - 18) if tease else velocity))
            previous = pitch
    return notes


# --------------------------------------------------------------------------- acid line (Peak-Time Techno)


@dataclass
class Acid:
    steps: tuple[int, ...]
    intervals: tuple[int, ...]  # semitones above the chord root: 0, 12, 3, 7, 10
    slides: frozenset[int]  # steps that tie into the next note (only between short notes)
    accents: frozenset[int]


def make_acid(rng: random.Random) -> Acid:
    """303 style (Roland): 16 steps, few slides, sparse accents before kicks, mostly the root."""
    steps = tuple(sorted(rng.sample(range(1, 17), rng.choice([9, 10, 11]))))
    intervals = tuple(rng.choices([0, 0, 0, 12, 3, 7, 10], k=len(steps)))
    slides = frozenset(rng.sample(steps[:-1], 2))
    accents = frozenset(s for s in (4, 8, 12, 16) if s in steps and rng.random() < 0.6)
    return Acid(steps, intervals, slides, accents)


def generate_acid(
    acid: Acid,
    harmony: Harmony,
    meter: Meter,
    bars: int,
    low: int = 48,
    high: int = 62,
    tease: bool = False,
    rng: random.Random | None = None,
    lift: bool = False,
) -> list[Note]:
    """Straight 16ths; a slide becomes an overlapping note (glide on a mono legato synth).

    It develops like the recipe asks, one thing at a time: each 16 bars start thinned out (root and
    accented steps only) and fill up after 4 bars; every 8 bars one note, one accent and one slide
    move while the core stays. `lift` (the last peak) plays the second half an octave higher."""
    rng = rng or random.Random(0)
    grid = Grid(meter, 0.25, 0.0, 0.25)
    notes = []
    intervals = list(acid.intervals)
    accents, slides = set(acid.accents), set(acid.slides)
    steps = acid.steps
    for bar in range(bars):
        if bar and bar % 8 == 0:
            intervals[rng.randrange(len(intervals))] = rng.choice([0, 12, 3, 7, 10])
            accents ^= {rng.choice(steps)}  # one accent added or taken away
            if slides:
                slides.discard(rng.choice(sorted(slides)))
            slides.add(rng.choice(steps[:-1]))
        if tease and bar % 4 >= 2:
            continue
        thinned = tease or bar % 16 < 4
        top = high + 12 if lift and bar >= bars // 2 else high
        floor = low + 12 if lift and bar >= bars // 2 else low
        for i, (step, interval) in enumerate(zip(steps, intervals)):
            if thinned and interval != 0 and step not in accents:
                continue
            t = grid.position(bar, step - 1)
            root = floor + (harmony.at(t).chord.root - floor) % 12
            pitch = root + interval if root + interval <= top else root + interval - 12
            nxt = steps[i + 1] if i + 1 < len(steps) else None
            length = (nxt - step) * 0.25 + 0.05 if step in slides and nxt is not None else 0.18
            velocity = 116 if step in accents else 84
            notes.append(Note(pitch, t, length, velocity - (16 if tease else 0)))
    return notes
