"""Wire protocol: newline-delimited JSON over a local TCP socket.

Client -> bridge:
    {"hello": <token>, "protocol": 1}              first line, authenticates
    {"id": 7, "op": "song.get", "params": {}, "timeout": 5.0}
Bridge -> client:
    {"hello": "ok", "protocol": 1, "bridge": "0.1.0", "live": [12, 4, 6]}
    {"id": 7, "ok": true, "result": {...}}
    {"id": 7, "ok": false, "error": {"code": "NOT_FOUND", "message": "...", "details": {...}}}
    {"event": "...", "data": {...}}                 unsolicited push (no id)
"""

import json
import os

PROTOCOL_VERSION = 1
BRIDGE_VERSION = "0.1.0"
MAX_LINE_BYTES = 4 * 1024 * 1024


class ErrorCode:
    UNAUTHORIZED = "UNAUTHORIZED"
    BAD_REQUEST = "BAD_REQUEST"
    UNKNOWN_OP = "UNKNOWN_OP"
    INVALID_PARAMS = "INVALID_PARAMS"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    UNSUPPORTED = "UNSUPPORTED"
    TIMEOUT = "TIMEOUT"
    LIVE_ERROR = "LIVE_ERROR"
    INTERNAL = "INTERNAL"


class OpError(Exception):
    def __init__(self, code, message, **details):
        Exception.__init__(self, message)
        self.code = code
        self.message = message
        self.details = details

    def to_wire(self):
        err = {"code": self.code, "message": self.message}
        if self.details:
            err["details"] = self.details
        return err


def encode(obj):
    return (json.dumps(obj, separators=(",", ":"), default=_default) + "\n").encode("utf-8")


def _default(value):
    # Live returns tuple-like vectors and its own number types.
    try:
        return list(value)
    except TypeError:
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return str(value)


def load_manifest():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "manifest.json")
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


_TYPE_CHECKS = {
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "string": lambda v: isinstance(v, str),
    "boolean": lambda v: isinstance(v, bool),
    "array": lambda v: isinstance(v, list),
    "object": lambda v: isinstance(v, dict),
    "null": lambda v: v is None,
}


def validate(manifest, op, params):
    """Boundary check against the generated manifest (names, required keys, primitive types)."""
    spec = manifest["ops"].get(op)
    if spec is None:
        raise OpError(ErrorCode.UNKNOWN_OP, "Unknown op '%s'" % op)
    if not isinstance(params, dict):
        raise OpError(ErrorCode.INVALID_PARAMS, "params must be an object")
    props = spec["properties"]
    unknown = sorted(set(params) - set(props))
    if unknown:
        raise OpError(ErrorCode.INVALID_PARAMS, "Unknown parameter(s): %s" % ", ".join(unknown), unknown=unknown)
    missing = [k for k in spec["required"] if k not in params]
    if missing:
        raise OpError(ErrorCode.INVALID_PARAMS, "Missing parameter(s): %s" % ", ".join(missing), missing=missing)
    for key, value in params.items():
        types = props[key]
        if types and not any(_TYPE_CHECKS[t](value) for t in types if t in _TYPE_CHECKS):
            raise OpError(
                ErrorCode.INVALID_PARAMS,
                "Parameter '%s' must be %s" % (key, " or ".join(types)),
                parameter=key,
            )
    return spec
