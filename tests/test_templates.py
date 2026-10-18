"""The tutorial templates: 19 bass patterns, 19 lead patterns, techno patterns, 15 emotion progressions."""

import random

import pytest

from midibakery.compose import harmony
from midibakery.compose.bass_templates import BASS_TEMPLATES, generate_bass_template
from midibakery.compose.chord_templates import CHORD_TEMPLATES, generate_chord_template, template_harmony
from midibakery.compose.drums import map_pads
from midibakery.compose.lead_templates import LEADS, generate_lead_template
from midibakery.compose.parts import generate_part
from midibakery.compose.patterns import bass_names, catalog, drum_names, lead_names, mood_names
from midibakery.compose.rhythm import Meter
from midibakery.compose.specs import BassSpec, ChordsSpec, ComposeRequest, DrumsSpec, MelodySpec
from midibakery.compose.techno_templates import TECHNO, TECHNO_LEADS, generate_techno_drums
from midibakery.compose.theory import Scale

A_MINOR = Scale(9, (0, 2, 3, 5, 7, 8, 10), "Minor")
C_MAJOR = Scale(0)
M44 = Meter(4, 4)
PROGRESSION = "i VI III VII"


def _harmony(scale=A_MINOR, bars=8):
    return harmony.from_progression(PROGRESSION, scale, M44, bars, 1)


def _inside(notes, bars, meter=M44):
    assert notes
    assert all(0 <= n.start_time < bars * meter.beats_per_bar for n in notes)
    assert all(0 <= n.pitch <= 127 and 1 <= n.velocity <= 127 and n.duration > 0 for n in notes)


def test_counts():
    assert len(BASS_TEMPLATES) == 19
    assert len(LEADS) == 19
    assert len(CHORD_TEMPLATES) == 15


@pytest.mark.parametrize("name", list(BASS_TEMPLATES))
def test_bass_templates(name):
    template = BASS_TEMPLATES[name]
    notes = generate_bass_template(template, _harmony(), M44, 8)
    _inside(notes["main"], 8)
    assert bool(template.layer) == ("layer" in notes)
    assert all(n.pitch % 12 in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11) for n in notes["main"])
    # deterministic, and every bar of the cycle has notes
    assert [n.pitch for n in notes["main"]] == [n.pitch for n in generate_bass_template(template, _harmony(), M44, 8)["main"]]
    assert {int(n.start_time // 4) for n in notes["main"]} == set(range(8))


@pytest.mark.parametrize("name", list(LEADS) + list(TECHNO_LEADS))
@pytest.mark.parametrize("scale", [A_MINOR, C_MAJOR])
def test_lead_templates(name, scale):
    template = LEADS.get(name) or TECHNO_LEADS[name]
    parts = generate_lead_template(template, _harmony(scale), scale, M44, 8)
    assert parts
    for notes in parts.values():
        if notes:
            _inside(notes, 8)
            assert 24 <= min(n.pitch for n in notes) and max(n.pitch for n in notes) <= 108


def test_lead_pitches_follow_the_key():
    # descending pedal in E major: the tutorial's degrees 5-4-3-2 over the tonic
    template = LEADS["descending_pedal"]
    notes = generate_lead_template(template, _harmony(Scale(4)), Scale(4), M44, 1)["main"]
    assert {n.pitch % 12 for n in notes} <= Scale(4).pitch_classes
    assert [round(n.start_time * 4) + 1 for n in notes] == [1, 4, 7, 10, 13, 16]


def test_lead_part_cycles_and_active_bars():
    notes = generate_lead_template(LEADS["triad_voicing_dance"], _harmony(), A_MINOR, M44, 4)
    assert {int(n.start_time // 4) for n in notes["dance"]} == {1, 3}  # every second bar
    assert {int(n.start_time // 4) for n in notes["main"]} == {0, 1, 2, 3}


@pytest.mark.parametrize("name", drum_names())
def test_techno_drums(name):
    notes = generate_techno_drums(TECHNO[name], M44, 4, map_pads(None))
    _inside(notes, 4)


def test_techno_refs_resolve():
    for pattern in TECHNO.values():
        if pattern.kind == "bass":
            assert pattern.ref in BASS_TEMPLATES
        if pattern.kind == "lead":
            assert pattern.ref in TECHNO_LEADS
        if pattern.kind == "chords":
            assert pattern.progression


def test_triplet_hats_sit_between_16ths():
    notes = generate_techno_drums(TECHNO["hat_triplets"], M44, 1, map_pads(None))
    assert len(notes) == 24
    assert any(abs((n.start_time * 4) % 1) > 0.01 for n in notes)


@pytest.mark.parametrize("name", list(CHORD_TEMPLATES))
@pytest.mark.parametrize("tonic", [A_MINOR, C_MAJOR])
def test_chord_templates(name, tonic):
    template = CHORD_TEMPLATES[name]
    h = template_harmony(template, tonic, M44, 8)
    parts = generate_chord_template(template, tonic, None, M44, 8)
    _inside(parts["chords"], 8)
    assert ("pedal" in parts) == bool(template.pedal)
    # every chord is the diatonic chord of its mode on the song's tonic
    mode = {0, 2, 4, 5, 7, 9, 11} if template.mode == "major" else {0, 2, 3, 5, 7, 8, 10}
    allowed = {(tonic.root + i) % 12 for i in mode} | ({(tonic.root + 10) % 12} if name == "resolute_major" else set())
    for segment in h.segments:
        assert segment.chord.root in allowed
    # the first chord starts at 0 and the progression fills the clip
    assert parts["chords"][0].start_time == 0.0
    assert h.segments[-1].end == 8 * 4


def test_chord_progressions_match_the_video():
    symbols = lambda name: [s.chord.symbol for s in template_harmony(CHORD_TEMPLATES[name], Scale(9, (0, 2, 3, 5, 7, 8, 10), "Minor"), M44, 4).segments]
    assert symbols("uplifting_sweet") == ["F", "Am", "C", "G"]  # 6 1 3 7
    assert symbols("sad_neutral") == ["Am", "G", "F", "G"]  # 1 7 6 5-ish: i VII VI VII
    assert symbols("dark_cinematic")[0] == "Am"
    c_major = Scale(0)
    happy = [s.chord.symbol for s in template_harmony(CHORD_TEMPLATES["happy"], c_major, M44, 4).segments]
    assert happy == ["Am", "F", "C", "G"]  # 6 4 1 5
    assert [s.chord.symbol for s in template_harmony(CHORD_TEMPLATES["pure_joy"], c_major, M44, 4).segments] == ["Am", "F", "C", "Dm"]


def test_anticipated_chords_start_on_the_upbeat():
    parts = generate_chord_template(CHORD_TEMPLATES["happy"], C_MAJOR, None, M44, 4)
    starts = sorted({n.start_time for n in parts["chords"]})
    assert starts == [0.0, 3.5, 7.5, 11.5]


def test_specs_accept_names_and_reject_unknown():
    assert BassSpec(track=0, slot=0, pattern="rolling_16").pattern == "rolling_16"
    assert MelodySpec(track=0, slot=0, pattern="gated_vocal").pattern == "gated_vocal"
    assert DrumsSpec(track=0, slot=0, pattern="hat_16").pattern == "hat_16"
    assert ChordsSpec(track=0, slot=0, pattern="happy").pattern == "happy"
    with pytest.raises(ValueError, match="unknown bass pattern"):
        BassSpec(track=0, slot=0, pattern="nope")
    with pytest.raises(ValueError, match="unknown chord pattern"):
        ChordsSpec(track=0, slot=0, pattern="nope")
    with pytest.raises(ValueError, match="either pattern or progression"):
        ChordsSpec(track=0, slot=0, pattern="happy", progression="Am F")
    with pytest.raises(ValueError, match="unknown"):
        ComposeRequest(kind="chords", track=0, slot=0, pattern="rolling_16").spec()
    assert ComposeRequest(kind="chords", track=0, slot=0, pattern="happy").spec().pattern == "happy"
    assert ComposeRequest(kind="bass", track=0, slot=0, pattern="tekkaos_phrygian").spec().pattern == "tekkaos_phrygian"


@pytest.mark.parametrize("name", bass_names())
def test_generate_part_bass_pattern(name):
    spec = BassSpec(track=0, slot=0, pattern=name, bars=4)
    notes = generate_part(spec, _harmony(bars=4), A_MINOR, M44, 4, random.Random(1))
    _inside(notes, 4)


@pytest.mark.parametrize("name", lead_names())
def test_generate_part_lead_pattern(name):
    spec = MelodySpec(track=0, slot=0, pattern=name, bars=4)
    _inside(generate_part(spec, _harmony(bars=4), A_MINOR, M44, 4, random.Random(1)), 4)


@pytest.mark.parametrize("name", drum_names())
def test_generate_part_drum_pattern(name):
    spec = DrumsSpec(track=0, slot=0, pattern=name, bars=4)
    _inside(generate_part(spec, None, A_MINOR, M44, 4, random.Random(1)), 4)


@pytest.mark.parametrize("name", mood_names())
def test_generate_part_mood(name):
    spec = ChordsSpec(track=0, slot=0, pattern=name, bars=4)
    h = template_harmony(CHORD_TEMPLATES[name], A_MINOR, M44, 4)
    _inside(generate_part(spec, h, A_MINOR, M44, 4, random.Random(1)), 4)


def test_catalog_lists_everything():
    c = catalog()
    assert len(c["mood"]) == 15
    assert len(c["melody"]) >= 19 and len(c["bass"]) >= 19 and c["drums"]
    assert all(entry["description"] for family in c.values() for entry in family)
