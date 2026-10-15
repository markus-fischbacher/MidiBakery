"""The agent's tools are the MCP server's tools, called in-process.

Using the same MCPServer as Claude Desktop/Code keeps one tool surface: the
same schemas, validation, plan previews and confirmations. Confirmations
(input_required / elicitation) are routed to the frontend through `confirm`.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from mcp import Client
from mcp.server import MCPServer
from mcp_types import ElicitResult

Confirm = Callable[[str], Awaitable[bool]]

# For small local models: few, coarse tools work better than the full set.
REDUCED_TOOLS = frozenset({
    "get_session",
    "get_clip",
    "create_track",
    "create_clip",
    "edit_notes",
    "compose_drums",
    "compose_bass",
    "compose_chords",
    "compose_melody",
    "transform_notes",
    "plan_changes",
    "apply_plan",
    "transport",
    "undo",
})


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    read_only: bool = False


@dataclass
class ToolOutcome:
    """What a tool call produced: text for the model, structure and piano roll for the UI."""

    text: str
    is_error: bool = False
    structured: dict[str, Any] | None = None
    roll: dict[str, Any] | None = None
    meta: dict[str, Any] = field(default_factory=dict)


class ToolHost:
    """An in-process MCP client session on the MidiShower server."""

    def __init__(self, server: MCPServer, confirm: Confirm, allowed: frozenset[str] | None = None):
        self._server = server
        self._confirm = confirm
        self._allowed = allowed
        self._client: Client | None = None
        self.tools: list[ToolSpec] = []

    async def __aenter__(self) -> ToolHost:
        self._client = Client(self._server, elicitation_callback=self._elicit)
        await self._client.__aenter__()
        listed = (await self._client.list_tools()).tools
        self.tools = sorted(
            (
                ToolSpec(
                    t.name,
                    t.description or t.title or t.name,
                    t.input_schema,
                    bool(t.annotations and t.annotations.read_only_hint),
                )
                for t in listed
                if self._allowed is None or t.name in self._allowed
            ),
            key=lambda t: t.name,  # deterministic order keeps the prompt cache warm
        )
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._client is not None:
            await self._client.__aexit__(*exc)
            self._client = None

    def names(self) -> set[str]:
        return {t.name for t in self.tools}

    async def call(self, name: str, arguments: Any) -> ToolOutcome:
        if name not in self.names():
            return ToolOutcome(f"Unknown tool '{name}'. Available: {', '.join(sorted(self.names()))}", is_error=True)
        if not isinstance(arguments, dict):
            return ToolOutcome(f"Arguments for '{name}' must be a JSON object, got {json.dumps(arguments)}", is_error=True)
        assert self._client is not None, "use ToolHost as an async context manager"
        result = await self._client.call_tool(name, arguments)
        text = "\n".join(c.text for c in result.content if getattr(c, "type", None) == "text")
        meta = dict(result.meta or {})
        return ToolOutcome(
            text=text or json.dumps(result.structured_content or {}),
            is_error=bool(result.is_error),
            structured=result.structured_content,
            roll=meta.get("midishower/roll"),
            meta=meta,
        )

    async def _elicit(self, context: Any, params: Any) -> ElicitResult:
        accepted = await self._confirm(params.message)
        if accepted:
            return ElicitResult(action="accept", content={"confirm": True})
        return ElicitResult(action="decline")
