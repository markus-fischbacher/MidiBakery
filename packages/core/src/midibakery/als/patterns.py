"""Loops of a Set as MidiBakery patterns: the drum, bass, lead and chord figures that repeat.

A track's notes are cut into bars on the 16th grid; the longest repeating 1, 2 or 4 bar figure that covers the most
bars is a pattern. Bass is stored as intervals above its own root (so it follows the chords when composed), a lead as
scale degrees of the Set's key, drums as hits per role (pad names decide the role), chords as a progression of
roman numerals in the Set's key (the voicing and rhythm are not kept). Only 4/4 Sets, and a figure must
repeat: a part that never repeats is not a loop. What it came from (Set, track, bars) goes in the description.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from midibakery.als.reader import Song, Track
from midibakery.compose import user_patterns
from midibakery.compose.drums import classify_pad
from midibakery.compose.harmony import CLIP_SHAPES, _clip_chord
from midibakery.compose.theory import NOTE_NAMES, Scale

PER_FAMILY = 2
SIZES = (1, 2, 4)
OFF_SCALE = 0.2  # a lead with more notes than this outside its key is not turned into degrees
MAJOR, MINOR = (0, 2, 4, 5, 7, 9, 11), (0, 2, 3, 5, 7, 8, 10)

# (step 1-16, length in beats, pitch, velocity)
RawNote = tuple[int, float, int, int]


def _bars(notes: list[tuple[float, float, int, float]], beats_per_bar: float) -> dict[int, list[RawNote]]:
    out: dict[int, list[RawNote]] = {}
    for time, duration, pitch, velocity in notes:
        bar, within = divmod(time, beats_per_bar)
        step = round(within * 4) + 1
        if step > 16:  # rounds up into the next bar's downbeat
            bar, step = bar + 1, 1
        out.setdefault(int(bar), []).append((step, round(max(duration, 0.1), 2), pitch, int(round(velocity))))
    for bar in out.values():
        bar.sort()
    return out


def _track_notes(track: Track) -> list[tuple[float, float, int, float]]:
    return [(c.start + n.time, n.duration, n.pitch, n.velocity) for c in track.clips for n in c.notes]


def _signature(bar: list[RawNote] | None, with_pitch: bool) -> tuple:
    return tuple((s, p) if with_pitch else (s,) for s, _, p, _ in (bar or ()))


def figures(by_bar: dict[int, list[RawNote]], with_pitch: bool = True) -> list[tuple[int, list[int], int, list[int]]]:
    """(window size, the bars of its first occurrence, how often it repeats, the first bar of each occurrence), best first.

    Windows are aligned to the first sounding bar. A window that is a shorter figure played twice is not also listed as the longer one.
    """
    if not by_bar:
        return []
    first, last = min(by_bar), max(by_bar)
    found: dict[tuple, tuple[int, list[int], int, list[int]]] = {}
    for size in SIZES:
        counts: Counter = Counter()
        origin: dict[tuple, list[int]] = {}
        for start in range(first, last + 1, size):
            window = [_signature(by_bar.get(b), with_pitch) for b in range(start, start + size)]
            if sum(1 for w in window if w) * 2 < size or not any(window):
                continue
            if size > 1 and window[: size // 2] == window[size // 2:]:  # a shorter figure repeated: listed as that one
                continue
            key = tuple(window)
            counts[key] += 1
            origin.setdefault(key, []).append(start)
        for key, count in counts.items():
            if count >= 2:
                found[key] = (size, list(range(origin[key][0], origin[key][0] + size)), count, origin[key])
    return sorted(found.values(), key=lambda f: (-f[0] * f[2], f[0]))


def _pick(by_bar: dict[int, list[RawNote]], with_pitch: bool = True) -> list[tuple[list[int], int, list[int]]]:
    """The best figures (their bars, repeat count and occurrences), without two that are the same notes."""
    chosen: list[tuple[list[int], int, list[int]]] = []
    seen: set[tuple] = set()
    seen_bars: set[tuple] = set()
    for size, bars, count, starts in figures(by_bar, with_pitch):
        key = tuple(_signature(by_bar.get(b), True) for b in bars)
        if key in seen or all(bar in seen_bars for bar in key) and chosen:  # the same, or a piece of a longer one
            continue
        seen.add(key)
        seen_bars.update(key)
        chosen.append((bars, count, starts))
    return chosen


def _drum_roles(track: Track) -> dict[int, str]:
    pads = {p.note: classify_pad(p.name) for d in track.devices if d.kind == "Drum Rack" for p in d.pads}
    return {note: role for note, role in pads.items() if role}


def drums(song: Song, roles: dict[int, str]) -> list[dict[str, Any]]:
    hits: list[tuple[float, float, str, float]] = []
    for track in song.tracks:
        if roles.get(track.index) not in ("kick", "drums"):
            continue
        by_note = _drum_roles(track)
        single = classify_pad(track.name) or ("kick" if roles[track.index] == "kick" else None)
        for time, duration, pitch, velocity in _track_notes(track):
            role = by_note.get(pitch) or (single if not by_note else None)
            if role:
                hits.append((time, duration, role, velocity))
    by_bar: dict[int, list[RawNote]] = {}
    names: dict[int, str] = {}
    roles_seen = {r: i for i, r in enumerate(sorted({h[2] for h in hits}))}
    for time, duration, role, velocity in hits:
        names[roles_seen[role]] = role
    for bar, notes in _bars([(t, d, roles_seen[r], v) for t, d, r, v in hits], song.beats_per_bar).items():
        by_bar[bar] = notes  # the "pitch" slot carries the role index
    out = []
    for bars, count, starts in _pick(by_bar)[:PER_FAMILY]:
        out.append({"kind": "drums", "bars": [[{"role": names[p], "step": s, "velocity": v, "length": min(l, 0.5)}
                                               for s, l, p, v in by_bar.get(b, [])] for b in bars],
                    "bar_numbers": bars, "repeats": count, "occurrences": starts, "track": "drums"})
    return out


def _root(notes: list[RawNote]) -> int:
    """The pitch class a bass figure is built on: its most played one, the lower on a tie."""
    counts = Counter(p % 12 for _, _, p, _ in notes)
    top = max(counts.values())
    lowest = {pc: min(p for _, _, p, _ in notes if p % 12 == pc) for pc in counts if counts[pc] == top}
    return min(lowest, key=lambda pc: lowest[pc])


def bass(song: Song, roles: dict[int, str]) -> list[dict[str, Any]]:
    found = []
    for track in song.tracks:
        if roles.get(track.index) != "bass":
            continue
        by_bar = _bars(_track_notes(track), song.beats_per_bar)
        for bars, count, starts in _pick(by_bar):
            window = [n for b in bars for n in by_bar.get(b, [])]
            root = _root(window)
            low = min(p for _, _, p, _ in window)
            base = low - (low - root) % 12
            found.append({"kind": "bass", "bars": [[{"step": s, "length": l, "interval": p - base, "velocity": v}
                                                    for s, l, p, v in by_bar.get(b, [])] for b in bars],
                          "low": base, "bar_numbers": bars, "repeats": count, "occurrences": starts, "track": track.name, "_score": len(bars) * count})
    return _top(found)


def lead(song: Song, roles: dict[int, str], key: str) -> list[dict[str, Any]]:
    parts = key.rstrip("?").split()
    if len(parts) != 2 or parts[0] not in NOTE_NAMES or parts[1] not in ("major", "minor"):
        return []
    root, intervals = NOTE_NAMES.index(parts[0]), MAJOR if parts[1] == "major" else MINOR
    found = []
    for track in song.tracks:
        if roles.get(track.index) != "lead":
            continue
        by_bar = _bars(_track_notes(track), song.beats_per_bar)
        for bars, count, starts in _pick(by_bar):
            window = [n for b in bars for n in by_bar.get(b, [])]
            degrees = {}
            for _, _, p, _ in window:
                octaves, pc = divmod(p - 60 - root, 12)
                degrees[p] = octaves * 7 + intervals.index(pc) if pc in intervals else None
            if sum(1 for _, _, p, _ in window if degrees[p] is None) > OFF_SCALE * len(window):
                continue
            found.append({"kind": "lead", "scale": parts[1], "bar_numbers": bars, "repeats": count, "occurrences": starts, "track": track.name,
                          "bars": [[{"step": s, "length": l, "degree": degrees[p], "velocity": v}
                                    for s, l, p, v in by_bar.get(b, []) if degrees[p] is not None] for b in bars],
                          "_score": len(bars) * count})
    return _top(found)


# A chord's root as an offset above the key's tonic, written like parse_chord reads it (accidentals against the major scale).
NUMERALS = ("I", "bII", "II", "bIII", "III", "IV", "bV", "V", "bVI", "VI", "bVII", "VII")
SUFFIXES = {(0, 4, 7): "", (0, 3, 7): "", (0, 3, 6): "°", (0, 4, 8): "+", (0, 4, 7, 10): "7", (0, 3, 7, 10): "7", (0, 4, 7, 11): "maj7"}
OFF_CHORDS = 0.25  # a progression with this share of chord roots outside its key is dropped
CHORD_BARS_MIN = 0.75  # share of a figure's bars with a clear chord


def roman(root: int, shape: tuple[int, ...], tonic: int) -> str:
    numeral = NUMERALS[(root - tonic) % 12]
    return (numeral.lower() if shape[1] == 3 else numeral) + SUFFIXES[shape]


def _bar_chords(notes: list[RawNote], scale: Scale) -> list[Any]:
    """The chord of the whole bar, then of each half of it (None where no clear chord sounds)."""
    out = []
    for first, last in ((0.0, 4.0), (0.0, 2.0), (2.0, 4.0)):
        weights: dict[int, float] = {}
        low = None
        for step, length, pitch, _ in notes:
            start, end = (step - 1) / 4, (step - 1) / 4 + length
            overlap = min(end, last) - max(start, first)
            if overlap > 0:
                weights[pitch % 12] = weights.get(pitch % 12, 0.0) + overlap
                low = pitch if low is None or pitch < low else low
        out.append(_clip_chord(weights, scale, None if low is None else low % 12))
    return out


def _own_key(codes: list[int], preferred: tuple[int, str] | None) -> tuple[int, str] | None:
    """The key a chord loop is written in: the Set's own key when the chords fit it, else the key they fit best.

    The Set's detected key can be wrong for a chord part (extended pad chords), so the loop is not dropped for that:
    among the 24 keys that hold at least 3/4 of the chord roots, the one with most chords on its tonic wins (then the one the loop starts on).
    """
    roots = [code // 16 for code in codes]
    shapes = [CLIP_SHAPES[code % 16] for code in codes]

    def fits(tonic: int, mode: str) -> bool:
        scale = Scale(tonic, MAJOR if mode == "major" else MINOR, "")
        return sum(1 for r in roots if scale.degree_of(r + 120) is None) < OFF_CHORDS * len(roots)

    if preferred is not None and fits(*preferred):
        return preferred
    options = [(t, m) for t in range(12) for m in ("minor", "major") if fits(t, m)]
    if not options:
        return None
    on_tonic = lambda o: sum(1 for r, sh in zip(roots, shapes) if r == o[0] and (sh[1] == 3) == (o[1] == "minor"))  # noqa: E731
    first = lambda o: roots[0] == o[0] and (shapes[0][1] == 3) == (o[1] == "minor")  # noqa: E731
    return max(options, key=lambda o: (on_tonic(o), first(o)))


def chords(song: Song, roles: dict[int, str], key: str) -> list[dict[str, Any]]:
    """The chord progression a chord track loops: roman numerals of its key, one or two chords per bar."""
    parts = key.rstrip("?").split()
    preferred = (NOTE_NAMES.index(parts[0]), parts[1]) if len(parts) == 2 and parts[0] in NOTE_NAMES and parts[1] in ("major", "minor") else None
    scale = Scale(preferred[0] if preferred else 0, MAJOR if preferred and preferred[1] == "major" else MINOR, "")
    found = []
    for track in song.tracks:
        if roles.get(track.index) != "chords":
            continue
        by_bar = _bars(_track_notes(track), song.beats_per_bar)
        halves = {bar: _bar_chords(notes, scale) for bar, notes in by_bar.items()}
        both = [h for h in halves.values() if h[1] is not None and h[2] is not None]
        twice = sum(1 for h in both if (h[1].root, h[1].intervals) != (h[2].root, h[2].intervals)) * 2 > len(halves)  # most bars change mid-bar
        halves = {bar: ([h[1], h[2]] if twice else [h[0]]) for bar, h in halves.items()}
        # a chord is a (root, shape) number so the figure finder can compare bars
        coded: dict[int, list[RawNote]] = {}
        for bar, pair in halves.items():
            seen = [(i, c) for i, c in enumerate(pair) if c is not None]
            if seen:
                coded[bar] = [(1 + 8 * i, 1.0, c.root * 16 + CLIP_SHAPES.index(tuple(c.intervals)), 100) for i, c in seen
                              if tuple(c.intervals) in CLIP_SHAPES]
        for bars, count, starts in _pick(coded):
            filled = [b for b in bars if len(coded.get(b, ())) == (2 if twice else 1)]
            if len(filled) < CHORD_BARS_MIN * len(bars):
                continue
            codes = [code for b in bars for _, _, code, _ in coded.get(b, [])]
            if len(set(codes)) < 2:  # one chord held is no progression
                continue
            own = _own_key(codes, preferred)
            if own is None:  # chords that fit no key: a misread, not a progression
                continue
            tonic, mode = own
            symbols = [roman(code // 16, CLIP_SHAPES[code % 16], tonic) for code in codes]
            found.append({"kind": "chords", "progression": " ".join(symbols), "chords_per_bar": 2.0 if twice else 1.0, "scale": mode,
                          "bars": [[] for _ in bars], "bar_numbers": bars, "repeats": count, "occurrences": starts, "track": track.name,
                          "_score": len(bars) * count})
    return _top(found)


def _top(found: list[dict[str, Any]]) -> list[dict[str, Any]]:
    found.sort(key=lambda f: -f["_score"])
    out, seen = [], set()
    for item in found:
        key = repr((item["bars"], item.get("progression")))
        if key in seen:
            continue
        seen.add(key)
        out.append({k: v for k, v in item.items() if k != "_score"})
    return out[:PER_FAMILY]


def extract(song: Song, roles: dict[int, str], key: str, set_id: str) -> list[dict[str, Any]]:
    """The patterns of a Set, named my_<set>_<family>_<n>, ready for user_patterns.save."""
    if abs(song.beats_per_bar - 4) > 1e-6:
        return []
    base = user_patterns.PREFIX + user_patterns.slug(song.name)
    out = []
    bpm = [max(60, round(song.tempo) - 8), round(song.tempo) + 8]
    for family, items in (("bass", bass(song, roles)), ("lead", lead(song, roles, key)), ("drums", drums(song, roles)), ("chords", chords(song, roles, key))):
        for number, item in enumerate(items, 1):
            span = f"bars {item['bar_numbers'][0] + 1}-{item['bar_numbers'][-1] + 1}"
            out.append({**item, "name": f"{base}_{family}_{number}",
                        "label": f"{song.name}: {family} {number}", "bpm": bpm,
                        "description": f"{len(item['bars'])}-bar {family} loop from the track \"{item['track']}\" of {song.name} "
                                       f"({span}, repeats {item['repeats']}x, {round(song.tempo)} BPM, {key})"})
    return out
