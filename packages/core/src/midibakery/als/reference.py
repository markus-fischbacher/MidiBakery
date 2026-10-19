"""A Set as a MidiBakery reference: the JSON the Reference Analyzer writes, from the Set's own data.

``bar_grid: "als"`` says the bars are the Set's own musical bars (from the first sounding bar): there is no
audio to warp, so the tempo may change and nothing drifts. plan_song follows the sections like any reference.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from midibakery.als import key as key_mod
from midibakery.als import roles as roles_mod
from midibakery.als import sections as sections_mod
from midibakery.als.reader import Song, read


def reference_id(path: str | Path) -> str:
    return "als-" + hashlib.sha1(str(Path(path).resolve()).encode()).hexdigest()[:12]


def summarize(song: Song, roles: dict[int, str]) -> dict[str, Any]:
    """What the importer lists for a Set: version, tempo, key and which roles it found."""
    counts: dict[str, int] = {}
    for role in roles.values():
        counts[role] = counts.get(role, 0) + 1
    return {
        "name": song.name,
        "file": song.path,
        "live": song.live_version.removeprefix("Ableton ").strip(),
        "tempo": round(song.tempo, 2),
        "beats_per_bar": song.beats_per_bar,
        "key": key_mod.detect(song, roles),
        "tracks": len(song.tracks),
        "roles": counts,
        "unknown": [t.name for t in song.tracks if roles.get(t.index) == "unknown"],
    }


def build(path: str | Path) -> dict[str, Any]:
    song = read(path)
    roles = roles_mod.assign(song)
    act, sections = sections_mod.sections(song, roles)
    if act is None:
        raise ValueError(f"{song.name} has no notes or clips on the Arrangement")
    return {
        **summarize(song, roles),
        "id": reference_id(path),
        "source": "als",
        "track": "",
        "analyzed": datetime.now(timezone.utc).isoformat(),
        "warped": True,
        "bar_grid": "als",
        "set_first_bar": act.first_bar,
        "first_bar": 1,
        "bars": act.bars,
        "sections": sections,
        "lanes": {role: [int(role in bar) for bar in act.grid] for role in roles_mod.PLAYING_ROLES},
        "track_roles": [{"index": t.index, "name": t.name, "role": roles[t.index]} for t in song.tracks],
    }
