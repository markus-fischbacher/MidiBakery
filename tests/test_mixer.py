"""Mixer and routing ops: real Remote Script against the fake LOM over a real socket."""

import pytest
from pydantic import ValidationError

from midibakery.bridge import BridgeError
from midibakery.catalog.ops import DeviceParamSet, MixerGet, MixerSet


async def test_return_with_reverb_and_a_send_in_db(client, live):
    created = await client.call("return.create", {"name": "Hall", "device": "Reverb"})
    assert created["kind"] == "return" and created["index"] == 0 and created["name"] == "Hall"
    assert created["devices"] == ["Reverb"]
    devices = live.on_main(lambda: [d.name for d in live.song.return_tracks[0].devices])
    assert devices == ["Reverb"]

    track = await client.call("mixer.set", {"track": 0, "sends": [{"return_track": 0, "db": -12}]})
    send = track["sends"][0]
    assert send["name"] == "Hall" and send["display"] == "-12.0 dB"
    # Every track got a send to the new return, also tracks created later.
    new = (await client.call("track.create", {"name": "Late"}))["track"]
    assert len((await client.call("mixer.get", {"track": new}))["sends"]) == 1


async def test_device_on_a_return_track(client):
    await client.call("return.create", {"name": "Hall", "device": "Reverb"})
    changed = await client.call("device.set_param", {"return_track": 0, "device": 0, "parameter": "Dry/Wet", "value": 1.0})
    assert changed["value"] == 1.0
    with pytest.raises(BridgeError, match="No return_track index 1"):
        await client.call("device.params", {"return_track": 1, "device": 0})
    for both_or_none in ({"track": 0, "return_track": 0}, {}):
        with pytest.raises(ValidationError, match="either track or return_track"):
            DeviceParamSet(device=0, parameter=0, value=0, **both_or_none)


async def test_volume_in_db_pan_mute_and_crossfade(client):
    state = await client.call("mixer.set", {"track": 1, "volume_db": -6, "pan": -0.5, "mute": True, "crossfade": "B"})
    assert state["volume"]["display"] == "-6.0 dB"
    assert state["pan"]["value"] == -0.5 and state["mute"] is True and state["crossfade"] == "B"
    silent = await client.call("mixer.set", {"track": 1, "volume_db": -200})
    assert silent["volume"]["display"] == "-inf dB"


async def test_routing_by_the_names_live_shows(client):
    options = (await client.call("mixer.get", {"track": 0, "options": True}))["options"]
    assert "No Input" in options["input_routing_types"] and "Sends Only" in options["output_routing_types"]
    state = await client.call("mixer.set", {"track": 0, "input_routing": "No Input", "output_routing": "Sends Only"})
    assert state["routing"]["input_routing"] == "No Input" and state["routing"]["output_routing"] == "Sends Only"

    with pytest.raises(BridgeError) as exc:
        await client.call("mixer.set", {"track": 0, "output_routing": "Nowhere"})
    assert exc.value.code == "NOT_FOUND" and "Sends Only" in exc.value.details["available"]


async def test_whole_mixer_and_the_master(client):
    await client.call("return.create", {})
    mixer = await client.call("mixer.get", {})
    assert len(mixer["tracks"]) == 2 and len(mixer["returns"]) == 1
    assert mixer["master"]["kind"] == "master" and "sends" not in mixer["master"]
    master = await client.call("mixer.set", {"master": True, "volume_db": -3})
    assert master["volume"]["display"] == "-3.0 dB"


async def test_mixer_changes_are_one_undo_step_each(client, live):
    before = live.on_main(lambda: live.song.undo_steps)
    await client.call("mixer.set", {"track": 0, "volume_db": -10, "pan": 0.3})
    assert live.on_main(lambda: live.song.undo_steps) == before + 1


async def test_missing_return_is_not_found(client):
    with pytest.raises(BridgeError) as exc:
        await client.call("mixer.set", {"track": 0, "sends": [{"return_track": 3, "db": -6}]})
    assert exc.value.code == "NOT_FOUND"


def test_core_rejects_ambiguous_or_empty_mixer_calls():
    with pytest.raises(ValidationError):
        MixerSet(track=0, master=True, volume=0.5)
    with pytest.raises(ValidationError):
        MixerSet(track=0)
    with pytest.raises(ValidationError):
        MixerSet(master=True, mute=True)
    with pytest.raises(ValidationError):
        MixerSet(track=0, volume=0.5, volume_db=-6)
    with pytest.raises(ValidationError):
        MixerSet(track=0, sends=[{"return_track": 0}])
    with pytest.raises(ValidationError):
        MixerGet(options=True)
