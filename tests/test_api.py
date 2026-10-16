"""Local API for the Max for Live devices: auth, MIDI tool endpoints, chat WebSocket."""

import json
import stat

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from midibakery.agent import REDUCED_TOOLS
from midibakery.agent.providers.base import ToolCall, Turn
from midibakery.api.server import api_info_path, build_app, write_api_info
from midibakery.bridge import BridgeClient
from midibakery.compose.theory import Scale
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
    assert api.post("/miditool/generate", json={"kind": "drums"}).status_code == 401
    with pytest.raises(WebSocketDisconnect) as exc:
        with api.websocket_connect("/chat?token=wrong") as ws:
            ws.receive_json()
    assert exc.value.code == 4401


def test_discovery_file_is_private(bridge_env):
    path = write_api_info(8766, TOKEN)
    assert path == api_info_path()
    assert json.loads(path.read_text()) == {"port": 8766, "token": TOKEN, "version": "0.1.0"}
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_health_reports_live(app_factory, live):
    api, _ = app_factory()
    body = api.get("/health", headers=AUTH).json()
    assert body["ok"] is True and body["live"]["live"] == [12, 4, 6]


# --------------------------------------------------------------------------
# MIDI tools
# --------------------------------------------------------------------------


def test_generate_is_seeded_in_scale_and_inside_the_selection(app_factory):
    api, _ = app_factory()
    request = {
        "kind": "melody",
        "context": {"scale": A_MINOR, "start": 8.0, "length": 8.0, "seed": 5, "numerator": 4, "denominator": 4},
        "params": {"progression": "i VI III VII", "density": 0.6},
    }
    first = api.post("/miditool/generate", json=request, headers=AUTH).json()
    second = api.post("/miditool/generate", json=request, headers=AUTH).json()
    assert first == second and first["seed"] == 5
    assert first["chords"][:2] == ["Am (i)", "F (VI)"]
    scale = Scale(9, (0, 2, 3, 5, 7, 8, 10))
    assert first["notes"] and all(scale.contains(n["pitch"]) for n in first["notes"])
    assert all(8.0 <= n["start_time"] < 16.0 and n["start_time"] + n["duration"] <= 16.0 + 1e-6 for n in first["notes"])


def test_generate_drums_uses_given_pads(app_factory):
    api, _ = app_factory()
    pads = [{"note": 36, "name": "Kick"}, {"note": 37, "name": "Snare"}, {"note": 38, "name": "Closed HH"}]
    body = api.post("/miditool/generate", headers=AUTH, json={
        "kind": "drums", "context": {"length": 4, "seed": 1, "pads": pads}, "params": {"style": "rock"},
    }).json()
    assert body["drum_map"] == "drum_rack"
    assert {n["pitch"] for n in body["notes"]} <= {36, 37, 38}


def test_generate_rejects_set_only_and_unknown_params(app_factory):
    api, _ = app_factory()
    for params in ({"track": 1}, {"follow_kick": {"track": 0, "slot": 0}}, {"style": "polka"}):
        response = api.post("/miditool/generate", headers=AUTH, json={"kind": "bass", "params": params})
        assert response.status_code == 422, params


def test_transform_returns_the_full_note_list(app_factory):
    api, _ = app_factory()
    notes = [
        {"note_id": 10, "pitch": 60, "start_time": 4.1, "duration": 0.5, "probability": 0.5},
        {"note_id": 11, "pitch": 64, "start_time": 5.0, "duration": 0.5},
    ]
    body = api.post("/miditool/transform", headers=AUTH, json={
        "notes": notes, "operation": "quantize", "context": {"start": 4.0, "length": 4.0},
    }).json()
    assert body["diff"] == {"added": 0, "modified": 1, "removed": 0}
    assert [(n["note_id"], n["start_time"], n["probability"]) for n in body["notes"]] == [(10, 4.0, 0.5), (11, 5.0, 1.0)]

    chord = [{"pitch": p, "start_time": 0, "duration": 1} for p in (60, 64, 67)]
    arp = api.post("/miditool/transform", headers=AUTH, json={
        "notes": chord, "operation": "arpeggiate", "params": {"rate": 0.25}, "context": {"length": 4, "seed": 2},
    }).json()
    assert arp["diff"] == {"added": 4, "modified": 0, "removed": 3}
    assert [n["pitch"] for n in arp["notes"]] == [60, 64, 67, 60]
    assert all("note_id" not in n for n in arp["notes"])

    up = api.post("/miditool/transform", headers=AUTH, json={
        "notes": notes, "operation": "transpose", "params": {"semitones": 2}, "context": {"start": 4.0, "length": 4.0},
    }).json()
    assert [n["pitch"] for n in up["notes"]] == [62, 66]


def test_transform_rejects_duplicate_ids(app_factory):
    api, _ = app_factory()
    notes = [{"note_id": 1, "pitch": 60, "start_time": 0, "duration": 1}] * 2
    assert api.post("/miditool/transform", headers=AUTH, json={"notes": notes, "operation": "invert"}).status_code == 422


# --------------------------------------------------------------------------
# Chat WebSocket
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
        Turn("tool_use", [ToolCall("t1", "compose_chords", {"track": 1, "slot": 0, "seed": 4})]),
        Turn("end_turn", text="Chords are on track 2."),
    ])
    api, providers = app_factory(provider)
    with api.websocket_connect(f"/chat?token={TOKEN}&provider=anthropic&model=claude-opus-5-5&ignored=1") as ws:
        ready = ws.receive_json()
        assert ready["type"] == "ready" and ready["tools"] == 35
        ws.send_json({"type": "user", "text": "Chords please"})
        events = _until(ws, "done")
    assert providers[0][0] == {"provider": "anthropic", "model": "claude-opus-5-5"}
    assert [e["type"] for e in events] == ["tool_call", "tool_result", "plan", "text", "done"]
    assert events[2]["roll"]["clips"][0]["kind"] == "chords"
    assert live.on_main(lambda: live.song.tracks[1].clip_slots[0].has_clip)


def test_plan_preview_is_applied_and_undone_from_the_page(app_factory, live):
    """The page's Apply and Undo buttons run apply_plan and undo through the same tool host."""
    provider = ScriptedProvider([
        Turn("tool_use", [ToolCall("t1", "plan_changes", {"steps": [{"kind": "chords", "track": 1, "slot": 0, "seed": 4}]})]),
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


def test_local_models_get_every_tool(app_factory):
    provider = ScriptedProvider([Turn("end_turn", text="hi")])
    provider.name = "lmstudio"
    api, _ = app_factory(provider)
    with api.websocket_connect(f"/chat?token={TOKEN}") as ws:
        ready = ws.receive_json()
    assert ready["tools"] > len(REDUCED_TOOLS)
    assert {"launch_clip", "fire_scene", "update_track"} <= {t.name for t in provider.tools}


def test_chat_confirmation_round_trip(app_factory, live):
    provider = ScriptedProvider([
        Turn("tool_use", [ToolCall("t1", "delete_track", {"track": 1})]),
        Turn("end_turn", text="Deleted."),
    ])
    api, _ = app_factory(provider)
    with api.websocket_connect(f"/chat?token={TOKEN}&tools=reduced") as ws:
        assert ws.receive_json()["tools"] == len(REDUCED_TOOLS)
        ws.send_json({"type": "user", "text": "delete track 2"})
        # delete_track is not in the reduced set: the model gets an error, nothing is asked.
        events = _until(ws, "done")
    assert events[1]["is_error"] and "Unknown tool" in events[1]["result"]

    provider = ScriptedProvider([
        Turn("tool_use", [ToolCall("t1", "delete_track", {"track": 1})]),
        Turn("end_turn", text="Kept."),
    ])
    api, _ = app_factory(provider)
    with api.websocket_connect(f"/chat?token={TOKEN}") as ws:
        ws.receive_json()
        ws.send_json({"type": "user", "text": "delete track 2"})
        events = _until(ws, "confirm")
        assert events[-1]["message"] == "Delete track 2 '2-MIDI' with 0 clip(s)?"
        ws.send_json({"type": "confirm_reply", "id": events[-1]["id"], "accept": False})
        events = _until(ws, "done")
    assert events[0]["type"] == "tool_result" and events[0]["is_error"] and "CANCELLED" in events[0]["result"]
    assert live.on_main(lambda: len(live.song.tracks)) == 2


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


@pytest.mark.parametrize("kind, params", [
    ("drums", {"swing": 0, "density": 0.5, "style": "house", "chance": 0.5}),
    ("bass", {"swing": 0.2, "density": 0.5, "style": "syncopated"}),
    ("chords", {"swing": 0, "rhythm": "stabs"}),
    ("melody", {"swing": 0, "density": 0.7}),
])
def test_generate_accepts_the_requests_the_generator_device_builds(app_factory, kind, params):
    """Mirrors buildBody() in packages/m4l/src/miditool.js."""
    api, _ = app_factory()
    body = {"context": {"start": 4, "length": 16, "seed": 1, "scale": A_MINOR}, "kind": kind, "params": params}
    response = api.post("/miditool/generate", json=body, headers=AUTH)
    assert response.status_code == 200, response.text
    notes = response.json()["notes"]
    assert notes and all(4 <= n["start_time"] < 20 for n in notes)


@pytest.mark.parametrize("operation, params", [
    ("humanize", {"amount": 0.5}),
    ("quantize", {"strength": 1.0, "grid": 0.25}),
    ("invert", {}),
    ("arpeggiate", {"rate": 0.25}),
    ("variation", {"amount": 0.5}),
    ("transpose", {"semitones": 12}),
])
def test_transform_accepts_the_requests_the_transform_device_builds(app_factory, operation, params):
    api, _ = app_factory()
    notes = [
        {"note_id": 1, "pitch": 57, "start_time": 4.0, "duration": 1.0, "velocity": 100, "mute": False,
         "probability": 1, "velocity_deviation": 0, "release_velocity": 64},
        {"note_id": 2, "pitch": 60, "start_time": 4.0, "duration": 1.0, "velocity": 90, "mute": False,
         "probability": 1, "velocity_deviation": 0, "release_velocity": 64},
    ]
    body = {"context": {"start": 4, "length": 16, "seed": 1, "scale": A_MINOR}, "operation": operation, "params": params, "notes": notes}
    response = api.post("/miditool/transform", json=body, headers=AUTH)
    assert response.status_code == 200, response.text
    assert response.json()["notes"]


def test_models_lists_default_and_claude_and_skips_unreachable_local_servers(app_factory, monkeypatch):
    monkeypatch.setenv("LMSTUDIO_HOST", "http://127.0.0.1:9")  # nothing listens on the discard port
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:9")
    api, _ = app_factory()
    assert api.get("/models").status_code == 401
    models = api.get("/models", headers=AUTH).json()["models"]
    assert models[0]["provider"] == "" and models[0]["label"].startswith("Default (")
    assert {"provider": "anthropic", "model": "claude-opus-5-5", "label": "Claude Opus 5.5"} in models
    assert not [m for m in models if m["provider"] in ("lmstudio", "ollama")]


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
        Turn("tool_use", [ToolCall("t1", "plan_song", {"genre": "trap", "seed": 3, "create_missing": True})]),
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
        assert set(song["tracks"]) == {"drums", "bass", "chords", "lead"}

        ws.send_json({"type": "tool", "name": "apply_plan", "input": {"plan_id": song["plan_id"]}})
        events = _until(ws, "done")
        assert not next(e for e in events if e["type"] == "tool_result")["is_error"]
    page = api.get("/ui").text
    assert 'if (ev.name === "plan_song"' in page and "function showSong(song)" in page
