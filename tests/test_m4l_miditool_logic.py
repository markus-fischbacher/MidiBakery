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
    assert ["nested-retrigger"] not in data["log"]  # Live answers "Did not receive a note dictionary in time"
    clears = [e for e in data["log"] if e[0] == "liveapi"]
    # once after the first response, once for the new cycle; never on in-cycle re-applies
    assert clears == [["liveapi", "live_set view detail_clip", 7, "remove_notes_extended", 0, 128, 4, 16]] * 2
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


def _writes(data):
    return [e for e in data["log"] if e[0] == "liveapi" or (e[0] == "outlet" and e[1] == 2) or (e[0] == "dict" and e[2]["notes"])]


@pytest.mark.skipif(NODE is None, reason="no Node.js available")
@pytest.mark.parametrize("scenario", ["switch", "params-changed"])
def test_stale_response_never_writes(tmp_path, scenario):
    data = _run(tmp_path, scenario)
    assert _writes(data) == []  # no removal, no re-trigger, no notes
    assert data["statuses"][-1].startswith("Selection or settings changed")


@pytest.mark.skipif(NODE is None, reason="no Node.js available")
def test_switch_away_and_back_still_targets_the_original_clip(tmp_path):
    data = _run(tmp_path, "switch-back")
    removals = [e for e in data["log"] if e[0] == "liveapi"]
    assert [e[2] for e in removals] == [7]


@pytest.mark.skipif(NODE is None, reason="no Node.js available")
def test_response_for_a_superseded_request_after_a_b_a_is_ignored(tmp_path):
    data = _run(tmp_path, "switch-apply-back")
    # request A (id 1) was replaced by the request made for B (id 2); B's own result no longer matches
    # the clip in the detail view (A again), so nothing is written to either clip
    assert _writes(data) == []


@pytest.mark.skipif(NODE is None, reason="no Node.js available")
def test_delayed_reapply_rechecks_the_clip(tmp_path):
    data = _run(tmp_path, "delayed-reapply")
    assert not [e for e in data["after"] if e[0] == "liveapi"]
    assert not [e for e in data["after"] if e[0] == "outlet" and e[1] == 2]
    assert data["statuses"][-1].startswith("Selection or settings changed")


@pytest.mark.skipif(NODE is None, reason="no Node.js available")
def test_failed_removal_does_not_apply_notes(tmp_path):
    data = _run(tmp_path, "remove-fails")
    assert not [e for e in data["log"] if e[0] == "outlet" and e[1] == 2]
    assert data["statuses"][-1].startswith("Error: could not clear")


@pytest.mark.skipif(NODE is None, reason="no Node.js available")
def test_failed_request_reports_error_and_writes_nothing(tmp_path):
    data = _run(tmp_path, "failure")
    assert _writes(data) == []
    assert data["statuses"][-1] == "Error: boom"


@pytest.mark.skipif(NODE is None, reason="no Node.js available")
def test_meter_is_sent_only_when_the_tool_context_has_a_valid_one(tmp_path):
    data = _run(tmp_path, "meter")
    plain, seven_eight, invalid = data["bodies"]
    assert "numerator" not in plain  # unknown: the server falls back to 4/4
    assert (seven_eight["numerator"], seven_eight["denominator"]) == (7, 8)
    assert "numerator" not in invalid
    assert data["requests"] == 3  # a changed meter is a changed request, never a cache hit


@pytest.mark.skipif(NODE is None, reason="no Node.js available")
def test_moved_selection_at_the_next_apply_never_reuses_the_cached_result(tmp_path):
    data = _run(tmp_path, "selection")
    assert data["after"] == data["before"] + 1  # a new request, not a cache hit
    assert data["last"] == {"notes": []}  # the old notes are not written for the new range


@pytest.mark.skipif(NODE is None, reason="no Node.js available")
def test_status_shows_the_pad_fallback_and_ignored_controls(tmp_path):
    status = " ".join(_run(tmp_path, "describe")["statuses"])
    assert "pads unknown (no Drum Rack on the track): General MIDI drum pitches" in status and "ignored: octave" in status


@pytest.mark.skipif(NODE is None, reason="no Node.js available")
def test_named_pads_of_the_tracks_drum_rack_are_sent_and_a_changed_kit_is_not_cached(tmp_path):
    out = _run(tmp_path, "pads")
    assert out["pads"] == [{"note": 48, "name": "Kick Heavy"}, {"note": 49, "name": "Snare Tight"}]  # out-of-range chain dropped
    assert out["after"] == out["before"] + 1  # the moved kick pad made a new request


@pytest.mark.skipif(NODE is None, reason="no Node.js available")
def test_pads_are_found_one_level_inside_an_instrument_rack(tmp_path):
    assert _run(tmp_path, "pads-nested")["pads"] == [{"note": 48, "name": "Kick Heavy"}, {"note": 49, "name": "Snare Tight"}]


@pytest.mark.skipif(NODE is None, reason="no Node.js available")
def test_older_live_reads_populated_drum_pads(tmp_path):
    assert _run(tmp_path, "pads-legacy")["pads"] == [{"note": 36, "name": "Kick"}, {"note": 41, "name": "Floor Tom"}]


@pytest.mark.skipif(NODE is None, reason="no Node.js available")
def test_no_drum_rack_sends_no_pads(tmp_path):
    assert _run(tmp_path, "no-rack")["pads"] is None
