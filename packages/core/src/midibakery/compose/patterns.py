"""Named patterns for the compose tool: one place that knows the template families.

- bass:   ``BASS_TEMPLATES`` (19 bass patterns) plus the techno tutorial's bass entries
- melody: ``LEADS`` (19 lead patterns) plus the techno tutorial's ambience and build-up leads
- drums:  the techno tutorial's clap and hat patterns
- mood:   ``CHORD_TEMPLATES`` (15 emotion progressions), usable by chords, bass and melody
"""

from __future__ import annotations

from midibakery.compose import harmony as harmony_mod
from midibakery.compose import user_patterns
from midibakery.compose.bass_templates import BASS_TEMPLATES, BassTemplate, describe_template
from midibakery.compose.chord_templates import CHORD_TEMPLATES, MAJOR, MINOR, ChordTemplate, describe_chords, template_scale
from midibakery.compose.lead_templates import LEADS, LeadTemplate, describe_lead
from midibakery.compose.rhythm import Meter
from midibakery.compose.techno_templates import TECHNO, TECHNO_LEADS, TechnoPattern, describe_techno
from midibakery.compose.theory import Scale


def bass_names() -> tuple[str, ...]:
    return tuple(BASS_TEMPLATES) + tuple(n for n, p in TECHNO.items() if p.kind == "bass")


def lead_names() -> tuple[str, ...]:
    return tuple(LEADS) + tuple(n for n in TECHNO_LEADS if n not in LEADS)


def drum_names() -> tuple[str, ...]:
    return tuple(n for n, p in TECHNO.items() if p.kind == "drums")


def mood_names() -> tuple[str, ...]:
    return tuple(CHORD_TEMPLATES)


def bass_template(name: str) -> BassTemplate:
    if name in BASS_TEMPLATES:
        return BASS_TEMPLATES[name]
    if name not in TECHNO:
        return user_patterns.load("bass", name)  # type: ignore[return-value]
    return BASS_TEMPLATES[TECHNO[name].ref]


def lead_template(name: str) -> LeadTemplate:
    if name in LEADS:
        return LEADS[name]
    return TECHNO_LEADS[name] if name in TECHNO_LEADS else user_patterns.load("lead", name)  # type: ignore[return-value]


def drum_pattern(name: str) -> TechnoPattern:
    return TECHNO[name] if name in TECHNO else user_patterns.load("drums", name)  # type: ignore[return-value]


def user_pattern_names(family: str) -> tuple[str, ...]:
    """The imported Sets' patterns of one family (bass, melody, drums); not part of the tool descriptions."""
    return user_patterns.names("lead" if family == "melody" else family)


def mood_template(name: str) -> ChordTemplate:
    return CHORD_TEMPLATES[name]


def user_harmony(name: str, tonic: Scale, meter: Meter, bars: int, chords_per_bar: float | None = None) -> harmony_mod.Harmony:
    """The chords of an imported Set's loop, in the mode it was played in, on the song's tonic."""
    progression, rate, mode = user_patterns.chords(name)
    scale = Scale(tonic.root, MAJOR if mode == "major" else MINOR, mode.capitalize())
    return harmony_mod.from_progression(progression, scale, meter, bars, rate if chords_per_bar is None else chords_per_bar)


def mood_harmony(name: str, tonic: Scale, meter: Meter, bars: int, chords_per_bar: float | None = None) -> harmony_mod.Harmony:
    """The progression of a named mood pattern in its own mode on the tonic; its own chord rate unless one is given."""
    if name not in CHORD_TEMPLATES:
        return user_harmony(name, tonic, meter, bars, chords_per_bar)
    template = mood_template(name)
    rate = template.chords_per_bar if chords_per_bar is None else chords_per_bar
    return harmony_mod.from_progression(template.progression, template_scale(template, tonic), meter, bars, rate)


def catalog() -> dict[str, list[dict[str, object]]]:
    """Every pattern with its description, per family (for docs and listings)."""
    return {
        "bass": [describe_template(BASS_TEMPLATES[n]) for n in BASS_TEMPLATES] + [describe_techno(TECHNO[n]) for n in bass_names() if n in TECHNO],
        "melody": [describe_lead(lead_template(n)) for n in lead_names()],
        "drums": [describe_techno(TECHNO[n]) for n in drum_names()],
        "mood": [describe_chords(t) for t in CHORD_TEMPLATES.values()],
    }
