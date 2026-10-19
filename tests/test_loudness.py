"""plan_loudness: rounds toward a LUFS target through the Master Limiter's Input Gain, read from the meter."""

import json
import uuid
from datetime import datetime, timezone

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from midibakery.mcp import build_server
from test_master import _drag_meter, _payload, _shown


def _reading(home, integrated, seconds=200.0, **values):
    updated = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    (home / "meter.json").write_text(json.dumps({"integrated_lufs": integrated, "measured_seconds": seconds,
                                                  "peak_db": -0.5, "updated": updated, "since": updated,
                                                  "measurement_id": str(uuid.uuid4()), "sample_rate": 48000, **values}))


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
    plan = _payload(await server.call_tool("plan_loudness", {"target": "house", "scope": "whole_song"}))
    assert plan["target"] == "house: -8 LUFS integrated" and plan["limiter_input_gain"] == "+0.0 dB -> +4.0 dB"
    assert _shown(live, 2)["Input Gain"] == "0.0 dB"  # a plan changes nothing
    applied = _payload(await server.call_tool("apply_plan", {"plan_id": plan["plan_id"]}))
    assert applied["change_db"] == 4.0 and _shown(live, 2)["Input Gain"] == "4.0 dB"
    assert (bridge_env / "meter-reset").exists()
    # the meter has not started again: no next round on the old reading
    with pytest.raises(ToolError, match="not started again"):
        await server.call_tool("plan_loudness", {"target": "house", "scope": "whole_song"})
    (bridge_env / "meter-reset").unlink()  # the device takes the reset ...
    _reading(bridge_env, -9.0, seconds=8)  # ... and has heard only 8 s since
    with pytest.raises(ToolError, match="8 s since its last reset"):
        await server.call_tool("plan_loudness", {"target_lufs": -8, "scope": "excerpt"})
    _reading(bridge_env, -8.3)
    done = _payload(await server.call_tool("plan_loudness", {"target": "house", "scope": "whole_song"}))
    assert done["on_target"] and done["limiter_input_gain"] == "+4.0 dB"


async def test_big_steps_are_split_and_the_limiter_is_not_pushed_past_12_db(client, live, bridge_env):
    server = await _chain(client, live)
    _reading(bridge_env, -20.0)
    plan = _payload(await server.call_tool("plan_loudness", {"target_lufs": -8, "scope": "whole_song"}))
    assert plan["limiter_input_gain"] == "+0.0 dB -> +6.0 dB" and any("another round" in w for w in plan["warnings"])
    await client.call("device.set_param", {"master": True, "device": 2, "parameter": "Input Gain", "display": 12})
    with pytest.raises(ToolError, match="input-gain cap"):
        await server.call_tool("plan_loudness", {"target_lufs": -8, "scope": "whole_song"})


async def test_streaming_turns_a_loud_master_down(client, live, bridge_env):
    server = await _chain(client, live)
    _reading(bridge_env, -9.0)
    plan = _payload(await server.call_tool("plan_loudness", {"target": "streaming", "scope": "whole_song"}))
    assert plan["limiter_input_gain"] == "+0.0 dB -> -5.0 dB"


async def test_it_needs_a_target_a_limiter_and_the_meter(client, live, bridge_env):
    server = build_server(client)
    _reading(bridge_env, -12.0)
    with pytest.raises(ToolError, match="Give a target"):
        await server.call_tool("plan_loudness", {})
    with pytest.raises(ToolError, match="No MidiBakery Loudness Meter"):
        await server.call_tool("plan_loudness", {"target": "trap", "scope": "whole_song"})
    _drag_meter(live)
    with pytest.raises(ToolError, match="plan_master puts one there"):
        await server.call_tool("plan_loudness", {"target": "trap", "scope": "whole_song"})


async def test_scope_is_not_inferred_from_duration_or_on_target_reading(client, live, bridge_env):
    server = await _chain(client, live)
    _reading(bridge_env, -8, seconds=3600)
    with pytest.raises(ToolError, match="Declare scope"):
        await server.call_tool("plan_loudness", {"target": "house"})
    with pytest.raises(ToolError, match="whole tracks"):
        await server.call_tool("plan_loudness", {"target": "house", "scope": "excerpt"})
    done = _payload(await server.call_tool("plan_loudness", {"target_lufs": -8, "scope": "excerpt"}))
    assert done["on_target"] and done["measurement_scope"] == "excerpt"
    assert done["scope_source"] == "user_declared" and done["coverage_verified"] is False
    assert done["measurement_id"]


@pytest.mark.parametrize("seconds,accepted", [(0.3, False), (0.4, True), (8, True), (29.9, True)])
async def test_short_complete_songs_need_one_integrated_block_not_30_seconds(client, live, bridge_env, seconds, accepted):
    server = await _chain(client, live)
    _reading(bridge_env, -14, seconds=seconds)
    if accepted:
        done = _payload(await server.call_tool("plan_loudness", {"target": "streaming", "scope": "whole_song"}))
        assert done["on_target"] and done["measurement_scope"] == "whole_song" and not done["coverage_verified"]
    else:
        with pytest.raises(ToolError, match="at least 0.4 s"):
            await server.call_tool("plan_loudness", {"target": "streaming", "scope": "whole_song"})


@pytest.mark.parametrize("seconds,accepted", [(29.9, False), (30, True)])
async def test_excerpt_minimum_is_exact(client, live, bridge_env, seconds, accepted):
    server = await _chain(client, live)
    _reading(bridge_env, -14, seconds=seconds)
    args = {"target_lufs": -14, "scope": "excerpt"}
    if accepted:
        assert _payload(await server.call_tool("plan_loudness", args))["on_target"]
    else:
        with pytest.raises(ToolError, match="at least 30 s"):
            await server.call_tool("plan_loudness", args)


async def test_scope_requires_a_current_identifiable_reading(client, live, bridge_env):
    server = await _chain(client, live)
    args = {"target": "house", "scope": "whole_song"}
    _reading(bridge_env, -12, measurement_id=None)
    with pytest.raises(ToolError, match="updated Loudness Meter"):
        await server.call_tool("plan_loudness", args)
    _reading(bridge_env, -12, updated="2000-01-01T00:00:00Z")
    with pytest.raises(ToolError, match="stale"):
        await server.call_tool("plan_loudness", args)
    _reading(bridge_env, None)
    with pytest.raises(ToolError, match="finite integrated"):
        await server.call_tool("plan_loudness", args)


@pytest.mark.parametrize("key,value", [
    ("integrated_lufs", float("nan")), ("measured_seconds", -1), ("measured_seconds", "200"),
    ("sample_rate", float("inf")), ("integrated_lufs", True),
])
async def test_invalid_meter_numbers_are_rejected(client, live, bridge_env, key, value):
    server = await _chain(client, live)
    _reading(bridge_env, -12)
    reading = json.loads((bridge_env / "meter.json").read_text())
    reading[key] = value
    (bridge_env / "meter.json").write_text(json.dumps(reading))
    with pytest.raises(ToolError, match="invalid|negative"):
        await server.call_tool("plan_loudness", {"target": "house", "scope": "whole_song"})


@pytest.mark.parametrize("change", ["reset", "rate", "since", "duration", "pending", "gain", "ceiling", "mode", "limiter", "meter", "chain"])
async def test_stale_plans_never_write_gain(client, live, bridge_env, change):
    from fake_song import Device, make_device

    server = await _chain(client, live)
    _reading(bridge_env, -12)
    plan = _payload(await server.call_tool("plan_loudness", {"target": "house", "scope": "whole_song"}))
    before = live.on_main(lambda: live.song.undo_steps)
    path = bridge_env / "meter.json"
    reading = json.loads(path.read_text())
    if change in ("reset", "rate", "since", "duration"):
        key, value = {"reset": ("measurement_id", "new-session"), "rate": ("sample_rate", 44100),
                      "since": ("since", "new-reset"), "duration": ("measured_seconds", 1)}[change]
        reading[key] = value
        path.write_text(json.dumps(reading))
    elif change == "pending":
        (bridge_env / "meter-reset").write_text("reset")
    elif change in ("gain", "ceiling", "mode"):
        name, value = {"gain": ("Input Gain", 1), "ceiling": ("Ceiling", -2),
                       "mode": ("Mode", "Standard")}[change]
        await client.call("device.set_param", {"master": True, "device": 2, "parameter": name, "display": value})
        before += 1
    elif change == "limiter":
        live.on_main(lambda: live.song.master_track.devices.__setitem__(2, make_device("Limiter")))
    elif change == "meter":
        live.on_main(lambda: live.song.master_track.devices.__setitem__(3, Device("MidiBakery Loudness Meter")))
    else:
        await client.call("device.insert", {"master": True, "name": "Reverb", "index": 0})
        before += 1
    with pytest.raises(ToolError, match="changed|pending reset"):
        await server.call_tool("apply_plan", {"plan_id": plan["plan_id"]})
    assert live.on_main(lambda: live.song.undo_steps) == before


async def test_more_readings_in_same_session_do_not_invalidate_plan(client, live, bridge_env):
    server = await _chain(client, live)
    _reading(bridge_env, -12)
    plan = _payload(await server.call_tool("plan_loudness", {"target": "house", "scope": "whole_song"}))
    path = bridge_env / "meter.json"
    reading = json.loads(path.read_text())
    reading["measured_seconds"] += 1
    path.write_text(json.dumps(reading))
    assert _payload(await server.call_tool("apply_plan", {"plan_id": plan["plan_id"]}))["ok"]


async def test_delivery_warning_and_gain_warning_are_not_compliance_claims(client, live, bridge_env):
    server = await _chain(client, live)
    _reading(bridge_env, -20)
    await client.call("device.set_param", {"master": True, "device": 2, "parameter": "Input Gain", "display": 2})
    plan = _payload(await server.call_tool("plan_loudness", {"target": "house", "scope": "whole_song"}))
    assert any("Spotify" in w for w in plan["warnings"])
    assert any("gain reduction is not measured" in w for w in plan["warnings"])
    await client.call("device.set_param", {"master": True, "device": 2, "parameter": "Ceiling", "display": -2})
    plan = _payload(await server.call_tool("plan_loudness", {"target": "house", "scope": "whole_song"}))
    assert not any("Spotify" in w for w in plan["warnings"])


async def test_targets_are_unambiguous_and_meter_must_be_last(client, live, bridge_env):
    server = await _chain(client, live)
    _reading(bridge_env, -12)
    with pytest.raises(ToolError, match="not both"):
        await server.call_tool("plan_loudness", {"target": "house", "target_lufs": -8, "scope": "whole_song"})
    await client.call("device.insert", {"master": True, "name": "Reverb"})
    with pytest.raises(ToolError, match="last on the Master"):
        await server.call_tool("plan_loudness", {"target": "house", "scope": "whole_song"})


async def test_existing_gain_above_cap_can_be_reduced_without_exceeding_step(client, live, bridge_env):
    server = await _chain(client, live)
    await client.call("device.set_param", {"master": True, "device": 2, "parameter": "Input Gain", "display": 20})
    _reading(bridge_env, -13)
    plan = _payload(await server.call_tool("plan_loudness", {"target": "streaming", "scope": "whole_song"}))
    assert plan["limiter_input_gain"] == "+20.0 dB -> +19.0 dB"


async def test_failed_reset_request_rolls_back_gain_and_reports_failure(client, live, bridge_env, monkeypatch):
    from midibakery.bridge import BridgeError
    from midibakery.compose import loudness

    await _chain(client, live)
    _reading(bridge_env, -12)
    plan = await loudness.build_loudness(client.call, loudness.LoudnessRequest(target="house", scope="whole_song"))
    assert isinstance(plan, loudness.LoudnessPlan)

    def fail_reset():
        raise BridgeError("INTERNAL", "Cannot request a loudness reset")

    monkeypatch.setattr(loudness, "request_reset", fail_reset)
    before = live.on_main(lambda: live.song.undo_calls)
    with pytest.raises(BridgeError, match="Cannot request a loudness reset") as exc:
        await loudness.apply_loudness(client.call, plan)
    assert exc.value.details["rolled_back"] and live.on_main(lambda: live.song.undo_calls) == before + 1
