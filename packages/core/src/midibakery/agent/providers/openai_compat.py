"""Local models via an OpenAI-compatible /v1/chat/completions server (LM Studio).

Raw HTTP on purpose (no OpenAI SDK): streaming SSE with tool calls whose
arguments arrive as JSON-string fragments, joined per tool-call index.
"""

from __future__ import annotations

import itertools
import json
import os
from typing import Any

import httpx2 as httpx

from midibakery.agent.providers.base import Emit, Provider, ToolCall, ToolResult, Turn
from midibakery.agent.providers.ollama import inline_refs
from midibakery.agent.tools import ToolSpec

DEFAULT_MODEL = "google/gemma-4-e4b"
DEFAULT_URL = "http://127.0.0.1:1234"


class OpenAICompatProvider(Provider):
    name = "lmstudio"

    def __init__(self, model: str = DEFAULT_MODEL, base_url: str | None = None, client: httpx.AsyncClient | None = None):
        self.model = model
        self.base_url = (base_url or os.environ.get("LMSTUDIO_HOST") or DEFAULT_URL).rstrip("/")
        if not self.base_url.startswith("http"):
            self.base_url = "http://" + self.base_url
        if self.base_url.endswith("/v1"):
            self.base_url = self.base_url[:-3]
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=5.0))
        self._system = ""
        self._tools: list[dict[str, Any]] = []
        self.messages: list[dict[str, Any]] = []
        self._ids = itertools.count(1)

    def configure(self, system: str, tools: list[ToolSpec]) -> None:
        self._system = system
        self._tools = [
            {"type": "function", "function": {"name": t.name, "description": t.description, "parameters": inline_refs(t.input_schema)}}
            for t in tools
        ]

    def add_user(self, text: str) -> None:
        self.messages.append({"role": "user", "content": text})

    def reset(self) -> None:
        self.messages = []

    async def stream_turn(self, emit: Emit) -> Turn:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": self._system}, *self.messages],
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if self._tools:
            body["tools"] = self._tools
        text_parts: list[str] = []
        pending: dict[int, dict[str, Any]] = {}  # tool-call index -> {id, name, arguments}
        usage: dict[str, Any] = {}
        finish = "end_turn"
        try:
            async with self._client.stream("POST", f"{self.base_url}/v1/chat/completions", json=body) as response:
                if response.status_code >= 400:
                    detail = (await response.aread()).decode(errors="replace")
                    return Turn("error", error=f"LM Studio returned {response.status_code}: {detail[:300]}")
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if not data:
                        continue
                    if data == "[DONE]":
                        break
                    chunk = json.loads(data)
                    if chunk.get("error"):
                        error = chunk["error"]
                        return Turn("error", error=f"LM Studio: {error.get('message', error) if isinstance(error, dict) else error}")
                    if chunk.get("usage"):
                        u = chunk["usage"]
                        usage = {"input_tokens": u.get("prompt_tokens"), "output_tokens": u.get("completion_tokens"), "model": self.model}
                    for choice in chunk.get("choices") or []:
                        delta = choice.get("delta") or {}
                        reasoning = delta.get("reasoning_content") or delta.get("reasoning")
                        if reasoning:
                            await emit({"type": "thinking", "text": reasoning})
                        if delta.get("content"):
                            text_parts.append(delta["content"])
                            await emit({"type": "text", "text": delta["content"]})
                        for part in delta.get("tool_calls") or []:
                            slot = pending.setdefault(part.get("index", len(pending)), {"id": None, "name": "", "arguments": ""})
                            if part.get("id"):
                                slot["id"] = part["id"]
                            fn = part.get("function") or {}
                            if fn.get("name"):
                                slot["name"] += fn["name"]
                            if fn.get("arguments"):
                                slot["arguments"] += fn["arguments"] if isinstance(fn["arguments"], str) else json.dumps(fn["arguments"])
                        if choice.get("finish_reason") == "length":
                            finish = "max_tokens"
        except httpx.ConnectError:
            return Turn("error", error=f"Cannot reach LM Studio at {self.base_url}. Start the server (`lms server start` or the Developer tab) or set LMSTUDIO_HOST.")

        calls: list[ToolCall] = []
        raw_calls: list[dict[str, Any]] = []
        for index in sorted(pending):
            slot = pending[index]
            call_id = slot["id"] or f"call_{next(self._ids)}"
            arguments: Any = slot["arguments"] or "{}"
            try:
                arguments = json.loads(arguments)
            except ValueError:
                pass  # passed on as-is; the tool host reports it as invalid
            raw_calls.append({"id": call_id, "type": "function", "function": {"name": slot["name"], "arguments": slot["arguments"] or "{}"}})
            calls.append(ToolCall(call_id, slot["name"], arguments))

        text = "".join(text_parts)
        assistant: dict[str, Any] = {"role": "assistant", "content": text}
        if raw_calls:
            assistant["tool_calls"] = raw_calls
        self.messages.append(assistant)
        stop = "tool_use" if calls else finish
        return Turn(stop, calls, text, {k: v for k, v in usage.items() if v is not None})

    def add_tool_results(self, results: list[ToolResult]) -> None:
        for r in results:
            content = ("ERROR: " + r.content) if r.is_error else r.content
            self.messages.append({"role": "tool", "tool_call_id": r.call_id, "content": content})
