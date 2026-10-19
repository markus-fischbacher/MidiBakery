"""Finds Sets on disk and keeps the imported ones: <MidiBakery folder>/references/als-<id>.json.

The Reference Analyzer's folder, so get_reference and plan_song(reference=...) see imported Sets with
no other change. Nothing leaves the user's machine and nothing is shipped with the product.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from midibakery.als.reader import AlsError
from midibakery.als.reference import build, reference_id
from midibakery.bridge.client import config_dir

SKIP_DIRS = {"Backup", "Samples", "Ableton Project Info", ".git", "node_modules"}
MAX_FILES = 2000


def references_dir() -> Path:
    return config_dir() / "references"


def find_sets(path: str | Path) -> list[Path]:
    """The .als files of a file or folder, folders searched recursively; Backup folders and the
    backup copies Live keeps are skipped."""
    if not str(path).strip():
        raise ValueError("path: expected a file or folder")
    root = Path(path).expanduser()
    if root.is_file():
        if root.suffix.lower() != ".als":
            raise ValueError(f"{root.name} is not a Live Set (.als)")
        return [root]
    if not root.is_dir():
        raise ValueError(f"No such file or folder: {root}")
    found: list[Path] = []
    for current, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
        for name in sorted(files):
            if name.lower().endswith(".als") and not name.startswith("."):
                found.append(Path(current, name))
        if len(found) > MAX_FILES:
            raise ValueError(f"More than {MAX_FILES} Sets there; choose a smaller folder")
    return found


def imported_ids() -> dict[str, str]:
    """id -> reference file name of every imported Set."""
    out = {}
    for file in references_dir().glob("als-*.json"):
        out[file.stem] = file.name
    return out


def listing(files: list[Path]) -> list[dict[str, Any]]:
    done = imported_ids()
    return [{"file": str(f), "name": f.stem, "id": reference_id(f), "imported": reference_id(f) in done,
             "folder": f.parent.name} for f in files]


def preview(path: str | Path) -> dict[str, Any]:
    """The whole analysis of one Set (nothing is stored)."""
    path = Path(path).expanduser()
    if path.suffix.lower() != ".als" or not path.is_file():
        raise ValueError(f"Not a Live Set: {path}")
    try:
        return build(path)
    except AlsError as exc:
        raise ValueError(str(exc)) from exc


def store(analysis: dict[str, Any], genre: str | None = None) -> dict[str, Any]:
    if genre:
        analysis = {**analysis, "genre": genre}
    folder = references_dir()
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{analysis['id']}.json").write_text(json.dumps(analysis, indent=1), encoding="utf-8")
    return analysis


def run(files: list[str], genres: dict[str, str] | None = None) -> dict[str, Any]:
    """Imports each Set; one that fails is reported and the others still go through."""
    imported, failed = [], []
    for file in files:
        try:
            analysis = store(preview(file), (genres or {}).get(file))
            imported.append({"file": file, "id": analysis["id"], "name": analysis["name"], "bars": analysis["bars"],
                             "sections": len(analysis["sections"])})
        except (ValueError, OSError) as exc:
            failed.append({"file": file, "error": str(exc)})
    return {"imported": imported, "failed": failed}


def library() -> list[dict[str, Any]]:
    out = []
    for file in sorted(references_dir().glob("als-*.json")):
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        out.append({k: data.get(k) for k in ("id", "name", "file", "live", "tempo", "key", "bars", "genre", "tracks", "roles",
                                             "unknown", "lanes", "sections")})
    return sorted(out, key=lambda item: (str(item["name"]).lower(), str(item["id"])))


def delete(reference: str) -> bool:
    if not re.fullmatch(r"als-[0-9a-f]{12}", reference):
        raise ValueError("Not an imported Set")
    path = references_dir() / f"{reference}.json"
    if not path.exists():
        return False
    path.unlink()
    return True


def pick(kind: str) -> str:
    """Ask the user for a Live Set ("file") or a folder ("folder") in the system's file dialog; "" when cancelled.
    For the importer page in a browser, which cannot read a path from its own file dialog. macOS only."""
    if kind not in ("file", "folder"):
        raise ValueError("kind: expected file or folder")
    if sys.platform != "darwin":
        raise ValueError("The file dialog is only available on macOS; type the path instead")
    choose = ('choose file with prompt "Choose a Live Set" of type {"als"}' if kind == "file"
              else 'choose folder with prompt "Choose a folder with Live Sets"')
    try:
        done = subprocess.run(["osascript", "-e", f"POSIX path of ({choose})"], capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        return ""
    return done.stdout.strip() if done.returncode == 0 else ""  # a cancelled dialog exits with an error


# The importer's list of Sets, shared by every page that shows it (the device and a popped-out browser tab).
# In memory: it is a work list, not data; the API restarting empties it.
QUEUE_FIELDS = {"file": str, "name": str, "folder": str, "id": str, "imported": bool, "selected": bool, "genre": str}
_queue: dict[str, Any] = {"rev": 0, "sets": []}


def queue() -> dict[str, Any]:
    return _queue


def set_queue(sets: Any) -> dict[str, Any]:
    if not isinstance(sets, list) or len(sets) > MAX_FILES:
        raise ValueError("sets: expected a list")
    kept = []
    for item in sets:
        if not isinstance(item, dict) or not isinstance(item.get("file"), str):
            raise ValueError("sets: every entry needs a file")
        kept.append({k: item[k] for k, kind in QUEUE_FIELDS.items() if isinstance(item.get(k), kind)})
    _queue["sets"] = kept
    _queue["rev"] += 1
    return _queue
