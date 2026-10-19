"""measure_master: the Master's loudness from the MidiBakery Loudness Meter device.

The device (packages/m4l/src/midibakery-meter.js) approximates BS.1770 and writes its
reading to <MidiBakery folder>/meter.json twice a second; a reset request is the file meter-reset, which
the device deletes. Sample peaks cannot verify a true-peak ceiling.
"""

from __future__ import annotations

import json
import math
import time
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from midibakery.bridge.client import BridgeError, config_dir

from .master import METER, is_meter, master_devices
from .plan import Call

STALE_SECONDS = 3.0  # the device writes every 0.5 s while DSP blocks arrive
WHERE = "Audio Effects > Max Audio Effect > MidiBakery"


class MeterQuery(BaseModel):
    """Master LUFS and peak from the Loudness Meter device. reset=true restarts them."""

    model_config = ConfigDict(extra="forbid")

    reset: bool = False


def find_meter(devices: tuple[str, ...]) -> tuple[int, list[str]]:
    """The meter's index on the Master and warnings; NOT_FOUND without one."""
    meter = next((i for i, d in enumerate(devices) if is_meter(d)), None)
    if meter is None:
        raise BridgeError("NOT_FOUND", f"No {METER} on the Master. Drag it from Live's browser ({WHERE}) onto the "
                          "Master as its last device, then play the song.", {"master_devices": list(devices)})
    after = devices[meter + 1:]
    return meter, [f"The meter is not the Master's last device: it does not hear {', '.join(after)}"] if after else []


def request_reset() -> None:
    """The device deletes this file on its next block and starts again."""
    try:
        config_dir().mkdir(parents=True, exist_ok=True)
        (config_dir() / "meter-reset").write_text("midibakery\n", encoding="utf-8")
    except OSError as exc:
        raise BridgeError("INTERNAL", f"Cannot request a loudness reset: {exc}. Check the MidiBakery folder permissions.") from exc


def reset_pending() -> bool:
    return (config_dir() / "meter-reset").exists()


def read_meter() -> tuple[dict[str, Any], list[str]]:
    """The meter's last reading plus "measuring" (written in the last STALE_SECONDS), and warnings."""
    path = config_dir() / "meter.json"
    try:
        reading = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise BridgeError("NOT_FOUND", f"The {METER} has not measured anything yet: play the song in Live.") from None
    if not isinstance(reading, dict):
        raise BridgeError("CONFLICT", "The meter reading is not an object: reset the meter and measure again")
    age = _age(reading.get("updated"), path)
    result = {k: reading.get(k) for k in ("integrated_lufs", "short_term_lufs", "momentary_lufs", "peak_db",
                                          "short_term_peak_db", "measured_seconds", "measurement_id", "since", "sample_rate")}
    for key in ("integrated_lufs", "short_term_lufs", "momentary_lufs", "peak_db", "short_term_peak_db",
                "measured_seconds", "sample_rate"):
        value = result[key]
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)):
            raise BridgeError("CONFLICT", f"The meter's {key} is invalid: reset the meter and measure again")
    if result["measured_seconds"] is not None and result["measured_seconds"] < 0:
        raise BridgeError("CONFLICT", "The meter's measured_seconds is negative: reset and measure again")
    result["reading_fresh"] = age <= STALE_SECONDS
    result["measuring"] = result["reading_fresh"]  # compatibility: freshness, not transport state
    result["measurement_scope"] = "unknown"
    result["coverage_verified"] = False
    warnings = []
    if not result["reading_fresh"]:
        warnings.append(f"The meter last updated {age:.0f} s ago (the device is off or was removed, or Live is closed): "
                        "these are its last values")
    if reading.get("integrated_lufs") is None:
        warnings.append("Nothing above -70 LUFS measured yet: play the song")
    return result, warnings


async def measure_master(call: Call, query: MeterQuery) -> dict[str, Any]:
    _, warnings = find_meter(master_devices(await call("mixer.get", {})))
    if query.reset:
        request_reset()
        return {"ok": True, "reset": True, "warnings": warnings,
                "next": "Play the song (or the part to measure), then call measure_master again"}
    result, more = read_meter()
    result["is_playing"] = (await call("song.get", {}))["is_playing"]
    result["notes"] = ["Integrated loudness covers everything played since the last reset: reset, then play the whole "
                       "song once for whole-track comparisons. An excerpt describes only that excerpt; coverage is not verified.",
                       "peak_db is sample peak, not true peak; intersample peaks may exceed it by more than 0.5 dB.",
                       "Approximate, not conformance-validated. reading_fresh and the legacy measuring flag describe "
                       "file freshness, not playback; is_playing is Live's transport state."]
    result["warnings"] = warnings + more
    return result


def _age(updated: Any, path) -> float:
    try:
        return max(0.0, time.time() - datetime.fromisoformat(str(updated).replace("Z", "+00:00")).timestamp())
    except ValueError:
        return max(0.0, time.time() - path.stat().st_mtime)
