"""complexity="rich": what plan_song adds to a genre template so songs are layered, answer themselves and
differ from seed to seed. "simple" skips all of this and plays the template as it is.

- Sections (``enrich``): a seed varies the lengths of drops, breaks, grooves and verses, may split the
  last drop with a short second break, may add an 8-bar Mini Drop before the first build; later sections of a
  kind get notes of their own; every section but the last fills into the next; some drops breathe (kick and bass
  out for the last bar of a phrase); auto filter sweeps change their curve.
- Voices derived from the lead and the bass (they share rhythm and harmony, so they never clash with them):
  ``lead2`` doubles the lead an octave up or a third above and plays every second 16th of a dense lead,
  ``bass2`` is a mid layer an octave above the bass, ``answer`` plays a reply (the call's rhythm, inverted or
  repeated, ending on a chord tone) in the rests of the lead. Each has its own part spec per section, so
  layers come in later in the first drop and drop out before the end of a long one.
- Drums (``ghost_notes``, ``snare_roll``, ``humanize``): quiet ghost hits, a rising snare/clap roll into a drop,
  a little velocity and timing play on everything but the kick (the sidechain follows the kick).
- FX (``rich_fx``): short risers before other section borders, a noise sweep up and a reverse swell before
  every drop, a downlifter after it, a quieter impact where a drop ends.
"""

from __future__ import annotations

import random
import re
from dataclasses import replace
from typing import Any

from midibakery.compose.harmony import Harmony
from midibakery.compose.notes import Note
from midibakery.compose.structures import Section, _resize, parse_segments
from midibakery.compose.theory import Scale

EPSILON = 1e-6
DERIVED_FROM = {"answer": "lead", "lead2": "lead", "bass2": "bass"}
SILENT = ("-", "", "rumble", "sparse", "accent")  # parts that give a layer nothing to double
ANSWER_BEATS = 2.0  # the shortest rest the answer fills
FILTERS = {"answer": "Low-pass", "lead2": "Low-pass", "bass2": "Low-pass"}
LAYER_SWEEPS = {
    "lead2": ("400>7000~exp", "8000>1500~log", "1500>9000", "600>5000~sine/4"),
    "bass2": ("200>2500~sine/4", "150>1800~exp", "1200>300~log", "300>1500"),
    "answer": ("2000>9000~exp", "1200>6000~sine/4", "6000>2500~log"),
}


def _unique(name: str, sections: list[Section]) -> str:
    taken = {s.name for s in sections}
    return name if name not in taken else next(f"{name} {n}" for n in range(2, 99) if f"{name} {n}" not in taken)


def _quarter(bars: int) -> int:
    return max(4, bars // 2 // 4 * 4)


# --------------------------------------------------------------------------- sections


def enrich(sections: tuple[Section, ...], seed: int, structural: bool = True, skip: frozenset[str] = frozenset()) -> tuple[Section, ...]:
    """The template's (or the reference's) sections with the rich additions. ``structural`` False (a reference or a
    target duration sets the structure) leaves lengths and order alone; ``skip`` names derived roles to leave out."""
    r = random.Random(f"{seed}:rich")
    seen: dict[str, int] = {}
    varied = []
    for s in sections:  # a later section of a kind plays notes of its own
        n = seen.get(s.kind, 0)
        seen[s.kind] = n + 1
        varied.append(replace(s, variation=max(s.variation, n)) if s.kind in ("build", "drop", "break", "groove", "verse") else s)
    out = _extra(_jitter(varied, r), r) if structural else varied
    eligible = 0
    result = []
    for i, s in enumerate(out):
        s, layered = _decorate(s, last=i == len(out) - 1, first_drop=eligible == 0, r=r, skip=skip)
        eligible += layered
        result.append(s)
    return tuple(result)


def _jitter(sections: list[Section], r: random.Random) -> list[Section]:
    out = []
    for s in sections:
        delta = r.choice((-1, 0, 0, 1))
        if s.kind in ("drop", "break", "groove", "verse") and s.bars >= 16 and delta:
            s = _resize(s, s.bars + delta * (8 if s.bars >= 32 else 4))
        out.append(s)
    return out


def _extra(sections: list[Section], r: random.Random) -> list[Section]:
    """A Mini Drop after the intro, a short second break in the last drop; each by chance."""
    out = list(sections)
    kinds = [s.kind for s in out]
    mini, split = r.random() < 0.5, r.random() < 0.6
    drops = [i for i, s in enumerate(out) if s.kind == "drop" and s.bars >= 24]
    brk = next((s for s in out if s.kind == "break"), None)
    if split and brk is not None and drops:
        i = drops[-1]
        drop = out[i]
        first = _quarter(drop.bars)
        head = replace(_resize(drop, first), fill=True, pause_every=0)
        tail = replace(_resize(drop, drop.bars - first), name=_unique(f"{drop.name} Return", out), variation=drop.variation + 1, fill=drop.fill)
        pause = replace(_resize(brk, 8), name=_unique(f"{brk.name} 2", out), variation=brk.variation + 1, fill=True, rest_beats=0.0, pause_every=0)
        out[i:i + 1] = [head, pause, tail]
    first_drop = next((s for s in out if s.kind == "drop"), None)
    if mini and first_drop is not None and kinds[:2] == ["intro", "build"]:
        parts = dict(_resize(first_drop, 8).parts)
        if "lead" in parts:
            parts["lead"] = "tease"
        out.insert(1, replace(_resize(first_drop, 8), name=_unique("Mini Drop", out), energy=min(first_drop.energy, 0.8), fill=True,
                              variation=first_drop.variation + 2, rest_beats=0.0, pause_every=0, sweeps={}, parts=parts))
    return out


def _window(spec: str, bars: int, start: int, stop: int, silent: tuple[str, ...] = SILENT) -> str | None:
    """The part of a part spec inside bars [start, stop) as a spec of its own ("-:8,hook:16"); None if nothing plays there."""
    items: list[str] = []
    cursor = 0
    for name, offset, count in parse_segments(spec, bars):
        begin, end = max(offset, start), min(offset + count, stop)
        if name in silent or end <= begin:
            continue
        if begin > cursor:
            items.append(f"-:{begin - cursor}")
        items.append(f"{name}:{end - begin}")
        cursor = end
    return ",".join(items) or None


def _vary_sweeps(sweeps: dict[str, str], r: random.Random) -> dict[str, str]:
    """A plain "a>b" ramp takes another curve now and then: slow start, fast start, or the plain line."""
    out = {}
    for role, spec in sweeps.items():
        parts = []
        for item in spec.split(","):
            head, _, count = item.partition(":")
            if not role.endswith(".res") and re.fullmatch(r"\d+>\d+", head):
                head += r.choice(("", "", "~exp", "~log"))
            parts.append(head + (f":{count}" if count else ""))
        out[role] = ",".join(parts)
    return out


def _decorate(s: Section, last: bool, first_drop: bool, r: random.Random, skip: frozenset[str]) -> tuple[Section, bool]:
    """Part specs for the derived voices, fills, phrase breaths and sweep curves. Returns the section and whether
    it is a full drop (the first one lets the layers in late)."""
    parts, sweeps = dict(s.parts), _vary_sweeps(s.sweeps, r)
    big = s.kind == "drop" and s.energy >= 0.85
    fill = s.fill or (not last and parts.get("drums", "-") not in ("", "-"))
    pause = s.pause_every
    if big and not pause and s.bars >= 16 and r.random() < 0.35:
        pause = r.choice((8, 16))

    def enter() -> int:
        if s.bars < 16:
            return 0
        return r.choice((_quarter(s.bars), 8)) if first_drop else r.choice((0, 0, 8))

    def leave() -> int:
        return s.bars - 4 if s.bars >= 24 and r.random() < 0.3 else s.bars

    def add(role: str, base: str, chance: float, early: bool, silent: tuple[str, ...] = SILENT) -> None:
        spec = parts.get(base)
        if role in skip or not spec or r.random() >= chance:
            return
        window = _window(spec, s.bars, enter() if early else 0, leave(), silent)
        if window:
            parts[role] = window
            sweeps.setdefault(role, r.choice(LAYER_SWEEPS[role]))

    if big:
        add("lead2", "lead", 0.85, True, SILENT + ("tease",))
        add("bass2", "bass", 0.85, True)
        add("answer", "lead", 0.9, True)
    elif s.kind in ("break", "build"):
        add("answer", "lead", 0.6, False)
    return replace(s, parts=parts, sweeps=sweeps, fill=fill, pause_every=pause), big


# --------------------------------------------------------------------------- derived voices


def double_lead(notes: list[Note], scale: Scale, r: random.Random) -> list[Note]:
    """The lead's layer: an octave up or a third above, quieter; a dense lead (16ths) keeps only its 8ths."""
    mode = r.choice(("octave", "octave", "third"))
    out = []
    for n in notes:
        if n.duration < 0.3 and abs(n.start_time * 2 - round(n.start_time * 2)) > 0.01:
            continue
        pitch = scale.step(n.pitch, 2) if mode == "third" else n.pitch + 12
        if pitch > 108:
            pitch -= 12
        out.append(replace(n, pitch=pitch, velocity=max(1.0, n.velocity - 14)))
    return out


def mid_layer(notes: list[Note]) -> list[Note]:
    """The bass's mid layer: an octave up, shorter, the off-grid short notes left to the sub."""
    out = []
    for n in notes:
        if n.duration < 0.3 and abs(n.start_time * 2 - round(n.start_time * 2)) > 0.01:
            continue
        out.append(replace(n, pitch=n.pitch + 12, velocity=max(1.0, n.velocity - 14), duration=n.duration * 0.9))
    return out


def _chord_tone(harmony: Harmony, time: float, pitch: int, low: int, high: int) -> int:
    pcs = harmony.at(time).chord.pitch_classes
    options = [p for p in range(low, high + 1) if p % 12 in pcs]
    return min(options, key=lambda p: abs(p - pitch)) if options else pitch


def answer_notes(lead: list[Note], rests: list[tuple[float, float]], harmony: Harmony, scale: Scale, low: int, high: int) -> list[Note]:
    """A reply in each rest of the lead: the last notes before the rest, in the same rhythm, half a beat late, one octave
    away; every second reply upside down. The last note lands on a chord tone and holds."""
    shift = 12 if high < 66 else -12
    lo, hi = low + shift, high + shift
    out: list[Note] = []
    for index, (begin, end) in enumerate(rests):
        if end - begin < ANSWER_BEATS - EPSILON:
            continue
        source = sorted((n for n in lead if begin - 4.0 - EPSILON <= n.start_time < begin - EPSILON), key=lambda n: n.start_time)[-4:]
        if not source:
            continue
        origin, pivot = source[0].start_time, source[0].pitch + shift
        phrase: list[Note] = []
        for n in source:
            start = begin + 0.5 + n.start_time - origin
            if start >= end - 0.75:
                break
            pitch = n.pitch + shift
            if index % 2 == 1:
                pitch = scale.snap(2 * pivot - pitch)
            while pitch > hi:
                pitch -= 12
            while pitch < lo:
                pitch += 12
            phrase.append(Note(pitch, start, n.duration, max(1.0, n.velocity - 10)))
        if not phrase:
            continue
        last = phrase[-1]
        landing = _chord_tone(harmony, last.start_time, last.pitch, lo, hi)
        phrase[-1] = replace(last, pitch=landing, duration=min(3.0, end - 0.25 - last.start_time))
        out += phrase
    return out


# --------------------------------------------------------------------------- drums


def ghost_notes(notes: list[Note], bars: int, bpb: float, pitch: int, avoid: set[int], r: random.Random) -> list[Note]:
    """Quiet ghost hits on off 16ths where nothing hits: about every second bar one or two."""
    out = list(notes)
    for bar in range(bars):
        if r.random() >= 0.45:
            continue
        for offset in r.sample((0.75, 1.75, 2.25, 2.75, 3.25, 3.75), r.choice((1, 2))):
            t = bar * bpb + offset
            if any(abs(n.start_time - t) < 0.1 and n.pitch in avoid for n in out):
                continue
            out.append(Note(pitch, t, 0.15, r.uniform(28, 44)))
    return out


def snare_roll(notes: list[Note], bars: int, bpb: float, pitch: int) -> list[Note]:
    """The last two bars of a build: 8ths, then 16ths, getting louder; they replace the pitch's own hits there."""
    kept = [n for n in notes if not (n.pitch == pitch and n.start_time >= (bars - 2) * bpb - EPSILON)]
    hits: list[Note] = []
    for step in range(int(bpb * 2)):
        hits.append(Note(pitch, (bars - 2) * bpb + step * 0.5, 0.2, 40 + 30 * step / (bpb * 2)))
    for step in range(int(bpb * 4)):
        hits.append(Note(pitch, (bars - 1) * bpb + step * 0.25, 0.2, 62 + 58 * step / (bpb * 4)))
    return kept + hits


def humanize(notes: list[Note], r: random.Random, keep: set[int]) -> list[Note]:
    """A few percent of velocity and a few ms of timing off the grid, except for the pitches in `keep` (the kick)."""
    out = []
    for n in notes:
        if n.pitch in keep:
            out.append(n)
            continue
        start = n.start_time if n.start_time < 0.01 else max(0.0, n.start_time + r.uniform(-0.01, 0.02))
        out.append(replace(n, start_time=start, velocity=max(1.0, min(127.0, n.velocity * r.uniform(0.93, 1.07)))))
    return out


# --------------------------------------------------------------------------- FX


def rich_fx(actions: list[dict[str, Any]], counts: dict[str, int], roles: dict[str, Any], sections: tuple[Section, ...],
            starts: list[float], bpb: float, scale: Scale, riser_db: float, sweep_db: float, riser_macro: bool,
            plays: dict[str, dict[str, str]], r: random.Random) -> None:
    """More than one riser: short risers before borders that are no drop, on the sweep track a noise sweep and a reverse swell
    before every drop and a downlifter after it, an impact where a drop ends. Adds to `actions`, `counts` and `plays`."""
    def note(role: str, text: str, name: str) -> None:
        said = plays.setdefault(name, {})
        said[role] = f"{said[role]}; {text}" if role in said else text

    def sustained(role: str, at: float, length: float, name: str, shape: dict[str, Any], extra: list[dict[str, Any]] | None = None) -> None:
        envelopes = [{"parameter": "Volume", "unit": "display", "shapes": [{"length": length, **shape}]}, *(extra or [])]
        actions.append({"action": "add_clip", "track": roles[role].index, "start": at, "length": length, "name": name,
                        "notes": [Note(60 + scale.root, 0.0, length, 100).to_spec()], "envelopes": envelopes})
        counts[role] += 1

    riser, sweep, impact = roles.get("riser"), roles.get("sweep"), roles.get("impact")
    for i, (section, at) in enumerate(zip(sections, starts)):
        before = sections[i - 1] if i else None
        after = sections[i + 1] if i + 1 < len(sections) else None
        down = 0
        if sweep is not None and before is not None and before.kind == "drop" and section.kind != "drop" and section.bars >= 4 and r.random() < 0.8:
            down = min(4, section.bars // 2)
            sustained("sweep", at, down * bpb, f"{section.name} Downlifter", {"type": "exp", "from_value": sweep_db, "to_value": -40.0})
            note("sweep", f"downlifter, first {down} bars", section.name)
        if impact is not None and before is not None and before.kind == "drop" and section.kind != "drop" and r.random() < 0.6:
            actions.append({"action": "add_clip", "track": impact.index, "start": at, "length": 2 * bpb, "name": f"{section.name} Impact",
                            "notes": [Note(36 + scale.root, 0.0, bpb, 92).to_spec()]})
            counts["impact"] += 1
            note("impact", "first beat", section.name)
        if after is None or section.kind == "drop" and section.bars < 4:
            continue
        end = at + section.bars * bpb
        if after.kind == "drop" and section.kind != "drop":
            if sweep is not None:
                bars = min(r.choice((4, 8)), section.bars - down)
                length = bars * bpb - section.rest_beats - 2.0
                if length >= 2.0:
                    sustained("sweep", end - bars * bpb, length, f"{section.name} Sweep", {"type": "exp", "from_value": -35.0, "to_value": sweep_db})
                    sustained("sweep", end - section.rest_beats - 2.0, 2.0, f"{section.name} Swell", {"type": "exp", "from_value": -30.0, "to_value": sweep_db + 3})
                    note("sweep", f"noise sweep, last {bars} bars, swell on the last 2 beats", section.name)
        elif riser is not None and section.bars >= 4 and r.random() < 0.5:
            extra = [{"device": 0, "parameter": "Filter Cutoff", "shapes": [{"type": "exp", "length": 2 * bpb, "from_value": 0.3, "to_value": 1.0}]}] if riser_macro else None
            sustained("riser", end - 2 * bpb, 2 * bpb, f"{section.name} Short Riser", {"type": "exp", "from_value": -30.0, "to_value": riser_db - 3}, extra)
            note("riser", "short, last 2 bars", section.name)
