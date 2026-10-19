"""Sidechain: device.routing, display values in device.set_param, and the song's ducking."""

import pytest

from fake_song import DrumRackDevice
from midibakery.bridge import BridgeError
from midibakery.mcp import build_server
from test_song import _payload, _studio


def _drums_and_compressor(song):
    rack = DrumRackDevice("909 Core Kit")
    rack.add_pad("Bass Drum", 36)
    rack.add_pad("Closed Hi Hat", 42)
    song.tracks[0].devices.append(rack)
    song.tracks[0].name = "Drums"
    song.tracks[1].insert_device("Compressor", 0)


async def test_a_compressor_is_keyed_from_a_track_and_channel(client, live):
    live.on_main(lambda: _drums_and_compressor(live.song))
    read = await client.call("device.routing", {"track": 1, "device": 0})
    assert read["input"] == "No Input" and read["available"]["inputs"] == ["Drums", "Main", "No Input"]
    keyed = await client.call("device.routing", {"track": 1, "device": 0, "input_track": 0,
                                                 "channel": ["909 Core Kit | Kick | Post FX", "909 Core Kit | Bass Drum | Post FX", "Post FX"]})
    assert keyed["input"] == "Drums" and keyed["input_channel"] == "909 Core Kit | Bass Drum | Post FX"  # the first Live offers
    with pytest.raises(BridgeError, match="No sidechain channel 'Pre Mixer'") as exc:
        await client.call("device.routing", {"track": 1, "device": 0, "input_track": 0, "channel": "Pre Mixer"})
    assert "Post FX" in exc.value.details["available"]


async def test_routing_needs_a_source_and_a_routable_device(client, live):
    live.on_main(lambda: _drums_and_compressor(live.song))
    with pytest.raises(BridgeError, match="Not a sidechain source") as exc:
        await client.call("device.routing", {"track": 1, "device": 0, "input_track": 1})  # not itself
    assert exc.value.code == "NOT_FOUND"
    live.on_main(lambda: live.song.tracks[1].insert_device("Auto Filter", 1))
    with pytest.raises(BridgeError, match="has no sidechain input") as exc:
        await client.call("device.routing", {"track": 1, "device": 1})
    assert exc.value.code == "UNSUPPORTED"


async def test_set_param_by_what_live_shows(client, live):
    live.on_main(lambda: _drums_and_compressor(live.song))
    threshold = await client.call("device.set_param", {"track": 1, "device": 0, "parameter": "Threshold", "display": -24})
    assert threshold["display"] == "-24.00 dB"
    release = await client.call("device.set_param", {"track": 1, "device": 0, "parameter": "Release", "display": 0.16})
    assert release["display"] == "160.0 ms"  # seconds in, Live's ms out
    kind = await client.call("device.set_param", {"track": 1, "device": 0, "parameter": "S/C EQ Type", "display": "Low pass"})
    assert kind["value"] == 3.0
    with pytest.raises(BridgeError, match="shows no 'Lowpass'"):
        await client.call("device.set_param", {"track": 1, "device": 0, "parameter": "S/C EQ Type", "display": "Lowpass"})


def test_pump_steps_follow_each_genres_main_kick():
    from midibakery.compose.song import pump_steps

    assert pump_steps("house") == pump_steps("peak_time_techno") == (0, 4, 8, 12)  # not Peak-Time's ghost kick
    assert pump_steps("drum_and_bass") == (0, 10) and pump_steps("trap") == (0, 7, 10)


async def _house(server, **args):
    return _payload(await server.call_tool("plan_song", {"genre": "house", "seed": 7, "fx": False, **args}))


def _compressors(live):
    def read():
        out = {}
        for track in live.song.tracks:
            for device in track.devices:
                if device.class_name == "Compressor2":
                    shown = {p.name: p.str_for_value(p.value) for p in device.parameters}
                    out[track.name] = (track.devices.index(device), device.input_routing_type.display_name, device.input_routing_channel.display_name,
                                       shown["Threshold"], shown["Release"], shown["S/C On"], shown["S/C EQ On"])
        return out

    return live.on_main(read)


async def test_sidechain_ducks_bass_and_chords_under_a_trigger_track(client, live):
    _studio(live)
    server = build_server(client)
    preview = await _house(server)
    trigger = preview["tracks"]["sidechain"]
    assert trigger["new"] and trigger["device"] == "Operator" and trigger["name"] == "Sidechain" and "fader -inf" in trigger["plays"]
    assert preview["tracks"]["bass"]["sidechain"] == "Compressor keyed from the sidechain track, threshold -24 dB (new device)"
    assert preview["tracks"]["chords"]["sidechain"] == "Compressor keyed from the sidechain track, threshold -18 dB"
    assert "sidechain" not in preview["tracks"]["lead"] and "sidechain" not in preview["tracks"]["drums"]
    applied = _payload(await server.call_tool("apply_plan", {"plan_id": preview["plan_id"]}))
    assert not applied.get("warnings")

    compressors = _compressors(live)
    assert compressors["Bass"] == (0, "Sidechain", "Post FX", "-24.00 dB", "160.0 ms", "On", "Off")  # an empty track: first device
    chords = next(v for k, v in compressors.items() if k.endswith("Chords"))
    assert chords[:3] == (2, "Sidechain", "Post FX") and chords[3] == "-18.00 dB"  # after the instrument and the Auto Filter

    def trigger_track():
        track = next(t for t in live.song.tracks if t.name == "Sidechain")
        clips = [(c.name, c.start_time, c.end_time, len(c.notes)) for c in track.arrangement_clips]
        notes = sorted(track.arrangement_clips[0].notes.values(), key=lambda n: n["start_time"])[:5]
        return track.mixer_device.volume.str_for_value(track.mixer_device.volume.value), clips, [(n["start_time"], n["duration"], n["velocity"]) for n in notes]

    # the trigger track comes first; every other track moved down one, its clips with it
    order = live.on_main(lambda: [(t.name, sorted({c.name.split()[-1] for c in t.arrangement_clips})) for t in live.song.tracks])
    assert order[0] == ("Sidechain", ["Sidechain"]), order
    assert all(clips in ([], [name]) for name, clips in order[1:] if name in ("Drums", "Bass", "Chords", "Lead")), order
    assert next(t["track"] for t in applied["new_tracks"] if t["name"] == "Sidechain") == 0

    fader, clips, notes = live.on_main(trigger_track)
    assert fader == "-inf dB" and clips == [("Sidechain", 0.0, 512.0, 512)]  # 128 bars, a note per beat, through the breaks too
    assert notes == [(0.0, 0.25, 127), (1.0, 0.25, 127), (2.0, 0.25, 127), (3.0, 0.25, 127), (4.0, 0.25, 127)]


async def test_no_sidechain_no_trigger_track(client, live):
    _studio(live)
    server = build_server(client)
    preview = await _house(server, sidechain=False)
    assert "sidechain" not in preview["tracks"] and "sidechain" not in preview["tracks"]["bass"]


async def test_an_existing_trigger_track_and_compressor_are_reused(client, live):
    _studio(live)

    def setup():
        live.song.tracks[1].insert_device("Compressor", 0)
        live.song.create_midi_track(-1)
        live.song.tracks[-1].name = "Sidechain"  # empty: it gets an instrument to sound

    live.on_main(setup)
    server = build_server(client)
    preview = await _house(server, create_missing=False)
    assert preview["tracks"]["sidechain"]["track"] == 2
    assert preview["tracks"]["bass"]["sidechain"] == "Compressor keyed from the sidechain track, threshold -24 dB"
    assert any("its Compressor is keyed from the sidechain track" in w for w in preview["warnings"])
    await server.call_tool("apply_plan", {"plan_id": preview["plan_id"]})
    assert _compressors(live)["Bass"][:3] == (0, "Sidechain", "Post FX")
    assert live.on_main(lambda: [d.name for d in live.song.tracks[2].devices]) == ["Operator"]


def _kick_and_trigger_times(live, kick):
    def read():
        drum_track = next(t for t in live.song.tracks if t.name == "Drums")
        trigger = next(t for t in live.song.tracks if t.name == "Sidechain")
        kicks = {round(c.start_time + n["start_time"], 6) for c in drum_track.arrangement_clips
                 for n in c.notes.values() if n["pitch"] == kick and not n.get("mute")}
        triggers = {round(c.start_time + n["start_time"], 6) for c in trigger.arrangement_clips for n in c.notes.values()}
        return kicks, triggers
    return live.on_main(read)


@pytest.mark.parametrize("genre", ["house", "peak_time_techno", "drum_and_bass", "trap", "melodic_techno"])
async def test_kick_following_matches_generated_drums_including_rests_and_variations(client, live, genre):
    _studio(live)
    server = build_server(client)
    preview = _payload(await server.call_tool("plan_song", {"genre": genre, "seed": 7, "fx": False,
                                                          "sidechain_mode": "follow_kick", "start_bar": 5}))
    assert preview["sidechain_mode"] == "follow_kick"
    await server.call_tool("apply_plan", {"plan_id": preview["plan_id"]})
    kicks, triggers = _kick_and_trigger_times(live, 36)
    assert kicks and triggers == kicks and min(triggers) >= 16


async def test_follow_kick_works_after_new_kit_remaps_pitches(client, live):
    server = build_server(client)
    preview = await _house(server, sidechain_mode="follow_kick")
    applied = _payload(await server.call_tool("apply_plan", {"plan_id": preview["plan_id"]}))
    track = next(t["track"] for t in applied["new_tracks"] if t["name"] == "Drums")
    pads = (await client.call("drum_rack.pads", {"track": track}))["pads"]
    from midibakery.compose.drums import map_pads
    kick = map_pads(pads).note("kick")
    kicks, triggers = _kick_and_trigger_times(live, kick)
    assert kicks and kicks == triggers


async def _copied_kick_plan(client, live, **note_values):
    _studio(live)
    await client.call("clip.create", {"track": 0, "slot": 0, "length": 4})
    await client.call("notes.apply", {"track": 0, "slot": 0, "add": [
        {"pitch": 36, "start_time": 0.5, "duration": 0.25, **note_values},
        {"pitch": 36, "start_time": 1.5, "duration": 0.25, "mute": True},
        {"pitch": 42, "start_time": 2, "duration": 0.25},
    ]})
    server = build_server(client)
    preview = await _house(server, clips=[{"role": "drums", "track": 0, "slot": 0}], sidechain_mode="follow_kick")
    return server, preview


async def test_follow_kick_copies_source_onsets_not_a_genre_grid(client, live):
    server, preview = await _copied_kick_plan(client, live)
    await server.call_tool("apply_plan", {"plan_id": preview["plan_id"]})
    kicks, triggers = _kick_and_trigger_times(live, 36)
    assert kicks and kicks == triggers and all(t % 4 == 0.5 for t in triggers)


async def test_follow_kick_rejects_changed_source_before_writing(client, live):
    from mcp.server.mcpserver.exceptions import ToolError

    server, preview = await _copied_kick_plan(client, live)
    await client.call("notes.apply", {"track": 0, "slot": 0, "add": [{"pitch": 36, "start_time": 3, "duration": 0.25}]})
    before = live.on_main(lambda: live.song.undo_steps)
    with pytest.raises(ToolError, match="copied drum clip changed"):
        await server.call_tool("apply_plan", {"plan_id": preview["plan_id"]})
    assert live.on_main(lambda: live.song.undo_steps) == before


async def test_follow_kick_rejects_unpredictable_note_probability(client, live):
    from mcp.server.mcpserver.exceptions import ToolError

    with pytest.raises(ToolError, match="deterministic kick"):
        await _copied_kick_plan(client, live, probability=0.5)


async def test_follow_kick_needs_a_known_kick_pad(client, live):
    from mcp.server.mcpserver.exceptions import ToolError

    _studio(live)
    live.on_main(lambda: live.song.tracks[0].devices.__setitem__(0, DrumRackDevice()))
    with pytest.raises(ToolError, match="identifiable kick"):
        await _house(build_server(client), sidechain_mode="follow_kick")
