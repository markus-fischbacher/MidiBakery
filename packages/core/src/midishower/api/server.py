"""Local HTTP/WebSocket API for the Max for Live devices.

- ``WS /chat``: the chat device. Client sends ``{"type": "user", "text": ...}``,
  ``{"type": "confirm_reply", "id": n, "accept": bool}``, ``{"type": "cancel"}``
  and ``{"type": "reset"}``; the server streams agent events (``text``,
  ``thinking``, ``tool_call``, ``tool_result``, ``plan``, ``confirm``, ``done``,
  ``error``) as JSON messages.
- ``POST /miditool/generate`` and ``/miditool/transform``: the clip-view MIDI
  Tools. Notes in, notes out; nothing is written to Live by the server.
- ``GET /health``: server and Live bridge status.
- ``GET /ui``: the chat page shown by the chat device (``jweb``) or a browser.
  It holds no secret; the device passes the token in the URL fragment
  (``/ui#token=...``), which browsers never send to the server.

Binds to loopback only. Every request needs the token from ``api.json`` in the
MidiShower config folder, as ``Authorization: Bearer <token>`` or, for
WebSockets, ``?token=<token>``.
"""

from __future__ import annotations

import asyncio
import hmac
import itertools
import json
import os
import secrets
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

from midishower.agent import LOCAL_PROVIDERS, REDUCED_TOOLS, SMALL_SYSTEM_PROMPT, SMALL_TOOLS, SYSTEM_PROMPT, Agent, Provider, ToolHost
from midishower.bridge import BridgeClient, BridgeError
from midishower.bridge.client import config_dir
from midishower.compose.standalone import GenerateRequest, TransformRequest, generate, transform
from midishower.mcp import build_server

VERSION = "0.1.0"
UI_PAGE = Path(__file__).with_name("ui") / "chat.html"
ProviderFactory = Callable[[dict[str, str]], Provider]


def api_info_path() -> Path:
    return config_dir() / "api.json"


def write_api_info(port: int, token: str) -> Path:
    """Discovery file for the devices: port and token, readable by the user only."""
    path = api_info_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        json.dump({"port": port, "token": token, "version": VERSION}, fh)
    os.replace(tmp, path)
    return path


def _authorized(token: str, supplied: str | None) -> bool:
    return bool(supplied) and hmac.compare_digest(token, supplied)


def _bearer(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    return header[7:] if header.lower().startswith("bearer ") else None


def build_app(bridge: BridgeClient, provider_factory: ProviderFactory, token: str) -> Starlette:
    server = build_server(bridge)

    def guard(handler):
        async def wrapped(request: Request):
            if not _authorized(token, _bearer(request)):
                return JSONResponse({"error": "UNAUTHORIZED"}, status_code=401)
            return await handler(request)

        return wrapped

    async def ui(request: Request) -> HTMLResponse:
        # no-store: a reloaded device always gets the page matching this API version
        return HTMLResponse(UI_PAGE.read_text(encoding="utf-8"), headers={"Cache-Control": "no-store"})

    async def health(request: Request) -> JSONResponse:
        try:
            live = await asyncio.wait_for(bridge.call("live.health"), 3.0)
        except (BridgeError, asyncio.TimeoutError) as exc:
            live = {"error": str(exc)}
        return JSONResponse({"ok": True, "version": VERSION, "live": live})

    def notes_endpoint(model, run):
        async def endpoint(request: Request) -> JSONResponse:
            try:
                body = model.model_validate(await request.json())
                return JSONResponse(run(body))
            except ValidationError as exc:
                return JSONResponse({"error": "INVALID_PARAMS", "details": exc.errors(include_url=False, include_context=False)}, status_code=422)
            except ValueError as exc:
                return JSONResponse({"error": "INVALID_PARAMS", "message": str(exc)}, status_code=422)

        return endpoint

    async def chat(ws: WebSocket) -> None:
        if not _authorized(token, ws.query_params.get("token")):
            await ws.close(code=4401)
            return
        await ws.accept()
        send_lock = asyncio.Lock()
        pending: dict[int, asyncio.Future[bool]] = {}
        ids = itertools.count(1)

        async def emit(event: dict[str, Any]) -> None:
            async with send_lock:
                await ws.send_json(event)

        async def confirm(message: str) -> bool:
            confirm_id = next(ids)
            future: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
            pending[confirm_id] = future
            await emit({"type": "confirm", "id": confirm_id, "message": message})
            try:
                return await future
            finally:
                pending.pop(confirm_id, None)

        options = {k: v for k, v in ws.query_params.items() if k in ("provider", "model", "tools")}
        try:
            provider = provider_factory(options)
        except ValueError as exc:
            await emit({"type": "error", "message": str(exc)})
            await ws.close()
            return
        # Local models get the small profile unless the device asks for tools=full.
        small = provider.name in LOCAL_PROVIDERS and options.get("tools") != "full"
        allowed = SMALL_TOOLS if small else REDUCED_TOOLS if options.get("tools") == "reduced" else None
        running: asyncio.Task[None] | None = None
        async with ToolHost(server, confirm, allowed) as host:
            agent = Agent(provider, host, SMALL_SYSTEM_PROMPT if small else SYSTEM_PROMPT, compact=small)
            await emit({"type": "ready", "provider": provider.name, "model": provider.model, "tools": len(host.tools)})
            try:
                while True:
                    message = await ws.receive_json()
                    kind = message.get("type")
                    if kind == "user":
                        if running is not None and not running.done():
                            await emit({"type": "error", "message": "Still working on the previous message; send cancel first."})
                            continue
                        running = asyncio.create_task(agent.send(str(message.get("text", "")), emit))
                    elif kind == "confirm_reply":
                        future = pending.get(message.get("id"))
                        if future is not None and not future.done():
                            future.set_result(bool(message.get("accept")))
                    elif kind == "cancel":
                        if running is not None and not running.done():
                            running.cancel()
                            await emit({"type": "done", "stop_reason": "cancelled", "usage": {}})
                    elif kind == "reset":
                        agent.reset()
                        await emit({"type": "reset"})
                    else:
                        await emit({"type": "error", "message": f"Unknown message type {kind!r}"})
            except WebSocketDisconnect:
                pass
            finally:
                for future in pending.values():
                    if not future.done():
                        future.set_result(False)
                if running is not None and not running.done():
                    running.cancel()

    return Starlette(
        routes=[
            Route("/health", guard(health), methods=["GET"]),
            Route("/ui", ui, methods=["GET"]),
            Route("/miditool/generate", guard(notes_endpoint(GenerateRequest, generate)), methods=["POST"]),
            Route("/miditool/transform", guard(notes_endpoint(TransformRequest, transform)), methods=["POST"]),
            WebSocketRoute("/chat", chat),
        ]
    )


def serve(provider_factory: ProviderFactory, port: int = 8766) -> None:
    import uvicorn

    token = secrets.token_urlsafe(32)
    bridge = BridgeClient()
    app = build_app(bridge, provider_factory, token)
    path = write_api_info(port, token)
    print(f"MidiShower API on http://127.0.0.1:{port} (token in {path})")
    try:
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
    finally:
        try:
            if json.loads(path.read_text()).get("token") == token:
                path.unlink()
        except (OSError, ValueError):
            pass
