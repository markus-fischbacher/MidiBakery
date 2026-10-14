"""User confirmation for destructive tool calls.

On protocol 2026-07-28 the tool answers the first call with an
``InputRequiredResult`` carrying a form elicitation; the client asks the user
and retries the same call with the answer in ``input_responses``. Older
sessions use a classic ``elicitation/create`` round trip. Clients without the
elicitation capability are not asked: they rely on the tools' ``destructiveHint``
and on Live's undo.
"""

from __future__ import annotations

import json
from typing import Any

from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ElicitRequest, ElicitRequestFormParams, ElicitResult, InputRequiredResult
from pydantic import BaseModel, Field

CONFIRM_KEY = "midishower.confirm"
MODERN_PROTOCOL = "2026-07-28"
SCHEMA = {
    "type": "object",
    "properties": {
        "confirm": {
            "type": "boolean",
            "title": "Go ahead",
            "description": "The change can be undone in Live with one undo step.",
            "default": True,
        }
    },
    "required": ["confirm"],
}


class ConfirmForm(BaseModel):
    confirm: bool = Field(True, title="Go ahead", description="The change can be undone in Live with one undo step.")


def _capabilities(ctx: Context | None) -> Any:
    if ctx is None:
        return None
    try:
        return ctx.client_capabilities
    except (LookupError, RuntimeError, ValueError):
        return None  # called outside a client request (tests, direct calls)


def _modern(ctx: Context) -> bool:
    try:
        version = ctx.protocol_version
    except (LookupError, RuntimeError, ValueError):
        return False
    return bool(version) and version >= MODERN_PROTOCOL


def request_state(ctx: Context | None) -> dict[str, Any]:
    """State this tool put into a previous InputRequiredResult (e.g. the seed), or {}."""
    if ctx is None:
        return {}
    try:
        raw = ctx.request_state
    except (LookupError, RuntimeError, ValueError):
        return {}
    if not raw:
        return {}
    try:
        state = json.loads(raw)
    except ValueError:
        return {}
    return state if isinstance(state, dict) else {}


def _declined() -> ToolError:
    return ToolError("CANCELLED: the user declined the change; nothing was written to Live")


async def confirm(ctx: Context | None, message: str, state: dict[str, Any] | None = None) -> InputRequiredResult | None:
    """Ask the user before a destructive change.

    Returns None when the call may go ahead, an InputRequiredResult the tool must
    return as-is when the client still has to ask, and raises ToolError when the
    user declined.
    """
    capabilities = _capabilities(ctx)
    if ctx is None or capabilities is None or capabilities.elicitation is None:
        return None

    if _modern(ctx):
        responses = ctx.input_responses or {}
        answer = responses.get(CONFIRM_KEY)
        if answer is None:
            return InputRequiredResult(
                input_requests={CONFIRM_KEY: ElicitRequest(params=ElicitRequestFormParams(message=message, requested_schema=SCHEMA))},
                request_state=json.dumps(state) if state else None,
            )
        if isinstance(answer, ElicitResult) and answer.action == "accept" and (answer.content or {}).get("confirm", True):
            return None
        raise _declined()

    result = await ctx.elicit(message, ConfirmForm)
    if result.action == "accept" and getattr(result.data, "confirm", False):
        return None
    raise _declined()
