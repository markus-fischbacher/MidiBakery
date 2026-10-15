"""The Claude API key: from the environment, the macOS Keychain or an Anthropic profile.

The API that Live starts does not see the user's shell, so a key exported there
is not enough. `midibakery auth set-key` and the chat page store it in the
Keychain (service "MidiBakery"); on other systems in a file only the user can
read. An `ant auth login` profile works too: the Anthropic SDK finds it itself.
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


class FileStore:
    """Fallback outside macOS: a file in the config folder, readable by the user only."""

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


def store() -> KeychainStore | FileStore:
    return KeychainStore() if sys.platform == "darwin" else FileStore()


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
        source = "keychain" if sys.platform == "darwin" else "file"
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
