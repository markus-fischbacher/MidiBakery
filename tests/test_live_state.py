"""Live state events: the Remote Script pushes `state` to subscribers, the API forwards it to chat pages."""

import asyncio
import json
import socket

from starlette.testclient import TestClient

from midibakery.agent.providers.base import Turn
from midibakery.api.live_state import LiveState
from midibakery.api.server import build_app
from midibakery.bridge import BridgeClient, discovery_path
from test_agent import ScriptedProvider

TOKEN = "t" * 32


async def next_state(states, timeout=2.0):
    return await asyncio.wait_for(states.get(), timeout)


async def test_subscriber_gets_the_state_and_its_changes(live):
    states: asyncio.Queue = asyncio.Queue()
    client = BridgeClient(on_event=lambda topic, data: states.put_nowait(data), topics=("state",))
    try:
        await client.connect()
        first = await next_state(states)
        assert first["tempo"] == 120.0 and first["signature"] == [4, 4] and first["is_playing"] is False
        assert first["playing"] == [] and first["selected_track"] == 0

        await client.call("song.set", {"tempo": 124})
        changed = await next_state(states)
        assert changed["tempo"] == 124.0
    finally:
        await client.close()


async def test_state_names_playing_launching_and_stopping_clips(live, client):
    await client.call("clip.create", {"track": 0, "slot": 2, "length": 4, "name": "Beat"})
    tracks = live.on_main(lambda: live.song.tracks)
    name = live.on_main(lambda: tracks[0].name)

    def busy():
        tracks[0].playing_slot_index = 2
        tracks[1].fired_slot_index = 3
        live.song.is_playing = True

    live.on_main(busy)
    states: asyncio.Queue = asyncio.Queue()
    watcher = BridgeClient(on_event=lambda topic, data: states.put_nowait(data), topics=("state",))
    try:
        await watcher.connect()
        state = await next_state(states)
        assert state["is_playing"] is True
        assert state["playing"] == [{"track": 0, "name": name, "slot": 2, "clip": "Beat"}]
        assert state["launching"] == [{"track": 1, "slot": 3}]
        live.on_main(lambda: setattr(tracks[1], "fired_slot_index", -2))
        assert (await next_state(states))["stopping"] == [1]
    finally:
        await watcher.close()


def test_clients_without_subscription_get_no_events(live):
    info = json.loads(discovery_path().read_text())
    with socket.create_connection(("127.0.0.1", info["port"]), timeout=1) as sock:
        reader = sock.makefile()
        sock.sendall(json.dumps({"hello": info["token"], "protocol": 1}).encode() + b"\n")
        assert json.loads(reader.readline())["hello"] == "ok"
        sock.sendall(b'{"subscribe": ["everything"]}\n')
        assert json.loads(reader.readline())["error"]["code"] == "BAD_REQUEST"
        sock.sendall(b'{"id": 1, "op": "song.get", "params": {}}\n')
        assert json.loads(reader.readline())["id"] == 1  # the next line is the reply, not an event


def test_chat_page_gets_the_live_state(live):
    provider = ScriptedProvider([Turn("end_turn", text="hi")])
    app = build_app(BridgeClient(), lambda options: provider, TOKEN, LiveState(retry=0.05))
    with TestClient(app) as api, api.websocket_connect(f"/chat?token={TOKEN}") as ws:
        assert ws.receive_json()["type"] == "ready"
        message = ws.receive_json()
    assert message["type"] == "live_state" and message["connected"] is True
    assert message["state"]["tempo"] == 120.0


def test_chat_page_shows_the_status_line(live):
    page = TestClient(build_app(BridgeClient(), lambda options: None, TOKEN)).get("/ui").text
    assert '<div id="live" hidden' in page and 'case "live_state":' in page and "function showLive(ev)" in page
