"""Song structures per genre: sections with length, energy and what each role plays.

Templates are data. A section names its kind (intro, build, drop, ...) and for
every role a part: drums "full" / "no_kick" / "kick_hats" / "sparse" (Peak-Time also
"kick_only" and "drive"), the other roles "on", "sparse" or absent (silent); bass
"rumble" and chords "accent" are the quiet break pulse and one hit per phrase. Energy (0-1) drives density and
velocity. Sections of the same kind share their notes, which keeps a song
together; `variation` gives a later section of that kind its own notes.

Automation: a style names an Auto Filter type per role (`filters`), a section moves
its cutoff with `sweeps`, in Hz and in the segment syntax of the parts: "20:8,20>300"
holds 20 Hz for 8 bars, then sweeps to 300 Hz. A filtered role without a sweep
stays open (Low-pass 20 kHz, High-pass 20 Hz). "300>8000~exp" curves (slow start; ~log:
fast start), "400>3000~sine/2" swings between the two every 2 bars (also triangle, saw, square).
"chords.res" rides the same Auto Filter's resonance in % ("0>40~exp"); a role with a resonance
ride anywhere gets 0 % where a section has none. `throws`: in the named section kinds the role's
send to the Delay return jumps up on the last beat of every 8 bars.

Mix: a style's `mix` sets the faders of new tracks and the sends to a Reverb and a
Delay return, in dB as Live shows them; a role without a send stays dry.

FX: a riser fills the last bars (at most 8) before every drop that follows another kind
of section, an impact hits the drop's first beat; `sounds` names their presets.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Literal

Role = Literal["drums", "bass", "chords", "lead"]
ROLES: tuple[Role, ...] = ("drums", "bass", "chords", "lead")
FX_ROLES = ("riser", "impact")  # placed by the song's drops, not by the sections' parts
EXTRA_ROLES = ("answer", "lead2", "bass2")  # complexity="rich": voices derived from the lead and bass, with parts like the others
RICH_FX = ("sweep",)  # rich: a noise track for sweeps, downlifters and swells
LEAD_SOUND = "Synth Keys/Light Keys.adg"  # every genre's lead: it sounds better than the genre presets did
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
    pause_every: int = 0  # >0: the last bar of every N bars without kick and bass (a short breath)
    sweeps: dict[str, str] = field(default_factory=dict)  # role -> Auto Filter cutoff in Hz, e.g. "20:8,20>300"


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
class Mix:
    """Start levels of a song's new tracks and its two returns; role -> dB as Live shows it."""

    volume: dict[str, float] = field(default_factory=dict)  # fader
    reverb: dict[str, float] = field(default_factory=dict)  # send to the Reverb return
    delay: dict[str, float] = field(default_factory=dict)  # send to the Delay return
    decay: float = 2.0  # Reverb decay in seconds
    delay_16ths: int = 3  # Delay time in 16th notes (3 = dotted 8th)
    feedback: float = 0.35  # Delay feedback, 0-1
    duck: dict[str, float] = field(default_factory=dict)  # sidechain: Compressor threshold keyed from the kick
    release: float = 0.15  # its release in seconds: back up before the next kick


@dataclass(frozen=True)
class Style:
    """What a genre sets beyond its grooves (grooves.py: drums, bass and chords, with their swing)."""

    tempo: float
    chords_per_bar: float = 1.0
    lead_range: tuple[int, int] = (64, 86)
    lead: str = "hook"  # "hook" (call/response), "arp" (Melodic Techno), "acid" (Peak-Time)
    devices: dict[str, str] = field(default_factory=dict)  # role -> native device for new tracks
    sounds: dict[str, tuple[str, ...]] = field(default_factory=dict)  # role -> browser path loaded onto a new track
    filters: dict[str, str] = field(default_factory=dict)  # role -> Auto Filter type ("Low-pass", "High-pass") for sweeps
    mix: Mix = field(default_factory=Mix)
    throws: dict[str, tuple[str, ...]] = field(default_factory=dict)  # role -> section kinds with delay throws
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


def _s(name, kind, bars, energy, fill=False, variation=0, rest=0.0, pause=0, sweeps=None, **parts) -> Section:
    return Section(name, kind, bars, energy, dict(parts), fill, variation, rest, pause, dict(sweeps or {}))


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


def _kit(folder: str, name: str) -> tuple[str, ...]:
    """A Core Library Drum Rack."""
    return ("packs", "Core Library", "Racks", "Drum Racks", folder, f"{name}.adg")


def _mix(volume: str, reverb: str, delay: str, decay: float, delay_16ths: int, feedback: float, duck: str = "-,-,-,-", release: float = 0.15) -> Mix:
    """Levels per role as "drums,bass,chords,lead" in dB; "-" = no send (no ducking)."""
    def levels(spec: str) -> dict[str, float]:
        return {role: float(db) for role, db in zip(ROLES, spec.split(",")) if db.strip() != "-"}

    vol, rev, dly, ducks = {**levels(volume), **FX_VOLUME}, {**levels(reverb), **FX_REVERB}, {**levels(delay), **FX_DELAY}, levels(duck)
    # The second voices sit under the first: a little quieter, the answer wetter so it sounds further back.
    vol |= {"answer": vol["lead"] - 3, "lead2": vol["lead"] - 5, "bass2": vol["bass"] - 4, "sweep": vol["riser"] - 2}
    rev |= {"answer": rev.get("lead", -16) + 4, "lead2": rev.get("lead", -16), "sweep": -14.0}
    dly["answer"] = dly.get("lead", -18) - 2
    if "bass" in ducks:
        ducks["bass2"] = ducks["bass"]
    return Mix(vol, rev, dly, decay, delay_16ths, feedback, ducks, release)


FX_VOLUME = {"riser": -12.0, "impact": -8.0}
FX_REVERB = {"riser": -12.0, "impact": -18.0}
FX_DELAY = {"riser": -22.0}
FX_SOUNDS = {"riser": "Effects/Riser Basic.adg", "impact": "Bass/Sub 808 Pitch Boom.adg"}
# complexity="rich": the second voices sound different from the first (genres may name their own).
RICH_SOUNDS = {"answer": "Synth Keys/Basic Pluck Keys.adg", "lead2": "Synth Lead/Basic Peak Lead.adg", "bass2": "Bass/Reese Classic.adg",
               "sweep": "Effects/Broadcast Noise.adg"}


def _sounds(drums: tuple[str, ...], **presets: str) -> dict[str, tuple[str, ...]]:
    """The kit plus role -> "Category/Preset" in the browser's Sounds."""
    presets = {**FX_SOUNDS, **RICH_SOUNDS, **presets}
    return {"drums": drums, **{role: ("sounds", *path.split("/")) for role, path in presets.items()}}


TEMPLATES: dict[str, Template] = {
    # docs/GENRES.md, House: DJ intro that adds a layer after 8 bars, kick out in builds with a
    # beat of silence before the drop, open hats only in the second half of a drop, bass leaves the outro first.
    # Sweeps: the pads open out of the intro and the break, a high-pass lifts the drums in the
    # builds, the pads close again in the outro; the drops are open.
    "house": Template("house", "House", Style(
        124, lead_range=(72, 89),
        sounds=_sounds(_kit("Drum Machines", "909 Core Kit"), bass="Bass/Basic FM House Bass.adg", chords="Synth Keys/106 Organ.adg", lead=LEAD_SOUND),
        mix=_mix("-6,-8,-12,-11", "-24,-,-14,-16", "-,-,-22,-18", decay=1.8, delay_16ths=3, feedback=0.35, duck="-,-24,-18,-", release=0.16),
        filters={"drums": "High-pass", "chords": "Low-pass"}, throws={"lead": ("drop",)},
    ), (
        _s("Intro", "intro", 16, 0.4, fill=True, drums="kick_hats:8,groove", chords="-:8,pad", sweeps={"chords": "-:8,150>20000~exp"}),
        _s("Build", "build", 8, 0.6, fill=True, rest=1.0, drums="no_kick", chords="stabs", lead="tease", sweeps={"drums": "20>400"}),
        _s("Drop", "drop", 32, 0.9, drums="full", bass="on", chords="stabs", lead="hook"),
        _s("Break", "break", 16, 0.4, fill=True, drums="sparse", chords="pad", lead="tease", sweeps={"drums": "150", "chords": "200>20000~exp", "chords.res": "5>40~exp"}),
        _s("Build 2", "build", 8, 0.7, fill=True, rest=1.0, drums="no_kick", chords="stabs", lead="tease", sweeps={"drums": "20>500"}),
        _s("Drop 2", "drop", 32, 1.0, variation=1, drums="full", bass="on", chords="stabs", lead="hook"),
        _s("Outro", "outro", 16, 0.3, drums="full:8,kick_hats", bass="on:8", chords="pad:8", sweeps={"chords": "20000>150:8"}),
    )),
    # docs/GENRES.md, Melodic Techno: kick/hats/pad intro, bass and pads build, arp lead, pads-only breakdown.
    "melodic_techno": Template("melodic_techno", "Melodic Techno", Style(
        122, chords_per_bar=0.5, lead_range=(60, 84), lead="arp",
        sounds=_sounds(_kit("Electronic", "AG Techno Kit"), bass="Bass/Analogue Bass.adv", chords="Pad/Analog Soft Pad.adv", lead=LEAD_SOUND, riser="Effects/Hyper Riser.adg"),
        mix=_mix("-6,-8,-13,-12", "-26,-,-8,-12", "-,-,-20,-12", decay=4.5, delay_16ths=3, feedback=0.45, duck="-,-22,-16,-", release=0.2),
        progressions=MELODIC_PROGRESSIONS, devices={"lead": "Wavetable", "chords": "Wavetable", "bass": "Drift"},
        filters={"drums": "High-pass", "chords": "Low-pass", "lead": "Low-pass"}, throws={"lead": ("break",)},
    ), (
        # Sweeps: slow openings on pads and arp (the genre's long builds), a high-pass on the drums
        # before the climax, the pads close in the outro.
        _s("Intro", "intro", 16, 0.3, fill=True, drums="kick_hats:8,groove", chords="pad", sweeps={"chords": "150>3000"}),
        _s("Build", "build", 16, 0.5, fill=True, drums="groove", bass="on", chords="pad", lead="-:8,tease",
           sweeps={"drums": "20:12,20>200", "chords": "3000>20000~exp", "chords.res": "10>35", "lead": "-:8,500>2000"}),
        _s("Drop", "drop", 32, 0.9, drums="full", bass="on", chords="pad", lead="arp", sweeps={"lead": "800>6000:16,6000>3000"}),
        _s("Breakdown", "break", 16, 0.4, chords="pad", lead="tease", sweeps={"chords": "150>8000~exp", "lead": "600>2500"}),
        _s("Build 2", "build", 8, 0.7, fill=True, rest=1.0, drums="no_kick", chords="pad", lead="tease", sweeps={"drums": "20>350", "lead": "2500>10000"}),
        _s("Climax", "drop", 32, 1.0, variation=1, drums="full", bass="on", chords="pad", lead="arp", sweeps={"lead": "2000>12000"}),
        _s("Outro", "outro", 16, 0.3, drums="full:8,kick_hats", bass="on:8", chords="pad:8", sweeps={"chords": "12000>150:8"}),
    )),
    # docs/GENRES.md, Peak-Time Techno, combined from three reference tracks (Spektre remix, Katoff,
    # T78; 128 BPM, 224 bars = 7:00): tension by taking things away. Before each big drop the bass
    # leaves first, then the kick, while the synth is at its loudest; one bar without kick and bass
    # closes many phrases; after a breakdown the hats come in late; a stripped kick-and-bass part
    # follows the last peak; the outro hands over by removing bass, then kick, then hats.
    "peak_time_techno": Template("peak_time_techno", "Peak-Time Techno", Style(
        128, chords_per_bar=0.5, lead_range=(48, 62), lead="acid",
        sounds=_sounds(_kit("Drum Machines", "909 Core Kit"), bass="Bass/Basic Sub Boom.adg", chords="Pad/Butter Knife Stab.adg", lead=LEAD_SOUND, riser="Effects/Hyper Riser.adg"),
        mix=_mix("-5,-9,-12,-12", "-24,-,-12,-20", "-,-,-16,-16", decay=2.5, delay_16ths=3, feedback=0.4, duck="-,-24,-20,-", release=0.12),
        progressions=DRONE_PROGRESSIONS, devices={"lead": "Drift", "chords": "Wavetable", "bass": "Analog"},
        filters={"drums": "High-pass", "chords": "Low-pass", "lead": "Low-pass"}, throws={"chords": ("groove", "break")},
    ), (
        # Sweeps: the drums' high-pass thins the kick out before each peak and lets it slam back in;
        # the acid opens in the first 8 bars of a peak and closes a little; the lift and the breakdown hold, then sweep
        # in their last 8 / 12 bars, chords open out of the breakdown.
        _s("Intro", "intro", 32, 0.4, fill=True, drums="kick_hats:16,groove", bass="-:16,on"),
        _s("Groove", "groove", 16, 0.6, fill=True, pause=8, drums="groove", bass="on", chords="accent"),
        _s("Lift", "build", 16, 0.7, fill=True, rest=1.0, drums="groove:12,sparse", chords="tease:8,stabs", lead="-:8,tease",
           sweeps={"drums": "20:8,20>300", "chords": "200:8,200>20000~exp", "chords.res": "0:8,0>50~exp", "lead": "600:8,600>2500"}),
        _s("Peak", "drop", 32, 0.9, fill=True, pause=16, drums="full", bass="on", chords="stabs", lead="acid",
           sweeps={"lead": "400>5000:8,5000>1500", "lead.res": "20>60:8,60>30"}),
        _s("Breakdown", "break", 24, 0.5, drums="sparse:8", bass="rumble:16", chords="tease:8,stabs:2,-:2,stabs:2,-:2,stabs:6", lead="-:16,tease:6",
           sweeps={"drums": "250", "chords": "150:12,150>9000~exp", "lead": "800:12,800>3000"}),
        _s("Peak 2", "drop", 32, 1.0, variation=1, fill=True, pause=16, drums="drive:8,full", bass="on", chords="stabs", lead="acid",
           sweeps={"lead": "800>8000:8,8000>2000", "lead.res": "30>70:8,70>40"}),
        _s("Lift 2", "build", 8, 0.8, variation=1, fill=True, rest=1.0, drums="groove:5,sparse", chords="stabs", lead="acid",
           sweeps={"drums": "20>400", "lead": "2000>12000", "lead.res": "40>75"}),
        _s("Peak 3", "drop", 16, 1.0, variation=2, drums="full", bass="on", chords="stabs", lead="acid",
           sweeps={"lead": "6000>3000"}),
        _s("Stripped", "groove", 8, 0.6, variation=1, drums="kick_only:6", bass="on:6"),
        _s("Outro", "outro", 40, 0.4, drums="groove:24,kick_hats:8,sparse", bass="on:24"),
    )),
    # docs/GENRES.md, Drum & Bass: 32-bar DJ intro, drums out for the last 4 bars before a drop,
    # 64-bar drops, a drumless 32-bar breakdown, liquid pads with 2 bars per chord, bass leaves the outro first.
    "drum_and_bass": Template("drum_and_bass", "Drum & Bass", Style(
        174, chords_per_bar=0.5, lead_range=(72, 89),
        sounds=_sounds(_kit("Electronic", "Halfstep Kit"), bass="Bass/Basic Reese Bass.adg", bass2="Bass/Basic Saw Bass.adg", chords="Pad/Basic Mellow Pad.adg", lead=LEAD_SOUND, riser="Effects/ENCOM Riser.adg"),
        mix=_mix("-5,-8,-13,-11", "-26,-,-10,-16", "-,-,-,-16", decay=2.0, delay_16ths=3, feedback=0.3, duck="-,-18,-,-", release=0.09),
        progressions=DNB_PROGRESSIONS, devices={"bass": "Operator", "chords": "Wavetable", "lead": "Operator"},
        filters={"drums": "High-pass", "chords": "Low-pass"}, throws={"lead": ("drop",)},
    ), (
        _s("Intro", "intro", 32, 0.3, fill=True, drums="kick_hats:16,groove", chords="pad", sweeps={"chords": "200>20000~exp"}),
        _s("Build", "build", 16, 0.6, drums="no_kick:12", chords="pad", lead="tease", sweeps={"drums": "20>500"}),
        _s("Drop", "drop", 64, 1.0, fill=True, drums="full", bass="on", chords="pad", lead="hook"),
        _s("Breakdown", "break", 32, 0.4, chords="pad", lead="tease", sweeps={"chords": "150>8000~exp", "chords.res": "0>35~exp"}),
        _s("Build 2", "build", 16, 0.7, drums="no_kick:12", chords="pad", lead="tease", sweeps={"drums": "20>600", "chords": "8000>20000"}),
        _s("Drop 2", "drop", 64, 1.0, variation=1, fill=True, drums="full", bass="on", chords="pad", lead="hook"),
        _s("Outro", "outro", 32, 0.3, drums="full:16,kick_hats", bass="on:8", chords="pad:16", sweeps={"chords": "20000>150:16"}),
    )),
    # docs/GENRES.md, EDM Trap: short (2-3 min), half-time snare on beat 3, hat rolls, an 808 under the
    # kicks, plucks without the root, hook only in the drops, a beat of silence before each drop.
    "trap": Template("trap", "Trap", Style(
        145, chords_per_bar=0.5, lead_range=(69, 86),
        sounds=_sounds(_kit("Drum Machines", "808 Core Kit"), bass="Bass/808 Pure.adg", bass2="Bass/Basic Saw Bass.adg", chords="Synth Keys/Basic Bell Keys.adg", lead=LEAD_SOUND),
        mix=_mix("-6,-7,-12,-11", "-28,-,-12,-16", "-,-,-18,-16", decay=2.2, delay_16ths=2, feedback=0.3, duck="-,-14,-,-", release=0.1),
        progressions=TRAP_PROGRESSIONS, devices={"bass": "Operator", "chords": "Drift", "lead": "Wavetable"},
        filters={"drums": "High-pass", "chords": "Low-pass"}, throws={"lead": ("drop",), "chords": ("verse",)},
    ), (
        _s("Intro", "intro", 8, 0.3, chords="pad", lead="tease", sweeps={"chords": "200>20000~exp"}),
        _s("Build", "build", 8, 0.6, fill=True, rest=1.0, drums="sparse:4,no_kick", chords="pad", lead="tease", sweeps={"drums": "20>300"}),
        _s("Drop", "drop", 16, 1.0, drums="full", bass="on", chords="stabs", lead="hook"),
        _s("Verse", "verse", 16, 0.6, fill=True, drums="groove", bass="on", chords="stabs"),
        _s("Build 2", "build", 8, 0.7, fill=True, rest=1.0, drums="no_kick", chords="pad", lead="tease", sweeps={"drums": "20>400"}),
        _s("Drop 2", "drop", 32, 1.0, variation=1, drums="full", bass="on", chords="stabs", lead="hook"),
        _s("Outro", "outro", 8, 0.3, chords="pad", lead="tease", sweeps={"chords": "20000>150"}),
    )),
}

# Which sections grow or shrink when a song should be shorter or longer.
FLEXIBLE_KINDS = ("intro", "outro", "drop", "groove", "verse", "break")


def _round_bars(bars: float) -> int:
    return max(4, int(round(bars / 4.0)) * 4)


def _scale_spec(spec: str, old: int, new: int) -> str:
    """A part or sweep spec for a section resized from `old` to `new` bars: segment borders
    move with it ("kick_hats:16,groove" in 32 bars -> "kick_hats:8,groove" in 16)."""
    if old == new:
        return spec
    items = [item.strip() for item in spec.split(",") if item.strip()]
    out, pos, new_pos = [], 0, 0
    for item in items:
        name, _, count = item.partition(":")
        if not count:  # takes the rest, in the new length too
            out.append(name)
            continue
        pos += int(count)
        border = min(new, round(pos * new / old))
        if border > new_pos:
            out.append(f"{name}:{border - new_pos}")
        new_pos = border
    return ",".join(out) or "-"


def _resize(section: Section, bars: int) -> Section:
    return replace(
        section,
        bars=bars,
        parts={role: _scale_spec(spec, section.bars, bars) for role, spec in section.parts.items()},
        sweeps={role: _scale_spec(spec, section.bars, bars) for role, spec in section.sweeps.items()},
    )


def sized(template: Template, length: str = "standard", minutes: float | None = None, beats_per_bar: float = 4.0, tempo: float | None = None) -> tuple[Section, ...]:
    """The template's sections for a radio edit, the standard length, an extended mix, or a target duration."""
    sections = template.sections
    if minutes is not None:
        bpm = tempo or template.style.tempo
        target_bars = minutes * bpm / beats_per_bar
        fixed = sum(s.bars for s in sections if s.kind not in FLEXIBLE_KINDS)
        flexible = sum(s.bars for s in sections if s.kind in FLEXIBLE_KINDS) or 1
        factor = max(0.25, (target_bars - fixed) / flexible)
        return tuple(_resize(s, _round_bars(s.bars * factor)) if s.kind in FLEXIBLE_KINDS else s for s in sections)
    if length == "radio":
        return tuple(_resize(s, _round_bars(s.bars / 2)) if s.kind in ("intro", "outro", "break") else s for s in sections)
    if length == "extended":
        return tuple(_resize(s, s.bars * 2) if s.kind in ("intro", "outro") else s for s in sections)
    return sections


# A reference section kind the genre has no section for plays the first kind the genre has.
KIND_FALLBACKS = {"groove": ("groove", "verse", "drop"), "verse": ("verse", "groove", "drop"), "break": ("break", "intro"), "build": ("build", "break")}


def bar_grid(template: Template) -> int:
    """The template's phrase grid: the largest of 16, 8, 4 bars that all its sections fill."""
    return next(g for g in (16, 8, 4) if all(s.bars % g == 0 for s in template.sections)) if template.sections else 4


def _follow_elements(section: Section, elements: list[str], never: set[str], fill: frozenset[str], drum_parts: frozenset[str]) -> Section:
    """The roles an imported Set plays in this section decide which of the genre's parts sound. A role the Set
    plays nowhere is silent too, unless it is in ``fill`` (``fill_missing``, or loops taken from another Set): the genre's part stays."""
    parts = dict(section.parts)
    for role in ("bass", "chords", "lead"):
        if role in elements:
            parts.setdefault(role, "on")
        elif role not in never or role not in fill:
            parts.pop(role, None)
    kick, drums = "kick" in elements, "drums" in elements
    if not kick and not drums:
        if "drums" not in never or "drums" not in fill:
            parts.pop("drums", None)
    elif "drums" not in parts or parts["drums"] in ("-", ""):
        parts["drums"] = "full" if kick and drums else ("kick_hats" if kick else "no_kick")
    elif kick != drums and parts["drums"] in ("full", "groove"):  # a bare kick or no kick, whatever the genre plays
        wanted = "kick_hats" if kick else "no_kick"
        parts["drums"] = wanted if wanted in drum_parts else parts["drums"]
    return replace(section, parts=parts)


def from_reference(template: Template, sections: list[dict], follow_set: bool = False, fill_missing: bool | frozenset[str] = False,
                   drum_parts: frozenset[str] = frozenset()) -> tuple[Section, ...]:
    """A reference song's sections (name, kind, bars) with the template's parts: the n-th drop of the
    reference plays the template's n-th drop (its last one when it has fewer). Section borders
    snap to the template's bar grid; a section never gets shorter than one grid step. With ``follow_set`` (an
    imported Set) the roles it plays in each section decide which of the template's parts sound."""
    grid = bar_grid(template)
    never = {"bass", "chords", "lead", "drums"}
    fill = frozenset(never) if fill_missing is True else frozenset(fill_missing or ())
    for ref in sections:
        elements = ref.get("elements") or []
        never -= set(elements) | ({"drums"} if "kick" in elements else set())
    by_kind: dict[str, list[Section]] = {}
    for s in template.sections:
        by_kind.setdefault(s.kind, []).append(s)
    seen: dict[str, int] = {}
    out, total, end = [], 0.0, 0
    for i, ref in enumerate(sections):
        kind = str(ref.get("kind") or "drop")
        kind = next((k for k in KIND_FALLBACKS.get(kind, (kind,)) if k in by_kind), "drop" if "drop" in by_kind else template.sections[0].kind)
        total += max(0.0, float(ref.get("bars") or 0))
        bars = max(grid, int(total / grid + 0.5) * grid - end)  # half up: round() would snap 18.5 grid steps down
        end += bars
        n = seen.get(kind, 0)
        seen[kind] = n + 1
        source = by_kind[kind][min(n, len(by_kind[kind]) - 1)]
        names = {s.name for s in out}
        name = str(ref.get("name") or source.name)
        if name in names:
            name = f"{name} {i + 1}"
        resized = replace(_resize(source, bars), name=name)
        if follow_set and isinstance(ref.get("elements"), list):
            resized = _follow_elements(resized, ref["elements"], never, fill, drum_parts)
        out.append(resized)
    return tuple(out)
