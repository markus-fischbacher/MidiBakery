"""Racks: chains, their mixer and devices, drum pad notes, and macros."""

from ..protocol import ErrorCode, OpError
from ..registry import op
from .mixer import _display, _set_level

RACK_KINDS = {
    "InstrumentGroupDevice": "instrument",
    "AudioEffectGroupDevice": "audio_effect",
    "MidiEffectGroupDevice": "midi_effect",
    "DrumGroupDevice": "drum",
}


def _rack(ctx, params):
    device = ctx.device(params["track"], params["device"], params.get("chain_path"))
    if not getattr(device, "can_have_chains", False):
        raise OpError(ErrorCode.INVALID_PARAMS, "'%s' is not a rack" % device.name)
    return device


def _macros(rack):
    """Macro n is parameter n (parameter 0 is Device On); only the visible ones."""
    count = getattr(rack, "visible_macro_count", 8)
    parameters = list(rack.parameters)
    return [
        {"macro": n, "name": parameters[n].name, "value": round(parameters[n].value, 3), "display": _display(parameters[n])}
        for n in range(1, min(count, len(parameters) - 1) + 1)
    ]


def _chain(index, chain):
    data = {
        "index": index,
        "name": chain.name,
        "mute": chain.mute,
        "solo": chain.solo,
        "devices": [
            {"index": i, "name": d.name, "class_name": d.class_name, "is_rack": bool(getattr(d, "can_have_chains", False))}
            for i, d in enumerate(chain.devices)
        ],
    }
    mixer = getattr(chain, "mixer_device", None)
    if mixer is not None:
        data["volume"] = _display(mixer.volume)
        data["pan"] = _display(mixer.panning)
    if hasattr(chain, "in_note"):
        data["in_note"] = int(chain.in_note)  # Drum Rack (Live 12.3+): the pad note that plays the chain
    return data


def describe_rack(rack):
    return {
        "name": rack.name,
        "class_name": rack.class_name,
        "kind": RACK_KINDS.get(rack.class_name, "rack"),
        "macros": _macros(rack),
        "chains": [_chain(i, c) for i, c in enumerate(rack.chains)],
    }


@op("rack.get")
def rack_get(ctx, params):
    return describe_rack(_rack(ctx, params))


def _insert_devices(chain, names):
    if not names:
        return
    if not hasattr(chain, "insert_device"):
        raise OpError(ErrorCode.UNSUPPORTED, "This Live version cannot insert devices into rack chains")
    for name in names:
        try:
            chain.insert_device(name, len(chain.devices))
        except RuntimeError as exc:
            raise OpError(ErrorCode.NOT_FOUND, "Live could not insert '%s' into chain '%s': %s" % (name, chain.name, exc))


def _edit_chain(chain, change):
    if change.get("name") is not None:
        chain.name = change["name"]
    for key in ("mute", "solo"):
        if change.get(key) is not None:
            setattr(chain, key, change[key])
    if change.get("volume_db") is not None:
        _set_level(chain.mixer_device.volume, db=change["volume_db"])
    if change.get("pan") is not None:
        _set_level(chain.mixer_device.panning, change["pan"])
    if change.get("in_note") is not None:
        if not hasattr(chain, "in_note"):
            raise OpError(ErrorCode.INVALID_PARAMS, "Only Drum Rack chains have a pad note (in_note, Live 12.3+)")
        chain.in_note = change["in_note"]
    _insert_devices(chain, change.get("insert_devices"))


@op("rack.set")
def rack_set(ctx, params):
    rack = _rack(ctx, params)
    parameters = list(rack.parameters)
    for macro in params.get("macros") or []:
        n = macro["macro"]
        if not 1 <= n < len(parameters):
            raise OpError(ErrorCode.NOT_FOUND, "No macro %d on '%s'" % (n, rack.name))
        param = parameters[n]
        param.value = max(param.min, min(param.max, macro["value"]))
    for change in params.get("chains") or []:
        _edit_chain(ctx.chain(rack, change["chain"]), change)
    added = params.get("add_chain")
    if added is not None:
        if not hasattr(rack, "insert_chain"):
            raise OpError(ErrorCode.UNSUPPORTED, "Adding rack chains needs Live 12.3 or newer")
        index = len(rack.chains)
        rack.insert_chain(index)
        _edit_chain(list(rack.chains)[index], added)
    return describe_rack(rack)
