"""The two-pass apply logic of the MIDI Tool v8 code, run in Node with stubbed Max globals."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAX_NODE = Path("/Applications/Max.app/Contents/Resources/C74/packages/Node for Max/source/bin/osx/node/node")
NODE = str(MAX_NODE) if MAX_NODE.exists() else shutil.which("node")


@pytest.mark.skipif(NODE is None, reason="no Node.js available")
def test_generator_answers_synchronously_then_applies_the_cached_result(tmp_path):
    code = tmp_path / "miditool.js"
    code.write_text('var MODE = "generate";\n' + (ROOT / "packages/m4l/src/miditool.js").read_text())
    out = subprocess.run([NODE, str(ROOT / "tests/miditool_harness.js"), str(code), "basic"], capture_output=True, text=True, check=True)
    data = json.loads(out.stdout)
    log, body = data["log"], data["body"]

    dicts = [e for e in log if e[0] == "dict"]
    requests = [e for e in log if e[0] == "outlet" and e[1] == 1 and e[2] == "request"]
    bangs = [e for e in log if e[0] == "outlet" and e[1] == 2]

    # Every apply got exactly one synchronous answer.
    assert len(dicts) == 4
    assert dicts[0][2] == {"notes": []}                       # pass 1: generator adds nothing yet
    assert dicts[1][2]["notes"][0]["pitch"] == 69            # pass 2: cached result
    assert dicts[1][2]["notes"][0]["mute"] == 0               # booleans become ints for Max
    assert dicts[2][2] == dicts[1][2]                          # unchanged inputs stay cached
    assert len(requests) == 2                                  # first apply + after the density change
    assert len(bangs) == 2                                     # one re-apply per response + one per UI change
    assert ["task", "schedule"] in log                         # "click again" fallback armed after the re-apply

    assert body["kind"] == "drums"
    assert body["context"] == {"start": 4, "length": 16, "seed": 1,
                               "scale": {"root": 9, "intervals": [0, 2, 3, 5, 7, 8, 10], "name": "Minor"}}
    assert body["params"] == {"swing": 0, "density": 0.5, "style": "house", "chance": 1}


def _run(tmp_path, scenario):
    code = tmp_path / "miditool.js"
    code.write_text('var MODE = "generate";\n' + (ROOT / "packages/m4l/src/miditool.js").read_text())
    out = subprocess.run([NODE, str(ROOT / "tests/miditool_harness.js"), str(code), scenario], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


@pytest.mark.skipif(NODE is None, reason="no Node.js available")
def test_replace_clears_the_range_once_per_apply_cycle(tmp_path):
    data = _run(tmp_path, "replace")
    clears = [e for e in data["log"] if e[0] == "liveapi"]
    # once after the first response, once for the new cycle; never on in-cycle re-applies
    assert clears == [["liveapi", "live_set view detail_clip", "remove_notes_extended", 0, 128, 4, 16]] * 2
    after = data["after"]
    assert not [e for e in after if e[0] == "outlet" and e[1] == 1 and e[2] == "request"]  # no new API call
    kinds = [e[0] if e[0] != "outlet" else f"outlet{e[1]}" for e in after if e[0] in ("dict", "liveapi") or (e[0] == "outlet" and e[1] == 2)]
    assert kinds == ["dict", "liveapi", "outlet2", "dict"]  # empty answer, clear, re-trigger, cached notes
    last_dict = [e for e in after if e[0] == "dict"][-1]
    assert last_dict[2]["notes"][0]["pitch"] == 69


@pytest.mark.skipif(NODE is None, reason="no Node.js available")
def test_without_replace_nothing_is_cleared(tmp_path):
    data = _run(tmp_path, "replace-off")
    assert not [e for e in data["log"] if e[0] == "liveapi"]
