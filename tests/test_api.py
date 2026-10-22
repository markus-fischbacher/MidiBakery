"""Local API for the Max for Live devices: auth, chat WebSocket."""

import json
import stat

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from midibakery import __version__, credentials
from midibakery.agent.providers.base import ToolCall, Turn
from midibakery.api.server import api_info_path, build_app, write_api_info
from midibakery.bridge import BridgeClient
from test_agent import ScriptedProvider

TOKEN = "test-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
A_MINOR = {"root": 9, "intervals": [0, 2, 3, 5, 7, 8, 10], "name": "Minor"}


@pytest.fixture
def app_factory(bridge_env):
    def make(provider=None):
        providers = []

        def factory(options):
            p = provider or ScriptedProvider([Turn("end_turn", text="hi")])
            providers.append((options, p))
            return p

        return TestClient(build_app(BridgeClient(), factory, TOKEN)), providers

    return make


def test_requests_need_the_token(app_factory):
    api, _ = app_factory()
    assert api.get("/health").status_code == 401
    assert api.get("/health", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert api.get("/import/library").status_code == 401
    with pytest.raises(WebSocketDisconnect) as exc:
        with api.websocket_connect("/chat?token=wrong") as ws:
            ws.receive_json()
    assert exc.value.code == 4401


def test_discovery_file_is_private(bridge_env):
    path = write_api_info(8766, TOKEN)
    assert path == api_info_path()
    assert json.loads(path.read_text()) == {"port": 8766, "token": TOKEN, "version": __version__}
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_health_reports_live(app_factory, live):
    api, _ = app_factory()
    body = api.get("/health", headers=AUTH).json()
    assert body["ok"] is True and body["live"]["live"] == [12, 4, 6]


# --------------------------------------------------------------------------
# MIDI tools
# --------------------------------------------------------------------------


def _until(ws, kind):
    events = []
    while True:
        event = ws.receive_json()
        events.append(event)
        if event["type"] == kind:
            return events


def test_chat_streams_agent_events(app_factory, live):
    provider = ScriptedProvider([
        Turn("tool_use", [ToolCall("t1", "compose", {"kind": "chords", "track": 1, "slot": 0, "seed": 4})]),
        Turn("end_turn", text="Chords are on track 2."),
    ])
    api, providers = app_factory(provider)
    with api.websocket_connect(f"/chat?token={TOKEN}&provider=anthropic&model=claude-opus-5-5&ignored=1") as ws:
        ready = ws.receive_json()
        assert ready["type"] == "ready" and ready["tools"] == 12
        ws.send_json({"type": "user", "text": "Chords please"})
        events = _until(ws, "done")
    assert providers[0][0] == {"provider": "anthropic", "model": "claude-opus-5-5"}
    assert [e["type"] for e in events] == ["tool_call", "tool_result", "plan", "text", "done"]
    assert events[2]["roll"]["clips"][0]["kind"] == "chords"
    assert live.on_main(lambda: live.song.tracks[1].clip_slots[0].has_clip)


def test_plan_preview_is_applied_and_undone_from_the_page(app_factory, live):
    """The page's Apply and Undo buttons run apply_plan and undo through the same tool host."""
    provider = ScriptedProvider([
        Turn("tool_use", [ToolCall("t1", "compose", {"kind": "chords", "track": 1, "slot": 0, "seed": 4, "preview": True})]),
        Turn("end_turn", text="Here is a preview."),
        Turn("end_turn", text="ok"),
    ])
    api, _ = app_factory(provider)
    with api.websocket_connect(f"/chat?token={TOKEN}") as ws:
        ws.receive_json()
        ws.send_json({"type": "user", "text": "plan chords"})
        events = _until(ws, "done")
        plan = next(e for e in events if e["type"] == "plan")
        assert events[0]["source"] == "model"
        clip = plan["roll"]["clips"][0]
        assert plan["roll"]["plan_id"] and not plan["roll"]["applied"]
        assert clip["kind"] == "chords" and clip["add"] and clip["existing"] == []
        assert not live.on_main(lambda: live.song.tracks[1].clip_slots[0].has_clip)

        ws.send_json({"type": "tool", "name": "apply_plan", "input": {"plan_id": plan["roll"]["plan_id"]}})
        events = _until(ws, "done")
        assert [e["type"] for e in events] == ["tool_call", "tool_result", "done"]
        assert all(e["source"] == "user" for e in events[:2]) and not events[1]["is_error"]
        assert events[1]["result"]["plan_id"] == plan["roll"]["plan_id"]
        assert events[2]["stop_reason"] == "user_tool"
        assert live.on_main(lambda: live.song.tracks[1].clip_slots[0].has_clip)

        ws.send_json({"type": "tool", "name": "undo", "input": {"action": "undo"}})
        events = _until(ws, "done")
        assert events[1]["name"] == "undo" and not events[1]["is_error"]
        assert live.on_main(lambda: live.song.undo_calls) == 1

        # The model hears about the buttons with the next message, so it does not apply twice.
        ws.send_json({"type": "user", "text": "thanks"})
        _until(ws, "done")
    assert provider.users[-1].startswith("[The user ran apply_plan")
    assert "[The user ran undo" in provider.users[-1] and provider.users[-1].endswith("\n\nthanks")


def test_page_tools_are_limited_and_wait_for_the_model(app_factory, live):
    api, _ = app_factory()
    with api.websocket_connect(f"/chat?token={TOKEN}") as ws:
        ws.receive_json()
        ws.send_json({"type": "tool", "name": "delete_track", "input": {"track": 0}})
        assert ws.receive_json() == {"type": "error", "message": "delete_track cannot be run from the chat"}
        ws.send_json({"type": "tool", "name": "apply_plan", "input": {"plan_id": "gone"}})
        events = _until(ws, "done")
        assert events[1]["is_error"] and "NOT_FOUND" in events[1]["result"]
        ws.send_json({"type": "tool", "name": "undo", "input": {"action": "undo"}})
        events = _until(ws, "done")
        assert events[1]["is_error"] and "Nothing to undo" in events[1]["result"]
    assert live.on_main(lambda: len(live.song.tracks)) == 2


def test_chat_confirmation_round_trip(app_factory, live):
    provider = ScriptedProvider([
        Turn("tool_use", [ToolCall("t1", "delete_clip", {"track": 1, "slot": 0})]),
        Turn("end_turn", text="Kept."),
    ])
    live.on_main(lambda: live.song.tracks[1].clip_slots[0].create_clip(4.0))
    api, _ = app_factory(provider)
    with api.websocket_connect(f"/chat?token={TOKEN}") as ws:
        ws.receive_json()
        ws.send_json({"type": "user", "text": "delete the clip on track 2"})
        events = _until(ws, "confirm")
        assert events[-1]["message"].startswith("Delete clip") and "track 2 '2-MIDI'" in events[-1]["message"]
        ws.send_json({"type": "confirm_reply", "id": events[-1]["id"], "accept": False})
        events = _until(ws, "done")
    assert events[0]["type"] == "tool_result" and events[0]["is_error"] and "CANCELLED" in events[0]["result"]
    assert live.on_main(lambda: live.song.tracks[1].clip_slots[0].has_clip)


def test_chat_reset_and_unknown_messages(app_factory):
    api, _ = app_factory()
    with api.websocket_connect(f"/chat?token={TOKEN}") as ws:
        ws.receive_json()
        ws.send_json({"type": "reset"})
        assert ws.receive_json() == {"type": "reset"}
        ws.send_json({"type": "nope"})
        assert ws.receive_json()["type"] == "error"


def test_chat_page_is_served_without_token_and_holds_no_secret(app_factory):
    api, _ = app_factory()
    page = api.get("/ui")
    assert page.status_code == 200
    assert page.headers["cache-control"] == "no-store"
    assert "location.hash" in page.text and TOKEN not in page.text


def test_chat_page_reloads_for_a_new_token(app_factory):
    # The device adds ?key=... so a new token is a real navigation in jweb.
    api, _ = app_factory()
    page = api.get("/ui?key=0123abcd")
    assert page.status_code == 200
    assert 'addEventListener("hashchange", () => location.reload())' in page.text


def test_models_lists_default_and_claude_and_skips_unreachable_local_servers(app_factory, monkeypatch):
    monkeypatch.setenv("LMSTUDIO_HOST", "http://127.0.0.1:9")  # nothing listens on the discard port
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:9")
    api, _ = app_factory()
    assert api.get("/models").status_code == 401
    models = api.get("/models", headers=AUTH).json()["models"]
    assert models[0]["provider"] == "" and models[0]["label"].startswith("Default (")
    assert {"provider": "anthropic", "model": "claude-opus-5-5", "label": "Claude Opus 5.5"} in models
    assert not [m for m in models if m["provider"] in ("lmstudio", "ollama")]


def test_models_without_an_api_key_still_lists_the_choices(bridge_env, monkeypatch):
    monkeypatch.setenv("LMSTUDIO_HOST", "http://127.0.0.1:9")
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:9")

    def no_key(options):
        raise credentials.MissingKey("No Claude API key")

    api = TestClient(build_app(BridgeClient(), no_key, TOKEN))
    response = api.get("/models", headers=AUTH)
    assert response.status_code == 200 and "No Claude API key" in response.json()["error"]
    assert any(m["provider"] == "anthropic" for m in response.json()["models"])


async def test_local_models_are_listed_and_embeddings_dropped():
    import httpx2 as httpx

    from midibakery.api.models import list_models

    def handler(request):
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "google/gemma-4-e4b"}, {"id": "text-embedding-nomic"}]})
        return httpx.Response(200, json={"models": [{"name": "qwen3:8b"}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        models = await list_models("lmstudio", "google/gemma-4-e4b", client=client)
    labels = [m["label"] for m in models]
    assert "LM Studio · google/gemma-4-e4b" in labels and "Ollama · qwen3:8b" in labels
    assert not any("embedding" in label for label in labels)


def test_second_api_on_a_busy_port_keeps_the_running_apis_token(bridge_env):
    import socket

    from midibakery.api.server import serve

    write_api_info(8766, "running-token")
    with socket.socket() as running:
        running.bind(("127.0.0.1", 0))
        running.listen()
        with pytest.raises(SystemExit):
            serve(lambda options: None, port=running.getsockname()[1])
    assert json.loads(api_info_path().read_text())["token"] == "running-token"


def test_song_plan_reaches_the_page_and_its_apply_button_writes_it(app_factory, live):
    """plan_song's preview carries what the timeline card draws; Apply on the card writes the song."""
    provider = ScriptedProvider([
        Turn("tool_use", [ToolCall("t1", "plan_song", {"genre": "trap", "seed": 3})]),
        Turn("end_turn", text="Here is the song."),
    ])
    api, _ = app_factory(provider)
    with api.websocket_connect(f"/chat?token={TOKEN}") as ws:
        ws.receive_json()
        ws.send_json({"type": "user", "text": "a trap song"})
        events = _until(ws, "done")
        song = next(e for e in events if e["type"] == "tool_result" and e["name"] == "plan_song")["result"]
        assert song["genre"] == "Trap" and song["duration"] and song["bpm"]
        assert all({"name", "bar", "bars", "plays"} <= set(s) for s in song["sections"])
        assert set(song["tracks"]) == {"drums", "bass", "chords", "lead", "riser", "impact", "sidechain"}

        ws.send_json({"type": "tool", "name": "apply_plan", "input": {"plan_id": song["plan_id"]}})
        events = _until(ws, "done")
        assert not next(e for e in events if e["type"] == "tool_result")["is_error"]
    page = api.get("/ui").text
    assert 'if (ev.name === "plan_song"' in page and "function showSong(song)" in page


def test_api_info_appears_only_once_the_server_answers(tmp_path):
    """The devices open their page as soon as api.json exists: it must not name a server that is still starting."""
    import os
    import socket
    import subprocess
    import sys
    import time
    import urllib.request

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    env = {**os.environ, "MIDIBAKERY_HOME": str(tmp_path), "MIDIBAKERY_PORT": "0", "MIDIBAKERY_NO_UPDATE_CHECK": "1"}
    server = subprocess.Popen([sys.executable, "-m", "midibakery.cli", "api", "--provider", "anthropic", "--port", str(port)],
                              env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        info = tmp_path / "api.json"
        deadline = time.time() + 30
        while not info.exists() and time.time() < deadline and server.poll() is None:
            time.sleep(0.02)
        assert info.exists()
        token = json.loads(info.read_text())["token"]
        request = urllib.request.Request(f"http://127.0.0.1:{port}/health", headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(request, timeout=3) as response:  # the first request after the file appeared
            assert json.loads(response.read())["ok"] is True
    finally:
        server.terminate()
        server.wait(timeout=10)


def test_bake_endpoints(app_factory, live):
    api, _ = app_factory()
    assert api.get("/bake/options").status_code == 401
    assert api.get("/bake").status_code == 200  # the page holds no secret
    options = api.get("/bake/options", headers=AUTH).json()
    assert options["genres"][0] == "house" and options["baked"] is None
    bad = api.post("/bake/run", headers=AUTH, json={"genre": "polka"})
    assert bad.status_code == 422
    baked = api.post("/bake/run", headers=AUTH, json={"genre": "house", "length": "radio", "seed": 3}).json()
    assert baked["seed"] == 3 and baked["baked"]["genre"] == "house"
    assert api.get("/bake/options", headers=AUTH).json()["baked"]["seed"] == 3


def test_sounds_endpoints(app_factory, live, tmp_path, monkeypatch):
    monkeypatch.setenv("MIDIBAKERY_HOME", str(tmp_path))
    api, _ = app_factory()
    assert api.get("/sounds").status_code == 401
    assert api.get("/sounds", headers=AUTH).json() == {"mine": {}}
    presets = api.get("/sounds/presets?part=drums", headers=AUTH).json()["presets"]
    assert any(p["name"] == "909 Core Kit" for p in presets)
    assert api.get("/sounds/presets?part=riser", headers=AUTH).status_code == 422
    chosen = api.post("/sounds", headers=AUTH, json={"part": "lead", "path": "Synth Keys/Light Keys.adg"}).json()
    assert chosen == {"mine": {"lead": "sounds/Synth Keys/Light Keys.adg"}}
    assert api.post("/sounds", headers=AUTH, json={"part": "lead", "path": None}).json() == {"mine": {}}
    assert api.post("/sounds", headers=AUTH, json={"part": "riser", "path": "x"}).status_code == 422


def test_sounds_drop_resolves_a_dragged_preset(app_factory, live, tmp_path, monkeypatch):
    monkeypatch.setenv("MIDIBAKERY_HOME", str(tmp_path))
    api, _ = app_factory()
    assert api.post("/sounds/drop", json={"part": "drums", "file": "/x/909 Core Kit.adg"}).status_code == 401
    got = api.post("/sounds/drop", headers=AUTH, json={"part": "drums", "file": "/Library/Core Library/909 Core Kit.adg"}).json()
    assert got["preset"] == "909 Core Kit" and got["mine"]["drums"].endswith("909 Core Kit.adg")
    assert api.post("/sounds/drop", headers=AUTH, json={"part": "drums", "file": "/x/song.wav"}).status_code == 422
    assert api.post("/sounds/drop", headers=AUTH, json={"part": "drums", "file": "/x/Nothing Here.adg"}).status_code == 422


def test_sounds_per_genre_and_drop_uses_the_pages_genre(app_factory, live, tmp_path, monkeypatch):
    monkeypatch.setenv("MIDIBAKERY_HOME", str(tmp_path))
    api, _ = app_factory()
    api.post("/sounds", headers=AUTH, json={"part": "lead", "path": "Synth Keys/Light Keys.adg", "genre": "trap"})
    assert api.get("/sounds?genre=house", headers=AUTH).json() == {"mine": {}}
    assert "lead" in api.get("/sounds?genre=trap", headers=AUTH).json()["mine"]  # the page now shows trap
    api.post("/sounds/drop", headers=AUTH, json={"part": "drums", "file": "/x/909 Core Kit.adg"})
    assert "drums" in api.get("/sounds?genre=trap", headers=AUTH).json()["mine"]
    assert api.get("/sounds?genre=house", headers=AUTH).json() == {"mine": {}}


def test_sound_settings_page_and_search(app_factory, live, tmp_path, monkeypatch):
    monkeypatch.setenv("MIDIBAKERY_HOME", str(tmp_path))
    api, _ = app_factory()
    assert api.get("/sound-settings").status_code == 200  # the page holds no secret
    found = api.get("/sounds/presets?part=drums&q=909", headers=AUTH).json()["presets"]
    assert found and all("909" in p["name"] for p in found)
    api.get("/sounds?genre=trap", headers=AUTH)  # the Bake page's genre: drops are for it
    api.get("/sounds?genre=house&view=1", headers=AUTH)  # the settings page only looks
    dropped = api.post("/sounds/drop", headers=AUTH, json={"part": "drums", "file": "/x/909 Core Kit.adg"}).json()
    assert dropped["genre"] == "trap"
