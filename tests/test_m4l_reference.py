"""The Reference device's analysis (packages/m4l/src/reference-analysis.js) on a synthetic song, in Node."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from midibakery.mcp.server import read_references

ROOT = Path(__file__).resolve().parents[1]
MAX_NODE = Path("/Applications/Max.app/Contents/Resources/C74/packages/Node for Max/source/bin/osx/node/node")
NODE = str(MAX_NODE) if MAX_NODE.exists() else shutil.which("node")


needs_node = pytest.mark.skipif(NODE is None, reason="no Node.js available")


def _node(*args: str, genre: str = "auto") -> str:
    return subprocess.run([NODE, *args], capture_output=True, text=True, check=True, env={**os.environ, "GENRE": genre}).stdout


@needs_node
def test_sections_kick_and_key_of_a_synthetic_song():
    result = json.loads(_node(str(ROOT / "tests/reference_harness.js"), str(ROOT / "packages/m4l/src/reference-analysis.js")))
    assert result["tempo"] == 128 and result["grid"] == [0, 41344, 2646000]  # 4 beats at 22.05 kHz, 128 BPM
    assert result["bars"] == 64
    sections = [(s["name"], s["start_bar"], s["bars"]) for s in result["sections"]]
    assert sections == [("Intro", 1, 16), ("Break", 17, 16), ("Drop", 33, 32)], sections
    kick = result["lanes"]["kick"]
    assert min(kick[:16]) >= 0.5 and max(kick[16:32]) < 0.5 and min(kick[32:]) >= 0.5
    assert result["sections"][2]["elements"] == ["kick", "bass", "mids", "hats"]
    assert result["key"].startswith("A minor")


RUN = """
const { run } = require(process.argv[1]);
run(JSON.parse(process.argv[2])).then((r) => console.log(JSON.stringify(r)), (e) => { console.error(e); process.exit(1); });
"""


@needs_node
def test_run_places_sections_in_the_arrangement(tmp_path):
    # The 64 bar song at 128 BPM, its clip at arrangement bar 9 (beat 32) in a 120 BPM Set; the start
    # marker skips the file's first 8 bars (sections snap to 8 bar steps from the clip's first bar).
    wav = tmp_path / "song.wav"
    _node(str(ROOT / "tests/reference_harness.js"), str(ROOT / "packages/m4l/src/reference-analysis.js"), str(wav))
    clip = {"file": str(wav), "name": "Synth Song", "track": "Ref", "start": 32, "end": 32 + 56 * 4, "start_marker": 32,
            "warping": 1, "tempo": 120, "warp_markers": [{"beat_time": 0, "sample_time": 0}, {"beat_time": 256, "sample_time": 120}]}
    result = json.loads(_node("-e", RUN, str(ROOT / "packages/m4l/src/midibakery-reference.js"), json.dumps(clip)))
    assert result["tempo"] == 128 and result["set_tempo"] == 120 and result["first_bar"] == 9 and result["bars"] == 56
    # the file's break at its bar 17 is the clip's bar 9, arrangement bar 17
    sections = [(s["name"], s["start_bar"], s["beat"]) for s in result["sections"]]
    assert sections == [("Intro", 9, 32), ("Break", 17, 64), ("Drop", 33, 128)], sections


def test_read_references_lists_and_finds(tmp_path, monkeypatch):
    monkeypatch.setenv("MIDIBAKERY_HOME", str(tmp_path))
    (tmp_path / "references").mkdir()
    for i, name in enumerate(["Old Song", "New Song"]):
        ref = {"name": name, "file": f"/x/{name}.mp3", "analyzed": f"2026-10-0{i + 1}", "key": "A minor", "bars": 64,
               "sections": [{"name": "Intro", "start_bar": 1, "bars": 16, "kick": 1, "energy": -3}], "lanes": {"kick": [1] * 64}}
        (tmp_path / "references" / f"{i}.json").write_text(json.dumps(ref))
    (tmp_path / "references" / "broken.json").write_text("{")
    listed = read_references()["references"]
    assert [r["name"] for r in listed] == ["New Song", "Old Song"]
    assert "lanes" not in listed[0] and listed[0]["sections"] == [{"name": "Intro", "start_bar": 1, "bars": 16, "kick": 1, "elements": None}]
    assert read_references("old")["lanes"]["kick"][0] == 1
    with pytest.raises(Exception, match="No analyzed reference"):
        read_references("missing")


@needs_node
def test_unwarped_clip_gets_its_own_tempo_and_real_time_locators(tmp_path):
    # Unwarped, the 128 BPM song plays in real time from arrangement beat 32 of a 120 BPM Set:
    # its bar 17 starts 30 s in, at arrangement beat 32 + 30 s * 2 beats/s.
    wav = tmp_path / "song.wav"
    _node(str(ROOT / "tests/reference_harness.js"), str(ROOT / "packages/m4l/src/reference-analysis.js"), str(wav))
    seconds = 64 * 4 * 60 / 128
    clip = {"file": str(wav), "name": "Synth Song", "track": "Ref", "start": 32, "end": 32 + seconds * 2, "start_marker": 0,
            "warping": 0, "tempo": 120, "warp_markers": []}
    result = json.loads(_node("-e", RUN, str(ROOT / "packages/m4l/src/midibakery-reference.js"), json.dumps(clip)))
    assert result["tempo"] == 128 and not result["warped"] and result["bar_grid"] == "song" and result["bars"] in (63, 64)
    sections = [(s["name"], s["start_bar"], round(s["beat"], 1)) for s in result["sections"]]
    assert sections == [("Intro", 1, 32.0), ("Break", 17, 92.0), ("Drop", 33, 152.0)], sections
    # what the device warps the clip with: the detected tempo, bar 1 at the file's start
    assert result["warp"]["bpm"] == 128 and result["warp"]["first"] < 0.05 and result["warp"]["offset"] == 0
    assert abs(result["warp"]["length"] - seconds) < 0.01


WARP_PLAN = """
const vm = require("vm"), fs = require("fs");
const ctx = { outlet() {}, post() {}, LiveAPI: function () {}, Task: function () {}, Dict: function () {} };
vm.runInNewContext(fs.readFileSync(process.argv[1], "utf8"), ctx);
const [warp, start] = JSON.parse(process.argv[2]);
const plan = ctx.warpPlan(warp, start);
// Live's markers once warped as planned: one at the file's start, the end marker, the hidden last one
const spb = 60 / warp.bpm;
const markers = [{ beat_time: plan.beatAt(0), sample_time: 0 }, plan.end, { beat_time: plan.end.beat_time + 4, sample_time: plan.end.sample_time + 4 * spb }];
const off = [{ beat_time: plan.beatAt(0), sample_time: 0 }, { beat_time: plan.end.beat_time, sample_time: plan.end.sample_time + 0.05 }];
console.log(JSON.stringify({ down: plan.down, start: plan.start, end: plan.end, ok: ctx.warpedOk(markers, plan), off: ctx.warpedOk(off, plan),
  bar17: ctx.secondsAt(markers, plan.down + 64) }));
"""


@needs_node
def test_auto_warp_puts_bar_1_on_a_bar_line():
    script = str(ROOT / "packages/m4l/src/reference.js")
    # The Signal: 124 BPM from its first sample, the clip at the Arrangement's start
    plan = json.loads(_node("-e", WARP_PLAN, script, json.dumps([{"bpm": 124, "first": 0.006, "length": 305.85, "offset": 0}, 0])))
    assert plan["down"] == 0 and plan["start"] == 0 and plan["ok"] and not plan["off"]
    assert plan["end"]["beat_time"] == 628 and abs(plan["bar17"] - (0.006 + 64 * 60 / 124)) < 1e-6
    # 3 s of pad before the first kick, the clip at beat 6: bar 1 lands on clip beat 8, the start marker
    # keeps the pad and puts the downbeat on arrangement beat 6 + 8 - 2 = 12
    plan = json.loads(_node("-e", WARP_PLAN, script, json.dumps([{"bpm": 124, "first": 3, "length": 300, "offset": 0}, 6])))
    assert plan["down"] == 8 and plan["start"] == 2 and plan["ok"]


@needs_node
def test_genre_names_the_sections():
    harness = (str(ROOT / "tests/reference_harness.js"), str(ROOT / "packages/m4l/src/reference-analysis.js"))
    peak = json.loads(_node(*harness, genre="peak_time_techno"))
    assert peak["genre"] == "peak_time_techno"
    assert [s["name"] for s in peak["sections"]] == ["Intro", "Breakdown", "Peak"]
    # Drum & Bass phrases are 16 bars: no section shorter than that
    dnb = json.loads(_node(*harness, genre="drum_and_bass"))
    assert all(s["bars"] >= 16 for s in dnb["sections"]) and dnb["sections"][-1]["name"] == "Drop"
