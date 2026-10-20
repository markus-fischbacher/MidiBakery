"""The user's own pattern library: patterns taken from imported Live Sets, one file per Set.

``<MidiBakery folder>/patterns/<set id>.json``. The names (``my_<set>_<bass|lead|drums|chords>_<n>``) work wherever a
built-in pattern name does, but they are not listed in tool descriptions: they are the user's, and the
local-model tool budget is full. ``list_patterns`` and the importer show them.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from midibakery.bridge.client import config_dir
from midibakery.compose.bass_templates import BassTemplate, TNote
from midibakery.compose.lead_templates import LeadTemplate, LNote, Part
from midibakery.compose.techno_templates import DrumHit, TechnoPattern

KINDS = ("bass", "lead", "drums", "chords")
PREFIX = "my_"


def patterns_dir() -> Path:
    return config_dir() / "patterns"


def _files() -> list[Path]:
    return sorted(patterns_dir().glob("als-*.json"))


def _read(file: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and isinstance(data.get("patterns"), list) else None


def entries() -> list[dict[str, Any]]:
    """Every stored pattern as its JSON record, with the Set it came from."""
    out = []
    for file in _files():
        data = _read(file)
        for item in (data or {}).get("patterns", []):
            if isinstance(item, dict) and item.get("kind") in KINDS and isinstance(item.get("name"), str):
                out.append({**item, "set": data.get("set", file.stem), "set_name": data.get("set_name", "")})
    return out


def names(kind: str) -> tuple[str, ...]:
    return tuple(e["name"] for e in entries() if e["kind"] == kind)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:24] or "set"


def save(set_id: str, set_name: str, items: list[dict[str, Any]]) -> None:
    """Replaces the patterns of one Set (importing it again refreshes them)."""
    folder = patterns_dir()
    file = folder / f"{set_id}.json"
    if not items:
        file.unlink(missing_ok=True)
        return
    folder.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps({"set": set_id, "set_name": set_name, "patterns": items}, indent=1), encoding="utf-8")


def remove(set_id: str) -> int:
    if not re.fullmatch(r"als-[0-9a-f]{12}", set_id):
        raise ValueError("Not an imported Set")
    file = patterns_dir() / f"{set_id}.json"
    count = len((_read(file) or {}).get("patterns", []))
    file.unlink(missing_ok=True)
    return count


def _entry(kind: str, name: str) -> dict[str, Any]:
    for item in entries():
        if item["kind"] == kind and item["name"] == name:
            return item
    raise KeyError(name)


def _bass(item: dict[str, Any]) -> BassTemplate:
    bars = tuple(tuple(TNote(int(n["step"]), float(n["length"]), int(n["interval"]), float(n["velocity"])) for n in bar)
                 for bar in item["bars"])
    low = int(item["low"])
    return BassTemplate(item["name"], item["label"], tuple(item.get("genres", ())), tuple(item.get("bpm", (100, 150))), bars,
                        low=low, high=low + 11, description=item.get("description", ""), source="als")


def _lead(item: dict[str, Any]) -> LeadTemplate:
    bars = tuple(tuple(LNote(int(n["step"]), float(n["length"]), int(n["degree"]), 0, float(n["velocity"])) for n in bar)
                 for bar in item["bars"])
    bpm = tuple(item.get("bpm", (100, 150)))
    return LeadTemplate(item["name"], item["label"], "scale", {"main": Part(bars)}, octave=3, bpm=bpm,  # type: ignore[arg-type]
                        genres=tuple(item.get("genres", ())), scale_hint=item.get("scale", ""),
                        description=item.get("description", ""), source="als")


def _drums(item: dict[str, Any]) -> TechnoPattern:
    bars = tuple(tuple(DrumHit(h["role"], float(h["step"]), float(h["velocity"]), float(h["length"])) for h in bar)
                 for bar in item["bars"])
    return TechnoPattern(item["name"], item["label"], "drums", item.get("description", ""), bars=bars)


def chords(name: str) -> tuple[str, float, str]:
    """A chord loop: (roman numerals, chords per bar, the mode they are read in)."""
    item = _entry("chords", name)
    return str(item["progression"]), float(item.get("chords_per_bar", 1.0)), str(item.get("scale", "minor"))


def load(kind: str, name: str) -> BassTemplate | LeadTemplate | TechnoPattern:
    item = _entry(kind, name)
    return {"bass": _bass, "lead": _lead, "drums": _drums}[kind](item)
