"""The Bake device's songs: Bake, Again and Back against the fake LOM."""

import pytest

from midibakery.bake import Baker
from midibakery.bridge import BridgeError


async def _clips(client):
    """(track, start, name) of every arrangement clip."""
    arrangement = await client.call("arrangement.get", {})
    return sorted((t["index"], c["start"], c["name"]) for t in arrangement["tracks"] for c in t["clips"])


async def test_bake_writes_a_song_and_again_replaces_it(client, live):
    baker = Baker(client.call)
    first = await baker.bake({"genre": "house", "seed": 7})
    assert first["seed"] == 7 and first["baked"]["bars"].startswith("1-")
    song = await _clips(client)
    tracks = live.on_main(lambda: len(live.song.tracks))
    assert song

    again = await baker.bake({"mode": "again", "genre": "house", "seed": 8})
    assert again["baked"]["bars"].startswith("1-") and again["baked"]["can_go_back"]  # its own length: the sections vary per seed
    assert live.on_main(lambda: len(live.song.tracks)) == tracks  # the tracks are used again
    replaced = await _clips(client)
    assert replaced and min(c[1] for c in replaced) == min(c[1] for c in song)  # in place, not after it

    back = await baker.bake({"mode": "back"})
    assert back["seed"] == 7 and not back["baked"]["can_go_back"]
    assert await _clips(client) == song  # the same notes and places as the first one
    locators = (await client.call("arrangement.get", {}))["locators"]
    assert len({loc["time"] for loc in locators}) == len(locators)  # no locator twice


async def test_bake_passes_the_complexity_on_and_again_keeps_it(client, live):
    baker = Baker(client.call)
    with pytest.raises(ValueError, match="complexity"):
        await baker.bake({"genre": "house", "complexity": "wild"})
    simple = await baker.bake({"genre": "house", "seed": 5, "length": "radio", "complexity": "simple"})
    assert simple["baked"]["complexity"] == "simple"
    song = await _clips(client)
    again = await baker.bake({"mode": "again", "genre": "house", "length": "radio", "complexity": "simple", "seed": 5})
    assert again["baked"]["complexity"] == "simple" and await _clips(client) == song  # same seed, same simple song
    rich = await baker.bake({"genre": "house", "seed": 5, "length": "radio", "complexity": "rich"})
    assert rich["baked"]["complexity"] == "rich"
    assert (await baker.bake({"genre": "house", "seed": 6, "length": "radio"}))["baked"]["complexity"] == "rich"  # the default


async def test_a_new_bake_goes_after_the_last_song(client, live):
    baker = Baker(client.call)
    first = await baker.bake({"genre": "house", "seed": 1, "length": "radio"})
    second = await baker.bake({"genre": "house", "seed": 2, "length": "radio"})
    end = int(first["baked"]["bars"].split("-")[1])
    assert int(second["baked"]["bars"].split("-")[0]) > end


async def test_bake_needs_a_genre_or_reference_and_back_a_previous_seed(client, live):
    baker = Baker(client.call)
    with pytest.raises(ValueError, match="genre or a reference"):
        await baker.bake({"genre": None})
    with pytest.raises(ValueError, match="nothing to go back to"):
        await baker.bake({"mode": "back"})
    with pytest.raises(ValueError):
        await baker.bake({"genre": "polka"})
    assert await _clips(client) == []


async def test_a_failed_again_brings_the_previous_song_back(client, live, monkeypatch):
    baker = Baker(client.call)
    await baker.bake({"genre": "house", "seed": 7})
    locators = len(baker.last.locators)
    before = live.on_main(lambda: live.song.undo_calls)

    async def broken(*_args, **_kwargs):
        raise BridgeError("LIVE_ERROR", "boom")

    monkeypatch.setattr("midibakery.bake.build_song", broken)
    with pytest.raises(BridgeError) as failed:
        await baker.bake({"mode": "again", "genre": "house"})
    assert "previous song is back" in failed.value.message
    # the fake LOM only counts undo: the clip deletion (one step) and each locator deletion
    assert live.on_main(lambda: live.song.undo_calls) - before == 1 + locators
    assert baker.last is not None and baker.last.seed == 7
