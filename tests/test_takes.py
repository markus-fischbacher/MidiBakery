"""Take lanes: variations of a part to comp in Live, against the fake LOM."""

import json

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from midibakery.bridge import BridgeError
from midibakery.mcp import build_server


def _payload(result):
    content = result[0] if isinstance(result, tuple) else result
    if hasattr(content, "structured_content") and content.structured_content:
        return content.structured_content
    items = content.content if hasattr(content, "content") else content
    return json.loads(items[0].text)


async def _lanes(client, track):
    entry = next(t for t in (await client.call("arrangement.get", {}))["tracks"] if t["index"] == track)
    return entry.get("take_lanes", []), entry["clips"]


async def test_four_hook_takes_over_the_songs_chords(client, live):
    live.on_main(lambda: setattr(live.song.tracks[0], "name", "Chords"))
    chords = [{"pitch": p, "start_time": float(bar * 4), "duration": 4.0, "velocity": 90}
              for bar, root in enumerate((57, 53, 48, 55)) for p in (root, root + 3 if root in (57,) else root + 4, root + 7)]
    await client.call("arrangement.edit", {"actions": [{"action": "add_clip", "track": 0, "start": 0, "length": 16, "name": "Loop", "notes": chords}]})

    summary = _payload(await build_server(client).call_tool("compose_takes", {"track": 1, "start_bar": 1, "bars": 4, "count": 4, "seed": 10}))
    assert summary["chords_from"].startswith("from 'Loop'") and summary["chords"][0].startswith("Am")
    assert [t["seed"] for t in summary["takes"]] == [10, 11, 12, 13]

    lanes, main = await _lanes(client, 1)
    assert [lane["name"] for lane in lanes] == [f"Take {k} · hook · seed {9 + k}" for k in range(1, 5)]
    assert main == []  # the main lane stays as it was
    assert all(lane["clips"][0]["start"] == 0.0 and lane["clips"][0]["end"] == 16.0 for lane in lanes)
    takes = live.on_main(lambda: [[(n["pitch"], n["start_time"]) for n in lane.arrangement_clips[0].notes.values()] for lane in live.song.tracks[1].take_lanes])
    assert len({tuple(sorted(t)) for t in takes}) == 4  # four different takes


async def test_takes_of_other_kinds_and_their_params(client, live):
    server = build_server(client)
    summary = _payload(await server.call_tool("compose_takes", {"track": 1, "start_bar": 5, "bars": 2, "kind": "bass", "count": 2, "params": {"style": "offbeat"}}))
    assert summary["chords_from"] == "generated" and summary["kind"] == "bass"
    with pytest.raises(ToolError) as exc:
        await server.call_tool("compose_takes", {"track": 1, "start_bar": 1, "kind": "bass", "params": {"style": "polka"}})
    assert "params" in str(exc.value)
    with pytest.raises(ToolError) as exc:
        await server.call_tool("compose_takes", {"track": 1, "start_bar": 1, "kind": "hook", "params": {"lowest": 60}})
    assert "params" in str(exc.value) and "lowest" in str(exc.value)
    with pytest.raises(ToolError) as exc:
        await server.call_tool("compose_takes", {"track": 1, "start_bar": 1, "chords_from": {"track": 0, "arrangement_clip": 3}})
    assert "no arrangement clip 3 on track index 0" in str(exc.value)


async def test_a_take_clip_needs_a_lane(client):
    with pytest.raises(BridgeError) as exc:
        await client.call("arrangement.edit", {"actions": [{"action": "add_take_clip", "track": 1, "lane": -1, "start": 0, "length": 4}]})
    assert exc.value.code == "INVALID_PARAMS"
    await client.call("arrangement.edit", {"actions": [{"action": "add_take_lane", "track": 1, "name": "A"}]})
    await client.call("arrangement.edit", {"actions": [{"action": "add_take_clip", "track": 1, "lane": 0, "start": 0, "length": 4}]})
    with pytest.raises(BridgeError) as exc:
        await client.call("arrangement.edit", {"actions": [{"action": "add_take_clip", "track": 1, "lane": 0, "start": 2, "length": 4}]})
    assert exc.value.code == "CONFLICT"


async def test_takes_are_one_undo_step(client, live):
    before = live.on_main(lambda: live.song.undo_steps)
    await build_server(client).call_tool("compose_takes", {"track": 1, "start_bar": 1, "bars": 2, "count": 3})
    assert live.on_main(lambda: live.song.undo_steps) == before + 1
