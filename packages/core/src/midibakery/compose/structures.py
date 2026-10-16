"""Song structures per genre: sections with length, energy and what each role plays.

Templates are data. A section names its kind (intro, build, drop, ...) and for
every role a part: drums "full" / "no_kick" / "kick_hats" / "sparse", the other
roles "on", "sparse" or absent (silent). Energy (0-1) drives density and
velocity. Sections of the same kind share their notes, which keeps a song
together; `variation` gives a later section of that kind its own notes.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Literal

Role = Literal["drums", "bass", "chords", "lead"]
ROLES: tuple[Role, ...] = ("drums", "bass", "chords", "lead")
Genre = Literal["house", "techno", "drum_and_bass", "trap"]
Length = Literal["radio", "standard", "extended"]


@dataclass(frozen=True)
class Section:
    name: str
    kind: str
    bars: int
    energy: float
    parts: dict[str, str] = field(default_factory=dict)  # role -> part; a missing role is silent
    fill: bool = False  # drum fill into the next section
    variation: int = 0  # >0: own notes instead of sharing them with the earlier section of this kind
    rest_beats: float = 0.0  # silence at the end, e.g. the beat before a drop


EDM_PROGRESSIONS = {
    "major": ((5, 3, 0, 4), (0, 4, 5, 3), (0, 5, 3, 4), (1, 4, 0, 5)),  # vi IV I V, I V vi IV, I vi IV V, ii V I vi
    "minor": ((0, 5, 2, 6), (0, 3, 5, 4), (0, 6, 5, 6), (0, 5, 3, 4)),  # i VI III VII, i iv VI v, i VII VI VII, i VI iv v
}
SPARSE_PROGRESSIONS = {"major": ((5, 4), (0, 3), (5, 3)), "minor": ((0, 6), (0, 5), (0, 3))}


@dataclass(frozen=True)
class Style:
    """How a genre plays its roles; values are the existing generators' styles."""

    tempo: float
    drums: str
    bass: str
    chord_rhythm: str
    break_chords: str = "sustain"
    swing: float = 0.0
    bass_octave: int = 1
    chords_per_bar: float = 1.0
    lead_range: tuple[int, int] = (64, 86)
    # Scale degrees (0 = tonic) of typical loops, diatonic in the song's scale; by its third.
    progressions: dict[str, tuple[tuple[int, ...], ...]] = field(default_factory=lambda: dict(EDM_PROGRESSIONS))


@dataclass(frozen=True)
class Template:
    genre: str
    label: str
    style: Style
    sections: tuple[Section, ...]

    @property
    def bars(self) -> int:
        return sum(s.bars for s in self.sections)


def _s(name, kind, bars, energy, fill=False, variation=0, rest=0.0, **parts) -> Section:
    return Section(name, kind, bars, energy, dict(parts), fill, variation, rest)


def parse_segments(spec: str, bars: int) -> list[tuple[str, int, int]]:
    """'kick_hats:8,groove' -> [('kick_hats', 0, 8), ('groove', 8, rest)]; '-' is silence.
    A segment without a length takes what is left of the section."""
    segments, offset = [], 0
    items = [item.strip() for item in spec.split(",") if item.strip()]
    for item in items:
        name, _, count = item.partition(":")
        # A last segment with a length ends the part early: the rest of the section is silent.
        length = max(0, min(int(count) if count else bars - offset, bars - offset))
        if length:
            segments.append((name, offset, length))
        offset += length
    return segments


TEMPLATES: dict[str, Template] = {
    # docs/GENRES.md, House: DJ intro that adds a layer after 8 bars, kick out in builds with a
    # beat of silence before the drop, open hats only in the second half of a drop, bass leaves the outro first.
    "house": Template("house", "House", Style(124, "house", "offbeat", "stabs", swing=0.6, lead_range=(72, 89)), (
        _s("Intro", "intro", 16, 0.4, fill=True, drums="kick_hats:8,groove", chords="-:8,pad"),
        _s("Build", "build", 8, 0.6, fill=True, rest=1.0, drums="no_kick", chords="stabs", lead="tease"),
        _s("Drop", "drop", 32, 0.9, drums="full", bass="on", chords="stabs", lead="hook"),
        _s("Break", "break", 16, 0.4, fill=True, drums="sparse", chords="pad", lead="tease"),
        _s("Build 2", "build", 8, 0.7, fill=True, rest=1.0, drums="no_kick", chords="stabs", lead="tease"),
        _s("Drop 2", "drop", 32, 1.0, variation=1, drums="full", bass="on", chords="stabs", lead="hook"),
        _s("Outro", "outro", 16, 0.3, drums="full:8,kick_hats", bass="on:8", chords="pad:8"),
    )),
    "techno": Template("techno", "Techno", Style(130, "techno", "pulse", "stabs", chords_per_bar=0.5, progressions=SPARSE_PROGRESSIONS), (
        _s("Intro", "intro", 16, 0.3, drums="kick_hats"),
        _s("Groove", "groove", 32, 0.6, drums="full", bass="on"),
        _s("Build", "build", 16, 0.7, fill=True, drums="no_kick", bass="on", chords="on"),
        _s("Peak", "drop", 32, 1.0, drums="full", bass="on", chords="on", lead="sparse"),
        _s("Break", "break", 16, 0.4, chords="sustain"),
        _s("Peak 2", "drop", 32, 1.0, variation=1, drums="full", bass="on", chords="on", lead="sparse"),
        _s("Outro", "outro", 16, 0.3, drums="kick_hats", bass="on"),
    )),
    "drum_and_bass": Template("drum_and_bass", "Drum & Bass", Style(174, "breakbeat", "syncopated", "sustain", chords_per_bar=0.5), (
        _s("Intro", "intro", 16, 0.3, drums="sparse", chords="sustain"),
        _s("Build", "build", 8, 0.6, fill=True, drums="no_kick", chords="sustain", lead="sparse"),
        _s("Drop", "drop", 32, 1.0, drums="full", bass="on", chords="sustain", lead="on"),
        _s("Break", "break", 16, 0.4, chords="sustain", lead="sparse"),
        _s("Build 2", "build", 8, 0.7, fill=True, drums="no_kick", chords="sustain"),
        _s("Drop 2", "drop", 32, 1.0, variation=1, drums="full", bass="on", chords="sustain", lead="on"),
        _s("Outro", "outro", 16, 0.3, drums="sparse", chords="sustain"),
    )),
    "trap": Template("trap", "Trap", Style(140, "trap", "sustained", "sustain", bass_octave=0, chords_per_bar=0.5), (
        _s("Intro", "intro", 8, 0.3, chords="sustain", lead="sparse"),
        _s("Build", "build", 8, 0.6, fill=True, drums="no_kick", chords="sustain", lead="sparse"),
        _s("Drop", "drop", 16, 1.0, drums="full", bass="on", chords="sustain", lead="on"),
        _s("Verse", "verse", 16, 0.6, drums="full", bass="on", chords="sustain"),
        _s("Build 2", "build", 8, 0.7, fill=True, drums="no_kick", chords="sustain", lead="sparse"),
        _s("Drop 2", "drop", 16, 1.0, variation=1, drums="full", bass="on", chords="sustain", lead="on"),
        _s("Outro", "outro", 8, 0.3, chords="sustain", lead="sparse"),
    )),
}

# Which sections grow or shrink when a song should be shorter or longer.
FLEXIBLE_KINDS = ("intro", "outro", "drop", "groove", "verse", "break")


def _round_bars(bars: float) -> int:
    return max(4, int(round(bars / 4.0)) * 4)


def sized(template: Template, length: str = "standard", minutes: float | None = None, beats_per_bar: float = 4.0, tempo: float | None = None) -> tuple[Section, ...]:
    """The template's sections for a radio edit, the standard length, an extended mix, or a target duration."""
    sections = template.sections
    if minutes is not None:
        bpm = tempo or template.style.tempo
        target_bars = minutes * bpm / beats_per_bar
        fixed = sum(s.bars for s in sections if s.kind not in FLEXIBLE_KINDS)
        flexible = sum(s.bars for s in sections if s.kind in FLEXIBLE_KINDS) or 1
        factor = max(0.25, (target_bars - fixed) / flexible)
        return tuple(replace(s, bars=_round_bars(s.bars * factor)) if s.kind in FLEXIBLE_KINDS else s for s in sections)
    if length == "radio":
        return tuple(replace(s, bars=_round_bars(s.bars / 2)) if s.kind in ("intro", "outro", "break") else s for s in sections)
    if length == "extended":
        return tuple(replace(s, bars=s.bars * 2) if s.kind in ("intro", "outro") else s for s in sections)
    return sections
