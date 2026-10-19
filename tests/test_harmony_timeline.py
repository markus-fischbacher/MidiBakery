"""Harmony timelines cover every beat of the requested bars, whatever the chord rate."""

import random

import pytest

from midibakery.compose import harmony as harmony_mod
from midibakery.compose.rhythm import Meter
from midibakery.compose.theory import Scale

SCALE = Scale(0, (0, 2, 3, 5, 7, 8, 10), "Minor")
METERS = [Meter(4, 4), Meter(3, 4), Meter(6, 8), Meter(7, 8)]
RATES = [0.25, 0.3, 0.5, 0.6, 0.8, 1, 2, 4]


def _assert_covers(harmony, total):
    segments = harmony.segments
    assert segments[0].start == 0
    for a, b in zip(segments, segments[1:]):
        assert b.start == pytest.approx(a.end)
        assert a.length > 0
    assert segments[-1].end == pytest.approx(total)


@pytest.mark.parametrize("meter", METERS)
@pytest.mark.parametrize("rate", RATES)
@pytest.mark.parametrize("bars", [1, 3, 5, 7])
def test_every_builder_covers_the_exact_length(meter, rate, bars):
    total = meter.beats_per_bar * bars
    _assert_covers(harmony_mod.from_progression("i VI III VII", SCALE, meter, bars, rate), total)
    _assert_covers(harmony_mod.auto(SCALE, meter, bars, rate, random.Random(1)), total)
    notes = [{"pitch": 48, "start_time": 0, "duration": total, "velocity": 90}]
    _assert_covers(harmony_mod.detect(notes, SCALE, meter, bars, rate), total)


def test_reported_cases_end_where_the_bars_end():
    four = Meter(4, 4)
    assert harmony_mod.from_progression("i VI", SCALE, four, 5, 0.5).segments[-1].end == 20
    assert harmony_mod.from_progression("i VI", SCALE, four, 3, 0.8).segments[-1].end == 12


def test_whole_segment_cases_are_unchanged():
    harmony = harmony_mod.from_progression("i VI III VII", SCALE, Meter(4, 4), 4, 1)
    assert [(s.start, s.length) for s in harmony.segments] == [(0, 4), (4, 4), (8, 4), (12, 4)]
    assert len(harmony_mod.from_progression("i", SCALE, Meter(4, 4), 4, 0.5).segments) == 2
