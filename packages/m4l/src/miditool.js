/**
 * MidiBakery MIDI Tool (v8.codebox) - shared by the Generator and the Transformation.
 * The build script prepends `var MODE = "generate" | "transform";`.
 *
 * Live's MIDI Tools need a synchronous answer for every apply cycle, but the
 * notes come from the MidiBakery API over HTTP. So every apply is answered at
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
  kind: 0, drums: 0, bass: 5, chords: 0, density: 50, swing: 0, chance: 100, replace: 1,
  operation: 0, amount: 50, semitones: 12, rate: 1, seed: 1
};
var lastInput = null;
// cycle: Live's per-apply-cycle seed when the cached notes were last applied.
// clip: id of the detail clip a request/result was made for (checked again before every write).
var cache = { key: null, clip: 0, notes: null, info: "", cycle: null };
var pending = { id: 0, key: null, clip: 0 };
var requestCounter = 0;
var reapplied = false;
var REQUEST_TIMEOUT_MS = 20000;
var requestedAt = 0;
var instance = Math.floor(Math.random() * 1e9);
// Request and result dicts must outlive this call: node.script uses them asynchronously.
var requestDict = null;
var resultDict = null;
// "Working..." only for slow requests; fast ones (a few ms) would just flicker.
var showWorking = new Task(function () {
  if (pending.id) status("Working...");
});
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

// Id of the clip in the detail view (the clip the tool writes to); 0 when there is none.
// The id is Live's LiveAPI object id; its stability across selection changes is unverified in real Live.
function detailClipId() {
  try {
    var clip = new LiveAPI("live_set view detail_clip");
    return clip ? Number(clip.id) || 0 : 0;
  } catch (e) {
    return 0;
  }
}

// A delayed result may only be used while the clip, selection and settings it was made for are still current.
function isFresh(clip, key) {
  return Boolean(lastInput) && clip !== 0 && detailClipId() === clip && JSON.stringify(buildBody(lastInput)) === key;
}

function replacing() {
  return MODE === "generate" && params.replace;
}

function msg_dictionary(d) {
  if (inlet !== 0) return;
  lastInput = d;
  var body = buildBody(d);
  var key = JSON.stringify(body);
  var cycle = d.seed;
  var clipId = detailClipId();
  // With Replace, a new apply cycle (new Live seed) must clear the range again before
  // the cached notes go back in; within one cycle Live itself replaces the previous output.
  var sameCycle = reapplied || !replacing() || cache.cycle === cycle;
  if (cache.key === key && cache.clip === clipId && sameCycle) {
    dbg("apply cached", cache.notes.length, "notes");
    waitForApply.cancel();
    outlet_dictionary(0, { notes: cache.notes });
    status(cache.info);
    cache.cycle = cycle;
    reapplied = false;
    return;
  }
  // Synchronous no-op answer keeps Live in sync while the API computes.
  outlet_dictionary(0, { notes: MODE === "generate" ? [] : toLive(d.notes || []) });
  if (cache.key === key && cache.clip === clipId) {
    // Same settings, new cycle: no new request, just clear and re-apply. Deferred: re-triggering
    // the tool from inside Live's apply call nests cycles ("Did not receive a note dictionary in time").
    deferredApply.schedule(5);
    return;
  }
  if (pending.key === key && pending.clip === clipId && Date.now() - requestedAt < REQUEST_TIMEOUT_MS) return; // already asked
  requestCounter += 1;
  pending = { id: requestCounter, key: key, clip: clipId };
  requestedAt = Date.now();
  reapplied = false;
  showWorking.schedule(300);
  var name = "midibakery_" + instance + "_req" + requestCounter;
  requestDict = new Dict(name);
  requestDict.parse(key);
  resultDict = new Dict(name + "_res");
  dbg("request", requestCounter, (d.notes || []).length, "notes in");
  outlet(1, "request", requestCounter, MODE, name);
}

function response(id, dictName) {
  if (id !== pending.id) {
    dbg("stale response", id);
    return; // superseded by a newer request
  }
  var token = pending;
  pending = { id: 0, key: null, clip: 0 };
  if (!isFresh(token.clip, token.key)) {
    dbg("discarded response", id, "clip or settings changed");
    status("Selection or settings changed - result discarded");
    return;
  }
  var result = JSON.parse(new Dict(dictName).stringify());
  cache = { key: token.key, clip: token.clip, notes: toLive(result.notes || []), info: describe(result), cycle: null };
  dbg("response", id, cache.notes.length, "notes out");
  if (!reapplied) applyResult();
}

var deferredApply = new Task(function () { applyResult(); });

// Clear the time selection (Replace), then re-trigger the tool so Live applies the cache.
function applyResult() {
  if (cache.key === null || !isFresh(cache.clip, cache.key)) {
    dbg("apply skipped: clip or settings changed");
    status("Selection or settings changed - nothing applied");
    return;
  }
  if (replacing() && lastInput && !clearRange(cache.clip, buildContext(lastInput))) {
    status("Error: could not clear the selection - nothing applied");
    return;
  }
  reapplied = true;
  outlet(2, "bang");
  waitForApply.schedule(1500);
}

// Removes the notes in the range from the clip the result was made for; false if it did not happen.
function clearRange(clipId, context) {
  try {
    var clip = new LiveAPI("live_set view detail_clip");
    if (!clip || clipId === 0 || Number(clip.id) !== clipId) {
      dbg("replace: detail clip changed");
      return false;
    }
    clip.call("remove_notes_extended", 0, 128, context.start, context.length);
    dbg("replace: cleared", context.start, context.length);
    return true;
  } catch (e) {
    dbg("replace failed", String(e));
    return false;
  }
}

function failed(id, message) {
  dbg("failed", id, message);
  if (id !== pending.id) return;
  pending = { id: 0, key: null, clip: 0 };
  status("Error: " + message);
}

var INTEGER_PARAMS = { seed: 1, semitones: 1, kind: 1, operation: 1, rate: 1, drums: 1, bass: 1, chords: 1, replace: 1 };

function param(name, value) {
  if (!(name in params)) return;
  params[name] = INTEGER_PARAMS[name] ? Math.round(Number(value)) : Number(value);
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
  // Note probability only makes musical sense for drums (ghost notes, hats).
  outlet(4, "script", "sendbox", "chance_dial", "hidden", kind === "drums" ? 0 : 1);
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
  // Meter: read from the tool context when Live provides it; otherwise omitted, so the server
  // assumes 4/4. UNVERIFIED which of these fields real Live fills in. Drum Rack pad context is not
  // sent (no verified interface), so drums use General MIDI pitches.
  var numerator = Number(clip.signature_numerator);
  var denominator = Number(clip.signature_denominator);
  if (numerator >= 1 && numerator <= 99 && [1, 2, 4, 8, 16].indexOf(denominator) >= 0) {
    context.numerator = numerator;
    context.denominator = denominator;
  }
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
    if (kind === "drums") {
      p.style = DRUM_STYLES[params.drums];
      p.chance = params.chance / 100;
    }
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

// Shown when a transformation changed nothing, so it does not look like a failure.
var NO_CHANGE_HINTS = {
  arpeggiate: "No chords to arpeggiate (needs notes starting together). Cmd+Z restores earlier chords.",
  quantize: "Already on the grid - nothing to quantize.",
  invert: "Nothing to invert (a single pitch mirrors onto itself).",
  transpose: "Nothing transposed (0 semitones?).",
  humanize: "Nothing changed - raise Amount.",
  variation: "Nothing changed - raise Amount or try another seed."
};

function describe(result) {
  var d = result.diff;
  if (MODE === "transform" && d && !d.added && !d.modified && !d.removed) {
    return NO_CHANGE_HINTS[OPERATIONS[params.operation]] || "Nothing changed.";
  }
  var parts = [];
  if (result.chords) parts.push(Array.isArray(result.chords) ? result.chords.join(" - ") : String(result.chords));
  if (result.diff) parts.push("+" + result.diff.added + " ~" + result.diff.modified + " -" + result.diff.removed);
  if (result.notes) parts.push(result.notes.length + " notes");
  parts.push("seed " + result.seed);
  return parts.join("  ");
}
