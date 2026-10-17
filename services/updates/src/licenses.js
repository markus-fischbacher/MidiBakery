// Trials and licenses: POST /v1/midibakery/license/{trial,activate,deactivate}, JSON in and out.
// D1 (binding DB, migrations/) holds licenses, activations and trials; LICENSE_SIGNING_KEY signs the tokens.
// Licenses are created by packaging/release/issue_license.py (later: the merchant of record's webhook).

import { signer } from "./tokens.js";

export const TRIAL_DAYS = 30;
const MACHINE = /^[0-9a-f]{32}$/;
const KEY = /^MB(-[0-9A-Z]{4}){4}$/;

function json(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
  });
}
const fail = (status, error, message) => json(status, { error, message });

export function today(now = new Date()) {
  return now.toISOString().slice(0, 10);
}

export function addDays(date, days) {
  const d = new Date(`${date}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return today(d);
}

export async function keyHash(key) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(key));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function body(request) {
  try {
    const data = await request.json();
    return data && typeof data === "object" ? data : {};
  } catch (_) {
    return {};
  }
}

export async function handleLicense(request, env, action, now = new Date()) {
  if (request.method !== "POST") return fail(405, "METHOD", "use POST");
  const sign = env.DB ? await signer(env.LICENSE_SIGNING_KEY) : null;
  if (!sign) return fail(503, "LICENSING_OFF", "licensing is not set up on this service");
  const data = await body(request);
  const machine = String(data.machine || "");
  if (!MACHINE.test(machine)) return fail(400, "BAD_REQUEST", "missing or malformed machine id");
  const date = today(now);

  if (action === "trial") {
    // one trial per computer; asking again returns the same one
    await env.DB.prepare("INSERT OR IGNORE INTO trials (machine, started) VALUES (?, ?)").bind(machine, date).run();
    const trial = await env.DB.prepare("SELECT started FROM trials WHERE machine = ?").bind(machine).first();
    const expires = addDays(trial.started, TRIAL_DAYS);
    const token = await sign.sign({ product: "midibakery", kind: "trial", machine, issued: date, expires, updates_until: expires });
    return json(200, { token });
  }

  const key = String(data.key || "").toUpperCase();
  if (!KEY.test(key)) return fail(400, "INVALID_KEY", "That does not look like a MidiBakery license key.");
  const hash = await keyHash(key);
  const license = await env.DB.prepare("SELECT id, name, seats, updates_until, revoked FROM licenses WHERE key_hash = ?").bind(hash).first();

  if (action === "deactivate") {
    if (license) await env.DB.prepare("DELETE FROM activations WHERE key_hash = ? AND machine = ?").bind(hash, machine).run();
    return json(200, { ok: true });
  }
  if (action !== "activate") return fail(404, "NOT_FOUND", "unknown license action");
  if (!license) return fail(404, "UNKNOWN_KEY", "This license key is not known. Check it for typos.");
  if (license.revoked) return fail(403, "REVOKED", "This license key is no longer valid.");

  const known = await env.DB.prepare("SELECT machine FROM activations WHERE key_hash = ? AND machine = ?").bind(hash, machine).first();
  if (known) {
    await env.DB.prepare("UPDATE activations SET last_seen = ? WHERE key_hash = ? AND machine = ?").bind(date, hash, machine).run();
  } else {
    const used = await env.DB.prepare("SELECT COUNT(*) AS n FROM activations WHERE key_hash = ?").bind(hash).first();
    if (used.n >= license.seats) {
      return fail(409, "SEATS_FULL", `This license is active on ${used.n} computers already. ` +
        "Deactivate one (midibakery license deactivate, or the Chat device) and try again.");
    }
    await env.DB.prepare("INSERT INTO activations (key_hash, machine, activated, last_seen) VALUES (?, ?, ?, ?)")
      .bind(hash, machine, date, date).run();
  }
  const token = await sign.sign({
    product: "midibakery", kind: "license", license: license.id, name: license.name, machine,
    issued: date, expires: null, updates_until: license.updates_until,
  });
  return json(200, { token });
}
