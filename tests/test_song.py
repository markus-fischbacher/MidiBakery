"""Whole songs from genre templates: plan_song + apply_plan against the fake LOM."""

import json

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from fake_song import DrumRackDevice
from midibakery.compose.rollback import batch_steps
from midibakery.compose.song import _sweep
from midibakery.compose.structures import TEMPLATES, bar_grid, from_reference, parse_segments, sized
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
    return _payload(await server.call_tool("plan_song", {"genre": "house", "seed": 7, "fx": False, "sidechain": False, **args}))  # test_fx_*, test_sidechain_*


async def test_house_song_on_found_and_new_tracks(client, live):
    _studio(live)
    server = build_server(client)
    preview = await _plan(server)
    assert preview["genre"] == "House" and preview["from_bar"] == 1 and preview["bars"] == 128
    assert [s["name"] for s in preview["sections"]] == ["Intro", "Build", "Drop", "Break", "Build 2", "Drop 2", "Outro"]
    assert preview["tracks"]["drums"] == {"track": 0, "name": "Drums", "automation": "Auto Filter High-pass cutoff (new device)"} and preview["tracks"]["bass"]["track"] == 1
    assert preview["tracks"]["chords"]["new"] and preview["tracks"]["chords"]["device"] == "106 Organ"
    assert preview["tracks"]["lead"]["device"] == "Basic Pluck Keys"
    assert not (await client.call("arrangement.get", {}))["tracks"][0]["clips"]  # a preview changes nothing

    applied = _payload(await server.call_tool("apply_plan", {"plan_id": preview["plan_id"]}))
    assert applied["clips"] == preview["clips"] and [t["name"] for t in applied["new_tracks"]] == ["Chords", "Lead"]
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
    assert new_chords == ["106 Organ", "Auto Filter"]  # the genre's preset, then the filter for the sweeps
    assert live.on_main(lambda: live.song.view.selected_track is live.song.tracks[0])  # loading kept the selection


async def test_new_drum_track_gets_the_genre_kit_and_its_pads(client, live):
    server = build_server(client)
    preview = await _plan(server)
    assert preview["tracks"]["drums"]["device"] == "909 Core Kit" and not preview["warnings"]
    applied = _payload(await server.call_tool("apply_plan", {"plan_id": preview["plan_id"]}))
    assert [t["device"] for t in applied["new_tracks"]] == ["909 Core Kit", "Basic FM House Bass", "106 Organ", "Basic Pluck Keys"]
    assert "7 undo step(s)" in applied["undo"]  # tracks+returns, the mix after them, one per sound, clips
    drums = next(t["track"] for t in applied["new_tracks"] if t["name"] == "Drums")
    drop = (await client.call("notes.get", {"track": drums, "arrangement_clip": 2}))["notes"]
    pitches = {n["pitch"] for n in drop}
    assert 48 in pitches and 49 not in pitches  # the drop's crash moved from GM 49 to the kit's Crash pad


async def test_sounds_off_or_missing_keep_native_devices(client, live):
    server = build_server(client)
    preview = await _plan(server, sounds=False)
    assert preview["tracks"]["chords"]["device"] == "Wavetable" and "empty Drum Rack" in preview["warnings"][0]
    trap = _payload(await server.call_tool("plan_song", {"genre": "trap", "seed": 1}))  # its sounds are not in the fake browser
    applied = _payload(await server.call_tool("apply_plan", {"plan_id": trap["plan_id"]}))
    assert [t["device"] for t in applied["new_tracks"]] == ["Drum Rack", "Operator", "Drift", "Wavetable", "Riser Basic", "Sub 808 Pitch Boom", "Operator"]
    assert len(applied["warnings"]) == 4 and "808 Core Kit could not be loaded" in applied["warnings"][0]


async def test_mix_scaffold_returns_sends_and_levels(client, live):
    _studio(live)
    server = build_server(client)
    preview = await _plan(server)
    assert preview["mix"]["returns"] == {
        "reverb": "return index 0 'Reverb' (new, 1.8 s)",
        "delay": "return index 1 'Delay' (new, 3/16, feedback 35 %)",
    }
    assert preview["mix"]["levels"]["chords"] == "fader -12 dB, reverb -14 dB, delay -22 dB"
    assert preview["mix"]["levels"]["drums"] == "reverb -24 dB"  # an existing track keeps its fader
    assert "bass" not in preview["mix"]["levels"]
    applied = _payload(await server.call_tool("apply_plan", {"plan_id": preview["plan_id"]}))
    assert applied["mix"] == preview["mix"] and applied["undo"].startswith("5 undo step(s)")  # tracks+returns, the mix after them, 2 sounds, clips
    mixer = await client.call("mixer.get", {})
    assert [(r["name"], r["devices"]) for r in mixer["returns"]] == [("Reverb", ["Reverb"]), ("Delay", ["Delay"])]
    reverb = {p["name"]: p["value"] for p in (await client.call("device.params", {"return_track": 0, "device": 0}))["parameters"]}
    assert reverb["Dry/Wet"] == 1.0 and reverb["Decay Time"] == 0.3852  # 1.8 s
    delay = {p["name"]: p["value"] for p in (await client.call("device.params", {"return_track": 1, "device": 0}))["parameters"]}
    assert (delay["Dry/Wet"], delay["L 16th"], delay["Feedback"]) == (1.0, 2.0, 0.3684)  # 3/16, 35 %
    tracks = {t["name"]: t for t in mixer["tracks"]}
    chords = tracks["Chords"]
    assert chords["volume"]["display"] == "-12.0 dB" and [s["display"] for s in chords["sends"]] == ["-14.0 dB", "-22.0 dB"]
    assert tracks["Drums"]["volume"]["display"] == "0.0 dB" and [s["display"] for s in tracks["Drums"]["sends"]] == ["-24.0 dB", "-inf dB"]
    assert [s["display"] for s in tracks["Bass"]["sends"]] == ["-inf dB", "-inf dB"]


def test_sweeps_with_curves_and_waves():
    envelope = _sweep("20:4,20>20000~exp:4,400>4000~sine/2", 16, 0, 64.0, 4.0, 20000.0)
    assert envelope["points"] == [[0.0, 0.0], [16.0, 0.0]]
    curve, wave = envelope["shapes"]
    assert curve == {"type": "exp", "start": 16.0, "length": 16.0, "from_value": 0.0, "to_value": 1.0}
    assert wave["type"] == "sine" and wave["start"] == 32.01 and wave["period"] == 8.0  # a jump from 20 kHz down to 400 Hz
    assert _sweep(None, 8, 0, 32.0, 4.0, 20.0) == {"points": [[0.0, 0.0]]}


def test_live_closes_the_undo_step_at_a_new_return():
    ops = ["track.create", "return.create", "device.set_param", "return.create", "mixer.set"]
    assert [batch_steps(ops, done) for done in range(6)] == [0, 1, 1, 2, 1, 2]


async def test_the_sets_own_reverb_is_used_and_left_as_it_is(client, live):
    _studio(live)
    await client.call("return.create", {"name": "Hall", "device": "Reverb"})
    server = build_server(client)
    preview = await _plan(server)
    assert preview["mix"]["returns"]["reverb"] == "return index 0 'Hall' (the Set's)"
    assert preview["mix"]["returns"]["delay"] == "return index 1 'Delay' (new, 3/16, feedback 35 %)"
    assert "drums" not in preview["mix"]["levels"]  # its own track, its own return: untouched
    await client.call("return.create", {"name": "Other"})
    with pytest.raises(ToolError, match="Return tracks changed"):
        await server.call_tool("apply_plan", {"plan_id": preview["plan_id"]})
    preview = await _plan(server, mix=False)
    assert "mix" not in preview
    applied = _payload(await server.call_tool("apply_plan", {"plan_id": preview["plan_id"]}))
    assert "mix" not in applied and len((await client.call("mixer.get", {}))["returns"]) == 2


async def test_fx_riser_before_each_drop_and_an_impact_on_it(client, live):
    _studio(live)
    server = build_server(client)
    preview = await _plan(server, fx=True)
    plays = {s["name"]: s["plays"] for s in preview["sections"]}
    assert plays["Build"]["riser"] == plays["Build 2"]["riser"] == "last 8 bars" and "riser" not in plays["Break"]
    assert plays["Drop"]["impact"] == plays["Drop 2"]["impact"] == "first beat" and "impact" not in plays["Outro"]
    assert preview["tracks"]["riser"]["device"] == "Riser Basic" and preview["tracks"]["impact"]["device"] == "Sub 808 Pitch Boom"
    assert preview["mix"]["levels"]["riser"] == "fader -12 dB, reverb -12 dB, delay -22 dB"
    applied = _payload(await server.call_tool("apply_plan", {"plan_id": preview["plan_id"]}))
    assert "warnings" not in applied
    tracks = {t["name"]: t["index"] for t in (await client.call("tracks.list", {}))["tracks"]}
    arrangement = {t["index"]: t["clips"] for t in (await client.call("arrangement.get", {}))["tracks"]}
    risers = [(c["name"], c["start"], c["end"]) for c in arrangement[tracks["Riser"]]]
    assert risers == [("Build Riser", 64.0, 95.0), ("Build 2 Riser", 288.0, 319.0)]  # up to the beat of silence
    impacts = [(c["name"], c["start"]) for c in arrangement[tracks["Impact"]]]
    assert impacts == [("Drop Impact", 96.0), ("Drop 2 Impact", 320.0)]

    def swell():
        track = live.song.tracks[tracks["Riser"]]
        clip = sorted(track.arrangement_clips, key=lambda c: c.start_time)[0]
        cutoff = clip.envelopes[id(track.devices[0].parameters[1])]  # the Filter Cutoff macro
        volume = clip.envelopes[id(track.mixer_device.volume)]
        return [cutoff.value_at_time(t) for t in (1, 16, 30)], [volume.value_at_time(t) for t in (1, 16, 30)]

    cutoff, volume = live.on_main(swell)
    assert cutoff[0] < 30 < cutoff[1] < cutoff[2] and cutoff[1] - cutoff[0] < cutoff[2] - cutoff[1]  # 0-127, slow first
    assert volume[0] < volume[1] < volume[2]


async def test_fx_need_their_presets(client, live):
    server = build_server(client)
    melodic = _payload(await server.call_tool("plan_song", {"genre": "melodic_techno", "seed": 2}))  # Hyper Riser: not in the fake browser
    applied = _payload(await server.call_tool("apply_plan", {"plan_id": melodic["plan_id"]}))
    assert any("Hyper Riser could not be loaded" in w and "stays empty" in w for w in applied["warnings"])
    arrangement = {t["name"]: t["clips"] for t in (await client.call("arrangement.get", {}))["tracks"]}
    assert arrangement["Riser"] == [] and len(arrangement["Impact"]) == 2
    plain = await _plan(server, fx=True, sounds=False)
    assert "riser" not in plain["tracks"] and any("No riser or impact" in w for w in plain["warnings"])


async def test_fx_on_the_riser_track_of_an_earlier_song(client, live):
    _studio(live)
    server = build_server(client)
    first = await _plan(server, fx=True)
    await server.call_tool("apply_plan", {"plan_id": first["plan_id"]})
    second = await _plan(server, fx=True, seed=8)
    assert second["tracks"]["riser"]["name"] == "Riser" and "new" not in second["tracks"]["riser"]
    await server.call_tool("apply_plan", {"plan_id": second["plan_id"]})

    def envelopes():
        track = next(t for t in live.song.tracks if t.name == "Riser")
        return [len(c.envelopes) for c in sorted(track.arrangement_clips, key=lambda c: c.start_time)]

    assert live.on_main(envelopes) == [2, 2, 2, 2]  # Riser Basic is on the track: the macro swells too


async def test_fx_on_a_track_called_riser(client, live):
    _studio(live)
    await client.call("track.create", {"kind": "midi", "name": "Riser"})
    server = build_server(client)
    preview = await _plan(server, fx=True)
    assert preview["tracks"]["riser"] == {"track": 2, "name": "Riser"}
    applied = _payload(await server.call_tool("apply_plan", {"plan_id": preview["plan_id"]}))
    assert [t["name"] for t in applied["new_tracks"]] == ["Chords", "Lead", "Impact"]

    def riser():
        track = live.song.tracks[2]
        clips = sorted(track.arrangement_clips, key=lambda c: c.start_time)
        return [c.name for c in clips], [len(c.envelopes) for c in clips], track.mixer_device.volume.value

    names, envelopes, fader = live.on_main(riser)
    assert names == ["Build Riser", "Build 2 Riser"] and envelopes == [1, 1]  # its own sound: only the volume swells
    assert fader == 0.85  # an existing track keeps its fader


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


def _chord_clip(length, chords):
    """Notes for a clip: one (pitches) chord per 4 beats."""
    return [{"pitch": p, "start_time": 4.0 * i, "duration": 4.0, "velocity": 90} for i, pitches in enumerate(chords) for p in pitches]


async def _clip_with(client, length, notes, **fields):
    await client.call("clip.create", {"track": 1, "slot": 0, "length": length, "name": "Mine"})
    if notes:
        await client.call("notes.apply", {"track": 1, "slot": 0, "add": notes})


async def _drop_clips(client, track, start=96.0, end=224.0):
    return sorted(((c["start"], c["end"]) for c in (await client.call("arrangement.get", {"track": track}))["tracks"][0]["clips"]
                   if c["start"] >= start and c["end"] <= end))


async def test_copied_chord_clip_sets_the_harmony_in_every_section_including_breaks(client, live):
    _studio(live)
    # D major, Bb major, F major, A major: nothing like the genre's loops; D and A are outside C major
    await _clip_with(client, 16, _chord_clip(16, [(50, 54, 57), (46, 50, 53), (53, 57, 60), (57, 61, 64)]))
    server = build_server(client)
    preview = await _plan(server, roles={"chords": 1}, clips=[{"role": "chords", "track": 1, "slot": 0}])
    assert preview["harmony"]["main"][:4] == ["D", "Bb", "F (IV)", "A"] or preview["harmony"]["main"][:4] == ["D", "A#", "F (IV)", "A"]
    assert preview["harmony"]["break"] == preview["harmony"]["main"]  # the break follows the copied chords too
    assert not any("progression wins" in w for w in preview["warnings"])


async def test_given_progression_wins_over_a_copied_chord_clip_and_says_so(client, live):
    _studio(live)
    await _clip_with(client, 16, _chord_clip(16, [(50, 54, 57), (46, 50, 53), (53, 57, 60), (57, 61, 64)]))
    server = build_server(client)
    preview = await _plan(server, roles={"chords": 1}, progression="C G Am F", clips=[{"role": "chords", "track": 1, "slot": 0}])
    assert preview["harmony"]["main"][:4] == ["C (I)", "G (V)", "Am (vi)", "F (IV)"]
    assert any("progression wins" in w for w in preview["warnings"])


async def test_silent_copied_chord_clip_is_reported_not_guessed(client, live):
    _studio(live)
    await _clip_with(client, 16, [])
    server = build_server(client)
    preview = await _plan(server, roles={"chords": 1}, clips=[{"role": "chords", "track": 1, "slot": 0}])
    assert any("no confident chord" in w for w in preview["warnings"])


async def test_silent_bar_in_a_copied_chord_clip_is_listed(client, live):
    _studio(live)
    await _clip_with(client, 16, _chord_clip(16, [(48, 52, 55), (), (53, 57, 60), (55, 59, 62)]))
    server = build_server(client)
    preview = await _plan(server, roles={"chords": 1}, clips=[{"role": "chords", "track": 1, "slot": 0}])
    assert any("no confident chord in segment(s) 2" in w for w in preview["warnings"])
    assert preview["harmony"]["main"][:2] == ["C (I)", "C (I)"]


async def test_reused_clip_on_another_track_than_the_role_is_refused(client, live):
    _studio(live)
    await client.call("clip.create", {"track": 1, "slot": 0, "length": 16})
    server = build_server(client)
    with pytest.raises(ToolError) as exc:
        await _plan(server, roles={"bass": 0}, clips=[{"role": "bass", "track": 1, "slot": 0}])
    assert "roles.bass" in str(exc.value)
    assert not (await client.call("arrangement.get", {}))["tracks"][1]["clips"]  # nothing written


async def test_reused_clip_is_cut_to_fill_the_last_span_without_changing_the_source(client, live):
    _studio(live)
    notes = [{"pitch": 40 + i, "start_time": float(i), "duration": 1.0, "velocity": 100} for i in range(20)]
    await _clip_with(client, 20, notes)
    server = build_server(client)
    preview = await _plan(server, clips=[{"role": "bass", "track": 1, "slot": 0}])
    assert preview["reuse"]["bass"]["clip_beats"] == 20 and preview["reuse"]["bass"]["uncovered_beats"] == 0
    assert preview["reuse"]["bass"]["fragments"] > 0
    assert any("clips.bass" in w and "is cut to" in w for w in preview["warnings"])
    await server.call_tool("apply_plan", {"plan_id": preview["plan_id"]})
    spans = await _drop_clips(client, 1)
    assert spans[:6] == [(96.0 + 20 * k, 116.0 + 20 * k) for k in range(6)]  # six whole copies...
    assert spans[6] == (216.0, 224.0)  # ...then a cut ending exactly where the drop ends
    cut = next(c for c in (await client.call("arrangement.get", {"track": 1}))["tracks"][0]["clips"] if c["start"] == 216.0)
    pitches = [n["pitch"] for n in (await client.call("notes.get", {"track": 1, "arrangement_clip": cut["id"]}))["notes"]] if "id" in cut else None
    if pitches is not None:
        assert sorted(pitches) == list(range(40, 48))
    source = await client.call("clip.get", {"track": 1, "slot": 0})
    assert source["length"] == 20 and len((await client.call("notes.get", {"track": 1, "slot": 0}))["notes"]) == 20


async def test_reused_clip_longer_than_a_part_is_cut_to_it(client, live):
    _studio(live)
    notes = [{"pitch": 40, "start_time": float(i * 8), "duration": 2.0, "velocity": 100} for i in range(32)]
    await _clip_with(client, 256, notes)
    server = build_server(client)
    preview = await _plan(server, clips=[{"role": "bass", "track": 1, "slot": 0}])
    assert preview["reuse"]["bass"]["copies"] >= 0 and preview["reuse"]["bass"]["uncovered_beats"] == 0
    await server.call_tool("apply_plan", {"plan_id": preview["plan_id"]})
    spans = await _drop_clips(client, 1)
    assert spans == [(96.0, 224.0)]  # exactly as long as the drop


async def test_reused_clip_loop_window_sets_the_cut_notes(client, live):
    _studio(live)
    notes = [{"pitch": 40 + i, "start_time": 4.0 + i, "duration": 1.0, "velocity": 100} for i in range(20)]
    await _clip_with(client, 24, notes)
    await client.call("clip.set", {"track": 1, "slot": 0, "loop_end": 24.0})
    await client.call("clip.set", {"track": 1, "slot": 0, "loop_start": 4.0})  # a 20-beat window
    live.on_main(lambda: setattr(live.song.tracks[1].clip_slots[0].clip, "start_marker", 4.0))
    server = build_server(client)
    preview = await _plan(server, clips=[{"role": "bass", "track": 1, "slot": 0}])
    assert preview["reuse"]["bass"]["clip_beats"] == 20 and preview["reuse"]["bass"]["fragments"] > 0
    await server.call_tool("apply_plan", {"plan_id": preview["plan_id"]})
    spans = await _drop_clips(client, 1)
    assert spans[-1] == (216.0, 224.0)


async def test_reused_clip_playing_from_inside_its_loop_is_refused_when_it_needs_a_cut(client, live):
    _studio(live)
    await _clip_with(client, 20, [{"pitch": 40, "start_time": 0.0, "duration": 1.0, "velocity": 100}])
    live.on_main(lambda: setattr(live.song.tracks[1].clip_slots[0].clip, "start_marker", 4.0))
    server = build_server(client)
    with pytest.raises(ToolError) as exc:
        await _plan(server, clips=[{"role": "bass", "track": 1, "slot": 0}])
    assert "away from its loop start" in str(exc.value)
    assert not (await client.call("arrangement.get", {"track": 1}))["tracks"][0]["clips"]


async def test_reused_clip_with_envelopes_is_refused_when_it_needs_a_cut(client, live):
    _studio(live)
    await _clip_with(client, 20, [{"pitch": 40, "start_time": 0.0, "duration": 1.0, "velocity": 100}])
    live.on_main(lambda: live.song.tracks[1].clip_slots[0].clip.envelopes.update({1: object()}))
    server = build_server(client)
    with pytest.raises(ToolError) as exc:
        await _plan(server, clips=[{"role": "bass", "track": 1, "slot": 0}])
    assert "envelopes" in str(exc.value)
    # a clip that divides every span needs no cut, so it is still copied
    await client.call("clip.delete", {"track": 1, "slot": 0})
    await client.call("clip.create", {"track": 1, "slot": 0, "length": 16})
    live.on_main(lambda: live.song.tracks[1].clip_slots[0].clip.envelopes.update({1: object()}))
    assert (await _plan(server, clips=[{"role": "bass", "track": 1, "slot": 0}]))["reuse"]["bass"]["fragments"] == 0


async def test_reused_clip_notes_changed_after_planning(client, live):
    _studio(live)
    await _clip_with(client, 16, [{"pitch": 40, "start_time": 0.0, "duration": 1.0, "velocity": 100}])
    server = build_server(client)
    preview = await _plan(server, clips=[{"role": "bass", "track": 1, "slot": 0}])
    await client.call("notes.apply", {"track": 1, "slot": 0, "add": [{"pitch": 43, "start_time": 2.0, "duration": 1.0}]})
    with pytest.raises(ToolError) as exc:
        await server.call_tool("apply_plan", {"plan_id": preview["plan_id"]})
    assert "plan again" in str(exc.value)
    assert not (await client.call("arrangement.get", {"track": 1}))["tracks"][0]["clips"]


async def test_reused_clip_changed_after_planning(client, live):
    _studio(live)
    await client.call("clip.create", {"track": 1, "slot": 0, "length": 16})
    server = build_server(client)
    preview = await _plan(server, clips=[{"role": "bass", "track": 1, "slot": 0}])
    await client.call("clip.delete", {"track": 1, "slot": 0})
    await client.call("clip.create", {"track": 1, "slot": 0, "length": 12})
    with pytest.raises(ToolError) as exc:
        await server.call_tool("apply_plan", {"plan_id": preview["plan_id"]})
    assert "plan again" in str(exc.value)
    assert not (await client.call("arrangement.get", {"track": 1}))["tracks"][0]["clips"]


async def test_named_progression_keeps_its_chord_quality_under_genre_sevenths(client, live):
    _studio(live)

    def minor():
        live.song.root_note, live.song.scale_name = 9, "Minor"
        live.song.scale_intervals = (0, 2, 3, 5, 7, 8, 10)

    live.on_main(minor)
    server = build_server(client)
    preview = await _plan(server, progression="Am F E G")
    assert preview["harmony"]["main"][:4] == ["Am (i)", "F (VI)", "E (V)", "G (VII)"]  # what plays: no Em7, no Fmaj7
    chords = await client.call("arrangement.get", {})
    assert not chords["tracks"][0]["clips"]  # a preview changes nothing


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
                for key, spec in section.sweeps.items():
                    role, _, target = key.partition(".")
                    assert role in template.style.filters and role in section.parts and target in ("", "res"), (template.genre, section.name, key)
                    low, high = (0, 100) if target else (20, 20000)
                    for name, _, _ in parse_segments(spec, section.bars):
                        values, _, shape = name.partition("~")
                        assert all(v == "-" or low <= float(v) <= high for v in values.split(">")), spec
                        assert shape.partition("/")[0] in ("", "exp", "log", "sine", "triangle", "saw", "square"), spec


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
    assert 2 <= len(lead) / 32 <= 6  # a hook, not a stream of 16ths (every 4th bar rests for an answer)
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
    assert [s["name"] for s in preview["sections"]][:5] == ["Intro", "Groove", "Lift", "Peak", "Breakdown"]
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
    # After the references: tension by taking things away.
    assert not [n for n in bass if 60 <= n["start_time"] < 64]  # bar 16 of the peak: a breath without bass ...
    assert not [n for n in kick if 60 <= n["start_time"] < 64]  # ... and without kick
    assert [n for n in bass if 56 <= n["start_time"] < 60]
    drive = clips["Peak 2 Drums"][1]
    assert not [n for n in drive if n["start_time"] < 32 and n["pitch"] == 42]  # hats come in late after the breakdown
    assert [n for n in drive if n["start_time"] >= 32 and n["pitch"] == 42]
    rumble = clips["Breakdown Bass"][1]
    assert rumble and all(n["pitch"] < 40 and n["velocity"] < 70 for n in rumble)
    accents = {n["start_time"] for n in clips["Groove Chords"][1]}
    assert accents and all(t % 32 < 4 for t in accents) and len(accents) == 2  # one hit opens each 8-bar phrase
    rhythm = lambda first: tuple(sorted({round(t % 32, 2) for t in by_time if first <= t < first + 32}))  # noqa: E731
    assert rhythm(0) != rhythm(32)  # stabs change from one 8-bar phrase to the next
    roots = {min(ps) % 12 for ps in by_time.values()}
    assert len(roots) == 2  # home chord plus a two-chord shift
    acid = clips["Peak Lead"][1]
    assert all(48 <= n["pitch"] <= 62 for n in acid) and 6 <= len(acid) / 32 <= 12
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
    assert 4 <= len(arp) / 32 <= 8 and all(60 <= n["pitch"] <= 84 for n in arp)
    # the arp plays through 3 bars of each phrase and rests in the 4th: room for a counter melody
    assert not [n for n in arp if n["start_time"] % 16 >= 12] and all(any(p * 16 <= n["start_time"] < p * 16 + 12 for n in arp) for p in range(8))


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


async def test_peak_time_sweeps_auto_filters_clip_by_clip(client, live):
    _studio(live)
    _minor(live)
    preview, clips = await _song_notes(client, build_server(client), "peak_time_techno")
    assert preview["tracks"]["drums"]["automation"] == "Auto Filter High-pass cutoff (new device)"
    assert preview["tracks"]["lead"]["automation"] == "Auto Filter Low-pass cutoff and resonance"

    def read():
        out = {}
        for track in live.song.tracks:
            filters = [d for d in track.devices if d.class_name == "AutoFilter2"]
            if not filters:
                continue
            params = {p.name: p for p in filters[-1].parameters}
            freq, kind = params["Frequency"], params["Filter Type"]
            out[track.name] = (kind.value, {c.name: c.envelopes.get(id(freq)) for c in track.arrangement_clips})
        return {name: (kind, {clip: [env.value_at_time(t) for t in (0, 32, 60)] if env else None for clip, env in envs.items()}) for name, (kind, envs) in out.items()}

    tracks = live.on_main(read)
    kind, drums = tracks["Drums"]
    assert kind == 1.0  # High-pass
    assert all(values is not None for values in drums.values())  # every clip resets the filter
    assert drums["Lift Drums"][0] == 0.0 and drums["Lift Drums"][2] == pytest.approx(0.36, abs=0.03)  # 20 Hz -> ~250 Hz before the peak
    assert drums["Peak Drums"] == [0.0, 0.0, 0.0]  # the kick slams back in
    kind, lead = tracks["Lead"]
    assert kind == 0.0 and lead["Peak Lead"][0] < lead["Peak Lead"][1] < lead["Peak Lead"][2]  # the acid opens over the peak


async def test_an_existing_auto_filter_is_reused(client, live):
    _studio(live)
    live.on_main(lambda: live.song.tracks[0].insert_device("Auto Filter", 1))
    preview = await _plan(build_server(client), genre="peak_time_techno", create_missing=False)
    assert preview["tracks"]["drums"]["automation"] == "Auto Filter High-pass cutoff"
    assert any("Auto Filter is set to High-pass" in w for w in preview["warnings"])


async def test_an_unswept_role_keeps_an_earlier_songs_filter_open(client, live):
    _studio(live)
    live.on_main(lambda: live.song.tracks[1].insert_device("Auto Filter", 0))  # e.g. left by a Peak-Time song
    preview = await _plan(build_server(client), create_missing=False)  # House sweeps no bass
    assert preview["tracks"]["bass"]["automation"] == "Auto Filter Low-pass cutoff"


class _FailingEdit:
    """The bridge, but the song's clip edit breaks after its first clip."""

    def __init__(self, client):
        self._client = client

    def __getattr__(self, name):
        return getattr(self._client, name)

    async def call(self, op, params=None, **kwargs):
        if op == "arrangement.edit":
            params = {"actions": params["actions"][:1] + [{"action": "add_clip", "track": 99, "start": 0, "length": 4}]}
        return await self._client.call(op, params, **kwargs)


async def test_a_failed_apply_takes_back_tracks_and_clips(client, live):
    _studio(live)
    server = build_server(_FailingEdit(client))
    preview = await _plan(server, set_tempo=True)
    before = live.on_main(lambda: live.song.undo_calls)
    with pytest.raises(ToolError) as exc:
        await server.call_tool("apply_plan", {"plan_id": preview["plan_id"]})
    assert "were undone, Live is unchanged" in str(exc.value)
    assert live.on_main(lambda: live.song.undo_calls) - before == 6  # the clip already written, the tempo, two presets, the new tracks and returns (2 steps in Live)


class _FailingLocators(_FailingEdit):
    async def call(self, op, params=None, **kwargs):
        if op == "arrangement.locators" and len(params["actions"]) > 1:
            params = {"actions": params["actions"][:2] + [{"action": "delete_locator", "time": 9999}]}
        return await self._client.call(op, params, **kwargs)


async def test_failing_locators_keep_the_song_and_none_of_the_locators(client, live):
    _studio(live)
    server = build_server(_FailingLocators(client))
    preview = await _plan(server)
    result = _payload(await server.call_tool("apply_plan", {"plan_id": preview["plan_id"]}))
    assert result["locators"].startswith("not set: No locator at beat 9999")
    assert result["clips"] > 0 and (await client.call("arrangement.get", {}))["locators"] == []


async def test_songs_need_four_four(client, live):
    _studio(live)
    live.on_main(lambda: setattr(live.song, "signature_numerator", 3))
    with pytest.raises(ToolError) as exc:
        await _plan(build_server(client))
    assert "needs 4/4" in str(exc.value)


def test_shorter_and_longer_songs_move_the_section_borders():
    radio = {s.name: s for s in sized(TEMPLATES["peak_time_techno"], "radio")}
    assert radio["Intro"].bars == 16 and radio["Intro"].parts["drums"] == "kick_hats:8,groove"  # the groove still comes in
    assert radio["Breakdown"].parts["lead"] == "-:8,tease:3"  # the hook still hints before the peak
    extended = {s.name: s for s in sized(TEMPLATES["peak_time_techno"], "extended")}
    assert extended["Outro"].parts["drums"] == "groove:48,kick_hats:16,sparse"
    house = {s.name: s for s in sized(TEMPLATES["house"], minutes=3)}
    for section in house.values():
        for spec in (*section.parts.values(), *section.sweeps.values()):
            assert sum(length for _, _, length in parse_segments(spec, section.bars)) <= section.bars


def test_throw_points_hit_the_last_beat_of_every_phrase():
    from midibakery.compose.song import THROW_DB, _throw_points

    points = _throw_points(16, 0, 16, 4.0, -20.0)
    assert points[0] == [0.0, -20.0]
    assert [t for t, v in points if v == THROW_DB] == [31.0, 31.99, 63.0, 63.99]  # bars 8 and 16
    assert points[-1] == [64.0, -20.0]
    assert _throw_points(16, 8, 16, 4.0, -20.0)[1:] == [[30.99, -20.0], [31.0, THROW_DB], [31.99, THROW_DB], [32.0, -20.0]]  # a clip from bar 9


async def test_throws_and_resonance_ride_on_their_sections(client, live):
    _studio(live)
    _minor(live)
    preview, _ = await _song_notes(client, build_server(client), "peak_time_techno")
    chords = preview["tracks"]["chords"]
    assert "groove, break" in chords["throws"] and preview["tracks"]["lead"]["automation"].endswith("and resonance")

    def read():
        out = {}
        for track in live.song.tracks:
            send = track.mixer_device.sends[1] if len(track.mixer_device.sends) > 1 else None
            res = next((p for d in track.devices if d.class_name == "AutoFilter2" for p in d.parameters if p.name == "Resonance"), None)
            out[track.name] = {c.name: (c.envelopes.get(id(send)), c.envelopes.get(id(res))) for c in track.arrangement_clips}
        return out

    tracks = live.on_main(read)
    lead = next(v for k, v in tracks.items() if k.endswith("Lead"))
    assert all(res is not None for _, res in lead.values())  # every lead clip resets the resonance
    chord = next(v for k, v in tracks.items() if k.endswith("Chords"))
    thrown = sorted(name for name, (send, _) in chord.items() if send is not None)
    assert thrown and all(name.split(" ")[0] in ("Groove", "Breakdown") for name in thrown), thrown


async def test_a_kit_with_only_a_kick_gets_no_snare_fills(client, live):
    def setup():
        kit = DrumRackDevice()
        kit.add_pad("Kick", 36)
        live.song.tracks[0].devices.append(kit)

    live.on_main(setup)
    preview = await _plan(build_server(client), genre="drum_and_bass", seed=3, create_missing=False)
    assert preview["tracks"]["drums"]["track"] == 0


# As the Reference Analyzer device writes it (Katoff - The Signal, shortened): 152 bars at 124 BPM.
REFERENCE = {
    "name": "Katoff - The Signal", "file": "/x/Katoff - The Signal.mp3", "track": "3-Katoff", "analyzed": "2026-10-16T22:23:19Z",
    "tempo": 124, "key": "D# minor?", "genre": "auto", "bars": 152,
    "sections": [{"name": name, "kind": kind, "start_bar": start, "bars": bars, "kick": 1, "elements": ["kick"]} for name, kind, start, bars in (
        ("Intro", "intro", 1, 16), ("Drop", "drop", 17, 8), ("Groove", "groove", 25, 24), ("Break", "break", 49, 44),
        ("Drop 2", "drop", 93, 32), ("Groove 2", "groove", 125, 24), ("Outro", "outro", 149, 4))],
}


@pytest.fixture
def references(tmp_path, monkeypatch):
    monkeypatch.setenv("MIDIBAKERY_HOME", str(tmp_path))
    (tmp_path / "references").mkdir()
    (tmp_path / "references" / "katoff.json").write_text(json.dumps(REFERENCE))


def test_reference_sections_snap_to_the_genre_grid():
    template = TEMPLATES["peak_time_techno"]
    sections = from_reference(template, REFERENCE["sections"])
    assert [(s.name, s.kind, s.bars) for s in sections] == [
        ("Intro", "intro", 16), ("Drop", "drop", 8), ("Groove", "groove", 24), ("Break", "break", 48),
        ("Drop 2", "drop", 32), ("Groove 2", "groove", 24), ("Outro", "outro", 8)]
    # The n-th section of a kind plays the template's n-th one: Drop 2 is Peak 2, Groove 2 the stripped part.
    assert sections[4].parts["drums"] == "drive:8,full" and sections[4].variation == 1
    assert sections[5].parts["drums"].startswith("kick_only") and sections[5].variation == 1
    assert sections[0].parts["drums"] == "kick_hats:8,groove"  # resized from the template's 32-bar intro

    dnb = from_reference(TEMPLATES["drum_and_bass"], REFERENCE["sections"])
    assert bar_grid(TEMPLATES["drum_and_bass"]) == 16 and all(s.bars % 16 == 0 for s in dnb)
    assert [s.kind for s in dnb][2] == "drop"  # D&B has no groove: the drop plays
    assert sum(s.bars for s in dnb) == 160  # borders snap, so the total stays near the reference's 152


async def test_plan_song_follows_a_reference(client, live, references):
    _studio(live)
    server = build_server(client)
    preview = await _plan(server, genre="peak_time_techno", reference="signal", minutes=3)
    assert preview["reference"] == "Katoff - The Signal"
    assert [(s["name"], s["bar"], s["bars"]) for s in preview["sections"]] == [
        ("Intro", 1, 16), ("Drop", 17, 8), ("Groove", 25, 24), ("Break", 49, 48), ("Drop 2", 97, 32), ("Groove 2", 129, 24), ("Outro", 153, 8)]
    assert preview["bars"] == 160 and preview["tempo"] is None
    assert any("minutes ignored" in w for w in preview["warnings"])

    with pytest.raises(ToolError, match="No analyzed reference matches 'nothing'"):
        await _plan(server, reference="nothing")


async def test_a_reference_sets_tempo_and_key_with_set_tempo(client, live, references):
    _studio(live)
    server = build_server(client)
    preview = await _plan(server, genre="peak_time_techno", reference="katoff", set_tempo=True)
    assert preview["tempo"] == 124 and preview["bpm"] == 124 and preview["scale"].startswith("D# Minor")
    await server.call_tool("apply_plan", {"plan_id": preview["plan_id"]})
    song = live.on_main(lambda: (live.song.tempo, live.song.root_note, live.song.scale_name))
    assert song == (124, 3, "Minor")


async def test_an_unwarped_reference_needs_its_own_tempo(client, live, references, tmp_path):
    _studio(live)
    # analyzed unwarped: bars of the song's own 124 BPM, the Set plays 120
    unwarped = {**REFERENCE, "bar_grid": "song", "warped": False}
    (tmp_path / "references" / "katoff.json").write_text(json.dumps(unwarped))
    server = build_server(client)
    with pytest.raises(ToolError, match="is not warped: it plays at its own 124 BPM while the song would play at 120 BPM"):
        await _plan(server, genre="peak_time_techno", reference="katoff")
    # at the reference's tempo the bars line up; the plan still says how to make it tempo-proof
    preview = await _plan(server, genre="peak_time_techno", reference="katoff", set_tempo=True)
    assert preview["tempo"] == 124 and any("not warped" in w for w in preview["warnings"])


async def test_a_reference_song_starts_under_the_reference_clip(client, live, references, tmp_path):
    _studio(live)
    reference = {**REFERENCE, "sections": [{**s, "beat": (s["start_bar"] + 7) * 4} for s in REFERENCE["sections"]]}
    (tmp_path / "references" / "katoff.json").write_text(json.dumps(reference))  # the clip starts at bar 9
    audio = (await client.call("track.create", {"name": "Katoff"}))["track"]
    await client.call("arrangement.edit", {"actions": [{"action": "add_clip", "track": audio, "start": 32, "length": 152 * 4}]})
    server = build_server(client)
    preview = await _plan(server, genre="peak_time_techno", reference="katoff")
    assert preview["from_bar"] == 9 and preview["sections"][1]["bar"] == 25

    await client.call("arrangement.edit", {"actions": [{"action": "add_clip", "track": 0, "start": 100, "length": 4}]})  # the drums are busy
    preview = await _plan(server, genre="peak_time_techno", reference="katoff")
    assert preview["from_bar"] == 161  # after the reference clip
    assert any("Not under the reference at bar 9" in w for w in preview["warnings"])
    assert (await _plan(server, genre="peak_time_techno", reference="katoff", start_bar=200))["from_bar"] == 200


async def test_a_song_with_a_counter_melody(client, live):
    # "Create a melodic techno track ... apply a counter melody track as well": one plan_song call
    _studio(live)
    _minor(live)
    preview, clips = await _song_notes(client, build_server(client), "melodic_techno", counter=True)
    counter = preview["tracks"]["counter"]
    assert counter["name"] == "Counter" and counter["new"] and counter["device"] == "Basic Pluck Keys"
    assert preview["mix"]["levels"]["counter"].startswith("fader ")
    leads = {name.removesuffix(" Lead"): clip for name, (clip, notes) in clips.items() if name.endswith(" Lead") and notes}
    counters = {name.removesuffix(" Counter"): (clip, notes) for name, (clip, notes) in clips.items() if name.endswith(" Counter")}
    assert set(counters) == set(leads)  # a counter clip for every lead clip, at its place
    for section, (clip, notes) in counters.items():
        assert (clip["start"], clip["end"]) == (leads[section]["start"], leads[section]["end"]) and notes
        assert max(n["pitch"] for n in notes) <= 96
    drop = counters["Drop"][1]
    assert drop and len(drop) < len(clips["Drop Lead"][1]) / 2  # sparser than the arp it answers


async def test_a_track_of_an_unapplied_song_plan_says_apply_first(client, live):
    _studio(live)
    server = build_server(client)
    preview = await _plan(server, genre="melodic_techno")
    lead = preview["tracks"]["lead"]["track"]
    with pytest.raises(ToolError, match=rf"comes from song plan {preview['plan_id']}, which is not applied yet: apply_plan"):
        await server.call_tool("compose", {"kind": "melody", "track": 1, "counter_to": {"track": lead}})


def test_the_seed_picks_the_bass_among_the_templates_that_suit_the_genre():
    import random

    from midibakery.compose.song import _bass_variant

    picks = {getattr(_bass_variant("melodic_techno", 122, random.Random(seed)), "name", None) for seed in range(40)}
    assert None in picks and len(picks) >= 3  # the genre's own recipe and several templates
    assert _bass_variant("melodic_techno", 122, random.Random(5)) == _bass_variant("melodic_techno", 122, random.Random(5))
    assert {_bass_variant("trap", 140, random.Random(seed)) for seed in range(10)} == {None}  # no fitting template: the recipe
    assert {_bass_variant("house", 90, random.Random(seed)) for seed in range(10)} == {None}  # none fits the tempo


@pytest.mark.asyncio
async def test_set_tempo_varies_a_little_with_the_seed(client, live):
    _studio(live)
    server = build_server(client)
    tempos = {_payload(await server.call_tool("plan_song", {"genre": "house", "seed": seed, "set_tempo": True, "fx": False,
                                                             "sidechain": False, "create_missing": False}))["tempo"] for seed in range(8)}
    assert len(tempos) >= 2 and all(121 <= t <= 127 for t in tempos), tempos


def _drop_chords(clips):
    """The pitch classes sounding in each bar of 'Drop Chords', as (first half, second half)."""
    clip, notes = clips["Drop Chords"]
    bars = round(max(n["start_time"] + n["duration"] for n in notes) / 4)
    per_bar = [frozenset(n["pitch"] % 12 for n in notes if bar * 4 <= n["start_time"] < bar * 4 + 4) for bar in range(bars)]
    return per_bar[: bars // 2], per_bar[bars // 2:]


async def test_a_long_drop_turns_to_other_chords_in_its_second_half(client, live):
    _studio(live)
    _, clips = await _song_notes(client, build_server(client), "house", seed=7)
    first, second = _drop_chords(clips)
    assert first and second and first != second


async def test_second_progression_sets_the_chords_of_the_drops_second_half(client, live):
    _studio(live)
    _, clips = await _song_notes(client, build_server(client), "house", seed=7, progression="I I I I", second_progression="V V V V")
    first, second = _drop_chords(clips)
    assert all(0 in bar for bar in first) and not any(0 in bar for bar in second)  # C chords, then G chords (no C in them)
    assert all(2 in bar for bar in second)
