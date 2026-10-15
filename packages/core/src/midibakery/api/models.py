"""The model choices the chat offers: Default, Claude models and installed local models."""

from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx2 as httpx

from midibakery.agent.providers import ollama, openai_compat

CLAUDE_MODELS = (
    ("claude-sonnet-5-5", "Claude Sonnet 5.5"),
    ("claude-opus-5-5", "Claude Opus 5.5"),
    ("claude-haiku-5-5", "Claude Haiku 5.5"),
)
LOCAL_TIMEOUT = httpx.Timeout(1.5, connect=1.0)


def _base_url(env: str, default: str) -> str:
    url = (os.environ.get(env) or default).rstrip("/")
    if not url.startswith("http"):
        url = "http://" + url
    return url[:-3] if url.endswith("/v1") else url


async def _lmstudio(client: httpx.AsyncClient) -> list[str]:
    response = await client.get(f"{_base_url('LMSTUDIO_HOST', openai_compat.DEFAULT_URL)}/v1/models")
    response.raise_for_status()
    ids = [m.get("id", "") for m in response.json().get("data", [])]
    # Embedding models cannot chat.
    return sorted(i for i in ids if i and "embed" not in i.lower())


async def _ollama(client: httpx.AsyncClient) -> list[str]:
    response = await client.get(f"{_base_url('OLLAMA_HOST', ollama.DEFAULT_URL)}/api/tags")
    response.raise_for_status()
    names = [m.get("name", "") for m in response.json().get("models", [])]
    return sorted(n for n in names if n and "embed" not in n.lower())


async def list_models(default_provider: str, default_model: str, client: httpx.AsyncClient | None = None) -> list[dict[str, Any]]:
    """Choices as {provider, model, label}; provider "" with model "" is the API's own default.

    Local servers that are not running are skipped silently.
    """
    choices: list[dict[str, Any]] = [
        {"provider": "", "model": "", "label": f"Default ({default_provider} · {default_model})"},
    ]
    choices += [{"provider": "anthropic", "model": m, "label": label} for m, label in CLAUDE_MODELS]
    own = client is None
    client = client or httpx.AsyncClient(timeout=LOCAL_TIMEOUT)
    try:
        lmstudio, local_ollama = await asyncio.gather(_lmstudio(client), _ollama(client), return_exceptions=True)
    finally:
        if own:
            await client.aclose()
    if isinstance(lmstudio, list):
        choices += [{"provider": "lmstudio", "model": m, "label": f"LM Studio · {m}"} for m in lmstudio]
    if isinstance(local_ollama, list):
        choices += [{"provider": "ollama", "model": m, "label": f"Ollama · {m}"} for m in local_ollama]
    return choices
