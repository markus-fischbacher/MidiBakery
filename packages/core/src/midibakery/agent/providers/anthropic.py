"""Claude via the official Anthropic SDK: streaming, adaptive thinking, prompt caching."""

from __future__ import annotations

from typing import Any

import anthropic

from midibakery.agent.providers.base import Emit, Provider, ToolCall, ToolResult, Turn
from midibakery.agent.tools import ToolSpec

DEFAULT_MODEL = "claude-sonnet-5-5"
MODELS = ("claude-sonnet-5-5", "claude-opus-5-5")
FALLBACK_BETA = "server-side-fallback-2026-07-01"
JSON_RETRIES = 2


class AnthropicProvider(Provider):
    name = "anthropic"

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        effort: str = "medium",
        max_tokens: int = 32000,
        fallbacks: bool = True,
        client: Any | None = None,
    ):
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens
        # On a safety decline the API re-runs the request on a fallback model
        # chosen by refusal category (Claude API only).
        self.fallbacks = fallbacks
        if client is None:
            from midibakery.credentials import MissingKey, anthropic_key, status

            key = anthropic_key()
            if key is None and not status()["configured"]:
                raise MissingKey("Claude needs an API key: add it with the Key button or `midibakery auth set-key`")
            client = anthropic.AsyncAnthropic(api_key=key)  # None: the SDK uses an `ant auth login` profile
        self._client = client
        self._system: list[dict[str, Any]] = []
        self._tools: list[dict[str, Any]] = []
        self.messages: list[dict[str, Any]] = []

    def configure(self, system: str, tools: list[ToolSpec]) -> None:
        self._system = [{"type": "text", "text": system}]
        self._tools = [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
                # Inputs stream as generated; the MCP server validates them before anything runs.
                "eager_input_streaming": True,
            }
            for t in tools
        ]

    def add_user(self, text: str) -> None:
        self.messages.append({"role": "user", "content": text})

    def reset(self) -> None:
        self.messages = []

    def _request(self) -> dict[str, Any]:
        params: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": self._system,
            "tools": self._tools,
            "messages": self.messages,
            # Caches tools + system + history up to the last block; later turns read it.
            "cache_control": {"type": "ephemeral"},
            "thinking": {"type": "adaptive", "display": "summarized"},
            "output_config": {"effort": self.effort},
        }
        if self.fallbacks:
            params["betas"] = [FALLBACK_BETA]
            params["fallbacks"] = "default"
        return params

    def _stream(self):
        params = self._request()
        if self.fallbacks:
            return self._client.beta.messages.stream(**params)
        return self._client.messages.stream(**params)

    async def stream_turn(self, emit: Emit) -> Turn:
        retries = 0
        while True:
            try:
                async with self._stream() as stream:
                    async for event in stream:
                        if event.type != "content_block_delta":
                            continue
                        delta = event.delta
                        if delta.type == "text_delta":
                            await emit({"type": "text", "text": delta.text})
                        elif delta.type == "thinking_delta" and delta.thinking:
                            await emit({"type": "thinking", "text": delta.thinking})
                    message = await stream.get_final_message()
                break
            except ValueError:
                # Tool input JSON the SDK could not parse at all: no tool_use id
                # to answer, so re-issue the turn (bounded). API errors propagate.
                retries += 1
                if retries > JSON_RETRIES:
                    raise

        # Append-only history: the assistant turn exactly as returned.
        self.messages.append({"role": "assistant", "content": message.content})
        usage = _usage(message)
        text = "".join(b.text for b in message.content if b.type == "text")
        tool_uses = [b for b in message.content if b.type == "tool_use"]
        stop = message.stop_reason or "end_turn"

        if stop == "refusal":
            return Turn(stop, text=text, usage=usage, error="The model declined this request.")
        if stop == "max_tokens" and tool_uses:
            # A truncated tool input still parses as a partial object; never run it.
            self.messages.pop()
            return Turn(stop, text=text, usage=usage, error="The response was cut off before a tool call finished.")
        calls = [ToolCall(b.id, b.name, b.input) for b in tool_uses]
        return Turn(stop, calls, text, usage)

    def add_tool_results(self, results: list[ToolResult]) -> None:
        self.messages.append({
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": r.call_id, "content": r.content, "is_error": r.is_error}
                for r in results
            ],
        })


def _usage(message: Any) -> dict[str, Any]:
    usage = getattr(message, "usage", None)
    if usage is None:
        return {}
    keys = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
    data = {k: getattr(usage, k, None) for k in keys}
    data["model"] = getattr(message, "model", None)
    return {k: v for k, v in data.items() if v is not None}
