"""Rack ops: chains, macros, drum pad notes and devices inside racks, against the fake LOM."""

import pytest
from pydantic import ValidationError

from midibakery.bridge import BridgeError
from midibakery.catalog.ops import RackSet


async def test_instrument_rack_with_two_layers_and_a_macro(client, live):
    await client.call("device.insert", {"track": 0, "name": "Instrument Rack"})
    await client.call("rack.set", {"track": 0, "device": 0, "add_chain": {"name": "Body", "insert_devices": ["Operator"]}})
    rack = await client.call("rack.set", {
        "track": 0, "device": 0,
        "add_chain": {"name": "Air", "insert_devices": ["Wavetable", "Reverb"], "volume_db": -6, "pan": 0.4},
        "macros": [{"macro": 1, "value": 64}],
    })
    assert rack["kind"] == "instrument"
    assert [c["name"] for c in rack["chains"]] == ["Body", "Air"]
    assert [d["name"] for d in rack["chains"][1]["devices"]] == ["Wavetable", "Reverb"]
    assert rack["chains"][1]["volume"] == "-6.0 dB"
    assert rack["macros"][0] == {"macro": 1, "name": "Macro 1", "value": 64.0, "display": "64.00"}
    assert len(rack["macros"]) == 8


async def test_device_tools_reach_into_chains(client):
    await client.call("device.insert", {"track": 0, "name": "Instrument Rack"})
    await client.call("rack.set", {"track": 0, "device": 0, "add_chain": {"insert_devices": ["Operator"]}})
    params = await client.call("device.params", {"track": 0, "device": 0, "chain_path": [0, 0]})
    assert params["name"] == "Operator"
    changed = await client.call("device.set_param", {"track": 0, "device": 0, "chain_path": [0, 0], "parameter": "Volume", "value": 0.25})
    assert changed["value"] == 0.25
    with pytest.raises(BridgeError) as exc:
        await client.call("device.params", {"track": 0, "device": 0, "chain_path": [3, 0]})
    assert exc.value.code == "NOT_FOUND"
    with pytest.raises(BridgeError) as exc:
        await client.call("rack.set", {"track": 0, "device": 0, "chains": [{"chain": 5, "mute": True}]})
    assert "add_chain creates one" in str(exc.value)  # a model that edits a missing chain learns the way


async def test_drum_rack_pad_from_a_new_chain(client):
    await client.call("device.insert", {"track": 0, "name": "Drum Rack"})
    rack = await client.call("rack.set", {"track": 0, "device": 0, "add_chain": {"name": "Kick", "in_note": 36, "insert_devices": ["Simpler"]}})
    assert rack["kind"] == "drum"
    assert rack["chains"][0]["in_note"] == 36 and rack["chains"][0]["devices"][0]["name"] == "Simpler"
    moved = await client.call("rack.set", {"track": 0, "device": 0, "chains": [{"chain": 0, "in_note": 38, "mute": True}]})
    assert moved["chains"][0]["in_note"] == 38 and moved["chains"][0]["mute"] is True
    pads = await client.call("drum_rack.pads", {"track": 0})
    assert pads["pads"] == [{"note": 38, "name": "Kick"}]


async def test_pad_notes_only_on_drum_racks(client):
    await client.call("device.insert", {"track": 0, "name": "Instrument Rack"})
    with pytest.raises(BridgeError) as exc:
        await client.call("rack.set", {"track": 0, "device": 0, "add_chain": {"in_note": 36}})
    assert exc.value.code == "INVALID_PARAMS"


async def test_rack_ops_need_a_rack(client):
    await client.call("device.insert", {"track": 0, "name": "Operator"})
    with pytest.raises(BridgeError) as exc:
        await client.call("rack.get", {"track": 0, "device": 0})
    assert exc.value.code == "INVALID_PARAMS"


async def test_rack_edit_is_one_undo_step(client, live):
    await client.call("device.insert", {"track": 0, "name": "Instrument Rack"})
    before = live.on_main(lambda: live.song.undo_steps)
    await client.call("rack.set", {"track": 0, "device": 0, "add_chain": {"insert_devices": ["Operator", "Reverb"]}, "macros": [{"macro": 2, "value": 10}]})
    assert live.on_main(lambda: live.song.undo_steps) == before + 1


def test_core_rejects_empty_rack_edits():
    with pytest.raises(ValidationError):
        RackSet(track=0, device=0)
    with pytest.raises(ValidationError):
        RackSet(track=0, device=0, macros=[{"macro": 17, "value": 1}])
