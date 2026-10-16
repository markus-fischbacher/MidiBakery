"""Wire protocol: newline-delimited JSON over a local TCP socket.

Client -> bridge:
    {"hello": <token>, "protocol": 1}              first line, authenticates
    {"id": 7, "op": "song.get", "params": {}, "timeout": 5.0}
    {"subscribe": ["state"]}                        push these events to me (replaces earlier topics)
Bridge -> client:
    {"hello": "ok", "protocol": 1, "bridge": "0.1.0", "live": [12, 4, 6]}
    {"id": 7, "ok": true, "result": {...}}
    {"id": 7, "ok": false, "error": {"code": "NOT_FOUND", "message": "...", "details": {...}}}
    {"subscribed": ["state"]}
    {"event": "...", "data": {...}}                 unsolicited push (no id), only for subscribed topics
"""

import json
import os

PROTOCOL_VERSION = 1
BRIDGE_VERSION = "0.2.0"
TOPICS = ("state",)
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
    """Boundary check against the generated manifest: a reduced JSON Schema per op (types, bounds,
    enums, nested objects and lists, alternatives). Errors name the path, e.g. 'add[3].pitch'."""
    spec = manifest["ops"].get(op)
    if spec is None:
        raise OpError(ErrorCode.UNKNOWN_OP, "Unknown op '%s'" % op)
    if not isinstance(params, dict):
        raise OpError(ErrorCode.INVALID_PARAMS, "params must be an object")
    _check(spec["params"], params, "", manifest.get("defs", {}))
    return spec


def _where(path):
    return " in '%s'" % path if path else ""


def _invalid(path, message, **details):
    return OpError(ErrorCode.INVALID_PARAMS, "Parameter '%s' %s" % (path, message), parameter=path, **details)


def _describe(node, defs):
    node = defs.get(node["$ref"], {}) if "$ref" in node else node
    if "anyOf" in node:
        return " or ".join(_describe(sub, defs) for sub in node["anyOf"])
    if "const" in node:
        return repr(node["const"])
    return " or ".join(node.get("type", ["any value"]))


def _check(node, value, path, defs):
    if "$ref" in node:
        node = defs[node["$ref"]]
    if "anyOf" in node:
        _check_any(node["anyOf"], value, path, defs)
        return
    types = node.get("type")
    if types and not any(_TYPE_CHECKS[t](value) for t in types if t in _TYPE_CHECKS):
        raise _invalid(path, "must be %s" % " or ".join(types))
    if "const" in node and value != node["const"]:
        raise _invalid(path, "must be %r" % node["const"])
    if "enum" in node and value not in node["enum"]:
        raise _invalid(path, "must be one of %s" % ", ".join(repr(v) for v in node["enum"]))
    if _TYPE_CHECKS["number"](value):
        if "minimum" in node and value < node["minimum"]:
            raise _invalid(path, "must be at least %g" % node["minimum"])
        if "maximum" in node and value > node["maximum"]:
            raise _invalid(path, "must be at most %g" % node["maximum"])
        if "exclusiveMinimum" in node and value <= node["exclusiveMinimum"]:
            raise _invalid(path, "must be more than %g" % node["exclusiveMinimum"])
        if "exclusiveMaximum" in node and value >= node["exclusiveMaximum"]:
            raise _invalid(path, "must be less than %g" % node["exclusiveMaximum"])
    if isinstance(value, str):
        if len(value) < node.get("minLength", 0):
            raise _invalid(path, "must have at least %d characters" % node["minLength"])
        if "maxLength" in node and len(value) > node["maxLength"]:
            raise _invalid(path, "must have at most %d characters" % node["maxLength"])
    if isinstance(value, list):
        if len(value) < node.get("minItems", 0):
            raise _invalid(path, "needs at least %d item(s)" % node["minItems"])
        if "maxItems" in node and len(value) > node["maxItems"]:
            raise _invalid(path, "takes at most %d item(s)" % node["maxItems"])
        if "items" in node:
            for i, item in enumerate(value):
                _check(node["items"], item, "%s[%d]" % (path, i), defs)
    if isinstance(value, dict) and ("properties" in node or "required" in node):
        props = node.get("properties", {})
        if node.get("additionalProperties") is False:
            unknown = sorted(set(value) - set(props))
            if unknown:
                raise OpError(ErrorCode.INVALID_PARAMS, "Unknown parameter(s)%s: %s" % (_where(path), ", ".join(unknown)),
                              unknown=unknown, parameter=path or None)
        missing = [k for k in node.get("required", []) if k not in value]
        if missing:
            raise OpError(ErrorCode.INVALID_PARAMS, "Missing parameter(s)%s: %s" % (_where(path), ", ".join(missing)),
                          missing=missing, parameter=path or None)
        for key, item in value.items():
            if key in props:
                _check(props[key], item, "%s.%s" % (path, key) if path else key, defs)


def _check_any(alternatives, value, path, defs):
    """One alternative must fit. An object whose 'action' (or other const field) picks an
    alternative gets that alternative's error; otherwise the error lists what fits."""
    errors = []
    for sub in alternatives:
        try:
            _check(sub, value, path, defs)
            return
        except OpError as err:
            errors.append((sub, err))
    if isinstance(value, dict):
        choices = {}
        for sub, err in errors:
            node = defs.get(sub["$ref"], {}) if "$ref" in sub else sub
            consts = [(k, p["const"]) for k, p in node.get("properties", {}).items() if "const" in p]
            if consts and all(value.get(k) == c for k, c in consts):
                raise err
            for k, c in consts:
                choices.setdefault(k, []).append(c)
        for key, values in choices.items():
            if len(values) == len(alternatives):  # every alternative is picked by this field
                where = "%s.%s" % (path, key) if path else key
                raise _invalid(where, "must be one of %s" % ", ".join(repr(v) for v in values))
    fitting = [(sub, err) for sub, err in errors if _describe(sub, defs) != "null"]
    if len(fitting) == 1:
        raise fitting[0][1]  # e.g. a number or null: the number's own error
    raise _invalid(path, "must be %s" % _describe({"anyOf": alternatives}, defs))
