"""Genre grooves from the recipes in docs/GENRES.md: drum lanes, bass and chord rhythms as data.

Steps count 1-16 in a 4/4 bar of 16ths (step 1 = beat 1, 5 = beat 2, 9 = beat 3,
13 = beat 4). A lane plays its steps every bar, or only in some bars of a cycle
(e.g. the ghost clap in bar 2 of every 2). Parts pick lanes: an intro may play
only kick and hats, a build everything but the kick.

Only House has its own groove so far; other genres use the older generators.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace

from midibakery.compose.drums import DrumMap
from midibakery.compose.harmony import Harmony
from midibakery.compose.notes import Note, dedupe
from midibakery.compose.rhythm import Grid, Meter
from midibakery.compose.theory import Chord, Scale

STEP = 0.25


@dataclass(frozen=True)
class Lane:
    role: str  # drum role as in DrumMap (kick, clap, closed_hat, open_hat, shaker, ...)
    steps: tuple[int, ...]
    velocity: float
    length: float = 0.25
    jitter: float = 0.0  # +- random velocity
    probability: float = 1.0
    cycle: int = 1  # plays in bars where bar % cycle in `bars`
    bars: tuple[int, ...] = (0,)
    alternate: float = 0.0  # every second step this much quieter (hat "dance")


@dataclass(frozen=True)
class Groove:
    lanes: tuple[Lane, ...]
    parts: dict[str, frozenset[str]]  # part -> lane roles
    swing: float  # 0..1 of a triplet on 16ths; MPC 60% = 0.6
    late_lanes: frozenset[str] = frozenset()  # lanes that only join in the second half of a long "full" part


ALL = "all"

HOUSE = Groove(
    lanes=(
        Lane("kick", (1, 5, 9, 13), 112),
        Lane("clap", (5, 13), 104, length=0.5),
        # Loopmasters: closed hat on the 1st, 2nd and 4th 16th of every beat, the 3rd left to the open hat.
        Lane("closed_hat", (1, 2, 4, 5, 6, 8, 9, 10, 12, 13, 14, 16), 74, jitter=8, alternate=18),
        Lane("open_hat", (3, 7, 11, 15), 83, length=0.5, jitter=5),
        Lane("shaker", tuple(range(1, 17)), 46, jitter=12),
        # Ghost clap ~6 dB down on the first 16th after the last clap of a 2-bar loop.
        Lane("clap", (14,), 62, cycle=2, bars=(1,), probability=0.85),
    ),
    parts={
        "kick_hats": frozenset({"kick", "closed_hat"}),
        "groove": frozenset({"kick", "clap", "closed_hat", "shaker"}),
        "full": frozenset({"kick", "clap", "closed_hat", "shaker", "open_hat"}),
        "no_kick": frozenset({"clap", "closed_hat", "shaker", "open_hat"}),
        "sparse": frozenset({"closed_hat", "shaker"}),
    },
    swing=0.6,  # Attack: 55-65 % on 16ths, on all parts
    late_lanes=frozenset({"open_hat"}),  # EDMProd: open hat added in the second half of the drop
)

GROOVES: dict[str, Groove] = {"house": HOUSE}


def _hits(lane: Lane, grid: Grid, bar: int, rng: random.Random) -> list[Note]:
    if bar % lane.cycle not in lane.bars:
        return []
    notes = []
    for i, step in enumerate(lane.steps):
        if lane.probability < 1.0 and rng.random() > lane.probability:
            continue
        velocity = lane.velocity - (lane.alternate if i % 2 else 0) + rng.uniform(-lane.jitter, lane.jitter)
        notes.append(Note(-1, grid.position(bar, step - 1), lane.length, velocity))
    return notes


def _fill(grid: Grid, bar: int, strong: bool, variant: int, drum_map: DrumMap) -> list[Note]:
    """Last beat(s) of a bar. Variants alternate so boundaries do not all sound the same;
    the strong one (into a new section) is a snare roll over the whole bar, getting louder."""
    notes: list[Note] = []
    bpb = grid.meter.beats_per_bar
    start = bar * bpb
    snare = drum_map.note("snare") or drum_map.note("clap")
    if strong:
        # 8ths for two beats, then 16ths, velocity 50 -> 110
        times = [start + t * 0.5 for t in range(4)] + [start + 2 + t * 0.25 for t in range(8)]
        for i, t in enumerate(times):
            notes.append(Note(snare, t, 0.2, 50 + 60 * i / (len(times) - 1)))
        return notes
    if variant % 2 == 0:
        for i in range(4):  # snare 16ths on the last beat
            notes.append(Note(snare, start + bpb - 1 + i * 0.25, 0.2, 70 + 10 * i))
    else:
        toms = [drum_map.note(r) for r in ("high_tom", "mid_tom", "mid_tom", "low_tom")]
        for i, pitch in enumerate(toms):
            if pitch is not None:
                notes.append(Note(pitch, start + bpb - 1 + i * 0.25, 0.25, 92 - 4 * i))
    return notes


def generate_groove(
    groove: Groove,
    part: str,
    meter: Meter,
    bars: int,
    rng: random.Random,
    drum_map: DrumMap,
    energy: float,
    fill_at_end: bool,
    crash: bool,
    long_part: bool,
    phrase_offset: int = 0,
) -> list[Note]:
    """One part of a section: lanes of the part, fills every 8 bars (alternating), a strong fill at the
    end if asked, a crash on bar 1 if asked. Velocity grows a little with energy."""
    grid = Grid(meter, STEP, groove.swing, 0.25)
    roles = groove.parts[part]
    notes: list[Note] = []
    for bar in range(bars):
        late = long_part and bar < bars // 2
        for lane in groove.lanes:
            if lane.role not in roles or (late and lane.role in groove.late_lanes):
                continue
            pitch = drum_map.note(lane.role)
            if pitch is None:
                continue
            notes += [replace(n, pitch=pitch) for n in _hits(lane, grid, bar, rng)]
        last = bar == bars - 1
        boundary = (phrase_offset + bar) % 8 == 7
        if (last and fill_at_end) or (boundary and not last):
            fill = _fill(grid, bar, strong=last and fill_at_end, variant=(phrase_offset + bar) // 8, drum_map=drum_map)
            cut = min(n.start_time for n in fill) if fill else None
            if cut is not None:  # the fill replaces snare/clap/hats under it; the kick stays unless strong
                keep_kick = not (last and fill_at_end)
                kick = drum_map.note("kick")
                notes = [n for n in notes if n.start_time < cut - 1e-9 or (keep_kick and n.pitch == kick)]
            notes += fill
    cymbal = drum_map.note("crash")
    if crash and cymbal is not None and cymbal not in (drum_map.note("open_hat"), drum_map.note("closed_hat")):
        notes.append(Note(cymbal, 0.0, 1.0, 100))  # a kit without crash or ride gets none, not an open hat
    factor = 0.85 + 0.15 * energy
    return dedupe([replace(n, velocity=max(1.0, min(127.0, n.velocity * factor))) for n in notes])


# --------------------------------------------------------------------------- bass


@dataclass(frozen=True)
class BassPattern:
    steps: tuple[int, ...]
    length: float
    velocity: float
    low: int  # MIDI range of the root
    high: int
    third_every: int = 0  # every n-th note goes to the chord's third (NI: "sometimes the 3rd")


HOUSE_BASS = BassPattern((3, 7, 11, 15), length=0.42, velocity=104, low=28, high=39, third_every=8)
BASS: dict[str, BassPattern] = {"house": HOUSE_BASS}


def _fold(pitch_class: int, low: int, high: int) -> int:
    pitch = low + (pitch_class - low) % 12
    return pitch if pitch <= high else pitch - 12


def generate_recipe_bass(pattern: BassPattern, harmony: Harmony, meter: Meter, bars: int, swing: float) -> list[Note]:
    """Offbeat/rolling bass from a step pattern on the chord roots, in the recipe's register."""
    grid = Grid(meter, STEP, swing, 0.25)
    notes = []
    count = 0
    for bar in range(bars):
        for step in pattern.steps:
            t = grid.position(bar, step - 1)
            chord = harmony.at(t).chord
            pc = chord.root
            if pattern.third_every and count % pattern.third_every == pattern.third_every - 1 and len(chord.intervals) > 1:
                pc = (chord.root + chord.intervals[1]) % 12
            notes.append(Note(_fold(pc, pattern.low, pattern.high), t, pattern.length, pattern.velocity))
            count += 1
    return notes


# --------------------------------------------------------------------------- chords


@dataclass(frozen=True)
class ChordPattern:
    stab_steps: tuple[tuple[int, ...], ...]  # per bar of a cycle
    stab_length: float
    stab_velocity: float
    pad_velocity: float  # quiet held chord under the stabs; 0 = none
    low: int
    high: int
    sevenths: bool


# Stabs 1/16-1/8 (here a dotted 16th) on syncopated 16ths, a quiet pad underneath, 7th chords.
HOUSE_CHORDS = ChordPattern(((4, 7, 11), (4, 7, 11, 15)), stab_length=0.375, stab_velocity=96, pad_velocity=48, low=55, high=72, sevenths=True)
CHORDS: dict[str, ChordPattern] = {"house": HOUSE_CHORDS}


def _voicing(chord: Chord, low: int, high: int, previous: tuple[int, ...] | None) -> tuple[int, ...]:
    """Close voicing in [low, high], nearest to the previous one (smooth movement)."""
    options = []
    for inversion in range(len(chord.intervals)):
        pcs = [(chord.root + i) % 12 for i in chord.intervals]
        pcs = pcs[inversion:] + pcs[:inversion]
        for base in range(low, high - 6):
            if base % 12 != pcs[0]:
                continue
            voice = [base]
            for pc in pcs[1:]:
                nxt = voice[-1] + 1
                while nxt % 12 != pc:
                    nxt += 1
                voice.append(nxt)
            if voice[-1] <= high:
                options.append(tuple(voice))
    if not options:
        return tuple(sorted(low + (chord.root + i - low) % 12 for i in chord.intervals))
    if previous is None:
        middle = (low + high) / 2
        return min(options, key=lambda v: abs(sum(v) / len(v) - middle))
    return min(options, key=lambda v: sum(abs(a - b) for a, b in zip(sorted(v), sorted(previous))))


def seventh_harmony(harmony: Harmony, scale: Scale) -> Harmony:
    """The same chords as diatonic 7th chords (m7, maj7, 7), as House recipes ask."""
    from midibakery.compose.harmony import Segment
    from midibakery.compose.theory import diatonic_chord

    segments = []
    for segment in harmony.segments:
        chord = segment.chord
        if chord.degree is not None and len(scale) == 7 and len(chord.intervals) == 3:
            chord = diatonic_chord(scale, chord.degree, 4)
        segments.append(Segment(segment.start, segment.length, chord))
    return Harmony(tuple(segments), harmony.source)


def generate_recipe_chords(pattern: ChordPattern, harmony: Harmony, meter: Meter, bars: int, swing: float, stabs: bool, pad: bool) -> list[Note]:
    grid = Grid(meter, STEP, swing, 0.25)
    notes: list[Note] = []
    previous = None
    for segment in harmony.segments:
        voice = _voicing(segment.chord, pattern.low, pattern.high, previous)
        previous = voice
        if pad:
            velocity = pattern.pad_velocity if stabs else pattern.pad_velocity + 22
            notes += [Note(p, segment.start, segment.length, velocity) for p in voice]
        if not stabs:
            continue
        first_bar = int(segment.start // meter.beats_per_bar + 1e-9)
        last_bar = int((segment.end - 1e-9) // meter.beats_per_bar)
        for bar in range(first_bar, min(bars, last_bar + 1)):
            for step in pattern.stab_steps[bar % len(pattern.stab_steps)]:
                t = grid.position(bar, step - 1)
                if segment.start - 1e-9 <= t < segment.end - 1e-9:
                    notes += [Note(p, t, pattern.stab_length, pattern.stab_velocity) for p in voice]
    return notes
