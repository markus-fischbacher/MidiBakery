"""Provider interface: one LLM backend, owning its own conversation format."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from midishower.agent.tools import ToolSpec

Emit = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass
class ToolCall:
    id: str
    name: str
    input: Any


@dataclass
class ToolResult:
    call_id: str
    name: str
    content: str
    is_error: bool = False


@dataclass
class Turn:
    """One model response. `tool_calls` empty means the model is done for now."""

    stop_reason: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    text: str = ""
    usage: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class Provider(ABC):
    """Streams model turns and keeps the conversation in the backend's own format.

    The history is append-only: assistant turns are stored exactly as the
    backend returned them (Anthropic thinking blocks must not be edited).
    """

    name: str
    model: str

    @abstractmethod
    def configure(self, system: str, tools: list[ToolSpec]) -> None:
        """Fix the system prompt and tool list for this conversation."""

    @abstractmethod
    def add_user(self, text: str) -> None: ...

    @abstractmethod
    async def stream_turn(self, emit: Emit) -> Turn:
        """Generate one assistant turn, emitting text/thinking deltas, and append it to the history."""

    @abstractmethod
    def add_tool_results(self, results: list[ToolResult]) -> None:
        """Answer every tool call of the last turn, in one message."""

    @abstractmethod
    def reset(self) -> None:
        """Forget the conversation (system prompt and tools stay)."""
