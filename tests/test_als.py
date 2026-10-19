"""The .als importer: reading Live 11 and 12 Sets, roles, key, sections, the library and its API."""

import gzip
import json

import pytest
from starlette.testclient import TestClient

from als_fixtures import (audio_clip, drum_rack, edm_set, four_on_the_floor, keytrack, midi_clip, note, track,
                          write_set)
from midibakery.als import key as key_mod
from midibakery.als import library, roles, sections
from midibakery.als.reader import AlsError, clip_notes, read
from midibakery.als.reference import build as build_reference
from midibakery.api.server import build_app
from midibakery.bridge import BridgeClient
from midibakery.compose.song import _check_unwarped
from test_api import AUTH, TOKEN


@pytest.mark.parametrize("live", [11, 12])
def test_reads_tempo_signature_tracks_and_returns(tmp_path, live):
    song = read(edm_set(tmp_path / "a.als", live=live, tempo=132, locators=[(64, "Drop")]))
    assert (song.tempo, song.beats_per_bar, song.live_major) == (132, 4, live)
    assert [t.kind for t in song.tracks] == ["midi", "midi", "midi", "midi", "return"]  # Live puts returns in Tracks
    assert [(loc.beat, loc.name) for loc in song.locators] == [(64, "Drop")]


def test_time_signature_code_is_numerator_and_denominator(tmp_path):
    waltz = read(write_set(tmp_path / "w.als", [], signature=2 + 99 * 2))  # 3/4
    assert waltz.beats_per_bar == 3
    six_eight = read(write_set(tmp_path / "s.als", [], signature=5 + 99 * 3))  # 6/8
    assert six_eight.beats_per_bar == 3


def test_a_file_that_is_not_a_set_is_an_error(tmp_path):
    (tmp_path / "x.als").write_bytes(b"not gzip")
    with pytest.raises(AlsError):
        read(tmp_path / "x.als")
    (tmp_path / "y.als").write_bytes(gzip.compress(b"<html/>"))
    with pytest.raises(AlsError):
        read(tmp_path / "y.als")


def _clip(xml):
    import xml.etree.ElementTree as ET

    return ET.fromstring(xml)


def test_loop_repeats_the_loop_region_to_the_clip_length():
    clip = _clip(midi_clip(0, 16, [keytrack(60, note(0), note(1), note(3))], loop_end=2, loop_on=True))
    notes, loop = clip_notes(clip, 16)
    assert loop == 2
    assert [n.time for n in notes if n.pitch == 60] == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
    # the note at beat 3 lies behind the loop end: it never sounds
    assert len(notes) == 16


def test_start_marker_offsets_the_first_pass_only():
    clip = _clip(midi_clip(0, 8, [keytrack(60, note(0), note(1), note(2), note(3))], loop_end=4, start_relative=2, loop_on=True))
    notes, _ = clip_notes(clip, 8)
    # plays notes 2, 3, then the loop from the top: 0, 1, 2, 3 ... cut at 8 beats
    assert [n.time for n in notes] == [0, 1, 2, 3, 4, 5, 6, 7][: len(notes)]
    assert [n.time for n in notes][:2] == [0, 1] and len(notes) == 8


def test_notes_beyond_the_clip_end_and_disabled_notes_are_dropped():
    clip = _clip(midi_clip(0, 4, [keytrack(60, note(0), note(1, enabled=False), note(3.5, 2), note(5))], loop_end=8))
    notes, loop = clip_notes(clip, 4)
    assert loop == 0
    assert [(n.time, n.duration) for n in notes] == [(0, 0.25), (3.5, 0.5)]


def test_drum_rack_pads_are_read_from_their_inverted_receiving_notes(tmp_path):
    rack = drum_rack([(36, "Kick"), (38, "Snare")])
    song = read(write_set(tmp_path / "d.als", [track("MidiTrack", "Pattern", devices=rack)]))
    pads = song.tracks[0].devices[0].pads
    assert [(p.note, p.name) for p in pads] == [(36, "Kick"), (38, "Snare")]


def test_roles_come_from_names_then_instruments_then_pitch(tmp_path):
    kit = drum_rack([(36, "Kick"), (38, "Snare")])
    low = midi_clip(0, 4, [keytrack(33, note(0, 1))])
    high = midi_clip(0, 4, [keytrack(72, note(0, 1))])
    tracks = [
        track("MidiTrack", "SC Trigger", id_=1), track("MidiTrack", "Kick Rumble", id_=2),
        track("MidiTrack", "Hat/Ride/Clap", id_=3), track("MidiTrack", "Psy Bass", id_=4),
        track("MidiTrack", "Acid Fx", id_=5), track("MidiTrack", "Hook", id_=6),
        track("MidiTrack", "Beats", devices=kit, id_=7),
        track("MidiTrack", "Track 8", low, id_=8), track("MidiTrack", "Track 9", high, id_=9),
        track("MidiTrack", "Filter", id_=10), track("AudioTrack", "Something", id_=11),
        track("GroupTrack", "BASS", id_=12), track("ReturnTrack", "A-Bass Reverb", id_=13),
    ]
    found = roles.assign(read(write_set(tmp_path / "r.als", tracks)))
    assert list(found.values()) == ["sidechain", "kick", "drums", "bass", "fx", "lead", "drums", "bass", "lead",
                                    "unknown", "unknown", "group", "return"]


def test_key_from_notes_and_unsure_when_close(tmp_path):
    g_minor = [31, 38, 43, 46, 38, 31, 36, 46, 34, 43, 50, 31, 38, 43, 46, 41, 36, 39]
    notes = [keytrack(p, note(i * 0.5, 0.5)) for i, p in enumerate(g_minor)]
    song = read(write_set(tmp_path / "k.als", [track("MidiTrack", "Lead", midi_clip(0, 16, notes), id_=1)]))
    assert key_mod.detect(song, roles.assign(song)).startswith("G minor")
    empty = read(write_set(tmp_path / "e.als", [track("MidiTrack", "Lead", id_=1)]))
    assert key_mod.detect(empty, roles.assign(empty)) == "?"


def test_sections_follow_who_plays_when(tmp_path):
    song = read(edm_set(tmp_path / "s.als"))
    act, found = sections.sections(song, roles.assign(song))
    assert (act.first_bar, act.bars) == (1, 32)
    assert [(s["start_bar"], s["bars"], s["kind"]) for s in found] == [
        (1, 4, "intro"), (5, 4, "build"), (9, 8, "drop"), (17, 8, "break"), (25, 8, "drop")]
    drop = found[2]
    assert set(drop["elements"]) >= {"kick", "bass", "lead", "drums"}
    assert found[3]["kick"] == 0 and found[3]["name"] == "Break" and found[4]["name"] == "Drop 2"


def test_locators_name_the_sections_and_say_what_they_are(tmp_path):
    song = read(edm_set(tmp_path / "l.als", locators=[(0, "Start"), (32, "Pre Chorus"), (64, "Chorus"), (96, "Outro")]))
    _, found = sections.sections(song, roles.assign(song))
    assert [(s["start_bar"], s["name"], s["kind"]) for s in found] == [
        (1, "Start", "intro"), (9, "Pre Chorus", "build"), (17, "Chorus", "drop"), (25, "Outro", "outro")]


def test_audio_clips_count_as_playing_and_a_late_start_is_trimmed(tmp_path):
    tracks = [track("AudioTrack", "Kick Loop", audio_clip(64, 128), id_=1),
              track("MidiTrack", "Bass", midi_clip(64, 128, [keytrack(31, note(0, 4))]), id_=2)]
    song = read(write_set(tmp_path / "au.als", tracks))
    act, found = sections.sections(song, roles.assign(song))
    assert (act.first_bar, act.bars) == (17, 16)
    assert found[0]["start_bar"] == 1


def test_reference_has_what_plan_song_reads(tmp_path):
    ref = build_reference(edm_set(tmp_path / "Night Drive.als", tempo=130))
    assert ref["name"] == "Night Drive" and ref["tempo"] == 130 and ref["bar_grid"] == "als" and ref["source"] == "als"
    assert ref["id"].startswith("als-") and ref["bars"] == 32 and ref["first_bar"] == 1
    assert {"name", "kind", "start_bar", "bars", "kick", "elements"} <= set(ref["sections"][0])
    assert set(ref["lanes"]) == set(roles.PLAYING_ROLES) and len(ref["lanes"]["kick"]) == 32
    # bars are musical, not seconds: no drift check against the song's tempo
    _check_unwarped(ref, 150.0)
    with pytest.raises(ValueError):
        build_reference(write_set(tmp_path / "empty.als", [track("MidiTrack", "Kick", id_=1)]))


def test_find_sets_skips_backups_and_non_sets(tmp_path):
    edm_set(tmp_path / "A Project" / "A.als")
    edm_set(tmp_path / "A Project" / "Backup" / "A [2025-01-01 100000].als")
    edm_set(tmp_path / "B Project" / "B.als")
    (tmp_path / "B Project" / "notes.txt").write_text("x")
    (tmp_path / "B Project" / ".hidden.als").write_bytes(b"")
    assert [p.name for p in library.find_sets(tmp_path)] == ["A.als", "B.als"]
    assert [p.name for p in library.find_sets(tmp_path / "B Project" / "B.als")] == ["B.als"]
    with pytest.raises(ValueError):
        library.find_sets(tmp_path / "B Project" / "notes.txt")
    with pytest.raises(ValueError):
        library.find_sets(tmp_path / "missing")


@pytest.fixture
def api(bridge_env, tmp_path):
    from test_api import ScriptedProvider, Turn

    return TestClient(build_app(BridgeClient(), lambda options: ScriptedProvider([Turn("end_turn", text="hi")]), TOKEN))


def test_import_endpoints_need_the_token(api, tmp_path):
    for method, path in (("post", "/import/scan"), ("post", "/import/preview"), ("post", "/import/run"),
                         ("get", "/import/library"), ("delete", "/import/als-0123456789ab")):
        assert getattr(api, method)(path).status_code == 401
    assert "Set Importer" in api.get("/importer").text  # the page itself holds no secret


def test_import_scan_preview_run_library_delete(api, tmp_path):
    folder = tmp_path / "Sets"
    one = edm_set(folder / "One Project" / "One.als", tempo=126)
    edm_set(folder / "Two Project" / "Two.als", live=11)
    (folder / "Bad Project").mkdir()
    (folder / "Bad Project" / "Bad.als").write_bytes(b"junk")

    found = api.post("/import/scan", json={"path": str(folder)}, headers=AUTH).json()["sets"]
    assert [s["name"] for s in found] == ["Bad", "One", "Two"] and not any(s["imported"] for s in found)

    preview = api.post("/import/preview", json={"file": str(one)}, headers=AUTH).json()
    assert preview["tempo"] == 126 and len(preview["sections"]) == 5
    assert api.post("/import/preview", json={"file": str(folder / "Bad Project" / "Bad.als")}, headers=AUTH).status_code == 422

    files = [s["file"] for s in found]
    result = api.post("/import/run", json={"files": files, "genres": {str(one): "house"}}, headers=AUTH).json()
    assert [i["name"] for i in result["imported"]] == ["One", "Two"] and [f["file"] for f in result["failed"]] == [files[0]]

    stored = {d["name"]: d for d in (json.loads(f.read_text()) for f in library.references_dir().glob("als-*.json"))}
    assert stored["One"]["bar_grid"] == "als" and stored["One"]["genre"] == "house" and "genre" not in stored["Two"]
    from midibakery.compose.references import find_reference

    assert find_reference("One")["tempo"] == 126  # plan_song / get_reference see it like any reference

    rescanned = api.post("/import/scan", json={"path": str(folder)}, headers=AUTH).json()["sets"]
    assert [s["imported"] for s in rescanned] == [False, True, True]
    listing = api.get("/import/library", headers=AUTH).json()["library"]
    assert [i["name"] for i in listing] == sorted(i["name"] for i in listing) and len(listing) == 2

    assert api.delete(f"/import/{listing[0]['id']}", headers=AUTH).json() == {"deleted": True}
    assert api.delete(f"/import/{listing[0]['id']}", headers=AUTH).json() == {"deleted": False}
    assert api.delete("/import/..%2Fsecrets", headers=AUTH).status_code in (404, 422)
    assert len(api.get("/import/library", headers=AUTH).json()["library"]) == 1


def test_import_rejects_bad_input(api):
    assert api.post("/import/scan", json={"path": "/no/such/place"}, headers=AUTH).status_code == 422
    assert api.post("/import/scan", json={}, headers=AUTH).status_code == 422
    assert api.post("/import/run", json={"files": "x"}, headers=AUTH).status_code == 422
    assert api.post("/import/scan", content=b"[1]", headers=AUTH).status_code == 422


def test_pick_asks_the_system_dialog_and_a_cancel_is_empty(api, monkeypatch):
    import subprocess

    ran = []

    def fake(cmd, **kwargs):
        ran.append(cmd[-1])
        return subprocess.CompletedProcess(cmd, 0 if len(ran) == 1 else 1, "/Users/me/Sets\n", "")

    monkeypatch.setattr(library.subprocess, "run", fake)
    monkeypatch.setattr(library.sys, "platform", "darwin")
    assert api.post("/import/pick", json={"kind": "folder"}, headers=AUTH).json() == {"path": "/Users/me/Sets"}
    assert "choose folder" in ran[0]
    assert api.post("/import/pick", json={"kind": "file"}, headers=AUTH).json() == {"path": ""}  # cancelled
    assert "{\"als\"}" in ran[1]
    assert api.post("/import/pick", json={"kind": "x"}, headers=AUTH).status_code == 422
    assert api.post("/import/pick", json={"kind": "file"}).status_code == 401
