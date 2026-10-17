"""Licensing: a 30-day trial, then a license key. Both end up as a token the license service
(services/updates, /v1/midibakery/license/...) signs with Ed25519 and the app checks offline.

    token = <key id>.<base64url payload JSON>.<base64url signature over "<key id>.<payload>">

The payload names the kind ("trial" or "license"), the computer it was issued for (a hash, see
machine_id), when it expires (trials only) and until when updates are included. Without a key in
LICENSE_KEYS licensing is off and everything is allowed: development builds, and releases until the
service runs.

This cannot stop someone who edits the code; it keeps honest users honest without getting in a paying
user's way: after the first contact the app needs no connection, and nothing in a Set is ever touched
when a trial ends. Only new generations and edits stop; undo keeps working.
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from midibakery import __version__
from midibakery.bridge.client import config_dir

TIMEOUT = 15.0
REFRESH_EVERY = 7 * 24 * 3600  # renewals (a later updates_until) reach the app within a week
PURCHASE_URL = "https://klirrwerk.com/midibakery"

# Public keys that sign license tokens, by key id: base64 of the raw 32-byte Ed25519 key.
# packaging/release/keygen.py --license makes the pair; the private half is only the Worker's secret.
LICENSE_KEYS: dict[str, str] = {}

KEY_FORMAT = re.compile(r"^MB(-[0-9A-Z]{4}){4}$")  # what the service issues, e.g. MB-7KQ2-9XWM-…


class LicenseError(Exception):
    """The service refused, could not be reached, or answered something that does not verify."""

    def __init__(self, message: str, code: str = "LICENSE_ERROR"):
        super().__init__(message)
        self.code = code


@dataclass
class Status:
    state: str  # off | none | trial | licensed | expired | invalid
    allowed: bool  # may generate and edit
    message: str
    name: str = ""  # licensee
    expires: str | None = None  # trial end (ISO date)
    days_left: int | None = None
    updates_until: str | None = None

    def as_dict(self) -> dict:
        return asdict(self) | {"purchase_url": PURCHASE_URL}


# ---------------------------------------------------------------------------- this computer


def _raw_machine_id() -> str | None:
    try:
        if sys.platform == "darwin":
            out = subprocess.run(["/usr/sbin/ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                                 capture_output=True, text=True, timeout=5).stdout
            match = re.search(r'"IOPlatformUUID" = "([^"]+)"', out)
            return match[1] if match else None
        if sys.platform == "win32":
            import winreg

            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0,
                                winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
                return str(winreg.QueryValueEx(key, "MachineGuid")[0])
        return Path("/etc/machine-id").read_text().strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def machine_id() -> str:
    """This computer, as the service sees it: a salted hash of the system's own id (nothing personal).
    Falls back to a random id kept in the config folder."""
    raw = os.environ.get("MIDIBAKERY_MACHINE_ID") or _raw_machine_id()
    if not raw:
        path = config_dir() / "machine-id"
        try:
            raw = path.read_text().strip()
        except OSError:
            raw = ""
        if not raw:
            raw = uuid.uuid4().hex
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(raw + "\n")
    return hashlib.sha256(f"midibakery:{raw}".encode()).hexdigest()[:32]


# ---------------------------------------------------------------------------- tokens


def _b64decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def verify(token: str, keys: dict[str, str] | None = None) -> dict:
    """The payload of a token a known key signed; raises LicenseError."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    keys = LICENSE_KEYS if keys is None else keys
    try:
        key_id, payload, signature = token.strip().split(".")
        data = json.loads(_b64decode(payload))
        signature_bytes = _b64decode(signature)
    except ValueError as exc:
        raise LicenseError("malformed license token", "INVALID") from exc
    if key_id not in keys:
        raise LicenseError(f"license token signed with an unknown key {key_id!r}", "INVALID")
    try:
        Ed25519PublicKey.from_public_bytes(base64.b64decode(keys[key_id])).verify(signature_bytes, f"{key_id}.{payload}".encode())
    except (InvalidSignature, ValueError) as exc:
        raise LicenseError("license token signature does not verify", "INVALID") from exc
    if not isinstance(data, dict) or data.get("product") != "midibakery" or data.get("kind") not in ("trial", "license"):
        raise LicenseError("not a MidiBakery license token", "INVALID")
    return data


def _today() -> datetime.date:
    return datetime.datetime.now(datetime.timezone.utc).date()


def evaluate(data: dict, machine: str | None = None) -> Status:
    machine = machine or machine_id()
    updates_until = data.get("updates_until")
    if data.get("machine") != machine:
        return Status("invalid", False, "This license was activated on another computer. Activate it here.",
                      updates_until=updates_until)
    if data["kind"] == "trial":
        expires = datetime.date.fromisoformat(data["expires"])
        left = (expires - _today()).days
        if left < 0:
            return Status("expired", False, f"The trial ended on {expires}. Enter a license key to keep going.",
                          expires=str(expires), days_left=0)
        return Status("trial", True, f"Trial: {left} day{'s' if left != 1 else ''} left", expires=str(expires),
                      days_left=left, updates_until=updates_until)
    name = data.get("name") or ""
    return Status("licensed", True, f"Licensed to {name}" if name else "Licensed", name=name, updates_until=updates_until)


# ---------------------------------------------------------------------------- stored state


def _path() -> Path:
    return config_dir() / "license.json"


def stored() -> dict:
    try:
        data = json.loads(_path().read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _store(**fields) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        json.dump(fields, fh, indent=2)
    os.replace(tmp, path)


def enabled() -> bool:
    return bool(LICENSE_KEYS)


def status() -> Status:
    if not enabled():
        return Status("off", True, "")
    token = stored().get("token")
    if not token:
        return Status("none", False, "Start the free 30-day trial or enter a license key.")
    try:
        return evaluate(verify(token))
    except LicenseError as exc:
        return Status("invalid", False, f"The stored license is not valid ({exc}). Enter your license key again.")
    except (KeyError, ValueError):
        return Status("invalid", False, "The stored license is not valid. Enter your license key again.")


def allowed() -> bool:
    return status().allowed


def require() -> None:
    """Raises LicenseError (code LICENSE_REQUIRED) unless generating and editing are allowed."""
    current = status()
    if not current.allowed:
        raise LicenseError(current.message, "LICENSE_REQUIRED")


def updates_header() -> dict[str, str]:
    """For the update service: the token shows which updates this install may download."""
    token = stored().get("token")
    return {"Authorization": f"License {token}"} if enabled() and token else {}


# ---------------------------------------------------------------------------- the service


async def _post(path: str, body: dict, client=None) -> dict:
    import httpx2 as httpx

    from midibakery.updates import SERVICE

    own = client is None
    client = client or httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True)
    try:
        response = await client.post(f"{SERVICE}/license/{path}", json=body | {"version": __version__},
                                     headers={"User-Agent": f"MidiBakery/{__version__}"})
        try:
            data = response.json()
        except ValueError:
            data = {}
    except httpx.HTTPError as exc:
        raise LicenseError(f"the license service is unreachable ({exc.__class__.__name__}); check the internet connection",
                           "UNREACHABLE") from exc
    finally:
        if own:
            await client.aclose()
    if response.status_code != 200:
        raise LicenseError(data.get("message") or f"the license service answered {response.status_code}",
                           data.get("error") or "LICENSE_ERROR")
    return data


async def _accept(data: dict, key: str | None) -> Status:
    token = data.get("token", "")
    payload = verify(token)
    result = evaluate(payload)
    if result.state == "invalid":
        raise LicenseError("the service issued a token for another computer", "INVALID")
    _store(token=token, **({"key": key} if key else {}), refreshed=_today().isoformat())
    return result


async def start_trial(client=None) -> Status:
    """One trial per computer; asking again returns the same trial."""
    return await _accept(await _post("trial", {"machine": machine_id()}, client), None)


def normalize_key(key: str) -> str:
    key = re.sub(r"[\s_]", "", key).upper()
    if not KEY_FORMAT.match(key):
        raise LicenseError("That does not look like a MidiBakery license key (MB-XXXX-XXXX-XXXX-XXXX).", "INVALID_KEY")
    return key


async def activate(key: str, client=None) -> Status:
    """Activates this computer; a license covers a few computers (the service says when all are taken)."""
    key = normalize_key(key)
    return await _accept(await _post("activate", {"key": key, "machine": machine_id()}, client), key)


async def deactivate(client=None) -> None:
    """Frees this computer's seat and forgets the license here."""
    key = stored().get("key")
    if key:
        await _post("deactivate", {"key": key, "machine": machine_id()}, client)
    _path().unlink(missing_ok=True)


async def refresh(client=None) -> Status | None:
    """Now and then: a renewal or a revocation reaches the app. Errors leave the stored token as it is."""
    data = stored()
    key = data.get("key")
    if not enabled() or not key:
        return None
    try:
        last = datetime.date.fromisoformat(data.get("refreshed", "1970-01-01"))
    except ValueError:
        last = datetime.date(1970, 1, 1)
    if (_today() - last).days * 86400 < REFRESH_EVERY:
        return None
    try:
        return await _accept(await _post("activate", {"key": key, "machine": machine_id()}, client), key)
    except LicenseError as exc:
        if exc.code in ("REVOKED", "UNKNOWN_KEY"):
            _path().unlink(missing_ok=True)
        return None
