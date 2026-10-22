"""Builds the packaged MidiBakery app: one folder with the `midibakery` program, its Python and the
payload `midibakery install` copies into Live (the Remote Script and the built Max for Live devices).

    uv run --group package python packaging/build_app.py
    -> build/app/midibakery/                  the app folder (installers put it in runtime/<version>/)
    -> build/app/MidiBakery-<version>-<os>-<arch>.zip

PyInstaller freezes for the system it runs on: macOS builds on a Mac, Windows on Windows (CI does both).
The app is not signed here (D4e).
"""

from __future__ import annotations

import argparse
import importlib.util
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build" / "app"
ENTRY = Path(__file__).with_name("entry.py")
VERSION = re.search(r'^__version__ = "([^"]+)"', (ROOT / "packages/core/src/midibakery/__init__.py").read_text(encoding="utf-8"), re.M)[1]

# Imported by name at runtime, invisible to PyInstaller's analysis.
HIDDEN = [
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
]


def platform_name() -> str:
    system = {"darwin": "macos", "win32": "windows"}.get(sys.platform, sys.platform)
    machine = platform.machine().lower()
    arch = {"x86_64": "x64", "amd64": "x64", "arm64": "arm64", "aarch64": "arm64"}.get(machine, machine)
    return f"{system}-{arch}"


def stage_payload(work: Path) -> Path:
    """build/app/work/payload: what install.payload() finds in the app (remote_script/, devices/)."""
    payload = work / "payload"
    shutil.rmtree(payload, ignore_errors=True)
    shutil.copytree(ROOT / "packages/remote_script/MidiBakery", payload / "remote_script/MidiBakery",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    spec = importlib.util.spec_from_file_location("midibakery_m4l_build", ROOT / "packages/m4l/build.py")
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)
    build.build(payload / "devices")
    return payload


def freeze(payload: Path, work: Path) -> Path:
    command = [
        sys.executable, "-m", "PyInstaller", str(ENTRY),
        "--name", "midibakery", "--onedir", "--console", "--noconfirm", "--clean",
        "--distpath", str(OUT), "--workpath", str(work / "pyinstaller"), "--specpath", str(work),
        "--collect-data", "midibakery",  # chat.html, importer.html
        "--collect-submodules", "midibakery",
        "--add-data", f"{payload}{':' if sys.platform != 'win32' else ';'}payload",
    ]
    for name in HIDDEN:
        command += ["--hidden-import", name]
    if sys.platform == "darwin":
        command += ["--osx-bundle-identifier", "com.klirrwerk.midibakery"]
    subprocess.run(command, check=True, cwd=ROOT)
    return OUT / "midibakery"


def archive(app: Path) -> Path:
    base = OUT / f"MidiBakery-{VERSION}-{platform_name()}"
    # zip keeps the executable bit on macOS through shutil (it stores the mode in external_attr)
    return Path(shutil.make_archive(str(base), "zip", root_dir=app.parent, base_dir=app.name))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--no-archive", action="store_true", help="only the app folder")
    args = parser.parse_args(argv)
    work = ROOT / "build" / "work"
    work.mkdir(parents=True, exist_ok=True)
    payload = stage_payload(work)
    app = freeze(payload, work)
    print(f"built {app.relative_to(ROOT)} ({VERSION}, {platform_name()})")
    if not args.no_archive:
        print(f"archived {archive(app).relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
