/**
 * MidiShower Node for Max helper, shared by the devices.
 *
 *   node.script midishower-chat.js       chat device: feeds jweb the chat page URL
 *   node.script midishower-miditool.js   MIDI Tools: async HTTP for the v8 code
 *
 * Those entry files set MIDISHOWER_DEVICE and load this module. Script arguments
 * are not used: Node for Max runs scripts through its own runner, so
 * process.argv does not hold them where a plain `node script arg` would.
 *
 * Finds the local MidiShower API through api.json (port + token) written by
 * `midishower api`, and follows it when the API restarts with a new token.
 * Uses only Node built-ins (Max 9.1+ bundles Node 22: fetch, child_process).
 */

"use strict";

const fs = require("fs");
const os = require("os");
const path = require("path");
const { execFile } = require("child_process");
const Max = require("max-api");

const MODE = process.env.MIDISHOWER_DEVICE === "chat" ? "chat" : "miditool";
const POLL_MS = 2000;
const REQUEST_TIMEOUT_MS = 15000;

function configDir() {
  if (process.env.MIDISHOWER_HOME) return process.env.MIDISHOWER_HOME;
  if (process.platform === "darwin") return path.join(os.homedir(), "Library", "Application Support", "MidiShower");
  if (process.platform === "win32") return path.join(process.env.APPDATA || os.homedir(), "MidiShower");
  return path.join(os.homedir(), ".config", "midishower");
}

const API_FILE = path.join(configDir(), "api.json");
const LOG_FILE = path.join(configDir(), `device-${MODE}.log`);

// Small rolling log next to api.json, for diagnosing devices without the Max console.
function log(...parts) {
  try {
    const line = `${new Date().toISOString()} ${parts.map((p) => (typeof p === "string" ? p : JSON.stringify(p))).join(" ")}\n`;
    if (fs.existsSync(LOG_FILE) && fs.statSync(LOG_FILE).size > 256 * 1024) fs.renameSync(LOG_FILE, `${LOG_FILE}.1`);
    fs.appendFileSync(LOG_FILE, line);
  } catch (_) {
    // logging must never break the device
  }
}
let api = null; // {port, token}
// Chat: jweb may not be ready when the first URL arrives, so it is re-sent until
// the page reports back ("loaded", via window.max in jweb).
let pageLoaded = false;
let loadAttempts = 0;

function readApi() {
  try {
    const info = JSON.parse(fs.readFileSync(API_FILE, "utf8"));
    if (Number.isInteger(info.port) && typeof info.token === "string") return { port: info.port, token: info.token };
  } catch (_) {
    // missing or half-written: treat as not running
  }
  return null;
}

function chatUrl() {
  return `http://127.0.0.1:${api.port}/ui#token=${encodeURIComponent(api.token)}`;
}

async function refresh() {
  const next = readApi();
  const changed = JSON.stringify(next) !== JSON.stringify(api);
  api = next;
  if (!changed) return;
  if (!api) {
    await Max.outlet("status", "MidiShower API not running - start it with: midishower api");
    return;
  }
  await Max.outlet("status", `MidiShower API on port ${api.port}`);
  if (MODE === "chat") {
    pageLoaded = false;
    loadAttempts = 0;
    await loadPage();
  }
}

const MAX_LOAD_ATTEMPTS = 5;

async function loadPage() {
  if (MODE !== "chat" || !api || pageLoaded) return;
  if (loadAttempts >= MAX_LOAD_ATTEMPTS) {
    if (loadAttempts === MAX_LOAD_ATTEMPTS) {
      loadAttempts += 1;
      await Max.outlet("status", "Chat page did not load in the device - use Pop out");
    }
    return;
  }
  loadAttempts += 1;
  if (loadAttempts > 1) await Max.outlet("status", `Loading chat page (attempt ${loadAttempts})...`);
  log("send url", chatUrl().replace(/token=.*/, "token=***"), "attempt", loadAttempts);
  await Max.outlet("url", chatUrl());
}

// Everything jweb reports (navigation, load events) except "loaded", for the log.
Max.addHandler("jweb", (...args) => log("jweb", args));

Max.addHandler("loaded", async () => {
  log("page loaded");
  pageLoaded = true;
  if (api) await Max.outlet("status", `Connected to MidiShower API on port ${api.port}`);
});

async function post(route, body) {
  if (!api) throw new Error("MidiShower API not running");
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(`http://127.0.0.1:${api.port}${route}`, {
      method: "POST",
      headers: { "content-type": "application/json", authorization: `Bearer ${api.token}` },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = data.message || (data.details && data.details.map((d) => `${(d.loc || []).join(".")}: ${d.msg}`).join("; ")) || data.error;
      throw new Error(`${response.status} ${detail || response.statusText}`);
    }
    return data;
  } finally {
    clearTimeout(timer);
  }
}

// From the v8 code: request <id> <generate|transform> <json body>
Max.addHandler("request", async (id, kind, json) => {
  try {
    if (kind !== "generate" && kind !== "transform") throw new Error(`unknown request kind ${kind}`);
    const result = await post(`/miditool/${kind}`, JSON.parse(json));
    await Max.outlet("response", id, JSON.stringify(result));
  } catch (error) {
    await Max.outlet("failed", id, String(error.message || error));
  }
});

// Chat device: open the same page in the system browser, with more room.
Max.addHandler("popout", () => {
  if (!api) return;
  const url = chatUrl();
  if (process.platform === "darwin") execFile("open", [url]);
  else if (process.platform === "win32") execFile("cmd", ["/c", "start", "", url]);
  else execFile("xdg-open", [url]);
});

Max.addHandler("refresh", () => {
  api = null;
  return refresh();
});

log("start", MODE, process.version);
refresh();
setInterval(refresh, POLL_MS);
setInterval(loadPage, 3000);
