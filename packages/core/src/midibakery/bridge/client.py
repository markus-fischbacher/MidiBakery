"""Async client for the MidiBakery Remote Script running inside Live."""

from __future__ import annotations

import asyncio
import itertools
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from midibakery.catalog import get_op
from midibakery.catalog.ops import Batch

PROTOCOL_VERSION = 1
# Slack on top of the op timeout for the socket round trip and Live's ~100 ms tick.
TRANSPORT_SLACK = 1.0


def config_dir() -> Path:
    override = os.environ.get("MIDIBAKERY_HOME")
    if override:
        return Path(override)
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/MidiBakery"
    if sys.platform.startswith("win"):
        return Path(os.environ.get("APPDATA", Path.home())) / "MidiBakery"
    return Path.home() / ".config/midibakery"


def discovery_path() -> Path:
    return config_dir() / "bridge.json"


class BridgeError(Exception):
    """An op failed. `code` mirrors the bridge's ErrorCode values."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.details = details or {}


class BridgeUnavailable(BridgeError):
    def __init__(self, message: str):
        super().__init__("UNAVAILABLE", message)


EventHandler = Callable[[str, dict[str, Any]], None]


class BridgeClient:
    """One authenticated connection; reconnects lazily on the next call.

    With `topics` (e.g. ("state",)) the bridge pushes those events to `on_event`
    from the moment the connection is up, again after every reconnect."""

    def __init__(self, on_event: EventHandler | None = None, topics: tuple[str, ...] = ()):
        self._on_event = on_event
        self._topics = topics
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._pending: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self._ids = itertools.count(1)
        self._connect_lock = asyncio.Lock()
        self._read_task: asyncio.Task[None] | None = None
        self.live_version: tuple[int, ...] = ()

    @property
    def connected(self) -> bool:
        return self._writer is not None and not self._writer.is_closing()

    async def connect(self) -> None:
        async with self._connect_lock:
            if self.connected:
                return
            try:
                info = json.loads(discovery_path().read_text())
            except FileNotFoundError:
                raise BridgeUnavailable(
                    "Live bridge not running: open Ableton Live and select 'MidiBakery' as a Control Surface"
                ) from None
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection("127.0.0.1", info["port"], limit=8 * 1024 * 1024), 2.0
                )
            except (OSError, asyncio.TimeoutError) as exc:
                raise BridgeUnavailable(f"Cannot reach Live bridge on port {info.get('port')}: {exc}") from None
            writer.write(_frame({"hello": info["token"], "protocol": PROTOCOL_VERSION}))
            await writer.drain()
            try:
                hello = json.loads(await asyncio.wait_for(reader.readline(), 3.0))
            except (asyncio.TimeoutError, ValueError):
                writer.close()
                raise BridgeUnavailable("Live bridge did not answer the handshake") from None
            if hello.get("hello") != "ok":
                writer.close()
                raise BridgeUnavailable(f"Live bridge refused connection: {hello.get('error')}")
            if hello.get("protocol") != PROTOCOL_VERSION:
                writer.close()
                raise BridgeUnavailable(
                    f"Protocol mismatch: bridge {hello.get('protocol')}, core {PROTOCOL_VERSION}. Reinstall the Remote Script."
                )
            self.live_version = tuple(hello.get("live", ()))
            if self._topics:
                writer.write(_frame({"subscribe": list(self._topics)}))
                await writer.drain()
            self._reader, self._writer = reader, writer
            self._read_task = asyncio.create_task(self._read_loop(reader))

    async def wait_closed(self) -> None:
        """Returns when Live closes the connection (or close() is called)."""
        if self._read_task is not None:
            await asyncio.shield(self._read_task)

    async def close(self) -> None:
        if self._writer is not None:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except OSError:
                pass
        if self._read_task is not None:
            self._read_task.cancel()
        self._writer = self._reader = None
        self._fail_pending(BridgeUnavailable("Connection closed"))

    async def call(self, op: str, params: dict[str, Any] | None = None) -> Any:
        """Validate against the catalog, send, and await the result."""
        spec = get_op(op)
        payload = _validate(op, params or {})
        if not self.connected:
            await self.connect()
        await self._clip_names(payload)
        for item in payload.get("ops", []) if op == "batch" else []:
            await self._clip_names(item.get("params", {}))
            for action in item.get("params", {}).get("actions", []) if item.get("op") == "arrangement.edit" else []:
                await self._clip_names(action, ("clip", "with_clip"))
        for action in payload.get("actions", []) if op == "arrangement.edit" else []:
            await self._clip_names(action, ("clip", "with_clip"))
        if not self.connected:
            await self.connect()
        req_id = next(self._ids)
        future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self._pending[req_id] = future
        assert self._writer is not None
        self._writer.write(_frame({"id": req_id, "op": op, "params": payload, "timeout": spec.timeout}))
        try:
            await self._writer.drain()
            reply = await asyncio.wait_for(future, spec.timeout + TRANSPORT_SLACK)
        except asyncio.TimeoutError:
            raise BridgeError("TIMEOUT", f"No reply from Live for '{op}' within {spec.timeout}s") from None
        except (ConnectionError, OSError) as exc:
            await self.close()
            raise BridgeUnavailable(f"Lost connection to Live: {exc}") from None
        finally:
            self._pending.pop(req_id, None)
        if reply.get("ok"):
            return reply.get("result")
        error = reply.get("error") or {}
        raise BridgeError(error.get("code", "INTERNAL"), error.get("message", "Unknown error"), error.get("details"))

    async def _clip_names(self, params: dict[str, Any], keys: tuple[str, ...] = ("arrangement_clip",)) -> None:
        """Clip ops take an arrangement clip by name too ('Drop Bass'), like compose: Live only knows indices.
        The exact name (any case), else the one clip whose name contains it."""
        for key in keys:
            await self._clip_name(params, key)

    async def _clip_name(self, params: dict[str, Any], key: str) -> None:
        ref = params.get(key)
        if not isinstance(ref, str) or not isinstance(params.get("track"), int):
            return
        if ref.strip().isdigit():
            params[key] = int(ref.strip())
            return
        clips = (await self.call("arrangement.get", {"track": params["track"]}))["tracks"][0]["clips"]
        wanted = ref.strip().casefold()
        exact = [c for c in clips if str(c.get("name", "")).strip().casefold() == wanted]
        found = exact or [c for c in clips if wanted in str(c.get("name", "")).casefold()]
        if len(found) != 1 and not exact:
            listed = ", ".join(f"{c['index']} '{c.get('name', '')}'" for c in clips[:16]) or "none"
            problem = f"{len(found)} arrangement clips match '{ref}'" if found else f"No arrangement clip named '{ref}'"
            raise BridgeError("NOT_FOUND", f"{problem} on track index {params['track']} (its clips: {listed})",
                              {"track": params["track"], "arrangement_clip": ref})
        params[key] = int(found[0]["index"])

    async def _read_loop(self, reader: asyncio.StreamReader) -> None:
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break
                try:
                    message = json.loads(line)
                except ValueError:
                    continue
                if "event" in message:
                    if self._on_event:
                        self._on_event(message["event"], message.get("data") or {})
                    continue
                future = self._pending.get(message.get("id"))
                if future is not None and not future.done():
                    future.set_result(message)
        except (ConnectionError, OSError, asyncio.CancelledError):
            pass
        finally:
            self._writer = None
            self._fail_pending(BridgeUnavailable("Live closed the connection"))

    def _fail_pending(self, error: BridgeError) -> None:
        for future in self._pending.values():
            if not future.done():
                future.set_exception(error)
        self._pending.clear()


def _frame(obj: dict[str, Any]) -> bytes:
    return (json.dumps(obj, separators=(",", ":")) + "\n").encode()


def _validate(op: str, params: dict[str, Any]) -> dict[str, Any]:
    """Full Pydantic validation, including every op nested in a batch."""
    spec = get_op(op)
    try:
        model = spec.params.model_validate(params)
        if isinstance(model, Batch):
            for i, item in enumerate(model.ops):
                if item.op == "batch":
                    raise BridgeError("INVALID_PARAMS", "Batches cannot be nested", {"index": i})
                try:
                    item.params = _validate(item.op, item.params)
                except KeyError as exc:
                    # qwen batched tool calls: tools are not ops
                    raise BridgeError("UNKNOWN_OP", f"{exc}; batch ops are Live ops such as clip.set or notes.apply, "
                                      "not tools: call a tool like compose on its own", {"index": i}) from None
    except ValidationError as exc:
        raise BridgeError(
            "INVALID_PARAMS",
            f"Invalid parameters for '{op}'",
            {"errors": exc.errors(include_url=False, include_context=False)},
        ) from None
    return model.model_dump(mode="json", exclude_none=True)
