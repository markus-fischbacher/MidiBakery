"""Installs MidiBakery into Ableton Live: the Remote Script and the Max for Live devices into the User
Library, launcher.json (how the Remote Script starts the API) into the config folder.

installed.json in the config folder lists every path an install wrote. The next install removes what the
new version no longer has (a renamed device), and uninstall removes exactly those paths, nothing of the
user's. The files come from the payload: the repository (devices built on the spot) or, in the packaged
app, the payload folder next to it. Both installers run `midibakery install`, for a first install and
for every update.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from midibakery import __version__
from midibakery.bridge.client import config_dir

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT_NAME = "MidiBakery"
REMOTE_SCRIPTS = "Remote Scripts"
INSTALL_LIST = "install.json"  # the devices' list, written by packages/m4l/build.py
RECORD = "installed.json"
FOLDER_INFO = "Ableton Folder Info"  # Live's metadata in a browser folder, not the user's work
VERSION_DIR = re.compile(r"^\d+\.\d+\.\d+$")


@dataclass(frozen=True)
class Payload:
    remote_script: Path  # the MidiBakery Remote Script folder
    devices: Path  # built devices with INSTALL_LIST


def frozen() -> bool:
    """True in the packaged app (PyInstaller), where Python and the payload ship with MidiBakery."""
    return bool(getattr(sys, "frozen", False))


def payload() -> Payload:
    if frozen():
        root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "payload"
        return Payload(root / "remote_script" / SCRIPT_NAME, root / "devices")
    return repo_payload()


def repo_payload() -> Payload:
    """From a checkout: the Remote Script's sources and freshly built devices."""
    import importlib.util

    script = REPO_ROOT / "packages" / "remote_script" / SCRIPT_NAME
    build_py = REPO_ROOT / "packages" / "m4l" / "build.py"
    if not build_py.exists():
        raise SystemExit("No payload: run this from the MidiBakery repository or the installed app")
    spec = importlib.util.spec_from_file_location("midibakery_m4l_build", build_py)
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)
    build.build()
    return Payload(script, build.DIST)


# ---------------------------------------------------------------------------- where Live keeps things


def live_preferences() -> list[Path]:
    """Live's preference folders ("Live 12.4.6", ...), newest first."""
    if sys.platform == "darwin":
        root = Path.home() / "Library/Preferences/Ableton"
        folders = [p for p in root.glob("Live *") if p.is_dir()]
    elif sys.platform.startswith("win"):
        root = Path(os.environ.get("APPDATA", Path.home())) / "Ableton"
        folders = [p / "Preferences" for p in root.glob("Live *") if (p / "Preferences").is_dir()]
    else:
        return []

    def version(path: Path) -> tuple[int, ...]:
        name = path.parent.name if path.name == "Preferences" else path.name
        return tuple(int(n) for n in re.findall(r"\d+", name))

    return sorted(folders, key=version, reverse=True)


def library_from_config(cfg: Path) -> Path | None:
    """The User Library a Library.cfg names: <ProjectPath>/<ProjectName> of its UserLibrary project."""
    try:
        root = ET.parse(cfg).getroot()
    except (OSError, ET.ParseError):
        return None
    project = root.find("./ContentLibrary/UserLibrary/LibraryProject")
    if project is None:
        return None
    path, name = project.find("ProjectPath"), project.find("ProjectName")
    if path is None or name is None or not path.get("Value") or not name.get("Value"):
        return None
    return Path(path.get("Value")) / name.get("Value")


def default_library() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Music/Ableton/User Library"
    if sys.platform.startswith("win"):
        return Path.home() / "Documents/Ableton/User Library"
    raise SystemExit("Ableton Live only runs on macOS and Windows")


def user_library() -> Path:
    """The newest Live's User Library (it can be moved in Live's settings), else the default location."""
    for prefs in live_preferences():
        library = library_from_config(prefs / "Library.cfg")
        if library is not None:
            return library
    return default_library()


# ---------------------------------------------------------------------------- launcher.json


def launcher_command(provider: str, model: str | None, port: int) -> list[str]:
    if frozen():
        command = [sys.executable, "api", "--provider", provider, "--port", str(port)]
    else:
        command = [sys.executable, "-u", "-m", "midibakery.cli", "api", "--provider", provider, "--port", str(port)]
    return command + ["--model", model] if model else command


def write_launcher(provider: str, model: str | None, port: int) -> Path:
    """launcher.json tells the Remote Script how to start the API with Live."""
    path = config_dir() / "launcher.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    config = {"command": launcher_command(provider, model, port), "port": port, "version": __version__}
    if not frozen():
        config["cwd"] = str(REPO_ROOT)
    path.write_text(json.dumps(config, indent=2) + "\n")
    return path


def remove_launcher() -> None:
    (config_dir() / "launcher.json").unlink(missing_ok=True)


# ---------------------------------------------------------------------------- install / uninstall


def _record_path() -> Path:
    return config_dir() / RECORD


def read_record() -> dict | None:
    try:
        return json.loads(_record_path().read_text())
    except (OSError, ValueError):
        return None


def _remove(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def _prune_empty(folder: Path, library: Path) -> None:
    """Removes folders the install left empty (Live's folder info aside), up to the library itself."""
    while folder != library and library in folder.parents and folder.is_dir():
        rest = [p for p in folder.iterdir() if p.name != FOLDER_INFO]
        if rest:
            return
        shutil.rmtree(folder)
        folder = folder.parent


def install(library: Path, source: Payload, *, link: bool = False) -> dict:
    """Copies the Remote Script and the devices into `library` and records what it wrote."""
    devices = json.loads((source.devices / INSTALL_LIST).read_text(encoding="utf-8"))
    script_target = Path(REMOTE_SCRIPTS) / SCRIPT_NAME
    script = library / script_target
    script.parent.mkdir(parents=True, exist_ok=True)
    _remove(script)
    if link:
        script.symlink_to(source.remote_script, target_is_directory=True)
    else:
        shutil.copytree(source.remote_script, script, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    written = [script_target.as_posix()]
    for entry in devices["files"]:
        target = library / entry["target"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source.devices / entry["source"], target)
        written.append(entry["target"])

    # What the last install wrote and this one did not: a renamed device, or everything in a User Library
    # that Live no longer uses.
    previous = read_record()
    if previous and previous.get("library"):
        old_library = Path(previous["library"])
        keep = set(written) if old_library == library else set()
        for rel in set(previous.get("paths", [])) - keep:
            gone = old_library / rel
            _remove(gone)
            _prune_empty(gone.parent, old_library)

    record = {"version": __version__, "library": str(library), "paths": written}
    _record_path().parent.mkdir(parents=True, exist_ok=True)
    _record_path().write_text(json.dumps(record, indent=1) + "\n")
    return record


def uninstall(*, purge: bool = False) -> list[Path]:
    """Removes what installed.json lists and launcher.json; `purge` also the config folder (stored
    analyses, logs) and the stored Claude API key."""
    removed = []
    record = read_record()
    if record:
        library = Path(record["library"])
        for rel in record.get("paths", []):
            path = library / rel
            if path.exists() or path.is_symlink():
                _remove(path)
                removed.append(path)
            _prune_empty(path.parent, library)
    _record_path().unlink(missing_ok=True)
    remove_launcher()
    if purge:
        from midibakery import credentials

        credentials.store().delete()
        shutil.rmtree(config_dir(), ignore_errors=True)
    return removed


def prune_runtimes(current: Path) -> list[Path]:
    """The packaged app lives in runtime/<version>/; an update leaves the old version beside it, which
    may still run (an API from before the update) and on Windows cannot be deleted then. Removes the
    other version folders it can; the rest goes on a later install."""
    removed = []
    for sibling in current.parent.iterdir():
        if sibling != current and sibling.is_dir() and VERSION_DIR.match(sibling.name):
            try:
                shutil.rmtree(sibling)
                removed.append(sibling)
            except OSError:
                pass
    return removed
