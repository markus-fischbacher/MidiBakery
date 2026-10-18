"""plan_loudness: rounds toward a LUFS target through the Master Limiter's Input Gain, read from the meter."""

import json
from datetime import datetime, timezone

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from midibakery.mcp import build_server
from test_master import _drag_meter, _payload, _shown


def _reading(home, integrated, seconds=200.0):
    updated = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    (home / "meter.json").write_text(json.dumps({"integrated_lufs": integrated, "measured_seconds": seconds,
                                                  "peak_db": -0.5, "updated": updated}))


async def _chain(client, live):
    """The Master as plan_master and the user leave it: the chain, then the meter."""
    server = build_server(client)
    preview = _payload(await server.call_tool("plan_master", {"genre": "house"}))
    await server.call_tool("apply_plan", {"plan_id": preview["plan_id"]})
    _drag_meter(live)
    return server


async def test_a_round_raises_the_limiter_gain_and_restarts_the_meter(client, live, bridge_env):
    server = await _chain(client, live)
    _reading(bridge_env, -12.0)
    plan = _payload(await server.call_tool("plan_loudness", {"target": "house"}))
    assert plan["target"] == "house: -8 LUFS integrated" and plan["limiter_input_gain"] == "+0.0 dB -> +4.0 dB"
    assert _shown(live, 2)["Input Gain"] == "0.0 dB"  # a plan changes nothing
    applied = _payload(await server.call_tool("apply_plan", {"plan_id": plan["plan_id"]}))
    assert applied["change_db"] == 4.0 and _shown(live, 2)["Input Gain"] == "4.0 dB"
    assert (bridge_env / "meter-reset").exists()
    # the meter has not started again: no next round on the old reading
    with pytest.raises(ToolError, match="not started again"):
        await server.call_tool("plan_loudness", {"target": "house"})
    (bridge_env / "meter-reset").unlink()  # the device takes the reset ...
    _reading(bridge_env, -9.0, seconds=8)  # ... and has heard only 8 s since
    with pytest.raises(ToolError, match="8 s since its last reset"):
        await server.call_tool("plan_loudness", {"target": "house"})
    _reading(bridge_env, -8.3)
    done = _payload(await server.call_tool("plan_loudness", {"target": "house"}))
    assert done["on_target"] and done["limiter_input_gain"] == "+4.0 dB"


async def test_big_steps_are_split_and_the_limiter_is_not_pushed_past_12_db(client, live, bridge_env):
    server = await _chain(client, live)
    _reading(bridge_env, -20.0)
    plan = _payload(await server.call_tool("plan_loudness", {"target_lufs": -8}))
    assert plan["limiter_input_gain"] == "+0.0 dB -> +6.0 dB" and any("another round" in w for w in plan["warnings"])
    await client.call("device.set_param", {"master": True, "device": 2, "parameter": "Input Gain", "display": 12})
    with pytest.raises(ToolError, match="squash"):
        await server.call_tool("plan_loudness", {"target_lufs": -8})


async def test_streaming_turns_a_loud_master_down(client, live, bridge_env):
    server = await _chain(client, live)
    _reading(bridge_env, -9.0)
    plan = _payload(await server.call_tool("plan_loudness", {"target": "streaming"}))
    assert plan["limiter_input_gain"] == "+0.0 dB -> -5.0 dB"


async def test_it_needs_a_target_a_limiter_and_the_meter(client, live, bridge_env):
    server = build_server(client)
    _reading(bridge_env, -12.0)
    with pytest.raises(ToolError, match="Give a target"):
        await server.call_tool("plan_loudness", {})
    with pytest.raises(ToolError, match="No MidiBakery Loudness Meter"):
        await server.call_tool("plan_loudness", {"target": "trap"})
    _drag_meter(live)
    with pytest.raises(ToolError, match="plan_master puts one there"):
        await server.call_tool("plan_loudness", {"target": "trap"})
