"""Genre sevenths decorate generated diatonic chords, never rewrite chords the user named."""

import random
from dataclasses import replace

from midibakery.compose import harmony as harmony_mod
from midibakery.compose.grooves import seventh_harmony
from midibakery.compose.rhythm import Meter
from midibakery.compose.theory import Scale

A_MINOR = Scale(9, (0, 2, 3, 5, 7, 8, 10), "Minor")
M44 = Meter(4, 4)


def _pcs(harmony):
    return [sorted(segment.chord.intervals) for segment in harmony.segments]


def test_generated_diatonic_triads_still_get_sevenths():
    generated = harmony_mod.from_progression("i VI v VII", A_MINOR, M44, 4, 1)
    assert all(len(i) == 4 for i in _pcs(seventh_harmony(generated, A_MINOR)))


def test_explicit_chords_keep_their_quality():
    explicit = replace(harmony_mod.from_progression("Am F E G", A_MINOR, M44, 4, 1), explicit=True)
    assert seventh_harmony(explicit, A_MINOR) is explicit
    e_major = explicit.segments[2].chord
    assert e_major.symbol == "E" and sorted(e_major.intervals) == [0, 4, 7]  # the G# survives, no Em7


def test_explicitness_survives_cycling():
    explicit = replace(harmony_mod.from_progression("Am F E G", A_MINOR, M44, 4, 1), explicit=True)
    assert explicit.for_length(M44, 8).explicit
    assert not harmony_mod.auto(A_MINOR, M44, 4, 1, random.Random(1)).explicit
