"""Browser ops: search Live's browser and load kits, presets and devices onto tracks, against the fake LOM."""

import pytest

from midibakery.bridge import BridgeError


async def test_search_finds_kits_before_deeper_items(client):
    found = await client.call("browser.search", {"query": "909", "category": "drums"})
    assert [i["path"] for i in found["items"]] == [["drums", "909 Core Kit.adg"], ["drums", "Drum Hits", "Kick 909 Long.wav"]]
    assert found["complete"]
    presets = await client.call("browser.search", {"query": "bass", "category": "instruments"})
    assert presets["items"][0]["path"] == ["instruments", "Drift", "Bass", "Sub Bass.adv"]  # folders are not loadable
    folders = await client.call("browser.search", {"query": "bass", "category": "instruments", "loadable_only": False})
    assert folders["items"][0]["path"] == ["instruments", "Drift", "Bass"]


async def test_kit_replaces_the_empty_drum_rack(client, live):
    await client.call("device.insert", {"track": 0, "name": "Drum Rack"})
    await client.call("device.insert", {"track": 0, "name": "Auto Filter"})
    loaded = await client.call("browser.load", {"track": 0, "path": ["drums", "909 Core Kit.adg"]})
    assert loaded["loaded"] == "909 Core Kit.adg"
    assert [d["name"] for d in loaded["devices"]] == ["909 Core Kit", "Auto Filter"]
    pads = await client.call("drum_rack.pads", {"track": 0, "device": 0})
    assert {p["name"] for p in pads["pads"]} >= {"Kick 909", "Snare 909"}
    assert live.on_main(lambda: live.song.view.selected_track is live.song.tracks[0])  # the selection is back


async def test_load_names_what_the_folder_holds(client):
    with pytest.raises(BridgeError) as exc:
        await client.call("browser.load", {"track": 1, "path": ["instruments", "Drift", "Pads"]})
    assert exc.value.code == "NOT_FOUND" and exc.value.details["available"] == ["Bass"]
    with pytest.raises(BridgeError) as exc:
        await client.call("browser.load", {"track": 1, "path": ["instruments", "Drift", "Bass"]})
    assert "cannot be loaded" in str(exc.value)


async def test_search_falls_back_to_some_of_the_words(client):
    # a model asked for "organ pad" and gave up: nothing has both words, "106 Organ" has one
    found = await client.call("browser.search", {"query": "organ pad"})
    assert found["matched"] == "some words"
    assert found["items"][0]["name"] == "106 Organ.adg"
    assert "matched" not in await client.call("browser.search", {"query": "organ"})


async def test_load_by_name_without_a_path(client, live):
    # models send ['Operator'] instead of a path from browser.search
    await client.call("device.insert", {"track": 0, "name": "Drift"})
    loaded = await client.call("browser.load", {"track": 0, "path": ["Operator"]})
    assert [d["class_name"] for d in loaded["devices"]] == ["Operator"]
    preset = await client.call("browser.load", {"track": 0, "path": ["Basic Pluck Keys"]})
    assert preset["loaded"] == "Basic Pluck Keys.adg"
    with pytest.raises(BridgeError, match="No browser item named 'Moog'"):
        await client.call("browser.load", {"track": 0, "path": ["Moog"]})
