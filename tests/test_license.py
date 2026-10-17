"""Licensing: tokens signed by the license service (services/updates/src/licenses.js), checked offline by the
app (midibakery.license); the gate in the MCP tools, the API and the chat; keys and license tools."""

import asyncio
import base64
import datetime
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import httpx2 as httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from mcp.server.mcpserver.exceptions import ToolError
from starlette.testclient import TestClient

from midibakery import license, updates
from midibakery.api.server import build_app
from midibakery.bridge import BridgeClient
from midibakery.agent.providers.base import Turn
from midibakery.mcp import build_server
from test_agent import ScriptedProvider

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"packaging/release/{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


keygen = _load("keygen")
issue_license = _load("issue_license")
MACHINE_RAW = "test-computer"


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


class Signer:
    """What the Worker does: sign a payload as <key id>.<payload>.<signature>."""

    def __init__(self):
        self.private = Ed25519PrivateKey.generate()
        public = self.private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.kid = keygen.key_id(public, "ml")
        self.keys = {self.kid: base64.b64encode(public).decode()}

    def token(self, **fields) -> str:
        payload = {"product": "midibakery", "machine": license.machine_id(), "issued": "2026-10-17"} | fields
        body = f"{self.kid}.{b64url(json.dumps(payload).encode())}"
        return f"{body}.{b64url(self.private.sign(body.encode()))}"


def days(n: int) -> str:
    return (datetime.datetime.now(datetime.timezone.utc).date() + datetime.timedelta(days=n)).isoformat()


@pytest.fixture
def signer(bridge_env, monkeypatch):
    monkeypatch.setenv("MIDIBAKERY_MACHINE_ID", MACHINE_RAW)
    s = Signer()
    monkeypatch.setattr(license, "LICENSE_KEYS", s.keys)
    return s


def service(answers: dict, seen: list | None = None) -> httpx.AsyncClient:
    def answer(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(json.loads(request.content))
        status, body = answers[request.url.path.rsplit("/", 1)[1]]
        return httpx.Response(status, json=body)

    return httpx.AsyncClient(transport=httpx.MockTransport(answer))


# ---------------------------------------------------------------------------- states


def test_without_keys_licensing_is_off_and_everything_allowed(bridge_env):
    assert license.LICENSE_KEYS == {}  # releases add the key once the service runs
    assert license.status().state == "off" and license.allowed()


def test_no_license_yet_blocks(signer):
    state = license.status()
    assert state.state == "none" and not state.allowed and "trial" in state.message


def test_trial_counts_down_and_ends(signer):
    license._store(token=signer.token(kind="trial", expires=days(12), updates_until=days(12)))
    state = license.status()
    assert (state.state, state.allowed, state.days_left, state.message) == ("trial", True, 12, "Trial: 12 days left")
    license._store(token=signer.token(kind="trial", expires=days(-1), updates_until=days(-1)))
    state = license.status()
    assert state.state == "expired" and not state.allowed


def test_a_license_shows_its_name_and_updates(signer):
    license._store(token=signer.token(kind="license", name="Ada", expires=None, updates_until="2027-10-17"), key="MB-AAAA-BBBB-CCCC-DDDD")
    state = license.status()
    assert (state.state, state.allowed, state.message, state.updates_until) == ("licensed", True, "Licensed to Ada", "2027-10-17")


def test_another_computers_token_or_a_forged_one_is_refused(signer, monkeypatch):
    license._store(token=signer.token(kind="license", name="Ada", updates_until="2027-10-17"))
    monkeypatch.setenv("MIDIBAKERY_MACHINE_ID", "another-computer")
    assert license.status().state == "invalid"
    monkeypatch.setenv("MIDIBAKERY_MACHINE_ID", MACHINE_RAW)

    token = signer.token(kind="trial", expires=days(1), updates_until=days(1))
    kid, _, signature = token.split(".")
    forged = f"{kid}.{b64url(json.dumps({'product': 'midibakery', 'kind': 'license', 'machine': license.machine_id()}).encode())}.{signature}"
    license._store(token=forged)
    assert license.status().state == "invalid"
    license._store(token=Signer().token(kind="license", updates_until="2099-01-01"))  # a key the app does not know
    assert license.status().state == "invalid"


def test_the_machine_id_is_a_hash(bridge_env, monkeypatch):
    monkeypatch.setenv("MIDIBAKERY_MACHINE_ID", "IOPlatformUUID-1234")
    hashed = license.machine_id()
    assert len(hashed) == 32 and "1234" not in hashed
    monkeypatch.delenv("MIDIBAKERY_MACHINE_ID")
    assert len(license.machine_id()) == 32  # the system's own id, or a stored random one


def test_the_stored_license_is_private(signer):
    license._store(token="x")
    assert (license.config_dir() / "license.json").stat().st_mode & 0o077 == 0


# ---------------------------------------------------------------------------- the service


def test_start_trial_and_activate(signer):
    seen: list = []
    trial = signer.token(kind="trial", expires=days(30), updates_until=days(30))
    state = asyncio.run(license.start_trial(service({"trial": (200, {"token": trial})}, seen)))
    assert state.state == "trial" and seen[0]["machine"] == license.machine_id()

    full = signer.token(kind="license", name="Ada", updates_until="2027-10-17")
    state = asyncio.run(license.activate(" mb-7kq2-9xwm-abcd-efgh ", service({"activate": (200, {"token": full})}, seen)))
    assert state.state == "licensed"
    assert seen[1]["key"] == "MB-7KQ2-9XWM-ABCD-EFGH"
    assert license.stored()["key"] == "MB-7KQ2-9XWM-ABCD-EFGH"


def test_service_errors_reach_the_user(signer):
    with pytest.raises(license.LicenseError, match="2 computers") as caught:
        asyncio.run(license.activate("MB-7KQ2-9XWM-ABCD-EFGH", service({"activate": (409, {"error": "SEATS_FULL", "message": "active on 2 computers"})})))
    assert caught.value.code == "SEATS_FULL"
    with pytest.raises(license.LicenseError, match="does not look like"):
        asyncio.run(license.activate("hello"))
    other = Signer().token(kind="trial", expires=days(30), updates_until=days(30))  # signed by someone else
    with pytest.raises(license.LicenseError):
        asyncio.run(license.start_trial(service({"trial": (200, {"token": other})})))
    assert license.status().state == "none"


def test_deactivate_frees_the_seat_and_forgets(signer):
    license._store(token=signer.token(kind="license", updates_until="2027-10-17"), key="MB-AAAA-BBBB-CCCC-DDDD")
    seen: list = []
    asyncio.run(license.deactivate(service({"deactivate": (200, {"ok": True})}, seen)))
    assert seen[0]["key"] == "MB-AAAA-BBBB-CCCC-DDDD" and license.status().state == "none"


def test_weekly_refresh_brings_renewals_and_revocations(signer):
    license._store(token=signer.token(kind="license", updates_until="2027-10-17"), key="MB-AAAA-BBBB-CCCC-DDDD", refreshed=days(-1))
    assert asyncio.run(license.refresh(service({}))) is None  # checked yesterday: not yet
    license._store(**license.stored() | {"refreshed": days(-8)})
    renewed = signer.token(kind="license", updates_until="2028-10-17")
    assert asyncio.run(license.refresh(service({"activate": (200, {"token": renewed})}))).updates_until == "2028-10-17"
    license._store(**license.stored() | {"refreshed": days(-8)})
    asyncio.run(license.refresh(service({"activate": (403, {"error": "REVOKED", "message": "no longer valid"})})))
    assert license.status().state == "none"
    license._store(token=renewed, key="MB-AAAA-BBBB-CCCC-DDDD", refreshed=days(-8))
    asyncio.run(license.refresh(service({"activate": (503, {"error": "LICENSING_OFF"})})))  # outage: keeps working
    assert license.status().state == "licensed"


# ---------------------------------------------------------------------------- the gate


async def test_mcp_tools_need_a_license_but_reading_and_undo_do_not(signer, client, live):
    server = build_server(client)
    with pytest.raises(ToolError, match="LICENSE_REQUIRED"):
        await server.call_tool("create_clip", {"track": 1, "slot": 0, "length": 4})
    await server.call_tool("get_session", {})
    with pytest.raises(ToolError, match="Nothing to undo"):  # reached Live: undo needs no license
        await server.call_tool("undo", {"action": "undo"})
    license._store(token=signer.token(kind="trial", expires=days(3), updates_until=days(3)))
    await server.call_tool("create_clip", {"track": 1, "slot": 0, "length": 4})


def test_api_license_endpoints_and_gate(signer, monkeypatch):
    auth = {"Authorization": "Bearer t"}

    async def start_trial():
        license._store(token=signer.token(kind="trial", expires=days(30), updates_until=days(30)))

    monkeypatch.setattr(license, "start_trial", start_trial)
    provider = ScriptedProvider([Turn("end_turn", text="never asked")])
    with TestClient(build_app(BridgeClient(), lambda options: provider, "t")) as client:
        assert client.get("/license", headers=auth).json()["state"] == "none"
        assert client.get("/health", headers=auth).json()["license"]["state"] == "none"
        body = {"length": 4, "kind": "drums"}
        response = client.post("/miditool/generate", json=body, headers=auth)
        assert response.status_code == 402 and response.json()["error"] == "LICENSE_REQUIRED"
        with client.websocket_connect("/chat?token=t") as ws:
            ws.receive_json()  # ready
            ws.send_json({"type": "user", "text": "make a beat"})
            event = ws.receive_json()
            while event["type"] != "error":
                event = ws.receive_json()
            assert event["code"] == "LICENSE_REQUIRED"
        state = client.post("/license/trial", headers=auth).json()
        assert state["state"] == "trial" and state["allowed"] and state["purchase_url"]
        bad = client.post("/license/activate", json={"key": "nope"}, headers=auth)
        assert bad.status_code == 422 and bad.json()["error"] == "INVALID_KEY"


def test_updates_outside_the_license_are_not_installed(signer):
    license._store(token=signer.token(kind="license", updates_until="2027-01-01"))
    newer = updates.evaluate({"version": "99.0.0", "released": "2027-02-01T00:00:00Z",
                              "files": {updates.platform_key(): {"name": "x.pkg", "size": 1, "sha256": "0"}}})
    assert newer.available and not newer.included
    with pytest.raises(updates.UpdateError, match="not included"):
        asyncio.run(updates.download(newer))
    assert updates.evaluate({"version": "99.0.0", "released": "2026-12-01T00:00:00Z", "files": {}}).included
    assert updates._headers()["Authorization"].startswith("License ")


# ---------------------------------------------------------------------------- tools


def test_issued_keys_match_the_apps_format_and_hash():
    key = issue_license.new_key()
    assert license.normalize_key(key.lower()) == key
    assert issue_license.key_hash(key) == issue_license.key_hash(f" {key.lower()} ")
    sql = issue_license.issue_sql(key, "O'Brien", "", 2, 12, "")
    assert "'O''Brien'" in sql and key not in sql  # only the hash goes into the database
    assert issue_license.add_months(datetime.date(2026, 1, 31), 1) == datetime.date(2026, 2, 28)


@pytest.mark.skipif(shutil.which("node") is None, reason="no Node.js available")
def test_the_workers_tokens_verify_in_the_app(signer, tmp_path, monkeypatch):
    """keygen.py --license -> Worker secret; the Worker's signer (WebCrypto) -> a token the app accepts."""
    key_file = tmp_path / "license.key"
    assert keygen.main(["--license", str(key_file)]) == 0
    secret = key_file.read_text().strip()
    kid, pkcs8 = secret.split(":")
    private = serialization.load_der_private_key(base64.b64decode(pkcs8), None)
    public = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    monkeypatch.setattr(license, "LICENSE_KEYS", {kid: base64.b64encode(public).decode()})
    script = tmp_path / "sign.mjs"
    script.write_text(f"""
import {{ signer }} from {json.dumps((ROOT / "services/updates/src/tokens.js").as_uri())};
const s = await signer(process.argv[2]);
console.log(await s.sign({{ product: "midibakery", kind: "license", name: "Ada", machine: process.argv[3],
  issued: "2026-10-17", expires: null, updates_until: "2027-10-17" }}));
""")
    result = subprocess.run(["node", str(script), secret, license.machine_id()], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    license._store(token=result.stdout.strip())
    assert license.status().message == "Licensed to Ada"
