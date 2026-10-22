"""MCP client round trips: confirmation of destructive changes."""

import json

import pytest
from mcp import Client
from mcp_types import ElicitResult

from midibakery.mcp import build_server


class Answer:
    """Elicitation callback that records the questions and gives a fixed answer."""

    def __init__(self, action="accept", confirm=True):
        self.action = action
        self.confirm = confirm
        self.messages = []

    async def __call__(self, context, params):
        self.messages.append(params.message)
        content = {"confirm": self.confirm} if self.action == "accept" else None
        return ElicitResult(action=self.action, content=content)


def _tracks(live):
    return live.on_main(lambda: [t.name for t in live.song.tracks])


def _notes(live, track, slot):
    return live.on_main(lambda: list(live.song.tracks[track].clip_slots[slot].clip.notes.values()))


def _clips(live, track):
    return live.on_main(lambda: [s.has_clip for s in live.song.tracks[track].clip_slots][:2])


ASKED = "Delete clip 'Riff' in slot 1 of track 1 '1-MIDI'?"


@pytest.mark.parametrize("mode", ["auto", "legacy"])
async def test_delete_asks_and_runs_on_accept(client, live, mode):
    await client.call("clip.create", {"track": 0, "slot": 0, "length": 4, "name": "Riff"})
    answer = Answer()
    async with Client(build_server(client), mode=mode, elicitation_callback=answer) as mcp:
        result = await mcp.call_tool("delete_clip", {"track": 0, "slot": 0})
    assert not result.is_error
    assert answer.messages == [ASKED]
    assert _clips(live, 0) == [False, False]


@pytest.mark.parametrize("answer", [Answer("decline"), Answer("cancel"), Answer("accept", confirm=False)], ids=["decline", "cancel", "unchecked"])
async def test_delete_is_cancelled_when_user_says_no(client, live, answer):
    await client.call("clip.create", {"track": 0, "slot": 0, "length": 4, "name": "Riff"})
    async with Client(build_server(client), elicitation_callback=answer) as mcp:
        result = await mcp.call_tool("delete_clip", {"track": 0, "slot": 0})
    assert result.is_error and "CANCELLED" in result.content[0].text
    assert _clips(live, 0) == [True, False]


async def test_clients_without_elicitation_get_a_plan_instead(client, live):
    await client.call("clip.create", {"track": 0, "slot": 0, "length": 4, "name": "Riff"})
    async with Client(build_server(client)) as mcp:
        result = await mcp.call_tool("delete_clip", {"track": 0, "slot": 0})
        assert not result.is_error and _clips(live, 0) == [True, False]  # nothing deleted yet
        pending = json.loads(result.content[0].text)
        assert pending["not_applied"] == ASKED and "apply_plan" in pending["next"]
        assert not (await mcp.call_tool("apply_plan", {"plan_id": pending["plan_id"]})).is_error
    assert _clips(live, 0) == [False, False]


async def test_a_deferred_delete_is_refused_when_the_tracks_changed(client, live):
    await client.call("clip.create", {"track": 1, "slot": 0, "length": 4, "name": "Riff"})
    async with Client(build_server(client)) as mcp:
        pending = json.loads((await mcp.call_tool("delete_clip", {"track": 1, "slot": 0})).content[0].text)
        await client.call("track.delete", {"track": 0})  # index 1 is gone, '2-MIDI' is index 0 now
        result = await mcp.call_tool("apply_plan", {"plan_id": pending["plan_id"]})
    assert result.is_error and "CONFLICT" in result.content[0].text
    assert _clips(live, 0) == [True, False]


async def test_replacing_without_elicitation_waits_for_apply_plan(client, live):
    async with Client(build_server(client)) as mcp:
        await mcp.call_tool("compose", {"kind": "chords", "track": 1, "slot": 0, "seed": 3})
        before = _notes(live, 1, 0)
        result = await mcp.call_tool("compose", {"kind": "melody", "track": 1, "slot": 0, "seed": 4, "if_exists": "replace"})
        assert not result.is_error and _notes(live, 1, 0) == before
        assert result.structured_content["not_applied"] == f"Replace {len(before)} existing note(s) in track 2 slot 1?"
        assert not (await mcp.call_tool("apply_plan", {"plan_id": result.structured_content["plan_id"]})).is_error
    assert _notes(live, 1, 0) != before


async def test_edits_without_removals_are_not_asked(client, live):
    answer = Answer()
    async with Client(build_server(client), elicitation_callback=answer) as mcp:
        assert not (await mcp.call_tool("compose", {"kind": "drums", "track": 0, "slot": 0, "seed": 1})).is_error
        assert not (await mcp.call_tool("compose", {"kind": "drums", "track": 0, "slot": 0, "seed": 2, "if_exists": "merge"})).is_error
    assert answer.messages == []


async def test_replace_asks_and_keeps_the_same_idea_across_the_round_trip(client, live):
    answer = Answer()
    async with Client(build_server(client), elicitation_callback=answer) as mcp:
        await mcp.call_tool("compose", {"kind": "chords", "track": 1, "slot": 0, "seed": 3})
        before = len(_notes(live, 1, 0))
        result = await mcp.call_tool("compose", {"kind": "melody", "track": 1, "slot": 0, "if_exists": "replace"})
    assert not result.is_error
    assert answer.messages == [f"Replace {before} existing note(s) in track 2 slot 1?"]
    change = result.structured_content["changes"][0]
    # The seed drawn on the first round is reused after the confirmation, so the
    # notes written are exactly the ones the result reports.
    roll = result.meta["midibakery/roll"]["clips"][0]
    written = sorted((n["pitch"], n["start_time"]) for n in _notes(live, 1, 0))
    assert written == sorted((n[0], n[1]) for n in roll["add"])
    assert change["seed"] == result.structured_content["applied"][0]["seed"]


async def test_apply_plan_with_replacement_asks(client, live):
    await client.call("clip.create", {"track": 0, "slot": 0, "length": 4})
    await client.call("notes.apply", {"track": 0, "slot": 0, "add": [{"pitch": 60, "start_time": 0, "duration": 1}]})
    declined = Answer("decline")
    server = build_server(client)
    async with Client(server, elicitation_callback=declined) as mcp:
        plan = (await mcp.call_tool("compose", {"kind": "drums", "track": 0, "slot": 0, "seed": 1, "if_exists": "replace",
                                                "preview": True})).structured_content
        assert (await mcp.call_tool("apply_plan", {"plan_id": plan["plan_id"]})).is_error
    assert len(_notes(live, 0, 0)) == 1
    async with Client(server, elicitation_callback=Answer()) as mcp:
        # Declining keeps the plan, so it can still be applied later.
        assert not (await mcp.call_tool("apply_plan", {"plan_id": plan["plan_id"]})).is_error
    assert len(_notes(live, 0, 0)) == plan["changes"][0]["add"]


async def test_replacing_an_arrangement_clip_asks_with_its_name(client, live):
    await client.call("arrangement.edit", {"actions": [{"action": "add_clip", "track": 1, "start": 0, "length": 16}]})
    await client.call("notes.apply", {"track": 1, "arrangement_clip": 0, "add": [{"pitch": 33, "start_time": 0.0, "duration": 1}]})
    answer = Answer(confirm=False)
    async with Client(build_server(client), elicitation_callback=answer) as mcp:
        result = await mcp.call_tool("compose", {"kind": "bass", "track": 1, "arrangement_clip": 0})
    assert result.is_error and "CANCELLED" in result.content[0].text
    assert answer.messages == ["Replace 1 existing note(s) in track 2 arrangement clip 1?"]
