"""Unit tests for the composition engine: theory, determinism, scale and bar boundaries."""

import random

import pytest

from midishower.compose import harmony
from midishower.compose import transform as tf
from midishower.compose.bass import STYLES as BASS_STYLES
from midishower.compose.bass import generate_bass
from midishower.compose.chords import RHYTHMS, generate_chords
from midishower.compose.drums import GM_NOTES, STYLES as DRUM_STYLES
from midishower.compose.drums import classify_pad, generate_drums, kick_times, map_pads
from midishower.compose.melody import generate_melody
from midishower.compose.rhythm import Grid, Meter
from midishower.compose.theory import (
    Scale,
    detect_chord,
    diatonic_chord,
    functional_progression,
    parse_chord,
    parse_progression,
    pitch_name,
    voice_lead,
)

A_MINOR = Scale(9, (0, 2, 3, 5, 7, 8, 10), "Minor")
C_MAJOR = Scale(0)
D_DORIAN = Scale(2, (0, 2, 3, 5, 7, 9, 10), "Dorian")
E_PENTA = Scale(4, (0, 3, 5, 7, 10), "Minor Pentatonic")
METERS = [Meter(4, 4), Meter(3, 4), Meter(6, 8), Meter(7, 8), Meter(5, 4)]


def as_tuples(notes):
    return [(n.pitch, n.start_time, n.duration, n.velocity, n.probability, n.velocity_deviation) for n in notes]


# --------------------------------------------------------------------------
# Theory
# --------------------------------------------------------------------------


def test_scale_from_song_data():
    scale = Scale.from_song({"root_note": 9, "scale_name": "Minor", "scale_intervals": [0, 2, 3, 5, 7, 8, 10]})
    assert scale == A_MINOR
    assert scale.pitch_classes == frozenset({9, 11, 0, 2, 4, 5, 7})
    assert Scale.from_song({}) == Scale(0)
    assert scale.pitch(0, octave=3) == 69  # A3
    assert scale.pitch(7, octave=3) == 81
    assert pitch_name(60) == "C3"


def test_snap_step_and_degrees():
    assert C_MAJOR.snap(61) == 60 and C_MAJOR.snap(61, direction=1) == 62
    assert C_MAJOR.step(64, 1) == 65 and C_MAJOR.step(60, -1) == 59
    assert E_PENTA.step(64, 5) == 76
    for pitch in range(0, 128):
        degree = A_MINOR.degree_of(pitch)
        assert (degree is not None) == A_MINOR.contains(pitch)
        if degree is not None:
            assert A_MINOR.pitch_of_degree(degree) == pitch


def test_diatonic_chords_and_parsing():
    assert [diatonic_chord(C_MAJOR, d).symbol for d in range(7)] == ["C", "Dm", "Em", "F", "G", "Am", "Bdim"]
    assert diatonic_chord(C_MAJOR, 4, 4).symbol == "G7"
    assert [c.symbol for c in parse_progression("i VI III VII", A_MINOR)] == ["Am", "F", "C", "G"]
    assert [c.symbol for c in parse_progression("ii7 - V7 - Imaj7", C_MAJOR)] == ["Dm7", "G7", "Cmaj7"]
    assert parse_chord("V", A_MINOR).symbol == "E"  # harmonic-minor dominant: case wins
    assert parse_chord("bVII", C_MAJOR).symbol == "A#"
    assert parse_chord("F#m7", C_MAJOR).symbol == "F#m7"
    assert parse_chord("vi", C_MAJOR).roman() == "vi"
    with pytest.raises(ValueError):
        parse_chord("H7", C_MAJOR)


def test_functional_progression_is_cadential_and_seeded():
    for seed in range(20):
        chords = functional_progression(C_MAJOR, 4, random.Random(seed))
        assert chords[0].degree == 0
        assert all(c.intervals[:3] != (0, 3, 6) for c in chords)  # no diminished loop chords
        assert all(a != b for a, b in zip(chords, chords[1:])) or chords[-1].degree == 0
        assert chords == functional_progression(C_MAJOR, 4, random.Random(seed))
    pent = functional_progression(E_PENTA, 4, random.Random(1))
    assert all(set(c.pitch_classes) <= E_PENTA.pitch_classes for c in pent)


def test_voice_leading_moves_little_and_stays_in_range():
    chords = parse_progression("I V vi IV I", C_MAJOR)
    voicings = voice_lead(chords, 52, 76)
    for chord, voicing in zip(chords, voicings):
        assert all(52 <= p <= 76 for p in voicing)
        assert sorted(p % 12 for p in voicing) == sorted(chord.pitch_classes)
    for a, b in zip(voicings, voicings[1:]):
        assert sum(abs(x - y) for x, y in zip(a, b)) <= 7


def test_chord_detection():
    assert detect_chord({9: 1.0, 0: 1.0, 4: 1.0}, C_MAJOR).symbol == "Am"
    assert detect_chord({7: 2.0, 11: 1.0, 2: 1.0, 5: 0.5}, C_MAJOR, 7).symbol == "G"


# --------------------------------------------------------------------------
# Rhythm
# --------------------------------------------------------------------------


def test_meter_pulses():
    assert Meter(4, 4).pulses == (0, 1, 2, 3) and Meter(4, 4).backbeats == (1, 3)
    assert Meter(6, 8).pulses == (0, 1.5) and Meter(6, 8).beats_per_bar == 3
    assert Meter(7, 8).pulses == (0, 1, 2)  # 2+2+3
    assert Meter(3, 4).beats_per_bar == 3


def test_swing_and_quantize():
    grid = Grid(Meter(), 0.25, swing=1.0)
    assert grid.position(0, 1) == pytest.approx(0.25 + 0.25 / 3)
    assert grid.position(1, 2) == 4.5
    assert grid.quantize(0.33) == pytest.approx(0.25 + 0.25 / 3)
    assert Grid(Meter(), 0.25).quantize(0.3, strength=0.5) == pytest.approx(0.275)


# --------------------------------------------------------------------------
# Generators: determinism, scale, bar boundaries
# --------------------------------------------------------------------------


def _gens(scale, meter, bars, seed):
    rng = random.Random(seed)
    h = harmony.auto(scale, meter, bars, 1, rng)
    return {
        **{f"drums:{s}": generate_drums(meter, bars, s, random.Random(seed), map_pads(None), 0.6, 0.3) for s in DRUM_STYLES},
        **{f"bass:{s}": generate_bass(h, scale, meter, bars, s, random.Random(seed)) for s in BASS_STYLES},
        **{f"chords:{r}": generate_chords(h, meter, bars, r, random.Random(seed)) for r in RHYTHMS},
        "melody": generate_melody(h, scale, meter, bars, random.Random(seed)),
    }


@pytest.mark.parametrize("meter", METERS, ids=str)
def test_generators_are_deterministic_per_seed(meter):
    first = _gens(D_DORIAN, meter, 4, 1234)
    second = _gens(D_DORIAN, meter, 4, 1234)
    other = _gens(D_DORIAN, meter, 4, 999)
    for key in first:
        assert as_tuples(first[key]) == as_tuples(second[key]), key
        assert first[key], f"{key} produced no notes"
    assert any(as_tuples(first[k]) != as_tuples(other[k]) for k in first)


@pytest.mark.parametrize("scale", [C_MAJOR, A_MINOR, D_DORIAN, E_PENTA], ids=lambda s: s.describe())
@pytest.mark.parametrize("seed", [1, 7, 42])
def test_pitched_parts_stay_in_scale(scale, seed):
    for key, notes in _gens(scale, Meter(4, 4), 8, seed).items():
        if key.startswith("drums"):
            continue
        off = [pitch_name(n.pitch) for n in notes if not scale.contains(n.pitch)]
        assert not off, f"{key} left {scale.describe()}: {off}"


@pytest.mark.parametrize("meter", METERS, ids=str)
@pytest.mark.parametrize("bars", [1, 2, 5])
def test_notes_respect_bar_boundaries(meter, bars):
    from midishower.compose.notes import fit_to_length

    length = meter.beats_per_bar * bars
    for key, notes in _gens(A_MINOR, meter, bars, 3).items():
        assert all(0 <= n.start_time < length for n in notes), key
        fitted = fit_to_length(notes, length)
        assert all(n.end_time <= length + 1e-9 for n in fitted), key
        for n in fitted:
            assert 0 <= n.pitch <= 127 and 1 <= n.velocity <= 127 and 0 <= n.probability <= 1


def test_drums_use_probability_and_velocity_deviation():
    notes = generate_drums(Meter(), 4, "house", random.Random(5), map_pads(None), density=0.4)
    assert any(n.probability < 1 for n in notes)
    assert any(n.velocity_deviation for n in notes)
    kicks = kick_times([{"pitch": n.pitch, "start_time": n.start_time} for n in notes], GM_NOTES["kick"])
    assert kicks[:4] == [0, 1, 2, 3]  # four on the floor


def test_bass_locks_to_kick_and_follows_chords():
    meter = Meter()
    h = harmony.from_progression("I IV", C_MAJOR, meter, 2, 1)
    kick = [0.0, 1.5, 2.5, 4.0, 5.75]
    notes = generate_bass(h, C_MAJOR, meter, 2, "syncopated", random.Random(1), kick=kick)
    assert [n.start_time for n in notes] == kick
    assert notes[0].pitch % 12 == 0 and notes[3].pitch % 12 == 5  # roots on the chord changes
    avoid = generate_bass(h, C_MAJOR, meter, 2, "pulse", random.Random(1), kick=kick, kick_relation="avoid")
    assert all(min(abs(n.start_time - k) for k in kick) >= 0.1 for n in avoid)


def test_melody_strong_beats_are_chord_tones():
    meter = Meter()
    h = harmony.from_progression("vi IV I V", C_MAJOR, meter, 4, 1)
    notes = generate_melody(h, C_MAJOR, meter, 4, random.Random(11))
    for n in notes:
        if meter.accent(n.start_time % 4) >= 0.8:
            assert h.at(n.start_time).chord.contains(n.pitch), (pitch_name(n.pitch), n.start_time)


def test_harmony_detection_round_trip():
    meter = Meter()
    h = harmony.from_progression("vi IV I V", C_MAJOR, meter, 4, 1)
    chords = generate_chords(h, meter, 4, "stabs", random.Random(1))
    dicts = [{"pitch": n.pitch, "start_time": n.start_time, "duration": n.duration} for n in chords]
    detected = harmony.detect(dicts, C_MAJOR, meter, 4, 1)
    assert [s.chord.symbol for s in detected.segments] == ["Am", "F", "C", "G"]


# --------------------------------------------------------------------------
# Drum pads
# --------------------------------------------------------------------------


def test_pad_names_are_classified():
    names = {
        "Kick 808": "kick", "BD Deep": "kick", "Snare Tight": "snare", "Clap Wide": "clap",
        "Hihat Closed": "closed_hat", "HH 1": "closed_hat", "Open Hat": "open_hat", "OH Long": "open_hat",
        "Rimshot": "rim", "Ride Bell": "ride", "Crash": "crash", "Low Tom": "low_tom", "Tom Hi": "high_tom",
        "Shaker": "shaker", "Conga": "perc", "Pad 7": None,
    }
    for name, role in names.items():
        assert classify_pad(name) == role, name


def test_map_pads_with_substitutes_and_gm_fallback():
    assert map_pads(None).source == "gm" and map_pads(None).note("kick") == 36
    kit = map_pads([{"note": 36, "name": "Kick"}, {"note": 40, "name": "Snare"}, {"note": 44, "name": "Closed HH"}])
    assert kit.source == "drum_rack"
    assert kit.note("kick") == 36 and kit.note("snare") == 40
    assert kit.note("clap") == 40  # borrowed from the snare
    assert kit.note("open_hat") == 44  # borrowed from the closed hat
    assert kit.note("crash") is None  # no related pad: role is dropped, not sent to an empty pad
    unnamed = map_pads([{"note": 48, "name": "1"}, {"note": 50, "name": "2"}])
    assert unnamed.note("kick") == 48


# --------------------------------------------------------------------------
# Transformations produce diffs
# --------------------------------------------------------------------------


def _clip(*pitches_starts):
    return [
        {"note_id": i + 1, "pitch": p, "start_time": s, "duration": d, "velocity": 100.0, "mute": False,
         "probability": 1.0, "velocity_deviation": 0.0, "release_velocity": 64.0}
        for i, (p, s, d) in enumerate(pitches_starts)
    ]


def test_quantize_only_touches_off_grid_notes():
    notes = _clip((60, 0.0, 0.5), (62, 0.27, 0.5), (64, 1.0, 0.5))
    diff = tf.quantize(notes, Grid(Meter(), 0.25))
    assert diff.modify == [{"note_id": 2, "start_time": 0.25}]
    assert not diff.add and not diff.remove


def test_humanize_is_seeded_and_modifies_by_id():
    notes = _clip((60, 0.0, 0.5), (62, 1.0, 0.5))
    a = tf.humanize(notes, random.Random(3), 0.8)
    b = tf.humanize(notes, random.Random(3), 0.8)
    assert a.modify == b.modify and {m["note_id"] for m in a.modify} <= {1, 2}
    assert all(set(m) <= {"note_id", "start_time", "velocity"} for m in a.modify)


def test_invert_is_diatonic():
    notes = _clip((60, 0, 1), (64, 1, 1), (67, 2, 1))
    diff = tf.invert(notes, C_MAJOR, axis=64)
    pitches = {m["note_id"]: m["pitch"] for m in diff.modify}
    assert pitches == {1: 67, 3: 60}  # E stays, C <-> G mirrored around E in C major


def test_transpose_in_key():
    diff = tf.transpose(_clip((60, 0, 1), (64, 1, 1)), C_MAJOR, 2)
    assert [m["pitch"] for m in diff.modify] == [64, 67]


def test_arpeggiate_replaces_chords_only():
    notes = _clip((60, 0, 1), (64, 0, 1), (67, 0, 1), (72, 2, 0.5))
    diff = tf.arpeggiate(notes, random.Random(1), rate=0.25, direction="up")
    assert sorted(diff.remove) == [1, 2, 3]
    assert [n.pitch for n in diff.add] == [60, 64, 67, 60]
    assert [n.start_time for n in diff.add] == [0, 0.25, 0.5, 0.75]


def test_variation_keeps_scale_and_uses_probability():
    notes = _clip(*[(C_MAJOR.pitch(d, 3), d * 0.5, 0.5) for d in range(16)])
    diff = tf.variation(notes, random.Random(4), C_MAJOR, amount=1.0)
    assert diff.modify and not diff.add and not diff.remove
    assert all(C_MAJOR.contains(m["pitch"]) for m in diff.modify if "pitch" in m)
    assert any("probability" in m for m in diff.modify)
    assert tf.variation(notes, random.Random(4), C_MAJOR, 1.0).modify == diff.modify


def test_fit_to_length_removes_same_pitch_overlaps():
    from midishower.compose.notes import Note, fit_to_length

    notes = [Note(42, 0.0, 0.5), Note(42, 0.25, 0.5), Note(36, 0.0, 2.0), Note(42, 3.9, 1.0), Note(50, 4.0, 1.0)]
    fitted = fit_to_length(notes, 4.0)
    assert [(n.pitch, n.start_time, n.duration) for n in fitted] == [(36, 0.0, 2.0), (42, 0.0, 0.25), (42, 0.25, 0.5), (42, 3.9, 0.1)]
    for gen in ("trap", "house"):
        drums = fit_to_length(generate_drums(Meter(), 4, gen, random.Random(2), map_pads(None), 1.0, 1.0), 16)
        by_pitch = {}
        for n in drums:
            assert n.start_time >= by_pitch.get(n.pitch, 0) - 1e-9
            by_pitch[n.pitch] = n.end_time
