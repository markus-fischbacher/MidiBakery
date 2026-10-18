/**
 * Node for Max side of the MidiBakery Loudness Meter device (on the Master, after the Limiter).
 *
 *   samplerate <hz>         from dspstate~: answers "coeff pre|rlb a0 a1 a2 b1 b2" for the biquad~ filters,
 *                           "window <samples>" (100 ms) for average~ and "status Measuring at ..."
 *   block <rmsL> <rmsR> <peakL> <peakR>   every 100 ms (loudness.js); before the sample rate is known it
 *                           answers "needrate" (the device bangs dspstate~) and measures nothing
 *   reset                   the Reset button: integrated loudness and peak start again
 *   about <version>         the About button -> "status <text>"
 *
 * Twice a second it writes the reading to <MidiBakery folder>/meter.json, where MidiBakery's
 * measure_master tool reads it, and shows it ("m|s|i|p <value>"). measure_master asks for a reset by
 * writing meter-reset (any content); the meter deletes it and starts again.
 */

"use strict";

const fs = require("fs");
const os = require("os");
const path = require("path");
const { kWeighting, Meter, display } = require("./loudness.js");
const { about } = require("./midibakery-about.js");

function configDir() {
  if (process.env.MIDIBAKERY_HOME) return process.env.MIDIBAKERY_HOME;
  if (process.platform === "darwin") return path.join(os.homedir(), "Library", "Application Support", "MidiBakery");
  if (process.platform === "win32") return path.join(process.env.APPDATA || os.homedir(), "MidiBakery");
  return path.join(os.homedir(), ".config", "midibakery");
}

const READING = path.join(configDir(), "meter.json");
const RESET = path.join(configDir(), "meter-reset");
const WRITE_EVERY_MS = 500;

const SETTLE_BLOCKS = 3; // the filters' first 300 ms after new coefficients do not count

const meter = new Meter();
let sampleRate = null;
let settle = 0;
let written = 0;
let asked = 0;

async function show(Max, reading) {
  for (const [name, value] of display(reading)) await Max.outlet(name, value);
}

function write() {
  try {
    fs.mkdirSync(configDir(), { recursive: true });
    const reading = { ...meter.reading(), sample_rate: sampleRate, updated: new Date().toISOString() };
    fs.writeFileSync(`${READING}.tmp`, JSON.stringify(reading, null, 1));
    fs.renameSync(`${READING}.tmp`, READING); // a reader never sees half a file
    return reading;
  } catch (_) {
    return null; // the meter keeps measuring when the folder is not writable
  }
}

async function onBlock(Max, rmsLeft, rmsRight, peakLeft, peakRight) {
  const now = Date.now();
  if (!sampleRate) {
    if (now - asked > 1000) {
      asked = now;
      await Max.outlet("needrate");
    }
    return;
  }
  if (settle > 0) {
    settle -= 1;
    return;
  }
  if (fs.existsSync(RESET)) {
    try {
      fs.unlinkSync(RESET);
    } catch (_) {
      // another reset request in the same moment: one reset is enough
    }
    meter.reset();
  }
  meter.block(+rmsLeft || 0, +rmsRight || 0, +peakLeft || 0, +peakRight || 0);
  if (now - written < WRITE_EVERY_MS) return;
  written = now;
  const reading = write();
  if (reading) await show(Max, reading);
}

async function onSampleRate(Max, rate) {
  if (!(+rate > 0)) return;
  if (+rate !== sampleRate) meter.reset(); // a reading spans one sample rate
  sampleRate = +rate;
  settle = SETTLE_BLOCKS;
  const { pre, rlb } = kWeighting(sampleRate);
  await Max.outlet("coeff", "pre", ...pre);
  await Max.outlet("coeff", "rlb", ...rlb);
  await Max.outlet("window", Math.round(sampleRate / 10));
  await Max.outlet("status", `Measuring at ${sampleRate / 1000} kHz. Reset, then play the song.`);
}

let Max = null;
try {
  Max = require("max-api");
} catch (_) {
  Max = null;
}
if (Max) {
  Max.addHandler("samplerate", (rate) => onSampleRate(Max, rate));
  Max.addHandler("block", (...values) => onBlock(Max, ...values));
  Max.addHandler("reset", async () => {
    meter.reset();
    const reading = write();
    if (reading) await show(Max, reading);
  });
  Max.addHandler("about", async (version) => Max.outlet("status", await about(version)));
}

module.exports = { configDir };
