from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

# Manifest format version; bump when the wire contract changes incompatibly.
PROTOCOL_VERSION = 1


@dataclass(frozen=True)
class OpSpec:
    name: str
    params: type[BaseModel]
    summary: str
    read_only: bool
    destructive: bool = False
    # Seconds the client waits for a reply. Live drains its queue every ~100 ms.
    timeout: float = 5.0
    # Minimum Live version (major, minor, patch) the op needs.
    min_live: tuple[int, int, int] = (12, 0, 0)


OPS: dict[str, OpSpec] = {}


def register(spec: OpSpec) -> OpSpec:
    if spec.name in OPS:
        raise ValueError(f"duplicate op {spec.name!r}")
    OPS[spec.name] = spec
    return spec


def get_op(name: str) -> OpSpec:
    try:
        return OPS[name]
    except KeyError:
        raise KeyError(f"unknown op {name!r}") from None


# Schema keywords the Remote Script checks; titles, descriptions and defaults stay in the core.
_KEEP = ("type", "enum", "const", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
         "minItems", "maxItems", "minLength", "maxLength", "required")


def _compact(schema: dict[str, Any]) -> dict[str, Any]:
    """A JSON Schema reduced to what the bridge validates: types, bounds, enums, nested objects
    and lists, alternatives (anyOf / oneOf) and references into the shared defs."""
    if "$ref" in schema:
        return {"$ref": schema["$ref"].rsplit("/", 1)[-1]}
    out: dict[str, Any] = {k: schema[k] for k in _KEEP if k in schema}
    if isinstance(out.get("type"), str):
        out["type"] = [out["type"]]
    if "required" in out:
        out["required"] = sorted(out["required"])
    if "items" in schema:
        out["items"] = _compact(schema["items"])
    if "properties" in schema:
        out["properties"] = {k: _compact(v) for k, v in sorted(schema["properties"].items())}
    if schema.get("additionalProperties") is False:
        out["additionalProperties"] = False
    alternatives = schema.get("anyOf") or schema.get("oneOf")
    if alternatives:
        out["anyOf"] = [_compact(sub) for sub in alternatives]
    return out


def manifest() -> dict[str, Any]:
    """Compact contract consumed by the Remote Script for boundary validation.

    The Remote Script runs on Live's bundled Python without third-party packages, so it checks a
    reduced JSON Schema (MidiBakery/protocol.py); the core validates fully with Pydantic before
    sending, so this guards clients that talk to the bridge directly.
    """
    ops: dict[str, Any] = {}
    defs: dict[str, Any] = {}
    for name in sorted(OPS):
        spec = OPS[name]
        schema = spec.params.model_json_schema()
        for def_name, definition in schema.get("$defs", {}).items():
            compact = _compact(definition)
            if defs.setdefault(def_name, compact) != compact:
                raise ValueError(f"two different models are both called {def_name!r}")
        ops[name] = {
            "read_only": spec.read_only,
            "destructive": spec.destructive,
            "params": _compact(schema),
            "min_live": list(spec.min_live),
        }
    return {"protocol": PROTOCOL_VERSION, "defs": dict(sorted(defs.items())), "ops": ops}
