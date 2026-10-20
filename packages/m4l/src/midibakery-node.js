/**
 * MidiBakery Node for Max helper, shared by the devices.
 *
 *   node.script midibakery-chat.js       chat device: feeds jweb the chat page URL
 *   node.script midibakery-miditool.js   MIDI Tools: async HTTP for the v8 code
 *
 * Those entry files set MIDIBAKERY_DEVICE and load this module. Script arguments
 * are not used: Node for Max runs scripts through its own runner, so
 * process.argv does not hold them where a plain `node script arg` would.
 *
 * Finds the local MidiBakery API through api.json (port + token) written by
 * `midibakery api`, and follows it when the API restarts with a new token.
 * Uses only Node built-ins (Max 9.1+ bundles Node 22: fetch, child_process).
 */

"use strict";

const crypto = require("crypto");
const fs = require("fs");
const os = require("os");
const path = require("path");
const { execFile } = require("child_process");
const Max = require("max-api");
const { about } = require("./midibakery-about.js");

// Devices that show a page of the API in a jweb (the others are MIDI Tools): the page each shows.
const PAGES = { chat: "/ui", importer: "/importer" };
const MODE = process.env.MIDIBAKERY_DEVICE in PAGES ? process.env.MIDIBAKERY_DEVICE : "miditool";
const PAGE = PAGES[MODE];
const POLL_MS = 2000;
const REQUEST_TIMEOUT_MS = 15000;

function configDir() {
  if (process.env.MIDIBAKERY_HOME) return process.env.MIDIBAKERY_HOME;
  if (process.platform === "darwin") return path.join(os.homedir(), "Library", "Application Support", "MidiBakery");
  if (process.platform === "win32") return path.join(process.env.APPDATA || os.homedir(), "MidiBakery");
  return path.join(os.homedir(), ".config", "midibakery");
}

const API_FILE = path.join(configDir(), "api.json");
const LOG_FILE = path.join(configDir(), `device-${MODE}.log`);

// Small rolling log next to api.json, for diagnosing devices without the Max console.
function log(...parts) {
  try {
    const text = parts.map((p) => (typeof p === "string" ? p : JSON.stringify(p))).join(" ");
    // Never write the API token (it shows up in URLs jweb reports back).
    const line = `${new Date().toISOString()} ${text.replace(/token=[^\s"&]*/g, "token=***")}\n`;
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
let waiting = false; // the API did not answer yet: "Starting..." is on the status line

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
  // A new token must be a new page: jweb does not reload when only the #fragment changes,
  // and the page reads its token once. The query is derived from the token, never the token.
  const key = crypto.createHash("sha256").update(api.token).digest("hex").slice(0, 8);
  return `http://127.0.0.1:${api.port}${PAGE}?key=${key}#token=${encodeURIComponent(api.token)}`;
}

async function refresh() {
  const next = readApi();
  const changed = JSON.stringify(next) !== JSON.stringify(api);
  api = next;
  if (!changed) return;
  if (!api) {
    await Max.outlet("status", "MidiBakery API not running - start it with: midibakery api");
    return;
  }
  if (!PAGE) await Max.outlet("status", `MidiBakery API on port ${api.port}`);
  if (PAGE) {
    waiting = false;
    pageLoaded = false;
    loadAttempts = 0;
    await loadPage();
  }
}

const MAX_LOAD_ATTEMPTS = 5;

// api.json can be left from an API that is gone, or name one that is still starting: jweb would show
// "page can't be reached" for that moment. Only a page of an API that answers is sent.
async function answers() {
  try {
    const response = await fetch(`http://127.0.0.1:${api.port}/health`, {
      headers: { authorization: `Bearer ${api.token}` },
      signal: AbortSignal.timeout(1500),
    });
    return response.ok;
  } catch (_) {
    return false;
  }
}

async function loadPage() {
  if (!PAGE || !api || pageLoaded) return;
  if (loadAttempts >= MAX_LOAD_ATTEMPTS) {
    if (loadAttempts === MAX_LOAD_ATTEMPTS) {
      loadAttempts += 1;
      await Max.outlet("status", "The page did not load in the device - use Pop out");
    }
    return;
  }
  if (!(await answers())) {
    if (!waiting) await Max.outlet("status", "Starting MidiBakery API...");
    waiting = true;
    return;
  }
  waiting = false;
  loadAttempts += 1;
  if (loadAttempts > 1) await Max.outlet("status", `Loading page (attempt ${loadAttempts})...`);
  log("send url", chatUrl(), "attempt", loadAttempts);
  await Max.outlet("url", chatUrl());
}

// Everything jweb reports (navigation, load events) except "loaded", for the log.
Max.addHandler("jweb", (...args) => log("jweb", args));

Max.addHandler("loaded", async () => {
  log("page loaded");
  pageLoaded = true;
  if (api) await Max.outlet("status", `Connected to MidiBakery API on port ${api.port}`);
});

// Max dicts hold numbers, strings, arrays and dicts only: no booleans, no null.
function toMaxDict(value) {
  if (value === true) return 1;
  if (value === false) return 0;
  if (Array.isArray(value)) return value.filter((v) => v !== null && v !== undefined).map(toMaxDict);
  if (value && typeof value === "object") {
    const out = {};
    for (const [key, v] of Object.entries(value)) {
      if (v !== null && v !== undefined) out[key] = toMaxDict(v);
    }
    return out;
  }
  return value;
}

function describeError(error) {
  if (!error) return "unknown error";
  if (typeof error === "string") return error;
  return error.message || error.name || JSON.stringify(error);
}

async function post(route, body) {
  if (!api) throw new Error("MidiBakery API not running");
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

// From the v8 code: request <id> <generate|transform> <dict name>; the body is in that dict
// and the result goes back in "<dict name>_res".
Max.addHandler("request", async (id, kind, dictName) => {
  const started = Date.now();
  let step = "check";
  try {
    if (kind !== "generate" && kind !== "transform") throw new Error(`unknown request kind ${kind}`);
    step = "read request dict";
    const body = await Max.getDict(dictName);
    step = "call API";
    const result = await post(`/miditool/${kind}`, body);
    step = "write result dict";
    const resName = `${dictName}_res`;
    await Max.setDict(resName, toMaxDict(result));
    log("request", id, kind, `${(result.notes || []).length} notes`, `${Date.now() - started} ms`);
    await Max.outlet("response", id, resName);
  } catch (error) {
    const message = `${step}: ${describeError(error)}`;
    log("request failed", id, kind, message, error && error.stack ? error.stack : "");
    await Max.outlet("failed", id, message);
  }
});

Max.addHandler("log", (...args) => log("v8", args));

// Chat device: open the same page in the system browser, with more room.
Max.addHandler("popout", () => {
  if (!api) return;
  const url = chatUrl();
  if (process.platform === "darwin") execFile("open", [url]);
  else if (process.platform === "win32") execFile("cmd", ["/c", "start", "", url]);
  else execFile("xdg-open", [url]);
});

// About button: about <device version> -> the versions in the status line.
Max.addHandler("about", async (version) => {
  await Max.outlet("status", await about(version));
});

Max.addHandler("refresh", () => {
  api = null;
  return refresh();
});

log("start", MODE, process.version);
refresh();
setInterval(refresh, POLL_MS);
setInterval(loadPage, 3000);
