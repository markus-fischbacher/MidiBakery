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


def _json_type(schema: dict[str, Any]) -> list[str]:
    """Reduce a property schema to the primitive JSON types the bridge checks."""
    if "type" in schema:
        t = schema["type"]
        return t if isinstance(t, list) else [t]
    if "anyOf" in schema:
        types: list[str] = []
        for sub in schema["anyOf"]:
            types.extend(_json_type(sub))
        return types
    if "$ref" in schema:
        return ["object"]
    if "enum" in schema:
        return ["string"]
    return []


def manifest() -> dict[str, Any]:
    """Compact contract consumed by the Remote Script for boundary validation.

    The Remote Script runs on Live's bundled Python without third-party
    packages, so it only checks names, required keys and primitive types;
    full validation happens in the core with Pydantic before sending.
    """
    ops: dict[str, Any] = {}
    for name in sorted(OPS):
        spec = OPS[name]
        schema = spec.params.model_json_schema()
        props = schema.get("properties", {})
        ops[name] = {
            "read_only": spec.read_only,
            "destructive": spec.destructive,
            "required": sorted(schema.get("required", [])),
            "properties": {k: _json_type(v) for k, v in sorted(props.items())},
            "min_live": list(spec.min_live),
        }
    return {"protocol": PROTOCOL_VERSION, "ops": ops}
