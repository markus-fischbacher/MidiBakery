// MidiBakery's update service: a Cloudflare Worker in front of the R2 bucket that holds the releases.
//
//   GET /v1/midibakery/latest?channel=stable           the channel's signed manifest (envelope JSON)
//   GET /v1/midibakery/download/<version>/<installer>  an installer
//
// R2 layout (written by .github/workflows/release.yml):
//   midibakery/channels/<channel>.json
//   midibakery/releases/<version>/<installer>
//
// The Worker only hands out files; whether they can be trusted is decided by the app, which checks the
// manifest's Ed25519 signature and each installer's SHA-256 (packages/core/src/midibakery/updates.py).
// Requests carry version, os, arch and channel; nothing is logged or stored beyond Cloudflare's defaults.

const PREFIX = "/v1/midibakery/";
const CHANNEL = /^[a-z][a-z0-9-]{0,31}$/;
const VERSION = /^\d+\.\d+\.\d+$/;
const INSTALLER = /^MidiBakery-[A-Za-z0-9.-]+\.(pkg|exe)$/;

// Sold versions later: a request may carry "Authorization: License <key>". Until then every request is
// allowed; this is the one place a check goes.
export async function licensed(request, env) {
  return true;
}

function text(status, message, extra = {}) {
  return new Response(message + "\n", {
    status,
    headers: { "content-type": "text/plain; charset=utf-8", "cache-control": "no-store", ...extra },
  });
}

async function object(env, key, request, headers) {
  const found = await env.RELEASES.get(key);
  if (found === null) return text(404, "not found");
  const out = new Headers(headers);
  if (found.httpEtag) out.set("etag", found.httpEtag);
  out.set("content-length", String(found.size));
  return new Response(request.method === "HEAD" ? null : found.body, { status: 200, headers: out });
}

export async function handle(request, env) {
  if (request.method !== "GET" && request.method !== "HEAD") return text(405, "method not allowed", { allow: "GET, HEAD" });
  const url = new URL(request.url);
  if (!url.pathname.startsWith(PREFIX)) return text(404, "not found");
  if (!(await licensed(request, env))) return text(403, "no valid license");
  const parts = url.pathname.slice(PREFIX.length).split("/");

  if (parts.length === 1 && parts[0] === "latest") {
    const channel = url.searchParams.get("channel") || "stable";
    if (!CHANNEL.test(channel)) return text(400, "bad channel");
    // short cache: a new release reaches everyone within minutes
    return object(env, `midibakery/channels/${channel}.json`, request, {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "public, max-age=300",
    });
  }
  if (parts.length === 3 && parts[0] === "download") {
    const [, version, name] = parts;
    if (!VERSION.test(version) || !INSTALLER.test(name)) return text(400, "bad download path");
    // a release's files never change
    return object(env, `midibakery/releases/${version}/${name}`, request, {
      "content-type": "application/octet-stream",
      "content-disposition": `attachment; filename="${name}"`,
      "cache-control": "public, max-age=31536000, immutable",
    });
  }
  return text(404, "not found");
}

export default {
  async fetch(request, env) {
    try {
      return await handle(request, env);
    } catch (error) {
      return text(500, "update service error");
    }
  },
};
