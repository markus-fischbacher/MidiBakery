"""Updates: asks MidiBakery's update service (updates.klirrwerk.com, services/updates) once a day whether a
newer version exists, and on request downloads its installer and opens it.

The service hands out a manifest signed with Ed25519 (packaging/release/make_manifest.py signs it in CI);
only a manifest whose signature one of UPDATE_KEYS verifies counts, and an installer only runs when its
SHA-256 is the manifest's. HTTPS alone would trust whoever controls the domain or the storage.

The request carries the version, system, architecture and channel, nothing that identifies the user.
`midibakery update --disable` turns the daily check off (settings.json in the config folder).
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from midibakery import __version__
from midibakery.bridge.client import config_dir

SERVICE = os.environ.get("MIDIBAKERY_UPDATE_URL", "https://updates.klirrwerk.com/v1/midibakery")
CHANNEL = "stable"
CHECK_EVERY = 24 * 3600
TIMEOUT = 10.0
DOWNLOAD_TIMEOUT = 300.0

# Public keys that sign the update manifests, by key id: base64 of the raw 32-byte Ed25519 key.
# packaging/release/keygen.py makes a key pair; its public half goes here, the private half only into
# the CI secret MIDIBAKERY_SIGNING_KEY. Without a key here the check stays off.
UPDATE_KEYS: dict[str, str] = {
    "mb-4977c1a77ff7": "s98KLeZmV3//hmsGgTDLNFjkitC5dPUWCZUS3vS3fnA=",
}


class UpdateError(Exception):
    """The service could not be asked, or what it answered cannot be trusted."""


@dataclass
class Update:
    version: str  # the newest version on the channel
    available: bool  # newer than this one, with an installer for this system
    notes: str = ""
    file: dict | None = None  # {"name", "size", "sha256"} of this system's installer
    checked: float = 0.0  # time.time() of the check
    released: str = ""  # ISO time of the release

    @property
    def url(self) -> str | None:
        return f"{SERVICE}/download/{self.version}/{self.file['name']}" if self.file else None


def platform_key() -> str:
    """The manifest's name for this system: macos-arm64, macos-x64 or windows-x64."""
    system = {"darwin": "macos", "win32": "windows"}.get(sys.platform, sys.platform)
    machine = platform.machine().lower()
    return f"{system}-{ {'x86_64': 'x64', 'amd64': 'x64', 'aarch64': 'arm64'}.get(machine, machine) }"


def parse_version(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in text.split("."))


# ---------------------------------------------------------------------------- settings


def _settings_path() -> Path:
    return config_dir() / "settings.json"


def settings() -> dict:
    try:
        return json.loads(_settings_path().read_text())
    except (OSError, ValueError):
        return {}


def set_enabled(enabled: bool) -> None:
    current = settings()
    current["update_check"] = enabled
    _settings_path().parent.mkdir(parents=True, exist_ok=True)
    _settings_path().write_text(json.dumps(current, indent=2) + "\n")


def enabled() -> bool:
    """On unless switched off (settings, MIDIBAKERY_NO_UPDATE_CHECK) or no key to trust manifests by."""
    return bool(UPDATE_KEYS) and not os.environ.get("MIDIBAKERY_NO_UPDATE_CHECK") and settings().get("update_check", True)


# ---------------------------------------------------------------------------- the manifest


def verify(envelope: dict, keys: dict[str, str] | None = None) -> dict:
    """The manifest inside a signed envelope {"manifest": <JSON text>, "key": <id>, "signature": <base64>}.
    Raises UpdateError unless a known key signed exactly that text."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    keys = UPDATE_KEYS if keys is None else keys
    try:
        text, key_id, signature = envelope["manifest"], envelope["key"], base64.b64decode(envelope["signature"], validate=True)
    except (KeyError, TypeError, ValueError) as exc:
        raise UpdateError(f"malformed update answer ({exc})") from exc
    if key_id not in keys:
        raise UpdateError(f"update manifest signed with an unknown key {key_id!r}")
    try:
        Ed25519PublicKey.from_public_bytes(base64.b64decode(keys[key_id])).verify(signature, text.encode("utf-8"))
    except (InvalidSignature, ValueError) as exc:
        raise UpdateError("update manifest signature does not verify") from exc
    manifest = json.loads(text)
    if manifest.get("product") != "midibakery":
        raise UpdateError("update manifest is not MidiBakery's")
    return manifest


def evaluate(manifest: dict, current: str = __version__, system: str | None = None) -> Update:
    system = system or platform_key()
    file = manifest.get("files", {}).get(system)
    newer = parse_version(manifest["version"]) > parse_version(current)
    return Update(version=manifest["version"], available=newer and file is not None, notes=manifest.get("notes", ""),
                  file=file, checked=time.time(), released=manifest.get("released", ""))


# ---------------------------------------------------------------------------- asking the service


def _headers() -> dict[str, str]:
    return {"User-Agent": f"MidiBakery/{__version__}"}


async def fetch(client=None) -> Update:
    """Asks the service now; raises UpdateError."""
    import httpx2 as httpx

    params = {"version": __version__, "os": platform_key().split("-")[0], "arch": platform_key().split("-")[1], "channel": CHANNEL}
    own = client is None
    client = client or httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True)
    try:
        response = await client.get(f"{SERVICE}/latest", params=params, headers=_headers())
        if response.status_code != 200:
            raise UpdateError(f"update service answered {response.status_code}")
        envelope = response.json()
    except httpx.HTTPError as exc:
        raise UpdateError(f"update service unreachable ({exc.__class__.__name__})") from exc
    except ValueError as exc:
        raise UpdateError("update service answered no JSON") from exc
    finally:
        if own:
            await client.aclose()
    return evaluate(verify(envelope))


def _cache_path() -> Path:
    return config_dir() / "update.json"


def cached() -> Update | None:
    try:
        return Update(**json.loads(_cache_path().read_text()))
    except (OSError, ValueError, TypeError):
        return None


def _store(update: Update) -> None:
    _cache_path().parent.mkdir(parents=True, exist_ok=True)
    _cache_path().write_text(json.dumps(asdict(update), indent=1) + "\n")


async def check(*, force: bool = False, client=None) -> Update | None:
    """The last day's answer, or a fresh one; None when the check is off. A failed check returns the
    cached answer (or None) and is tried again on the next call."""
    if not enabled() and not force:
        return None
    last = cached()
    if last is not None and not force and time.time() - last.checked < CHECK_EVERY:
        return evaluate_cached(last)
    update = await fetch(client)
    _store(update)
    return update


def evaluate_cached(update: Update) -> Update:
    """A cached answer after this version changed (an update installed meanwhile) is no longer news."""
    if update.available and parse_version(update.version) <= parse_version(__version__):
        update.available = False
    return update


# ---------------------------------------------------------------------------- installing


async def download(update: Update, client=None) -> Path:
    """The installer in the config folder's downloads/, checked against the manifest's SHA-256."""
    import httpx2 as httpx

    if not update.available or not update.file:
        raise UpdateError("no update to download")
    target = config_dir() / "downloads" / Path(update.file["name"]).name
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".part")
    digest = hashlib.sha256()
    own = client is None
    client = client or httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT, follow_redirects=True)
    try:
        async with client.stream("GET", update.url, headers=_headers()) as response:
            if response.status_code != 200:
                raise UpdateError(f"download answered {response.status_code}")
            with open(partial, "wb") as fh:
                async for chunk in response.aiter_bytes():
                    digest.update(chunk)
                    fh.write(chunk)
    except httpx.HTTPError as exc:
        partial.unlink(missing_ok=True)
        raise UpdateError(f"download failed ({exc.__class__.__name__})") from exc
    finally:
        if own:
            await client.aclose()
    if digest.hexdigest() != update.file["sha256"]:
        partial.unlink(missing_ok=True)
        raise UpdateError("the downloaded installer does not match the manifest; it was deleted")
    os.replace(partial, target)
    return target


def open_installer(path: Path) -> None:
    """Hands the installer to the system: the macOS Installer app or the Windows setup, which the user runs."""
    if sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    elif sys.platform == "win32":
        os.startfile(str(path))  # noqa: S606 - the verified setup the user asked for
    else:
        raise UpdateError("installers exist for macOS and Windows only")
