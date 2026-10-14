import json
import shutil
import subprocess

import pytest

from midishower.catalog import OPS
from midishower.cli import MANIFEST_PATH, SCRIPT_SOURCE, manifest_json


def test_manifest_is_up_to_date():
    assert MANIFEST_PATH.read_text() == manifest_json(), "run `uv run midishower manifest`"


def test_every_op_has_a_handler_and_vice_versa():
    from MidiShower.registry import HANDLERS
    import MidiShower.ops  # noqa: F401

    assert set(HANDLERS) == set(OPS)


def test_manifest_flags_match_catalog():
    ops = json.loads(MANIFEST_PATH.read_text())["ops"]
    for name, spec in OPS.items():
        assert ops[name]["read_only"] == spec.read_only
        assert ops[name]["destructive"] == spec.destructive


def test_remote_script_compiles_on_lives_python():
    """Live 12 embeds Python 3.11; the bridge must not use newer syntax."""
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv not available")
    found = subprocess.run([uv, "python", "find", "3.11"], capture_output=True, text=True)
    if found.returncode != 0:
        pytest.skip("Python 3.11 not installed (uv python install 3.11)")
    result = subprocess.run(
        [found.stdout.strip(), "-I", "-c", "import compileall,sys; sys.exit(not compileall.compile_dir(sys.argv[1], quiet=1, legacy=False, workers=1, force=True, ddir='x'))", str(SCRIPT_SOURCE)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
