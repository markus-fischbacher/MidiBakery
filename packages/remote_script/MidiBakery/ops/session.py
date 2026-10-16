from ..protocol import BRIDGE_VERSION, PROTOCOL_VERSION, ErrorCode, OpError
from ..registry import index_of, op

_SONG_SETTABLE = (
    "tempo",
    "signature_numerator",
    "signature_denominator",
    "root_note",
    "scale_name",
    "scale_mode",
    "metronome",
    "loop",
    "loop_start",
    "loop_length",
)


@op("live.health")
def health(ctx, params):
    return {
        "bridge": BRIDGE_VERSION,
        "protocol": PROTOCOL_VERSION,
        "live": list(ctx.live_version),
        "ops": ctx.supported_ops,
    }


@op("song.get")
def song_get(ctx, params):
    song = ctx.song
    view = song.view
    result = {
        "tempo": song.tempo,
        "signature_numerator": song.signature_numerator,
        "signature_denominator": song.signature_denominator,
        "is_playing": song.is_playing,
        "record_mode": song.record_mode,
        "metronome": song.metronome,
        "current_song_time": song.current_song_time,
        "loop": song.loop,
        "loop_start": song.loop_start,
        "loop_length": song.loop_length,
        "track_count": len(song.tracks),
        "return_track_count": len(song.return_tracks),
        "scene_count": len(song.scenes),
        "selected_track": index_of(song.tracks, view.selected_track),
        "selected_scene": index_of(song.scenes, view.selected_scene),
    }
    # Song scale properties: root_note/scale_name since Live 9, scale_mode 12.0.5, intervals 12.
    for key in ("root_note", "scale_name", "scale_mode", "scale_intervals"):
        if hasattr(song, key):
            value = getattr(song, key)
            result[key] = list(value) if key == "scale_intervals" else value
    return result


@op("song.set")
def song_set(ctx, params):
    song = ctx.song
    changed = []
    for key in _SONG_SETTABLE:
        if key in params and params[key] is not None:
            if not hasattr(song, key):
                raise OpError(ErrorCode.UNSUPPORTED, "This Live version has no song.%s" % key)
            setattr(song, key, params[key])
            changed.append(key)
    return {"changed": changed}


@op("transport.control")
def transport(ctx, params):
    song = ctx.song
    action = params["action"]
    if action == "play":
        if params.get("from_beat") is not None:
            song.current_song_time = params["from_beat"]
        song.start_playing()
    elif action == "stop":
        song.stop_playing()
    elif action == "stop_clips":
        song.stop_all_clips()
    elif action == "continue":
        song.continue_playing()
    elif action == "toggle_record":
        song.record_mode = not song.record_mode
    else:
        raise OpError(ErrorCode.INVALID_PARAMS, "Unknown transport action '%s'" % action)
    return {"is_playing": song.is_playing, "record_mode": song.record_mode}


@op("history.step")
def history(ctx, params):
    song = ctx.song
    if params["action"] == "undo":
        if not song.can_undo:
            raise OpError(ErrorCode.CONFLICT, "Nothing to undo")
        song.undo()
    else:
        if not song.can_redo:
            raise OpError(ErrorCode.CONFLICT, "Nothing to redo")
        song.redo()
    return {"can_undo": song.can_undo, "can_redo": song.can_redo}


@op("scene.create")
def scene_create(ctx, params):
    song = ctx.song
    index = params.get("index", -1)
    if index > len(song.scenes):
        raise OpError(ErrorCode.INVALID_PARAMS, "Scene index %d is beyond the end (song has %d scenes)" % (index, len(song.scenes)))
    song.create_scene(index)
    new_index = len(song.scenes) - 1 if index == -1 else index
    if params.get("name"):
        song.scenes[new_index].name = params["name"]
    return {"scene": new_index}


@op("scene.fire")
def scene_fire(ctx, params):
    ctx.scene(params["scene"]).fire()
    return {"scene": params["scene"]}


@op("batch")
def batch(ctx, params, execute):
    """One undo step for the whole batch. Stops at the first failing op and
    reports what already ran; it does not auto-undo, because undoing when the
    batch made no undoable change would revert the user's previous action."""
    song = ctx.song
    results = []
    song.begin_undo_step()
    try:
        for i, item in enumerate(params["ops"]):
            if not isinstance(item, dict) or not isinstance(item.get("op"), str):
                raise OpError(ErrorCode.INVALID_PARAMS, "ops[%d] needs an 'op' string" % i, index=i)
            if item["op"] == "history.step":
                raise OpError(ErrorCode.INVALID_PARAMS, "history.step is not allowed inside a batch", index=i)
            try:
                results.append(execute(item["op"], item.get("params") or {}))
            except OpError as err:
                err.details.update({"index": i, "completed": results})
                raise
            except Exception as exc:
                raise OpError(ErrorCode.LIVE_ERROR, str(exc) or exc.__class__.__name__, index=i, completed=results)
    finally:
        song.end_undo_step()
    return {"results": results}
