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
    assert trigger["new"] and trigger["device"] == "Operator" and trigger["name"] == "House Sidechain" and "fader -inf" in trigger["plays"]
    assert preview["tracks"]["bass"]["sidechain"] == "Compressor keyed from the sidechain track, threshold -24 dB (new device)"
    assert preview["tracks"]["chords"]["sidechain"] == "Compressor keyed from the sidechain track, threshold -18 dB"
    assert "sidechain" not in preview["tracks"]["lead"] and "sidechain" not in preview["tracks"]["drums"]
    applied = _payload(await server.call_tool("apply_plan", {"plan_id": preview["plan_id"]}))
    assert not applied.get("warnings")

    compressors = _compressors(live)
    assert compressors["Bass"] == (0, "House Sidechain", "Post FX", "-24.00 dB", "160.0 ms", "On", "Off")  # an empty track: first device
    chords = next(v for k, v in compressors.items() if k.endswith("Chords"))
    assert chords[:3] == (2, "House Sidechain", "Post FX") and chords[3] == "-18.00 dB"  # after the instrument and the Auto Filter

    def trigger_track():
        track = next(t for t in live.song.tracks if t.name == "House Sidechain")
        clips = [(c.name, c.start_time, c.end_time, len(c.notes)) for c in track.arrangement_clips]
        notes = sorted(track.arrangement_clips[0].notes.values(), key=lambda n: n["start_time"])[:5]
        return track.mixer_device.volume.str_for_value(track.mixer_device.volume.value), clips, [(n["start_time"], n["duration"], n["velocity"]) for n in notes]

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
