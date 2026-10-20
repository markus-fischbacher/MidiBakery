"""Agent loop: an LLM provider (Anthropic, Ollama or LM Studio) driving the MidiBakery tools."""

from midibakery.agent.loop import SMALL_SYSTEM_PROMPT, SYSTEM_PROMPT, Agent, without_tools
from midibakery.agent.providers import LOCAL_PROVIDERS, Provider, make_provider
from midibakery.agent.tools import LOCAL_HIDDEN, REDUCED_TOOLS, SMALL_TOOLS, ToolHost

__all__ = ["LOCAL_HIDDEN", "LOCAL_PROVIDERS", "REDUCED_TOOLS", "SMALL_SYSTEM_PROMPT", "SMALL_TOOLS", "SYSTEM_PROMPT", "Agent", "Provider", "ToolHost", "make_provider", "without_tools"]
