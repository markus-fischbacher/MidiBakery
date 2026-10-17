// License tokens: <key id>.<base64url payload JSON>.<base64url Ed25519 signature over "<key id>.<payload>">.
// The app checks them offline (packages/core/src/midibakery/license.py); the Worker signs them and checks
// the ones that come with update downloads. WebCrypto only.

const encoder = new TextEncoder();

export function b64url(bytes) {
  let text = "";
  for (const byte of new Uint8Array(bytes)) text += String.fromCharCode(byte);
  return btoa(text).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/, "");
}

function unb64(text) {
  const plain = text.replaceAll("-", "+").replaceAll("_", "/");
  const binary = atob(plain + "=".repeat((4 - (plain.length % 4)) % 4));
  return Uint8Array.from(binary, (c) => c.charCodeAt(0));
}

/** The secret LICENSE_SIGNING_KEY: "<key id>:<base64 PKCS#8 Ed25519 private key>" (keygen.py --license). */
export async function signer(secret) {
  const [keyId, pkcs8] = String(secret || "").split(":");
  if (!keyId || !pkcs8) return null;
  const key = await crypto.subtle.importKey("pkcs8", unb64(pkcs8), { name: "Ed25519" }, false, ["sign"]);
  return {
    async sign(payload) {
      const body = `${keyId}.${b64url(encoder.encode(JSON.stringify(payload)))}`;
      const signature = await crypto.subtle.sign({ name: "Ed25519" }, key, encoder.encode(body));
      return `${body}.${b64url(signature)}`;
    },
  };
}

/** The payload of a token one of keys ({id: base64 raw public key}) signed, or null. */
export async function verify(token, keys) {
  const parts = String(token || "").trim().split(".");
  if (parts.length !== 3 || !keys || !(parts[0] in keys)) return null;
  try {
    const raw = Uint8Array.from(atob(keys[parts[0]]), (c) => c.charCodeAt(0));
    const key = await crypto.subtle.importKey("raw", raw, { name: "Ed25519" }, false, ["verify"]);
    const ok = await crypto.subtle.verify({ name: "Ed25519" }, key, unb64(parts[2]), encoder.encode(`${parts[0]}.${parts[1]}`));
    if (!ok) return null;
    const payload = JSON.parse(new TextDecoder().decode(unb64(parts[1])));
    return payload && payload.product === "midibakery" ? payload : null;
  } catch (_) {
    return null;
  }
}
