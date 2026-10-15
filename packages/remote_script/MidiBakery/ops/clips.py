from ..protocol import ErrorCode, OpError
from ..registry import op


LAUNCH_MODES = {0: "trigger", 1: "gate", 2: "toggle", 3: "repeat"}
LAUNCH_MODE_TOGGLE = 2
# Track.fired_slot_index while the track's Clip Stop button is fired, i.e. a quantized stop is pending.
STOP_PENDING = -2


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
        "is_triggered": clip.is_triggered,
        "launch_mode": LAUNCH_MODES.get(clip.launch_mode, clip.launch_mode),
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
    result = describe_clip(ctx.clip(params["track"], params["slot"]))
    track = ctx.track(params["track"])
    result["stop_pending"] = track.fired_slot_index == STOP_PENDING
    return result


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
        if not slot.has_clip:
            # fire() on an empty slot stops the track: almost always a wrong slot, not the intent.
            raise OpError(ErrorCode.NOT_FOUND, "Slot %d/%d is empty; nothing to play (action 'stop' stops the track)" % (params["track"], params["slot"]))
        _fire(ctx.song, ctx.track(params["track"]), slot)
    else:
        slot.stop()
    return {"track": params["track"], "slot": params["slot"]}


def _fire(song, track, slot):
    # fire() on a Toggle clip that is playing or triggered switches it off, the
    # opposite of what was asked. Live keeps a clip playing across a transport stop,
    # so such a clip only needs the transport. Live reads the launch mode when the
    # quantized launch happens, so switching it around fire() does not help.
    clip = slot.clip
    if clip.launch_mode == LAUNCH_MODE_TOGGLE and (clip.is_playing or clip.is_triggered):
        if track.fired_slot_index == STOP_PENDING:
            # A quantized stop is still pending (the transport stopped before it ran):
            # starting the transport would let it run. Stop now, then launch fresh.
            track.stop_all_clips(False)
            slot.fire()
            return
        if not song.is_playing:
            song.start_playing()
        return
    slot.fire()
