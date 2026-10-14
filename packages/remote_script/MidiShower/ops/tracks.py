from ..protocol import ErrorCode, OpError
from ..registry import op


def _kind(track):
    if track.is_foldable:
        return "group"
    return "midi" if track.has_midi_input else "audio"


def _clamp_param(param, value):
    return max(param.min, min(param.max, value))


@op("tracks.list")
def tracks_list(ctx, params):
    tracks = []
    for index, track in enumerate(ctx.song.tracks):
        mixer = track.mixer_device
        clips = []
        for slot_index, slot in enumerate(track.clip_slots):
            if slot.has_clip:
                clip = slot.clip
                clips.append({
                    "slot": slot_index,
                    "name": clip.name,
                    "length": clip.length,
                    "is_midi": clip.is_midi_clip,
                    "is_playing": clip.is_playing,
                })
        tracks.append({
            "index": index,
            "name": track.name,
            "kind": _kind(track),
            "color_index": track.color_index,
            "mute": track.mute,
            "solo": track.solo,
            "arm": track.arm if track.can_be_armed else None,
            "volume": mixer.volume.value,
            "pan": mixer.panning.value,
            "devices": [
                {"index": i, "name": d.name, "class_name": d.class_name} for i, d in enumerate(track.devices)
            ],
            "clips": clips,
        })
    return {"tracks": tracks}


@op("track.create")
def track_create(ctx, params):
    song = ctx.song
    index = params.get("index", -1)
    if index > len(song.tracks):
        raise OpError(ErrorCode.INVALID_PARAMS, "Track index %d beyond end (%d)" % (index, len(song.tracks)))
    if params.get("kind", "midi") == "midi":
        song.create_midi_track(index)
    else:
        song.create_audio_track(index)
    new_index = len(song.tracks) - 1 if index == -1 else index
    if params.get("name"):
        song.tracks[new_index].name = params["name"]
    return {"track": new_index}


@op("track.set")
def track_set(ctx, params):
    track = ctx.track(params["track"])
    mixer = track.mixer_device
    changed = []
    for key in ("name", "color_index", "mute", "solo"):
        if params.get(key) is not None:
            setattr(track, key, params[key])
            changed.append(key)
    if params.get("arm") is not None:
        if not track.can_be_armed:
            raise OpError(ErrorCode.INVALID_PARAMS, "Track %d cannot be armed" % params["track"])
        track.arm = params["arm"]
        changed.append("arm")
    if params.get("volume") is not None:
        mixer.volume.value = _clamp_param(mixer.volume, params["volume"])
        changed.append("volume")
    if params.get("pan") is not None:
        mixer.panning.value = _clamp_param(mixer.panning, params["pan"])
        changed.append("pan")
    return {"changed": changed}


@op("track.delete")
def track_delete(ctx, params):
    ctx.track(params["track"])  # existence check
    ctx.song.delete_track(params["track"])
    return {"deleted": params["track"]}
