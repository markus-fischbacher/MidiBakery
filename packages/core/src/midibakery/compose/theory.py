"""Music theory core: scales from Live's song data, chords, functional harmony, voice leading.

Pitches are MIDI numbers with Live's naming (60 = C3). Pitch classes are 0..11
with 0 = C. Scales come from ``Song.root_note`` and ``Song.scale_intervals``, so
every scale Live offers works without a hard-coded table.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import Any

NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
MAJOR = (0, 2, 4, 5, 7, 9, 11)


def clamp_pitch(pitch: int) -> int:
    return max(0, min(127, int(pitch)))


def pitch_name(pitch: int) -> str:
    """Live's octave numbering: 60 -> C3."""
    return f"{NOTE_NAMES[pitch % 12]}{pitch // 12 - 2}"


def octave_base(octave: int) -> int:
    """MIDI pitch of C in Live's octave `octave` (C3 = 60, C1 = 36)."""
    return 12 * (octave + 2)


@dataclass(frozen=True)
class Scale:
    root: int
    intervals: tuple[int, ...] = MAJOR
    name: str = "Major"

    def __post_init__(self) -> None:
        if not self.intervals or self.intervals[0] != 0:
            raise ValueError("scale intervals must start with 0")
        if list(self.intervals) != sorted(set(self.intervals)) or self.intervals[-1] > 11:
            raise ValueError("scale intervals must be ascending within one octave")

    @classmethod
    def from_song(cls, song: dict[str, Any]) -> Scale:
        """Build from a ``song.get`` result; falls back to C Major if Live has no scale data."""
        if not song.get("scale_intervals"):
            return cls(int(song.get("root_note", 0)) % 12)
        intervals = tuple(int(i) for i in song["scale_intervals"])
        return cls(int(song.get("root_note", 0)) % 12, intervals, song.get("scale_name") or "")

    def __len__(self) -> int:
        return len(self.intervals)

    @property
    def pitch_classes(self) -> frozenset[int]:
        return frozenset((self.root + i) % 12 for i in self.intervals)

    def contains(self, pitch: int) -> bool:
        return pitch % 12 in self.pitch_classes

    def pitch(self, degree: int, octave: int = 3) -> int:
        """Pitch of a scale degree (0-based, any integer) counted from the root in `octave`."""
        octaves, index = divmod(degree, len(self.intervals))
        return octave_base(octave) + self.root + 12 * octaves + self.intervals[index]

    def degree_of(self, pitch: int) -> int | None:
        """Absolute degree (inverse of ``pitch`` with octave -2 as origin), None if off-scale."""
        rel = pitch - self.root
        octaves, pc = divmod(rel, 12)
        if pc not in self.intervals:
            return None
        return octaves * len(self.intervals) + self.intervals.index(pc)

    def pitch_of_degree(self, absolute_degree: int) -> int:
        octaves, index = divmod(absolute_degree, len(self.intervals))
        return self.root + 12 * octaves + self.intervals[index]

    def snap(self, pitch: int, direction: int = 0) -> int:
        """Nearest scale pitch. Ties go down unless `direction` > 0."""
        if self.contains(pitch):
            return pitch
        for distance in range(1, 12):
            first, second = (pitch + distance, pitch - distance) if direction > 0 else (pitch - distance, pitch + distance)
            if self.contains(first):
                return first
            if self.contains(second):
                return second
        return pitch

    def step(self, pitch: int, steps: int) -> int:
        """Move `steps` scale steps from `pitch` (snapped into the scale first)."""
        degree = self.degree_of(self.snap(pitch))
        assert degree is not None
        return self.pitch_of_degree(degree + steps)

    def describe(self) -> str:
        return f"{NOTE_NAMES[self.root]} {self.name}".strip()


# --------------------------------------------------------------------------
# Chords
# --------------------------------------------------------------------------

QUALITIES: dict[str, tuple[int, ...]] = {
    "": (0, 4, 7),
    "m": (0, 3, 7),
    "dim": (0, 3, 6),
    "aug": (0, 4, 8),
    "sus2": (0, 2, 7),
    "sus4": (0, 5, 7),
    "7": (0, 4, 7, 10),
    "maj7": (0, 4, 7, 11),
    "m7": (0, 3, 7, 10),
    "m7b5": (0, 3, 6, 10),
    "dim7": (0, 3, 6, 9),
    "mmaj7": (0, 3, 7, 11),
    "6": (0, 4, 7, 9),
    "m6": (0, 3, 7, 9),
    "add9": (0, 4, 7, 14),
}
_QUALITY_BY_SHAPE = {shape: name for name, shape in QUALITIES.items()}
ROMAN = ("I", "II", "III", "IV", "V", "VI", "VII")


@dataclass(frozen=True)
class Chord:
    root: int  # pitch class
    intervals: tuple[int, ...]  # from the root, ascending, may exceed 11 (extensions)
    degree: int | None = None  # 0-based scale degree when diatonic

    @property
    def pitch_classes(self) -> tuple[int, ...]:
        return tuple((self.root + i) % 12 for i in self.intervals)

    @property
    def symbol(self) -> str:
        quality = _QUALITY_BY_SHAPE.get(self.intervals)
        if quality is None:
            quality = "(" + ",".join(str(i) for i in self.intervals) + ")"
        return NOTE_NAMES[self.root] + quality

    def contains(self, pitch: int) -> bool:
        return pitch % 12 in self.pitch_classes

    def roman(self) -> str | None:
        if self.degree is None or self.degree >= len(ROMAN):
            return None
        numeral = ROMAN[self.degree]
        third = self.intervals[1] if len(self.intervals) > 1 else 4
        numeral = numeral if third == 4 else numeral.lower()
        if self.intervals[:3] == (0, 3, 6):
            numeral += "°"
        if len(self.intervals) > 3:
            numeral += "7"
        return numeral


def diatonic_chord(scale: Scale, degree: int, size: int = 3) -> Chord:
    """Stack every other scale tone from `degree` (thirds in heptatonic scales)."""
    n = len(scale)
    degree %= n
    base = scale.pitch_of_degree(degree)
    pitches = [scale.pitch_of_degree(degree + 2 * k) for k in range(size)]
    return Chord(base % 12, tuple(p - base for p in pitches), degree)


_ROMAN_RE = re.compile(r"^(?P<acc>[b#]?)(?P<num>VII|VI|IV|V|III|II|I)(?P<suffix>°|o|dim|\+|aug|maj7|7|sus2|sus4)?$", re.I)
_NAME_RE = re.compile(r"^(?P<root>[A-G])(?P<acc>[b#]?)(?P<quality>maj7|mmaj7|m7b5|m7|m6|m|dim7|dim|aug|sus2|sus4|add9|7|6)?$")


def parse_chord(token: str, scale: Scale) -> Chord:
    """Roman numeral relative to the scale ("vi", "V7", "bVII", "ii°") or a chord name ("Am7", "F#")."""
    token = token.strip()
    match = _NAME_RE.match(token)
    if match:
        pc = NOTE_NAMES.index(match["root"]) + {"": 0, "#": 1, "b": -1}[match["acc"]]
        chord = Chord(pc % 12, QUALITIES[match["quality"] or ""])
        degree = scale.degree_of(chord.root + 120)
        return Chord(chord.root, chord.intervals, None if degree is None else degree % len(scale))
    match = _ROMAN_RE.match(token)
    if not match:
        raise ValueError(f"cannot parse chord {token!r}; use roman numerals (I, vi, V7, bVII) or names (Am, F#m7)")
    numeral = match["num"]
    degree = ROMAN.index(numeral.upper())
    suffix = (match["suffix"] or "").lower()
    seventh = suffix in ("7", "maj7")
    if not match["acc"] and len(scale) == 7 and suffix in ("", "7"):
        diatonic = diatonic_chord(scale, degree, 4 if seventh else 3)
        # Case agrees with the scale's own chord ("vi" in major, "VII" in minor): stay diatonic.
        if numeral.isupper() == (diatonic.intervals[1] == 4):
            return diatonic
    # Chromatic or explicitly qualified chord: case decides major/minor.
    major_root = (scale.root + MAJOR[degree] + {"": 0, "#": 1, "b": -1}[match["acc"]]) % 12
    if match["acc"] or len(scale) != 7:
        root = major_root
    else:
        root = scale.pitch_of_degree(degree) % 12
    if suffix in ("°", "o", "dim"):
        quality = "dim7" if seventh else "dim"
    elif suffix in ("+", "aug"):
        quality = "aug"
    elif suffix in ("sus2", "sus4"):
        quality = suffix
    elif suffix == "maj7":
        quality = "maj7" if numeral.isupper() else "mmaj7"
    elif numeral.isupper():
        quality = "7" if seventh else ""
    else:
        quality = "m7" if seventh else "m"
    scale_degree = scale.degree_of(root + 120)
    return Chord(root, QUALITIES[quality], None if scale_degree is None else scale_degree % len(scale))


def parse_progression(text: str, scale: Scale) -> list[Chord]:
    tokens = [t for t in re.split(r"[\s,|\-–]+", text) if t]
    if not tokens:
        raise ValueError("empty chord progression")
    return [parse_chord(t, scale) for t in tokens]


# Functional harmony for heptatonic scales: tonic, subdominant and dominant families.
FUNCTIONS = {0: "T", 2: "T", 5: "T", 1: "S", 3: "S", 4: "D", 6: "D"}
_FUNCTION_DEGREES = {"T": (0, 5, 2), "S": (3, 1), "D": (4, 6)}
_FUNCTION_WEIGHTS = {"T": (0.6, 0.3, 0.1), "S": (0.65, 0.35), "D": (0.8, 0.2)}
_NEXT_FUNCTION = {"T": (("S", 0.5), ("D", 0.25), ("T", 0.25)), "S": (("D", 0.6), ("T", 0.25), ("S", 0.15)), "D": (("T", 1.0),)}


def functional_progression(scale: Scale, length: int, rng: random.Random, sevenths: bool = False) -> list[Chord]:
    """A cadence-aware progression: starts on the tonic, moves T -> S -> D -> T,
    and ends on a dominant (loop turnaround) for lengths of 4 and more."""
    size = 4 if sevenths else 3
    n = len(scale)
    if n != 7:
        # No functional map for pentatonic/exotic scales: tonic first, then distinct degrees.
        degrees = [0]
        while len(degrees) < length:
            choice = rng.choice([d for d in range(n) if d != degrees[-1]] or [0])
            degrees.append(choice)
        return [diatonic_chord(scale, d, size) for d in degrees]

    degrees = [0]
    function = "T"
    for i in range(1, length):
        last = i == length - 1
        if last and length >= 4:
            function = "D"
        else:
            options, weights = zip(*_NEXT_FUNCTION[function])
            function = rng.choices(options, weights)[0]
        # Diminished triads (vii° in major, ii° in minor) make weak loop chords; leave them out.
        candidates = [
            d for d in _FUNCTION_DEGREES[function] if d != degrees[-1] and diatonic_chord(scale, d).intervals[:3] != (0, 3, 6)
        ]
        weights = [_FUNCTION_WEIGHTS[function][_FUNCTION_DEGREES[function].index(d)] for d in candidates]
        if not candidates:
            candidates, weights = [0], [1.0]
        degree = rng.choices(candidates, weights)[0]
        degrees.append(degree)
    return [diatonic_chord(scale, d, size) for d in degrees]


def chord_pitches_in_range(chord: Chord, low: int, high: int) -> list[int]:
    return [p for p in range(low, high + 1) if chord.contains(p)]


def voicings(chord: Chord, low: int, high: int) -> list[tuple[int, ...]]:
    """All close-position voicings (any inversion, any octave) inside [low, high]."""
    pcs = chord.pitch_classes
    found: list[tuple[int, ...]] = []
    for rotation in range(len(pcs)):
        order = pcs[rotation:] + pcs[:rotation]
        for start in range(low, low + 12):
            if start % 12 != order[0]:
                continue
            voicing = [start]
            for pc in order[1:]:
                nxt = voicing[-1] + 1
                while nxt % 12 != pc:
                    nxt += 1
                voicing.append(nxt)
            shift = 0
            while voicing[-1] + shift <= high:
                candidate = tuple(p + shift for p in voicing)
                if candidate[0] >= low:
                    found.append(candidate)
                shift += 12
    return sorted(set(found))


def _movement(a: tuple[int, ...], b: tuple[int, ...]) -> int:
    if len(a) == len(b):
        return sum(abs(x - y) for x, y in zip(a, b))
    return sum(min(abs(x - y) for y in b) for x in a) + sum(min(abs(x - y) for x in a) for y in b)


def voice_lead(chords: list[Chord], low: int = 52, high: int = 76) -> list[tuple[int, ...]]:
    """Pick one voicing per chord so voices move as little as possible.

    The first chord sits closest to the middle of the range; each following
    chord takes the voicing with the smallest total movement, with a small
    pull back to the centre so long progressions do not drift to an edge.
    """
    center = (low + high) / 2
    result: list[tuple[int, ...]] = []
    for chord in chords:
        options = voicings(chord, low, high)
        if not options:
            raise ValueError(f"range {low}..{high} is too narrow for {chord.symbol}")

        def cost(v: tuple[int, ...]) -> tuple[float, tuple[int, ...]]:
            drift = abs(sum(v) / len(v) - center)
            if not result:
                return (drift, v)
            return (_movement(result[-1], v) + 0.25 * drift, v)

        result.append(min(options, key=cost))
    return result


def detect_chord(weights: dict[int, float], scale: Scale, bass_pc: int | None = None) -> Chord | None:
    """Best diatonic triad for pitch-class weights (e.g. note durations in a segment)."""
    if not weights:
        return None
    total = sum(weights.values())
    best: tuple[float, int] | None = None
    for degree in range(len(scale)):
        chord = diatonic_chord(scale, degree)
        pcs = chord.pitch_classes
        inside = sum(w for pc, w in weights.items() if pc in pcs)
        score = inside - 0.6 * (total - inside)
        score += 0.15 * total * (weights.get(chord.root, 0) > 0)
        if bass_pc is not None and bass_pc == chord.root:
            score += 0.2 * total
        if best is None or score > best[0] + 1e-9:
            best = (score, degree)
    assert best is not None
    return diatonic_chord(scale, best[1])
