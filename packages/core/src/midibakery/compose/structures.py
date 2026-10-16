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
Genre = Literal["house", "melodic_techno", "peak_time_techno", "drum_and_bass", "trap"]
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
# Peak-Time: one chord, with a two-chord shift in the last 2 bars of each 8 for movement (Attack:
# "a two-chord parallel shift adds movement"). Major songs use vi as the home chord.
DRONE_PROGRESSIONS = {"major": ((5, 5, 5, 4), (5, 5, 5, 3), (5, 5, 5, 1)), "minor": ((0, 0, 0, 6), (0, 0, 0, 5), (0, 0, 0, 3))}
# Melodic Techno (Beatportal): Am-F-C-G, Am-Dm-Em-C.
MELODIC_PROGRESSIONS = {"major": ((5, 3, 0, 4), (5, 1, 2, 0)), "minor": ((0, 5, 2, 6), (0, 3, 4, 2))}
# Drum & Bass (KAN): i-VI-III-VII, i-III-VI-iv, i-VII-VI-VII, i-iv-v.
DNB_PROGRESSIONS = {"major": ((5, 3, 0, 4), (0, 5, 3, 4)), "minor": ((0, 5, 2, 6), (0, 2, 5, 3), (0, 6, 5, 6), (0, 3, 4, 0))}
# Trap (eMastered, NI): i-VI-v-i, i-III-V-iv, i-iv-v, i-III-VI-VII.
TRAP_PROGRESSIONS = {"major": ((5, 3, 0, 4), (5, 4, 3, 4)), "minor": ((0, 5, 4, 0), (0, 2, 4, 3), (0, 3, 4, 0), (0, 2, 5, 6))}


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
    lead: str = "hook"  # "hook" (call/response), "arp" (Melodic Techno), "acid" (Peak-Time)
    devices: dict[str, str] = field(default_factory=dict)  # role -> native device for new tracks
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
    # docs/GENRES.md, Melodic Techno: kick/hats/pad intro, bass and pads build, arp lead, pads-only breakdown.
    "melodic_techno": Template("melodic_techno", "Melodic Techno", Style(
        122, "techno", "pulse", "sustain", chords_per_bar=0.5, lead_range=(60, 84), lead="arp",
        progressions=MELODIC_PROGRESSIONS, devices={"lead": "Wavetable", "chords": "Wavetable", "bass": "Drift"},
    ), (
        _s("Intro", "intro", 16, 0.3, fill=True, drums="kick_hats:8,groove", chords="pad"),
        _s("Build", "build", 16, 0.5, fill=True, drums="groove", bass="on", chords="pad", lead="-:8,tease"),
        _s("Drop", "drop", 32, 0.9, drums="full", bass="on", chords="pad", lead="arp"),
        _s("Breakdown", "break", 16, 0.4, chords="pad", lead="tease"),
        _s("Build 2", "build", 8, 0.7, fill=True, rest=1.0, drums="no_kick", chords="pad", lead="tease"),
        _s("Climax", "drop", 32, 1.0, variation=1, drums="full", bass="on", chords="pad", lead="arp"),
        _s("Outro", "outro", 16, 0.3, drums="full:8,kick_hats", bass="on:8", chords="pad:8"),
    )),
    # docs/GENRES.md, Peak-Time Techno: DJ intro, tension by adding one thing per 8-16 bars, kick-less
    # breakdowns that reveal the stab hook, rides and the acid line at the peaks, bass leaves the outro first.
    "peak_time_techno": Template("peak_time_techno", "Peak-Time Techno", Style(
        131, "techno", "pulse", "stabs", swing=0.15, chords_per_bar=0.5, lead_range=(48, 62), lead="acid",
        progressions=DRONE_PROGRESSIONS, devices={"lead": "Drift", "chords": "Wavetable", "bass": "Analog"},
    ), (
        _s("Intro", "intro", 32, 0.4, fill=True, drums="kick_hats:16,groove", chords="-:24,tease"),
        _s("Groove", "groove", 32, 0.6, fill=True, drums="groove", bass="on", chords="-:16,tease"),
        _s("Breakdown", "break", 16, 0.5, fill=True, rest=1.0, drums="no_kick", bass="on", chords="stabs"),
        _s("Peak", "drop", 32, 0.9, fill=True, drums="full", bass="on", chords="stabs", lead="acid"),
        _s("Groove 2", "groove", 16, 0.7, variation=1, fill=True, drums="groove", bass="on", chords="stabs", lead="-:8,tease"),
        _s("Breakdown 2", "break", 16, 0.6, variation=1, fill=True, rest=1.0, drums="no_kick", chords="stabs", lead="tease"),
        _s("Peak 2", "drop", 32, 1.0, variation=1, drums="full", bass="on", chords="stabs", lead="acid"),
        _s("Outro", "outro", 32, 0.4, drums="full:16,kick_hats", bass="on:8"),
    )),
    # docs/GENRES.md, Drum & Bass: 32-bar DJ intro, drums out for the last 4 bars before a drop,
    # 64-bar drops, a drumless 32-bar breakdown, liquid pads with 2 bars per chord, bass leaves the outro first.
    "drum_and_bass": Template("drum_and_bass", "Drum & Bass", Style(
        174, "breakbeat", "syncopated", "sustain", swing=0.1, chords_per_bar=0.5, lead_range=(72, 89),
        progressions=DNB_PROGRESSIONS, devices={"bass": "Operator", "chords": "Wavetable", "lead": "Operator"},
    ), (
        _s("Intro", "intro", 32, 0.3, fill=True, drums="kick_hats:16,groove", chords="pad"),
        _s("Build", "build", 16, 0.6, drums="no_kick:12", chords="pad", lead="tease"),
        _s("Drop", "drop", 64, 1.0, fill=True, drums="full", bass="on", chords="pad", lead="hook"),
        _s("Breakdown", "break", 32, 0.4, chords="pad", lead="tease"),
        _s("Build 2", "build", 16, 0.7, drums="no_kick:12", chords="pad", lead="tease"),
        _s("Drop 2", "drop", 64, 1.0, variation=1, fill=True, drums="full", bass="on", chords="pad", lead="hook"),
        _s("Outro", "outro", 32, 0.3, drums="full:16,kick_hats", bass="on:8", chords="pad:16"),
    )),
    # docs/GENRES.md, EDM Trap: short (2-3 min), half-time snare on beat 3, hat rolls, an 808 under the
    # kicks, plucks without the root, hook only in the drops, a beat of silence before each drop.
    "trap": Template("trap", "Trap", Style(
        145, "trap", "sustained", "sustain", swing=0.12, chords_per_bar=0.5, lead_range=(69, 86),
        progressions=TRAP_PROGRESSIONS, devices={"bass": "Operator", "chords": "Drift", "lead": "Wavetable"},
    ), (
        _s("Intro", "intro", 8, 0.3, chords="pad", lead="tease"),
        _s("Build", "build", 8, 0.6, fill=True, rest=1.0, drums="sparse:4,no_kick", chords="pad", lead="tease"),
        _s("Drop", "drop", 16, 1.0, drums="full", bass="on", chords="stabs", lead="hook"),
        _s("Verse", "verse", 16, 0.6, fill=True, drums="groove", bass="on", chords="stabs"),
        _s("Build 2", "build", 8, 0.7, fill=True, rest=1.0, drums="no_kick", chords="pad", lead="tease"),
        _s("Drop 2", "drop", 32, 1.0, variation=1, drums="full", bass="on", chords="stabs", lead="hook"),
        _s("Outro", "outro", 8, 0.3, chords="pad", lead="tease"),
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
