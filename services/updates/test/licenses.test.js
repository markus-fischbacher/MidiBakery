// cd services/updates && node --test test/  (also run by tests/test_license.py)
import assert from "node:assert/strict";
import { test } from "node:test";

import worker from "../src/index.js";
import { addDays, keyHash, today, TRIAL_DAYS } from "../src/licenses.js";
import { b64url, verify } from "../src/tokens.js";
import { fakeD1 } from "./d1.js";

const MACHINE = "0123456789abcdef0123456789abcdef";
const OTHER = "fedcba9876543210fedcba9876543210";
const KEY = "MB-7KQ2-9XWM-ABCD-EFGH";

async function keys() {
  const pair = await crypto.subtle.generateKey({ name: "Ed25519" }, true, ["sign", "verify"]);
  const pkcs8 = new Uint8Array(await crypto.subtle.exportKey("pkcs8", pair.privateKey));
  const raw = new Uint8Array(await crypto.subtle.exportKey("raw", pair.publicKey));
  const b64 = (bytes) => btoa(String.fromCharCode(...bytes));
  return { secret: `ml-test:${b64(pkcs8)}`, public: { "ml-test": b64(raw) } };
}

async function setup({ seats = 2, revoked = 0, updatesUntil = "2027-10-17" } = {}) {
  const k = await keys();
  const DB = fakeD1();
  DB.raw.prepare("INSERT INTO licenses (key_hash, id, name, seats, updates_until, created, revoked) VALUES (?, ?, ?, ?, ?, ?, ?)")
    .run(await keyHash(KEY), "L-1", "Ada Lovelace", seats, updatesUntil, "2026-10-17", revoked);
  return { env: { DB, LICENSE_SIGNING_KEY: k.secret }, publicKeys: k.public };
}

const post = (env, action, body) => worker.fetch(new Request(`https://u/v1/midibakery/license/${action}`, {
  method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body),
}), env);

test("a trial runs 30 days from the first request, once per computer", async () => {
  const { env, publicKeys } = await setup();
  const first = await (await post(env, "trial", { machine: MACHINE })).json();
  const payload = await verify(first.token, publicKeys);
  assert.equal(payload.kind, "trial");
  assert.equal(payload.machine, MACHINE);
  assert.equal(payload.expires, addDays(today(), TRIAL_DAYS));
  env.DB.raw.prepare("UPDATE trials SET started = '2026-01-01' WHERE machine = ?").run(MACHINE);
  const again = await verify((await (await post(env, "trial", { machine: MACHINE })).json()).token, publicKeys);
  assert.equal(again.expires, addDays("2026-01-01", TRIAL_DAYS));  // not a fresh 30 days
});

test("activation issues a signed token with name and updates", async () => {
  const { env, publicKeys } = await setup();
  const response = await post(env, "activate", { key: KEY.toLowerCase(), machine: MACHINE });
  assert.equal(response.status, 200);
  const payload = await verify((await response.json()).token, publicKeys);
  assert.deepEqual([payload.kind, payload.license, payload.name, payload.updates_until, payload.expires],
    ["license", "L-1", "Ada Lovelace", "2027-10-17", null]);
  assert.equal((await post(env, "activate", { key: KEY, machine: MACHINE })).status, 200);  // again: same seat
});

test("seats are counted and freed by deactivation", async () => {
  const { env } = await setup({ seats: 1 });
  assert.equal((await post(env, "activate", { key: KEY, machine: MACHINE })).status, 200);
  const full = await post(env, "activate", { key: KEY, machine: OTHER });
  assert.equal(full.status, 409);
  assert.equal((await full.json()).error, "SEATS_FULL");
  assert.equal((await post(env, "deactivate", { key: KEY, machine: MACHINE })).status, 200);
  assert.equal((await post(env, "activate", { key: KEY, machine: OTHER })).status, 200);
});

test("unknown, malformed and revoked keys", async () => {
  const { env } = await setup({ revoked: 1 });
  assert.equal((await (await post(env, "activate", { key: "MB-AAAA-AAAA-AAAA-AAAA", machine: MACHINE })).json()).error, "UNKNOWN_KEY");
  assert.equal((await (await post(env, "activate", { key: "hello", machine: MACHINE })).json()).error, "INVALID_KEY");
  assert.equal((await (await post(env, "activate", { key: KEY, machine: MACHINE })).json()).error, "REVOKED");
  assert.equal((await post(env, "activate", { key: KEY, machine: "nope" })).status, 400);
});

test("without D1 or a signing key, licensing answers 503", async () => {
  const response = await post({}, "trial", { machine: MACHINE });
  assert.equal(response.status, 503);
  assert.equal((await response.json()).error, "LICENSING_OFF");
});

test("a forged or foreign token does not verify", async () => {
  const { env, publicKeys } = await setup();
  const token = (await (await post(env, "trial", { machine: MACHINE })).json()).token;
  const [id, , signature] = token.split(".");
  const forged = `${id}.${b64url(new TextEncoder().encode(JSON.stringify({ product: "midibakery", kind: "license" })))}.${signature}`;
  assert.equal(await verify(forged, publicKeys), null);
  assert.equal(await verify(token, (await keys()).public), null);
});

test("with REQUIRE_LICENSE_FOR_UPDATES, downloads follow the token's updates", async () => {
  const { env, publicKeys } = await setup({ updatesUntil: "2027-01-01" });
  const token = (await (await post(env, "activate", { key: KEY, machine: MACHINE })).json()).token;
  const files = {
    "midibakery/releases/0.3.0/manifest.json": JSON.stringify({ manifest: JSON.stringify({ released: "2026-12-01T10:00:00Z" }) }),
    "midibakery/releases/0.3.0/MidiBakery-0.3.0-macos-arm64.pkg": "PKG3",
    "midibakery/releases/0.4.0/manifest.json": JSON.stringify({ manifest: JSON.stringify({ released: "2027-02-01T10:00:00Z" }) }),
    "midibakery/releases/0.4.0/MidiBakery-0.4.0-macos-arm64.pkg": "PKG4",
  };
  const RELEASES = {
    async get(key) {
      if (!(key in files)) return null;
      const bytes = new TextEncoder().encode(files[key]);
      return { body: bytes, size: bytes.length, text: async () => files[key] };
    },
  };
  const gated = { ...env, RELEASES, REQUIRE_LICENSE_FOR_UPDATES: "1", LICENSE_PUBLIC_KEYS: JSON.stringify(publicKeys) };
  const download = (version, auth) => worker.fetch(new Request(
    `https://u/v1/midibakery/download/${version}/MidiBakery-${version}-macos-arm64.pkg`,
    { headers: auth ? { authorization: auth } : {} }), gated);
  assert.equal((await download("0.3.0", `License ${token}`)).status, 200);
  assert.equal((await download("0.4.0", `License ${token}`)).status, 402);  // after updates_until
  assert.equal((await download("0.3.0")).status, 402);
  assert.equal((await download("0.3.0", "License junk")).status, 402);
  assert.equal((await download("0.4.0", `License ${token}`).then(() => download("0.4.0"))).status, 402);
  const open = { ...env, RELEASES };  // not enforced: everyone gets everything
  const plain = await worker.fetch(new Request("https://u/v1/midibakery/download/0.4.0/MidiBakery-0.4.0-macos-arm64.pkg"), open);
  assert.equal(plain.status, 200);
});
