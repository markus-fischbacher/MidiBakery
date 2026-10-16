"""A compact snapshot of what Live is doing, pushed to subscribed clients.

Live's main thread reads it every few update_display() ticks and sends it when it
changed. Polling a handful of properties is cheaper and sturdier than one LOM
listener per track and clip, which would have to follow every track, clip and
Set change.
"""

STOP_PENDING = -2


def _index(items, item):
    for i, candidate in enumerate(items):
        if candidate == item:
            return i
    return None


def snapshot(song):
    tracks = list(song.tracks)
    playing, launching, stopping = [], [], []
    for index, track in enumerate(tracks):
        slots = track.clip_slots
        current = track.playing_slot_index
        if 0 <= current < len(slots) and slots[current].has_clip:
            playing.append({"track": index, "name": track.name, "slot": current, "clip": slots[current].clip.name})
        fired = track.fired_slot_index
        if fired == STOP_PENDING:
            stopping.append(index)
        elif 0 <= fired < len(slots):
            launching.append({"track": index, "slot": fired})
    view = song.view
    return {
        "tempo": round(song.tempo, 2),
        "signature": [song.signature_numerator, song.signature_denominator],
        "is_playing": song.is_playing,
        "record_mode": song.record_mode,
        "root_note": song.root_note,
        "scale_name": song.scale_name,
        "track_count": len(tracks),
        "selected_track": _index(tracks, view.selected_track),
        "selected_scene": _index(list(song.scenes), view.selected_scene),
        "playing": playing,
        "launching": launching,
        "stopping": stopping,
    }


class StateWatcher(object):
    """Called from update_display(); publishes `state` when it changed or someone subscribed."""

    EVERY_TICKS = 2  # Live ticks about every 100 ms

    def __init__(self, song, server, log):
        self._song = song
        self._server = server
        self._log = log
        self._ticks = 0
        self._last = None
        self._failed = False

    def tick(self):
        self._ticks += 1
        if self._ticks % self.EVERY_TICKS:
            return
        fresh = self._server.take_new_subscribers("state")
        if not self._server.has_subscribers("state"):
            self._last = None
            return
        try:
            state = snapshot(self._song)
        except Exception as exc:  # a half-loaded Set must never break Live's display loop
            if not self._failed:
                self._log("state snapshot failed: %s" % exc)
                self._failed = True
            return
        self._failed = False
        if state != self._last or fresh:
            self._last = state
            self._server.publish("state", state)
