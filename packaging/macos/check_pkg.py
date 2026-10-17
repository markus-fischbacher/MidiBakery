"""After `installer -pkg MidiBakery-*.pkg -target CurrentUserHomeDirectory` (CI, macOS): is everything where it
belongs, and does the app's uninstall take it all away again? Standard library only.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOME = Path.home()
CONFIG = HOME / "Library/Application Support/MidiBakery"
VERSION = re.search(r'^__version__ = "([^"]+)"', (ROOT / "packages/core/src/midibakery/__init__.py").read_text(encoding="utf-8"), re.M)[1]


def check(condition: bool, message: str) -> None:
    if not condition:
        log = CONFIG / "install.log"
        if log.exists():
            print(log.read_text())
        raise SystemExit(f"FAILED: {message}")
    print(f"ok  {message}")


def main() -> int:
    app = CONFIG / "runtime" / VERSION / "midibakery"
    check(app.is_file(), f"the app is in {app.parent}")
    record = json.loads((CONFIG / "installed.json").read_text())
    check(record["version"] == VERSION and record["api"] is True, "postinstall ran `midibakery install`")
    library = Path(record["library"])
    check((library / "Remote Scripts/MidiBakery/__init__.py").exists(), f"the Remote Script is in {library}")
    check(all((library / p).exists() for p in record["paths"]), f"all {len(record['paths'])} paths exist")
    launcher = json.loads((CONFIG / "launcher.json").read_text())
    check(Path(launcher["command"][0]) == app, "Live will start the installed app's API")
    receipts = subprocess.run(["pkgutil", "--volume", str(HOME), "--pkgs"], capture_output=True, text=True).stdout
    check("com.klirrwerk.midibakery" in receipts.split(), "macOS has the package's receipt")

    subprocess.run([str(app), "uninstall"], check=True)
    check(not (CONFIG / "runtime").exists(), "uninstall removed the app")
    check(not any((library / p).exists() for p in record["paths"]), "uninstall removed the Remote Script and the devices")
    receipts = subprocess.run(["pkgutil", "--volume", str(HOME), "--pkgs"], capture_output=True, text=True).stdout
    check("com.klirrwerk.midibakery" not in receipts.split(), "uninstall forgot the receipt")
    print("macOS installer check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
