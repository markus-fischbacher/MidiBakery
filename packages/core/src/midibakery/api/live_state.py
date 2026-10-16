"""Follows Live's `state` events for the chat pages' status line.

One bridge connection subscribed to `state`, reconnecting while Live is closed or
restarting. Pages wait on an asyncio.Event and then send the latest state, so a
burst of changes collapses into one message and states never arrive out of order.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from midibakery.bridge import BridgeClient, BridgeError

RETRY_SECONDS = 2.0


class LiveState:
    def __init__(self, client_factory: Callable[..., BridgeClient] | None = None, retry: float = RETRY_SECONDS):
        self._factory = client_factory or (lambda on_event: BridgeClient(on_event=on_event, topics=("state",)))
        self._retry = retry
        self._watchers: set[asyncio.Event] = set()
        self.connected = False
        self.state: dict[str, Any] | None = None

    def message(self) -> dict[str, Any]:
        return {"type": "live_state", "connected": self.connected, "state": self.state}

    def watch(self) -> asyncio.Event:
        """Set now and on every change; the caller clears it and sends message()."""
        changed = asyncio.Event()
        changed.set()
        self._watchers.add(changed)
        return changed

    def unwatch(self, changed: asyncio.Event) -> None:
        self._watchers.discard(changed)

    def _changed(self) -> None:
        for changed in self._watchers:
            changed.set()

    def _on_event(self, topic: str, data: dict[str, Any]) -> None:
        if topic == "state":
            self.state = data
            self.connected = True
            self._changed()

    async def run(self) -> None:
        while True:
            client = self._factory(self._on_event)
            try:
                await client.connect()
                await client.wait_closed()
            except BridgeError:
                pass
            finally:
                await client.close()
            if self.connected or self.state is not None:
                self.connected, self.state = False, None
                self._changed()
            await asyncio.sleep(self._retry)
