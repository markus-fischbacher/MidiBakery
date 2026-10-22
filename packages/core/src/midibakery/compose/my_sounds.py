"""The user's default preset per part: ``sounds.json`` in the MidiBakery folder, e.g. {"lead": "Synth Keys/Light Keys.adg"}.

A new track of that part loads it instead of the genre's preset. A path starts in the browser's "sounds" folder;
"packs/Core Library/..." or any other first folder name is used as given.
"""
from __future__ import annotations

import json
from pathlib import Path

from midibakery.bridge.client import config_dir
from midibakery.compose.structures import ROLES

ROOTS = {"sounds", "packs", "plugins", "user_library", "drums", "instruments", "audio_effects", "midi_effects"}


def sounds_path() -> Path:
    return config_dir() / "sounds.json"


def load() -> dict[str, tuple[str, ...]]:
    """Role -> browser path; a missing or broken file, unknown roles and empty paths count as none."""
    try:
        data = json.loads(sounds_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out: dict[str, tuple[str, ...]] = {}
    for role, path in (data.items() if isinstance(data, dict) else ()):
        if role in ROLES and isinstance(path, str) and path.strip("/"):
            out[role] = parse(path)
    return out


def parse(path: str) -> tuple[str, ...]:
    parts = tuple(p for p in path.strip("/").split("/") if p)
    return parts if parts[0] in ROOTS else ("sounds", *parts)


def save(role: str, path: str | None) -> dict[str, str]:
    """Set (or, with no path, clear) one part's default; returns what is stored."""
    if role not in ROLES:
        raise ValueError(f"part: one of {', '.join(ROLES)}")
    try:
        data = json.loads(sounds_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    data = data if isinstance(data, dict) else {}
    if path:
        data[role] = "/".join(parse(path))
    else:
        data.pop(role, None)
    sounds_path().parent.mkdir(parents=True, exist_ok=True)
    sounds_path().write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


# What the picker searches Live's browser for, per part: (category, words); the first words come first.
SEARCHES: dict[str, tuple[tuple[str, str], ...]] = {
    "drums": (("drums", "kit"),),
    "bass": (("sounds", "bass"),),
    "chords": (("sounds", "pad"), ("sounds", "keys"), ("sounds", "stab")),
    "lead": (("sounds", "lead"), ("sounds", "keys"), ("sounds", "pluck")),
}


async def presets(call, part: str, limit: int = 60) -> list[dict[str, str]]:
    """Presets of Live's browser that suit a part: name and the path `save` takes."""
    if part not in SEARCHES:
        raise ValueError(f"part: one of {', '.join(SEARCHES)}")
    found: dict[str, dict[str, str]] = {}
    for category, words in SEARCHES[part]:
        result = await call("browser.search", {"query": words, "category": category, "limit": limit})
        for item in result.get("items", []):
            path = "/".join(item["path"])
            found.setdefault(path, {"name": item["name"].rsplit(".", 1)[0], "path": path})
    return sorted(found.values(), key=lambda p: p["name"].lower())
