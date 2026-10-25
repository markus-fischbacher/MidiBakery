"""Updates: the signed manifest (packaging/release), the app's check and download, the API's endpoints, the
update service (services/updates, a Cloudflare Worker, tested with node --test)."""

import asyncio
import base64
import hashlib
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import httpx2 as httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from starlette.testclient import TestClient

from midibakery import __version__, updates
from midibakery.api.server import build_app
from midibakery.bridge import BridgeClient

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("make_manifest", ROOT / "packaging/release/make_manifest.py")
make_manifest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(make_manifest)

NEWER = ".".join(str(p + (1 if i == 1 else 0)) for i, p in enumerate(updates.parse_version(__version__)))
INSTALLER = b"pretend installer"


@pytest.fixture
def key(tmp_path, monkeypatch):
    """A fresh signing key the app trusts, and an empty config folder with the check switched on."""
    monkeypatch.setenv("MIDIBAKERY_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("MIDIBAKERY_NO_UPDATE_CHECK", raising=False)
    monkeypatch.setattr(updates, "platform_key", lambda: "macos-arm64")  # releases exist for macOS and Windows only
    private = Ed25519PrivateKey.generate()
    seed = private.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    public = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    monkeypatch.setattr(updates, "UPDATE_KEYS", {make_manifest.key_id(public): base64.b64encode(public).decode()})
    return base64.b64encode(seed).decode()


def release(tmp_path, key, version=NEWER, payload=INSTALLER) -> dict:
    folder = tmp_path / "release"
    folder.mkdir(exist_ok=True)
    (folder / f"MidiBakery-{version}-macos-arm64.pkg").write_bytes(payload)
    (folder / f"MidiBakery-{version}-macos-arm64.zip").write_bytes(b"not an installer")
    return make_manifest.sign(make_manifest.manifest(folder, version, "stable", "Faster chat."), key)


def service(envelope: dict, payload: bytes = INSTALLER, seen: list | None = None) -> httpx.AsyncClient:
    def answer(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        if request.url.path.endswith("/latest"):
            return httpx.Response(200, json=envelope)
        if "/download/" in request.url.path:
            return httpx.Response(200, content=payload)
        return httpx.Response(404)

    return httpx.AsyncClient(transport=httpx.MockTransport(answer))


def test_the_manifest_lists_installers_only_and_verifies(tmp_path, key):
    envelope = release(tmp_path, key)
    manifest = updates.verify(envelope)
    assert manifest["version"] == NEWER and manifest["notes"] == "Faster chat."
    assert list(manifest["files"]) == [updates.platform_key()]  # the zip is not an installer
    entry = manifest["files"][updates.platform_key()]
    assert entry["sha256"] == hashlib.sha256(INSTALLER).hexdigest() and entry["size"] == len(INSTALLER)


def test_a_changed_manifest_or_unknown_key_is_rejected(tmp_path, key):
    envelope = release(tmp_path, key)
    tampered = dict(envelope, manifest=envelope["manifest"].replace(hashlib.sha256(INSTALLER).hexdigest(), "0" * 64))
    with pytest.raises(updates.UpdateError, match="does not verify"):
        updates.verify(tampered)
    with pytest.raises(updates.UpdateError, match="unknown key"):
        updates.verify(dict(envelope, key="mb-other"))
    with pytest.raises(updates.UpdateError, match="malformed"):
        updates.verify({"manifest": envelope["manifest"]})
    other = Ed25519PrivateKey.generate().private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                                                       serialization.NoEncryption())
    forged = make_manifest.sign(json.loads(envelope["manifest"]), base64.b64encode(other).decode())
    with pytest.raises(updates.UpdateError):
        updates.verify(dict(forged, key=envelope["key"]))


def test_release_files_must_carry_the_release_version(tmp_path, key):
    folder = tmp_path / "release"
    folder.mkdir()
    (folder / "MidiBakery-9.9.9-macos-arm64.pkg").write_bytes(b"x")
    with pytest.raises(SystemExit, match="not version"):
        make_manifest.manifest(folder, NEWER, "stable", "")


def test_evaluate_needs_a_newer_version_with_an_installer_for_this_system(key):
    manifest = {"version": NEWER, "files": {"plan9-x64": {"name": "x", "size": 1, "sha256": "0"}}}
    assert not updates.evaluate(manifest).available
    manifest["files"][updates.platform_key()] = {"name": "y", "size": 1, "sha256": "0"}
    assert updates.evaluate(manifest).available
    assert not updates.evaluate(dict(manifest, version=__version__)).available
    assert updates.parse_version("0.10.0") > updates.parse_version("0.9.9")


def test_check_asks_once_a_day_without_identifying_the_user(tmp_path, key):
    seen: list = []
    client = service(release(tmp_path, key), seen=seen)
    update = asyncio.run(updates.check(client=client))
    assert update.available and update.version == NEWER
    assert asyncio.run(updates.check(client=client)).version == NEWER  # cached
    assert len(seen) == 1
    params = dict(seen[0].url.params)
    assert params == {"version": __version__, "os": updates.platform_key().split("-")[0],
                      "arch": updates.platform_key().split("-")[1], "channel": "stable"}
    assert "authorization" not in seen[0].headers
    asyncio.run(updates.check(force=True, client=client))
    assert len(seen) == 2


def test_the_check_can_be_switched_off(tmp_path, key, monkeypatch):
    updates.set_enabled(False)
    assert asyncio.run(updates.check()) is None
    updates.set_enabled(True)
    assert updates.enabled()
    monkeypatch.setattr(updates, "UPDATE_KEYS", {})
    assert not updates.enabled()  # nothing to trust a manifest by


def test_download_keeps_only_an_installer_matching_the_manifest(tmp_path, key):
    envelope = release(tmp_path, key)
    update = asyncio.run(updates.check(client=service(envelope)))
    path = asyncio.run(updates.download(update, client=service(envelope)))
    assert path.read_bytes() == INSTALLER and path.parent == updates.config_dir() / "downloads"

    path.unlink()
    with pytest.raises(updates.UpdateError, match="does not match"):
        asyncio.run(updates.download(update, client=service(envelope, payload=b"something else")))
    assert list((updates.config_dir() / "downloads").iterdir()) == []


def test_a_cached_update_is_no_news_once_installed(tmp_path, key, monkeypatch):
    asyncio.run(updates.check(client=service(release(tmp_path, key))))
    monkeypatch.setattr(updates, "__version__", NEWER)
    assert not asyncio.run(updates.check()).available


def test_api_reports_and_installs_an_update(bridge_env, monkeypatch, tmp_path):
    found = updates.Update(version=NEWER, available=True, notes="n",
                           file={"name": "MidiBakery.pkg", "size": 3, "sha256": "x"}, checked=1.0)
    opened = []

    async def check(force=False):
        return found

    async def download(update):
        return tmp_path / update.file["name"]

    monkeypatch.setattr(updates, "check", check)
    monkeypatch.setattr(updates, "download", download)
    monkeypatch.setattr(updates, "open_installer", opened.append)
    auth = {"Authorization": "Bearer t"}
    with TestClient(build_app(BridgeClient(), lambda options: None, "t")) as client:
        assert client.get("/update").status_code == 401
        status = client.get("/update?force=1", headers=auth).json()
        assert status["current"] == __version__ and status["update"] == {"version": NEWER, "notes": "n", "size": 3}
        assert client.get("/health", headers=auth).json()["update"]["version"] == NEWER
        result = client.post("/update/install", headers=auth).json()
        assert result == {"ok": True, "version": NEWER, "installer": "MidiBakery.pkg"}
        assert opened == [tmp_path / "MidiBakery.pkg"]


def test_api_without_an_update_installs_nothing(bridge_env):
    with TestClient(build_app(BridgeClient(), lambda options: None, "t")) as client:
        auth = {"Authorization": "Bearer t"}
        assert client.get("/update", headers=auth).json()["update"] is None
        assert client.post("/update/install", headers=auth).status_code == 409


@pytest.mark.skipif(shutil.which("node") is None, reason="no Node.js available")
def test_update_service_worker():
    result = subprocess.run(["node", "--test", "test/worker.test.js"], cwd=ROOT / "services/updates", capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
