"""One part's notes from its request model, the same for every caller: the compose
tool and plans (plan.py), take lanes (takes.py) and the MIDI Tools (standalone.py)."""

from __future__ import annotations

import random

from midibakery.compose.bass import generate_bass
from midibakery.compose.chords import generate_chords
from midibakery.compose.counter import generate_counter
from midibakery.compose.drums import DrumMap, generate_drums, map_pads
from midibakery.compose.harmony import Harmony
from midibakery.compose.melody import generate_melody
from midibakery.compose.bass_templates import generate_bass_template
from midibakery.compose.chord_templates import generate_chord_template
from midibakery.compose.lead_templates import generate_lead_template
from midibakery.compose.notes import Note, dedupe
from midibakery.compose.patterns import bass_template, drum_pattern, lead_template, mood_template
from midibakery.compose.rhythm import Meter
from midibakery.compose.specs import SWING_UNITS, BassSpec, ChordsSpec, DrumsSpec, Generate, MelodySpec
from midibakery.compose.techno_templates import generate_techno_drums
from midibakery.compose.theory import Scale


def generate_part(
    spec: Generate,
    harmony: Harmony | None,
    scale: Scale,
    meter: Meter,
    bars: int,
    rng: random.Random,
    drum_map: DrumMap | None = None,
    kick: list[float] | None = None,
    main: list[Note] | None = None,
) -> list[Note]:
    """Drums need no harmony (`drum_map` defaults to General MIDI); the others need one."""
    unit = SWING_UNITS[spec.swing_unit]  # type: ignore[attr-defined]
    if isinstance(spec, DrumsSpec):
        if spec.pattern:
            return generate_techno_drums(drum_pattern(spec.pattern), meter, bars, drum_map or map_pads(None), spec.swing)
        return generate_drums(
            meter, bars, spec.style, rng, drum_map or map_pads(None),
            density=spec.density, swing=spec.swing, swing_unit=unit, fills=spec.fills, chance=spec.chance,
        )
    assert harmony is not None, "bass, chords and melody follow a harmony"
    if isinstance(spec, BassSpec):
        if spec.pattern:
            parts = generate_bass_template(bass_template(spec.pattern), harmony, meter, bars, spec.swing or None)
            return dedupe([n for notes in parts.values() for n in notes])
        return generate_bass(
            harmony, scale, meter, bars, spec.style, rng, spec.octave, kick, spec.kick_relation,
            density=spec.density, swing=spec.swing, swing_unit=unit,
        )
    if isinstance(spec, ChordsSpec):
        if spec.pattern:
            parts = generate_chord_template(mood_template(spec.pattern), scale, harmony, meter, bars)
            return dedupe([n for notes in parts.values() for n in notes])
        return generate_chords(harmony, meter, bars, spec.rhythm, rng, spec.low, spec.high, spec.voices, swing=spec.swing, swing_unit=unit)
    if isinstance(spec, MelodySpec):
        if spec.counter_to is not None:
            assert main is not None, "a counter melody needs the main melody's notes"
            return generate_counter(
                main, harmony, scale, meter, bars, rng, spec.counter_mode or "fill_the_gaps", spec.counter_register or "above",
                density=spec.density if "density" in spec.model_fields_set else None, swing=spec.swing,
            )
        if spec.pattern:
            parts = generate_lead_template(lead_template(spec.pattern), harmony, scale, meter, bars, spec.swing)
            return dedupe([n for notes in parts.values() for n in notes])
        return generate_melody(harmony, scale, meter, bars, rng, spec.low, spec.high, spec.density, swing=spec.swing, swing_unit=unit)
    raise TypeError(f"no generator for {type(spec).__name__}")
