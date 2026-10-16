/*
 * MidiBakery Reference Analyzer device, v8 side: finds the reference clip on this track through the Live
 * API, hands it to node.script for the analysis, passes the result to the view and sets
 * Arrangement locators at its sections (or removes the locators within the clip).
 *
 * inlet 0:  init (live.thisdevice), analyze, locators, unlocators, genre <menu index>, result <json>,
 *           status <text>
 * outlet 0: to node.script (analyze / lookup / log <json>)
 * outlet 1: to the view (show <json>, status <text>)
 */

autowatch = 0;
inlets = 1;
outlets = 2;

var ready = false;
var current = null; // the last result
// the Genre menu's items, as plan_song names the genres
var GENRES = ["auto", "house", "melodic_techno", "peak_time_techno", "drum_and_bass", "trap"];
var chosen = "auto";
var job = null; // locator job: {queue, home, phase, ticks, task}
var LOCATOR_TICK_MS = 60;
var LOCATOR_TIMEOUT_TICKS = 40; // ~2.4 s per locator, then it is skipped

function status(text) {
  outlet(1, "status", text);
}

function log(text) {
  outlet(0, "log", text);
}

/** LiveAPI get() returns a list; single values come first. */
function one(api, name) {
  var value = api.get(name);
  return value && value.length !== undefined ? value[0] : value;
}

function ids(list) {
  var out = [];
  for (var i = 0; list && i < list.length; i++) if (list[i] === "id") out.push(list[i + 1]);
  return out;
}

/** Live returns warp markers as a dict: a JSON string in a list, or an object. */
function warpMarkers(clip) {
  var raw = clip.get("warp_markers");
  try {
    var value = raw;
    if (raw && raw.length !== undefined && typeof raw !== "string") value = raw.join(" ");
    if (typeof value === "string") value = JSON.parse(value);
    var list = value && value.warp_markers ? value.warp_markers : value;
    var markers = [];
    for (var i = 0; list && i < list.length; i++) markers.push({ beat_time: Number(list[i].beat_time), sample_time: Number(list[i].sample_time) });
    return markers;
  } catch (e) {
    log("warp markers unreadable: " + String(raw).slice(0, 200));
    return [];
  }
}

/** The longest audio clip in this track's Arrangement. */
function referenceClip() {
  var track = new LiveAPI("this_device canonical_parent");
  if (!track || track.id == 0) return null;
  var best = null;
  var clips = ids(track.get("arrangement_clips"));
  for (var i = 0; i < clips.length; i++) {
    var clip = new LiveAPI("id " + clips[i]);
    if (!one(clip, "is_audio_clip")) continue;
    var start = one(clip, "start_time");
    var end = one(clip, "end_time");
    if (!best || end - start > best.end - best.start) best = { api: clip, start: start, end: end };
  }
  if (!best) return null;
  var clip = best.api;
  return {
    file: String(one(clip, "file_path")),
    name: String(one(clip, "name")),
    track: String(one(track, "name")),
    start: best.start,
    end: best.end,
    start_marker: one(clip, "start_marker"),
    end_marker: one(clip, "end_marker"),
    warping: one(clip, "warping") ? 1 : 0,
    warp_markers: warpMarkers(clip),
    tempo: one(new LiveAPI("live_set"), "tempo"),
    genre: chosen,
  };
}

function genre(index) {
  chosen = GENRES[index] || "auto";
}

function init() {
  ready = true;
  var clip = referenceClip();
  if (clip) outlet(0, "lookup", JSON.stringify(clip));
  else status("Drop the reference song on this track's Arrangement, then press Analyze");
}

function analyze() {
  if (!ready) return;
  var clip = referenceClip();
  if (!clip) {
    status("No audio clip in this track's Arrangement");
    return;
  }
  status("Analyzing " + clip.name + (clip.warping ? "..." : " (not warped: detecting its tempo)..."));
  outlet(0, "analyze", JSON.stringify(clip));
}

function result(json) {
  try {
    current = JSON.parse(json);
  } catch (e) {
    status("Unreadable result");
    return;
  }
  outlet(1, "show", json);
}

function locators() {
  if (!ready) return;
  if (!current || !current.sections || !current.sections.length) {
    status("Analyze first");
    return;
  }
  var queue = [];
  // Live puts a new locator on the Arrangement's grid anyway: aim for whole bars
  for (var i = 0; i < current.sections.length; i++) queue.push({ time: Math.round(current.sections[i].beat / 4) * 4, name: current.sections[i].name });
  start("set", queue, "Setting " + queue.length + " locators...");
}

/** Removes every locator within the reference clip's range of the Arrangement. */
function unlocators() {
  if (!ready) return;
  var clip = referenceClip();
  if (!clip) {
    status("No audio clip in this track's Arrangement");
    return;
  }
  var queue = [];
  var all = cues(new LiveAPI("live_set"));
  for (var i = 0; i < all.length; i++) if (all[i].time >= clip.start - 0.001 && all[i].time < clip.end) queue.push({ id: all[i].id, time: all[i].time, name: all[i].name });
  if (!queue.length) {
    status("No locators within the clip");
    return;
  }
  start("remove", queue, "Removing " + queue.length + " locators...");
}

function start(kind, queue, message) {
  if (job) return;
  var song = new LiveAPI("live_set");
  if (one(song, "is_playing")) {
    status("Stop the transport first");
    return;
  }
  job = { kind: kind, song: song, queue: queue, home: one(song, "current_song_time"), phase: "move", ticks: 0, done: 0 };
  job.task = new Task(kind === "set" ? step : removeStep, this);
  job.task.interval = LOCATOR_TICK_MS;
  job.task.repeat(-1);
  status(message);
}

function finish(message) {
  job.song.set("current_song_time", job.home);
  job.task.cancel();
  status(message);
  job = null;
}

function cues(song) {
  var list = ids(song.get("cue_points"));
  var out = [];
  for (var i = 0; i < list.length; i++) {
    var cue = new LiveAPI("id " + list[i]);
    out.push({ id: list[i], api: cue, time: one(cue, "time"), name: String(one(cue, "name")) });
  }
  return out;
}

/** The locator a section already has: one with its name within 4 bars (Live snapped it to its grid
 * on an earlier press), else any locator within a bar, which gets renamed: toggling there with
 * set_or_delete_cue could delete it. */
function cueNear(song, time, name) {
  var all = cues(song);
  for (var i = 0; i < all.length; i++) if (all[i].name === name && Math.abs(all[i].time - time) <= 16) return all[i];
  for (var j = 0; j < all.length; j++) if (Math.abs(all[j].time - time) < 4) return all[j];
  return null;
}

/** One locator at a time: Live sets a locator only at the play position, which moves a tick later,
 * and snaps it to the Arrangement's grid; the new locator is the one whose id was not there before. */
function step() {
  var song = job.song;
  var item = job.queue[0];
  if (!item) {
    finish(job.done + " locators set");
    return;
  }
  job.ticks++;
  if (job.ticks > LOCATOR_TIMEOUT_TICKS) {
    log("locator skipped at beat " + item.time + " in phase " + job.phase);
    next();
    return;
  }
  if (job.phase === "move") {
    var existing = cueNear(song, item.time, item.name);
    if (existing) {
      if (existing.name !== item.name) existing.api.set("name", item.name);
      job.done++;
      next();
      return;
    }
    job.before = cues(song);
    song.set("current_song_time", item.time);
    job.phase = "wait";
  } else if (job.phase === "wait") {
    if (Math.abs(one(song, "current_song_time") - item.time) < 0.001) {
      song.call("set_or_delete_cue");
      job.phase = "name";
    }
  } else if (job.phase === "name") {
    var now = cues(song);
    if (now.length < job.before.length) {
      // the grid snapped onto another locator and the toggle deleted it: put it back with its name
      var left = {};
      for (var k = 0; k < now.length; k++) left[now[k].id] = true;
      for (var d = 0; d < job.before.length; d++) if (!left[job.before[d].id]) item.name = job.before[d].name;
      log("locator near beat " + item.time + " was toggled off; restoring it as " + item.name);
      job.before = now;
      song.call("set_or_delete_cue");
      return; // the next tick names the restored locator
    }
    var known = {};
    for (var i = 0; i < job.before.length; i++) known[job.before[i].id] = true;
    for (var j = 0; j < now.length; j++) {
      if (known[now[j].id]) continue;
      now[j].api.set("name", item.name);
      if (Math.abs(now[j].time - item.time) > 0.01) log("locator " + item.name + " snapped from beat " + item.time + " to " + now[j].time);
      job.done++;
      next();
      return;
    }
  }
}

/** One locator at a time: move the play position onto it and toggle it off. Live snaps the play
 * position to its grid first; if that toggled a new locator on instead, toggle once more. */
function removeStep() {
  var song = job.song;
  var item = job.queue[0];
  if (!item) {
    finish(job.done + " locators removed");
    return;
  }
  job.ticks++;
  if (job.ticks > LOCATOR_TIMEOUT_TICKS) {
    log("locator " + item.name + " at beat " + item.time + " not removed (phase " + job.phase + ")");
    next();
    return;
  }
  if (job.phase === "move") {
    job.before = cues(song);
    song.set("current_song_time", item.time);
    job.phase = "wait";
  } else if (job.phase === "wait") {
    if (Math.abs(one(song, "current_song_time") - item.time) < 0.001) {
      song.call("set_or_delete_cue");
      job.phase = "check";
    }
  } else if (job.phase === "check") {
    var now = cues(song);
    var gone = true;
    for (var i = 0; i < now.length; i++) if (now[i].id === item.id) gone = false;
    if (now.length > job.before.length) {
      log("removing " + item.name + " at beat " + item.time + " added a locator on the grid; taking it back");
      song.call("set_or_delete_cue");
      next();
    } else if (now.length < job.before.length) {
      if (!gone) log("removing " + item.name + " at beat " + item.time + " removed another locator");
      else job.done++;
      next();
    }
  }
}

function next() {
  job.queue.shift();
  job.phase = "move";
  job.ticks = 0;
}

function anything() {
  // node.script's status lines
  if (messagename === "status") status(arrayfromargs(arguments).join(" "));
}
