"""plan_master: a genre's master chain on the Master, previewed, then applied in two undo steps."""

import json

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from midibakery.compose.master import GLUE_ATTACK_MS, STYLES
from midibakery.mcp import build_server


def _payload(result):
    content = result[0] if isinstance(result, tuple) else result
    if hasattr(content, "structured_content") and content.structured_content:
        return content.structured_content
    items = content.content if hasattr(content, "content") else content
    return json.loads(items[0].text)


def _shown(live, device):
    """{parameter: what Live shows} of a master device."""
    def read():
        return {p.name: p.str_for_value(p.value) for p in live.song.master_track.devices[device].parameters}

    return live.on_main(read)


def _master_names(live):
    return live.on_main(lambda: [d.name for d in live.song.master_track.devices])


async def test_preview_changes_nothing_and_apply_sets_the_chain(client, live):
    server = build_server(client)
    preview = _payload(await server.call_tool("plan_master", {"genre": "peak_time_techno"}))
    assert [d["device"] for d in preview["master_chain"]] == ["EQ Eight", "Glue Compressor", "Limiter"]
    assert "low cut 30 Hz" in preview["master_chain"][0]["settings"]
    assert "-1 dB true peak" in preview["master_chain"][2]["settings"]
    assert any("not a finished master" in n for n in preview["notes"])
    assert _master_names(live) == []

    applied = _payload(await server.call_tool("apply_plan", {"plan_id": preview["plan_id"]}))
    assert applied["ok"] and "2 undo steps" in applied["undo"]
    assert _master_names(live) == ["EQ Eight", "Glue Compressor", "Limiter"]
    eq, glue, limiter = (_shown(live, i) for i in range(3))
    assert eq["1 Filter Type A"] == "High Pass 12dB" and eq["1 Frequency A"].startswith("30.")
    assert glue["Attack"] == "30" and glue["Ratio"] == "2" and glue["Release"] == "A"
    assert glue["Threshold"] == "-10.0 dB" and glue["S/C EQ On"] == "On" and glue["S/C EQ Freq"].startswith("150")
    assert limiter["Ceiling"] == "-1.0 dB" and limiter["Mode"] == "True Peak" and limiter["Input Gain"] == "0.0 dB"

    again = _payload(await server.call_tool("apply_plan", {"plan_id": preview["plan_id"]}))
    assert again["already_applied"]


async def test_sub_heavy_genres_cut_lower_and_steeper(client, live):
    server = build_server(client)
    preview = _payload(await server.call_tool("plan_master", {"genre": "drum_and_bass"}))
    await server.call_tool("apply_plan", {"plan_id": preview["plan_id"]})
    eq = _shown(live, 0)
    assert eq["1 Filter Type A"] == "High Pass 48dB" and eq["1 Frequency A"].startswith("20.")


async def test_without_genre_and_with_own_ceiling(client, live):
    server = build_server(client)
    preview = _payload(await server.call_tool("plan_master", {"ceiling_db": -2}))
    assert preview["genre"] == "any genre"
    await server.call_tool("apply_plan", {"plan_id": preview["plan_id"]})
    assert _shown(live, 2)["Ceiling"] == "-2.0 dB"


async def test_a_master_with_a_limiter_is_left_alone(client, live):
    server = build_server(client)
    await client.call("device.insert", {"master": True, "name": "Limiter"})
    with pytest.raises(ToolError, match="already has 'Limiter'"):
        await server.call_tool("plan_master", {"genre": "house"})
    assert _master_names(live) == ["Limiter"]


async def test_other_master_devices_stay_before_the_chain(client, live):
    server = build_server(client)
    await client.call("device.insert", {"master": True, "name": "Reverb"})
    preview = _payload(await server.call_tool("plan_master", {"genre": "house"}))
    assert preview["after"] == ["Reverb"] and preview["warnings"]
    applied = _payload(await server.call_tool("apply_plan", {"plan_id": preview["plan_id"]}))
    assert applied["devices"] == {"EQ Eight": 1, "Glue Compressor": 2, "Limiter": 3}
    assert _shown(live, 3)["Mode"] == "True Peak"


async def test_master_changed_after_planning(client, live):
    server = build_server(client)
    preview = _payload(await server.call_tool("plan_master", {"genre": "house"}))
    await client.call("device.insert", {"master": True, "name": "Reverb"})
    with pytest.raises(ToolError, match="changed"):
        await server.call_tool("apply_plan", {"plan_id": preview["plan_id"]})
    assert _master_names(live) == ["Reverb"]


async def test_device_ops_take_the_master(client, live):
    await client.call("device.insert", {"master": True, "name": "Glue Compressor"})
    params = await client.call("device.params", {"master": True, "device": 0})
    assert params["name"] == "Glue Compressor"
    await client.call("device.set_param", {"master": True, "device": 0, "parameter": "Threshold", "display": -6})
    assert _shown(live, 0)["Threshold"] == "-6.0 dB"


def test_every_genre_has_a_master_style_on_glue_steps():
    assert set(STYLES) == {"house", "melodic_techno", "peak_time_techno", "drum_and_bass", "trap"}
    assert all(s.glue_attack_ms in GLUE_ATTACK_MS and s.ceiling_db == -1.0 for s in STYLES.values())
