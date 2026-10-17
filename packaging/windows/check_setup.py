"""Runs the Windows setup as a user would (silently here, CI) and checks the install, an update in place
and the uninstaller. Standard library only.

    python packaging/windows/check_setup.py build/app/MidiBakery-<version>-windows-x64-setup.exe
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSION = re.search(r'^__version__ = "([^"]+)"', (ROOT / "packages/core/src/midibakery/__init__.py").read_text(encoding="utf-8"), re.M)[1]
APP_DIR = Path(os.environ["LOCALAPPDATA"]) / "Programs" / "MidiBakery"
CONFIG = Path(os.environ["APPDATA"]) / "MidiBakery"
SILENT = ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"]


def check(condition: bool, message: str) -> None:
    if not condition:
        for log in (APP_DIR / "install.log", ROOT / "build" / "setup.log"):
            if log.exists():
                print(f"--- {log}\n{log.read_text(errors='replace')}")
        raise SystemExit(f"FAILED: {message}")
    print(f"ok  {message}")


def run_setup(setup: Path) -> None:
    result = subprocess.run([str(setup), *SILENT, f"/LOG={ROOT / 'build' / 'setup.log'}"], timeout=300)
    check(result.returncode == 0, f"the setup exits with 0 (got {result.returncode})")


def main(setup: str) -> int:
    run_setup(Path(setup).resolve())
    app = APP_DIR / "runtime" / VERSION / "midibakery.exe"
    check(app.is_file(), f"the app is in {app.parent}")
    record = json.loads((CONFIG / "installed.json").read_text())
    check(record["version"] == VERSION and record["api"] is True, "the setup ran `midibakery install`")
    library = Path(record["library"])
    check((library / "Remote Scripts/MidiBakery/__init__.py").exists(), f"the Remote Script is in {library}")
    check(all((library / p).exists() for p in record["paths"]), f"all {len(record['paths'])} paths exist")
    launcher = json.loads((CONFIG / "launcher.json").read_text())
    check(Path(launcher["command"][0]) == app, "Live will start the installed app's API")

    # An update (here: the same version again) keeps the API's settings.
    subprocess.run([str(app), "install", "--api-provider", "lmstudio", "--api-port", "9123"], check=True)
    run_setup(Path(setup).resolve())
    launcher = json.loads((CONFIG / "launcher.json").read_text())
    check(launcher["provider"] == "lmstudio" and launcher["port"] == 9123, "an update keeps the API's settings")

    uninstaller = APP_DIR / "unins000.exe"
    check(uninstaller.is_file(), "the uninstaller is there")
    result = subprocess.run([str(uninstaller), *SILENT], timeout=300)
    check(result.returncode == 0, "the uninstaller exits with 0")
    # the uninstaller hands over to a copy of itself and returns; give it a moment
    import time

    deadline = time.monotonic() + 60
    while APP_DIR.exists() and time.monotonic() < deadline:
        time.sleep(0.5)
    check(not APP_DIR.exists(), "the uninstaller removed the app")
    check(not any((library / p).exists() for p in record["paths"]), "the uninstaller removed the Remote Script and the devices")
    check(not (CONFIG / "launcher.json").exists(), "Live no longer starts the API")
    print("Windows setup check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
