import json

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from midibakery.mcp import build_server


def _payload(result):
    return json.loads(result.content[0].text)


async def test_tool_list_is_small_and_annotated():
    server = build_server()
    tools = {t.name: t for t in await server.list_tools()}
    assert len(tools) <= 39  # the real guard is the character budget in test_agent (local models)
    assert tools["get_session"].annotations.read_only_hint is True
    assert tools["delete_track"].annotations.destructive_hint is True
    assert "note_id" in json.dumps(tools["edit_notes"].input_schema)


async def test_get_session_and_edit_notes_through_mcp(client, live):
    server = build_server(client)
    session = _payload(await server.call_tool("get_session", {}))
    assert session["song"]["scale_name"] == "Major"
    assert len(session["tracks"]) == 2

    await server.call_tool("create_clip", {"track": 1, "slot": 0, "length": 4})
    await server.call_tool("edit_notes", {
        "track": 1, "slot": 0,
        "add": [{"pitch": 60, "start_time": 0, "duration": 0.5}, {"pitch": 62, "start_time": 0.5, "duration": 0.5}],
    })
    clip = _payload(await server.call_tool("get_clip", {"track": 1, "slot": 0}))
    assert [n["pitch"] for n in clip["notes"]] == [60, 62]


async def test_bridge_errors_become_tool_errors(client, live):
    server = build_server(client)
    with pytest.raises(ToolError, match="NOT_FOUND"):
        await server.call_tool("delete_track", {"track": 42})
