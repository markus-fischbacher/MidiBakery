"""Whole songs from genre templates: plan_song + apply_plan against the fake LOM."""

import json

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from fake_song import DrumRackDevice
from midibakery.compose.structures import TEMPLATES, sized
from midibakery.mcp import build_server


def _payload(result):
    content = result[0] if isinstance(result, tuple) else result
    if hasattr(content, "structured_content") and content.structured_content:
        return content.structured_content
    items = content.content if hasattr(content, "content") else content
    return json.loads(items[0].text)


def _studio(live):
    """Track 1 with a named Drum Rack, track 2 called 'Bass'."""
    def setup():
        rack = DrumRackDevice()
        for name, note in (("Kick", 36), ("Snare", 38), ("Clap", 39), ("Closed Hat", 42), ("Open Hat", 46)):
            rack.add_pad(name, note)
        live.song.tracks[0].devices.append(rack)
        live.song.tracks[0].name = "Drums"
        live.song.tracks[1].name = "Bass"

    live.on_main(setup)


async def _plan(server, **args):
    return _payload(await server.call_tool("plan_song", {"genre": "house", "seed": 7, **args}))


async def test_house_song_on_found_and_new_tracks(client, live):
    _studio(live)
    server = build_server(client)
    preview = await _plan(server)
    assert preview["genre"] == "House" and preview["from_bar"] == 1 and preview["bars"] == 128
    assert [s["name"] for s in preview["sections"]] == ["Intro", "Build", "Drop", "Break", "Build 2", "Drop 2", "Outro"]
    assert preview["tracks"]["drums"] == {"track": 0, "name": "Drums"} and preview["tracks"]["bass"]["track"] == 1
    assert preview["tracks"]["chords"]["new"] and preview["tracks"]["chords"]["device"] == "Wavetable"
    assert preview["tracks"]["lead"]["device"] == "Operator"
    assert not (await client.call("arrangement.get", {}))["tracks"][0]["clips"]  # a preview changes nothing

    applied = _payload(await server.call_tool("apply_plan", {"plan_id": preview["plan_id"]}))
    assert applied["clips"] == preview["clips"] and [t["name"] for t in applied["new_tracks"]] == ["House Chords", "House Lead"]
    arrangement = await client.call("arrangement.get", {})
    assert [(l["name"], l["time"]) for l in arrangement["locators"]][:3] == [("Intro", 0.0), ("Build", 64.0), ("Drop", 96.0)]
    drums = {c["name"]: c for c in arrangement["tracks"][0]["clips"]}
    assert set(drums) == {"Intro Drums", "Build Drums", "Drop Drums", "Break Drums", "Build 2 Drums", "Drop 2 Drums", "Outro Drums"}
    intro = (await client.call("notes.get", {"track": 0, "arrangement_clip": 0}))["notes"]
    assert 39 not in {n["pitch"] for n in intro if n["start_time"] < 32} and 39 in {n["pitch"] for n in intro}  # clap joins after 8 bars
    build = (await client.call("notes.get", {"track": 0, "arrangement_clip": 1}))["notes"]
    assert build and 36 not in {n["pitch"] for n in build}  # builds drop the kick
    drop = (await client.call("notes.get", {"track": 0, "arrangement_clip": 2}))["notes"]
    assert 36 in {n["pitch"] for n in drop}
    bass = [c["name"] for c in arrangement["tracks"][1]["clips"]]
    assert bass == ["Drop Bass", "Drop 2 Bass", "Outro Bass"]
    new_chords = live.on_main(lambda: [d.name for d in live.song.tracks[2].devices])
    assert new_chords == ["Wavetable"]


async def test_same_seed_same_song_and_variation_for_the_second_drop(client, live):
    _studio(live)
    server = build_server(client)
    first, second = await _plan(server), await _plan(server)
    assert first["notes"] == second["notes"]
    other = await _plan(server, seed=8)
    assert other["notes"] != first["notes"]


async def test_never_on_top_of_existing_clips(client, live):
    _studio(live)
    await client.call("arrangement.edit", {"actions": [{"action": "add_clip", "track": 0, "start": 0, "length": 32, "name": "Mine"}]})
    server = build_server(client)
    with pytest.raises(ToolError) as exc:
        await _plan(server, start_bar=1)
    assert "Mine" in str(exc.value) and "bar 9" in str(exc.value)
    preview = await _plan(server)  # default: after the last clip
    assert preview["from_bar"] == 9


async def test_lengths(client, live):
    _studio(live)
    server = build_server(client)
    radio = await _plan(server, length="radio")
    extended = await _plan(server, length="extended")
    standard = await _plan(server)
    assert radio["bars"] < standard["bars"] < extended["bars"]
    short = await _plan(server, minutes=2.5)  # 2.5 min at 120 BPM = 75 bars
    assert 60 <= short["bars"] <= 92


async def test_own_session_clip_for_a_role(client, live):
    _studio(live)
    await client.call("clip.create", {"track": 1, "slot": 0, "length": 16, "name": "My Bass"})
    server = build_server(client)
    preview = await _plan(server, clips=[{"role": "bass", "track": 1, "slot": 0}])
    await server.call_tool("apply_plan", {"plan_id": preview["plan_id"]})
    bass = (await client.call("arrangement.get", {"track": 1}))["tracks"][0]["clips"]
    assert {c["name"] for c in bass} == {"My Bass"} and len(bass) == 2 * 8 + 2  # 32-bar drops, the outro's first 8 bars, 4-bar loop


async def test_without_creating_tracks_parts_are_left_out(client, live):
    _studio(live)
    server = build_server(client)
    preview = await _plan(server, create_missing=False)
    assert set(preview["tracks"]) == {"drums", "bass"} and preview["warnings"]


async def test_tracks_changed_after_planning(client, live):
    _studio(live)
    server = build_server(client)
    preview = await _plan(server)
    await client.call("track.create", {"name": "Surprise"})
    with pytest.raises(ToolError) as exc:
        await server.call_tool("apply_plan", {"plan_id": preview["plan_id"]})
    assert "changed" in str(exc.value)


def test_every_template_is_whole_bars_and_uses_known_parts():
    for template in TEMPLATES.values():
        for length in ("radio", "standard", "extended"):
            for section in sized(template, length):
                assert section.bars % 4 == 0 and section.bars >= 4
                assert set(section.parts) <= {"drums", "bass", "chords", "lead"}


async def test_genre_loops_in_the_songs_key(client, live):
    _studio(live)
    server = build_server(client)
    major = await _plan(server)
    loops = {("Am", "F", "C", "G"), ("C", "G", "Am", "F"), ("C", "Am", "F", "G"), ("Dm", "G", "C", "Am")}
    main = tuple(c.split(" ")[0] for c in major["harmony"]["main"][:4])
    assert main in loops and major["harmony"]["break"] != major["harmony"]["main"]
    def a_minor():
        live.song.root_note, live.song.scale_name = 9, "Minor"
        live.song.scale_intervals = (0, 2, 3, 5, 7, 8, 10)

    live.on_main(a_minor)
    minor = await _plan(server)
    assert minor["harmony"]["main"][0].startswith("Am") or minor["harmony"]["main"][0].startswith("F")  # i or VI first


async def test_house_follows_the_recipe(client, live):
    _studio(live)
    server = build_server(client)
    preview = await _plan(server)
    await server.call_tool("apply_plan", {"plan_id": preview["plan_id"]})
    arrangement = await client.call("arrangement.get", {})
    clips = {c["name"]: c for t in arrangement["tracks"] for c in t["clips"]}
    assert clips["Intro Chords"]["start"] == 32.0  # the pad enters at bar 9 of the intro
    assert clips["Outro Bass"]["end"] - clips["Outro Bass"]["start"] == 32.0  # bass leaves the outro first

    async def notes(name):
        clip = clips[name]
        track = next(t["index"] for t in arrangement["tracks"] if any(c is clip or c == clip for c in t["clips"]))
        index = next(c["index"] for t in arrangement["tracks"] if t["index"] == track for c in t["clips"] if c["start"] == clip["start"])
        return (await client.call("notes.get", {"track": track, "arrangement_clip": index}))["notes"]

    build = await notes("Build Drums")
    assert max(n["start_time"] + n["duration"] for n in build) <= 31.0 + 1e-6  # a beat of silence before the drop
    bass = await notes("Drop Bass")
    assert all(28 <= n["pitch"] <= 39 for n in bass) and {round(n["start_time"] % 1, 2) for n in bass} == {0.5}  # offbeats, low
    lead = await notes("Drop Lead")
    assert 3 <= len(lead) / 32 <= 6  # a hook, not a stream of 16ths
    chords = await notes("Drop Chords")
    assert max(n["pitch"] for n in chords) < min(n["pitch"] for n in lead) + 6
    drop = await notes("Drop Drums")
    open_hat = [n for n in drop if n["pitch"] == 46]
    assert open_hat and min(n["start_time"] for n in open_hat) >= 64  # open hats join in the second half
