"""MCP client round trips: confirmation of destructive changes and the piano-roll app."""

import json

import pytest
from mcp import Client
from mcp_types import ElicitResult

from midishower.mcp import build_server
from midishower.mcp.server import PIANO_ROLL_URI


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


@pytest.mark.parametrize("mode", ["auto", "legacy"])
async def test_delete_asks_and_runs_on_accept(client, live, mode):
    answer = Answer()
    async with Client(build_server(client), mode=mode, elicitation_callback=answer) as mcp:
        result = await mcp.call_tool("delete_track", {"track": 1})
    assert not result.is_error
    assert answer.messages == ["Delete track 2 '2-MIDI' with 0 clip(s)?"]
    assert _tracks(live) == ["1-MIDI"]


@pytest.mark.parametrize("answer", [Answer("decline"), Answer("cancel"), Answer("accept", confirm=False)], ids=["decline", "cancel", "unchecked"])
async def test_delete_is_cancelled_when_user_says_no(client, live, answer):
    async with Client(build_server(client), elicitation_callback=answer) as mcp:
        result = await mcp.call_tool("delete_track", {"track": 0})
    assert result.is_error and "CANCELLED" in result.content[0].text
    assert _tracks(live) == ["1-MIDI", "2-MIDI"]


async def test_clients_without_elicitation_are_not_asked(client, live):
    async with Client(build_server(client)) as mcp:
        result = await mcp.call_tool("delete_track", {"track": 0})
    assert not result.is_error
    assert _tracks(live) == ["2-MIDI"]


async def test_batch_with_delete_asks_once(client, live):
    await client.call("clip.create", {"track": 0, "slot": 0, "length": 4, "name": "Riff"})
    answer = Answer()
    async with Client(build_server(client), elicitation_callback=answer) as mcp:
        result = await mcp.call_tool("run_batch", {"ops": [
            {"op": "song.set", "params": {"tempo": 100}},
            {"op": "clip.delete", "params": {"track": 0, "slot": 0}},
        ]})
    assert not result.is_error
    assert len(answer.messages) == 1 and "delete clip 'Riff' in slot 1" in answer.messages[0]


async def test_edits_without_removals_are_not_asked(client, live):
    answer = Answer()
    async with Client(build_server(client), elicitation_callback=answer) as mcp:
        assert not (await mcp.call_tool("compose_drums", {"track": 0, "slot": 0, "seed": 1})).is_error
        assert not (await mcp.call_tool("compose_drums", {"track": 0, "slot": 0, "seed": 2, "if_exists": "merge"})).is_error
    assert answer.messages == []


async def test_replace_asks_and_keeps_the_same_idea_across_the_round_trip(client, live):
    answer = Answer()
    async with Client(build_server(client), elicitation_callback=answer) as mcp:
        await mcp.call_tool("compose_chords", {"track": 1, "slot": 0, "seed": 3})
        before = len(_notes(live, 1, 0))
        result = await mcp.call_tool("compose_melody", {"track": 1, "slot": 0, "if_exists": "replace"})
    assert not result.is_error
    assert answer.messages == [f"Replace {before} existing note(s) in track 2 slot 1?"]
    change = result.structured_content["changes"][0]
    # The seed drawn on the first round is reused after the confirmation, so the
    # notes written are exactly the ones the result reports.
    roll = result.meta["midishower/roll"]["clips"][0]
    written = sorted((n["pitch"], n["start_time"]) for n in _notes(live, 1, 0))
    assert written == sorted((n[0], n[1]) for n in roll["add"])
    assert change["seed"] == result.structured_content["applied"][0]["seed"]


async def test_apply_plan_with_replacement_asks(client, live):
    await client.call("clip.create", {"track": 0, "slot": 0, "length": 4})
    await client.call("notes.apply", {"track": 0, "slot": 0, "add": [{"pitch": 60, "start_time": 0, "duration": 1}]})
    declined = Answer("decline")
    server = build_server(client)
    async with Client(server, elicitation_callback=declined) as mcp:
        plan = (await mcp.call_tool("plan_changes", {"steps": [
            {"kind": "drums", "track": 0, "slot": 0, "seed": 1, "if_exists": "replace"},
        ]})).structured_content
        assert (await mcp.call_tool("apply_plan", {"plan_id": plan["plan_id"]})).is_error
    assert len(_notes(live, 0, 0)) == 1
    async with Client(server, elicitation_callback=Answer()) as mcp:
        # Declining keeps the plan, so it can still be applied later.
        assert not (await mcp.call_tool("apply_plan", {"plan_id": plan["plan_id"]})).is_error
    assert len(_notes(live, 0, 0)) == plan["changes"][0]["add"]


async def test_piano_roll_app(client, live):
    async with Client(build_server(client)) as mcp:
        tools = {t.name: t for t in (await mcp.list_tools()).tools}
        for name in ("compose_drums", "compose_bass", "compose_chords", "compose_melody", "transform_notes", "plan_changes"):
            assert tools[name].meta["ui"]["resourceUri"] == PIANO_ROLL_URI
        resource = await mcp.read_resource(PIANO_ROLL_URI)
        html = resource.contents[0].text
        assert resource.contents[0].mime_type == "text/html;profile=mcp-app"
        assert "ui/initialize" in html and "apply_plan" in html

        await client.call("clip.create", {"track": 1, "slot": 0, "length": 4})
        await client.call("notes.apply", {"track": 1, "slot": 0, "add": [
            {"pitch": 60, "start_time": 0.1, "duration": 1}, {"pitch": 64, "start_time": 1, "duration": 1},
        ]})
        result = await mcp.call_tool("transform_notes", {"track": 1, "slot": 0, "operation": "quantize", "preview": True})
        roll = result.meta["midishower/roll"]
        assert roll["applied"] is False and roll["plan_id"] == result.structured_content["plan_id"]
        clip = roll["clips"][0]
        assert clip["length"] == 4 and len(clip["existing"]) == 2
        assert clip["modify"] == [{"note_id": clip["existing"][0][0], "start_time": 0.0}]
        assert json.loads(result.content[0].text)["changes"][0]["modify"] == 1
