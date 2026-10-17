"""Builds the macOS installer (.pkg) from the packaged app (packaging/build_app.py).

    uv run --group package python packaging/build_app.py
    python packaging/macos/build_pkg.py          # -> build/app/MidiBakery-<version>-macos-arm64.pkg

The package installs for the current user only ("Install for me only"), no administrator needed:
the app goes to ~/Library/Application Support/MidiBakery/runtime/<version>/, and its postinstall runs
`midibakery install`, which puts the Remote Script and the devices into the User Library Live uses and
keeps the API's settings of an earlier install. The same package updates an install. Not signed yet (D4e).
"""

from __future__ import annotations

import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
APP = ROOT / "build" / "app" / "midibakery"
WORK = ROOT / "build" / "work" / "pkg"
IDENTIFIER = "com.klirrwerk.midibakery"
LIVE_BUNDLE = "com.ableton.live"
VERSION = re.search(r'^__version__ = "([^"]+)"', (ROOT / "packages/core/src/midibakery/__init__.py").read_text(encoding="utf-8"), re.M)[1]

POSTINSTALL = """#!/bin/sh
# Runs as the user after the app landed in $2 (runtime/<version>): installs the Remote Script and the
# devices into Live's User Library. A failure fails the installation; the log says why.
LOG="$2/../../install.log"
echo "$(date) installing MidiBakery {version} from $2" >> "$LOG"
"$2/midibakery" install >> "$LOG" 2>&1
"""

DISTRIBUTION = """<?xml version="1.0" encoding="utf-8"?>
<installer-gui-script minSpecVersion="2">
    <title>MidiBakery {version}</title>
    <organization>com.klirrwerk</organization>
    <domains enable_anywhere="false" enable_currentUserHome="true" enable_localSystem="false"/>
    <options customize="never" require-scripts="false" hostArchitectures="{arch}"/>
    <welcome file="welcome.html" mime-type="text/html"/>
    <conclusion file="conclusion.html" mime-type="text/html"/>
    <installation-check script="liveIsNotRunning()"/>
    <script><![CDATA[
function liveIsNotRunning() {{
    if (system.applications.fromIdentifier("{live}")) {{
        my.result.type = "Warning";
        my.result.title = "Ableton Live is running";
        my.result.message = "You can install now: MidiBakery takes effect when you restart Live.";
        return false;
    }}
    return true;
}}
    ]]></script>
    <choices-outline>
        <line choice="{identifier}"/>
    </choices-outline>
    <choice id="{identifier}" visible="false" title="MidiBakery">
        <pkg-ref id="{identifier}"/>
    </choice>
    <pkg-ref id="{identifier}" version="{version}" onConclusion="none">MidiBakery-component.pkg</pkg-ref>
</installer-gui-script>
"""


def arch() -> str:
    return {"arm64": "arm64", "x86_64": "x86_64"}[platform.machine()]


def build(app: Path = APP) -> Path:
    if sys.platform != "darwin":
        raise SystemExit("pkgbuild and productbuild only exist on macOS")
    if not (app / "midibakery").exists():
        raise SystemExit(f"no app in {app}: run packaging/build_app.py first")
    shutil.rmtree(WORK, ignore_errors=True)
    scripts = WORK / "scripts"
    scripts.mkdir(parents=True)
    postinstall = scripts / "postinstall"
    postinstall.write_text(POSTINSTALL.format(version=VERSION))
    postinstall.chmod(0o755)
    root = WORK / "root"
    shutil.copytree(app, root, symlinks=True)
    component = WORK / "MidiBakery-component.pkg"
    subprocess.run([
        "pkgbuild", "--root", str(root), "--identifier", IDENTIFIER, "--version", VERSION,
        # in the user's home ("Install for me only"): ~/Library/Application Support/...
        "--install-location", f"/Library/Application Support/MidiBakery/runtime/{VERSION}",
        "--scripts", str(scripts), "--ownership", "recommended", str(component),
    ], check=True)
    distribution = WORK / "distribution.xml"
    distribution.write_text(DISTRIBUTION.format(version=VERSION, arch=arch(), identifier=IDENTIFIER, live=LIVE_BUNDLE))
    resources = WORK / "resources"
    shutil.copytree(HERE / "resources", resources)
    for page in resources.glob("*.html"):
        page.write_text(page.read_text(encoding="utf-8").replace("{version}", VERSION), encoding="utf-8")
    pkg = ROOT / "build" / "app" / f"MidiBakery-{VERSION}-macos-{'arm64' if arch() == 'arm64' else 'x64'}.pkg"
    subprocess.run([
        "productbuild", "--distribution", str(distribution), "--package-path", str(WORK),
        "--resources", str(resources), str(pkg),
    ], check=True)
    return pkg


if __name__ == "__main__":
    print(f"built {build().relative_to(ROOT)}")
