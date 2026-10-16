"""One part's notes from its request model, the same for every caller: the compose
tool and plans (plan.py), take lanes (takes.py) and the MIDI Tools (standalone.py)."""

from __future__ import annotations

import random

from midibakery.compose.bass import generate_bass
from midibakery.compose.chords import generate_chords
from midibakery.compose.drums import DrumMap, generate_drums, map_pads
from midibakery.compose.harmony import Harmony
from midibakery.compose.melody import generate_melody
from midibakery.compose.notes import Note
from midibakery.compose.rhythm import Meter
from midibakery.compose.specs import SWING_UNITS, BassSpec, ChordsSpec, DrumsSpec, Generate, MelodySpec
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
) -> list[Note]:
    """Drums need no harmony (`drum_map` defaults to General MIDI); the others need one."""
    unit = SWING_UNITS[spec.swing_unit]  # type: ignore[attr-defined]
    if isinstance(spec, DrumsSpec):
        return generate_drums(
            meter, bars, spec.style, rng, drum_map or map_pads(None),
            density=spec.density, swing=spec.swing, swing_unit=unit, fills=spec.fills, chance=spec.chance,
        )
    assert harmony is not None, "bass, chords and melody follow a harmony"
    if isinstance(spec, BassSpec):
        return generate_bass(
            harmony, scale, meter, bars, spec.style, rng, spec.octave, kick, spec.kick_relation,
            density=spec.density, swing=spec.swing, swing_unit=unit,
        )
    if isinstance(spec, ChordsSpec):
        return generate_chords(harmony, meter, bars, spec.rhythm, rng, spec.low, spec.high, spec.voices, swing=spec.swing, swing_unit=unit)
    if isinstance(spec, MelodySpec):
        return generate_melody(harmony, scale, meter, bars, rng, spec.low, spec.high, spec.density, swing=spec.swing, swing_unit=unit)
    raise TypeError(f"no generator for {type(spec).__name__}")
