"""Clip automation: targets, shapes and units, shared by `arrangement.edit` (add_clip) and `clip.envelope`.

A target is a parameter of a device on the clip's track (into racks with chain_path) or,
without a device, of the track's mixer: "Volume", "Pan", "Send A", "Send B", ...
Values are 0-1 of the parameter's range, or with unit "display" in the units Live shows,
in base units: Hz, s, dB, %. Shapes become points here, so the bridge carries a few
numbers instead of hundreds of points.
"""

import math
import re

from ..protocol import ErrorCode, OpError
from ..registry import op

EPSILON = 1e-6
JUMP = 0.01  # beats between the two points of a jump: Live keeps one value per time
MAX_POINTS = 2048
TABLE_SIZE = 512
_NUMBER = re.compile(r"^\s*(-?inf|[-+]?\d+(?:\.\d+)?)\s*([kmM]?)(Hz|s|ms|dB|%)?", re.IGNORECASE)
SEND_NAME = re.compile(r"^Send ([A-L])$")


def _mixer_param(track, name):
    mixer = track.mixer_device
    if name == "Volume":
        return mixer.volume
    if name == "Pan":
        return mixer.panning
    match = SEND_NAME.match(name)
    if match:
        index = ord(match.group(1)) - ord("A")
        sends = list(mixer.sends)
        if index < len(sends):
            return sends[index]
    return None


def _target(ctx, track, i, env):
    name = env["parameter"]
    if env.get("device") is None:
        param = _mixer_param(track, name)
        if param is None:
            sends = ["Send %s" % chr(ord("A") + k) for k in range(len(list(track.mixer_device.sends)))]
            raise OpError(ErrorCode.NOT_FOUND, "envelopes[%d]: the mixer has no '%s'" % (i, name), available=["Volume", "Pan"] + sends)
        return param
    devices = list(track.devices)
    index = env["device"]
    if not 0 <= index < len(devices):
        raise OpError(ErrorCode.NOT_FOUND, "envelopes[%d]: no device %d on the track (it has %d)" % (i, index, len(devices)))
    device = devices[index]
    path = list(env.get("chain_path") or ())
    if len(path) % 2:
        raise OpError(ErrorCode.INVALID_PARAMS, "envelopes[%d]: chain_path needs chain, device pairs" % i)
    for chain_index, inner_index in zip(path[0::2], path[1::2]):
        inner = list(ctx.chain(device, chain_index).devices)
        if not 0 <= inner_index < len(inner):
            raise OpError(ErrorCode.NOT_FOUND, "envelopes[%d]: no device %d in chain %d of '%s'" % (i, inner_index, chain_index, device.name))
        device = inner[inner_index]
    param = next((p for p in device.parameters if p.name == name), None)
    if param is None:
        raise OpError(ErrorCode.NOT_FOUND, "envelopes[%d]: device '%s' has no parameter '%s'" % (i, device.name, name),
                      available=[p.name for p in device.parameters][:60])
    return param


def _shape_points(shape):
    """Points (beat, value) of one shape. Ramps go from_value -> to_value; the waves swing
    between them every `period` beats, starting at from_value."""
    kind, start, length = shape["type"], float(shape["start"]), float(shape["length"])
    a, b = float(shape["from_value"]), float(shape["to_value"])
    end = start + length
    if kind in ("ramp", "exp", "log"):
        if kind == "ramp":
            return [(start, a), (end, b)]
        count = max(8, min(64, int(length * 4)))  # a curve as 16th lines, at least 8
        points = []
        for k in range(count + 1):
            x = k / float(count)
            f = (math.exp(4 * x) - 1) / (math.exp(4) - 1)  # slow start, fast end
            if kind == "log":
                f = 1 - (math.exp(4 * (1 - x)) - 1) / (math.exp(4) - 1)
            points.append((start + x * length, a + (b - a) * f))
        return points
    period = float(shape.get("period") or 4.0)
    points = []
    cycle = start
    while cycle < end - EPSILON:
        top = min(end, cycle + period)
        if kind == "sine":
            steps = max(8, int(round(period * 4)))
            for k in range(steps):
                t = cycle + period * k / float(steps)
                if t >= end - EPSILON:
                    break
                points.append((t, a + (b - a) * (1 - math.cos(2 * math.pi * k / steps)) / 2))
        elif kind == "triangle":
            points.append((cycle, a))
            if cycle + period / 2 < end:
                points.append((cycle + period / 2, b))
        elif kind == "saw":
            points += [(cycle, a), (top - JUMP, a + (b - a) * (top - JUMP - cycle) / period)]
        elif kind == "square":
            half = min(end, cycle + period / 2)
            points += [(cycle, a), (half - JUMP, a)]
            if half < end - EPSILON:
                points += [(half, b), (top - JUMP, b)]
        else:
            raise OpError(ErrorCode.INVALID_PARAMS, "Unknown shape '%s'" % kind)
        cycle += period
        if len(points) > MAX_POINTS:
            raise OpError(ErrorCode.INVALID_PARAMS, "Shape '%s' needs more than %d points; use a longer period" % (kind, MAX_POINTS))
    last = (end - start) / period % 1.0
    if kind == "sine":
        points.append((end, a + (b - a) * (1 - math.cos(2 * math.pi * last)) / 2))
    elif kind == "triangle":
        x = last if last > EPSILON else 1.0
        points.append((end, a + (b - a) * (1 - abs(2 * x - 1))))
    return points


def _display_number(param, value):
    """The number Live shows for a raw value, in base units (Hz, s, dB, %); None if it shows none."""
    try:
        text = param.str_for_value(value)
    except Exception:
        return None
    match = _NUMBER.match(text or "")
    if not match:
        return None
    number = match.group(1).lower()
    if number.endswith("inf"):
        return float("-inf") if number.startswith("-") else float("inf")
    x = float(number)
    prefix, unit = match.group(2), (match.group(3) or "").lower()
    if prefix == "k":
        x *= 1000.0
    if unit == "ms" or prefix == "m" and unit == "s":  # the regex reads "ms" as milli + s
        x /= 1000.0
    return x


class _Units(object):
    """Display value -> raw value for one parameter: a table of Live's own display, interpolated."""

    def __init__(self, param, i):
        self.param = param
        span = param.max - param.min
        raws = [param.min + span * k / float(TABLE_SIZE) for k in range(TABLE_SIZE + 1)]
        table = [(_display_number(param, r), r) for r in raws]
        if any(shown is None for shown, _ in table):
            raise OpError(ErrorCode.INVALID_PARAMS, "envelopes[%d]: '%s' shows no number; use unit 'fraction'" % (i, param.name))
        if table[0][0] > table[-1][0]:
            table.reverse()
        self.table = table

    def raw(self, shown):
        table = self.table
        if shown <= table[0][0]:
            return table[0][1]
        if shown >= table[-1][0]:
            return table[-1][1]
        for (d0, r0), (d1, r1) in zip(table, table[1:]):
            if d0 <= shown <= d1:
                if d0 == float("-inf") or d1 - d0 < EPSILON:
                    return r1
                return r0 + (r1 - r0) * (shown - d0) / (d1 - d0)
        return table[-1][1]


def resolve(ctx, track, envelopes):
    """(parameter, points as 0-1 fractions) per envelope."""
    resolved = []
    for i, env in enumerate(envelopes):
        param = _target(ctx, track, i, env)
        points = [(float(t), float(v)) for t, v in env.get("points") or ()]
        for shape in env.get("shapes") or ():
            points += _shape_points(shape)
        if not points:
            raise OpError(ErrorCode.INVALID_PARAMS, "envelopes[%d]: no points or shapes" % i)
        if len(points) > MAX_POINTS:
            raise OpError(ErrorCode.INVALID_PARAMS, "envelopes[%d]: %d points, at most %d" % (i, len(points), MAX_POINTS))
        span = param.max - param.min
        if env.get("unit") == "display":
            units = _Units(param, i)
            points = [(t, (units.raw(v) - param.min) / span if span else 0.0) for t, v in points]
        points = sorted(((t, min(1.0, max(0.0, v))) for t, v in points), key=lambda p: p[0])
        resolved.append((param, points))
    return resolved


def raw(param, fraction):
    value = param.min + fraction * (param.max - param.min)
    return float(round(value)) if param.is_quantized else value


def write(clip, param, points, length, clear=True):
    """Breakpoints where Live has create_event, else 16th steps along the lines between them
    (Live 12.4 has only insert_step). clear: an existing envelope is emptied first."""
    env = clip.automation_envelope(param)
    if env is not None and clear:
        clip.clear_envelope(param)
        env = None
    env = env or clip.create_automation_envelope(param)
    if env is None:
        raise OpError(ErrorCode.LIVE_ERROR, "Live did not create an envelope for '%s'" % param.name)
    if param.is_quantized or not hasattr(env, "create_event"):
        _write_steps(env, param, points, length)
        return "steps"
    try:
        if clear and points[0][0] > 0:  # hold the first value from the clip start
            env.create_event(0.0, raw(param, points[0][1]))
        for t, v in points:
            if t <= length + EPSILON:
                env.create_event(max(0.0, t), raw(param, v))
        if clear and points[-1][0] < length:
            env.create_event(length, raw(param, points[-1][1]))
    except Exception:  # an unknown signature in this Live build: fall back to steps
        _write_steps(env, param, points, length)
        return "steps"
    return "events"


def _value(points, t):
    if t <= points[0][0]:
        return points[0][1]
    for (t0, v0), (t1, v1) in zip(points, points[1:]):
        if t <= t1:
            return v0 if t1 - t0 < EPSILON else v0 + (v1 - v0) * (t - t0) / (t1 - t0)
    return points[-1][1]


def _write_steps(env, param, points, length):
    step, t = 0.25, 0.0
    while t < length - EPSILON:
        env.insert_step(t, min(step, length - t), raw(param, _value(points, t)))
        t += step


def _readback(clip, param, length):
    """What Live plays at the start, each quarter and the end: a check, in Live's display.
    Sampled inside a 16th: at a step's border Live answers with the step before."""
    env = clip.automation_envelope(param)
    if env is None:
        return None
    shown = []
    for k in range(5):
        t = min(length - 0.125, length * k / 4.0 + 0.125)
        try:
            shown.append(param.str_for_value(env.value_at_time(t)))
        except Exception:
            return None
    return shown


def _rebuild(ctx, track_index, clip, resolved):
    """Live neither creates, reads nor extends envelopes on an arrangement clip: build the clip
    again in a session slot with its notes and the given envelopes, and put it back.
    Returns the new clip and, per envelope, the write mode and a check read on the session copy."""
    from .arrangement import _free_slot
    from .notes import _all_notes, _make_spec, _note_dict

    track = ctx.track(track_index)
    start, length = clip.start_time, clip.end_time - clip.start_time
    if not clip.is_midi_clip:
        raise OpError(ErrorCode.UNSUPPORTED, "Envelopes on arrangement audio clips are not supported; use a session clip")
    if abs(clip.loop_start) > EPSILON or abs(clip.start_marker) > EPSILON or abs(clip.length - length) > EPSILON:
        raise OpError(ErrorCode.UNSUPPORTED, "This arrangement clip is trimmed or repeats its loop; envelopes need a clip that plays its notes once from the start")
    notes = [_note_dict(n) for n in _all_notes(clip)]
    name, color = clip.name, clip.color_index
    index, scene = _free_slot(ctx, track)
    slot = track.clip_slots[index]
    try:
        slot.create_clip(length)
        copy = slot.clip
        copy.name = name
        copy.color_index = color
        if notes:
            copy.add_new_notes(tuple(_make_spec(n) for n in notes))
        written = [(write(copy, param, points, length), _readback(copy, param, length)) for param, points in resolved]
        track.delete_clip(clip)
        track.duplicate_clip_to_arrangement(copy, start)
    finally:
        if slot.has_clip:
            slot.delete_clip()
        if scene is not None:
            ctx.song.delete_scene(scene)
    placed = next(c for c in ctx.arrangement_clips(track_index) if abs(c.start_time - start) < EPSILON)
    return placed, written


@op("clip.envelope")
def clip_envelope(ctx, params):
    """Write envelopes onto an existing clip; `clear` (default) replaces what the parameter had.
    An arrangement clip is rebuilt with only the envelopes given: Live hides the ones it has."""
    track = ctx.track(params["track"])
    clip = ctx.clip_at(params)
    resolved = resolve(ctx, track, params["envelopes"])
    if getattr(clip, "is_arrangement_clip", False):
        if not params.get("replace_envelopes"):
            # has_envelopes answers False there too (Live 12.4.6), so any envelope it has would go unseen.
            raise OpError(
                ErrorCode.CONFLICT,
                "Live shows no script the envelopes of an arrangement clip, not even whether it has any: writing "
                "rebuilds the clip from its notes with only the envelopes you give. Pass replace_envelopes=true "
                "with every envelope it should keep (a song's clips have its filter sweep).",
            )
        clip, written = _rebuild(ctx, params["track"], clip, resolved)
        length = clip.end_time - clip.start_time
    else:
        length = clip.loop_end - clip.loop_start if clip.looping else clip.length
        try:
            written = [(write(clip, param, points, length, params.get("clear", True)), _readback(clip, param, length)) for param, points in resolved]
        except RuntimeError as exc:
            raise OpError(ErrorCode.LIVE_ERROR, "Live refused an envelope on this clip: %s" % exc)
    results = [
        {"parameter": param.name, "points": len(points), "mode": mode, "check": check}
        for (param, points), (mode, check) in zip(resolved, written)
    ]
    data = {"track": params["track"], "clip": clip.name, "length": length, "envelopes": results}
    if getattr(clip, "is_arrangement_clip", False):
        data["rebuilt"] = "the arrangement clip was rebuilt through a session slot with these envelopes only"
    return data
