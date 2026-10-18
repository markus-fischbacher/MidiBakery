"""Named patterns for the compose tool: one place that knows the template families.

- bass:   ``BASS_TEMPLATES`` (19 bass patterns) plus the techno tutorial's bass entries
- melody: ``LEADS`` (19 lead patterns) plus the techno tutorial's ambience and build-up leads
- drums:  the techno tutorial's clap and hat patterns
- mood:   ``CHORD_TEMPLATES`` (15 emotion progressions), usable by chords, bass and melody
"""

from __future__ import annotations

from midibakery.compose.bass_templates import BASS_TEMPLATES, BassTemplate, describe_template
from midibakery.compose.chord_templates import CHORD_TEMPLATES, ChordTemplate, describe_chords
from midibakery.compose.lead_templates import LEADS, LeadTemplate, describe_lead
from midibakery.compose.techno_templates import TECHNO, TECHNO_LEADS, TechnoPattern, describe_techno


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
    return BASS_TEMPLATES[TECHNO[name].ref]


def lead_template(name: str) -> LeadTemplate:
    return LEADS[name] if name in LEADS else TECHNO_LEADS[name]


def drum_pattern(name: str) -> TechnoPattern:
    return TECHNO[name]


def mood_template(name: str) -> ChordTemplate:
    return CHORD_TEMPLATES[name]


def catalog() -> dict[str, list[dict[str, object]]]:
    """Every pattern with its description, per family (for docs and listings)."""
    return {
        "bass": [describe_template(BASS_TEMPLATES[n]) for n in BASS_TEMPLATES] + [describe_techno(TECHNO[n]) for n in bass_names() if n in TECHNO],
        "melody": [describe_lead(lead_template(n)) for n in lead_names()],
        "drums": [describe_techno(TECHNO[n]) for n in drum_names()],
        "mood": [describe_chords(t) for t in CHORD_TEMPLATES.values()],
    }
