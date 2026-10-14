"""Note editing with Live 11+/12's id-based API.

Edits are diffs: untouched notes keep their ids, probability, velocity
deviation and release velocity, and the whole edit is one undo step.
"""

from ..protocol import ErrorCode, OpError
from ..registry import op

NOTE_FIELDS = (
    "pitch",
    "start_time",
    "duration",
    "velocity",
    "mute",
    "probability",
    "velocity_deviation",
    "release_velocity",
)
_ADD_DEFAULTS = {
    "velocity": 100.0,
    "mute": False,
    "probability": 1.0,
    "velocity_deviation": 0.0,
    "release_velocity": 64.0,
}


def _note_dict(note):
    data = {"note_id": note.note_id}
    for key in NOTE_FIELDS:
        data[key] = getattr(note, key)
    return data


def _whole_clip_span(clip):
    return max(clip.length, clip.loop_end, clip.end_marker) + 1.0


def _all_notes(clip):
    return clip.get_notes_extended(from_pitch=0, pitch_span=128, from_time=0.0, time_span=_whole_clip_span(clip))


@op("notes.get")
def notes_get(ctx, params):
    clip = ctx.midi_clip(params["track"], params["slot"])
    from_time = float(params.get("from_time", 0.0))
    time_span = params.get("time_span")
    if time_span is None:
        time_span = _whole_clip_span(clip) - from_time
    if time_span <= 0:
        return {"notes": [], "clip_length": clip.length}
    notes = clip.get_notes_extended(
        from_pitch=params.get("from_pitch", 0),
        pitch_span=params.get("pitch_span", 128),
        from_time=from_time,
        time_span=float(time_span),
    )
    ordered = sorted((_note_dict(n) for n in notes), key=lambda n: (n["start_time"], n["pitch"]))
    return {"notes": ordered, "clip_length": clip.length}


def _validate_note(index, note, require_all):
    if not isinstance(note, dict):
        raise OpError(ErrorCode.INVALID_PARAMS, "Note %d must be an object" % index)
    for key in ("pitch", "start_time", "duration") if require_all else ():
        if key not in note:
            raise OpError(ErrorCode.INVALID_PARAMS, "Note %d is missing '%s'" % (index, key))
    pitch = note.get("pitch")
    if pitch is not None and not (isinstance(pitch, int) and 0 <= pitch <= 127):
        raise OpError(ErrorCode.INVALID_PARAMS, "Note %d: pitch must be 0..127" % index)
    duration = note.get("duration")
    if duration is not None and not duration > 0:
        raise OpError(ErrorCode.INVALID_PARAMS, "Note %d: duration must be > 0" % index)
    start = note.get("start_time")
    if start is not None and start < 0:
        raise OpError(ErrorCode.INVALID_PARAMS, "Note %d: start_time must be >= 0" % index)


def _make_spec(note):
    from Live.Clip import MidiNoteSpecification

    kwargs = dict(_ADD_DEFAULTS)
    kwargs.update({k: v for k, v in note.items() if k in NOTE_FIELDS and v is not None})
    kwargs["pitch"] = int(kwargs["pitch"])
    for key in ("start_time", "duration", "velocity", "probability", "velocity_deviation", "release_velocity"):
        kwargs[key] = float(kwargs[key])
    return MidiNoteSpecification(**kwargs)


@op("notes.apply")
def notes_apply(ctx, params):
    clip = ctx.midi_clip(params["track"], params["slot"])
    add = params.get("add") or []
    modify = params.get("modify") or []
    remove = params.get("remove") or []
    if not (add or modify or remove):
        raise OpError(ErrorCode.INVALID_PARAMS, "Nothing to do: give add, modify or remove")

    # Validate everything before touching the clip, so a bad request changes nothing.
    for i, note in enumerate(add):
        _validate_note(i, note, require_all=True)
    for i, change in enumerate(modify):
        _validate_note(i, change, require_all=False)
        if not isinstance(change.get("note_id"), int):
            raise OpError(ErrorCode.INVALID_PARAMS, "modify[%d] needs an integer note_id" % i)
    existing = _all_notes(clip)
    known_ids = set(n.note_id for n in existing)
    wanted = set(c["note_id"] for c in modify) | set(remove)
    unknown = sorted(wanted - known_ids)
    if unknown:
        raise OpError(ErrorCode.NOT_FOUND, "Unknown note_id(s) in this clip", note_ids=unknown)
    overlap = sorted(set(c["note_id"] for c in modify) & set(remove))
    if overlap:
        raise OpError(ErrorCode.INVALID_PARAMS, "note_id(s) both modified and removed", note_ids=overlap)

    if modify:
        changes = dict((c["note_id"], c) for c in modify)
        for note in existing:
            change = changes.get(note.note_id)
            if change is None:
                continue
            for key in NOTE_FIELDS:
                if change.get(key) is not None:
                    setattr(note, key, change[key])
        clip.apply_note_modifications(existing)

    if remove:
        clip.remove_notes_by_id(list(remove))

    added_ids = []
    if add:
        added_ids = list(clip.add_new_notes(tuple(_make_spec(n) for n in add)))

    return {"added": added_ids, "modified": len(modify), "removed": len(remove)}
