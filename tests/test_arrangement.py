"""Arrangement View ops: clips on the timeline, locators, session -> arrangement, against the fake LOM."""

import pytest
from pydantic import ValidationError

from midibakery.bridge import BridgeError
from midibakery.catalog.ops import ArrangementEdit, ClipRef

KICK = {"pitch": 36, "start_time": 0.0, "duration": 0.25, "velocity": 110}


async def test_clips_with_notes_on_the_timeline(client):
    result = await client.call("arrangement.edit", {"actions": [
        {"action": "add_clip", "track": 0, "start": 16, "length": 16, "name": "Drop", "notes": [KICK, {**KICK, "start_time": 1.0}]},
        {"action": "add_clip", "track": 0, "start": 0, "length": 16, "name": "Intro"},
    ]})
    assert [r["start"] for r in result["results"]] == [16.0, 0.0] and result["song_length"] == 32.0
    arrangement = await client.call("arrangement.get", {})
    clips = arrangement["tracks"][0]["clips"]
    assert [(c["index"], c["name"], c["start"], c["end"]) for c in clips] == [(0, "Intro", 0.0, 16.0), (1, "Drop", 16.0, 32.0)]

    clip = await client.call("clip.get", {"track": 0, "arrangement_clip": 1})
    assert clip["start_time"] == 16.0 and clip["end_time"] == 32.0 and "stop_pending" not in clip
    notes = (await client.call("notes.get", {"track": 0, "arrangement_clip": 1}))["notes"]
    assert [n["start_time"] for n in notes] == [0.0, 1.0]

    changed = await client.call("notes.apply", {"track": 0, "arrangement_clip": 1, "modify": [{"note_id": notes[0]["note_id"], "velocity": 90}]})
    assert changed["modified"] == 1


async def test_nothing_is_overwritten(client):
    await client.call("arrangement.edit", {"actions": [{"action": "add_clip", "track": 1, "start": 0, "length": 16, "name": "Keep"}]})
    with pytest.raises(BridgeError) as exc:
        await client.call("arrangement.edit", {"actions": [
            {"action": "add_clip", "track": 1, "start": 16, "length": 4},
            {"action": "add_clip", "track": 1, "start": 8, "length": 16},
        ]})
    assert exc.value.code == "CONFLICT" and exc.value.details["index"] == 1 and exc.value.details["completed"] == 1
    assert "Keep" in str(exc.value)
    clips = (await client.call("arrangement.get", {"track": 1}))["tracks"][0]["clips"]
    assert [(c["start"], c["end"]) for c in clips] == [(0.0, 16.0), (16.0, 20.0)]  # earlier actions stay; undo reverts all


async def test_session_clip_to_the_arrangement(client):
    await client.call("clip.create", {"track": 0, "slot": 0, "length": 8, "name": "Loop"})
    await client.call("notes.apply", {"track": 0, "slot": 0, "add": [KICK]})
    await client.call("arrangement.edit", {"actions": [
        {"action": "copy_session_clip", "track": 0, "slot": 0, "start": 32},
        {"action": "copy_session_clip", "track": 0, "slot": 0, "start": 40},
    ]})
    clips = (await client.call("arrangement.get", {"track": 0}))["tracks"][0]["clips"]
    assert [(c["name"], c["start"]) for c in clips] == [("Loop", 32.0), ("Loop", 40.0)]
    assert len((await client.call("notes.get", {"track": 0, "arrangement_clip": 1}))["notes"]) == 1


async def test_locators_named_moved_back_and_deleted(client, live):
    # The fake applies a new play position one tick later, like Live: the op has to wait for it.
    live.on_main(lambda: setattr(live.song, "current_song_time", 4.0))
    await client.call("arrangement.locators", {"actions": [
        {"action": "set_locator", "time": 0, "name": "Intro"},
        {"action": "set_locator", "time": 64, "name": "Drop"},
        {"action": "set_locator", "time": 64, "name": "Drop 1"},  # existing: renamed, not toggled away
    ]})
    locators = (await client.call("arrangement.get", {}))["locators"]
    assert [(l["name"], l["time"]) for l in locators] == [("Intro", 0.0), ("Drop 1", 64.0)]
    assert live.on_main(lambda: live.song.current_song_time) == 4.0  # play position restored

    await client.call("arrangement.locators", {"actions": [{"action": "delete_locator", "time": 0}]})
    assert [l["name"] for l in (await client.call("arrangement.get", {}))["locators"]] == ["Drop 1"]


async def test_locators_need_a_stopped_transport(client, live):
    live.on_main(lambda: setattr(live.song, "is_playing", True))
    with pytest.raises(BridgeError) as exc:
        await client.call("arrangement.locators", {"actions": [{"action": "set_locator", "time": 32}]})
    assert exc.value.code == "CONFLICT"


async def test_locators_cannot_share_a_batch(client):
    with pytest.raises(BridgeError) as exc:
        await client.call("batch", {"ops": [{"op": "arrangement.locators", "params": {"actions": [{"action": "set_locator", "time": 0}]}}]})
    assert exc.value.code == "INVALID_PARAMS"


async def test_edit_arrangement_tool_does_clips_then_locators(client, live):
    from midibakery.mcp import build_server

    server = build_server(client)
    await server.call_tool("edit_arrangement", {"actions": [
        {"action": "set_locator", "time": 0, "name": "Intro"},
        {"action": "add_clip", "track": 0, "start": 0, "length": 16, "name": "Intro"},
        {"action": "set_locator", "time": 16, "name": "Drop"},
    ]})
    arrangement = await client.call("arrangement.get", {})
    assert [l["name"] for l in arrangement["locators"]] == ["Intro", "Drop"]
    assert [c["name"] for c in arrangement["tracks"][0]["clips"]] == ["Intro"]


async def test_delete_arrangement_clips(client):
    await client.call("arrangement.edit", {"actions": [
        {"action": "add_clip", "track": 0, "start": 0, "length": 4},
        {"action": "add_clip", "track": 0, "start": 4, "length": 4},
        {"action": "add_clip", "track": 0, "start": 8, "length": 4},
    ]})
    await client.call("arrangement.edit", {"actions": [{"action": "delete_clip", "track": 0, "clip": 1}]})
    await client.call("clip.delete", {"track": 0, "arrangement_clip": 0})
    clips = (await client.call("arrangement.get", {"track": 0}))["tracks"][0]["clips"]
    assert [c["start"] for c in clips] == [8.0]


async def test_one_edit_is_one_undo_step(client, live):
    before = live.on_main(lambda: live.song.undo_steps)
    await client.call("arrangement.edit", {"actions": [
        {"action": "add_clip", "track": 0, "start": 0, "length": 4},
        {"action": "add_clip", "track": 1, "start": 0, "length": 4},
    ]})
    assert live.on_main(lambda: live.song.undo_steps) == before + 1


async def test_audio_tracks_get_no_midi_clips(client):
    audio = (await client.call("track.create", {"kind": "audio"}))["track"]
    with pytest.raises(BridgeError) as exc:
        await client.call("arrangement.edit", {"actions": [{"action": "add_clip", "track": audio, "start": 0, "length": 4}]})
    assert exc.value.code == "INVALID_PARAMS"


def test_core_checks_clip_addressing_and_actions():
    with pytest.raises(ValidationError):
        ClipRef(track=0)
    with pytest.raises(ValidationError):
        ClipRef(track=0, slot=0, arrangement_clip=0)
    with pytest.raises(ValidationError):
        ArrangementEdit(actions=[{"action": "move_clip", "track": 0}])
    with pytest.raises(ValidationError):
        ArrangementEdit(actions=[{"action": "add_clip", "track": 0, "start": 0, "length": 0}])
    with pytest.raises(ValidationError):
        ArrangementEdit(actions=[{"action": "set_locator", "time": 0}])  # locators go to arrangement.locators


async def test_edit_arrangement_keeps_the_play_position(client, live):
    from midibakery.mcp import build_server

    live.on_main(lambda: setattr(live.song, "current_song_time", 12.0))
    await client.call("clip.create", {"track": 0, "slot": 0, "length": 8})
    await build_server(client).call_tool("edit_arrangement", {"actions": [{"action": "copy_session_clip", "track": 0, "slot": 0, "start": 64}]})
    assert (await client.call("song.get"))["current_song_time"] == 12.0  # Live moved it to 72; the tool put it back


def _with_filter(song, full=False):
    track = song.tracks[0]
    track.insert_device("Auto Filter", 0)
    for slot in track.clip_slots if full else track.clip_slots[:1]:
        slot.create_clip(4)  # the user's clips stay
    return len(song.scenes)


async def test_clip_automation_goes_through_a_session_slot(client, live):
    live.on_main(lambda: _with_filter(live.song))
    result = await client.call("arrangement.edit", {"actions": [{
        "action": "add_clip", "track": 0, "start": 8, "length": 8, "name": "Sweep", "color_index": 5, "notes": [KICK],
        "envelopes": [{"device": 0, "parameter": "Filter Freq", "points": [[0, 0.0], [8, 1.0]]}],
    }]})
    assert result["results"][0]["envelopes"] == 1 and result["results"][0]["envelope_mode"] == "events"

    def check():
        track = live.song.tracks[0]
        clip = track.arrangement_clips[0]
        envelope = clip.envelopes[id(track.devices[0].parameters[2])]  # Filter Freq, 20-20000 (hidden from scripts in Live)
        return (
            (clip.name, clip.start_time, clip.end_time, clip.color_index, len(clip.notes)),
            [envelope.value_at_time(t) for t in (0, 4, 8)],
            [slot.has_clip for slot in track.clip_slots[:3]],
        )

    clip, values, slots = live.on_main(check)
    assert clip == ("Sweep", 8.0, 16.0, 5, 1)
    assert values == [20.0, pytest.approx(10010.0), 20000.0]
    assert slots == [True, False, False]


async def test_a_full_track_gets_a_scene_for_the_automation_and_loses_it_again(client, live):
    scenes = live.on_main(lambda: _with_filter(live.song, full=True))
    await client.call("arrangement.edit", {"actions": [{
        "action": "add_clip", "track": 0, "start": 0, "length": 4,
        "envelopes": [{"device": 0, "parameter": "Device On", "points": [[0, 1], [2, 0]]}],
    }]})

    def check():
        track = live.song.tracks[0]
        envelope = track.arrangement_clips[0].envelopes[id(track.devices[0].parameters[0])]
        return len(live.song.scenes), len(track.clip_slots), [envelope.value_at_time(t) for t in (0, 3)]

    assert live.on_main(check) == (scenes, scenes, [1.0, 0.0])  # a quantized parameter steps


async def test_automation_of_an_unknown_parameter_changes_nothing(client, live):
    live.on_main(lambda: _with_filter(live.song))
    with pytest.raises(BridgeError) as exc:
        await client.call("arrangement.edit", {"actions": [{
            "action": "add_clip", "track": 0, "start": 0, "length": 4,
            "envelopes": [{"device": 0, "parameter": "Cutoff", "points": [[0, 0.5]]}],
        }]})
    assert exc.value.code == "NOT_FOUND" and "Cutoff" in str(exc.value)
    track = live.on_main(lambda: live.song.tracks[0])
    assert live.on_main(lambda: (len(track.arrangement_clips), sum(s.has_clip for s in track.clip_slots))) == (0, 1)


async def test_swap_and_move_arrangement_clips(client, live):
    # "swap Intro Bass and Drop Bass": a model rebuilt both clips by hand and failed four times
    await client.call("arrangement.edit", {"actions": [
        {"action": "add_clip", "track": 0, "start": 0, "length": 16, "name": "Intro Bass", "notes": [KICK]},
        {"action": "add_clip", "track": 0, "start": 16, "length": 8, "name": "Break"},
        {"action": "add_clip", "track": 0, "start": 32, "length": 16, "name": "Drop Bass", "notes": [{**KICK, "pitch": 45}, {**KICK, "start_time": 2.0}]},
    ]})
    await client.call("arrangement.edit", {"actions": [{"action": "swap_clips", "track": 0, "clip": 2, "with_clip": 0}]})
    clips = (await client.call("arrangement.get", {}))["tracks"][0]["clips"]
    assert [(c["name"], c["start"], c["end"]) for c in clips] == [("Drop Bass", 0.0, 16.0), ("Break", 16.0, 24.0), ("Intro Bass", 32.0, 48.0)]
    notes = (await client.call("notes.get", {"track": 0, "arrangement_clip": 0}))["notes"]
    assert sorted((n["pitch"], n["start_time"]) for n in notes) == [(36, 2.0), (45, 0.0)]

    await client.call("arrangement.edit", {"actions": [{"action": "move_clip", "track": 0, "clip": 1, "start": 24}]})
    clips = (await client.call("arrangement.get", {}))["tracks"][0]["clips"]
    assert [(c["name"], c["start"]) for c in clips] == [("Drop Bass", 0.0), ("Break", 24.0), ("Intro Bass", 32.0)]
    # a move onto another clip changes nothing
    with pytest.raises(BridgeError, match="already 'Intro Bass'"):
        await client.call("arrangement.edit", {"actions": [{"action": "move_clip", "track": 0, "clip": 1, "start": 30}]})
    assert len((await client.call("arrangement.get", {}))["tracks"][0]["clips"]) == 3
    # clips of different lengths that would overlap after a swap: nothing is lifted
    with pytest.raises(BridgeError, match="already 'Intro Bass'"):  # Drop Bass at 24-40
        await client.call("arrangement.edit", {"actions": [{"action": "swap_clips", "track": 0, "clip": 1, "with_clip": 0}]})
    assert [c["name"] for c in (await client.call("arrangement.get", {}))["tracks"][0]["clips"]] == ["Drop Bass", "Break", "Intro Bass"]


def test_delete_clip_takes_arrangement_clip_like_every_other_tool():
    edit = ArrangementEdit.model_validate({"actions": [{"action": "delete_clip", "track": 0, "arrangement_clip": 1}]})
    assert edit.model_dump()["actions"][0]["clip"] == 1


async def test_clip_ops_take_arrangement_clips_by_name(client):
    # qwen: get_clip {"arrangement_clip": "Breakdown Bass"}, like compose and transform_notes take it
    await client.call("arrangement.edit", {"actions": [
        {"action": "add_clip", "track": 0, "start": 0, "length": 4, "name": "Intro Bass"},
        {"action": "add_clip", "track": 0, "start": 8, "length": 4, "name": "Drop Bass"},
    ]})
    await client.call("clip.set", {"track": 0, "arrangement_clip": "drop bass", "name": "Main Bass"})
    assert (await client.call("clip.get", {"track": 0, "arrangement_clip": "Main"}))["start_time"] == 8.0
    await client.call("batch", {"ops": [{"op": "clip.delete", "params": {"track": 0, "arrangement_clip": "Intro Bass"}}]})
    assert [c["name"] for c in (await client.call("arrangement.get", {}))["tracks"][0]["clips"]] == ["Main Bass"]
    with pytest.raises(BridgeError, match="No arrangement clip named 'Outro'.*0 'Main Bass'"):
        await client.call("clip.get", {"track": 0, "arrangement_clip": "Outro"})


async def test_a_failed_edit_arrangement_takes_back_clips_and_locators(client, live):
    from midibakery.mcp import build_server

    await client.call("arrangement.locators", {"actions": [{"action": "set_locator", "time": 0, "name": "Intro"}]})
    before = live.on_main(lambda: live.song.undo_calls)
    with pytest.raises(Exception) as exc:
        await build_server(client).call_tool("edit_arrangement", {"actions": [
            {"action": "set_locator", "time": 0, "name": "Start"},
            {"action": "set_locator", "time": 32, "name": "Drop"},
            {"action": "add_clip", "track": 0, "start": 0, "length": 4},
            {"action": "add_clip", "track": 99, "start": 0, "length": 4},
        ]})
    assert "were undone" in str(exc.value) and "locators were put back" in str(exc.value)
    assert live.on_main(lambda: live.song.undo_calls) == before + 1  # the clip edit; locators are restored, not undone
    assert [(l["name"], l["time"]) for l in (await client.call("arrangement.get", {}))["locators"]] == [("Intro", 0.0)]


async def test_failing_locators_change_nothing(client, live):
    from midibakery.mcp import build_server

    with pytest.raises(Exception) as exc:
        await build_server(client).call_tool("edit_arrangement", {"actions": [
            {"action": "add_clip", "track": 0, "start": 0, "length": 4},
            {"action": "set_locator", "time": 16, "name": "Drop"},
            {"action": "delete_locator", "time": 48},  # there is none
        ]})
    assert "NOT_FOUND" in str(exc.value) or "No locator" in str(exc.value)
    arrangement = await client.call("arrangement.get", {})
    assert arrangement["locators"] == [] and arrangement["tracks"][0]["clips"] == []  # the clips come after the locators
