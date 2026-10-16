"""Composition through the real Remote Script and the MCP server, against the fake LOM."""

import json

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from fake_song import DrumRackDevice, RackDevice, Chain
from midibakery.bridge import BridgeError
from midibakery.compose import DrumsSpec, apply_plan, build_plan
from midibakery.compose.theory import Scale
from midibakery.mcp import build_server

KIT = {"Kick 909": 36, "Clap": 39, "Snare": 40, "Closed HH": 44, "Open HH": 46}


def _payload(result):
    return json.loads(result.content[0].text)


def _add_kit(live, track=0, legacy=False, nested=False):
    def build():
        rack = DrumRackDevice(legacy=legacy)
        for name, note in KIT.items():
            rack.add_pad(name, note)
        device = RackDevice("Instrument Rack", [Chain("Chain", [rack])]) if nested else rack
        live.song.tracks[track].devices.append(device)

    live.on_main(build)


def _clip_notes(live, track, slot):
    return live.on_main(lambda: sorted(live.song.tracks[track].clip_slots[slot].clip.notes.values(), key=lambda n: (n["start_time"], n["pitch"])))


# --------------------------------------------------------------------------
# drum_rack.pads op
# --------------------------------------------------------------------------


@pytest.mark.parametrize("legacy,nested", [(False, False), (True, False), (False, True)], ids=["in_note", "drum_pads", "nested"])
async def test_drum_rack_pads(client, live, legacy, nested):
    _add_kit(live, legacy=legacy, nested=nested)
    result = await client.call("drum_rack.pads", {"track": 0})
    assert [(p["name"], p["note"]) for p in result["pads"]] == sorted(KIT.items(), key=lambda kv: kv[1])


async def test_drum_rack_pads_errors(client, live):
    with pytest.raises(BridgeError) as exc:
        await client.call("drum_rack.pads", {"track": 0})
    assert exc.value.code == "NOT_FOUND"
    await client.call("device.insert", {"track": 0, "name": "Drift"})
    with pytest.raises(BridgeError) as exc:
        await client.call("drum_rack.pads", {"track": 0, "device": 0})
    assert exc.value.code == "INVALID_PARAMS"


# --------------------------------------------------------------------------
# Plan / apply
# --------------------------------------------------------------------------


async def test_plan_does_not_touch_live_and_apply_is_one_undo_step(client, live):
    _add_kit(live)
    plan = await build_plan(client.call, [DrumsSpec(track=0, slot=0, bars=2, seed=7, style="house")])
    assert live.on_main(lambda: live.song.tracks[0].clip_slots[0].has_clip) is False
    preview = plan.preview()
    change = preview["changes"][0]
    assert change["action"] == "create clip" and change["drum_map"] == "drum_rack"
    assert change["pads"]["kick"] == 36 and change["pads"]["clap"] == 39 and change["pads"]["open_hat"] == 46

    steps_before = live.on_main(lambda: live.song.undo_steps)
    result = await apply_plan(client.call, plan)
    assert live.on_main(lambda: live.song.undo_steps) == steps_before + 1
    notes = _clip_notes(live, 0, 0)
    assert len(notes) == change["add"] == len(result["applied"][0]["added_note_ids"])
    assert {n["pitch"] for n in notes} <= set(KIT.values())
    assert all(n["start_time"] < 8 for n in notes)


async def test_same_seed_same_notes(client, live):
    plans = [await build_plan(client.call, [DrumsSpec(track=0, slot=s, seed=99, style="trap")]) for s in (0, 1)]
    a, b = (p.changes[0].add for p in plans)
    assert a == b


async def test_apply_detects_conflicts(client, live):
    plan = await build_plan(client.call, [DrumsSpec(track=0, slot=0, seed=1)])
    await client.call("clip.create", {"track": 0, "slot": 0, "length": 4})
    with pytest.raises(BridgeError) as exc:
        await apply_plan(client.call, plan)
    assert exc.value.code == "CONFLICT"


# --------------------------------------------------------------------------
# MCP tools
# --------------------------------------------------------------------------


async def test_compose_tools_are_listed_and_annotated():
    tools = {t.name: t for t in await build_server().list_tools()}
    assert len(tools) <= 36  # the real guard is the character budget in test_agent (local models)
    for name in ("compose_drums", "compose_bass", "compose_chords", "compose_melody", "transform_notes", "apply_plan"):
        assert tools[name].annotations.read_only_hint is False
        assert tools[name].annotations.destructive_hint is True
    assert tools["plan_changes"].annotations.read_only_hint is True
    assert tools["get_drum_pads"].annotations.read_only_hint is True
    assert "kind" not in tools["compose_drums"].input_schema["properties"]
    assert "preview" in tools["compose_melody"].input_schema["properties"]


async def test_plan_changes_schema_stays_small_but_steps_are_still_checked(client):
    server = build_server(client)
    tools = {t.name: t for t in await server.list_tools()}
    assert len(json.dumps(tools["plan_changes"].input_schema)) < 1500  # kind + free fields, not every compose schema
    with pytest.raises(ToolError) as exc:
        await server.call_tool("plan_changes", {"steps": [{"kind": "bass", "track": 0, "slot": 0, "styel": "walking"}]})
    assert "styel" in str(exc.value)


async def test_full_song_sketch_via_plan_changes(client, live):
    server = build_server(client)
    await client.call("song.set", {"root_note": 9, "scale_name": "Minor"})
    live.on_main(lambda: setattr(live.song, "scale_intervals", (0, 2, 3, 5, 7, 8, 10)))
    _add_kit(live)

    plan = _payload(await server.call_tool("plan_changes", {"steps": [
        {"kind": "drums", "track": 0, "slot": 0, "bars": 4, "seed": 1},
        {"kind": "chords", "track": 1, "slot": 0, "bars": 4, "seed": 2, "progression": "i VI III VII"},
        {"kind": "bass", "track": 1, "slot": 1, "bars": 4, "seed": 3, "follow_kick": {"track": 0, "slot": 0}},
        {"kind": "melody", "track": 1, "slot": 2, "bars": 4, "seed": 4},
    ]}))
    assert plan["scale"] == "A Minor"
    assert [c["action"] for c in plan["changes"]] == ["create clip"] * 4
    chords, bass, melody = plan["changes"][1:]
    assert chords["chords"] == bass["chords"] == melody["chords"]  # later steps share the chords
    assert bass["kick_pitch"] == 36 and bass["kick_hits"] >= 16
    assert live.on_main(lambda: live.song.tracks[1].clip_slots[0].has_clip) is False

    undo_before = live.on_main(lambda: live.song.undo_steps)
    applied = _payload(await server.call_tool("apply_plan", {"plan_id": plan["plan_id"]}))
    assert len(applied["applied"]) == 4
    assert live.on_main(lambda: live.song.undo_steps) == undo_before + 1

    scale = Scale(9, (0, 2, 3, 5, 7, 8, 10))
    for slot in (0, 1, 2):
        notes = _clip_notes(live, 1, slot)
        assert notes and all(scale.contains(n["pitch"]) for n in notes)
        assert all(0 <= n["start_time"] < 16 for n in notes)
    kicks = {n["start_time"] for n in _clip_notes(live, 0, 0) if n["pitch"] == 36}
    assert {n["start_time"] for n in _clip_notes(live, 1, 1)} <= kicks | {0.0, 4.0, 8.0, 12.0}

    with pytest.raises(ToolError, match="NOT_FOUND"):
        await server.call_tool("apply_plan", {"plan_id": plan["plan_id"]})


async def test_compose_preview_then_apply_and_if_exists(client, live):
    server = build_server(client)
    preview = _payload(await server.call_tool("compose_chords", {"track": 1, "slot": 0, "seed": 5, "preview": True}))
    assert live.on_main(lambda: live.song.tracks[1].clip_slots[0].has_clip) is False
    await server.call_tool("apply_plan", {"plan_id": preview["plan_id"]})
    assert len(_clip_notes(live, 1, 0)) == preview["changes"][0]["add"]

    with pytest.raises(ToolError, match="CONFLICT"):
        await server.call_tool("compose_chords", {"track": 1, "slot": 0, "seed": 6})
    replaced = _payload(await server.call_tool("compose_melody", {"track": 1, "slot": 0, "seed": 6, "if_exists": "replace"}))
    change = replaced["changes"][0]
    assert change["action"] == "replace notes" and change["remove"] == preview["changes"][0]["add"]
    assert len(_clip_notes(live, 1, 0)) == change["add"]


async def test_bass_follows_chords_from_existing_clip(client, live):
    server = build_server(client)
    await server.call_tool("compose_chords", {"track": 1, "slot": 0, "seed": 1, "progression": "vi IV I V"})
    bass = _payload(await server.call_tool("compose_bass", {
        "track": 1, "slot": 1, "seed": 1, "style": "sustained", "chords_from": {"track": 1, "slot": 0},
    }))
    assert bass["changes"][0]["chords_source"] == "clip"
    assert [c.split(" ")[0] for c in bass["changes"][0]["chords"]] == ["Am", "F", "C", "G"]
    assert [n["pitch"] % 12 for n in _clip_notes(live, 1, 1)] == [9, 5, 0, 7]


async def test_transform_notes_is_a_diff(client, live):
    server = build_server(client)
    await client.call("clip.create", {"track": 1, "slot": 0, "length": 4})
    ids = (await client.call("notes.apply", {"track": 1, "slot": 0, "add": [
        {"pitch": 60, "start_time": 0.0, "duration": 1, "probability": 0.5},
        {"pitch": 64, "start_time": 1.07, "duration": 1},
        {"pitch": 67, "start_time": 2.0, "duration": 1},
    ]}))["added"]

    result = _payload(await server.call_tool("transform_notes", {"track": 1, "slot": 0, "operation": "quantize"}))
    change = result["changes"][0]
    assert (change["add"], change["modify"], change["remove"]) == (0, 1, 0)
    notes = _clip_notes(live, 1, 0)
    assert [n["start_time"] for n in notes] == [0.0, 1.0, 2.0]
    assert notes[0]["probability"] == 0.5  # untouched note kept its data
    assert set(live.on_main(lambda: live.song.tracks[1].clip_slots[0].clip.notes)) == set(ids)

    await server.call_tool("transform_notes", {"track": 1, "slot": 0, "operation": "transpose", "steps": 1, "note_ids": [ids[2]]})
    assert [n["pitch"] for n in _clip_notes(live, 1, 0)] == [60, 64, 69]

    with pytest.raises(ToolError, match="NOT_FOUND"):
        await server.call_tool("transform_notes", {"track": 1, "slot": 0, "operation": "invert", "note_ids": [9999]})


async def test_transform_semitones_is_chromatic(client, live):
    server = build_server(client)
    await client.call("clip.create", {"track": 1, "slot": 0, "length": 4})
    await client.call("notes.apply", {"track": 1, "slot": 0, "add": [
        {"pitch": 60, "start_time": 0.0, "duration": 1}, {"pitch": 64, "start_time": 1.0, "duration": 1},
    ]})
    await server.call_tool("transform_notes", {"track": 1, "slot": 0, "operation": "transpose", "semitones": 2})
    assert [n["pitch"] for n in _clip_notes(live, 1, 0)] == [62, 66]
    plan = _payload(await server.call_tool("plan_changes", {"steps": [
        {"kind": "transform", "track": 1, "slot": 0, "operation": "transpose", "semitones": -2},
    ]}))
    assert plan["changes"][0]["modify"] == 2
    with pytest.raises(ToolError, match="semitones"):
        await server.call_tool("transform_notes", {"track": 1, "slot": 0, "operation": "transpose"})


async def test_chords_from_rejects_a_drum_track(client, live):
    _add_kit(live, track=0)
    server = build_server(client)
    await server.call_tool("compose_drums", {"track": 0, "slot": 0, "seed": 1})
    await server.call_tool("compose_chords", {"track": 1, "slot": 0, "seed": 1})
    with pytest.raises(ToolError, match="drum track") as exc:
        await server.call_tool("compose_bass", {"track": 1, "slot": 1, "chords_from": {"track": 0, "slot": 0}})
    assert "1 '2-MIDI'" in str(exc.value)  # points at the track that has a chord clip
    await server.call_tool("compose_bass", {"track": 1, "slot": 1, "seed": 2, "chords_from": {"track": 1, "slot": 0}})


async def test_apply_detects_shifted_tracks(client, live):
    plan = await build_plan(client.call, [DrumsSpec(track=1, slot=0, seed=1)])
    # A new, empty track with the same name and kind takes index 1: only the track id differs.
    await client.call("track.create", {"kind": "midi", "index": 1, "name": "2-MIDI"})
    with pytest.raises(BridgeError) as exc:
        await apply_plan(client.call, plan)
    assert exc.value.code == "CONFLICT"
    await client.call("track.delete", {"track": 0})
    await client.call("track.delete", {"track": 0})
    with pytest.raises(BridgeError) as exc:  # index 1 no longer exists
        await apply_plan(client.call, plan)
    assert exc.value.code == "CONFLICT"


async def test_failed_batch_is_rolled_back(client, live):
    plan = await build_plan(client.call, [DrumsSpec(track=0, slot=0, seed=1), DrumsSpec(track=1, slot=0, seed=2)])
    await client.call("clip.create", {"track": 1, "slot": 0, "length": 4})  # second clip.create will now fail
    undo_before = live.on_main(lambda: live.song.undo_calls)
    with pytest.raises(BridgeError) as exc:
        await apply_plan(client.call, plan, verify=False)
    assert exc.value.code == "CONFLICT" and exc.value.details["rolled_back"] is True
    assert "undone" in exc.value.message
    assert live.on_main(lambda: live.song.undo_calls) == undo_before + 1


async def test_failure_on_first_op_does_not_undo(client, live):
    plan = await build_plan(client.call, [DrumsSpec(track=0, slot=0, seed=1)])
    await client.call("clip.create", {"track": 0, "slot": 0, "length": 4})
    undo_before = live.on_main(lambda: live.song.undo_calls)
    with pytest.raises(BridgeError) as exc:
        await apply_plan(client.call, plan, verify=False)
    assert "rolled_back" not in exc.value.details
    assert live.on_main(lambda: live.song.undo_calls) == undo_before


async def test_compose_without_slot_takes_the_first_free_one(client, live):
    server = build_server(client)
    await client.call("clip.create", {"track": 1, "slot": 0, "length": 4})
    await client.call("clip.create", {"track": 1, "slot": 2, "length": 4})
    result = _payload(await server.call_tool("compose_chords", {"track": 1, "seed": 1}))
    assert result["changes"][0]["slot"] == 1
    plan = await build_plan(client.call, [DrumsSpec(track=1, seed=1), DrumsSpec(track=1, seed=2)])
    assert [c.slot for c in plan.changes] == [3, 4]
    for slot in range(3, 8):
        await client.call("clip.create", {"track": 1, "slot": slot, "length": 4})
    with pytest.raises(ToolError, match="no free clip slot"):
        await server.call_tool("compose_chords", {"track": 1})
