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
    device = ctx.device(params["track"], params["device"])
    return {
        "name": device.name,
        "class_name": device.class_name,
        "parameters": [_param_dict(i, p) for i, p in enumerate(device.parameters)],
    }


@op("device.set_param")
def device_set_param(ctx, params):
    device = ctx.device(params["track"], params["device"])
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
    value = params["value"]
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
