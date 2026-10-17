"""MidiBakery has one version: the package's (midibakery.__version__). Everything else takes or mirrors it."""

import re
import subprocess
import sys
import tomllib
from pathlib import Path

import midibakery
from MidiBakery import protocol  # the Remote Script (conftest puts it on the path)
from midibakery.api import server as api_server

ROOT = Path(__file__).resolve().parents[1]


def test_the_version_is_major_minor_patch():
    # The devices send it as a Max message atom: x.y.z stays a symbol, while "1.0" would turn into a float.
    assert re.fullmatch(r"\d+\.\d+\.\d+", midibakery.__version__)


def test_the_remote_script_carries_the_same_version():
    assert protocol.BRIDGE_VERSION == midibakery.__version__


def test_the_package_metadata_reads_it_from_the_module():
    project = tomllib.loads((ROOT / "packages/core/pyproject.toml").read_text())
    assert "version" not in project["project"] and "version" in project["project"]["dynamic"]
    assert project["tool"]["hatch"]["version"]["path"] == "src/midibakery/__init__.py"


def test_api_and_cli_report_it():
    assert api_server.VERSION == midibakery.__version__
    result = subprocess.run([sys.executable, "-m", "midibakery.cli", "--version"], capture_output=True, text=True)
    assert result.stdout.strip() == f"MidiBakery {midibakery.__version__}"
