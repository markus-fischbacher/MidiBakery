"""The user's default preset per part: ``sounds.json`` in the MidiBakery folder, e.g. {"lead": "Synth Keys/Light Keys.adg",
"genres": {"trap": {"bass": "Bass/808 Pure.adg"}}}: the top level holds every genre's, "genres" one genre's own (it wins).

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


def _read() -> dict:
    try:
        data = json.loads(sounds_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _valid(data: object) -> dict[str, str]:
    return {role: path for role, path in (data.items() if isinstance(data, dict) else ())
            if role in ROLES and isinstance(path, str) and path.strip("/")}


def stored(genre: str | None = None) -> dict[str, str]:
    """Role -> path as stored: the genre's own presets over the ones for every genre."""
    data = _read()
    mine = _valid(data)
    if genre:
        mine.update(_valid((data.get("genres") or {}).get(genre)))
    return mine


def load(genre: str | None = None) -> dict[str, tuple[str, ...]]:
    """Role -> browser path for new tracks of a genre; a missing or broken file, unknown roles and empty paths count as none."""
    return {role: parse(path) for role, path in stored(genre).items()}


def parse(path: str) -> tuple[str, ...]:
    parts = tuple(p for p in path.strip("/").split("/") if p)
    return parts if parts[0] in ROOTS else ("sounds", *parts)


def save(role: str, path: str | None, genre: str | None = None) -> dict[str, str]:
    """Set (or, with no path, clear) one part's default, for one genre or for every genre; returns what then applies."""
    if role not in ROLES:
        raise ValueError(f"part: one of {', '.join(ROLES)}")
    data = _read()
    scope = data.setdefault("genres", {}).setdefault(genre, {}) if genre else data
    if not isinstance(scope, dict):
        scope = data["genres"][genre] = {}
    if path:
        scope[role] = "/".join(parse(path))
    else:
        scope.pop(role, None)
    if not data.get("genres", {}).get(genre if genre else "", True):
        del data["genres"][genre]
    if not data.get("genres"):
        data.pop("genres", None)
    sounds_path().parent.mkdir(parents=True, exist_ok=True)
    sounds_path().write_text(json.dumps(data, indent=2), encoding="utf-8")
    return stored(genre)


# What the picker searches Live's browser for, per part: (category, words); the first words come first.
SEARCHES: dict[str, tuple[tuple[str, str], ...]] = {
    "drums": (("drums", "kit"),),
    "bass": (("sounds", "bass"),),
    "chords": (("sounds", "pad"), ("sounds", "keys"), ("sounds", "stab")),
    "lead": (("sounds", "lead"), ("sounds", "keys"), ("sounds", "pluck")),
}


async def presets(call, part: str, limit: int = 60, query: str = "") -> list[dict[str, str]]:
    """Presets of Live's browser that suit a part (or, with `query`, whose name has those words): name and the path `save` takes."""
    if part not in SEARCHES:
        raise ValueError(f"part: one of {', '.join(SEARCHES)}")
    found: dict[str, dict[str, str]] = {}
    searches = ((SEARCHES[part][0][0], query.strip()),) if query.strip() else SEARCHES[part]
    for category, words in searches:
        result = await call("browser.search", {"query": words, "category": category, "limit": limit})
        for item in result.get("items", []):
            path = "/".join(item["path"])
            found.setdefault(path, {"name": item["name"].rsplit(".", 1)[0], "path": path})
    return sorted(found.values(), key=lambda p: p["name"].lower())


PRESET_SUFFIXES = (".adg", ".adv", ".adp")


async def resolve(call, file: str) -> str:
    """The browser path of a preset file dragged out of Live's browser: its name is searched in the browser."""
    name = file.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
    if not name.lower().endswith(PRESET_SUFFIXES):
        raise ValueError(f"'{name}' is not a preset (.adg, .adv or .adp): drag one from Live's browser")
    stem = name.rsplit(".", 1)[0]
    result = await call("browser.search", {"query": stem, "category": "all", "limit": 40})
    items = [i for i in result.get("items", []) if i["name"].lower() == name.lower()]
    if not items:
        raise ValueError(f"'{name}' was not found in Live's browser")
    return "/".join(min(items, key=lambda i: len(i["path"]))["path"])  # the shallowest: the library's own, not a copy
