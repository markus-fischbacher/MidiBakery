"""Drum pattern generator with Drum Rack pad detection by name.

Patterns are built per role (kick, snare, hats ...) and only mapped to MIDI
notes at the end, so the same groove plays on any Drum Rack: pads are found by
their names (``drum_rack.pads``), General MIDI notes are the fallback.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import Literal

from midishower.compose.notes import Note, dedupe
from midishower.compose.rhythm import Grid, Meter

DrumStyle = Literal["house", "techno", "hiphop", "trap", "rock", "breakbeat"]
STYLES: tuple[str, ...] = ("house", "techno", "hiphop", "trap", "rock", "breakbeat")

GM_NOTES = {
    "kick": 36,
    "rim": 37,
    "snare": 38,
    "clap": 39,
    "closed_hat": 42,
    "pedal_hat": 44,
    "low_tom": 45,
    "open_hat": 46,
    "mid_tom": 47,
    "crash": 49,
    "high_tom": 50,
    "ride": 51,
    "perc": 56,
    "shaker": 70,
}

# Checked in order; the first role whose pattern matches a pad name wins.
_ROLE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("open_hat", re.compile(r"open.?h|\bo\.?hh?\b|\boh\b|openhat")),
    ("pedal_hat", re.compile(r"pedal|\bphh?\b|foot.?h")),
    ("closed_hat", re.compile(r"hi.?hat|\bhh\b|\bchh?\b|closed|\bhat\b|hats")),
    ("kick", re.compile(r"kick|\bbd\b|bass.?drum|\bkik|\bkck")),
    ("clap", re.compile(r"clap|\bcp\b|\bclp")),
    ("rim", re.compile(r"\brim|\brs\b|side.?stick|stick")),
    ("snare", re.compile(r"snare|\bsd\b|\bsnr")),
    ("crash", re.compile(r"crash|cymbal|\bcym|splash|china")),
    ("ride", re.compile(r"ride|\brd\b|bell")),
    ("low_tom", re.compile(r"(low|floor|lo).?tom|tom.?(low|lo|floor|1\b)|\blt\b")),
    ("high_tom", re.compile(r"(high|hi).?tom|tom.?(high|hi|3\b)|\bht\b")),
    ("mid_tom", re.compile(r"tom|\bmt\b")),
    ("shaker", re.compile(r"shak|\bshk|tamb|maraca|cabasa")),
    ("perc", re.compile(r"perc|conga|bongo|cowbell|clave|block|tabla|\bfx\b|zap|click")),
]

# When a kit has no pad for a role, borrow a related one before giving up.
_SUBSTITUTES = {
    "clap": ("snare", "rim"),
    "snare": ("clap", "rim"),
    "rim": ("snare", "clap", "perc"),
    "open_hat": ("closed_hat", "ride", "shaker"),
    "closed_hat": ("pedal_hat", "shaker", "ride"),
    "pedal_hat": ("closed_hat",),
    "ride": ("closed_hat", "crash"),
    "crash": ("ride", "open_hat"),
    "low_tom": ("mid_tom", "high_tom", "perc"),
    "mid_tom": ("low_tom", "high_tom", "perc"),
    "high_tom": ("mid_tom", "low_tom", "perc"),
    "shaker": ("closed_hat", "perc"),
    "perc": ("rim", "shaker", "high_tom"),
    "kick": (),
}


def classify_pad(name: str) -> str | None:
    text = name.lower().replace("_", " ")
    for role, pattern in _ROLE_PATTERNS:
        if pattern.search(text):
            return role
    return None


@dataclass(frozen=True)
class DrumMap:
    notes: dict[str, int]
    detected: tuple[str, ...]  # roles found on real pads
    source: str  # "drum_rack" or "gm"

    def note(self, role: str) -> int | None:
        return self.notes.get(role)


def map_pads(pads: list[dict] | None) -> DrumMap:
    """Role -> MIDI note from Drum Rack pads (``[{"note", "name"}]``), GM fallback."""
    if not pads:
        return DrumMap(dict(GM_NOTES), (), "gm")
    found: dict[str, int] = {}
    for pad in sorted(pads, key=lambda p: p["note"]):
        role = classify_pad(pad.get("name", ""))
        if role and role not in found:
            found[role] = int(pad["note"])
    notes: dict[str, int] = {}
    for role in GM_NOTES:
        if role in found:
            notes[role] = found[role]
            continue
        for substitute in _SUBSTITUTES.get(role, ()):
            if substitute in found:
                notes[role] = found[substitute]
                break
    if "kick" not in notes:
        # Kits with unnamed pads: the lowest pad is the kick by convention.
        notes["kick"] = min(int(p["note"]) for p in pads)
    return DrumMap(notes, tuple(sorted(found)), "drum_rack")


@dataclass(frozen=True)
class Hit:
    role: str
    time: float
    velocity: float
    probability: float = 1.0
    velocity_deviation: float = 0.0
    duration: float = 0.25


def _bar_hits(style: str, meter: Meter, grid: Grid, bar: int, rng: random.Random, density: float, core: dict) -> list[Hit]:
    """One bar of hits, `bar` relative to the clip. `core` holds per-clip choices shared by all bars."""
    bpb = meter.beats_per_bar
    t0 = bar * bpb
    pulses = meter.pulses
    offbeats = meter.offbeats()
    backbeats = meter.backbeats
    steps = grid.steps_per_bar
    hits: list[Hit] = []

    def at(step: int) -> float:
        return grid.position(bar, step)

    def step_of(offset: float) -> int:
        return round(offset / grid.step)

    if style in ("house", "techno"):
        for p in pulses:
            hits.append(Hit("kick", t0 + p, 120 if p == 0 else 112))
        for b in backbeats:
            hits.append(Hit("clap" if style == "house" else "snare", t0 + b, 105 if style == "house" else 95))
        for o in offbeats:
            hits.append(Hit("open_hat", at(step_of(o)), 92, velocity_deviation=10, duration=0.25))
        taken = {step_of(p) for p in pulses} | {step_of(o) for o in offbeats}
        for s in range(steps):
            if s in taken:
                continue
            if style == "techno" or rng.random() < 0.35 + 0.6 * density:
                prob = 1.0 if style == "techno" else round(0.55 + 0.4 * density, 2)
                hits.append(Hit("closed_hat", at(s), 70 if s % 2 else 82, prob, 18))
        if style == "techno":
            for s in core["rim_steps"]:
                hits.append(Hit("rim", at(s), 80, 0.7, 15))
    elif style == "hiphop":
        hits.append(Hit("kick", t0, 118))
        for s in core["kick_steps"]:
            hits.append(Hit("kick", at(s), 100))
        for b in backbeats:
            hits.append(Hit("snare", t0 + b, 112))
        for s in range(0, steps, 2):
            hits.append(Hit("closed_hat", at(s), 88 if s % 4 == 0 else 72, velocity_deviation=12))
        for s in core["ghost_steps"]:
            hits.append(Hit("snare", at(s), 42, round(0.35 + 0.5 * density, 2), 10))
    elif style == "trap":
        hits.append(Hit("kick", t0, 120, duration=0.5))
        for s in core["kick_steps"]:
            hits.append(Hit("kick", at(s), 105, duration=0.5))
        half = bpb / 2
        hits.append(Hit("clap", t0 + half, 110))
        hits.append(Hit("snare", t0 + half, 100))
        for s in range(steps):
            if s % 2 and rng.random() > 0.4 + 0.6 * density:
                continue
            roll = rng.random() < 0.12 * (1 + density) and s < steps - 1
            if roll:
                # 1/32 or 1/16-triplet ratchet.
                parts = rng.choice((2, 3))
                for k in range(parts):
                    hits.append(Hit("closed_hat", at(s) + k * grid.step / parts, 70 + 10 * k, duration=grid.step / parts))
            else:
                hits.append(Hit("closed_hat", at(s), 85 if s % 2 == 0 else 65, velocity_deviation=15))
        if core["open_step"] is not None:
            hits.append(Hit("open_hat", at(core["open_step"]), 85, 0.8))
    elif style == "rock":
        hits.append(Hit("kick", t0, 118))
        if len(pulses) > 2:
            hits.append(Hit("kick", t0 + pulses[2], 110))
        for s in core["kick_steps"]:
            hits.append(Hit("kick", at(s), 95, round(0.5 + 0.5 * density, 2)))
        for b in backbeats:
            hits.append(Hit("snare", t0 + b, 115))
        hat = "ride" if core["ride"] else "closed_hat"
        for s in range(0, steps, 2):
            hits.append(Hit(hat, at(s), 90 if s % 4 == 0 else 75, velocity_deviation=10))
    elif style == "breakbeat":
        hits.append(Hit("kick", t0, 120))
        hits.append(Hit("kick", at(min(steps - 1, step_of(bpb * 0.625))), 108))
        for b in backbeats:
            hits.append(Hit("snare", t0 + b, 115))
        for s in core["ghost_steps"]:
            hits.append(Hit("snare", at(s), 45, round(0.4 + 0.5 * density, 2), 12))
        for s in range(0, steps, 2):
            hits.append(Hit("closed_hat", at(s), 85 if s % 4 == 0 else 68, velocity_deviation=12))
    else:
        raise ValueError(f"unknown drum style {style!r}")
    return hits


def _core_choices(style: str, grid: Grid, rng: random.Random, density: float) -> dict:
    """Pattern decisions made once per clip, so every bar grooves the same way."""
    steps = grid.steps_per_bar
    odd = [s for s in range(steps) if s % 4 in (2, 3) and s > 0]
    weak = [s for s in range(1, steps) if s % 2 == 1]
    count = 1 + round(2 * density)
    return {
        "kick_steps": sorted(rng.sample(odd, min(len(odd), count))) if odd else [],
        "ghost_steps": sorted(rng.sample(weak, min(len(weak), 1 + round(2 * density)))) if weak else [],
        "rim_steps": sorted(rng.sample(weak, min(len(weak), 2))) if weak else [],
        "open_step": rng.choice(weak) if weak and rng.random() < 0.6 else None,
        "ride": rng.random() < 0.25,
    }


def _fill(meter: Meter, grid: Grid, bar: int, rng: random.Random) -> list[Hit]:
    """Snare/tom run over the bar's last pulse, leading into the next phrase."""
    last = meter.pulses[-1]
    start_step = round(last / grid.step)
    roles = rng.choice((("snare",), ("high_tom", "mid_tom", "low_tom"), ("snare", "high_tom", "low_tom")))
    hits = []
    for i, s in enumerate(range(start_step, grid.steps_per_bar)):
        role = roles[min(len(roles) - 1, i * len(roles) // max(1, grid.steps_per_bar - start_step))]
        hits.append(Hit(role, grid.position(bar, s), 70 + 12 * i))
    return hits


def generate_drums(
    meter: Meter,
    bars: int,
    style: str,
    rng: random.Random,
    drum_map: DrumMap,
    density: float = 0.5,
    swing: float = 0.0,
    swing_unit: float = 0.25,
    fills: bool = True,
    chance: float = 1.0,
) -> list[Note]:
    """`chance` works like Live's note Chance for the hits that may drop out (ghost notes,
    some hats, extra kicks): 1 = every hit always plays, 0.5 = the style's own
    probabilities, 0 = twice the variation."""
    grid = Grid(meter, 0.25, swing, swing_unit)
    core = _core_choices(style, grid, rng, density)
    hits: list[Hit] = []
    for bar in range(bars):
        bar_hits = _bar_hits(style, meter, grid, bar, rng, density, core)
        phrase_end = fills and bars >= 2 and (bar % 4 == 3 or bar == bars - 1) and bar > 0
        if phrase_end and rng.random() < 0.4 + 0.5 * density:
            cut = bar * meter.beats_per_bar + meter.pulses[-1] - 1e-9
            # The fill replaces snares and hats in its range; kicks stay.
            bar_hits = [h for h in bar_hits if h.time < cut or h.role == "kick"] + _fill(meter, grid, bar, rng)
        if bar % 4 == 0 and bar > 0 and style in ("rock", "breakbeat") and rng.random() < 0.6:
            bar_hits.append(Hit("crash", bar * meter.beats_per_bar, 105, duration=1.0))
        hits.extend(bar_hits)

    notes = []
    for hit in hits:
        pitch = drum_map.note(hit.role)
        if pitch is None:
            continue
        notes.append(Note(pitch, hit.time, hit.duration, hit.velocity, scale_chance(hit.probability, 1.0 - chance), hit.velocity_deviation))
    return dedupe(notes)


def scale_chance(probability: float, variation: float) -> float:
    """Scale a style probability: variation 0 = always plays, 0.5 = unchanged, 1 = twice as
    likely to drop out. Hits at 1.0 always stay at 1.0."""
    if probability >= 1.0:
        return 1.0
    return round(max(0.05, min(1.0, 1.0 - (1.0 - probability) * 2.0 * variation)), 2)


def kick_times(notes: list[dict], kick_pitch: int) -> list[float]:
    """Onsets of the kick in an existing drum clip (``notes.get`` notes)."""
    return sorted({round(n["start_time"], 4) for n in notes if n["pitch"] == kick_pitch and not n.get("mute")})
