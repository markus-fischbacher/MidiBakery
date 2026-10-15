"""Claude's API key: Keychain/file storage, where it comes from, and the chat's key flow."""

import stat
import subprocess

import pytest
from starlette.testclient import TestClient

from midibakery import credentials
from midibakery.agent.providers.anthropic import AnthropicProvider
from midibakery.api.server import build_app
from midibakery.bridge import BridgeClient

KEY = "sk-ant-api03-" + "a" * 40
TOKEN = "t" * 32
AUTH = {"Authorization": f"Bearer {TOKEN}"}


class MemoryStore:
    def __init__(self):
        self.key = None

    def load(self):
        return self.key

    def save(self, key):
        if not credentials.valid_format(key):
            raise credentials.InvalidKey("bad")
        self.key = key

    def delete(self):
        self.key = None


@pytest.fixture
def memory(monkeypatch):
    store = MemoryStore()
    monkeypatch.delenv(credentials.ENV_KEY, raising=False)
    monkeypatch.setattr(credentials, "store", lambda: store)
    monkeypatch.setattr(credentials, "_has_profile", lambda: False)
    return store


def test_keychain_gets_the_key_over_stdin_never_argv():
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs.get("input")))
        return subprocess.CompletedProcess(argv, 0, stdout=KEY + "\n" if "find-generic-password" in argv else "", stderr="")

    store = credentials.KeychainStore(run)
    store.save(KEY)
    assert all(KEY not in " ".join(argv) for argv, _ in calls)
    assert KEY in calls[0][1] and "-s MidiBakery -a anthropic-api-key" in calls[0][1]
    assert store.load() == KEY


def test_malformed_keys_never_reach_the_keychain():
    def run(argv, **kwargs):
        raise AssertionError("security must not run")

    with pytest.raises(credentials.InvalidKey):
        credentials.KeychainStore(run).save('sk-ant" ; delete-keychain')


def test_file_store_is_private(tmp_path):
    store = credentials.FileStore(tmp_path / "key")
    store.save(KEY)
    assert store.load() == KEY
    assert stat.S_IMODE((tmp_path / "key").stat().st_mode) == 0o600
    store.delete()
    assert store.load() is None


def test_status_names_the_source_not_the_key(memory, monkeypatch):
    assert credentials.status() == {"configured": False, "source": None}
    memory.key = KEY
    assert credentials.status()["source"] in ("keychain", "file")
    monkeypatch.setenv(credentials.ENV_KEY, KEY)
    assert credentials.status() == {"configured": True, "source": "env"}
    assert KEY not in str(credentials.status())


def test_provider_uses_the_stored_key(memory):
    memory.key = KEY
    assert AnthropicProvider()._client.api_key == KEY


def test_provider_without_any_key_says_so(memory):
    with pytest.raises(credentials.MissingKey):
        AnthropicProvider()


@pytest.fixture
def api(memory, bridge_env, monkeypatch):
    async def verify(key):
        if key.endswith("bad"):
            raise credentials.InvalidKey("The Claude API rejected this key")

    monkeypatch.setattr(credentials, "verify", verify)

    def factory(options):
        return AnthropicProvider()

    return TestClient(build_app(BridgeClient(), factory, TOKEN))


def test_key_endpoint_stores_checks_and_removes(api, memory):
    assert api.get("/auth/anthropic").status_code == 401
    assert api.get("/auth/anthropic", headers=AUTH).json() == {"configured": False, "source": None}

    rejected = api.put("/auth/anthropic", headers=AUTH, json={"api_key": KEY[:-3] + "bad"})
    assert rejected.status_code == 422 and memory.key is None
    assert api.put("/auth/anthropic", headers=AUTH, json={"api_key": "not a key"}).status_code == 422

    stored = api.put("/auth/anthropic", headers=AUTH, json={"api_key": KEY})
    assert stored.status_code == 200 and stored.json()["configured"]
    assert KEY not in stored.text and memory.key == KEY

    assert api.delete("/auth/anthropic", headers=AUTH).json()["configured"] is False


def test_chat_without_key_asks_for_one_instead_of_reconnecting(api):
    with api.websocket_connect(f"/chat?token={TOKEN}&provider=anthropic") as ws:
        event = ws.receive_json()
    assert event["type"] == "error" and event["code"] == "NO_API_KEY"


def test_chat_page_offers_key_entry_in_browser_and_device(api):
    page = api.get("/ui").text
    assert 'id="keyInput" type="password"' in page
    assert "if (keyMode) { keyMode = false; saveKey(raw); return true; }" in page
