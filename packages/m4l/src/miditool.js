/**
 * MidiShower MIDI Tool (v8.codebox) - shared by the Generator and the Transformation.
 * The build script prepends `var MODE = "generate" | "transform";`.
 *
 * Live's MIDI Tools need a synchronous answer for every apply cycle, but the
 * notes come from the MidiShower API over HTTP. So every apply is answered at
 * once: from the cache when the request was computed before, otherwise with
 * a no-op (no new notes / the unchanged notes) while the request goes out via
 * node.script. When the response arrives it is cached and the tool re-triggers
 * itself once, which applies the result inside the same apply cycle.
 *
 * Inlet 0: joined notes + context dict from live.miditool.in (via dict.join)
 * Inlet 1: `param <name> <value>` from the UI; response / failed / status from node.script
 *
 * Requests and responses travel as named Max dictionaries, not as message
 * symbols: a clip's notes make the payload too large for a single symbol.
 * Outlets: 0 live.miditool.out, 1 node.script, 2 bang -> live.miditool.in,
 *          3 status text, 4 UI feedback (seed, style menu visibility)
 */

inlets = 2;
outlets = 5;

var DRUM_STYLES = ["house", "techno", "hiphop", "trap", "rock", "breakbeat"];
var BASS_STYLES = ["sustained", "pulse", "offbeat", "octave", "walking", "syncopated"];
var CHORD_RHYTHMS = ["sustain", "pulse", "offbeat", "stabs"];
var KINDS = ["drums", "bass", "chords", "melody"];
var OPERATIONS = ["humanize", "quantize", "invert", "arpeggiate", "variation", "transpose"];
var ARP_RATES = [0.125, 0.25, 0.5, 1.0];

var params = {
  kind: 0, drums: 0, bass: 5, chords: 0, density: 50, swing: 0,
  operation: 0, amount: 50, semitones: 12, rate: 1, seed: 1
};
var lastInput = null;
var cache = { key: null, notes: null, info: "" };
var pending = { id: 0, key: null };
var requestCounter = 0;
var reapplied = false;
var REQUEST_TIMEOUT_MS = 20000;
var requestedAt = 0;
var instance = Math.floor(Math.random() * 1e9);
// The request dict must outlive this call: node.script reads it asynchronously.
var requestDict = null;
// If Live ignores the self-triggered re-apply (e.g. Auto off), ask for a second click.
var waitForApply = new Task(function () {
  if (cache.key !== null && reapplied) status("Ready - click " + (MODE === "generate" ? "Generate" : "Transform") + " again");
});

function dbg() {
  outlet(1, ["log", MODE].concat(Array.prototype.slice.call(arguments)));
}

function status(text) {
  outlet(3, "set", text);
}

function msg_dictionary(d) {
  if (inlet !== 0) return;
  lastInput = d;
  var body = buildBody(d);
  var key = JSON.stringify(body);
  if (cache.key === key) {
    dbg("apply cached", cache.notes.length, "notes");
    waitForApply.cancel();
    outlet_dictionary(0, { notes: cache.notes });
    status(cache.info);
    reapplied = false;
    return;
  }
  // Synchronous no-op answer keeps Live in sync while the API computes.
  outlet_dictionary(0, { notes: MODE === "generate" ? [] : toLive(d.notes || []) });
  if (pending.key === key && Date.now() - requestedAt < REQUEST_TIMEOUT_MS) return; // already asked
  requestCounter += 1;
  pending = { id: requestCounter, key: key };
  requestedAt = Date.now();
  reapplied = false;
  status("Working...");
  var name = "midishower_" + instance + "_req" + requestCounter;
  requestDict = new Dict(name);
  requestDict.parse(key);
  dbg("request", requestCounter, (d.notes || []).length, "notes in");
  outlet(1, "request", requestCounter, MODE, name);
}

function response(id, dictName) {
  if (id !== pending.id) {
    dbg("stale response", id);
    return; // superseded by a newer request
  }
  var result = JSON.parse(new Dict(dictName).stringify());
  cache = { key: pending.key, notes: toLive(result.notes || []), info: describe(result) };
  pending = { id: 0, key: null };
  dbg("response", id, cache.notes.length, "notes out");
  if (!reapplied) {
    reapplied = true;
    outlet(2, "bang");
    waitForApply.schedule(1500);
  }
}

function failed(id, message) {
  dbg("failed", id, message);
  if (id !== pending.id) return;
  pending = { id: 0, key: null };
  status("Error: " + message);
}

function param(name, value) {
  if (!(name in params)) return;
  params[name] = value;
  if (name === "kind") showStyleMenu();
  if (lastInput) outlet(2, "bang");
}

function dice() {
  // A new seed; the seed number box reports back through `param seed`.
  outlet(4, "seed", 1 + Math.floor(Math.random() * 9999));
}

function loadbang() {
  showStyleMenu();
}

function showStyleMenu() {
  // Scripting messages for thispatcher; the boxes have scripting names style_<kind>.
  if (MODE !== "generate") return;
  var kind = KINDS[params.kind];
  ["drums", "bass", "chords"].forEach(function (name) {
    outlet(4, "script", "sendbox", "style_" + name, "hidden", kind === name ? 0 : 1);
  });
}

function buildContext(d) {
  var clip = d.clip || {};
  var start = Number(clip.time_selection_start) || 0;
  var end = Number(clip.time_selection_end) || 0;
  var context = {
    start: start,
    length: end > start ? end - start : 16,
    seed: params.seed
  };
  var scale = d.scale || {};
  var intervals = scale.scale_intervals || [];
  // Live reports "Chromatic" when the clip has no scale; generators need a real one.
  if (scale.scale_mode && intervals.length && intervals.length < 12) {
    context.scale = { root: Number(scale.root_note) % 12, intervals: intervals, name: String(scale.scale_name || "") };
  }
  return context;
}

function buildBody(d) {
  var context = buildContext(d);
  var amount = params.amount / 100;
  if (MODE === "generate") {
    var kind = KINDS[params.kind];
    var p = { swing: params.swing / 100 };
    if (kind !== "chords") p.density = params.density / 100;
    if (kind === "drums") p.style = DRUM_STYLES[params.drums];
    if (kind === "bass") p.style = BASS_STYLES[params.bass];
    if (kind === "chords") p.rhythm = CHORD_RHYTHMS[params.chords];
    return { context: context, kind: kind, params: p };
  }
  var operation = OPERATIONS[params.operation];
  var t = {};
  if (operation === "humanize" || operation === "variation") t.amount = amount;
  if (operation === "quantize") {
    t.strength = amount;
    var grid = d.grid || {};
    if (grid.enabled && Number(grid.interval) > 0) t.grid = Math.min(4, Number(grid.interval));
  }
  if (operation === "transpose") t.semitones = params.semitones;
  if (operation === "arpeggiate") t.rate = ARP_RATES[params.rate];
  return { context: context, operation: operation, params: t, notes: fromLive(d.notes || []) };
}

var NOTE_KEYS = ["note_id", "pitch", "start_time", "duration", "velocity", "mute", "probability", "velocity_deviation", "release_velocity"];

function fromLive(notes) {
  return notes.map(function (n) {
    var out = {};
    NOTE_KEYS.forEach(function (k) { if (n[k] !== undefined) out[k] = k === "mute" ? Boolean(n[k]) : n[k]; });
    return out;
  });
}

function toLive(notes) {
  return notes.map(function (n) {
    var out = {};
    NOTE_KEYS.forEach(function (k) {
      if (n[k] === undefined || n[k] === null) return;
      out[k] = k === "mute" ? (n[k] ? 1 : 0) : n[k];
    });
    return out;
  });
}

function describe(result) {
  var parts = [];
  if (result.chords) parts.push(Array.isArray(result.chords) ? result.chords.join(" - ") : String(result.chords));
  if (result.diff) parts.push("+" + result.diff.added + " ~" + result.diff.modified + " -" + result.diff.removed);
  if (result.notes) parts.push(result.notes.length + " notes");
  parts.push("seed " + result.seed);
  return parts.join("  ");
}
