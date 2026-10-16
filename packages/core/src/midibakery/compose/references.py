"""Reference songs the MidiBakery Reference Analyzer device analyzed in Live.

The device writes one JSON file per song to <MidiBakery folder>/references: name, file,
track, tempo, key ("D# minor", "?" when unsure) and sections with name, kind (intro,
build, drop, break, groove, outro), start_bar and bars.
"""

from __future__ import annotations

import json
import re
from typing import Any

from midibakery.bridge.client import config_dir
from midibakery.compose.theory import MAJOR, NOTE_NAMES, Scale

MINOR = (0, 2, 3, 5, 7, 8, 10)
FLATS = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#"}


def load_references() -> list[dict[str, Any]]:
    """Every readable analysis, newest first."""
    found = []
    for path in (config_dir() / "references").glob("*.json"):
        try:
            found.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    found.sort(key=lambda r: r.get("analyzed", ""), reverse=True)
    return found


def find_reference(name: str) -> dict[str, Any] | None:
    """The newest analysis whose song, file or track name contains `name` (any case)."""
    wanted = name.casefold()
    return next((r for r in load_references() if any(wanted in str(r.get(k, "")).casefold() for k in ("name", "file", "track"))), None)


def reference_scale(key: str | None) -> Scale | None:
    """'D# minor?' -> D# Minor; None for a missing or unreadable key."""
    match = re.match(r"\s*([A-G][#b]?)\s*(major|minor)", key or "", re.I)
    if not match:
        return None
    root = FLATS.get(match[1], match[1])
    if root not in NOTE_NAMES:
        return None
    minor = match[2].lower() == "minor"
    return Scale(NOTE_NAMES.index(root), MINOR if minor else MAJOR, "Minor" if minor else "Major")
