// cd services/updates && node --test test/worker.test.js  (also run by tests/test_updates.py)
import assert from "node:assert/strict";
import { test } from "node:test";

import worker from "../src/index.js";

function bucket(files) {
  return {
    async get(key) {
      if (!(key in files)) return null;
      const bytes = new TextEncoder().encode(files[key]);
      return { body: bytes, size: bytes.length, httpEtag: `"${key.length}"` };
    },
  };
}

const env = {
  RELEASES: bucket({
    "midibakery/channels/stable.json": '{"manifest":"{}","key":"mb-1","signature":"AA=="}',
    "midibakery/releases/0.3.0/MidiBakery-0.3.0-macos-arm64.pkg": "PKG",
  }),
};
const get = (path, init) => worker.fetch(new Request(`https://updates.klirrwerk.com${path}`, init), env);

test("latest returns the channel's envelope, briefly cached", async () => {
  const response = await get("/v1/midibakery/latest?channel=stable&version=0.2.0&os=macos&arch=arm64");
  assert.equal(response.status, 200);
  assert.equal(JSON.parse(await response.text()).key, "mb-1");
  assert.match(response.headers.get("cache-control"), /max-age=300/);
  assert.match(response.headers.get("content-type"), /application\/json/);
});

test("latest defaults to the stable channel", async () => {
  assert.equal((await get("/v1/midibakery/latest")).status, 200);
});

test("an unknown or malformed channel is refused", async () => {
  assert.equal((await get("/v1/midibakery/latest?channel=beta")).status, 404);
  assert.equal((await get("/v1/midibakery/latest?channel=../x")).status, 400);
});

test("download streams an installer, immutable", async () => {
  const response = await get("/v1/midibakery/download/0.3.0/MidiBakery-0.3.0-macos-arm64.pkg");
  assert.equal(response.status, 200);
  assert.equal(await response.text(), "PKG");
  assert.equal(response.headers.get("content-length"), "3");
  assert.match(response.headers.get("cache-control"), /immutable/);
});

test("HEAD answers without a body", async () => {
  const response = await get("/v1/midibakery/download/0.3.0/MidiBakery-0.3.0-macos-arm64.pkg", { method: "HEAD" });
  assert.equal(response.status, 200);
  assert.equal(await response.text(), "");
});

test("download paths outside the release layout are refused", async () => {
  for (const path of [
    "/v1/midibakery/download/0.3/MidiBakery-0.3.0-macos-arm64.pkg",
    "/v1/midibakery/download/0.3.0/..%2Fchannels%2Fstable.json",
    "/v1/midibakery/download/0.3.0/other.pkg",
    "/v1/midibakery/download/0.3.0/MidiBakery-0.3.0.zip",
  ]) {
    assert.equal((await get(path)).status, 400, path);
  }
  assert.equal((await get("/v1/midibakery/download/0.3.0/a/b")).status, 404);
  assert.equal((await get("/v1/midibakery/download/0.9.0/MidiBakery-0.9.0-macos-arm64.pkg")).status, 404);
});

test("other paths and methods", async () => {
  assert.equal((await get("/")).status, 404);
  assert.equal((await get("/v1/other/latest")).status, 404);
  assert.equal((await get("/v1/midibakery/latest", { method: "POST" })).status, 405);
});

test("a failing bucket answers 500 without details", async () => {
  const broken = { RELEASES: { get: async () => { throw new Error("secret detail"); } } };
  const response = await worker.fetch(new Request("https://u/v1/midibakery/latest"), broken);
  assert.equal(response.status, 500);
  assert.doesNotMatch(await response.text(), /secret/);
});
