from ..protocol import ErrorCode, OpError
from ..registry import op


def describe_clip(clip):
    return {
        "name": clip.name,
        "length": clip.length,
        "is_midi": clip.is_midi_clip,
        "looping": clip.looping,
        "loop_start": clip.loop_start,
        "loop_end": clip.loop_end,
        "start_marker": clip.start_marker,
        "end_marker": clip.end_marker,
        "color_index": clip.color_index,
        "is_playing": clip.is_playing,
        "signature_numerator": clip.signature_numerator,
        "signature_denominator": clip.signature_denominator,
    }


@op("clip.create")
def clip_create(ctx, params):
    track = ctx.track(params["track"])
    slot = ctx.clip_slot(params["track"], params["slot"])
    if not track.has_midi_input:
        raise OpError(ErrorCode.INVALID_PARAMS, "Track %d is not a MIDI track" % params["track"])
    if slot.has_clip:
        raise OpError(ErrorCode.CONFLICT, "Slot %d/%d already has a clip" % (params["track"], params["slot"]))
    slot.create_clip(float(params.get("length", 4.0)))
    if params.get("name"):
        slot.clip.name = params["name"]
    return describe_clip(slot.clip)


@op("clip.get")
def clip_get(ctx, params):
    return describe_clip(ctx.clip(params["track"], params["slot"]))


@op("clip.set")
def clip_set(ctx, params):
    clip = ctx.clip(params["track"], params["slot"])
    loop_start = params.get("loop_start")
    loop_end = params.get("loop_end")
    start = clip.loop_start if loop_start is None else loop_start
    end = clip.loop_end if loop_end is None else loop_end
    if start >= end:
        raise OpError(ErrorCode.INVALID_PARAMS, "loop_start must be before loop_end")
    for key in ("name", "color_index", "looping"):
        if params.get(key) is not None:
            setattr(clip, key, params[key])
    # Order matters: Live rejects a loop_start beyond the current loop_end.
    if loop_end is not None and loop_end > clip.loop_end:
        clip.loop_end = loop_end
        if loop_start is not None:
            clip.loop_start = loop_start
    else:
        if loop_start is not None:
            clip.loop_start = loop_start
        if loop_end is not None:
            clip.loop_end = loop_end
    return describe_clip(clip)


@op("clip.delete")
def clip_delete(ctx, params):
    ctx.clip(params["track"], params["slot"])  # existence check
    ctx.clip_slot(params["track"], params["slot"]).delete_clip()
    return {"deleted": [params["track"], params["slot"]]}


@op("clip.launch")
def clip_launch(ctx, params):
    slot = ctx.clip_slot(params["track"], params["slot"])
    if params.get("action", "fire") == "fire":
        slot.fire()
    else:
        slot.stop()
    return {"track": params["track"], "slot": params["slot"]}
