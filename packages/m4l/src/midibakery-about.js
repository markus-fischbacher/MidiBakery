/**
 * The devices' About line: this device's version (build.py puts it into the About button's message)
 * next to the running API's and the Remote Script's, from the API's /health. Parts of one install
 * share one version; a difference means something was not reinstalled.
 *
 * Shared by midibakery-node.js and midibakery-reference.js; Node built-ins only.
 */

"use strict";

const fs = require("fs");
const os = require("os");
const path = require("path");

const TIMEOUT_MS = 4000;

function configDir() {
  if (process.env.MIDIBAKERY_HOME) return process.env.MIDIBAKERY_HOME;
  if (process.platform === "darwin") return path.join(os.homedir(), "Library", "Application Support", "MidiBakery");
  if (process.platform === "win32") return path.join(process.env.APPDATA || os.homedir(), "MidiBakery");
  return path.join(os.homedir(), ".config", "midibakery");
}

function readApi() {
  try {
    const info = JSON.parse(fs.readFileSync(path.join(configDir(), "api.json"), "utf8"));
    if (Number.isInteger(info.port) && typeof info.token === "string") return info;
  } catch (_) {
    // missing or half-written: not running
  }
  return null;
}

/** {api, script}: the versions the API reports; api null when it does not answer, script null without Live. */
async function versions() {
  const info = readApi();
  if (!info) return { api: null, script: null };
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const response = await fetch(`http://127.0.0.1:${info.port}/health`, {
      headers: { authorization: `Bearer ${info.token}` },
      signal: controller.signal,
    });
    const data = await response.json();
    return { api: data.version || null, script: (data.live && data.live.bridge) || null };
  } catch (_) {
    return { api: null, script: null };
  } finally {
    clearTimeout(timer);
  }
}

/** One line for the device's status, e.g. "MidiBakery 0.2.0 (device, API, Remote Script)". */
function aboutText(device, found) {
  if (!found.api) return `MidiBakery ${device} · API not running`;
  const parts = [["device", device], ["API", found.api]];
  if (found.script) parts.push(["Remote Script", found.script]);
  const missing = found.script ? "" : " · Remote Script not connected";
  if (parts.every(([, version]) => version === device)) return `MidiBakery ${device} (${parts.map(([name]) => name).join(", ")})${missing}`;
  return `Versions differ: ${parts.map(([name, version]) => `${name} ${version}`).join(", ")} - reinstall MidiBakery${missing}`;
}

async function about(device) {
  return aboutText(String(device), await versions());
}

module.exports = { about, aboutText, versions };
