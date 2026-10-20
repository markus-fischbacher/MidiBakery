"""The sections of a Set (intro, build, drop, break, outro) from who plays when.

Per bar, each role is active when one of its tracks has a note sounding (MIDI) or a clip placed (audio).
A section ends where the set of active roles changes; short runs (fills, one-bar drop-outs) join their
neighbours, borders near a four-bar line snap to it, and locators, when the producer set them, override the
cuts and name the sections. The kind then follows from what plays: no kick is a break (or a build when a drop
follows), kick with bass and the most going on is a drop.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from midibakery.als.reader import Song
from midibakery.als.roles import PLAYING_ROLES

MIN_RUN = 2  # bars: shorter runs of a different line-up join their neighbours
SNAP = 4  # bars: a phrase
WEIGHTS = {"kick": 1.0, "drums": 1.0, "bass": 1.0, "chords": 1.0, "lead": 1.0, "fx": 0.5}
SECTION_ROLES = ("kick", "drums", "bass", "chords", "lead")  # what makes two bars the same line-up


@dataclass
class Activity:
    first_bar: int  # 1-based bar of the Set where anything first plays
    bars: int  # length from there to the last sounding bar
    grid: list[frozenset[str]]  # per bar: the active roles


def activity(song: Song, roles: dict[int, str]) -> Activity | None:
    bpb = song.beats_per_bar
    by_bar: dict[int, set[str]] = {}

    def mark(role: str, start: float, end: float) -> None:
        for bar in range(int(start // bpb), max(int(start // bpb), math.ceil(end / bpb - 1e-6) - 1) + 1):
            by_bar.setdefault(bar, set()).add(role)

    for track in song.tracks:
        role = roles.get(track.index)
        if role not in PLAYING_ROLES:
            continue
        for clip in track.clips:
            if clip.kind == "audio":
                mark(role, clip.start, clip.end)
            for note in clip.notes:
                mark(role, clip.start + note.time, clip.start + note.time + max(note.duration, 0.01))
    if not by_bar:
        return None
    first, last = min(by_bar), max(by_bar)
    return Activity(first + 1, last - first + 1, [frozenset(by_bar.get(b, ())) for b in range(first, last + 1)])


def _runs(lineups: list[frozenset[str]]) -> list[list[int]]:
    """[start, end) of each stretch of bars with the same line-up."""
    runs: list[list[int]] = []
    for i, lineup in enumerate(lineups):
        if runs and lineups[runs[-1][0]] == lineup:
            runs[-1][1] = i + 1
        else:
            runs.append([i, i + 1])
    return runs


def _merge_short(runs: list[list[int]]) -> list[list[int]]:
    """Runs shorter than MIN_RUN join the previous run (the first joins the next)."""
    changed = True
    while changed and len(runs) > 1:
        changed = False
        for i, (start, end) in enumerate(runs):
            if end - start < MIN_RUN:
                if i > 0:
                    runs[i - 1][1] = end
                    del runs[i]
                else:
                    runs[1][0] = start
                    del runs[0]
                changed = True
                break
    return runs


def _snap(borders: list[int], total: int) -> list[int]:
    snapped = []
    for border in borders:
        near = round(border / SNAP) * SNAP
        snapped.append(near if 0 < near < total and abs(near - border) <= 1 else border)
    return sorted(set(snapped))


def _cuts(act: Activity, song: Song) -> list[int]:
    """Bar indexes (0 = the first sounding bar) where a new section starts, after the first."""
    bpb = song.beats_per_bar
    located = sorted({int(round(loc.beat / bpb)) + 1 - act.first_bar for loc in song.locators} - {0})
    inside = [c for c in located if 0 < c < act.bars]
    if len(inside) >= 2:  # the producer marked the sections: trust that over the heuristics
        return inside
    lineups = [frozenset(r for r in lineup if r in SECTION_ROLES) for lineup in act.grid]
    runs = _merge_short(_runs(lineups))
    return _snap([start for start, _ in runs[1:]], act.bars)


def _label(stats: list[dict]) -> None:
    """Sets each section's kind: intro, build, drop, break, groove or outro."""
    top = max(s["energy"] for s in stats)
    for s in stats:
        if s["kick"] < 0.3:
            s["kind"] = "break"
        elif s["bass"] >= 0.5 and s["energy"] >= top * 0.8:
            s["kind"] = "drop"
        else:
            s["kind"] = "groove"
    for i, s in enumerate(stats):
        following = stats[i + 1] if i + 1 < len(stats) else None
        if following and following["kind"] == "drop" and s["kind"] != "drop" and i > 0:
            if s["fx"] > 0 or s["kind"] == "groove" or s["energy"] > top * 0.3:
                s["kind"] = "build"
    if len(stats) > 1:
        if stats[0]["kind"] != "drop" or stats[0]["bars"] <= 4:
            stats[0]["kind"] = "intro"
        last = stats[-1]
        if last["kind"] != "drop" or last["bars"] <= 4:
            last["kind"] = "outro"


HINTS = (("pre", "build"), ("build", "build"), ("riser", "build"), ("break", "break"), ("outro", "outro"),
         ("intro", "intro"), ("drop", "drop"), ("chorus", "drop"), ("verse", "groove"), ("groove", "groove"))


def _hint(name: str) -> str | None:
    """A producer's section name says what it is ("Pre Chorus" is a build, "Final break" a break)."""
    text = name.lower()
    return next((kind for word, kind in HINTS if word in text), None)


def _join(stats: list[dict]) -> list[dict]:
    """Neighbouring sections of the same kind are one: a drop only when the same parts play."""
    out: list[dict] = []
    for s in stats:
        prev = out[-1] if out else None
        if prev and prev["kind"] == s["kind"] and (s["kind"] != "drop" or prev["elements"] == s["elements"]):
            total = prev["bars"] + s["bars"]
            prev["energy"] = round((prev["energy"] * prev["bars"] + s["energy"] * s["bars"]) / total, 3)
            prev["kick"] = round((prev["kick"] * prev["bars"] + s["kick"] * s["bars"]) / total, 2)
            prev["bars"] = total
            prev["elements"] = [e for e in prev["elements"] if e in s["elements"]] if s["kind"] == "drop" else \
                [e for e in prev["elements"] + s["elements"] if e in prev["elements"] or e in s["elements"]]
            prev["elements"] = list(dict.fromkeys(prev["elements"]))
        else:
            out.append(s)
    return out


def _name(stats: list[dict], locator_names: dict[int, str]) -> None:
    seen: dict[str, int] = {}
    for s in stats:
        seen[s["kind"]] = seen.get(s["kind"], 0) + 1
        title = s["kind"].capitalize()
        s["name"] = locator_names.get(s["start_bar"]) or (title if seen[s["kind"]] == 1 else f"{title} {seen[s['kind']]}")


def sections(song: Song, roles: dict[int, str]) -> tuple[Activity | None, list[dict]]:
    act = activity(song, roles)
    if act is None:
        return None, []
    borders = [0, *_cuts(act, song), act.bars]
    stats: list[dict] = []
    for start, end in zip(borders, borders[1:]):
        part = act.grid[start:end]
        share = {r: sum(r in bar for bar in part) / len(part) for r in PLAYING_ROLES}
        energy = sum(WEIGHTS[r] * share[r] for r in PLAYING_ROLES) / sum(WEIGHTS.values())
        elements = [r for r in PLAYING_ROLES if share[r] >= 0.5]
        stats.append({"start_bar": start + 1, "bars": end - start, "energy": round(energy, 3),
                      "kick": round(share["kick"], 2), "bass": share["bass"], "fx": share["fx"], "elements": elements})
    _label(stats)
    bpb = song.beats_per_bar
    named = {int(round(loc.beat / bpb)) + 1 - act.first_bar + 1: loc.name for loc in song.locators if loc.name}
    for s in stats:
        hint = _hint(named.get(s["start_bar"], ""))
        if hint:
            s["kind"] = hint
    stats = _join(stats)
    _name(stats, named)
    for s in stats:
        del s["bass"], s["fx"]
    return act, stats
