"""measure_master: the Master's loudness from the MidiBakery Loudness Meter device.

The device (packages/m4l/src/midibakery-meter.js) measures after BS.1770 while Live plays and writes its
reading to <MidiBakery folder>/meter.json twice a second; a reset request is the file meter-reset, which
the device deletes. Its peaks are sample peaks: a true peak can lie up to ~0.5 dB higher.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from midibakery.bridge.client import BridgeError, config_dir

from .master import METER, is_meter, master_devices
from .plan import Call

STALE_SECONDS = 3.0  # the device writes every 0.5 s while Live plays
WHERE = "Audio Effects > Max Audio Effect > MidiBakery"


class MeterQuery(BaseModel):
    """Master loudness (LUFS) and peak from the MidiBakery Loudness Meter device while Live plays.
    reset=true restarts the integrated value and peak."""

    model_config = ConfigDict(extra="forbid")

    reset: bool = False


async def measure_master(call: Call, query: MeterQuery) -> dict[str, Any]:
    devices = master_devices(await call("mixer.get", {}))
    meter = next((i for i, d in enumerate(devices) if is_meter(d)), None)
    if meter is None:
        raise BridgeError("NOT_FOUND", f"No {METER} on the Master. Drag it from Live's browser ({WHERE}) onto the "
                          "Master as its last device, then play the song.", {"master_devices": list(devices)})
    warnings = []
    if after := devices[meter + 1:]:
        warnings.append(f"The meter is not the Master's last device: it does not hear {', '.join(after)}")
    if query.reset:
        config_dir().mkdir(parents=True, exist_ok=True)
        (config_dir() / "meter-reset").write_text("measure_master\n", encoding="utf-8")
        return {"ok": True, "reset": True, "warnings": warnings,
                "next": "Play the song (or the part to measure), then call measure_master again"}

    path = config_dir() / "meter.json"
    try:
        reading = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise BridgeError("NOT_FOUND", f"The {METER} has not measured anything yet: play the song in Live.") from None
    age = _age(reading.get("updated"), path)
    playing = age <= STALE_SECONDS
    result = {k: reading.get(k) for k in ("integrated_lufs", "short_term_lufs", "momentary_lufs", "peak_db",
                                          "short_term_peak_db", "measured_seconds")}
    result["measuring"] = playing
    if not playing:
        warnings.append(f"The meter stopped {age:.0f} s ago (the device is off or was removed, or Live is closed): "
                        "these are its last values")
    if reading.get("integrated_lufs") is None:
        warnings.append("Nothing above -70 LUFS measured yet: play the song")
    result["notes"] = ["Integrated loudness covers everything played since the last reset: reset, then play the whole "
                       "song (or the drop) for a number to compare.",
                       "peak_db is the sample peak since the reset; a true peak can be up to ~0.5 dB higher."]
    result["warnings"] = warnings
    return result


def _age(updated: Any, path) -> float:
    try:
        return max(0.0, time.time() - datetime.fromisoformat(str(updated).replace("Z", "+00:00")).timestamp())
    except ValueError:
        return max(0.0, time.time() - path.stat().st_mtime)
