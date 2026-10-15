"""LLM backends for the agent loop."""

from __future__ import annotations

from midishower.agent.providers.base import Provider, ToolCall, ToolResult, Turn

__all__ = ["Provider", "ToolCall", "ToolResult", "Turn", "make_provider"]


def make_provider(kind: str = "anthropic", model: str | None = None, **options) -> Provider:
    """`anthropic` (default model claude-sonnet-5-5) or `ollama` (local)."""
    if kind == "anthropic":
        from midishower.agent.providers.anthropic import DEFAULT_MODEL, AnthropicProvider

        return AnthropicProvider(model or DEFAULT_MODEL, **options)
    if kind == "ollama":
        from midishower.agent.providers.ollama import DEFAULT_MODEL, OllamaProvider

        return OllamaProvider(model or DEFAULT_MODEL, **options)
    raise ValueError(f"unknown provider {kind!r}; use 'anthropic' or 'ollama'")
