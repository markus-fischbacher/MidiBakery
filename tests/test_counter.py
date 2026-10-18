"""Counter melody generator: rules from docs/COUNTER_MELODY.md, checked on hand-written main melodies."""

import random

import pytest

from midibakery.compose import harmony as harmony_mod
from midibakery.compose.counter import MODES, PULSE, analyze, consonant, generate_counter
from midibakery.compose.notes import Note
from midibakery.compose.rhythm import Meter
from midibakery.compose.theory import Scale

METER = Meter(4, 4)
SCALE = Scale(0, (0, 2, 3, 5, 7, 8, 10), "Minor")  # C minor
BARS = 4
HARMONY = harmony_mod.from_progression("i VI III VII", SCALE, METER, BARS, 1)
STEP = 0.25


def line(*bars):
    """A main melody from bars of (pitch, step, length in 16ths) notes."""
    return [Note(p, b * 4 + s * STEP, length * STEP, 100) for b, notes in enumerate(bars) for p, s, length in notes]


# a busy 16th line over C minor, pitches 60..72
BUSY_PITCHES = (60, 63, 67, 70, 72, 70, 67, 63)
BUSY = [Note(BUSY_PITCHES[(i + b) % 8], b * 4 + i * STEP, STEP * 0.9, 100) for b in range(BARS) for i in range(16)]
# a sparse line: a few long held notes
SPARSE = line([(67, 0, 8), (65, 10, 6)], [(63, 0, 12)], [(65, 0, 6), (67, 8, 8)], [(60, 0, 16)])
# a phrase: two bars of melody, an empty bar, a closing note
PHRASE = line([(67, 0, 2), (70, 2, 2), (72, 4, 4), (70, 8, 4)], [(67, 0, 4), (65, 4, 4), (63, 8, 8)], [], [(60, 0, 4)])

MAINS = {"busy": BUSY, "sparse": SPARSE, "phrase": PHRASE}


def counter(main, mode, seed=1, **kwargs):
    return generate_counter(main, HARMONY, SCALE, METER, BARS, random.Random(seed), mode, **kwargs)


def sounding(notes, t):
    hit = [n for n in notes if n.start_time <= t + 1e-6 < n.end_time - 1e-6]
    return max(hit, key=lambda n: n.start_time) if hit else None


def strong_beats():
    return [bar * 4 + beat for bar in range(BARS) for beat in range(4) if METER.accent(beat) >= 0.8]


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("name", MAINS)
def test_strong_beats_are_consonant_and_the_line_stays_in_key(mode, name):
    main = MAINS[name]
    notes = counter(main, mode)
    for t in strong_beats():
        c, m = sounding(notes, t), sounding(main, t)
        if c and m:
            assert consonant(c.pitch - m.pitch, unison_ok=mode == "note_layering"), (mode, name, t, c.pitch, m.pitch)
    assert all(SCALE.contains(n.pitch) for n in notes)
    assert all(n.end_time <= BARS * 4 + 1e-6 for n in notes)


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("name", MAINS)
def test_no_parallel_fifths_or_octaves(mode, name):
    main = MAINS[name]
    notes = counter(main, mode)
    for a, b in zip(notes, notes[1:]):
        ma, mb = sounding(main, a.start_time), sounding(main, b.start_time)
        if not ma or not mb or ma == mb:
            continue
        ia, ib = abs(a.pitch - ma.pitch) % 12, abs(b.pitch - mb.pitch) % 12
        moved_together = (b.pitch - a.pitch) * (mb.pitch - ma.pitch) > 0
        assert not (moved_together and ia == ib and ia in (0, 7)), (mode, name, a, b)


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("name", MAINS)
def test_register_above_and_below_stay_an_octave_clear_and_never_cross(mode, name):
    main = MAINS[name]
    top, bottom = max(n.pitch for n in main), min(n.pitch for n in main)
    above = counter(main, mode, register="above")
    below = counter(main, mode, register="below")
    if name == "busy" and mode in ("fill_the_gaps", "call_and_response", "echo_gap_answer"):
        assert not above and not below  # no gap to answer in
        return
    assert above and below
    assert min(n.pitch for n in above) >= top + 12
    assert max(n.pitch for n in below) <= bottom - 12


def test_same_register_never_starts_with_the_main():
    for mode in MODES:
        main_starts = {round(n.start_time, 3) for n in SPARSE}
        notes = counter(SPARSE, mode, register="same")
        assert not main_starts & {round(n.start_time, 3) for n in notes}, mode


def onset_inside_main(main, note):
    """Starts while a main note is held or in a rest, not with a main onset."""
    return not any(abs(m.start_time - note.start_time) < 1e-6 for m in main)


@pytest.mark.parametrize("name", ["sparse", "phrase"])
def test_fill_the_gaps_starts_inside_held_notes_and_rests(name):
    main = MAINS[name]
    notes = counter(main, "fill_the_gaps")
    assert notes
    inside = [n for n in notes if onset_inside_main(main, n)]
    assert len(inside) >= 0.8 * len(notes)


def test_fill_the_gaps_has_nothing_to_add_to_a_line_without_gaps():
    assert counter(BUSY, "fill_the_gaps") == []


def test_call_and_response_answers_in_silent_beats_and_owns_the_empty_bar():
    notes = counter(PHRASE, "call_and_response")
    assert notes
    for n in notes:
        assert sounding(PHRASE, n.start_time) is None  # always starts in a rest
        assert not [m for m in PHRASE if m.start_time < n.end_time - 1e-6 and m.end_time > n.start_time + 1e-6]
    empty_bar = [n for n in notes if 8 <= n.start_time < 12]
    assert len(empty_bar) >= 2


def test_passive_over_active_thins_a_busy_line_and_fills_a_sparse_one():
    busy = counter(BUSY, "passive_over_active")
    assert 0.3 <= len(busy) / len(BUSY) <= 0.55
    assert sum(n.duration for n in busy) / len(busy) > 0.5  # longer notes
    sparse = counter(SPARSE, "passive_over_active")
    assert len(sparse) > len(SPARSE)


@pytest.mark.parametrize("name", MAINS)
def test_contrasting_rhythm_differs_from_the_main_per_bar(name):
    main = MAINS[name]
    notes = counter(main, "contrasting_rhythm")
    assert notes
    for bar in range(BARS):
        mine = {round(n.start_time / STEP) for n in notes if bar * 4 <= n.start_time < bar * 4 + 4}
        theirs = {round(n.start_time / STEP) for n in main if bar * 4 <= n.start_time < bar * 4 + 4}
        assert mine != theirs
        if mine and theirs:
            assert len(mine & theirs) / len(mine | theirs) <= 0.5


@pytest.mark.parametrize("name", MAINS)
def test_harmonic_notes_never_share_a_pitch_class_with_the_main(name):
    main = MAINS[name]
    notes = counter(main, "harmonic_notes")
    assert notes
    for n in notes:
        for m in main:
            if m.start_time < n.end_time - 1e-6 and m.end_time > n.start_time + 1e-6:
                assert n.pitch % 12 != m.pitch % 12, (n, m)


def test_note_layering_uses_the_mains_pitch_classes_an_octave_away():
    notes = counter(SPARSE, "note_layering")
    assert notes
    main_classes = {m.pitch % 12 for m in SPARSE}
    layered = [n for n in notes if n.pitch % 12 in main_classes]
    assert len(layered) >= 0.7 * len(notes)
    assert min(n.pitch for n in notes) >= max(m.pitch for m in SPARSE) + 12


@pytest.mark.parametrize("mode", MODES)
def test_same_seed_same_notes_and_another_seed_other_notes(mode):
    if mode == "trance_dotted_eighth_staircase":  # a fixed figure: only clashes with the main change a note
        shape = lambda seed: [(n.pitch, n.start_time) for n in counter(SPARSE, mode, seed=seed)]  # noqa: E731
        assert shape(7) == shape(8)
        return
    main = PHRASE if mode == "call_and_response" else SPARSE
    assert counter(main, mode, seed=7) == counter(main, mode, seed=7)
    assert any(counter(main, mode, seed=s) != counter(main, mode, seed=7) for s in range(8, 14))


def test_a_shorter_main_loops():
    two_bars = line([(67, 0, 4), (70, 8, 8)], [(63, 0, 8)])
    looped = analyze(two_bars, METER, BARS)
    assert len(looped.notes) == 6
    assert looped.onsets_per_bar == (2, 1, 2, 1)
    notes = counter(two_bars, "fill_the_gaps")
    assert any(n.start_time >= 8 for n in notes)


def test_analysis_reads_onsets_rests_and_range():
    a = analyze(PHRASE, METER, BARS)
    assert a.onsets_per_bar == (4, 3, 0, 1)
    assert (a.low, a.high) == (60, 72)
    assert a.at(0.0).pitch == 67 and a.at(1.0).pitch == 72
    assert (8.0, 12.0) in a.rests()
    assert a.silent(8.0, 12.0) and not a.silent(0.0, 1.0)


def test_modes_and_arguments_are_checked():
    with pytest.raises(ValueError, match="unknown counter melody mode"):
        counter(SPARSE, "echo")
    with pytest.raises(ValueError, match="unknown register"):
        counter(SPARSE, "fill_the_gaps", register="left")
    with pytest.raises(ValueError, match="no notes"):
        counter([], "fill_the_gaps")


def bar_notes(notes, bar):
    return [n for n in notes if bar * 4 <= n.start_time < bar * 4 + 4 - 1e-6]


def held_bars(bars=8):
    """A main that only ticks on the off-beat 16th before each bar ends: no strong beat to clash with."""
    return line(*[[(67, 14, 1)]] * bars)


def test_pulse_onsets_fall_on_the_3_3_3_3_3_1_steps():
    assert PULSE == (0, 3, 6, 9, 12, 15)
    for mode in ("dotted_eighth_pulse", "scale_staircase", "trance_dotted_eighth_staircase"):
        notes = counter(held_bars(BARS), mode)
        assert len(bar_notes(notes, 0)) == 6
        for n in notes:
            assert round(n.start_time * 4) % 16 in PULSE, (mode, n)
        assert {round(n.start_time * 4) % 16 for n in bar_notes(notes, 1)} == set(PULSE)


def test_dotted_eighth_pulse_is_one_chord_tone_per_bar():
    notes = counter(held_bars(BARS), "dotted_eighth_pulse")
    for bar in range(BARS):
        mine = bar_notes(notes, bar)
        assert len({n.pitch for n in mine}) == 1
        assert HARMONY.at(bar * 4).chord.contains(mine[0].pitch)
    clashing = counter(SPARSE, "dotted_eighth_pulse")  # over held notes a few notes move to a consonant tone
    assert all(SCALE.contains(n.pitch) for n in clashing)


def test_scale_staircase_rises_by_scale_steps_over_the_cycle():
    harmony = harmony_mod.from_progression("i", SCALE, METER, 8, 1)
    notes = generate_counter(held_bars(), harmony, SCALE, METER, 8, random.Random(3), "scale_staircase")
    per_bar = []
    for bar in range(8):
        pitches = {n.pitch for n in bar_notes(notes, bar)}
        assert len(pitches) == 1
        per_bar.append(SCALE.degree_of(pitches.pop()))
    assert set(b - a for a, b in zip(per_bar, per_bar[1:])) <= {-1, 0, 1}
    assert per_bar[:7] == sorted(per_bar[:7])
    assert max(per_bar) == per_bar[0] + 3 and per_bar[7] == per_bar[0] + 2  # top reached, one step back for bar 8
    assert SCALE.pitch_of_degree(per_bar[0]) % 12 == SCALE.root


def test_trance_figure_follows_the_described_degrees_per_bar():
    harmony = harmony_mod.from_progression("i", SCALE, METER, 8, 1)
    notes = generate_counter(held_bars(), harmony, SCALE, METER, 8, random.Random(1), "trance_dotted_eighth_staircase")
    base = SCALE.degree_of(min(n.pitch for n in notes))
    degrees = []
    for bar in range(8):
        pitches = {n.pitch for n in bar_notes(notes, bar)}
        assert len(pitches) == 1
        degrees.append(SCALE.degree_of(pitches.pop()) - base)
    assert degrees == [0, 0, 1, 1, 2, 2, 4, 4]


def test_a_pulse_note_that_clashes_on_a_strong_beat_moves_to_a_consonant_tone():
    main = line(*[[(67, 0, 8), (68, 8, 8)]] * BARS)  # held G, then A flat, every bar
    for mode in ("dotted_eighth_pulse", "scale_staircase", "trance_dotted_eighth_staircase"):
        notes = counter(main, mode)
        assert notes
        for t in strong_beats():
            c, m = sounding(notes, t), sounding(main, t)
            if c and m:
                assert consonant(c.pitch - m.pitch), (mode, t)


def test_echo_gap_answer_sits_in_held_notes_and_ends_on_a_longer_note():
    notes = counter(SPARSE, "echo_gap_answer")
    assert notes
    held = [(m.start_time, m.end_time) for m in SPARSE if m.duration >= 1.25]
    groups = {}
    for n in notes:
        span = next((h for h in held if h[0] < n.start_time < h[1]), None)
        assert span, n  # every answer note starts inside a long main note, never on its onset
        groups.setdefault(span, []).append(n)
    for group in groups.values():
        *short, last = group
        assert 3 <= len(short) <= 4
        assert last.duration > max(n.duration for n in short)
        assert last.start_time >= max(n.start_time for n in short)
    assert min(n.pitch for n in notes) >= max(m.pitch for m in SPARSE) + 12


def test_echo_gap_answer_moves_by_steps():
    notes = counter(SPARSE, "echo_gap_answer")
    for a, b in zip(notes, notes[1:]):
        if b.start_time - a.start_time <= 0.25 + 1e-6 and b.duration < 0.3:
            assert abs(b.pitch - a.pitch) <= 4, (a, b)  # a scale step; a clash shift may add a little


def test_echo_gap_answer_has_nothing_to_add_to_a_line_of_short_notes():
    assert counter(BUSY, "echo_gap_answer") == []
