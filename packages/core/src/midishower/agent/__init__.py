"""Agent loop: an LLM provider (Anthropic, Ollama or LM Studio) driving the MidiShower tools."""

from midishower.agent.loop import SMALL_SYSTEM_PROMPT, SYSTEM_PROMPT, Agent
from midishower.agent.providers import LOCAL_PROVIDERS, Provider, make_provider
from midishower.agent.tools import REDUCED_TOOLS, SMALL_TOOLS, ToolHost

__all__ = ["LOCAL_PROVIDERS", "REDUCED_TOOLS", "SMALL_SYSTEM_PROMPT", "SMALL_TOOLS", "SYSTEM_PROMPT", "Agent", "Provider", "ToolHost", "make_provider"]
