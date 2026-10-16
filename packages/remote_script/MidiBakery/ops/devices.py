from ..protocol import ErrorCode, OpError
from ..registry import op


def _param_dict(index, param):
    data = {
        "index": index,
        "name": param.name,
        "value": param.value,
        "min": param.min,
        "max": param.max,
        "is_quantized": param.is_quantized,
        "is_enabled": param.is_enabled,
    }
    try:
        data["display"] = param.str_for_value(param.value)
    except Exception:
        data["display"] = str(param)
    if param.is_quantized:
        data["value_items"] = list(param.value_items)
    return data


@op("device.insert")
def device_insert(ctx, params):
    track = ctx.track(params["track"])
    index = params.get("index", -1)
    count = len(track.devices)
    if index == -1:
        index = count
    if index > count:
        raise OpError(ErrorCode.INVALID_PARAMS, "Device index %d beyond chain end (%d)" % (index, count))
    try:
        track.insert_device(params["name"], index)
    except RuntimeError as exc:
        raise OpError(ErrorCode.NOT_FOUND, "Live could not insert '%s': %s" % (params["name"], exc))
    device = track.devices[index]
    return {"device": index, "name": device.name, "class_name": device.class_name}


@op("device.params")
def device_params(ctx, params):
    device = ctx.device(params)
    return {
        "name": device.name,
        "class_name": device.class_name,
        "parameters": [_param_dict(i, p) for i, p in enumerate(device.parameters)],
    }


def _raw_for_display(param, shown):
    """The raw value Live shows as `shown`: an item of a switch, or a number (base units: s, Hz,
    dB, %) found by bisection over Live's own display."""
    from .envelopes import _display_number

    if isinstance(shown, str):
        items = list(param.value_items) if param.is_quantized else []
        if shown not in items:
            raise OpError(ErrorCode.INVALID_PARAMS, "'%s' shows no '%s'" % (param.name, shown), available=items)
        return param.min + items.index(shown)
    low, high = param.min, param.max
    first, last = _display_number(param, low), _display_number(param, high)
    if first is None or last is None:
        raise OpError(ErrorCode.INVALID_PARAMS, "'%s' shows no number; give value" % param.name)
    if first > last:
        low, high, first, last = high, low, last, first
    if shown <= first:
        return low
    if shown >= last:
        return high
    for _ in range(40):
        middle = (low + high) / 2.0
        if (_display_number(param, middle) or 0.0) < shown:
            low = middle
        else:
            high = middle
    return high


@op("device.set_param")
def device_set_param(ctx, params):
    device = ctx.device(params)
    key = params["parameter"]
    parameters = list(device.parameters)
    if isinstance(key, int):
        if not 0 <= key < len(parameters):
            raise OpError(ErrorCode.NOT_FOUND, "No parameter %d on '%s'" % (key, device.name))
        index = key
    else:
        matches = [i for i, p in enumerate(parameters) if p.name == key]
        if not matches:
            raise OpError(
                ErrorCode.NOT_FOUND,
                "No parameter named '%s' on '%s'" % (key, device.name),
                available=[p.name for p in parameters],
            )
        index = matches[0]
    param = parameters[index]
    value = params["value"] if params.get("display") is None else _raw_for_display(param, params["display"])
    if not param.min <= value <= param.max:
        raise OpError(
            ErrorCode.INVALID_PARAMS,
            "Value %s outside %s..%s for '%s'" % (value, param.min, param.max, param.name),
            min=param.min,
            max=param.max,
        )
    if not param.is_enabled:
        raise OpError(ErrorCode.CONFLICT, "Parameter '%s' is disabled (automated or mapped)" % param.name)
    param.value = value
    return _param_dict(index, param)


def _drum_racks(devices):
    """Drum Racks in a device list, one level into Instrument/Effect Rack chains."""
    for device in devices:
        if getattr(device, "can_have_drum_pads", False):
            yield device
        elif getattr(device, "can_have_chains", False):
            for chain in device.chains:
                for inner in chain.devices:
                    if getattr(inner, "can_have_drum_pads", False):
                        yield inner


def _pads(rack):
    pads = []
    chains = list(rack.chains)
    if chains and hasattr(chains[0], "in_note"):
        # Live 12.3+: DrumChain.in_note is the note that triggers the chain.
        for chain in chains:
            note = chain.in_note
            if 0 <= note <= 127:
                pads.append({"note": int(note), "name": chain.name})
    else:
        for pad in rack.drum_pads:
            if len(pad.chains):
                pads.append({"note": int(pad.note), "name": pad.name})
    pads.sort(key=lambda p: p["note"])
    return pads


@op("drum_rack.pads")
def drum_rack_pads(ctx, params):
    track = ctx.track(params["track"])
    index = params.get("device")
    if index is not None:
        device = ctx.device({"track": params["track"], "device": index})
        if not getattr(device, "can_have_drum_pads", False):
            raise OpError(ErrorCode.INVALID_PARAMS, "Device %d on track %d is not a Drum Rack" % (index, params["track"]))
        rack = device
    else:
        rack = next(_drum_racks(track.devices), None)
        if rack is None:
            raise OpError(ErrorCode.NOT_FOUND, "No Drum Rack on track %d" % params["track"], track=params["track"])
    return {"name": rack.name, "pads": _pads(rack)}


def _device_routing(device):
    data = {}
    for key in ("input_routing_type", "input_routing_channel"):
        try:
            data[key.replace("_routing_type", "").replace("_routing", "")] = getattr(device, key).display_name
        except Exception:
            pass
    data["available"] = {
        "inputs": [e.display_name for e in device.available_input_routing_types],
        "channels": [e.display_name for e in device.available_input_routing_channels],
    }
    return data


@op("device.routing")
def device_routing(ctx, params):
    """A device's sidechain input (Live 12.4 lets scripts route the Compressor's): read it, or
    set the source track and then its channel, the first of `channel` that Live offers."""
    device = ctx.device(params)
    if not hasattr(device, "available_input_routing_types"):
        raise OpError(ErrorCode.UNSUPPORTED, "'%s' has no sidechain input Live lets scripts route" % device.name,
                      attributes=sorted(a for a in dir(device) if "rout" in a.lower() or "side" in a.lower()))
    from .mixer import _pick  # one picker for track and device routing

    if params.get("input_track") is not None:
        source = ctx.track(params["input_track"])
        types = list(device.available_input_routing_types)
        match = [e for e in types if getattr(e, "attached_object", None) == source] or [e for e in types if e.display_name == source.name]
        if not match:
            raise OpError(ErrorCode.NOT_FOUND, "Track %d '%s' is no sidechain source (a MIDI track needs an instrument)" % (params["input_track"], source.name),
                          available=[e.display_name for e in types])
        device.input_routing_type = match[0]
    elif params.get("input") is not None:
        device.input_routing_type = _pick(device.available_input_routing_types, params["input"], "sidechain input")
    channel = params.get("channel")
    if channel is not None:
        wanted = [channel] if isinstance(channel, str) else list(channel)
        channels = list(device.available_input_routing_channels)
        found = next((e for name in wanted for e in channels if e.display_name == name), None)
        if found is None:
            raise OpError(ErrorCode.NOT_FOUND, "No sidechain channel %s" % " or ".join("'%s'" % w for w in wanted),
                          available=[e.display_name for e in channels][:40])
        device.input_routing_channel = found
    return {"name": device.name, **_device_routing(device)}
