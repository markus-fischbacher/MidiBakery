"""Counter melody generator: a second line that answers a main melody read from a clip.

The rules come from docs/COUNTER_MELODY.md (two tutorials, 13 techniques). `analyze` reads the main
melody (onsets, held notes, rests, density, range); `generate_counter` builds an onset pattern per
mode and then picks every pitch against the main note sounding at that moment and the chord.

Rests are phrase rests: the time between two main notes counts only when the next one starts a beat or more
after the last one ended. The short silence between the staccato hits of an arp or a riff is not room to answer.

Without a mode the main picks it (`resolve`): long phrase rests -> call_and_response, some rests or held notes
-> fill_the_gaps, a main without any -> passive_over_active (few long notes, no room to fill). Without a
register: above the main, unless that would go past C7 (pitch 96); then below.

Modes (rhythm and placement, then pitch):
- fill_the_gaps: starts only inside the main's phrase rests and held notes (a beat or longer).
- call_and_response: the same at phrase level: answers in the main's phrase rests, from their first 16th.
- passive_over_active: a third to half of a busy main's onsets, longer notes; more notes over a sparse one.
- contrasting_rhythm: an onset pattern that differs from the main's (sparse over dense, dense over sparse).
- harmonic_notes: follows the main's onsets (or an eighth late) on another consonant note, never the same pitch class.
- note_layering: the main's own pitch classes an octave away, same time or delayed.

Fixed figures (their rhythm does not follow the main's; the main only sets register, gaps and clashes):
- dotted_eighth_pulse: the 3-3-3-3-3-1 pulse, one chord tone per bar (`roll` rhythm).
- scale_staircase: the same pulse climbing one scale step every one or two bars, one step back before the restart.
- trance_dotted_eighth_staircase: the Trance video's 8-bar figure in scale degrees 0 0 1 1 2 2 4 4
  (`described` pitches, `roll` rhythm).
- echo_gap_answer: 3-4 short stepwise notes inside a long main note, then one longer note that sustains under
  the main's re-entry (needs held notes of 1.25 beats or more; a busy main gets nothing).

Rules every mode keeps: the register is clear of the main's range (above/below: a third or more, never past
pitch 96 or under 36; same only
with onsets that never meet the main's); on strong beats (meter accent >= 0.8) the interval to the sounding
main note is a third, sixth, fifth or octave (a unison only in note_layering); no parallel fifths or octaves
between consecutive notes; chord tones first, then scale tones. A note that fits nowhere is shortened,
then dropped: a gap is better than a clash. Same seed, same notes. A figure note whose pitch would clash
on a strong beat moves to the nearest scale tone (a fifth at most) that is consonant there.
"""

from __future__ import annotations

import math
import random
from bisect import bisect_left
from dataclasses import dataclass

from midibakery.compose.harmony import Harmony
from midibakery.compose.notes import Note, dedupe
from midibakery.compose.rhythm import Grid, Meter
from midibakery.compose.theory import Scale

RULE_MODES = ("fill_the_gaps", "call_and_response", "passive_over_active", "contrasting_rhythm", "harmonic_notes", "note_layering")
FIGURES = ("dotted_eighth_pulse", "scale_staircase", "trance_dotted_eighth_staircase", "echo_gap_answer")
MODES = RULE_MODES + FIGURES
REGISTERS = ("above", "below", "same")

STEP = 0.25  # one 16th, in beats
EPS = 1e-6
WINDOW = 14  # semitones the counter line may span above/below the main's range
CEILING, FLOOR = 96, 36  # C7 and C2: a counter line higher or lower is shrill or mud
MIN_ROOM = 9  # semitones the line needs; less room above the main puts it below
REST = 1.0  # beats of silence before the next main note that make a phrase rest
CONSONANT = frozenset({3, 4, 7, 8, 9})  # thirds, fifths, sixths (octaves and unisons are handled apart)
PARALLEL = frozenset({0, 7})
PULSE = (0, 3, 6, 9, 12, 15)  # 16th steps of the 3-3-3-3-3-1 figure (the lead templates' TUMBLE, counted from 0)
TRANCE_DEGREES = (0, 0, 1, 1, 2, 2, 4, 4)  # scale degree per bar, tonic 0 (`described`)
MIN_ECHO_HOLD = 1.25  # beats a main note must last to be answered by echo_gap_answer
MAX_SHIFT = 7  # semitones a clashing figure note may move
MAX_BEATS = {"passive_over_active": 4.0}  # longest note per mode, default 2 beats


@dataclass(frozen=True)
class MainLine:
    notes: tuple[Note, ...]  # sorted, looped or cut to the bar count
    meter: Meter
    bars: int
    onset_steps: frozenset[int]  # 16th steps from the clip start where a main note starts
    onsets_per_bar: tuple[int, ...]
    low: int
    high: int
    median: float

    @property
    def length(self) -> float:
        return self.meter.beats_per_bar * self.bars

    def at(self, time: float) -> Note | None:
        """The main note sounding at `time` (the latest started one)."""
        sounding = [n for n in self.notes if n.start_time <= time + EPS and time < n.end_time - EPS]
        return max(sounding, key=lambda n: (n.start_time, n.pitch)) if sounding else None

    def overlapping(self, start: float, end: float) -> list[Note]:
        return [n for n in self.notes if n.start_time < end - EPS and n.end_time > start + EPS]

    def silent(self, start: float, end: float) -> bool:
        """No main note sounds anywhere in [start, end): a rest the counter may own."""
        return not self.overlapping(start, end)

    def held(self) -> list[tuple[float, float]]:
        return [(n.start_time, n.end_time) for n in self.notes]

    def phrase_rests(self, min_gap: float = REST) -> list[tuple[float, float]]:
        """Rests of `min_gap` beats or more: a note holds until the next one starts when that comes sooner."""
        return phrase_rests(self.notes, self.length, min_gap)

    def rests(self) -> list[tuple[float, float]]:
        """Spans where no main note sounds."""
        gaps, cursor = [], 0.0
        for n in self.notes:
            if n.start_time > cursor + EPS:
                gaps.append((cursor, n.start_time))
            cursor = max(cursor, n.end_time)
        if cursor < self.length - EPS:
            gaps.append((cursor, self.length))
        return gaps

    def strong_times(self) -> list[float]:
        bpb = self.meter.beats_per_bar
        return [bar * bpb + p for bar in range(self.bars) for p in self.meter.pulses if self.meter.accent(p) >= 0.8]


def phrase_rests(notes: tuple[Note, ...] | list[Note], length: float, min_gap: float = REST) -> list[tuple[float, float]]:
    """Spans of `min_gap` beats or more in which no note sounds and none is about to: the staccato gaps of a
    riff (shorter than `min_gap`) belong to its phrase."""
    spans: list[list[float]] = []
    for n in sorted(notes, key=lambda n: n.start_time):
        if spans and n.start_time - spans[-1][1] < min_gap - EPS:
            spans[-1][1] = max(spans[-1][1], n.end_time)
        else:
            spans.append([n.start_time, n.end_time])
    rests, cursor = [], 0.0
    for start, end in spans:
        if start - cursor >= min_gap - EPS:
            rests.append((cursor, start))
        cursor = max(cursor, end)
    if length - cursor >= min_gap - EPS:
        rests.append((cursor, length))
    return rests


def analyze(main: list[Note], meter: Meter, bars: int) -> MainLine:
    """The main melody as a line of `bars` bars: it loops when shorter, is cut when longer."""
    notes = sorted((n for n in main if not n.mute), key=lambda n: (n.start_time, n.pitch))
    if not notes:
        raise ValueError("the main melody has no notes to answer")
    bpb = meter.beats_per_bar
    total = bpb * bars
    cycle = max(1, math.ceil(max(n.end_time for n in notes) / bpb - EPS)) * bpb  # whole bars
    looped: list[Note] = []
    for k in range(int(total // cycle) + 1):
        for n in notes:
            start = n.start_time + k * cycle
            if start < total - EPS:
                looped.append(Note(n.pitch, start, min(n.duration, total - start), n.velocity))
    onset_steps = frozenset(round(n.start_time / STEP) for n in looped)
    per_bar = tuple(sum(1 for n in looped if int(n.start_time // bpb + EPS) == bar) for bar in range(bars))
    pitches = sorted(n.pitch for n in looped)
    mid = len(pitches) // 2
    median = pitches[mid] if len(pitches) % 2 else (pitches[mid - 1] + pitches[mid]) / 2
    return MainLine(tuple(looped), meter, bars, onset_steps, per_bar, pitches[0], pitches[-1], median)


def consonant(interval: int, unison_ok: bool = False) -> bool:
    d = abs(interval)
    if d == 0:
        return unison_ok
    return d % 12 == 0 or d % 12 in CONSONANT


@dataclass(frozen=True)
class Onset:
    step: int  # 16th step from the clip start
    end: float | None = None  # the note must end by this beat (the end of a rest it answers in)
    source: Note | None = None  # the main note a layer copies


def _pick(rng: random.Random, pool: list[int], count: int, spacing: int = 2) -> list[int]:
    """`count` steps of `pool` at random, at least `spacing` steps apart."""
    chosen: list[int] = []
    for step in sorted(pool, key=lambda s: rng.random()):
        if len(chosen) >= count:
            break
        if all(abs(step - c) >= spacing for c in chosen):
            chosen.append(step)
    return sorted(chosen)


def _weighted(line: MainLine, rng: random.Random, pool: list[int], count: int, spacing: int = 2) -> list[int]:
    """Like `_pick`, but strong positions are likelier."""
    accent = line.meter.accent
    keyed = sorted(pool, key=lambda s: rng.random() ** (1 / (0.2 + accent((s * STEP) % line.meter.beats_per_bar))))
    chosen: list[int] = []
    for step in reversed(keyed):  # the largest keys are the likeliest
        if len(chosen) >= count:
            break
        if all(abs(step - c) >= spacing for c in chosen):
            chosen.append(step)
    return sorted(chosen)


def _bar_steps(line: MainLine, bar: int) -> range:
    spb = round(line.meter.beats_per_bar / STEP)
    return range(bar * spb, (bar + 1) * spb)


def _room(line: MainLine) -> list[tuple[float, float]]:
    """Where a counter note may start: the phrase rests and the held notes of a beat or more (after their onset)."""
    holds = [(n.start_time + STEP, n.end_time) for n in line.notes if n.duration >= REST - EPS]
    return sorted(line.phrase_rests() + holds)


def _fill_the_gaps(line: MainLine, rng: random.Random, density: float | None) -> list[Onset]:
    """Fills phrase rests and held notes. A main without either has no room: answered like passive_over_active."""
    d = 0.5 if density is None else density
    room = _room(line)
    if not room:
        return _passive_over_active(line, rng, density)
    onsets = []
    for bar in range(line.bars):
        free = {s: end for s in _bar_steps(line, bar) if s not in line.onset_steps
                for start, end in room if start - EPS <= s * STEP <= end - STEP + EPS}
        onsets += [Onset(s, free[s]) for s in _weighted(line, rng, list(free), round(1 + 5 * d))]
    return onsets


def _call_and_response(line: MainLine, rng: random.Random, density: float | None) -> list[Onset]:
    """Answers in the phrase rests, from their first 16th. A main without one is answered like fill_the_gaps."""
    d = 0.5 if density is None else density
    rests = line.phrase_rests()
    if not rests:
        return _fill_the_gaps(line, rng, density)
    onsets: list[Onset] = []
    for start, end in rests:
        first, last = math.ceil(start / STEP - EPS), math.floor(end / STEP + EPS)  # 16th steps of the rest
        if last - first < 2:
            continue
        steps = [first] + [s for s in range(first + 2, last - 1, 2) if rng.random() < 0.35 + 0.5 * d]
        onsets += [Onset(s, end) for s in steps]
    return onsets


def _passive_over_active(line: MainLine, rng: random.Random, density: float | None) -> list[Onset]:
    onsets = []
    for bar in range(line.bars):
        steps = _bar_steps(line, bar)
        busy = line.onsets_per_bar[bar]
        if busy >= 5:
            ratio = 0.34 + 0.16 * rng.random() if density is None else 0.2 + 0.4 * density
            count = max(1, round(busy * ratio))
        else:
            count = min(8, max(2, busy * 2 + 2) if density is None else round(2 + 6 * density))
        spb = len(steps)
        onsets += [Onset(steps[0] + round(i * spb / count)) for i in range(count)]
    return onsets


def _contrasting_rhythm(line: MainLine, rng: random.Random, density: float | None) -> list[Onset]:
    onsets = []
    for bar in range(line.bars):
        steps = list(_bar_steps(line, bar))
        theirs = {s for s in steps if s in line.onset_steps}
        if len(theirs) >= 8:
            count = 3 + (rng.random() < 0.5)  # sparse over dense
        else:
            count = min(8, max(len(theirs) + 2, 4))  # dense over sparse
        if density is not None:
            count = max(1, round(1 + 7 * density))
        free = [s for s in steps if s not in theirs]
        mine = _weighted(line, rng, free, count, spacing=1 if len(theirs) < 8 else 2)
        if len(mine) < count:  # no room outside the main's onsets: share a few
            shared = _weighted(line, rng, [s for s in steps if s in theirs and s not in mine], count - len(mine), spacing=2)
            mine = sorted(mine + [s for s in shared if all(abs(s - m) >= 2 for m in mine)])
        if set(mine) == theirs and mine:  # never the same pattern
            mine = mine[:-1]
        onsets += [Onset(s) for s in mine]
    return onsets


def _harmonic_notes(line: MainLine, rng: random.Random, density: float | None) -> list[Onset]:
    chance = 0.7 if density is None else density
    onsets: dict[int, Onset] = {}
    for n in line.notes:
        if rng.random() >= chance:
            continue
        step = round(n.start_time / STEP) + (2 if rng.random() < 0.4 else 0)
        if step < line.length / STEP:
            onsets.setdefault(step, Onset(step))
    return list(onsets.values())


def _note_layering(line: MainLine, rng: random.Random, density: float | None) -> list[Onset]:
    chance = 1.0 if density is None else density
    onsets: dict[int, Onset] = {}
    delayed = True  # the previous copy came late: this one may sound with the main
    for n in line.notes:
        if rng.random() >= chance:
            continue
        delay = 0 if delayed and rng.random() < 0.6 else rng.choice((2, 3))
        delayed = delay > 0
        step = round(n.start_time / STEP) + delay
        if step < line.length / STEP:
            onsets.setdefault(step, Onset(step, source=n))
    return list(onsets.values())


RHYTHMS = {
    "fill_the_gaps": _fill_the_gaps,
    "call_and_response": _call_and_response,
    "passive_over_active": _passive_over_active,
    "contrasting_rhythm": _contrasting_rhythm,
    "harmonic_notes": _harmonic_notes,
    "note_layering": _note_layering,
}


def _window(line: MainLine, register: str) -> tuple[int, int]:
    """Lowest and highest pitch of the counter line: a third clear of the main, within C2..C7."""
    if register == "above":
        low = min(line.high + 3, CEILING - MIN_ROOM)
        return low, min(low + WINDOW, CEILING)
    if register == "below":
        high = max(line.low - 3, FLOOR + MIN_ROOM)
        return max(high - WINDOW, FLOOR), high
    width = max(line.high - line.low, 7)
    return line.low, line.low + width


class _Voice:
    """Picks pitches for one counter line and remembers the last note for the parallel check."""

    def __init__(self, line: MainLine, harmony: Harmony, scale: Scale, mode: str, register: str, rng: random.Random):
        self.line, self.harmony, self.scale, self.mode, self.register, self.rng = line, harmony, scale, mode, register, rng
        self.low, self.high = _window(line, register)
        self.strong = line.strong_times()
        self.previous: Note | None = None

    def _checked_times(self, start: float, end: float) -> list[float]:
        times = [start] + [n.start_time for n in self.line.overlapping(start, end) if n.start_time > start + EPS]
        i = bisect_left(self.strong, start + EPS)
        while i < len(self.strong) and self.strong[i] < end - EPS:
            times.append(self.strong[i])
            i += 1
        return times

    def valid(self, pitch: int, start: float, end: float) -> bool:
        line, mode = self.line, self.mode
        for m in line.overlapping(start, end):
            if mode == "harmonic_notes" and pitch % 12 == m.pitch % 12:
                return False
            if (self.register == "above" and pitch <= m.pitch) or (self.register == "below" and pitch >= m.pitch):
                return False
        for t in self._checked_times(start, end):
            m = line.at(t)
            if m and line.meter.accent(t % line.meter.beats_per_bar) >= 0.8 and not consonant(pitch - m.pitch, mode == "note_layering"):
                return False
        return not self._parallel(pitch, start)

    def _parallel(self, pitch: int, start: float) -> bool:
        """Parallel fifths or octaves against the main since the previous counter note."""
        prev = self.previous
        if prev is None:
            return False
        before, now = self.line.at(prev.start_time), self.line.at(start)
        if not before or not now or before == now:
            return False
        a, b = abs(prev.pitch - before.pitch), abs(pitch - now.pitch)
        same_way = (pitch - prev.pitch) * (now.pitch - before.pitch) > 0
        return same_way and a % 12 == b % 12 and a % 12 in PARALLEL and a > 0 and b > 0

    def choose(self, start: float, end: float, source: Note | None) -> int | None:
        chord = self.harmony.at(start).chord
        strong = self.line.meter.accent(start % self.line.meter.beats_per_bar) >= 0.8
        pool = [p for p in range(self.low, self.high + 1) if self.scale.contains(p)]
        chord_tones = [p for p in pool if chord.contains(p)]
        if source is not None:  # a layer: the main's own pitch class, else a chord tone
            tiers = [[p for p in pool if p % 12 == source.pitch % 12], chord_tones]
        elif strong or self.mode == "harmonic_notes" or self.rng.random() < 0.6:
            tiers = [chord_tones, pool]
        else:
            tiers = [pool, chord_tones]
        target = self.previous.pitch if self.previous else (self.low + self.high) // 2
        for tier in tiers:
            ranked = sorted(tier, key=lambda p: abs(p - target) + self.rng.random() * 3)
            for pitch in ranked:
                if self.valid(pitch, start, end):
                    return pitch
        return None


def _note(meter: Meter, rng: random.Random, pitch: int, start: float, stop: float) -> Note:
    velocity = 62 + 28 * meter.accent(start % meter.beats_per_bar) + rng.uniform(-5, 5)
    return Note(pitch, start, max(STEP * 0.9, (stop - start) * 0.92), velocity, 1.0, velocity_deviation=8)


def _fit(voice: _Voice, start: float, stops: list[float], target: int) -> tuple[int, float] | None:
    """The scale pitch nearest `target` (chord tones first on a tie) that is valid for the longest of `stops`.

    A figure's pitch is fixed by its shape; where it clashes on a strong beat it moves to the nearest
    consonant tone instead, and when nothing within a fifth fits the note is shortened, then dropped.
    """
    chord = voice.harmony.at(start).chord
    pool = [p for p in range(voice.low, voice.high + 1) if voice.scale.contains(p) and abs(p - target) <= MAX_SHIFT]
    ranked = sorted(pool, key=lambda p: (abs(p - target), not chord.contains(p)))
    for stop in stops:
        for pitch in ranked:
            if voice.valid(pitch, start, stop):
                return pitch, stop
    return None


def _stair_base(voice: _Voice, top: int) -> int:
    """Absolute scale degree of the tonic the staircase starts on: one that keeps `top` steps above it in the window."""
    size = len(voice.scale)
    tonic = next(p for p in range(voice.low, voice.low + 12) if p % 12 == voice.scale.root % 12)
    base = voice.scale.degree_of(tonic) or 0
    if voice.scale.pitch_of_degree(base + top) > voice.high and tonic - 12 >= voice.low:
        base -= size
    return base


def _pulse_figure(voice: _Voice, grid: Grid, bar_pitches: list[int]) -> list[Note]:
    """The 3-3-3-3-3-1 pulse, one target pitch per bar."""
    line, meter = voice.line, voice.line.meter
    spb = grid.steps_per_bar
    steps = [s for s in PULSE if s < spb]
    notes: list[Note] = []
    for bar, target in enumerate(bar_pitches):
        times = [grid.position(bar, s) for s in steps] + [(bar + 1) * meter.beats_per_bar]
        for i, s in enumerate(steps):
            if voice.register == "same" and bar * spb + s in line.onset_steps:
                continue  # the same octave never starts with the main
            start, end = times[i], times[i + 1]
            stops = [end] + ([start + 2 * STEP] if end - start > 2 * STEP + EPS else [])
            fit = _fit(voice, start, stops, target)
            if fit:
                note = _note(meter, voice.rng, fit[0], start, fit[1])
                notes.append(note)
                voice.previous = note
    return notes


def _dotted_eighth_pulse(voice: _Voice, grid: Grid) -> list[Note]:
    pool = [p for p in range(voice.low, voice.high + 1) if voice.scale.contains(p)]
    pitches: list[int] = []
    for bar in range(voice.line.bars):
        chord = voice.harmony.at(bar * voice.line.meter.beats_per_bar).chord
        tones = [p for p in pool if chord.contains(p)] or pool
        target = pitches[-1] if pitches else (voice.low + voice.high) // 2
        pitches.append(min(tones, key=lambda p: abs(p - target) + voice.rng.random() * 3))
    return _pulse_figure(voice, grid, pitches)


def _scale_staircase(voice: _Voice, grid: Grid) -> list[Note]:
    """Up one scale step every one or two bars (the first three stairs), hold the top, one step back for bar 8."""
    top = 3
    base = _stair_base(voice, top)
    offsets: list[int] = []
    while len(offsets) < voice.line.bars:
        cycle = [k for k in range(top) for _ in range(voice.rng.choice((1, 2)))]
        cycle += [top] * (7 - len(cycle)) + [top - 1]
        offsets += cycle
    return _pulse_figure(voice, grid, [voice.scale.pitch_of_degree(base + o) for o in offsets[: voice.line.bars]])


def _trance_dotted_eighth_staircase(voice: _Voice, grid: Grid) -> list[Note]:
    """The Trance video's counter melody: degrees `described`, rhythm `roll`. Not seed-dependent."""
    base = _stair_base(voice, max(TRANCE_DEGREES))
    degrees = [TRANCE_DEGREES[bar % len(TRANCE_DEGREES)] for bar in range(voice.line.bars)]
    return _pulse_figure(voice, grid, [voice.scale.pitch_of_degree(base + d) for d in degrees])


def _echo_gap_answer(voice: _Voice, grid: Grid) -> list[Note]:
    """In each long main note: 3-4 short notes moving by a step, then a longer one that sustains under the re-entry."""
    line, meter, rng = voice.line, voice.line.meter, voice.rng
    spb = grid.steps_per_bar
    spans = sorted({(s, e) for s, e in line.held() if e - s >= MIN_ECHO_HOLD - EPS})
    pool = [p for p in range(voice.low, voice.high + 1) if voice.scale.contains(p)]
    plans = []
    for s, e in spans:
        first = round(s / STEP) + 1  # the main's onset is never shared
        count = min(rng.choice((3, 4)), int((e - s - 0.5) / STEP + EPS))
        if count >= 3 and first + count < line.length / STEP and first not in line.onset_steps:
            plans.append((first, count, e))
    notes: list[Note] = []
    for k, (first, count, end) in enumerate(plans):
        times = [grid.position((first + i) // spb, (first + i) % spb) for i in range(count + 1)]
        chord = voice.harmony.at(times[0]).chord
        tones = [p for p in pool if chord.contains(p)] or pool
        centre = (voice.low + voice.high) / 2
        target = min(tones, key=lambda p: abs(p - centre) + rng.random() * 4)
        direction = rng.choice((1, -1))
        for i in range(count):
            if not voice.low <= voice.scale.step(target, direction) <= voice.high:
                direction = -direction
            fit = _fit(voice, times[i], [times[i + 1]], target)
            if fit:
                note = _note(meter, rng, fit[0], times[i], fit[1])
                notes.append(note)
                voice.previous, target = note, fit[0]
            target = voice.scale.step(target, direction)
        cap = grid.position(plans[k + 1][0] // spb, plans[k + 1][0] % spb) if k + 1 < len(plans) else line.length
        start = times[count]
        chord = voice.harmony.at(start).chord
        final = min((p for p in pool if chord.contains(p)), key=lambda p: abs(p - target), default=target)
        stops = [s for s in (min(end + 1.0, cap), min(end, cap)) if s - start >= 2 * STEP]
        fit = _fit(voice, start, stops, final) if stops else None
        if fit:
            note = _note(meter, rng, fit[0], start, fit[1])
            notes.append(note)
            voice.previous = note
    return notes


FIGURE_BUILDERS = {
    "dotted_eighth_pulse": _dotted_eighth_pulse,
    "scale_staircase": _scale_staircase,
    "trance_dotted_eighth_staircase": _trance_dotted_eighth_staircase,
    "echo_gap_answer": _echo_gap_answer,
}


def resolve(main: list[Note], meter: Meter, bars: int, mode: str | None = None, register: str | None = None) -> tuple[str, str, str]:
    """The mode and register a counter melody uses, and why (empty when both were given)."""
    line = analyze(main, meter, bars)
    reasons = []
    if mode is None:
        rests = line.phrase_rests()
        share = sum(end - start for start, end in rests) / line.length
        per_bar = sum(line.onsets_per_bar) / line.bars
        if any(end - start >= 2 * REST - EPS for start, end in rests) and share >= 0.25:
            mode = "call_and_response"
            reasons.append(f"the lead rests {100 * share:.0f}% of the time: the counter answers in its rests")
        elif _room(line):
            mode = "fill_the_gaps"
            reasons.append("the lead leaves short rests and held notes: the counter fills them")
        else:
            mode = "passive_over_active"
            reasons.append(f"the lead plays without a rest (about {per_bar:.0f} notes a bar): a few long notes against it")
    if register is None:
        register = "above" if line.high + 3 + MIN_ROOM <= CEILING else "below"
        if register == "below":
            reasons.append("below the lead: above it would go past C7")
    return mode, register, "; ".join(reasons)


def generate_counter(
    main: list[Note],
    harmony: Harmony,
    scale: Scale,
    meter: Meter,
    bars: int,
    rng: random.Random,
    mode: str | None = None,
    register: str | None = None,
    density: float | None = None,
    swing: float = 0.0,
) -> list[Note]:
    mode, register, _ = resolve(main, meter, bars, mode, register)
    if mode not in MODES:
        raise ValueError(f"unknown counter melody mode {mode!r}; use one of {', '.join(MODES)}")
    if register not in REGISTERS:
        raise ValueError(f"unknown register {register!r}; use above, below or same")
    line = analyze(main, meter, bars)
    grid = Grid(meter, STEP, swing)
    spb = grid.steps_per_bar
    if mode in FIGURE_BUILDERS:
        return dedupe(FIGURE_BUILDERS[mode](_Voice(line, harmony, scale, mode, register, rng), grid))
    onsets = RHYTHMS[mode](line, rng, density)
    if register == "same":  # the same octave needs a different rhythm: never start with the main
        onsets = [o if o.step not in line.onset_steps else Onset(o.step + 1, o.end, o.source) for o in onsets]
        onsets = [o for o in onsets if o.step not in line.onset_steps]
    unique = {o.step: o for o in onsets if o.step < bars * spb}
    ordered = [unique[s] for s in sorted(unique)]
    times = [grid.position(o.step // spb, o.step % spb) for o in ordered]
    voice = _Voice(line, harmony, scale, mode, register, rng)
    cap = MAX_BEATS.get(mode, 2.0)
    notes: list[Note] = []
    for i, onset in enumerate(ordered):
        start = times[i]
        end = min(times[i + 1] if i + 1 < len(times) else line.length, start + cap, onset.end or line.length)
        returns = next((n.start_time for n in line.notes if n.start_time > start + EPS), None)
        ends = [end]
        if returns is not None and returns < end - EPS:
            fill = mode in ("fill_the_gaps", "call_and_response")
            ends = [returns] if fill and rng.random() < 0.5 else [end, returns]  # sustain under the re-entry, or stop
        ends += [start + 2 * STEP] if end - start > 2 * STEP + EPS else []
        for stop in ends:
            pitch = voice.choose(start, stop, onset.source)
            if pitch is not None:
                note = _note(meter, rng, pitch, start, stop)
                notes.append(note)
                voice.previous = note
                break
    return dedupe(notes)
