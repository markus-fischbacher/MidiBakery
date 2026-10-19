"""Scope-aware gain proposals from approximate integrated loudness, not mastering-quality assessment.

Genre presets are reference figures of varying evidence quality (docs/GENRES.md). Whole-song coverage
is declared by the user, not inferred from measurement duration or verified by the meter.
"""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from midibakery.bridge.client import BridgeError

from .master import master_devices
from .meter import find_meter, read_meter, request_reset, reset_pending
from .plan import Call
from .rollback import undo, undo_batch

TARGETS: dict[str, float] = {
    "house": -8.0,
    "melodic_techno": -8.8,
    "peak_time_techno": -7.7,
    "drum_and_bass": -6.3,
    "trap": -8.4,
    "streaming": -14.0,
}
Target = Literal["house", "melodic_techno", "peak_time_techno", "drum_and_bass", "trap", "streaming"]
TOLERANCE_LU = 0.5
MAX_STEP_DB = 6.0  # one round; the limiter's reaction to more is hard to guess
MAX_GAIN_DB = 12.0  # conservative input-gain cap, not measured gain reduction
HEAVY_GAIN_DB = 6.0
MIN_SECONDS = 30.0  # excerpt policy; does not establish whole-song coverage
MIN_WHOLE_SECONDS = 0.4  # at least one integrated-loudness block for short complete songs


class LoudnessRequest(BaseModel):
    """LUFS gain proposal; declare scope (whole_song or excerpt). Coverage is not verified."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    target: Target | None = None
    target_lufs: float | None = Field(None, ge=-20.0, le=-5.0)  # instead of target
    scope: Literal["unknown", "whole_song", "excerpt"] = Field("unknown", description="User-declared playback since reset; excerpts need target_lufs")


@dataclass
class LoudnessPlan:
    id: str
    target_label: str
    target_lufs: float
    measured_lufs: float
    measured_seconds: float
    limiter: int  # the Limiter's index on the Master
    gain_db: float  # its Input Gain now
    new_gain_db: float
    scope: str
    measurement: tuple[str, str, float]
    devices: tuple[str, ...]
    limiter_id: int
    meter_id: int
    limiter_state: tuple
    warnings: list[str] = field(default_factory=list)

    @property
    def change_db(self) -> float:
        return round(self.new_gain_db - self.gain_db, 1)

    def preview(self) -> dict[str, Any]:
        return {
            "plan_id": self.id,
            "target": f"{self.target_label}: {self.target_lufs:g} LUFS integrated",
            "measured_lufs": self.measured_lufs,
            "measured_seconds": self.measured_seconds,
            **scope_info(self.scope, self.measurement[0]),
            "limiter_input_gain": f"{self.gain_db:+.1f} dB -> {self.new_gain_db:+.1f} dB",
            "notes": ["The ceiling setting stays unchanged; sample peak cannot verify true-peak compliance.",
                      "Input gain is not measured gain reduction; listen for distortion, pumping and flattened transients.",
                      "After apply_plan, repeat the same complete song or excerpt from reset and declare its scope again. "
                      "No convergence or mastering quality is guaranteed."],
            "warnings": self.warnings,
            "next": "apply_plan(plan_id) sets the Limiter's Input Gain (one undo step)",
        }


def _limiter(devices: tuple[str, ...], meter: int) -> int:
    found = [i for i, d in enumerate(devices[:meter]) if d == "Limiter"]
    if not found:
        raise BridgeError("NOT_FOUND", "No Limiter before the Loudness Meter on the Master: plan_master puts one there.",
                          {"master_devices": list(devices)})
    return found[-1]


def _db(display: str) -> float:
    match = re.search(r"-?\d+(\.\d+)?", display or "")
    if not match:
        raise BridgeError("INTERNAL", f"Cannot read the Limiter's Input Gain from {display!r}")
    return float(match[0])


def scope_info(scope: str, measurement_id: str) -> dict[str, Any]:
    return {"measurement_scope": scope, "scope_source": "user_declared", "coverage_verified": False,
            "measurement_id": measurement_id}


def _measurement(reading: dict[str, Any]) -> tuple[str, str, float]:
    identity, since, rate = reading.get("measurement_id"), reading.get("since"), reading.get("sample_rate")
    if not isinstance(identity, str) or not identity or not isinstance(since, str) or not since or not rate or rate <= 0:
        raise BridgeError("CONFLICT", "The meter lacks measurement identity: install the updated Loudness Meter, "
                          "reset it and measure again")
    return identity, since, rate


def _device_id(params: dict[str, Any]) -> int:
    identity = params.get("id")
    if not isinstance(identity, int) or isinstance(identity, bool):
        raise BridgeError("CONFLICT", "Device identity unavailable: install the updated Remote Script and restart Live")
    return identity


def _limiter_state(params: dict[str, Any]) -> tuple:
    return tuple((p["name"], p["value"]) for p in params["parameters"])


def _parameter(params: dict[str, Any], name: str) -> dict[str, Any]:
    parameter = next((p for p in params["parameters"] if p["name"] == name), None)
    if parameter is None:
        raise BridgeError("CONFLICT", f"The Limiter has no {name!r} parameter; check the device and plan again")
    return parameter


def _usable(reading: dict[str, Any]) -> None:
    if not reading["reading_fresh"]:
        raise BridgeError("CONFLICT", "The meter reading is stale: switch on the device and measure again")


async def build_loudness(call: Call, request: LoudnessRequest) -> LoudnessPlan | dict[str, Any]:
    """A plan for the next round, or the reading itself when it is on target."""
    if request.target_lufs is not None and request.target is not None:
        raise BridgeError("INVALID_PARAMS", "Give target or target_lufs, not both")
    if request.target_lufs is not None:
        label, target = "your target", request.target_lufs
    elif request.target is not None:
        label, target = request.target.replace("_", " "), TARGETS[request.target]
    else:
        raise BridgeError("INVALID_PARAMS", "Give a target (a genre or 'streaming') or target_lufs")
    if request.scope == "unknown":
        raise BridgeError("INVALID_PARAMS", "Declare scope='whole_song' only after reset and one complete playback, "
                          "or scope='excerpt' with an explicit target_lufs. Duration alone does not establish coverage.")
    if request.scope == "excerpt" and request.target is not None:
        raise BridgeError("INVALID_PARAMS", "Genre/streaming references describe whole tracks: an excerpt needs an explicit target_lufs")
    devices = master_devices(await call("mixer.get", {}))
    meter, warnings = find_meter(devices)
    if meter != len(devices) - 1:
        raise BridgeError("CONFLICT", "Put the Loudness Meter last on the Master before planning loudness")
    limiter = _limiter(devices, meter)
    if reset_pending():
        raise BridgeError("CONFLICT", "The Loudness Meter has not started again since the last change: switch it on "
                          "and play the song.")
    reading, more = read_meter()
    _usable(reading)
    measurement = _measurement(reading)
    measured, seconds = reading.get("integrated_lufs"), reading.get("measured_seconds") or 0
    minimum = MIN_WHOLE_SECONDS if request.scope == "whole_song" else MIN_SECONDS
    if measured is None or seconds < minimum:
        raise BridgeError("CONFLICT", f"The meter has {seconds:g} s since its last reset: need at least {minimum:g} s "
                          f"with a finite integrated reading for scope={request.scope}. Reset and repeat playback.")
    params = await call("device.params", {"master": True, "device": limiter})
    meter_params = await call("device.params", {"master": True, "device": meter})
    limiter_id, meter_id = _device_id(params), _device_id(meter_params)
    gain = _db(_parameter(params, "Input Gain")["display"])
    ceiling = _db(_parameter(params, "Ceiling")["display"])
    warnings += more
    warnings.append("Playback scope is user-declared, not verified. This approximate meter does not assess mastering quality.")
    if target > -14 and ceiling > -2:
        warnings.append("For Spotify masters louder than -14 LUFS, Spotify recommends below -2 dBTP. "
                        "The current ceiling is higher; adjust it explicitly and verify the render with a true-peak meter.")
    if _parameter(params, "Mode")["display"] != "True Peak":
        warnings.append("The Limiter is not in True Peak mode; no true-peak ceiling compliance is verified")
    delta = target - measured
    if abs(delta) <= TOLERANCE_LU:
        return {"on_target": True, "target": f"{label}: {target:g} LUFS", "measured_lufs": measured,
                "measured_seconds": seconds, **scope_info(request.scope, measurement[0]),
                "limiter_input_gain": f"{gain:+.1f} dB", "warnings": warnings}
    step = max(-MAX_STEP_DB, min(MAX_STEP_DB, delta))
    new_gain = round(min(MAX_GAIN_DB, gain + step) if step > 0 else gain + step, 1)
    if new_gain <= gain and delta > 0:
        raise BridgeError("CONFLICT", f"The Limiter already gets +{gain:g} dB: the input-gain cap prevents an increase. "
                          f"Reassess the mix or pick a quieter target ({measured:g} LUFS now); gain reduction is not measured.")
    if new_gain > HEAVY_GAIN_DB:
        warnings.append(f"+{new_gain:g} dB input gain may cause heavy limiting; gain reduction is not measured. Listen for pumping and dull drums")
    if step != delta:
        warnings.append(f"{delta:+.1f} LU to go: this round moves {step:+.1f} dB; another round follows")
    return LoudnessPlan(secrets.token_hex(4), label, target, measured, seconds, limiter, gain, new_gain,
                        request.scope, measurement, devices, limiter_id, meter_id, _limiter_state(params), warnings)


async def apply_loudness(call: Call, plan: LoudnessPlan) -> dict[str, Any]:
    devices = master_devices(await call("mixer.get", {}))
    if devices != plan.devices:
        raise BridgeError("CONFLICT", f"The Master's devices changed since loudness plan {plan.id}; plan again")
    if reset_pending():
        raise BridgeError("CONFLICT", "The meter has a pending reset: measure again and make a new loudness plan")
    reading, _ = read_meter()
    _usable(reading)
    if _measurement(reading) != plan.measurement or (reading.get("measured_seconds") or 0) < plan.measured_seconds:
        raise BridgeError("CONFLICT", "The measurement session changed: measure again and make a new loudness plan")
    params = await call("device.params", {"master": True, "device": plan.limiter})
    meter_params = await call("device.params", {"master": True, "device": len(devices) - 1})
    if (_device_id(params) != plan.limiter_id or _device_id(meter_params) != plan.meter_id
            or _limiter_state(params) != plan.limiter_state):
        raise BridgeError("CONFLICT", "The Limiter, meter or Limiter settings changed: measure again and plan again")
    try:
        await call("batch", {"ops": [{"op": "device.set_param", "params": {
            "master": True, "device": plan.limiter, "parameter": "Input Gain", "display": plan.new_gain_db}}],
            "label": f"MidiBakery loudness {plan.id}"})
    except BridgeError as exc:
        await undo_batch(call, exc, ["device.set_param"])
        raise
    try:
        request_reset()
    except BridgeError as exc:
        await undo(call, exc, 1, "the Limiter gain was restored")
        raise
    return {"ok": True, "limiter_input_gain": f"{plan.new_gain_db:+.1f} dB", "change_db": plan.change_db,
            "undo": "one undo step restores the gain",
            **scope_info(plan.scope, plan.measurement[0]),
            "warnings": plan.warnings,
            "next": "The meter resets: repeat the same complete song or excerpt, then plan_loudness with its scope"}
