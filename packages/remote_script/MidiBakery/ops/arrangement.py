"""Arrangement View: clips on the timeline, locators, and copying session clips there.

`arrangement.edit` runs clip actions as one undo step. Clips never land on top of
existing ones: an overlap is a CONFLICT, so nothing is overwritten unasked.

`arrangement.locators` runs across ticks: Live only sets a locator at the play
position, and a new play position takes effect on a later tick, not at once.
"""

from ..protocol import ErrorCode, OpError
from ..registry import op
from .notes import _make_spec, _validate_note

EPSILON = 1e-6
WAIT_TICKS = 30  # ~3 s at Live's ~100 ms tick


def _clip(index, clip):
    return {
        "index": index,
        "name": clip.name,
        "start": clip.start_time,
        "end": clip.end_time,
        "is_midi": clip.is_midi_clip,
    }


def _locators(song):
    cues = sorted(song.cue_points, key=lambda c: c.time)
    return [{"index": i, "name": c.name, "time": c.time} for i, c in enumerate(cues)]


@op("arrangement.get")
def arrangement_get(ctx, params):
    song = ctx.song
    only = params.get("track")
    indices = [only] if only is not None else range(len(song.tracks))
    tracks = []
    for index in indices:
        track = ctx.track(index)
        if not hasattr(track, "arrangement_clips"):
            continue  # group tracks hold no clips
        clips = ctx.arrangement_clips(index)
        tracks.append({"index": index, "name": track.name, "clips": [_clip(i, c) for i, c in enumerate(clips)]})
    return {"song_length": song.song_length, "locators": _locators(song), "tracks": tracks}


def _check_free(ctx, track_index, start, end):
    for i, clip in enumerate(ctx.arrangement_clips(track_index)):
        if clip.start_time < end - EPSILON and start < clip.end_time - EPSILON:
            raise OpError(
                ErrorCode.CONFLICT,
                "Track %d already has '%s' at beats %g-%g; delete it first or pick another start"
                % (track_index, clip.name or "a clip", clip.start_time, clip.end_time),
                track=track_index,
                arrangement_clip=i,
            )


def _find_clip(ctx, track_index, start):
    for clip in ctx.arrangement_clips(track_index):
        if abs(clip.start_time - start) < EPSILON:
            return clip
    raise OpError(ErrorCode.LIVE_ERROR, "Live did not place the clip at beat %g on track %d" % (start, track_index))


def _add_clip(ctx, action):
    track = ctx.track(action["track"])
    if not hasattr(track, "create_midi_clip"):
        raise OpError(ErrorCode.UNSUPPORTED, "Creating arrangement clips needs Live 12.1.10 or newer (and a MIDI track)")
    if not track.has_midi_input:
        raise OpError(ErrorCode.INVALID_PARAMS, "Track %d is not a MIDI track" % action["track"])
    start, length = float(action["start"]), float(action["length"])
    notes = action.get("notes") or []
    for i, note in enumerate(notes):
        _validate_note(i, note, require_all=True)
    _check_free(ctx, action["track"], start, start + length)
    clip = track.create_midi_clip(start, length)
    if clip is None:  # older builds return nothing; find it by its start
        clip = _find_clip(ctx, action["track"], start)
    if action.get("name"):
        clip.name = action["name"]
    if action.get("color_index") is not None:
        clip.color_index = action["color_index"]
    if notes:
        clip.add_new_notes(tuple(_make_spec(n) for n in notes))
    return {"track": action["track"], "start": start, "end": start + length, "notes": len(notes)}


def _copy_session_clip(ctx, action):
    track = ctx.track(action["track"])
    source = ctx.clip(action["track"], action["slot"])
    start = float(action["start"])
    _check_free(ctx, action["track"], start, start + source.length)
    track.duplicate_clip_to_arrangement(source, start)
    return {"track": action["track"], "start": start, "end": start + source.length, "from_slot": action["slot"]}


def _delete_clip(ctx, action):
    clip = ctx.clip_at({"track": action["track"], "arrangement_clip": action["clip"]})
    span = (clip.start_time, clip.end_time)
    ctx.track(action["track"]).delete_clip(clip)
    return {"track": action["track"], "deleted": {"start": span[0], "end": span[1]}}


def _cue_at(song, time):
    for cue in song.cue_points:
        if abs(cue.time - time) < EPSILON:
            return cue
    return None


ACTIONS = {
    "add_clip": _add_clip,
    "copy_session_clip": _copy_session_clip,
    "delete_clip": _delete_clip,
}


@op("arrangement.edit")
def arrangement_edit(ctx, params):
    results = []
    for i, action in enumerate(params.get("actions") or []):
        handler = ACTIONS.get(action.get("action"))
        if handler is None:
            raise OpError(ErrorCode.INVALID_PARAMS, "actions[%d]: unknown action %r" % (i, action.get("action")))
        try:
            results.append(handler(ctx, action))
        except OpError as err:
            err.details["index"] = i
            err.details["completed"] = len(results)
            raise
    return {"results": results, "song_length": ctx.song.song_length}


def _wait(condition, what):
    for _ in range(WAIT_TICKS):
        if condition():
            return
        yield
    raise OpError(ErrorCode.LIVE_ERROR, "Live did not %s" % what)


def _toggle_cue_at(song, time, present):
    """Move the play position to `time`, wait until Live has it, toggle the cue, wait for the result."""
    song.current_song_time = time
    yield from _wait(lambda: abs(song.current_song_time - time) < EPSILON, "move the play position to beat %g" % time)
    song.set_or_delete_cue()
    yield from _wait(lambda: (_cue_at(song, time) is not None) == present, "%s the locator at beat %g" % ("set" if present else "delete", time))


@op("arrangement.locators", multi_tick=True)
def arrangement_locators(ctx, params):
    song = ctx.song
    if song.is_playing:
        raise OpError(ErrorCode.CONFLICT, "Stop the transport to set or delete locators (Live places them at the play position)")
    position = song.current_song_time
    results = []
    try:
        for i, action in enumerate(params.get("actions") or []):
            time = float(action["time"])
            cue = _cue_at(song, time)
            if action.get("action") == "set_locator":
                if cue is None:
                    yield from _toggle_cue_at(song, time, present=True)
                    cue = _cue_at(song, time)
                if action.get("name"):
                    cue.name = action["name"]
                results.append({"locator": {"name": cue.name, "time": cue.time}})
            elif action.get("action") == "delete_locator":
                if cue is None:
                    raise OpError(ErrorCode.NOT_FOUND, "No locator at beat %g" % time, index=i, completed=len(results))
                yield from _toggle_cue_at(song, time, present=False)
                results.append({"deleted_locator": time})
            else:
                raise OpError(ErrorCode.INVALID_PARAMS, "actions[%d]: unknown action %r" % (i, action.get("action")))
    finally:
        song.current_song_time = position  # back to where the user was
    yield from _wait(lambda: abs(song.current_song_time - position) < EPSILON, "return to the play position")
    return {"results": results, "locators": _locators(song)}


@op("song.position", multi_tick=True)
def song_position(ctx, params):
    """Move the play position and wait until Live has it (it applies a new one on a later tick)."""
    song = ctx.song
    beat = float(params["beat"])
    song.current_song_time = beat
    yield from _wait(lambda: abs(song.current_song_time - beat) < EPSILON, "move the play position to beat %g" % beat)
    return {"position": song.current_song_time}
