"""Agent loop: an LLM provider (Anthropic or Ollama) driving the MidiShower tools."""

from midishower.agent.loop import SYSTEM_PROMPT, Agent
from midishower.agent.providers import Provider, make_provider
from midishower.agent.tools import REDUCED_TOOLS, ToolHost

__all__ = ["REDUCED_TOOLS", "SYSTEM_PROMPT", "Agent", "Provider", "ToolHost", "make_provider"]
