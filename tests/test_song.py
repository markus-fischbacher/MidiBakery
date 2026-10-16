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
        for name, note in (("Kick", 36), ("Snare", 38), ("Clap", 39), ("Closed Hat", 42), ("Open Hat", 46), ("Ride", 51)):
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


async def _song_notes(client, server, genre, **args):
    """Plan and apply a song; return {clip name: notes} (positions relative to each clip)."""
    preview = await _plan(server, genre=genre, **args)
    await server.call_tool("apply_plan", {"plan_id": preview["plan_id"]})
    arrangement = await client.call("arrangement.get", {})
    result = {}
    for track in arrangement["tracks"]:
        for clip in track["clips"]:
            notes = (await client.call("notes.get", {"track": track["index"], "arrangement_clip": clip["index"]}))["notes"]
            result[clip["name"]] = (clip, notes)
    return preview, result


def _minor(live):
    def setup():
        live.song.root_note, live.song.scale_name = 9, "Minor"
        live.song.scale_intervals = (0, 2, 3, 5, 7, 8, 10)

    live.on_main(setup)


async def test_peak_time_techno_follows_the_recipe(client, live):
    _studio(live)
    _minor(live)
    preview, clips = await _song_notes(client, build_server(client), "peak_time_techno")
    assert [s["name"] for s in preview["sections"]][:4] == ["Intro", "Groove", "Breakdown", "Peak"]
    kick = [n for n in clips["Peak Drums"][1] if n["pitch"] == 36 and n["velocity"] > 100]
    assert all(abs(n["start_time"] % 1) < 1e-6 for n in kick)  # straight kick, no swing
    bass = clips["Peak Bass"][1]
    assert all(abs(n["start_time"] % 1) > 0.2 for n in bass)  # the first 16th of each beat is left to the kick
    common = max(sum(1 for n in bass if n["pitch"] == p) for p in {n["pitch"] for n in bass})
    assert common / len(bass) >= 0.5 and all(36 <= n["pitch"] <= 59 for n in bass)  # mostly one note
    stabs = clips["Peak Chords"][1]
    by_time: dict[float, list[int]] = {}
    for n in stabs:
        by_time.setdefault(n["start_time"], []).append(n["pitch"])
    shapes = {tuple(p - min(ps) for p in sorted(ps)) for ps in by_time.values()}
    assert shapes == {(0, 3, 7), (0, 3, 7, 12)}  # one minor-triad shape moved as a block, root doubled up in every 2nd phrase
    rhythm = lambda first: tuple(sorted({round(t % 32, 2) for t in by_time if first <= t < first + 32}))  # noqa: E731
    assert rhythm(0) != rhythm(32)  # stabs change from one 8-bar phrase to the next
    roots = {min(ps) % 12 for ps in by_time.values()}
    assert len(roots) == 2  # home chord plus a two-chord shift
    acid = clips["Peak Lead"][1]
    assert all(48 <= n["pitch"] <= 62 for n in acid) and 8 <= len(acid) / 32 <= 12
    block = lambda first: [(round(n["start_time"] - first, 2), n["pitch"], n["velocity"], round(n["duration"], 2)) for n in acid if first <= n["start_time"] < first + 32]  # noqa: E731
    assert block(32) != block(64)  # the acid line moves one thing every 8 bars
    assert len(block(0)) < len([n for n in acid if 16 <= n["start_time"] < 32]) * 2  # each 16 bars start thinned out
    peak_2 = clips["Peak 2 Lead"][1]
    assert max(n["pitch"] for n in peak_2) > 62  # the last peak lifts the acid an octave in its second half
    ride = [n for n in clips["Peak Drums"][1] if n["pitch"] == 51 and n["duration"] < 1]  # not the crash accent on bar 1
    assert ride and min(n["start_time"] for n in ride) >= 64  # rides arrive in the second half of a peak


async def test_melodic_techno_has_an_arp_over_pads(client, live):
    _studio(live)
    _minor(live)
    _, clips = await _song_notes(client, build_server(client), "melodic_techno")
    pads = clips["Drop Chords"][1]
    assert min(n["duration"] for n in pads) >= 7.9  # one held chord per 2 bars
    arp = clips["Drop Lead"][1]
    assert 6 <= len(arp) / 32 <= 8 and all(60 <= n["pitch"] <= 84 for n in arp)


async def test_drum_and_bass_two_step_and_long_drops(client, live):
    _studio(live)
    _minor(live)
    preview, clips = await _song_notes(client, build_server(client), "drum_and_bass")
    assert {s["name"]: s["bars"] for s in preview["sections"]}["Drop"] == 64
    drop = [n for n in clips["Drop Drums"][1] if int(n["start_time"] // 4) % 8 != 7]  # leave out the fill bars
    kicks = sorted({round(n["start_time"] % 4, 2) for n in drop if n["pitch"] == 36})
    snares = sorted({round(n["start_time"] % 4, 2) for n in drop if n["pitch"] == 38 and n["velocity"] > 100})
    assert kicks == [0.0, 2.5] and snares == [1.0, 3.0]  # kick on 1 and 11, snare on 5 and 13
    build = clips["Build Drums"]
    assert build[0]["end"] - build[0]["start"] == 48  # drums out for the last 4 bars before the drop
    sub = clips["Drop Bass"][1]
    assert all(27 <= n["pitch"] <= 45 for n in sub)


async def test_trap_half_time_rolls_and_808(client, live):
    _studio(live)
    _minor(live)
    _, clips = await _song_notes(client, build_server(client), "trap")
    drop = clips["Drop Drums"][1]
    snares = {round(n["start_time"] % 4, 2) for n in drop if n["pitch"] == 38 and int(n["start_time"] // 4) % 8 != 7}
    assert 2.0 in snares and 1.0 not in snares and 3.0 not in snares  # half time: beat 3 only
    hats = sorted(n["start_time"] for n in drop if n["pitch"] == 42)
    gaps = {round(b - a, 3) for a, b in zip(hats, hats[1:])}
    assert 0.125 in gaps  # 1/32 rolls
    kicks = {n["start_time"] for n in drop if n["pitch"] == 36}
    bass = clips["Drop Bass"][1]
    assert sum(1 for n in bass if n["start_time"] in kicks) >= len(kicks) * 0.7  # an 808 under the kicks
    assert all(28 <= n["pitch"] <= 55 for n in bass)


async def test_a_lane_without_its_pad_does_not_double_another(client, live):
    def hats_only():
        rack = DrumRackDevice()
        for name, note in (("Kick", 36), ("Clap", 39), ("Closed Hat", 42)):
            rack.add_pad(name, note)
        live.song.tracks[0].devices.append(rack)

    live.on_main(hats_only)
    _, clips = await _song_notes(client, build_server(client), "peak_time_techno", create_missing=False)
    peak = clips["Peak Drums"][1]
    hats = [n["start_time"] for n in peak if n["pitch"] == 42]
    assert len(hats) == len(set(hats))  # the ride (no pad) did not land on the closed hat


async def test_a_new_song_starts_after_every_track_not_just_its_own(client, live):
    _studio(live)
    other = (await client.call("track.create", {"name": "Vocals"}))["track"]
    await client.call("arrangement.edit", {"actions": [{"action": "add_clip", "track": other, "start": 0, "length": 64}]})
    preview = await _plan(build_server(client), create_missing=False)
    assert preview["from_bar"] == 17  # after the Vocals clip, though plan_song does not use that track


async def test_no_ride_on_a_crash_when_the_kit_has_no_ride(client, live):
    def kit_808():
        rack = DrumRackDevice()
        for name, note in (("Bass Drum", 36), ("Hand Clap", 39), ("Closed Hi Hat", 42), ("Open Hi Hat", 46), ("Cymbal", 49), ("Maracas", 48)):
            rack.add_pad(name, note)
        live.song.tracks[0].devices.append(rack)

    live.on_main(kit_808)
    _, clips = await _song_notes(client, build_server(client), "peak_time_techno", create_missing=False)
    cymbal = [n for n in clips["Peak Drums"][1] if n["pitch"] == 49]
    assert len(cymbal) <= 1  # at most the crash accent on bar 1, never a ride pattern on the crash
