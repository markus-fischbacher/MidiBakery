"""Writes the signed update manifest for a release (CI, on a v* tag; see .github/workflows/release.yml).

    MIDIBAKERY_SIGNING_KEY=<base64 private key> \
    python packaging/release/make_manifest.py <folder with the installers> <out.json> [--channel stable] [--notes TEXT]

The folder holds the installers the package workflow built (MidiBakery-<version>-macos-arm64.pkg,
MidiBakery-<version>-windows-x64-setup.exe, ...). The out file is the envelope the update service hands
out: {"manifest": <the manifest's exact JSON text>, "key": <key id>, "signature": <base64 Ed25519>}.
The key comes only from the environment, never from a file in the repository.
"""

from __future__ import annotations

import argparse
import base64
import datetime
import hashlib
import json
import os
import re
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[2]
VERSION = re.search(r'^__version__ = "([^"]+)"', (ROOT / "packages/core/src/midibakery/__init__.py").read_text(encoding="utf-8"), re.M)[1]
# installer file name -> the platform key the app asks for (midibakery.updates.platform_key)
INSTALLER = re.compile(r"^MidiBakery-(?P<version>\d+\.\d+\.\d+)-(?P<platform>(?:macos|windows)-(?:arm64|x64))(?:-setup\.exe|\.pkg)$")


def key_id(public: bytes) -> str:
    return "mb-" + hashlib.sha256(public).hexdigest()[:12]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def manifest(folder: Path, version: str, channel: str, notes: str) -> dict:
    files = {}
    for path in sorted(folder.iterdir()):
        match = INSTALLER.match(path.name)
        if not match:
            continue
        if match["version"] != version:
            raise SystemExit(f"{path.name} is not version {version}")
        files[match["platform"]] = {"name": path.name, "size": path.stat().st_size, "sha256": sha256(path)}
    if not files:
        raise SystemExit(f"no installers in {folder}")
    return {"product": "midibakery", "channel": channel, "version": version,
            "released": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "notes": notes, "files": files}


def sign(data: dict, private_key: str) -> dict:
    private = Ed25519PrivateKey.from_private_bytes(base64.b64decode(private_key.strip()))
    public = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    text = json.dumps(data, indent=2, sort_keys=True)
    return {"manifest": text, "key": key_id(public), "signature": base64.b64encode(private.sign(text.encode("utf-8"))).decode()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folder", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--channel", default="stable")
    parser.add_argument("--notes", default="")
    parser.add_argument("--version", default=VERSION)
    args = parser.parse_args(argv)
    private_key = os.environ.get("MIDIBAKERY_SIGNING_KEY")
    if not private_key:
        raise SystemExit("MIDIBAKERY_SIGNING_KEY is not set (the GitHub secret; see packaging/release/keygen.py)")
    data = manifest(args.folder, args.version, args.channel, args.notes)
    envelope = sign(data, private_key)
    args.out.write_text(json.dumps(envelope, indent=2) + "\n")
    print(f"signed {args.channel} manifest for {data['version']} with {envelope['key']}: {', '.join(data['files'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
