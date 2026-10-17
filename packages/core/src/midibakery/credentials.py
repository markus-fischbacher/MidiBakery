"""The Claude API key: from the environment, the system's credential store or an Anthropic profile.

The API that Live starts does not see the user's shell, so a key exported there
is not enough. `midibakery auth set-key` and the chat page store it in the macOS
Keychain (service "MidiBakery") or the Windows Credential Manager (target
"MidiBakery/anthropic-api-key"); elsewhere in a file only the user can read.
An `ant auth login` profile works too: the Anthropic SDK finds it itself.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

SERVICE = "MidiBakery"
ACCOUNT = "anthropic-api-key"
ENV_KEY = "ANTHROPIC_API_KEY"
# Anthropic keys are URL-safe; anything else is a paste error (and could not be quoted safely for `security -i`).
KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{20,400}$")
SECURITY = "/usr/bin/security"


class MissingKey(ValueError):
    """No Claude credentials anywhere: environment, Keychain or profile."""


class InvalidKey(ValueError):
    """The key is malformed or was rejected by the Claude API."""


def valid_format(key: str) -> bool:
    return bool(KEY_PATTERN.match(key))


class KeychainStore:
    """macOS Keychain through /usr/bin/security; the key goes over stdin, never argv."""

    def __init__(self, run=subprocess.run):
        self._run = run

    def load(self) -> str | None:
        result = self._run([SECURITY, "find-generic-password", "-s", SERVICE, "-a", ACCOUNT, "-w"], capture_output=True, text=True)
        key = result.stdout.strip() if result.returncode == 0 else ""
        return key or None

    def save(self, key: str) -> None:
        if not valid_format(key):
            raise InvalidKey("That does not look like a Claude API key")
        command = f'add-generic-password -U -s {SERVICE} -a {ACCOUNT} -l "MidiBakery Claude API key" -w "{key}"\n'
        result = self._run([SECURITY, "-i"], input=command, capture_output=True, text=True)
        if result.returncode != 0 or result.stderr.strip():
            raise OSError(f"Keychain refused the key: {result.stderr.strip() or result.returncode}")

    def delete(self) -> None:
        self._run([SECURITY, "delete-generic-password", "-s", SERVICE, "-a", ACCOUNT], capture_output=True, text=True)


class CredentialManagerStore:
    """Windows Credential Manager (a generic credential of the current user), through advapi32."""

    TARGET = f"{SERVICE}/{ACCOUNT}"
    CRED_TYPE_GENERIC = 1
    CRED_PERSIST_LOCAL_MACHINE = 2  # this user, kept across logons, not roamed
    ERROR_NOT_FOUND = 1168

    def __init__(self):
        import ctypes
        from ctypes import wintypes

        class CREDENTIAL(ctypes.Structure):
            _fields_ = [
                ("Flags", wintypes.DWORD),
                ("Type", wintypes.DWORD),
                ("TargetName", wintypes.LPWSTR),
                ("Comment", wintypes.LPWSTR),
                ("LastWritten", wintypes.FILETIME),
                ("CredentialBlobSize", wintypes.DWORD),
                ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
                ("Persist", wintypes.DWORD),
                ("AttributeCount", wintypes.DWORD),
                ("Attributes", ctypes.c_void_p),
                ("TargetAlias", wintypes.LPWSTR),
                ("UserName", wintypes.LPWSTR),
            ]

        self._ctypes = ctypes
        self._credential = CREDENTIAL
        advapi = ctypes.WinDLL("advapi32", use_last_error=True)
        self._read = advapi.CredReadW
        self._read.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.POINTER(CREDENTIAL))]
        self._read.restype = wintypes.BOOL
        self._write = advapi.CredWriteW
        self._write.argtypes = [ctypes.POINTER(CREDENTIAL), wintypes.DWORD]
        self._write.restype = wintypes.BOOL
        self._delete = advapi.CredDeleteW
        self._delete.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        self._delete.restype = wintypes.BOOL
        self._free = advapi.CredFree
        self._free.argtypes = [ctypes.c_void_p]
        self._free.restype = None

    def load(self) -> str | None:
        ctypes = self._ctypes
        found = ctypes.POINTER(self._credential)()
        if not self._read(self.TARGET, self.CRED_TYPE_GENERIC, 0, ctypes.byref(found)):
            return None
        try:
            blob = ctypes.string_at(found.contents.CredentialBlob, found.contents.CredentialBlobSize)
        finally:
            self._free(found)
        return blob.decode("utf-8").strip() or None

    def save(self, key: str) -> None:
        if not valid_format(key):
            raise InvalidKey("That does not look like a Claude API key")
        ctypes = self._ctypes
        data = key.encode("utf-8")
        blob = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
        credential = self._credential()
        credential.Type = self.CRED_TYPE_GENERIC
        credential.TargetName = self.TARGET
        credential.Comment = "MidiBakery Claude API key"
        credential.CredentialBlobSize = len(data)
        credential.CredentialBlob = ctypes.cast(blob, ctypes.POINTER(ctypes.c_ubyte))
        credential.Persist = self.CRED_PERSIST_LOCAL_MACHINE
        credential.UserName = ACCOUNT
        if not self._write(ctypes.byref(credential), 0):
            raise OSError(f"Credential Manager refused the key (error {ctypes.get_last_error()})")

    def delete(self) -> None:
        if not self._delete(self.TARGET, self.CRED_TYPE_GENERIC, 0):
            error = self._ctypes.get_last_error()
            if error != self.ERROR_NOT_FOUND:
                raise OSError(f"Credential Manager could not remove the key (error {error})")


class FileStore:
    """Fallback outside macOS and Windows: a file in the config folder, readable by the user only."""

    def __init__(self, path: Path | None = None):
        if path is None:
            from midibakery.bridge.client import config_dir

            path = config_dir() / "anthropic-api-key"
        self.path = path

    def load(self) -> str | None:
        try:
            return self.path.read_text().strip() or None
        except OSError:
            return None

    def save(self, key: str) -> None:
        if not valid_format(key):
            raise InvalidKey("That does not look like a Claude API key")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as fh:
            fh.write(key)

    def delete(self) -> None:
        self.path.unlink(missing_ok=True)


def store() -> KeychainStore | CredentialManagerStore | FileStore:
    if sys.platform == "darwin":
        return KeychainStore()
    if sys.platform == "win32":
        return CredentialManagerStore()
    return FileStore()


def store_name() -> str:
    """How status() names the store: keychain, credential_manager or file."""
    return {"darwin": "keychain", "win32": "credential_manager"}.get(sys.platform, "file")


def _has_profile() -> bool:
    try:
        from anthropic.lib.credentials import default_credentials

        return default_credentials() is not None
    except Exception:
        return False


def anthropic_key() -> str | None:
    """The key to pass to the SDK, or None to let it look for a profile."""
    return os.environ.get(ENV_KEY) or store().load()


def status() -> dict[str, object]:
    """Where Claude's credentials come from; never the key itself."""
    if os.environ.get(ENV_KEY):
        source = "env"
    elif store().load():
        source = store_name()
    elif _has_profile():
        source = "profile"
    else:
        source = None
    return {"configured": source is not None, "source": source}


async def verify(key: str) -> None:
    """Raises InvalidKey if the Claude API rejects the key. Network trouble is not the key's fault."""
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=key, max_retries=0, timeout=10)
    try:
        await client.models.list(limit=1)
    except anthropic.AuthenticationError as exc:
        raise InvalidKey("The Claude API rejected this key") from exc
    except anthropic.APIConnectionError:
        pass
    finally:
        await client.close()
