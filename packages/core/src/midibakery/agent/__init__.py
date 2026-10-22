"""Agent loop: an LLM provider (Anthropic, Ollama or LM Studio) driving the MidiBakery tools."""

from midibakery.agent.loop import SYSTEM_PROMPT, Agent
from midibakery.agent.providers import LOCAL_PROVIDERS, Provider, make_provider
from midibakery.agent.tools import ToolHost

__all__ = ["LOCAL_PROVIDERS", "SYSTEM_PROMPT", "Agent", "Provider", "ToolHost", "make_provider"]
