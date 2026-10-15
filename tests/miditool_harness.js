// Runs the MIDI Tool v8 code with stubbed Max globals; prints the event log as JSON.
// Usage: node miditool_harness.js <code.js> <scenario>
"use strict";
const fs = require("fs");
const vm = require("vm");

const log = [];
const dicts = {};
function Dict(name) {
  this.parse = (text) => { dicts[name] = JSON.parse(text); };
  this.stringify = () => JSON.stringify(dicts[name]);
}
function Task(fn) {
  this.schedule = () => log.push(["task", "schedule"]);
  this.cancel = () => {};
}
function LiveAPI(path) {
  this.id = 7;
  this.call = (...args) => log.push(["liveapi", path, ...args]);
}
const sandbox = {
  LiveAPI, Dict, Task, Date, Array, String,
  inlet: 0,
  outlet: (...args) => log.push(["outlet", ...args]),
  outlet_dictionary: (n, d) => log.push(["dict", n, JSON.parse(JSON.stringify(d))]),
  post: () => {},
  Math, JSON, Number, String, Boolean,
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), sandbox);
const call = (inletIndex, fn, ...args) => { sandbox.inlet = inletIndex; return vm.runInContext(fn, sandbox)(...args); };

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

if (scenario === "basic") {
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
