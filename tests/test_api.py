"""Local API for the Max for Live devices: auth, MIDI tool endpoints, chat WebSocket."""

import json
import stat

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from midishower.agent.providers.base import ToolCall, Turn
from midishower.api.server import api_info_path, build_app, write_api_info
from midishower.bridge import BridgeClient
from midishower.compose.theory import Scale
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
        assert ready["type"] == "ready" and ready["tools"] == 27
        ws.send_json({"type": "user", "text": "Chords please"})
        events = _until(ws, "done")
    assert providers[0][0] == {"provider": "anthropic", "model": "claude-opus-5-5"}
    assert [e["type"] for e in events] == ["tool_call", "tool_result", "plan", "text", "done"]
    assert events[2]["roll"]["clips"][0]["kind"] == "chords"
    assert live.on_main(lambda: live.song.tracks[1].clip_slots[0].has_clip)


def test_chat_confirmation_round_trip(app_factory, live):
    provider = ScriptedProvider([
        Turn("tool_use", [ToolCall("t1", "delete_track", {"track": 1})]),
        Turn("end_turn", text="Deleted."),
    ])
    api, _ = app_factory(provider)
    with api.websocket_connect(f"/chat?token={TOKEN}&tools=reduced") as ws:
        assert ws.receive_json()["tools"] == 14
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
