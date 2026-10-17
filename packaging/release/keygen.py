"""Makes an Ed25519 key pair for MidiBakery. Run it yourself, once per purpose:

    uv run python packaging/release/keygen.py ~/midibakery-signing.key            # update manifests
    uv run python packaging/release/keygen.py --license ~/midibakery-license.key  # license tokens

It writes the private key (one line) to the file you name and prints the public half. Keep the file
offline (a password manager); it never goes into the repository.

Update manifests:
  - the file's content goes into the GitHub secret MIDIBAKERY_SIGNING_KEY (environment "release");
  - the printed line goes into UPDATE_KEYS in packages/core/src/midibakery/updates.py.

License tokens (the Worker signs them when it issues a trial or activates a license):
  - the file's content goes into the Worker secret: npx wrangler secret put LICENSE_SIGNING_KEY
    (in services/updates);
  - the printed line goes into LICENSE_KEYS in packages/core/src/midibakery/license.py, and into the
    LICENSE_PUBLIC_KEYS JSON in services/updates/wrangler.toml.

A new key needs a release that already trusts it (two keys listed for one release) before anything is
signed with it; installs that only know the old key reject the new one.
"""

from __future__ import annotations

import base64
import hashlib
import os
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

RAW = (serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def key_id(public: bytes, prefix: str = "mb") -> str:
    return f"{prefix}-" + hashlib.sha256(public).hexdigest()[:12]


def private_line(private: Ed25519PrivateKey, license_key: bool, kid: str) -> str:
    if license_key:
        # WebCrypto in the Worker imports PKCS#8, not raw keys; the key id travels with it
        der = private.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        return f"{kid}:{base64.b64encode(der).decode()}"
    seed = private.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    return base64.b64encode(seed).decode()


def main(argv: list[str]) -> int:
    license_key = "--license" in argv
    paths = [a for a in argv if a != "--license"]
    if len(paths) != 1:
        raise SystemExit(__doc__)
    path = Path(paths[0]).expanduser()
    if path.exists():
        raise SystemExit(f"{path} exists; refusing to overwrite a key")
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(*RAW)
    kid = key_id(public, "ml" if license_key else "mb")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(private_line(private, license_key, kid) + "\n")
    if license_key:
        print(f"private key written to {path} (Worker secret LICENSE_SIGNING_KEY)")
        print("public key for LICENSE_KEYS in packages/core/src/midibakery/license.py")
        print("and LICENSE_PUBLIC_KEYS in services/updates/wrangler.toml:")
    else:
        print(f"private key written to {path} (GitHub secret MIDIBAKERY_SIGNING_KEY)")
        print("public key for UPDATE_KEYS in packages/core/src/midibakery/updates.py:")
    print(f'    "{kid}": "{base64.b64encode(public).decode()}",')
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
