/**
 * Loudness after ITU-R BS.1770-4 / EBU R 128 for the MidiBakery Loudness Meter.
 *
 * The device's MSP part K-weights each channel (two biquad~ per channel with kWeighting()'s
 * coefficients), measures its mean square over 100 ms (average~ rms, read every 100 ms) and its
 * sample peak (peakamp~). Meter takes those 100 ms blocks:
 *   momentary   400 ms (the last 4 blocks)
 *   short-term  3 s (the last 30)
 *   integrated  every 400 ms block (75 % overlap) since the start or a reset, gated at -70 LUFS
 *               absolute and 10 LU below the mean surviving the absolute gate
 * Scheduler-read blocks approximate the algorithm; this is not a conformance-validated meter.
 * Peaks are sample peaks, not true peaks: no fixed bound on intersample overshoot is assumed.
 */

"use strict";

const { randomUUID } = require("crypto");
const ABSOLUTE_GATE = -70;
const RELATIVE_GATE = -10;
const SHORT_BLOCKS = 30;
const MOMENTARY_BLOCKS = 4;

/** Biquad coefficients of BS.1770's pre-filter (high shelf) and RLB high pass for any sample rate,
 * as libebur128 derives them; in Max biquad~'s order: a0 a1 a2 (feed forward), b1 b2 (feedback). */
function kWeighting(rate) {
  let f0 = 1681.974450955533;
  const G = 3.999843853973347;
  let Q = 0.7071752369554196;
  let K = Math.tan((Math.PI * f0) / rate);
  const Vh = Math.pow(10, G / 20);
  const Vb = Math.pow(Vh, 0.4996667741545416);
  let a0 = 1 + K / Q + K * K;
  const pre = [(Vh + (Vb * K) / Q + K * K) / a0, (2 * (K * K - Vh)) / a0, (Vh - (Vb * K) / Q + K * K) / a0,
    (2 * (K * K - 1)) / a0, (1 - K / Q + K * K) / a0];
  f0 = 38.13547087602444;
  Q = 0.5003270373238773;
  K = Math.tan((Math.PI * f0) / rate);
  a0 = 1 + K / Q + K * K;
  const rlb = [1, -2, 1, (2 * (K * K - 1)) / a0, (1 - K / Q + K * K) / a0];
  return { pre, rlb };
}

/** LUFS of a summed mean square (channel weights 1 for left and right). */
function lufs(meanSquare) {
  return meanSquare > 0 ? -0.691 + 10 * Math.log10(meanSquare) : -Infinity;
}

function db(amplitude) {
  return amplitude > 0 ? 20 * Math.log10(amplitude) : -Infinity;
}

function mean(values) {
  return values.length ? values.reduce((a, b) => a + b, 0) / values.length : 0;
}

class Meter {
  constructor() {
    this.reset();
  }

  reset() {
    this.blocks = []; // summed mean squares of the last SHORT_BLOCKS 100 ms blocks
    this.gating = []; // summed mean squares of every 400 ms block since the reset
    this.peaks = []; // the last SHORT_BLOCKS blocks' peaks
    this.peak = 0; // the highest sample peak since the reset
    this.since = new Date().toISOString();
    this.measurementId = randomUUID();
    this.count = 0;
  }

  /** One 100 ms block: the RMS of each K-weighted channel and each channel's sample peak. */
  block(rmsLeft, rmsRight, peakLeft, peakRight) {
    const z = rmsLeft * rmsLeft + rmsRight * rmsRight;
    this.blocks.push(z);
    if (this.blocks.length > SHORT_BLOCKS) this.blocks.shift();
    const peak = Math.max(Math.abs(peakLeft), Math.abs(peakRight));
    this.peaks.push(peak);
    if (this.peaks.length > SHORT_BLOCKS) this.peaks.shift();
    this.peak = Math.max(this.peak, peak);
    this.count += 1;
    if (this.blocks.length >= MOMENTARY_BLOCKS) this.gating.push(mean(this.blocks.slice(-MOMENTARY_BLOCKS)));
  }

  integrated() {
    const loud = this.gating.filter((z) => lufs(z) > ABSOLUTE_GATE);
    if (!loud.length) return -Infinity;
    const threshold = lufs(mean(loud)) + RELATIVE_GATE;
    const gated = loud.filter((z) => lufs(z) > threshold);
    return lufs(mean(gated));
  }

  /** Rounded readings; null where there is nothing to measure yet, or only silence (below the -70 LUFS gate:
   * the filters' tails would read as -130 LUFS). */
  reading() {
    const round = (x) => (Number.isFinite(x) ? Math.round(x * 10) / 10 : null);
    const audible = (x) => (x > ABSOLUTE_GATE ? round(x) : null);
    return {
      momentary_lufs: this.blocks.length >= MOMENTARY_BLOCKS ? audible(lufs(mean(this.blocks.slice(-MOMENTARY_BLOCKS)))) : null,
      short_term_lufs: this.blocks.length >= SHORT_BLOCKS ? audible(lufs(mean(this.blocks))) : null,
      integrated_lufs: round(this.integrated()),
      peak_db: round(db(this.peak)),
      short_term_peak_db: round(db(Math.max(0, ...this.peaks))),
      measured_seconds: Math.round(this.count) / 10,
      since: this.since,
      measurement_id: this.measurementId,
    };
  }
}

/** What the device shows: [name, value] for M, S, I (LUFS) and the peak (dB), "--" while unmeasured. */
function display(r) {
  const v = (x) => (x == null ? "--" : x.toFixed(1));
  return [["m", v(r.momentary_lufs)], ["s", v(r.short_term_lufs)], ["i", v(r.integrated_lufs)], ["p", v(r.peak_db)]];
}

module.exports = { kWeighting, lufs, db, Meter, display };
