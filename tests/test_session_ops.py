"""clip.set, history.step, scene.fire and song.position: real Remote Script against the fake LOM."""

import pytest

from midibakery.bridge import BridgeError


async def _clip(client, slot=0, length=8):
    await client.call("clip.create", {"track": 0, "slot": slot, "length": length})
    return {"track": 0, "slot": slot}


async def test_clip_set_names_colours_and_loops(client, live):
    ref = await _clip(client)
    clip = await client.call("clip.set", {**ref, "name": "Hook", "color_index": 12, "looping": False})
    assert (clip["name"], clip["color_index"], clip["looping"]) == ("Hook", 12, False)
    # A loop moved past its old end: Live refuses a loop_start beyond the current loop_end, so the end goes first.
    clip = await client.call("clip.set", {**ref, "loop_start": 12, "loop_end": 16})
    assert (clip["loop_start"], clip["loop_end"]) == (12, 16)
    # ...and moved back before its old start: the start goes first.
    clip = await client.call("clip.set", {**ref, "loop_start": 0, "loop_end": 4})
    assert (clip["loop_start"], clip["loop_end"]) == (0, 4)
    clip = await client.call("clip.set", {**ref, "loop_end": 6})
    assert (clip["loop_start"], clip["loop_end"]) == (0, 6)
    assert live.on_main(lambda: live.song.tracks[0].clip_slots[0].clip.name) == "Hook"


async def test_clip_set_refuses_a_loop_that_ends_before_it_starts(client):
    ref = await _clip(client)
    with pytest.raises(BridgeError, match="loop_start must be before loop_end") as exc:
        await client.call("clip.set", {**ref, "loop_start": 8})  # the loop ends at 8
    assert exc.value.code == "INVALID_PARAMS"
    with pytest.raises(BridgeError) as exc:
        await client.call("clip.set", {"track": 0, "slot": 3, "name": "x"})
    assert exc.value.code == "NOT_FOUND" and "Slot index 3 on track index 0" in exc.value.message


async def test_clip_set_on_an_arrangement_clip(client, live):
    await client.call("arrangement.edit", {"actions": [{"action": "add_clip", "track": 0, "start": 16, "length": 8}]})
    clip = await client.call("clip.set", {"track": 0, "arrangement_clip": 0, "name": "Verse", "color_index": 3})
    assert clip["name"] == "Verse" and clip["start_time"] == 16
    assert live.on_main(lambda: live.song.tracks[0].arrangement_clips[0].name) == "Verse"
    with pytest.raises(BridgeError, match="No arrangement_clip index 1 on track index 0"):
        await client.call("clip.set", {"track": 0, "arrangement_clip": 1, "name": "x"})


async def test_history_steps_back_and_forth(client, live):
    with pytest.raises(BridgeError, match="Nothing to undo") as exc:
        await client.call("history.step", {"action": "undo"})
    assert exc.value.code == "CONFLICT"
    await client.call("song.set", {"tempo": 99})
    steps = live.on_main(lambda: live.song.undo_steps)
    assert await client.call("history.step", {"action": "undo"}) == {"can_undo": True, "can_redo": True}
    assert await client.call("history.step", {"action": "redo"}) == {"can_undo": True, "can_redo": False}
    with pytest.raises(BridgeError, match="Nothing to redo"):
        await client.call("history.step", {"action": "redo"})
    # Stepping through the history is no undo step of its own.
    assert live.on_main(lambda: live.song.undo_steps) == steps
    assert live.on_main(lambda: live.song.undo_calls) == 1


async def test_scene_fire(client, live):
    assert await client.call("scene.fire", {"scene": 2}) == {"scene": 2}
    assert live.on_main(lambda: [s.fired for s in live.song.scenes[:3]]) == [0, 0, 1]
    count = live.on_main(lambda: len(live.song.scenes))
    with pytest.raises(BridgeError) as exc:
        await client.call("scene.fire", {"scene": count})
    assert exc.value.code == "NOT_FOUND" and exc.value.message == f"No scene index {count} (song has {count} scenes)"


async def test_song_position_waits_until_live_moved(client, live):
    # The fake, like Live, applies a new play position a tick after it is set; the op answers after that.
    assert await client.call("song.position", {"beat": 32}) == {"position": 32}
    assert live.on_main(lambda: live.song.current_song_time) == 32
    with pytest.raises(BridgeError, match="cannot run inside a batch") as exc:
        await client.call("batch", {"ops": [{"op": "song.position", "params": {"beat": 0}}]})
    assert exc.value.code == "INVALID_PARAMS"
    with pytest.raises(BridgeError) as exc:
        await client.call("song.position", {"beat": -1})
    assert exc.value.code == "INVALID_PARAMS"
