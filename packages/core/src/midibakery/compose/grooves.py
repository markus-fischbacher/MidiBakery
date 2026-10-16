"""Genre grooves from the recipes in docs/GENRES.md: drum lanes, bass and chord rhythms as data.

Steps count 1-16 in a 4/4 bar of 16ths (step 1 = beat 1, 5 = beat 2, 9 = beat 3,
13 = beat 4). A lane plays its steps every bar, or only in some bars of a cycle
(e.g. the ghost clap in bar 2 of every 2). Parts pick lanes: an intro may play
only kick and hats, a build everything but the kick.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field, replace

from midibakery.compose.drums import DrumMap
from midibakery.compose.harmony import Harmony, Segment
from midibakery.compose.notes import Note, dedupe
from midibakery.compose.rhythm import Grid, Meter
from midibakery.compose.theory import Chord, Scale, diatonic_chord

STEP = 0.25
MINOR_TRIAD = (0, 3, 7)
CORE_ROLES = frozenset({"kick", "snare", "clap", "closed_hat"})


# --------------------------------------------------------------------------- drums


@dataclass(frozen=True)
class Lane:
    role: str  # drum role as in DrumMap (kick, clap, snare, closed_hat, open_hat, shaker, ride, rim, ...)
    steps: tuple[int, ...]
    velocity: float
    length: float = 0.25
    jitter: float = 0.0  # +- random velocity
    probability: float = 1.0
    cycle: int = 1  # plays in bars where bar % cycle in `bars`
    bars: tuple[int, ...] = (0,)
    alternate: float = 0.0  # every second step this much quieter (hats that "dance")
    swing: bool = True  # Techno and D&B keep kick and main snares straight
    accents: dict[int, float] = field(default_factory=dict)  # step -> velocity offset (ride dips on 1 and 3)


@dataclass(frozen=True)
class Roll:
    """A hat or snare roll: `count` hits of `division` beats from `start` (beats in the bar), velocity ramping."""

    role: str
    start: float
    division: float
    count: int
    velocity_from: float
    velocity_to: float
    cycle: int = 2
    bars: tuple[int, ...] = (1,)


@dataclass(frozen=True)
class Groove:
    lanes: tuple[Lane, ...]
    parts: dict[str, frozenset[str]]  # part -> lane roles
    swing: float  # 0..1 of a triplet on 16ths; MPC 60% = 0.6
    late_lanes: frozenset[str] = frozenset()  # join only in the second half of a long "full" part
    rolls: tuple[Roll, ...] = ()  # in parts that play the roll's role
    fill_role: str = "snare"


_HOUSE_PARTS = {
    "kick_hats": frozenset({"kick", "closed_hat"}),
    "groove": frozenset({"kick", "clap", "closed_hat", "shaker"}),
    "full": frozenset({"kick", "clap", "closed_hat", "shaker", "open_hat"}),
    "no_kick": frozenset({"clap", "closed_hat", "shaker", "open_hat"}),
    "sparse": frozenset({"closed_hat", "shaker"}),
}

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
    parts=_HOUSE_PARTS,
    swing=0.6,  # Attack: 55-65 % on 16ths, on all parts
    late_lanes=frozenset({"open_hat"}),  # EDMProd: open hat added in the second half of the drop
)

# Peak-Time Techno: straight kick and bass, light swing on hats/percussion only, a ride that ducks
# on 1 and 3 and arrives at the peaks, ghost kick before beat 4, rim and low tom, sparse clap.
PEAK_TIME = Groove(
    lanes=(
        Lane("kick", (1, 5, 9, 13), 124, swing=False),
        Lane("kick", (12,), 52, probability=0.7, swing=False),  # ghost kick before beat 4 (Attack)
        Lane("clap", (5, 13), 96, length=0.5, swing=False),
        Lane("closed_hat", tuple(range(1, 17)), 82, jitter=8, alternate=28),  # 16ths, "dancing" velocity
        Lane("open_hat", (3, 7, 11, 15), 92, length=0.5, jitter=6),
        Lane("ride", (1, 3, 5, 7, 9, 11, 13, 15), 84, length=0.5, jitter=5, accents={1: -20, 9: -20}),
        Lane("rim", (1, 5, 6, 9, 13, 14), 66, jitter=8),
        Lane("low_tom", (14,), 74, probability=0.6),
        Lane("shaker", tuple(range(1, 17)), 44, jitter=12),
    ),
    parts={
        "kick_hats": frozenset({"kick", "closed_hat"}),
        "groove": frozenset({"kick", "closed_hat", "open_hat", "rim", "shaker"}),
        "full": frozenset({"kick", "clap", "closed_hat", "open_hat", "rim", "low_tom", "shaker", "ride"}),
        "no_kick": frozenset({"clap", "closed_hat", "open_hat", "rim", "shaker"}),
        "sparse": frozenset({"closed_hat", "shaker", "rim"}),
    },
    swing=0.15,
    late_lanes=frozenset({"ride"}),
    rolls=(Roll("clap", 1.0, 0.25, 12, 50, 100, cycle=4, bars=(3,)),),  # EDMProd: 16th clap roll in bar 4 from beat 2
    fill_role="clap",
)

MELODIC_TECHNO = Groove(
    lanes=(
        Lane("kick", (1, 5, 9, 13), 118, swing=False),
        Lane("clap", (5, 13), 92, length=0.5, swing=False),
        Lane("closed_hat", (3, 7, 11, 15), 86, jitter=6),
        Lane("closed_hat", (2, 4, 6, 8, 10, 12, 14, 16), 48, jitter=8),  # the quieter 16th layer
        Lane("shaker", tuple(range(1, 17)), 42, jitter=10),
        Lane("rim", (4, 8, 12, 16), 60, jitter=8, probability=0.8),
    ),
    parts={
        "kick_hats": frozenset({"kick", "closed_hat"}),
        "groove": frozenset({"kick", "clap", "closed_hat", "shaker", "rim"}),
        "full": frozenset({"kick", "clap", "closed_hat", "shaker", "rim"}),
        "no_kick": frozenset({"clap", "closed_hat", "shaker"}),
        "sparse": frozenset({"closed_hat", "shaker"}),
    },
    swing=0.1,
    fill_role="clap",
)

# Drum & Bass two-step: kick 1 + 11, snare 5 + 13 (straight), ghost snares 3/8/10/16, a skip snare
# on 12 every other bar, 8th hats alternating loud/soft, ride in the drops' second halves.
DNB = Groove(
    lanes=(
        Lane("kick", (1, 11), 120, swing=False),
        Lane("snare", (5,), 112, swing=False),
        Lane("snare", (13,), 122, swing=False),
        Lane("snare", (3, 8, 10, 16), 40, jitter=8, probability=0.6, swing=False),
        Lane("snare", (12,), 60, cycle=2, bars=(1,), swing=False),
        Lane("closed_hat", (1, 3, 5, 7, 9, 11, 13, 15), 96, jitter=6, alternate=28),
        Lane("ride", (1, 3, 5, 7, 9, 11, 13, 15), 70, jitter=6),
        Lane("shaker", tuple(range(1, 17)), 40, jitter=10),
    ),
    parts={
        "kick_hats": frozenset({"kick", "closed_hat"}),
        "groove": frozenset({"kick", "snare", "closed_hat", "shaker"}),
        "full": frozenset({"kick", "snare", "closed_hat", "shaker", "ride"}),
        "no_kick": frozenset({"snare", "closed_hat", "shaker"}),
        "sparse": frozenset({"closed_hat", "shaker"}),
    },
    swing=0.1,
    late_lanes=frozenset({"ride"}),
)

# EDM Trap at half time: snare on beat 3 (step 9), kick on 1 plus one before the snare and an offbeat,
# 8th hats with 32nd and triplet rolls that ramp up, one open hat on an offbeat.
TRAP = Groove(
    lanes=(
        Lane("kick", (1, 8, 11), 118),
        Lane("snare", (9,), 116, length=0.5),
        Lane("clap", (9,), 100, length=0.5),
        Lane("closed_hat", (1, 3, 5, 7, 9, 11, 13, 15), 84, jitter=8, alternate=16),
        Lane("open_hat", (7,), 80, length=0.5, cycle=2, bars=(0,)),
        Lane("rim", (16,), 70, probability=0.5),
    ),
    parts={
        "kick_hats": frozenset({"kick", "closed_hat"}),
        "groove": frozenset({"kick", "snare", "clap", "closed_hat"}),
        "full": frozenset({"kick", "snare", "clap", "closed_hat", "open_hat", "rim"}),
        "no_kick": frozenset({"snare", "clap", "closed_hat"}),
        "sparse": frozenset({"closed_hat"}),
    },
    swing=0.12,
    rolls=(
        Roll("closed_hat", 3.0, 0.125, 8, 60, 105, cycle=2, bars=(1,)),  # 1/32 roll at the end of every 2nd bar
        Roll("closed_hat", 1.5, 1 / 6, 3, 70, 95, cycle=4, bars=(2,)),  # 1/16 triplets before the snare
    ),
)

GROOVES: dict[str, Groove] = {
    "house": HOUSE,
    "melodic_techno": MELODIC_TECHNO,
    "peak_time_techno": PEAK_TIME,
    "drum_and_bass": DNB,
    "trap": TRAP,
}


def _hits(lane: Lane, grid: Grid, straight: Grid, bar: int, rng: random.Random) -> list[Note]:
    if bar % lane.cycle not in lane.bars:
        return []
    notes = []
    for i, step in enumerate(lane.steps):
        if lane.probability < 1.0 and rng.random() > lane.probability:
            continue
        velocity = lane.velocity - (lane.alternate if i % 2 else 0) + lane.accents.get(step, 0) + rng.uniform(-lane.jitter, lane.jitter)
        position = (grid if lane.swing else straight).position(bar, step - 1)
        notes.append(Note(-1, position, lane.length, velocity))
    return notes


def _fill(meter: Meter, bar: int, strong: bool, variant: int, drum_map: DrumMap, role: str) -> list[Note]:
    """Last beat(s) of a bar. Variants alternate so boundaries do not all sound the same;
    the strong one (into a new section) is a roll over the whole bar, getting louder."""
    notes: list[Note] = []
    bpb = meter.beats_per_bar
    start = bar * bpb
    snare = drum_map.note(role) or drum_map.note("snare") or drum_map.note("clap")
    if strong:
        # 8ths for two beats, 16ths for one, 32nds for the last (Peak-Time / D&B recipes) - velocity 50 -> 115
        times = [start + t * 0.5 for t in range(4)] + [start + 2 + t * 0.25 for t in range(4)] + [start + 3 + t * 0.125 for t in range(8)]
        for i, t in enumerate(times):
            notes.append(Note(snare, t, 0.12, 50 + 65 * i / (len(times) - 1)))
        return notes
    if variant % 2 == 0:
        for i in range(4):  # 16ths on the last beat
            notes.append(Note(snare, start + bpb - 1 + i * 0.25, 0.2, 70 + 10 * i))
    else:
        toms = [drum_map.note(r) for r in ("high_tom", "mid_tom", "mid_tom", "low_tom")]
        for i, pitch in enumerate(toms):
            if pitch is not None:
                notes.append(Note(pitch, start + bpb - 1 + i * 0.25, 0.25, 92 - 4 * i))
    return notes


def _rolls(groove: Groove, roles: frozenset[str], meter: Meter, bar: int, phrase_bar: int, drum_map: DrumMap) -> tuple[list[Note], tuple[float, float] | None]:
    """Rolls in `bar` (timing) when `phrase_bar` (bar counted from the section start) is in their cycle."""
    notes: list[Note] = []
    cut = None
    for roll in groove.rolls:
        pitch = drum_map.note(roll.role)
        if roll.role not in roles or pitch is None or phrase_bar % roll.cycle not in roll.bars:
            continue
        start = bar * meter.beats_per_bar + roll.start
        for i in range(roll.count):
            velocity = roll.velocity_from + (roll.velocity_to - roll.velocity_from) * i / max(1, roll.count - 1)
            notes.append(Note(pitch, start + i * roll.division, roll.division * 0.9, velocity))
        end = start + roll.count * roll.division
        cut = (start, end) if cut is None else (min(cut[0], start), max(cut[1], end))
    return notes, cut


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
    """One part of a section: lanes of the part, rolls, fills every 8 bars (alternating), a strong fill
    at the end if asked, a crash on bar 1 if the kit has one. Velocity grows a little with energy."""
    grid = Grid(meter, STEP, groove.swing, 0.25)
    straight = Grid(meter, STEP, 0.0, 0.25)
    roles = groove.parts[part]
    # In a real kit a lane plays only if the kit has that sound: a ride must not land on a crash or a
    # closed hat. Only the core may borrow a related pad (clap <-> snare, closed hat <- pedal hat).
    playable = {r for r in roles if drum_map.source == "gm" or r in drum_map.detected or r in CORE_ROLES}
    notes: list[Note] = []
    for bar in range(bars):
        late = long_part and bar < bars // 2
        for lane in groove.lanes:
            if lane.role not in playable or (late and lane.role in groove.late_lanes):
                continue
            pitch = drum_map.note(lane.role)
            if pitch is None:
                continue
            notes += [replace(n, pitch=pitch) for n in _hits(lane, grid, straight, bar, rng)]
        rolled, span = _rolls(groove, roles, meter, bar, phrase_offset + bar, drum_map)
        if rolled and span is not None:
            lo, hi = span
            pitches = {n.pitch for n in rolled}
            notes = [n for n in notes if not (n.pitch in pitches and lo - 1e-9 <= n.start_time < hi)] + rolled
        last = bar == bars - 1
        boundary = (phrase_offset + bar) % 8 == 7
        if (last and fill_at_end) or (boundary and not last):
            fill = _fill(meter, bar, strong=last and fill_at_end, variant=(phrase_offset + bar) // 8, drum_map=drum_map, role=groove.fill_role)
            if fill:  # the fill replaces snare/clap/hats under it; the kick stays unless it is the strong one
                cut = min(n.start_time for n in fill)
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
class BassNote:
    step: int
    length: float  # beats; longer than the gap to the next note = legato/glide on a mono synth
    interval: int = 0  # semitones above the chord root; -1 = the chord's third
    velocity: float = 104


@dataclass(frozen=True)
class BassPattern:
    bars: tuple[tuple[BassNote, ...], ...]  # one tuple per bar of the cycle
    low: int  # MIDI range of the root
    high: int
    straight: bool = False  # no swing (Techno, D&B)
    vary_every: int = 0  # every n bars one note moves to another chord tone (slow variation)


def _bar(steps: tuple[int, ...], length: float, velocity: float = 104, interval: int = 0) -> tuple[BassNote, ...]:
    return tuple(BassNote(s, length, interval, velocity) for s in steps)


BASS: dict[str, BassPattern] = {
    # House: offbeats, the 3rd now and then (NI), MIDI 28-39.
    "house": BassPattern((_bar((3, 7, 11, 15), 0.42), _bar((3, 7, 11), 0.42) + (BassNote(15, 0.42, -1),)), 28, 39),
    # Peak-Time: rolling 16ths that leave each beat's first 16th to the kick, one note, an octave jump
    # in the second bar (EDMProd), 70-90 % gate, mid-bass MIDI 36-48.
    "peak_time_techno": BassPattern(
        (_bar((2, 3, 4, 6, 7, 8, 10, 11, 12, 14, 15, 16), 0.2, 100),
         _bar((2, 3, 4, 6, 7, 8, 10, 11, 12, 14, 15), 0.2, 100) + (BassNote(16, 0.2, 12, 96),)),
        36, 47, straight=True, vary_every=8,
    ),
    # Melodic Techno: between the kicks on the chord roots, MIDI 33-45.
    "melodic_techno": BassPattern((_bar((3, 4, 7, 8, 11, 12, 15, 16), 0.22, 98),), 33, 45, straight=True),
    # Liquid D&B sub: long notes on the roots (2 bars per chord), a syncopated push; MIDI 27-38.
    "drum_and_bass": BassPattern(
        ((BassNote(1, 1.6), BassNote(8, 0.4, 0, 96), BassNote(11, 1.4)),
         (BassNote(1, 1.6), BassNote(11, 0.9, 7, 98), BassNote(15, 0.6, 0, 92))),
        27, 38, straight=True,
    ),
    # Trap 808: under every kick, root -> fifth, a pickup into the next bar that glides (overlaps); MIDI 28-43.
    "trap": BassPattern(
        ((BassNote(1, 1.6), BassNote(8, 0.7), BassNote(11, 1.0)),
         (BassNote(1, 1.6), BassNote(8, 0.7, 7), BassNote(11, 0.9), BassNote(15, 0.6, 12, 96))),
        28, 43,
    ),
}


def _fold(pitch_class: int, low: int, high: int) -> int:
    pitch = low + (pitch_class - low) % 12
    return pitch if pitch <= high else pitch - 12


def generate_recipe_bass(pattern: BassPattern, harmony: Harmony, meter: Meter, bars: int, swing: float, rng: random.Random | None = None) -> list[Note]:
    """Bass from a step pattern on the chord roots, in the recipe's register."""
    grid = Grid(meter, STEP, 0.0 if pattern.straight else swing, 0.25)
    rng = rng or random.Random(0)
    notes = []
    for bar in range(bars):
        moved = pattern.vary_every and bar % pattern.vary_every == pattern.vary_every - 1
        moved_step = rng.choice(pattern.bars[bar % len(pattern.bars)]).step if moved else None
        for note in pattern.bars[bar % len(pattern.bars)]:
            t = grid.position(bar, note.step - 1)
            chord = harmony.at(t).chord
            root = _fold(chord.root, pattern.low, pattern.high)
            if note.interval == -1 and len(chord.intervals) > 1:
                pitch = _fold((chord.root + chord.intervals[1]) % 12, pattern.low, pattern.high)
            else:
                pitch = root + note.interval
            if note.step == moved_step and len(chord.intervals) > 2:
                pitch = root + chord.intervals[2]  # slow variation: one note to the fifth
            notes.append(Note(pitch, t, note.length, note.velocity))
    return notes


# --------------------------------------------------------------------------- chords


@dataclass(frozen=True)
class ChordPattern:
    stab_steps: tuple[tuple[int, ...], ...]  # per bar of a cycle; () = no stabs
    stab_length: float
    stab_velocity: float
    pad_velocity: float  # quiet held chord under the stabs; 0 = none
    low: int
    high: int
    sevenths: bool
    parallel: bool = False  # Peak-Time: one minor-triad shape moved as a block, same inversion
    drop_root: bool = False  # Trap: the 808 has the root
    # Development per 8-bar phrase (Peak-Time: "one change per 8 bars"): other rhythms of the same
    # family, the root doubled an octave up in every second phrase, velocity rising over 16 bars.
    phrase_rhythms: tuple[tuple[tuple[int, ...], ...], ...] = ()
    octave_phrases: bool = False
    ramp: float = 0.0  # velocity added from the start to the end of each 16 bars


CHORDS: dict[str, ChordPattern] = {
    # Stabs 1/16-1/8 (a dotted 16th) on syncopated 16ths over a quiet pad, 7th chords.
    "house": ChordPattern(((4, 7, 11), (4, 7, 11, 15)), 0.375, 96, 48, 55, 72, sevenths=True),
    # Parallel minor stabs, one 16th, mostly off the downbeat; 2 bars made 4 by moving a hit.
    "peak_time_techno": ChordPattern(
        ((3, 8, 11), (3, 6, 11, 14), (3, 8, 11), (4, 8, 12, 14)), 0.25, 88, 0, 60, 76, sevenths=False, parallel=True,
        phrase_rhythms=(
            ((3, 8, 11), (3, 6, 11, 14), (3, 8, 11), (4, 8, 12, 14)),
            ((3, 7, 11, 14), (3, 8, 12), (3, 7, 11, 14), (2, 6, 11, 15)),
            ((4, 8, 11, 16), (3, 8, 11, 14), (4, 8, 11), (3, 6, 8, 11, 14)),
        ),
        octave_phrases=True,
        ramp=22,
    ),
    # Melodic: pads only, 1 chord per 2 bars.
    "melodic_techno": ChordPattern(((),), 0.0, 0, 64, 55, 74, sevenths=False),
    # Liquid: held m7/maj7 pads, C3-C5-ish.
    "drum_and_bass": ChordPattern(((),), 0.0, 0, 66, 52, 72, sevenths=True),
    # Trap: soft plucks and a muted pad, without the root.
    "trap": ChordPattern(((1, 4, 7), (1, 4, 7, 11)), 0.5, 80, 42, 57, 74, sevenths=False, drop_root=True),
}


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
    """The same chords as diatonic 7th chords (m7, maj7, 7), as House and Liquid recipes ask."""
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
        chord = segment.chord
        if pattern.parallel:
            # Attack: one minor-triad shape in the same inversion, moved as a block (even out of key)
            base = pattern.low + (chord.root - pattern.low) % 12
            voice = tuple(base + i for i in MINOR_TRIAD)
        else:
            voice = _voicing(chord, pattern.low, pattern.high, previous)
        if pattern.drop_root:
            voice = tuple(p for p in voice if p % 12 != chord.root) or voice
        previous = voice
        if pad and pattern.pad_velocity:
            velocity = pattern.pad_velocity if stabs else pattern.pad_velocity + 22
            notes += [Note(p, segment.start, segment.length, velocity) for p in voice]
        if not stabs or not any(pattern.stab_steps):
            continue
        first_bar = int(segment.start // meter.beats_per_bar + 1e-9)
        last_bar = int((segment.end - 1e-9) // meter.beats_per_bar)
        for bar in range(first_bar, min(bars, last_bar + 1)):
            phrase = bar // 8
            rhythms = pattern.phrase_rhythms[phrase % len(pattern.phrase_rhythms)] if pattern.phrase_rhythms else pattern.stab_steps
            stack = voice + ((voice[0] + 12,) if pattern.octave_phrases and phrase % 2 == 1 and voice[0] + 12 not in voice else ())
            velocity = pattern.stab_velocity - pattern.ramp / 2 + pattern.ramp * (bar % 16) / 15 if pattern.ramp else pattern.stab_velocity
            for step in rhythms[bar % len(rhythms)]:
                t = grid.position(bar, step - 1)
                if segment.start - 1e-9 <= t < segment.end - 1e-9:
                    notes += [Note(p, t, pattern.stab_length, velocity) for p in stack]
    return notes
