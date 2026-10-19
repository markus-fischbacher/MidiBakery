// Runs the MIDI Tool v8 code with stubbed Max globals; prints the event log as JSON.
// Usage: node miditool_harness.js <code.js> <scenario>
"use strict";
const fs = require("fs");
const vm = require("vm");

const log = [];
let inApply = false; // true while msg_dictionary (Live's synchronous apply call) runs
const dicts = {};
function Dict(name) {
  this.parse = (text) => { dicts[name] = JSON.parse(text); };
  this.stringify = () => JSON.stringify(dicts[name]);
}
// Tasks run after the current call returns, like Max's scheduler (see flush()).
const queue = [];
function Task(fn) {
  this.schedule = () => { log.push(["task", "schedule"]); queue.push(fn); };
  this.cancel = () => {};
}
let detailId = 7; // the clip in Live's detail view; scenarios change it to simulate a selection switch
let removeFails = false;
function LiveAPI(path) {
  this.id = detailId;
  this.call = (...args) => {
    if (removeFails) throw new Error("remove failed");
    log.push(["liveapi", path, this.id, ...args]);
  };
}
const sandbox = {
  LiveAPI, Dict, Task, Date, Array, String,
  inlet: 0,
  outlet: (...args) => {
    if (inApply && args[0] === 2) log.push(["nested-retrigger"]); // re-triggering inside Live's apply call
    log.push(["outlet", ...args]);
  },
  outlet_dictionary: (n, d) => log.push(["dict", n, JSON.parse(JSON.stringify(d))]),
  post: () => {},
  Math, JSON, Number, String, Boolean,
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), sandbox);
let holdQueue = false; // keep scheduled tasks pending until release() (a delayed deferred apply)
const flush = () => { while (!holdQueue && queue.length) queue.shift()(); };
const release = () => { holdQueue = false; flush(); };
const call = (inletIndex, fn, ...args) => {
  sandbox.inlet = inletIndex;
  inApply = fn === "msg_dictionary";
  const result = vm.runInContext(fn, sandbox)(...args);
  inApply = false;
  flush();
  return result;
};

const input = {
  notes: [{ note_id: 7, pitch: 60, start_time: 0, duration: 1, velocity: 100, mute: 0, probability: 1, velocity_deviation: 0, release_velocity: 64 }],
  clip: { time_selection_start: 4, time_selection_end: 20 },
  scale: { scale_mode: 1, root_note: 9, scale_intervals: [0, 2, 3, 5, 7, 8, 10], scale_name: "Minor" },
  grid: { interval: 0.25, enabled: 1 },
  seed: 123,
};
const requestOf = () => log.filter((e) => e[0] === "outlet" && e[1] === 1 && e[2] === "request").pop();

const scenario = process.argv[3] || "basic";
dicts.res = { seed: 1, notes: [{ pitch: 69, start_time: 4, duration: 1, velocity: 90, mute: false }], chords: "Am" };
const result = "res";

const applied = () => log.filter((e) => e[0] === "liveapi" || (e[0] === "outlet" && e[1] === 2) || (e[0] === "dict" && e[2].notes.length));
const statuses = () => log.filter((e) => e[0] === "outlet" && e[1] === 3).map((e) => e[3]);

if (scenario === "switch") {
  // request on clip A, user selects clip B, A's response arrives late
  call(0, "msg_dictionary", input);
  const req = requestOf();
  detailId = 8;
  call(1, "response", req[3], result);
  console.log(JSON.stringify({ log, applied: applied(), statuses: statuses() }));
} else if (scenario === "switch-back") {
  // A -> B -> A without an apply on B: the response is still valid for A
  call(0, "msg_dictionary", input);
  const req = requestOf();
  detailId = 8;
  detailId = 7;
  call(1, "response", req[3], result);
  console.log(JSON.stringify({ log, applied: applied(), statuses: statuses() }));
} else if (scenario === "switch-apply-back") {
  // A requests, B applies its own request, back on A: A's older response is superseded
  call(0, "msg_dictionary", input);
  const first = requestOf();
  detailId = 8;
  call(0, "msg_dictionary", input);
  const second = requestOf();
  detailId = 7;
  call(1, "response", first[3], result);
  call(1, "response", second[3], result);
  console.log(JSON.stringify({ log, applied: applied(), statuses: statuses(), ids: [first[3], second[3]] }));
} else if (scenario === "params-changed") {
  call(0, "msg_dictionary", input);
  const req = requestOf();
  sandbox.params_density = 1;
  vm.runInContext("params.density = 90", sandbox);
  call(1, "response", req[3], result);
  console.log(JSON.stringify({ log, applied: applied(), statuses: statuses() }));
} else if (scenario === "delayed-reapply") {
  // cache hit in a new cycle schedules a deferred apply; the clip changes before it runs
  call(0, "msg_dictionary", input);
  call(1, "response", requestOf()[3], result);
  call(0, "msg_dictionary", input);
  const marker = log.length;
  holdQueue = true;
  call(0, "msg_dictionary", { ...input, seed: 456 });
  detailId = 8;
  release();
  console.log(JSON.stringify({ log, after: log.slice(marker), applied: applied().slice(0), statuses: statuses() }));
} else if (scenario === "meter") {
  const bodies = [];
  const withMeter = (n, d) => ({ ...input, clip: { ...input.clip, signature_numerator: n, signature_denominator: d } });
  call(0, "msg_dictionary", input);
  bodies.push(dicts[requestOf()[5]].context);
  call(0, "msg_dictionary", withMeter(7, 8));
  bodies.push(dicts[requestOf()[5]].context);
  call(0, "msg_dictionary", withMeter(0, 3));
  bodies.push(dicts[requestOf()[5]].context);
  console.log(JSON.stringify({ bodies, requests: log.filter((e) => e[0] === "outlet" && e[1] === 1 && e[2] === "request").length }));
} else if (scenario === "selection") {
  call(0, "msg_dictionary", input);
  call(1, "response", requestOf()[3], result);
  call(0, "msg_dictionary", input);
  const before = log.filter((e) => e[0] === "outlet" && e[1] === 1 && e[2] === "request").length;
  const moved = { ...input, clip: { time_selection_start: 8, time_selection_end: 24 } };
  call(0, "msg_dictionary", moved);
  const dictsOut = log.filter((e) => e[0] === "dict");
  console.log(JSON.stringify({ before, after: log.filter((e) => e[0] === "outlet" && e[1] === 1 && e[2] === "request").length, last: dictsOut[dictsOut.length - 1][2] }));
} else if (scenario === "describe") {
  dicts.res = { seed: 1, notes: [], drum_map: "gm", ignored: ["octave"] };
  call(0, "msg_dictionary", input);
  call(1, "response", requestOf()[3], "res");
  call(0, "msg_dictionary", input);
  console.log(JSON.stringify({ statuses: statuses() }));
} else if (scenario === "remove-fails") {
  call(0, "msg_dictionary", input);
  removeFails = true;
  call(1, "response", requestOf()[3], result);
  console.log(JSON.stringify({ log, applied: applied(), statuses: statuses() }));
} else if (scenario === "failure") {
  call(0, "msg_dictionary", input);
  call(1, "failed", requestOf()[3], "boom");
  console.log(JSON.stringify({ log, applied: applied(), statuses: statuses() }));
} else if (scenario === "basic") {
  call(0, "msg_dictionary", input);                 // pass 1: no-op answer + request
  const req = requestOf();
  call(1, "response", req[3], result);              // response -> re-bang
  call(0, "msg_dictionary", input);                 // pass 2: cached answer
  call(0, "msg_dictionary", input);                 // later apply with same inputs: still cached, no new request
  call(1, "param", "density", 80);                  // UI change -> bang
  call(0, "msg_dictionary", input);                 // changed inputs -> new request
  call(1, "response", 1, result);                   // stale response id -> ignored
  console.log(JSON.stringify({ log, body: dicts[req[5]] }));
} else {
  // replace: a second Generate click starts a new apply cycle (new Live seed) with the same settings
  if (scenario === "replace-off") call(1, "param", "replace", 0);
  call(0, "msg_dictionary", input);
  call(1, "response", requestOf()[3], result);
  call(0, "msg_dictionary", input);                 // re-apply inside the same cycle
  const marker = log.length;
  call(0, "msg_dictionary", { ...input, seed: 456 }); // new cycle, same settings
  call(0, "msg_dictionary", { ...input, seed: 456 }); // the self-triggered re-apply
  console.log(JSON.stringify({ log, after: log.slice(marker) }));
}
