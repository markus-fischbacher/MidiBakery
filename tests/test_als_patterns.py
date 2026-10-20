"""Loops taken from imported Sets: extraction, the user library, and composing with the names."""

import pytest
from starlette.testclient import TestClient

from als_fixtures import edm_set, keytrack, midi_clip, note, track, write_set
from midibakery.als import library, patterns, roles
from midibakery.als.reader import read
from midibakery.api.server import build_app
from midibakery.bridge import BridgeClient
from midibakery.compose import user_patterns
from midibakery.compose.bass_templates import generate_bass_template
from midibakery.compose.parts import generate_part
from midibakery.compose.patterns import bass_names, bass_template, drum_pattern, lead_template, user_pattern_names
from midibakery.compose.rhythm import Meter
from midibakery.compose.specs import BassSpec, DrumsSpec, MelodySpec
from midibakery.compose.theory import Scale
from test_api import AUTH, TOKEN


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("MIDIBAKERY_HOME", str(tmp_path / "home"))
    return tmp_path


def _extract(path):
    song = read(path)
    assigned = roles.assign(song)
    return song, patterns.extract(song, assigned, "G minor", "als-000000000001")


def test_extracts_bass_lead_and_drum_loops(tmp_path):
    items = {i["name"]: i for i in _extract(edm_set(tmp_path / "Loops Demo.als"))[1]}
    assert set(items) == {"my_loops_demo_bass_1", "my_loops_demo_lead_1", "my_loops_demo_drums_1", "my_loops_demo_drums_2"}  # the 2nd: the intro's bare kick
    bass = items["my_loops_demo_bass_1"]
    assert [n["step"] for n in bass["bars"][0]] == [1, 5, 9, 13]  # one note per beat
    assert {n["interval"] for n in bass["bars"][0]} == {0}  # stored on its own root
    lead = items["my_loops_demo_lead_1"]
    assert len(lead["bars"]) == 2 and {n["degree"] for b in lead["bars"] for n in b} == {0, 2}  # the tonic and the minor third of G minor
    drums = items["my_loops_demo_drums_1"]
    assert {h["role"] for h in drums["bars"][0]} == {"kick", "clap"}
    assert "Loops Demo" in bass["description"] and "128 BPM" in bass["description"]


def test_a_part_that_never_repeats_is_not_a_loop(tmp_path):
    clip = midi_clip(0, 16, [keytrack(31 + i, note(i * 4, 0.5)) for i in range(4)])
    path = write_set(tmp_path / "Once.als", [track("MidiTrack", "Bass", clip)])
    assert _extract(path)[1] == []


def test_other_time_signatures_are_skipped(tmp_path):
    path = write_set(tmp_path / "Waltz.als", [track("MidiTrack", "Bass", midi_clip(0, 12, [keytrack(31, *(note(i, 0.5) for i in range(12)))]))],
                     signature=2 + 99 * 2)
    assert _extract(path)[1] == []


def test_a_lead_outside_its_key_gives_no_pattern(tmp_path):
    clip = midi_clip(0, 16, [keytrack(61 + i % 2, *(note(b * 4 + i, 0.5) for b in range(4) for i in range(0, 4, 2)))
                             for i in range(2)])
    path = write_set(tmp_path / "Chromatic.als", [track("MidiTrack", "Lead", clip)])
    assert not [i for i in _extract(path)[1] if i["kind"] == "lead"]


def test_import_stores_the_library_and_delete_removes_it(home):
    path = edm_set(home / "Loops Demo.als")
    done = library.run([str(path)])
    assert done["failed"] == [] and len(done["imported"][0]["patterns"]) == 4
    assert "my_loops_demo_bass_1" in user_pattern_names("bass")
    assert user_pattern_names("melody") == ("my_loops_demo_lead_1",)
    assert library.delete(done["imported"][0]["id"])
    assert user_pattern_names("bass") == ()


def test_importing_again_replaces_the_patterns(home):
    path = edm_set(home / "Loops Demo.als")
    library.run([str(path)])
    library.run([str(path)])
    assert len(user_patterns.entries()) == 4


def test_user_names_work_in_specs_but_not_in_the_tool_text(home):
    library.run([str(edm_set(home / "Loops Demo.als"))])
    assert BassSpec(track=0, pattern="my_loops_demo_bass_1").pattern == "my_loops_demo_bass_1"
    assert "my_loops_demo_bass_1" not in bass_names()
    with pytest.raises(ValueError, match="my_\\* pattern"):
        BassSpec(track=0, pattern="my_nothing_bass_1")


def test_composes_with_every_family(home):
    library.run([str(edm_set(home / "Loops Demo.als"))])
    from midibakery.compose import harmony as harmony_mod
    meter, scale = Meter(4, 4), Scale(7, (0, 2, 3, 5, 7, 8, 10), "Minor")
    harmony = harmony_mod.from_progression("i", scale, meter, 4, 1)
    bass = generate_part(BassSpec(track=0, pattern="my_loops_demo_bass_1"), harmony, scale, meter, 4, __import__("random").Random(1))
    assert len(bass) == 16 and {n.pitch % 12 for n in bass} == {7}  # on the chord root, G
    lead = generate_part(MelodySpec(track=0, pattern="my_loops_demo_lead_1"), harmony, scale, meter, 4, __import__("random").Random(1))
    assert lead and all(scale.contains(n.pitch) for n in lead)
    drums = generate_part(DrumsSpec(track=0, pattern="my_loops_demo_drums_1"), None, scale, meter, 4, __import__("random").Random(1))
    assert {n.pitch for n in drums} == {36, 39}  # kick and clap on the GM map


def test_user_bass_follows_the_chords(home):
    library.run([str(edm_set(home / "Loops Demo.als"))])
    from midibakery.compose import harmony as harmony_mod
    meter, scale = Meter(4, 4), Scale(0, (0, 2, 4, 5, 7, 9, 11), "Major")
    harmony = harmony_mod.from_progression("I IV", scale, meter, 2, 1)
    notes = generate_bass_template(bass_template("my_loops_demo_bass_1"), harmony, meter, 2)["main"]
    assert {n.pitch % 12 for n in notes if n.start_time < 4} == {0} and {n.pitch % 12 for n in notes if n.start_time >= 4} == {5}


def test_lookups_of_unknown_user_names_fail_clearly(home):
    with pytest.raises(KeyError):
        lead_template("my_nothing_lead_1")
    with pytest.raises(KeyError):
        drum_pattern("my_nothing_drums_1")


def test_api_lists_patterns_and_run_reports_them(home):
    path = edm_set(home / "Loops Demo.als")
    from test_api import ScriptedProvider, Turn
    client = TestClient(build_app(BridgeClient(), lambda options: ScriptedProvider([Turn("end_turn", text="hi")]), TOKEN))
    ran = client.post("/import/run", json={"files": [str(path)]}, headers=AUTH).json()
    assert len(ran["imported"][0]["patterns"]) == 4
    listed = client.get("/import/patterns", headers=AUTH).json()["patterns"]
    assert {p["kind"] for p in listed} == {"bass", "lead", "drums"} and listed[0]["set_name"] == "Loops Demo"
    assert client.get("/import/patterns").status_code == 401
    set_id = ran["imported"][0]["id"]
    assert client.delete(f"/import/patterns/{set_id}").status_code == 401
    assert client.delete(f"/import/patterns/{set_id}", headers=AUTH).json() == {"deleted": 4}
    assert client.get("/import/patterns", headers=AUTH).json()["patterns"] == []
    assert client.get("/import/library", headers=AUTH).json()["library"][0]["id"] == set_id  # the Set stays imported


def _chord_set(path):
    """Eight bars of Gm, Eb, Bb, F (i VI III VII in G minor), one chord a bar."""
    chords = [(55, 58, 62), (51, 55, 58), (58, 62, 65), (53, 57, 60)]
    keys = [keytrack(pitch, *(note(bar * 4, 4) for bar in range(8) if chords[bar % 4][i] == pitch)) for i in range(3) for pitch in {c[i] for c in chords}]
    return write_set(path, [track("MidiTrack", "Chords", midi_clip(0, 32, keys))])


def test_extracts_the_chord_progression_as_roman_numerals(tmp_path):
    items = {i["name"]: i for i in _extract(_chord_set(tmp_path / "Chord Demo.als"))[1]}
    chords = items["my_chord_demo_chords_1"]
    assert chords["progression"] == "i bVI bIII bVII" and chords["chords_per_bar"] == 1.0 and chords["scale"] == "minor"
    assert "4-bar chords loop" in chords["description"]


def test_a_chord_loop_composes_on_any_tonic(home):
    library.run([str(_chord_set(home / "Chord Demo.als"))])
    from midibakery.compose import harmony as harmony_mod
    from midibakery.compose.patterns import mood_harmony
    harmony = mood_harmony("my_chord_demo_chords_1", Scale(2, (0, 2, 4, 5, 7, 9, 11), "Major"), Meter(4, 4), 4)
    roots = [s.chord.root for s in harmony.segments]  # the Gm Eb Bb F of the Set, moved with its key onto D
    assert [(b - a) % 12 for a, b in zip(roots, roots[1:])] == [8, 7, 7] and [s.chord.intervals[1] for s in harmony.segments] == [3, 4, 4, 4]
    assert harmony_mod and user_pattern_names("chords") == ("my_chord_demo_chords_1",)


def test_api_lists_the_progression_of_a_chord_loop(home):
    from test_api import ScriptedProvider, Turn
    client = TestClient(build_app(BridgeClient(), lambda options: ScriptedProvider([Turn("end_turn", text="hi")]), TOKEN))
    client.post("/import/run", json={"files": [str(_chord_set(home / "Chord Demo.als"))]}, headers=AUTH)
    chords = [p for p in client.get("/import/patterns", headers=AUTH).json()["patterns"] if p["kind"] == "chords"]
    assert len(chords) == 1 and len(chords[0]["progression"].split()) == 4 and chords[0]["chords_per_bar"] == 1.0


def test_a_chord_loop_keeps_its_own_key_when_the_sets_key_is_wrong(tmp_path):
    path = _chord_set(tmp_path / "Chord Demo.als")
    song = read(path)
    items = patterns.extract(song, roles.assign(song), "C# major", "als-000000000001")  # the Gm Eb Bb F loop is nowhere near C# major
    chords = [i for i in items if i["kind"] == "chords"]
    assert chords and chords[0]["progression"] == "i bVI bIII bVII" and chords[0]["scale"] == "minor"
