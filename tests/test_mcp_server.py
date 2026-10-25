import json

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from midibakery.mcp import build_server


def _payload(result):
    return json.loads(result.content[0].text)


async def test_tool_list_is_small_and_annotated():
    server = build_server()
    tools = {t.name: t for t in await server.list_tools()}
    assert len(tools) == 16  # the real guard is the character budget in test_agent (local models)
    assert tools["get_session"].annotations.read_only_hint is True
    assert tools["delete_clip"].annotations.destructive_hint is True
    assert "arrangement_clip" in json.dumps(tools["compose"].input_schema)


async def test_get_session_and_get_clip_through_mcp(client, live):
    server = build_server(client)
    session = _payload(await server.call_tool("get_session", {}))
    assert session["song"]["scale_name"] == "Major"
    assert len(session["tracks"]) == 2

    await client.call("clip.create", {"track": 1, "slot": 0, "length": 4})
    await client.call("notes.apply", {
        "track": 1, "slot": 0,
        "add": [{"pitch": 60, "start_time": 0, "duration": 0.5}, {"pitch": 62, "start_time": 0.5, "duration": 0.5}],
    })
    clip = _payload(await server.call_tool("get_clip", {"track": 1, "slot": 0}))
    assert [n["pitch"] for n in clip["notes"]] == [60, 62]


async def test_bridge_errors_become_tool_errors(client, live):
    server = build_server(client)
    with pytest.raises(ToolError, match="NOT_FOUND"):
        await server.call_tool("delete_clip", {"track": 42, "slot": 0})


async def test_find_sounds_set_track_and_edit_notes(client, live):
    from midibakery.mcp import build_server
    import json
    server = build_server(client)

    def payload(r):
        c = r[0] if isinstance(r, tuple) else r
        return c.structured_content if getattr(c, "structured_content", None) else json.loads(c.content[0].text)

    found = payload(await server.call_tool("find_sounds", {"query": "909"}))
    assert found
    await server.call_tool("set_track", {"track": 1, "name": "Bassline"})
    assert live.on_main(lambda: live.song.tracks[1].name) == "Bassline"
    await client.call("clip.create", {"track": 1, "slot": 0, "length": 4})
    await client.call("notes.apply", {"track": 1, "slot": 0, "add": [
        {"pitch": 40, "start_time": 0.0, "duration": 1.0}, {"pitch": 43, "start_time": 2.0, "duration": 1.0}]})
    await server.call_tool("edit_notes", {"track": 1, "slot": 0, "transpose": 12, "from_time": 2.0, "add": [{"pitch": 36, "start_time": 3.0, "duration": 0.5}]})
    notes = sorted((n["start_time"], n["pitch"]) for n in (await client.call("notes.get", {"track": 1, "slot": 0}))["notes"])
    assert notes == [(0.0, 40), (2.0, 55), (3.0, 36)]
