"""Local models via Ollama's /api/chat (streaming NDJSON with tool calls)."""

from __future__ import annotations

import copy
import itertools
import json
import os
from typing import Any

import httpx2 as httpx

from midishower.agent.providers.base import Emit, Provider, ToolCall, ToolResult, Turn
from midishower.agent.tools import ToolSpec

DEFAULT_MODEL = "qwen3:8b"
DEFAULT_URL = "http://127.0.0.1:11434"


def inline_refs(schema: dict[str, Any]) -> dict[str, Any]:
    """Resolve local $ref/$defs: many local models and Ollama templates ignore references."""
    defs = schema.get("$defs", {})

    def resolve(node: Any, seen: tuple[str, ...] = ()) -> Any:
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/$defs/"):
                name = ref.rsplit("/", 1)[-1]
                if name in seen:
                    return {"type": "object"}  # recursive model: stop expanding
                merged = {**copy.deepcopy(defs.get(name, {})), **{k: v for k, v in node.items() if k != "$ref"}}
                return resolve(merged, seen + (name,))
            return {k: resolve(v, seen) for k, v in node.items() if k != "$defs"}
        if isinstance(node, list):
            return [resolve(v, seen) for v in node]
        return node

    return resolve(schema)


class OllamaProvider(Provider):
    name = "ollama"

    def __init__(self, model: str = DEFAULT_MODEL, base_url: str | None = None, client: httpx.AsyncClient | None = None, think: bool = False):
        self.model = model
        self.base_url = (base_url or os.environ.get("OLLAMA_HOST") or DEFAULT_URL).rstrip("/")
        if not self.base_url.startswith("http"):
            self.base_url = "http://" + self.base_url
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=5.0))
        self.think = think
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
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": self._system}, *self.messages],
            "tools": self._tools,
            "stream": True,
            "think": self.think,
        }
        text_parts: list[str] = []
        calls: list[ToolCall] = []
        raw_calls: list[dict[str, Any]] = []
        usage: dict[str, Any] = {}
        try:
            async with self._client.stream("POST", f"{self.base_url}/api/chat", json=body) as response:
                if response.status_code >= 400:
                    detail = (await response.aread()).decode(errors="replace")
                    return Turn("error", error=f"Ollama returned {response.status_code}: {detail[:300]}")
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    chunk = json.loads(line)
                    if chunk.get("error"):
                        return Turn("error", error=f"Ollama: {chunk['error']}")
                    message = chunk.get("message") or {}
                    if message.get("thinking"):
                        await emit({"type": "thinking", "text": message["thinking"]})
                    if message.get("content"):
                        text_parts.append(message["content"])
                        await emit({"type": "text", "text": message["content"]})
                    for call in message.get("tool_calls") or []:
                        fn = call.get("function") or {}
                        arguments = fn.get("arguments")
                        if isinstance(arguments, str):
                            try:
                                arguments = json.loads(arguments)
                            except ValueError:
                                pass  # passed on as-is; the tool host reports it as invalid
                        raw_calls.append(call)
                        calls.append(ToolCall(f"call_{next(self._ids)}", fn.get("name", ""), arguments))
                    if chunk.get("done"):
                        usage = {"input_tokens": chunk.get("prompt_eval_count"), "output_tokens": chunk.get("eval_count"), "model": self.model}
        except httpx.ConnectError:
            return Turn("error", error=f"Cannot reach Ollama at {self.base_url}. Is `ollama serve` running?")

        text = "".join(text_parts)
        assistant: dict[str, Any] = {"role": "assistant", "content": text}
        if raw_calls:
            assistant["tool_calls"] = raw_calls
        self.messages.append(assistant)
        return Turn("tool_use" if calls else "end_turn", calls, text, {k: v for k, v in usage.items() if v is not None})

    def add_tool_results(self, results: list[ToolResult]) -> None:
        for r in results:
            content = ("ERROR: " + r.content) if r.is_error else r.content
            self.messages.append({"role": "tool", "content": content, "tool_name": r.name})
