"""Local HTTP/WebSocket API for the Max for Live devices.

- ``WS /chat``: the chat device. Client sends ``{"type": "user", "text": ...}``,
  ``{"type": "confirm_reply", "id": n, "accept": bool}``, ``{"type": "cancel"}``,
  ``{"type": "reset"}`` and ``{"type": "tool", "name": ..., "input": {...}}`` for
  the page's own buttons (``apply_plan`` on a plan preview, ``undo``; see
  ``UI_TOOLS``); the server streams agent events (``text``, ``thinking``,
  ``tool_call``, ``tool_result``, ``plan``, ``confirm``, ``done``, ``error``) as
  JSON messages. Tool events carry ``source``: ``model`` or ``user``. ``live_state``
  messages (``connected``, ``state``) follow what Live plays, for the status line.
- ``POST /miditool/generate`` and ``/miditool/transform``: the clip-view MIDI
  Tools. Notes in, notes out; nothing is written to Live by the server.
- ``GET /health``: server and Live bridge status.
- ``GET /models``: model choices for the chat (Default, Claude, installed LM Studio / Ollama models).
- ``GET /ui``: the chat page shown by the chat device (``jweb``) or a browser.
  It holds no secret; the device passes the token in the URL fragment
  (``/ui#token=...``), which browsers never send to the server.

Binds to loopback only. Every request needs the token from ``api.json`` in the
MidiBakery config folder, as ``Authorization: Bearer <token>`` or, for
WebSockets, ``?token=<token>``.
"""

from __future__ import annotations

import asyncio
import contextlib
import hmac
import itertools
import json
import os
import secrets
import socket
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

from midibakery import credentials
from midibakery.agent import LOCAL_PROVIDERS, REDUCED_TOOLS, SMALL_SYSTEM_PROMPT, SMALL_TOOLS, SYSTEM_PROMPT, Agent, Provider, ToolHost
from midibakery.bridge import BridgeClient, BridgeError
from midibakery.bridge.client import config_dir
from midibakery.compose.standalone import GenerateRequest, TransformRequest, generate, transform
from midibakery.api.live_state import LiveState
from midibakery.api.models import list_models
from midibakery.mcp import build_server

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


def build_app(bridge: BridgeClient, provider_factory: ProviderFactory, token: str, live: LiveState | None = None) -> Starlette:
    live = live or LiveState()
    server = build_server(bridge)

    def guard(handler):
        async def wrapped(request: Request):
            if not _authorized(token, _bearer(request)):
                return JSONResponse({"error": "UNAUTHORIZED"}, status_code=401)
            return await handler(request)

        return wrapped

    default: dict[str, str] = {}

    async def models(request: Request) -> JSONResponse:
        """Model choices for the chat's menu; local models are listed when their server runs."""
        if not default:
            try:
                provider = provider_factory({})
            except ValueError as exc:  # e.g. no Claude key yet: the menu still lists every choice
                return JSONResponse({"models": await list_models("anthropic", "no API key"), "error": str(exc)})
            default.update(provider=provider.name, model=provider.model)
        return JSONResponse({"models": await list_models(default["provider"], default["model"])})

    async def auth(request: Request) -> JSONResponse:
        """Claude's API key: GET status, PUT {"api_key"} stores it in the Keychain, DELETE removes it.
        The key is never sent back."""
        store = credentials.store()
        if request.method == "PUT":
            try:
                key = str((await request.json()).get("api_key", "")).strip()
            except (ValueError, AttributeError):
                key = ""
            try:
                if not credentials.valid_format(key):
                    raise credentials.InvalidKey("That does not look like a Claude API key")
                await credentials.verify(key)
                await asyncio.to_thread(store.save, key)
            except credentials.InvalidKey as exc:
                return JSONResponse({"error": "INVALID_KEY", "message": str(exc)}, status_code=422)
            except OSError as exc:
                return JSONResponse({"error": "STORE_FAILED", "message": str(exc)}, status_code=500)
        elif request.method == "DELETE":
            await asyncio.to_thread(store.delete)
        return JSONResponse(await asyncio.to_thread(credentials.status))

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
        except credentials.MissingKey as exc:
            # Not a connection problem: the page asks for the key instead of reconnecting.
            await emit({"type": "error", "code": "NO_API_KEY", "message": str(exc)})
            await ws.close(code=4402)
            return
        except ValueError as exc:
            await emit({"type": "error", "message": str(exc)})
            await ws.close()
            return
        # Every model gets every tool; local models get them with lean schemas and short
        # results. tools=small or tools=reduced opts into a subset.
        small = options.get("tools") == "small"
        allowed = SMALL_TOOLS if small else REDUCED_TOOLS if options.get("tools") == "reduced" else None
        running: asyncio.Task[None] | None = None
        async with ToolHost(server, confirm, allowed) as host:
            agent = Agent(provider, host, SMALL_SYSTEM_PROMPT if small else SYSTEM_PROMPT, compact=provider.name in LOCAL_PROVIDERS)
            await emit({"type": "ready", "provider": provider.name, "model": provider.model, "tools": len(host.tools)})
            changed = live.watch()

            async def live_status() -> None:
                # The page's status line: what Live plays, tempo, scale; the latest state only.
                sent = False
                try:
                    while True:
                        await changed.wait()
                        changed.clear()
                        message = live.message()
                        if not sent and message["state"] is None:
                            continue  # nothing known yet; the page keeps the line hidden
                        sent = True
                        await emit(message)
                except (WebSocketDisconnect, RuntimeError):
                    pass

            status = asyncio.create_task(live_status())
            try:
                while True:
                    message = await ws.receive_json()
                    kind = message.get("type")
                    if kind in ("user", "tool"):
                        if running is not None and not running.done():
                            await emit({"type": "error", "message": "Still working on the previous message; send cancel first."})
                            continue
                        if kind == "user":
                            work = agent.send(str(message.get("text", "")), emit)
                        else:
                            arguments = message.get("input")
                            work = agent.run_tool(str(message.get("name", "")), arguments if isinstance(arguments, dict) else {}, emit)
                        # A task, not awaited here: apply_plan may ask for a confirm_reply on this socket.
                        running = asyncio.create_task(work)
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
                status.cancel()
                live.unwatch(changed)
                for future in pending.values():
                    if not future.done():
                        future.set_result(False)
                if running is not None and not running.done():
                    running.cancel()

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette):
        follow = asyncio.create_task(live.run())
        try:
            yield
        finally:
            follow.cancel()

    return Starlette(
        lifespan=lifespan,
        routes=[
            Route("/health", guard(health), methods=["GET"]),
            Route("/ui", ui, methods=["GET"]),
            Route("/models", guard(models), methods=["GET"]),
            Route("/auth/anthropic", guard(auth), methods=["GET", "PUT", "DELETE"]),
            Route("/miditool/generate", guard(notes_endpoint(GenerateRequest, generate)), methods=["POST"]),
            Route("/miditool/transform", guard(notes_endpoint(TransformRequest, transform)), methods=["POST"]),
            WebSocketRoute("/chat", chat),
        ]
    )


def serve(provider_factory: ProviderFactory, port: int = 8766) -> None:
    import uvicorn

    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            # Keep the running API's discovery file: overwriting it would lock its clients out.
            raise SystemExit(f"Port {port} is already in use; is the MidiBakery API already running?")
    token = secrets.token_urlsafe(32)
    bridge = BridgeClient()
    app = build_app(bridge, provider_factory, token)
    path = write_api_info(port, token)
    print(f"MidiBakery API on http://127.0.0.1:{port} (token in {path})")
    try:
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
    finally:
        try:
            if json.loads(path.read_text()).get("token") == token:
                path.unlink()
        except (OSError, ValueError):
            pass
