"""plan_loudness: the Master to a genre's loudness, in rounds through the Limiter's input gain.

A round: the Loudness Meter's integrated reading (measure_master) -> the gain change toward the target ->
apply_plan sets the Limiter's Input Gain (one undo step) and resets the meter -> the user plays the song again
-> the next round. The limiter turns part of each added dB into gain reduction, so a round moves the loudness
less than its gain change; rounds stop within TOLERANCE_LU.

Targets: the median integrated loudness of released tracks of the genre, measured on a stereo BS.1770 meter
(sources and ratings: docs/GENRES.md, "Lautheitsziele"). Streaming: Spotify's -14 LUFS.
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
MAX_GAIN_DB = 12.0  # beyond this the Limiter squashes the song: MidiBakery stops and says so
HEAVY_GAIN_DB = 6.0
MIN_SECONDS = 30.0  # less than the drop says little about the song


class LoudnessRequest(BaseModel):
    """One round toward a LUFS target: the Master Limiter's gain from the Loudness Meter's reading."""

    model_config = ConfigDict(extra="forbid")

    target: Target | None = None  # a genre's median, or Spotify's -14 LUFS
    target_lufs: float | None = Field(None, ge=-20.0, le=-5.0)  # instead of target


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
            "limiter_input_gain": f"{self.gain_db:+.1f} dB -> {self.new_gain_db:+.1f} dB",
            "notes": ["The Limiter's ceiling stays: louder means more limiting, not higher peaks.",
                      "After apply_plan the meter starts again: play the same part again, then plan_loudness for the next round."],
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


async def build_loudness(call: Call, request: LoudnessRequest) -> LoudnessPlan | dict[str, Any]:
    """A plan for the next round, or the reading itself when it is on target."""
    if request.target_lufs is not None:
        label, target = "your target", request.target_lufs
    elif request.target is not None:
        label, target = request.target.replace("_", " "), TARGETS[request.target]
    else:
        raise BridgeError("INVALID_PARAMS", "Give a target (a genre or 'streaming') or target_lufs")
    devices = master_devices(await call("mixer.get", {}))
    meter, warnings = find_meter(devices)
    limiter = _limiter(devices, meter)
    if reset_pending():
        raise BridgeError("CONFLICT", "The Loudness Meter has not started again since the last change: switch it on "
                          "and play the song.")
    reading, more = read_meter()
    measured, seconds = reading.get("integrated_lufs"), reading.get("measured_seconds") or 0
    if measured is None or seconds < MIN_SECONDS:
        raise BridgeError("CONFLICT", f"The meter has {seconds:g} s since its last reset: play at least the loudest "
                          f"{MIN_SECONDS:g} s (better the whole song), then plan_loudness again.")
    params = await call("device.params", {"master": True, "device": limiter})
    gain = _db(next(p["display"] for p in params["parameters"] if p["name"] == "Input Gain"))
    delta = target - measured
    if abs(delta) <= TOLERANCE_LU:
        return {"on_target": True, "target": f"{label}: {target:g} LUFS", "measured_lufs": measured,
                "limiter_input_gain": f"{gain:+.1f} dB", "warnings": warnings + more}
    step = max(-MAX_STEP_DB, min(MAX_STEP_DB, delta))
    new_gain = round(min(MAX_GAIN_DB, gain + step), 1)
    if new_gain <= gain and delta > 0:
        raise BridgeError("CONFLICT", f"The Limiter already gets +{gain:g} dB: more would squash the song. "
                          f"Make the mix itself louder or pick a quieter target ({measured:g} LUFS now).")
    if new_gain > HEAVY_GAIN_DB:
        warnings.append(f"+{new_gain:g} dB into the Limiter is heavy limiting: listen for pumping and dull drums")
    if step != delta:
        warnings.append(f"{delta:+.1f} LU to go: this round moves {step:+.1f} dB; another round follows")
    return LoudnessPlan(secrets.token_hex(4), label, target, measured, seconds, limiter, gain, new_gain,
                        warnings + more)


async def apply_loudness(call: Call, plan: LoudnessPlan) -> dict[str, Any]:
    devices = master_devices(await call("mixer.get", {}))
    if len(devices) <= plan.limiter or devices[plan.limiter] != "Limiter":
        raise BridgeError("CONFLICT", f"The Master's devices changed since loudness plan {plan.id}; plan again")
    await call("batch", {"ops": [{"op": "device.set_param", "params": {
        "master": True, "device": plan.limiter, "parameter": "Input Gain", "display": plan.new_gain_db}}],
        "label": f"MidiBakery loudness {plan.id}"})
    request_reset()
    return {"ok": True, "limiter_input_gain": f"{plan.new_gain_db:+.1f} dB", "change_db": plan.change_db,
            "undo": "one undo step restores the gain",
            "next": "The meter starts again: play the same part again, then plan_loudness for the next round"}
