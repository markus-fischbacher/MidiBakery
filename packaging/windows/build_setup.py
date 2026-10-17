"""Builds the Windows setup (Inno Setup 6) from the packaged app (packaging/build_app.py).

    uv run --group package python packaging/build_app.py
    python packaging/windows/build_setup.py      # -> build/app/MidiBakery-<version>-windows-x64-setup.exe

Needs Inno Setup's compiler (ISCC.exe), installed or on PATH. Not signed yet (D4e).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
APP = ROOT / "build" / "app" / "midibakery"
OUT = ROOT / "build" / "app"
VERSION = re.search(r'^__version__ = "([^"]+)"', (ROOT / "packages/core/src/midibakery/__init__.py").read_text(encoding="utf-8"), re.M)[1]


def iscc() -> Path:
    found = shutil.which("ISCC")
    if found:
        return Path(found)
    # the standard places: Program Files (x86) for a machine-wide install, Local\Programs for a per-user one
    bases = [os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"),
             os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs")]
    for base in filter(None, bases):
        candidates = sorted(Path(base).glob("Inno Setup*/ISCC.exe"), reverse=True)
        if candidates:
            return candidates[0]
    raise SystemExit("Inno Setup's ISCC.exe not found: install Inno Setup 6 (https://jrsoftware.org)")


def build(app: Path = APP) -> Path:
    if not (app / "midibakery.exe").exists():
        raise SystemExit(f"no Windows app in {app}: run packaging/build_app.py on Windows first")
    subprocess.run([str(iscc()), f"/DVersion={VERSION}", f"/DAppSource={app}", f"/DOutputDir={OUT}",
                    str(HERE / "midibakery.iss")], check=True)
    return OUT / f"MidiBakery-{VERSION}-windows-x64-setup.exe"


if __name__ == "__main__":
    if sys.platform != "win32":
        raise SystemExit("Inno Setup builds on Windows")
    print(f"built {build().relative_to(ROOT)}")
