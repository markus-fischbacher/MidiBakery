"""Chord timelines: from a progression, from functional harmony, or detected in an existing clip."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any

from midibakery.compose.rhythm import Meter
from midibakery.compose.theory import Chord, Scale, detect_chord, diatonic_chord, functional_progression, parse_progression


@dataclass(frozen=True)
class Segment:
    start: float
    length: float
    chord: Chord

    @property
    def end(self) -> float:
        return self.start + self.length


@dataclass(frozen=True)
class Harmony:
    segments: tuple[Segment, ...]
    source: str  # "progression", "auto" or "clip"
    explicit: bool = False  # chords the user named: generators must keep their quality as written

    def at(self, time: float) -> Segment:
        for segment in self.segments:
            if segment.start <= time + 1e-9 < segment.end:
                return segment
        return self.segments[-1] if time >= self.segments[-1].start else self.segments[0]

    def describe(self) -> list[str]:
        result = []
        for segment in self.segments:
            roman = segment.chord.roman()
            result.append(f"{segment.chord.symbol} ({roman})" if roman else segment.chord.symbol)
        return result

    def for_length(self, meter: Meter, bars: int) -> Harmony:
        """The same chords cycled or cut to cover `bars` bars."""
        total = meter.beats_per_bar * bars
        if not self.segments:
            return self
        cycle = self.segments[-1].end
        segments = []
        offset = 0.0
        while offset < total - 1e-9:
            for segment in self.segments:
                start = offset + segment.start
                if start >= total - 1e-9:
                    break
                segments.append(Segment(start, min(segment.length, total - start), segment.chord))
            offset += cycle
        return Harmony(tuple(segments), self.source, self.explicit)


def segment_count(meter: Meter, bars: int, chords_per_bar: float) -> int:
    """Segments that cover every beat of `bars` bars; the last one is cut to the end."""
    return max(1, math.ceil(bars * chords_per_bar - 1e-9))


def timeline(chords: list[Chord], meter: Meter, bars: int, chords_per_bar: float, source: str) -> Harmony:
    length = meter.beats_per_bar / chords_per_bar
    total = meter.beats_per_bar * bars
    count = segment_count(meter, bars, chords_per_bar)
    segments = tuple(Segment(i * length, min(length, total - i * length), chords[i % len(chords)]) for i in range(count))
    return Harmony(segments, source)


def from_progression(text: str, scale: Scale, meter: Meter, bars: int, chords_per_bar: float) -> Harmony:
    return timeline(parse_progression(text, scale), meter, bars, chords_per_bar, "progression")


def auto(scale: Scale, meter: Meter, bars: int, chords_per_bar: float, rng: random.Random, sevenths: bool = False) -> Harmony:
    count = segment_count(meter, bars, chords_per_bar)
    # A 4-chord cycle repeats like a real loop; longer clips get a second half.
    cycle = min(count, 4 if count <= 8 else 8)
    chords = functional_progression(scale, cycle, rng, sevenths)
    return timeline(chords, meter, bars, chords_per_bar, "auto")


def detect(notes: list[dict[str, Any]], scale: Scale, meter: Meter, bars: int, chords_per_bar: float) -> Harmony:
    """Chords of an existing clip, one per segment, weighted by how long each pitch class sounds."""
    length = meter.beats_per_bar / chords_per_bar
    total = meter.beats_per_bar * bars
    count = segment_count(meter, bars, chords_per_bar)
    chords: list[Chord] = []
    for i in range(count):
        start, end = i * length, min((i + 1) * length, total)
        weights: dict[int, float] = {}
        lowest: tuple[int, int] | None = None
        for note in notes:
            if note.get("mute"):
                continue
            overlap = min(end, note["start_time"] + note["duration"]) - max(start, note["start_time"])
            if overlap <= 0:
                continue
            pc = note["pitch"] % 12
            weights[pc] = weights.get(pc, 0.0) + overlap
            if lowest is None or note["pitch"] < lowest[0]:
                lowest = (note["pitch"], pc)
        chord = detect_chord(weights, scale, lowest[1] if lowest else None)
        if chord is None:
            chord = chords[-1] if chords else diatonic_chord(scale, 0)
        chords.append(chord)
    segments = tuple(Segment(i * length, min(length, total - i * length), c) for i, c in enumerate(chords))
    return Harmony(segments, "clip")


# Chord shapes recognized in a supplied clip, simplest first. Unlike `detect`, chords outside the scale keep
# their own quality (a D major chord in C major stays D major).
CLIP_SHAPES = ((0, 4, 7), (0, 3, 7), (0, 3, 6), (0, 4, 8), (0, 4, 7, 10), (0, 3, 7, 10), (0, 4, 7, 11))
MIN_CLIP_CONFIDENCE = 0.6  # share of a segment's sounding weight the chosen chord must explain


def _clip_chord(weights: dict[int, float], scale: Scale, lowest_pc: int | None) -> Chord | None:
    total = sum(weights.values())
    if total <= 0:
        return None
    best: tuple[float, Chord, float] | None = None
    for root in range(12):
        for shape in CLIP_SHAPES:
            pcs = {(root + i) % 12 for i in shape}
            inside = sum(w for pc, w in weights.items() if pc in pcs)
            if weights.get(root, 0) <= 0:
                continue
            score = inside - 0.8 * (total - inside) - 0.1 * total * (len(shape) - 3)
            if lowest_pc == root:
                score += 0.2 * total
            if best is None or score > best[0] + 1e-9:
                best = (score, Chord(root, shape), inside / total)
    if best is None or best[2] < MIN_CLIP_CONFIDENCE:
        return None
    chord = best[1]
    for degree in range(len(scale)):
        diatonic = diatonic_chord(scale, degree)
        if diatonic.root == chord.root and diatonic.intervals == chord.intervals:
            return diatonic
    return chord


def detect_clip(notes: list[dict[str, Any]], scale: Scale, meter: Meter, bars: int, chords_per_bar: float) -> tuple[Harmony, list[int]]:
    """The chords a supplied clip plays, one per segment, and the indexes of segments with no confident chord
    (silence or no clear chord). Those take the previous chord (the first one the next), never a guess of
    their own; when no segment is confident, the first chord is the scale's tonic and every index is listed."""
    length = meter.beats_per_bar / chords_per_bar
    total = meter.beats_per_bar * bars
    count = segment_count(meter, bars, chords_per_bar)
    found: list[Chord | None] = []
    for i in range(count):
        start, end = i * length, min((i + 1) * length, total)
        weights: dict[int, float] = {}
        lowest: tuple[int, int] | None = None
        for note in notes:
            if note.get("mute"):
                continue
            overlap = min(end, note["start_time"] + note["duration"]) - max(start, note["start_time"])
            if overlap <= 0:
                continue
            pc = note["pitch"] % 12
            weights[pc] = weights.get(pc, 0.0) + overlap
            if lowest is None or note["pitch"] < lowest[0]:
                lowest = (note["pitch"], pc)
        found.append(_clip_chord(weights, scale, lowest[1] if lowest else None))
    missing = [i for i, chord in enumerate(found) if chord is None]
    chords: list[Chord] = []
    for i, chord in enumerate(found):
        if chord is None:
            chord = next((c for c in found[i + 1:] if c is not None), None) if not chords else chords[-1]
            chord = chord or diatonic_chord(scale, 0)
        chords.append(chord)
    segments = tuple(Segment(i * length, min(length, total - i * length), c) for i, c in enumerate(chords))
    return Harmony(segments, "clip", explicit=True), missing
