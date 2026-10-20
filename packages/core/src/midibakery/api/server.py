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
- ``GET /health``: server and Live bridge status; ``update`` names a newer version, if there is one.
- ``GET /update``: the daily update check's result (``midibakery.updates``); ``?force=1`` asks now.
- ``POST /update/install``: downloads the newer version's installer, verifies it and opens it.
- ``GET /license``: trial or license state (``midibakery.license``); ``POST /license/trial``,
  ``POST /license/activate`` ``{"key"}``, ``POST /license/deactivate``. Without the trial or a license the
  MIDI Tools and the chat answer ``LICENSE_REQUIRED``; reading Live and undo keep working.
- ``GET /importer``: the Set Importer page; ``POST /import/scan`` ``{"path"}`` (a Live Set or a folder: the Sets in it),
  ``POST /import/preview`` ``{"file"}`` (one Set's roles, key and sections), ``POST /import/run`` ``{"files", "genres"?}``
  (stores them as references), ``GET``/``POST /import/queue`` (the list of Sets shared by the device and a popped-out page), ``POST /import/pick`` ``{"kind": "file"|"folder"}`` (the system file dialog, for the page in a browser),
  ``GET /import/library``, ``GET /import/patterns`` (the loops taken from imported Sets) and ``DELETE /import/{id}``.
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
import logging
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

from midibakery import credentials, license, updates
from midibakery.als import library as als_library
from midibakery.agent import LOCAL_HIDDEN, LOCAL_PROVIDERS, REDUCED_TOOLS, SMALL_SYSTEM_PROMPT, SMALL_TOOLS, SYSTEM_PROMPT, Agent, Provider, ToolHost, without_tools
from midibakery.bridge import BridgeClient, BridgeError
from midibakery.bridge.client import config_dir
from midibakery.compose import user_patterns
from midibakery.compose.standalone import GenerateRequest, TransformRequest, generate, transform
from midibakery import __version__
from midibakery.api.live_state import LiveState
from midibakery.api.models import list_models
from midibakery.mcp import build_server

VERSION = __version__
UPDATE_RECHECK = 6 * 3600  # the API often runs for days; updates.check itself asks the service once a day
UI_PAGE = Path(__file__).with_name("ui") / "chat.html"
IMPORTER_PAGE = Path(__file__).with_name("ui") / "importer.html"
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
    update_state: dict[str, Any] = {"update": None, "error": None}

    async def refresh_update(force: bool = False) -> None:
        try:
            update_state["update"] = await updates.check(force=force)
            update_state["error"] = None
        except updates.UpdateError as exc:
            update_state["error"] = str(exc)

    def update_info() -> dict[str, Any] | None:
        update = update_state["update"]
        if update is None or not update.available:
            return None
        return {"version": update.version, "notes": update.notes, "size": (update.file or {}).get("size"),
                "included": update.included}

    async def follow_updates() -> None:
        while True:
            await license.refresh()
            await refresh_update()
            await asyncio.sleep(UPDATE_RECHECK)

    async def update_status(request: Request) -> JSONResponse:
        if request.query_params.get("force"):
            await refresh_update(force=True)
        return JSONResponse({"current": VERSION, "enabled": updates.enabled(), "update": update_info(),
                             "error": update_state["error"]})

    async def update_install(request: Request) -> JSONResponse:
        update = update_state["update"]
        if update is None or not update.available:
            return JSONResponse({"error": "NO_UPDATE"}, status_code=409)
        if not update.included:
            return JSONResponse({"error": "NOT_INCLUDED", "message": f"MidiBakery {update.version} is not included in "
                                 "your license's updates.", "purchase_url": license.PURCHASE_URL}, status_code=402)
        try:
            path = await updates.download(update)
            updates.open_installer(path)
        except updates.UpdateError as exc:
            return JSONResponse({"error": "UPDATE_FAILED", "message": str(exc)}, status_code=502)
        return JSONResponse({"ok": True, "version": update.version, "installer": path.name})

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
        """Claude's API key: GET status, PUT {"api_key"} stores it (Keychain, Credential Manager), DELETE removes it.
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

    async def importer_ui(request: Request) -> HTMLResponse:
        return HTMLResponse(IMPORTER_PAGE.read_text(encoding="utf-8"), headers={"Cache-Control": "no-store"})

    def importer(action):
        """One import endpoint: the body's problems are the caller's (422), the work runs off the event loop."""
        async def endpoint(request: Request) -> JSONResponse:
            try:
                body = await request.json() if request.method in ("POST", "PUT") else {}
                if not isinstance(body, dict):
                    raise ValueError("expected a JSON object")
                return JSONResponse(await asyncio.to_thread(action, body, request))
            except (ValueError, OSError) as exc:
                return JSONResponse({"error": "INVALID_PARAMS", "message": str(exc)}, status_code=422)

        return endpoint

    def import_scan(body: dict, _request: Request) -> dict:
        return {"sets": als_library.listing(als_library.find_sets(str(body.get("path") or "")))}

    def import_preview(body: dict, _request: Request) -> dict:
        return als_library.preview(str(body.get("file") or ""))

    def import_run(body: dict, _request: Request) -> dict:
        files = body.get("files")
        if not isinstance(files, list) or not all(isinstance(f, str) for f in files):
            raise ValueError("files: expected a list of paths")
        genres = body.get("genres") if isinstance(body.get("genres"), dict) else None
        return als_library.run(files, genres)

    def import_queue(body: dict, request: Request) -> dict:
        return als_library.set_queue(body.get("sets")) if request.method == "POST" else als_library.queue()

    def import_pick(body: dict, _request: Request) -> dict:
        return {"path": als_library.pick(str(body.get("kind") or ""))}

    def import_library(_body: dict, _request: Request) -> dict:
        return {"library": als_library.library()}

    def import_patterns(_body: dict, _request: Request) -> dict:
        keep = ("name", "kind", "label", "description", "set", "set_name", "repeats", "bar_numbers", "bars")
        return {"patterns": [{k: e.get(k) for k in keep} for e in user_patterns.entries()]}

    def import_delete(_body: dict, request: Request) -> dict:
        return {"deleted": als_library.delete(request.path_params["reference"])}

    async def health(request: Request) -> JSONResponse:
        try:
            live = await asyncio.wait_for(bridge.call("live.health"), 3.0)
        except (BridgeError, asyncio.TimeoutError) as exc:
            live = {"error": str(exc)}
        # pid: the Remote Script stops an API of another version (left from before an update) by it
        state = license.status()
        return JSONResponse({"ok": True, "version": VERSION, "pid": os.getpid(), "live": live, "update": update_info(),
                             "license": {"state": state.state, "message": state.message}})

    async def license_state(request: Request) -> JSONResponse:
        return JSONResponse(license.status().as_dict())

    async def license_action(request: Request) -> JSONResponse:
        action = request.path_params["action"]
        try:
            if action == "trial":
                await license.start_trial()
            elif action == "activate":
                try:
                    key = str((await request.json()).get("key", ""))
                except (ValueError, AttributeError):
                    key = ""
                await license.activate(key)
            elif action == "deactivate":
                await license.deactivate()
            else:
                return JSONResponse({"error": "NOT_FOUND"}, status_code=404)
        except license.LicenseError as exc:
            return JSONResponse({"error": exc.code, "message": str(exc)}, status_code=422)
        return JSONResponse(license.status().as_dict())

    def notes_endpoint(model, run):
        async def endpoint(request: Request) -> JSONResponse:
            if not license.allowed():
                return JSONResponse({"error": "LICENSE_REQUIRED", "message": license.status().message}, status_code=402)
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
        # results, minus LOCAL_HIDDEN. tools=small or tools=reduced opts into a subset.
        small = options.get("tools") == "small"
        allowed = SMALL_TOOLS if small else REDUCED_TOOLS if options.get("tools") == "reduced" else None
        running: asyncio.Task[None] | None = None
        hidden = LOCAL_HIDDEN if allowed is None and provider.name in LOCAL_PROVIDERS else frozenset()
        async with ToolHost(server, confirm, allowed, hidden) as host:
            agent = Agent(provider, host, without_tools(SMALL_SYSTEM_PROMPT if small else SYSTEM_PROMPT, hidden), compact=provider.name in LOCAL_PROVIDERS)
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
                        if kind == "user" and not license.allowed():
                            # before the model runs: no tokens spent on an answer whose tools would refuse
                            await emit({"type": "error", "code": "LICENSE_REQUIRED", "message": license.status().message})
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
        tasks = [asyncio.create_task(live.run()), asyncio.create_task(follow_updates())]
        try:
            yield
        finally:
            for task in tasks:
                task.cancel()

    return Starlette(
        lifespan=lifespan,
        routes=[
            Route("/health", guard(health), methods=["GET"]),
            Route("/ui", ui, methods=["GET"]),
            Route("/importer", importer_ui, methods=["GET"]),
            Route("/import/scan", guard(importer(import_scan)), methods=["POST"]),
            Route("/import/preview", guard(importer(import_preview)), methods=["POST"]),
            Route("/import/run", guard(importer(import_run)), methods=["POST"]),
            Route("/import/queue", guard(importer(import_queue)), methods=["GET", "POST"]),
            Route("/import/pick", guard(importer(import_pick)), methods=["POST"]),
            Route("/import/library", guard(importer(import_library)), methods=["GET"]),
            Route("/import/patterns", guard(importer(import_patterns)), methods=["GET"]),
            Route("/import/{reference}", guard(importer(import_delete)), methods=["DELETE"]),
            Route("/models", guard(models), methods=["GET"]),
            Route("/update", guard(update_status), methods=["GET"]),
            Route("/update/install", guard(update_install), methods=["POST"]),
            Route("/license", guard(license_state), methods=["GET"]),
            Route("/license/{action}", guard(license_action), methods=["POST"]),
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
    # api.log is where a chat goes wrong is read afterwards: when, and which tool call
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", force=True)
    print(f"MidiBakery API on http://127.0.0.1:{port} (token in {path})", flush=True)
    try:
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
    finally:
        try:
            if json.loads(path.read_text()).get("token") == token:
                path.unlink()
        except (OSError, ValueError):
            pass
