"""Mixer and routing of tracks, return tracks and the master track."""

import re

from ..protocol import ErrorCode, OpError
from ..registry import op

CROSSFADE = {0: "A", 1: "none", 2: "B"}
CROSSFADE_VALUES = {v: k for k, v in CROSSFADE.items()}
_DB = re.compile(r"^\s*(-?inf|[-+]?\d+(?:\.\d+)?)\s*dB", re.IGNORECASE)
RETURN_LETTERS = "ABCDEFGHIJKL"


def _target(ctx, params):
    """(kind, index, track) for exactly one of track / return_track / master."""
    song = ctx.song
    if params.get("master"):
        return "master", None, song.master_track
    if params.get("return_track") is not None:
        index = params["return_track"]
        returns = song.return_tracks
        if not 0 <= index < len(returns):
            raise OpError(ErrorCode.NOT_FOUND, "No return track %d (song has %d)" % (index, len(returns)), return_track=index)
        return "return", index, returns[index]
    if params.get("track") is not None:
        return "track", params["track"], ctx.track(params["track"])
    raise OpError(ErrorCode.INVALID_PARAMS, "Give track, return_track or master")


def _display(param, value=None):
    try:
        return param.str_for_value(param.value if value is None else value)
    except Exception:
        return None


def _db_of(param, value):
    match = _DB.match(_display(param, value) or "")
    if not match:
        return None
    text = match.group(1).lower()
    return float("-inf") if text.endswith("inf") else float(text)


def value_for_db(param, db):
    """The fader value Live shows as `db` dB: bisection over Live's own display, which rises with the value."""
    low, high = param.min, param.max
    if _db_of(param, high) is None:
        raise OpError(ErrorCode.UNSUPPORTED, "%s has no dB scale" % param.name)
    if db >= _db_of(param, high):
        return high
    if db <= (_db_of(param, low) or float("-inf")):
        return low
    floor = param.min
    for _ in range(40):
        middle = (low + high) / 2.0
        if (_db_of(param, middle) or float("-inf")) < db:
            low = middle
        else:
            high = middle
    reached = _db_of(param, high)
    if reached is not None and reached - db > 0.5:
        return floor  # quieter than the quietest finite step: -inf
    return high


def _level(param):
    return {"value": round(param.value, 4), "display": _display(param)}


def _routing(track):
    data = {}
    for key in ("input_routing_type", "input_routing_channel", "output_routing_type", "output_routing_channel"):
        try:
            data[key.replace("_type", "").replace("routing_", "")] = getattr(track, key).display_name
        except Exception:
            pass  # master has no input; group tracks have no own input
    return data


def _options(track):
    data = {}
    for key in ("input_routing_types", "input_routing_channels", "output_routing_types", "output_routing_channels"):
        try:
            data[key] = [entry.display_name for entry in getattr(track, "available_" + key)]
        except Exception:
            pass
    return data


def _describe(song, kind, index, track, options=False):
    mixer = track.mixer_device
    data = {"kind": kind, "name": track.name, "volume": _level(mixer.volume), "pan": _level(mixer.panning)}
    if index is not None:
        data["index"] = index
    if kind != "master":
        data["mute"] = track.mute
        data["solo"] = track.solo
        data["sends"] = [
            dict(_level(send), return_track=i, name=_return_name(song, i))
            for i, send in enumerate(mixer.sends)
        ]
        try:
            data["crossfade"] = CROSSFADE.get(mixer.crossfade_assign, mixer.crossfade_assign)
        except Exception:
            pass
    data["routing"] = _routing(track)
    data["devices"] = [d.name for d in track.devices]  # e.g. which return holds the Reverb
    if options:
        data["options"] = _options(track)
    return data


def _return_name(song, index):
    returns = song.return_tracks
    return returns[index].name if index < len(returns) else RETURN_LETTERS[index % len(RETURN_LETTERS)]


@op("mixer.get")
def mixer_get(ctx, params):
    song = ctx.song
    if params.get("track") is not None or params.get("return_track") is not None or params.get("master"):
        kind, index, track = _target(ctx, params)
        return _describe(song, kind, index, track, options=bool(params.get("options")))
    if params.get("options"):
        raise OpError(ErrorCode.INVALID_PARAMS, "options needs a single track, return_track or master")
    return {
        "tracks": [_describe(song, "track", i, t) for i, t in enumerate(song.tracks)],
        "returns": [_describe(song, "return", i, t) for i, t in enumerate(song.return_tracks)],
        "master": _describe(song, "master", None, song.master_track),
    }


def _set_level(param, value=None, db=None):
    if db is not None:
        value = value_for_db(param, db)
    param.value = max(param.min, min(param.max, value))


def _pick(entries, wanted, what):
    for entry in entries:
        if entry.display_name == wanted:
            return entry
    names = ", ".join(e.display_name for e in entries)
    raise OpError(ErrorCode.NOT_FOUND, "No %s '%s'; available: %s" % (what, wanted, names), available=[e.display_name for e in entries])


@op("mixer.set")
def mixer_set(ctx, params):
    song = ctx.song
    kind, index, track = _target(ctx, params)
    mixer = track.mixer_device
    if kind == "master" and (params.get("sends") or any(params.get(k) is not None for k in ("mute", "solo", "crossfade"))):
        raise OpError(ErrorCode.INVALID_PARAMS, "The master track has no mute, solo, sends or crossfade assignment")
    if params.get("volume") is not None or params.get("volume_db") is not None:
        _set_level(mixer.volume, params.get("volume"), params.get("volume_db"))
    if params.get("pan") is not None:
        _set_level(mixer.panning, params["pan"])
    for send in params.get("sends") or []:
        sends = mixer.sends
        i = send["return_track"]
        if not 0 <= i < len(sends):
            raise OpError(ErrorCode.NOT_FOUND, "No send %d (song has %d return tracks)" % (i, len(sends)), return_track=i)
        _set_level(sends[i], send.get("value"), send.get("db"))
    for key in ("mute", "solo"):
        if params.get(key) is not None:
            setattr(track, key, params[key])
    if params.get("crossfade") is not None:
        mixer.crossfade_assign = CROSSFADE_VALUES[params["crossfade"]]
    # Type before channel: the channels on offer depend on the chosen type.
    for side in ("input", "output"):
        if params.get(side + "_routing") is not None:
            entry = _pick(getattr(track, "available_%s_routing_types" % side), params[side + "_routing"], side + " routing")
            setattr(track, side + "_routing_type", entry)
        if params.get(side + "_channel") is not None:
            entry = _pick(getattr(track, "available_%s_routing_channels" % side), params[side + "_channel"], side + " channel")
            setattr(track, side + "_routing_channel", entry)
    return _describe(song, kind, index, track)


@op("return.create")
def return_create(ctx, params):
    song = ctx.song
    device = params.get("device")
    if device and ctx.live_version < (12, 3, 0):
        raise OpError(ErrorCode.UNSUPPORTED, "Inserting a device needs Live 12.3 or newer")
    song.create_return_track()
    index = len(song.return_tracks) - 1
    track = song.return_tracks[index]
    if params.get("name"):
        track.name = params["name"]
    if device:
        try:
            track.insert_device(device, 0)
        except RuntimeError as exc:
            raise OpError(ErrorCode.NOT_FOUND, "Live could not insert '%s': %s" % (device, exc))
    return _describe(song, "return", index, track)
