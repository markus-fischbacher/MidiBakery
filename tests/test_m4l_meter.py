"""The Loudness Meter's measuring (packages/m4l/src/loudness.js) and its node.script, in Node.

The device's MSP part (two biquad~ per channel, average~ rms over 100 ms) is simulated sample by sample.
These checks exercise the algorithm, not Live's scheduler or full EBU meter conformance."""

import json
import os
import subprocess
from pathlib import Path

import pytest

from test_m4l_reference import NODE, needs_node

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "packages/m4l/src"

# biquad~ (y = a0 x + a1 x1 + a2 x2 - b1 y1 - b2 y2) and average~ rms over 100 ms, then Meter.block()
SIMULATION = """
const { kWeighting, Meter } = require(process.argv[1]);
const RATE = Number(process.argv[3] || 48000);
const { pre, rlb } = kWeighting(RATE);
function biquad(c) {
  let x1 = 0, x2 = 0, y1 = 0, y2 = 0;
  return (x) => { const y = c[0] * x + c[1] * x1 + c[2] * x2 - c[3] * y1 - c[4] * y2; x2 = x1; x1 = x; y2 = y1; y1 = y; return y; };
}
function channel() { const a = biquad(pre), b = biquad(rlb); return (x) => b(a(x)); }
// segments: [seconds, left amplitude, right amplitude] of a 997 Hz sine
function measure(segments) {
  const meter = new Meter(), left = channel(), right = channel();
  let n = 0;
  for (const [seconds, ampL, ampR] of segments) {
    for (let b = 0; b < seconds * 10; b++) {
      let sumL = 0, sumR = 0, peakL = 0, peakR = 0;
      for (let i = 0; i < RATE / 10; i++, n++) {
        const s = Math.sin((2 * Math.PI * 997 * n) / RATE);
        const l = left(ampL * s), r = right(ampR * s);
        sumL += l * l; sumR += r * r;
        peakL = Math.max(peakL, Math.abs(ampL * s)); peakR = Math.max(peakR, Math.abs(ampR * s));
      }
      meter.block(Math.sqrt(sumL / (RATE / 10)), Math.sqrt(sumR / (RATE / 10)), peakL, peakR);
    }
  }
  return meter.reading();
}
console.log(JSON.stringify({ coefficients: { pre, rlb }, cases: JSON.parse(process.argv[2]).map(measure) }));
"""


def _simulate(*cases: list, rate: int = 48000) -> dict:
    out = subprocess.run([NODE, "-e", SIMULATION, str(SRC / "loudness.js"), json.dumps(cases), str(rate)],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


@needs_node
def test_coefficients_at_48_khz_are_bs1770s():
    c = _simulate()["coefficients"]
    expected_pre = [1.53512485958697, -2.69169618940638, 1.19839281085285, -1.69065929318241, 0.73248077421585]
    expected_rlb = [1.0, -2.0, 1.0, -1.99004745483398, 0.99007225036621]
    assert all(abs(a - b) < 1e-9 for a, b in zip(c["pre"], expected_pre))
    assert all(abs(a - b) < 1e-9 for a, b in zip(c["rlb"], expected_rlb))


@needs_node
def test_a_full_scale_997_hz_sine_reads_as_bs1770_calibrates_it():
    left_only, both = _simulate([[5, 1.0, 0.0]], [[5, 1.0, 1.0]])["cases"]
    # BS.1770: a 0 dBFS 997 Hz sine in one front channel reads -3.01 LUFS
    assert abs(left_only["integrated_lufs"] + 3.0) <= 0.1, left_only
    assert abs(left_only["momentary_lufs"] + 3.0) <= 0.1 and abs(left_only["short_term_lufs"] + 3.0) <= 0.1
    assert abs(both["integrated_lufs"]) <= 0.1 and abs(both["peak_db"]) <= 0.1
    assert left_only["measured_seconds"] == 5


@needs_node
def test_gating_leaves_out_silence_and_quiet_passages():
    half = 10 ** (-20 / 20)
    silence, quiet = _simulate([[10, half, half], [10, 0, 0]], [[10, half, half], [10, half / 100, half / 100]])["cases"]
    # -20 dBFS in both channels: -20 LUFS; silence (absolute gate) and a part 40 dB lower (relative gate) do not count
    assert abs(silence["integrated_lufs"] + 20) <= 0.2, silence
    assert abs(quiet["integrated_lufs"] + 20) <= 0.2, quiet
    assert silence["momentary_lufs"] is None and silence["short_term_lufs"] is None  # nothing but silence left
    assert abs(quiet["short_term_lufs"] + 60) <= 0.2


@needs_node
@pytest.mark.parametrize("rate", [44100, 48000, 88200, 96000, 192000])
def test_sine_and_gating_across_sample_rates(rate):
    amplitude = 10 ** (-23 / 20)
    stereo, gated = _simulate([[5, amplitude, amplitude]],
                              [[5, amplitude, amplitude], [5, 0, 0]], rate=rate)["cases"]
    assert abs(stereo["integrated_lufs"] + 23) <= 0.1
    assert abs(gated["integrated_lufs"] + 23) <= 0.2
    assert stereo["measurement_id"] != gated["measurement_id"]


# midibakery-meter.js with a stand-in max-api: its handlers get called, its outlets recorded
SCRIPT = """
const Module = require("module");
const handlers = {}, sent = [];
const fakeMax = { addHandler: (name, fn) => { handlers[name] = fn; }, outlet: async (...a) => { sent.push(a); } };
const load = Module._load;
Module._load = function (request, ...rest) { return request === "max-api" ? fakeMax : load.call(this, request, ...rest); };
require(process.argv[1]);
const fs = require("fs"), path = require("path");
const home = process.env.MIDIBAKERY_HOME;
(async () => {
  await handlers.block(0.1, 0.1, 0.5, 0.5);                     // no sample rate yet: asks for it
  const asked = sent.some((m) => m[0] === "needrate");
  await handlers.samplerate(48000);
  for (let i = 0; i < 3 + 40; i++) await handlers.block(0.1, 0.1, 0.5, 0.5);  // 3 settle, then 4 s
  await new Promise((r) => setTimeout(r, 600));
  await handlers.block(0.1, 0.1, 0.5, 0.5);
  const first = JSON.parse(fs.readFileSync(path.join(home, "meter.json"), "utf8"));
  fs.writeFileSync(path.join(home, "meter-reset"), "");
  await new Promise((r) => setTimeout(r, 600));
  await handlers.block(0.1, 0.1, 0.25, 0.25);
  const after = JSON.parse(fs.readFileSync(path.join(home, "meter.json"), "utf8"));
  await handlers.reset();
  const manual = JSON.parse(fs.readFileSync(path.join(home, "meter.json"), "utf8"));
  await handlers.samplerate(44100);
  const changedRate = JSON.parse(fs.readFileSync(path.join(home, "meter.json"), "utf8"));
  console.log(JSON.stringify({ asked, sent, first, after, manual, changedRate,
    resetLeft: fs.existsSync(path.join(home, "meter-reset")) }));
})();
"""


@needs_node
def test_the_node_script_hands_out_coefficients_and_writes_the_reading(tmp_path):
    env = {**os.environ, "MIDIBAKERY_HOME": str(tmp_path)}
    out = subprocess.run([NODE, "-e", SCRIPT, str(SRC / "midibakery-meter.js")], capture_output=True, text=True,
                         check=True, env=env, timeout=30).stdout
    result = json.loads(out)
    assert result["asked"]
    sent = result["sent"]
    assert [m[:2] for m in sent if m[0] == "coeff"] == [["coeff", "pre"], ["coeff", "rlb"]] * 2
    assert ["window", 4800] in sent and ["status", "Measuring at 48 kHz. Reset, then play the song."] in sent
    assert ["i", "-17.7"] in sent and ["p", "-6.0"] in sent  # 0.1 RMS in both channels: -0.691 + 10 log10(0.02)
    first = result["first"]
    assert first["sample_rate"] == 48000 and first["measured_seconds"] == 4.1 and first["integrated_lufs"] == -17.7
    assert first["updated"] and first["since"]
    # measure_master's reset: the meter takes the request, deletes it and starts again
    after = result["after"]
    assert not result["resetLeft"] and after["measured_seconds"] == 0.1 and after["peak_db"] == -12.0
    assert first["measurement_id"] != after["measurement_id"]
    manual, changed_rate = result["manual"], result["changedRate"]
    assert manual["measured_seconds"] == changed_rate["measured_seconds"] == 0
    assert len({r["measurement_id"] for r in (first, after, manual, changed_rate)}) == 4
    assert changed_rate["sample_rate"] == 44100 and ["window", 4410] in sent


@needs_node
def test_immediate_reset_is_published_before_acknowledgement(tmp_path):
    script = SCRIPT.replace('await new Promise((r) => setTimeout(r, 600));', "")
    out = subprocess.run([NODE, "-e", script, str(SRC / "midibakery-meter.js")], capture_output=True, text=True,
                         check=True, env={**os.environ, "MIDIBAKERY_HOME": str(tmp_path)}, timeout=30).stdout
    result = json.loads(out)
    assert result["first"]["measurement_id"] != result["after"]["measurement_id"]
    assert not result["resetLeft"] and result["after"]["measured_seconds"] == 0.1


@needs_node
def test_write_failure_is_shown_instead_of_a_success_status(tmp_path):
    blocked = tmp_path / "not-a-directory"
    blocked.write_text("occupied")
    script = SCRIPT.split("(async () => {", 1)[0] + """
(async () => {
  await handlers.samplerate(48000);
  console.log(JSON.stringify(sent));
})();
"""
    out = subprocess.run([NODE, "-e", script, str(SRC / "midibakery-meter.js")], capture_output=True, text=True,
                         check=True, env={**os.environ, "MIDIBAKERY_HOME": str(blocked)}, timeout=30).stdout
    messages = json.loads(out)
    status = [message[1] for message in messages if message[0] == "status"]
    assert len(status) == 1 and status[0].startswith("Cannot write loudness reading:")
