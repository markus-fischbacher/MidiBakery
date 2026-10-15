"""The tool loop shared by every frontend (terminal chat, Live chat device, API)."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from midishower.agent.providers.base import Emit, Provider, ToolResult
from midishower.agent.tools import ToolHost, compact_tools
from midishower.mcp.server import INSTRUCTIONS

SYSTEM_PROMPT = (
    "You are MidiShower, a music production assistant inside Ableton Live 12. "
    "You compose and edit MIDI and control the Live session through tools. "
    "Answer in the user's language and keep replies short: say what you changed or propose, "
    "with names of tracks, clips, chords and seeds where useful.\n\n"
    "Work like a producer: read the session before writing, keep parts in the song's scale and "
    "time signature, and make parts fit together (bass follows the kick and the chords, melody "
    "follows the chords). For more than one part, or when the user wants to hear options first, "
    "use plan_changes and let them apply the preview; otherwise write directly with the compose "
    "tools. If a tool fails, read the error and fix the call instead of repeating it.\n\n"
    "Tool guide:\n" + INSTRUCTIONS
)

# For local models with a small context (e.g. 8k): the essentials of SYSTEM_PROMPT and INSTRUCTIONS.
SMALL_SYSTEM_PROMPT = (
    "You are MidiShower, a music assistant controlling the open Ableton Live 12 set through tools. "
    "Answer in the user's language, briefly.\n"
    "- Call get_session first. Tracks and clip slots are zero-based indices.\n"
    "- Times are in beats (quarter notes); pitch 60 = C3. Stay in the song scale.\n"
    "- compose_drums/bass/chords/melody write a new clip into an EMPTY slot; pick an empty slot from get_session. "
    "Give bass and melody chords_from (the chord clip), the bass follow_kick (the drum clip). Never set if_exists or overwrite a clip unless the user asks for it.\n"
    "- edit_notes and transform_notes change existing notes by note_id from get_clip.\n"
    "- Every write can be undone with undo. If a tool fails, read the error and fix the call. "
    "If the user declined a change (CANCELLED), nothing was written: say so, never claim it was done."
)

MAX_STEPS = 24


class Agent:
    """One conversation: a provider (the model) plus a tool host (Live via MCP)."""

    def __init__(self, provider: Provider, host: ToolHost, system: str = SYSTEM_PROMPT, max_steps: int = MAX_STEPS, compact: bool = False):
        """`compact` sends short descriptions and lean schemas (see compact_tools) for small local models."""
        self.provider = provider
        self.host = host
        self.max_steps = max_steps
        provider.configure(system, compact_tools(host.tools) if compact else host.tools)
        self._lock = asyncio.Lock()

    def reset(self) -> None:
        self.provider.reset()

    async def send(self, text: str, emit: Emit) -> None:
        """Handle one user message until the model stops calling tools. Events go to `emit`."""
        async with self._lock:
            self.provider.add_user(text)
            for _ in range(self.max_steps):
                try:
                    turn = await self.provider.stream_turn(emit)
                except Exception as exc:  # network, auth, rate limits: report, keep the session
                    await emit({"type": "error", "message": f"{type(exc).__name__}: {exc}"})
                    return
                if turn.error:
                    await emit({"type": "error", "message": turn.error, "stop_reason": turn.stop_reason})
                    return
                if not turn.tool_calls:
                    await emit({"type": "done", "stop_reason": turn.stop_reason, "usage": turn.usage})
                    return
                results = []
                # Sequential on purpose: Live ops depend on each other's order (create, then fill).
                for call in turn.tool_calls:
                    await emit({"type": "tool_call", "id": call.id, "name": call.name, "input": call.input})
                    outcome = await self.host.call(call.name, call.input)
                    event: dict[str, Any] = {
                        "type": "tool_result",
                        "id": call.id,
                        "name": call.name,
                        "is_error": outcome.is_error,
                        "result": outcome.structured if outcome.structured is not None else outcome.text,
                    }
                    await emit(event)
                    if outcome.roll:
                        await emit({"type": "plan", "id": call.id, "name": call.name, "roll": outcome.roll})
                    results.append(ToolResult(call.id, call.name, outcome.text, outcome.is_error))
                self.provider.add_tool_results(results)
            await emit({"type": "error", "message": f"Stopped after {self.max_steps} tool rounds without an answer."})


def describe_input(value: Any, limit: int = 160) -> str:
    """Short one-line rendering of tool input for terminal output."""
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return text if len(text) <= limit else text[: limit - 1] + "…"
