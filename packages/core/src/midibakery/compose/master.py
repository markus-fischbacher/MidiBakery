"""A master chain from sourced genre settings: EQ Eight (low cut), Glue Compressor, Limiter.

A starting point, not a finished master: nothing here hears the song. The Glue Compressor's
threshold is a convention to set by ear (1-2 dB of gain reduction on the loudest parts) and the
Limiter only catches peaks (no input gain), so the song gets no louder than the mix.

Sources and ratings: docs/GENRES.md, "Master chain". Measured in Live 12.4: the parameter names
below; Glue's Attack, Ratio and Release are steps (raw 0..6, 0..2, 0..6, shown as the values in
GLUE_*); a batch that inserts devices and then sets their parameters leaves two undo steps, so
apply runs two batches, one step each.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from midibakery.bridge.client import BridgeError
from midibakery.compose.structures import Genre

from .plan import Call
from .rollback import completed, undo

CHAIN = ("EQ Eight", "Glue Compressor", "Limiter")
GLUE_ATTACK_MS = (0.01, 0.1, 0.3, 1, 3, 10, 30)
GLUE_RATIO = (2, 4, 10)
GLUE_RELEASE = (0.1, 0.2, 0.4, 0.6, 0.8, 1.2, "auto")
METER = "MidiBakery Loudness Meter"  # measures what reaches it: the chain goes in before it
# A limiter or a chain of its own already on the master: MidiBakery leaves that master alone
_LIMITERS = ("limit", "maxim", "clipper", "ozone", "pro-l", "l2")


@dataclass(frozen=True)
class MasterStyle:
    label: str
    low_cut_hz: float
    low_cut_slope: Literal["High Pass 12dB", "High Pass 48dB"]
    glue_threshold_db: float = -10.0
    glue_attack_ms: float = 30
    glue_ratio: int = 2
    glue_release: float | str = "auto"
    glue_sidechain_hz: float = 150.0  # the kick and sub do not pump the whole mix
    ceiling_db: float = -1.0


# Four-on-the-floor genres: a gentle cut, inaudible at 30 Hz. Sub-heavy genres (808s, Reese subs
# down to 25 Hz): a steep cut lower down, so the sub keeps its weight.
STYLES: dict[str, MasterStyle] = {
    "house": MasterStyle("House", 30, "High Pass 12dB"),
    "melodic_techno": MasterStyle("Melodic Techno", 30, "High Pass 12dB"),
    "peak_time_techno": MasterStyle("Peak-Time Techno", 30, "High Pass 12dB"),
    "drum_and_bass": MasterStyle("Drum & Bass", 20, "High Pass 48dB"),
    "trap": MasterStyle("Trap", 20, "High Pass 48dB"),
}
GENERIC = MasterStyle("any genre", 30, "High Pass 12dB")


class MasterRequest(BaseModel):
    """A master chain (EQ Eight low cut, Glue Compressor, Limiter) with the genre's settings."""

    model_config = ConfigDict(extra="forbid")

    genre: Genre | None = None  # omitted: settings that suit any genre
    ceiling_db: float = Field(-1.0, ge=-3.0, le=-0.1)  # Limiter ceiling, true peak; -1 dB suits streaming


@dataclass
class MasterPlan:
    id: str
    style: MasterStyle
    ceiling_db: float
    existing: tuple[str, ...]  # the master's devices when planned: apply checks they did not change
    warnings: list[str] = field(default_factory=list)

    @property
    def first(self) -> int:
        """Where the chain goes: before the Loudness Meter, else at the end."""
        return next((i for i, d in enumerate(self.existing) if is_meter(d)), len(self.existing))

    def settings(self) -> list[tuple[str, list[tuple[str, dict[str, Any]]]]]:
        """(device, [(parameter, value or display)]) as device.set_param takes them."""
        s = self.style
        return [
            ("EQ Eight", [("1 Filter On A", {"display": "On"}), ("1 Filter Type A", {"display": s.low_cut_slope}),
                          ("1 Frequency A", {"display": s.low_cut_hz})]),
            ("Glue Compressor", [("Threshold", {"display": s.glue_threshold_db}),
                                 ("Attack", {"value": float(GLUE_ATTACK_MS.index(s.glue_attack_ms))}),
                                 ("Ratio", {"value": float(GLUE_RATIO.index(s.glue_ratio))}),
                                 ("Release", {"value": float(GLUE_RELEASE.index(s.glue_release))}),
                                 ("S/C EQ On", {"display": "On"}), ("S/C EQ Type", {"display": "High pass"}),
                                 ("S/C EQ Freq", {"display": s.glue_sidechain_hz})]),
            ("Limiter", [("Ceiling", {"display": self.ceiling_db}), ("Mode", {"display": "True Peak"})]),
        ]

    def insert_ops(self) -> list[dict[str, Any]]:
        return [{"op": "device.insert", "params": {"master": True, "name": name, "index": self.first + i}}
                for i, name in enumerate(CHAIN)]

    def param_ops(self) -> list[dict[str, Any]]:
        return [{"op": "device.set_param", "params": {"master": True, "device": self.first + i, "parameter": p, **v}}
                for i, (_, params) in enumerate(self.settings()) for p, v in params]

    def chain(self) -> list[dict[str, Any]]:
        s = self.style
        release = "Auto" if s.glue_release == "auto" else f"{s.glue_release} s"
        return [
            {"device": "EQ Eight", "settings": f"low cut {s.low_cut_hz:g} Hz, {s.low_cut_slope.removeprefix('High Pass ')}/oct slope"},
            {"device": "Glue Compressor", "settings": f"ratio {s.glue_ratio}:1, attack {s.glue_attack_ms:g} ms, release {release}, "
                                                      f"threshold {s.glue_threshold_db:g} dB, sidechain high pass {s.glue_sidechain_hz:g} Hz"},
            {"device": "Limiter", "settings": f"ceiling {self.ceiling_db:g} dB true peak, input gain 0 dB"},
        ]

    def preview(self) -> dict[str, Any]:
        return {
            "plan_id": self.id,
            "genre": self.style.label,
            "master_chain": self.chain(),
            **({"after": list(self.existing)} if self.existing else {}),
            "notes": [
                "A starting point, not a finished master: MidiBakery cannot hear the song.",
                "Play the loudest part and turn the Glue Compressor's threshold until its needle shows 1-2 dB.",
                "The Limiter only catches peaks (input gain 0 dB); the song gets no louder than the mix.",
            ],
            "warnings": self.warnings,
            "next": "apply_plan(plan_id) puts the chain on the Master; two undo steps remove it",
        }


def master_devices(mixer: dict[str, Any]) -> tuple[str, ...]:
    return tuple(mixer.get("master", {}).get("devices") or ())


def is_meter(device: str) -> bool:
    return "loudness meter" in device.lower()


async def build_master(call: Call, request: MasterRequest) -> MasterPlan:
    existing = master_devices(await call("mixer.get", {}))
    taken = [d for d in existing if d in CHAIN or any(w in d.lower() for w in _LIMITERS)]
    if taken:
        raise BridgeError("CONFLICT", f"The Master already has {', '.join(repr(d) for d in taken)}: MidiBakery puts its chain only "
                          "on a Master without one. Delete those devices in Live first, or adjust them yourself.",
                          {"master_devices": list(existing)})
    style = STYLES[request.genre] if request.genre else GENERIC
    plan = MasterPlan(secrets.token_hex(4), style, request.ceiling_db, existing)
    if before := existing[:plan.first]:
        plan.warnings.append(f"The Master's {', '.join(before)} stay(s) before the new chain")
    return plan


async def apply_master(call: Call, plan: MasterPlan) -> dict[str, Any]:
    """The devices (one undo step), then their settings (a second): Live closes the step between."""
    if master_devices(await call("mixer.get", {})) != plan.existing:
        raise BridgeError("CONFLICT", f"The Master's devices changed since master plan {plan.id} was made; plan again")
    try:
        await call("batch", {"ops": plan.insert_ops(), "label": f"MidiBakery master {plan.id}: devices"})
    except BridgeError as exc:
        await undo(call, exc, 1 if completed(exc) else 0, "the Master is unchanged")
        raise
    try:
        await call("batch", {"ops": plan.param_ops(), "label": f"MidiBakery master {plan.id}: settings"})
    except BridgeError as exc:
        await undo(call, exc, 1 + (1 if completed(exc) else 0), "the Master is unchanged")
        raise
    return {
        "ok": True,
        "master_chain": plan.chain(),
        "devices": {name: plan.first + i for i, name in enumerate(CHAIN)},
        "undo": "2 undo steps remove the chain (settings, then devices)",
        "next": "Play the loudest part and set the Glue Compressor's threshold for 1-2 dB of gain reduction",
    }
