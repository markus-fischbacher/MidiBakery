"""Makes the Ed25519 key pair that signs MidiBakery's update manifests. Run it once, yourself:

    uv run python packaging/release/keygen.py ~/midibakery-signing.key

It writes the private key (base64, one line) to the file you name and prints the public half. Then:
  - the file's content goes into the GitHub secret MIDIBAKERY_SIGNING_KEY, and the file somewhere safe
    offline (a password manager); never into the repository;
  - the printed line goes into UPDATE_KEYS in packages/core/src/midibakery/updates.py.

A new key needs a release that already trusts it (two keys in UPDATE_KEYS for one release) before
manifests are signed with it; installs that only know the old key reject the new one.
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


def key_id(public: bytes) -> str:
    return "mb-" + hashlib.sha256(public).hexdigest()[:12]


def main(target: str) -> int:
    path = Path(target).expanduser()
    if path.exists():
        raise SystemExit(f"{path} exists; refusing to overwrite a key")
    private = Ed25519PrivateKey.generate()
    seed = private.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    public = private.public_key().public_bytes(*RAW)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(base64.b64encode(seed).decode() + "\n")
    print(f"private key written to {path} (GitHub secret MIDIBAKERY_SIGNING_KEY)")
    print("public key for UPDATE_KEYS in packages/core/src/midibakery/updates.py:")
    print(f'    "{key_id(public)}": "{base64.b64encode(public).decode()}",')
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    sys.exit(main(sys.argv[1]))
