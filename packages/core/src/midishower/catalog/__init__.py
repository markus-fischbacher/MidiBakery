"""Single source of truth for every operation the Live bridge understands.

Each op is declared once here. The Remote Script manifest, the MCP tools and
(later) the LLM tool definitions for the in-Live chat are all derived from it.
"""

from midishower.catalog.registry import OPS, OpSpec, get_op, manifest
from midishower.catalog import ops as _ops  # noqa: F401  (registers all ops)

__all__ = ["OPS", "OpSpec", "get_op", "manifest"]
