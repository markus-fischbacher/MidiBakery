"""Op handler registry and shared Live Object Model lookups."""

from .protocol import ErrorCode, OpError

HANDLERS = {}


def op(name):
    def decorate(fn):
        if name in HANDLERS:
            raise ValueError("duplicate handler for %s" % name)
        HANDLERS[name] = fn
        return fn

    return decorate


class Context(object):
    """What a handler gets: the song, Live's version and a logger."""

    def __init__(self, song, live_version, log, supported_ops):
        self.song = song
        self.live_version = live_version
        self.log = log
        self.supported_ops = supported_ops

    def track(self, index):
        tracks = self.song.tracks
        if not 0 <= index < len(tracks):
            raise OpError(ErrorCode.NOT_FOUND, "No track %d (song has %d)" % (index, len(tracks)), track=index)
        return tracks[index]

    def clip_slot(self, track_index, slot_index):
        slots = self.track(track_index).clip_slots
        if not 0 <= slot_index < len(slots):
            raise OpError(ErrorCode.NOT_FOUND, "No clip slot %d (track has %d)" % (slot_index, len(slots)), slot=slot_index)
        return slots[slot_index]

    def clip(self, track_index, slot_index):
        slot = self.clip_slot(track_index, slot_index)
        if not slot.has_clip:
            raise OpError(ErrorCode.NOT_FOUND, "Slot %d/%d is empty" % (track_index, slot_index), track=track_index, slot=slot_index)
        return slot.clip

    def midi_clip(self, track_index, slot_index):
        clip = self.clip(track_index, slot_index)
        if not clip.is_midi_clip:
            raise OpError(ErrorCode.INVALID_PARAMS, "Clip %d/%d is not a MIDI clip" % (track_index, slot_index))
        return clip

    def device(self, track_index, device_index):
        devices = self.track(track_index).devices
        if not 0 <= device_index < len(devices):
            raise OpError(ErrorCode.NOT_FOUND, "No device %d on track %d" % (device_index, track_index), device=device_index)
        return devices[device_index]

    def scene(self, index):
        scenes = self.song.scenes
        if not 0 <= index < len(scenes):
            raise OpError(ErrorCode.NOT_FOUND, "No scene %d (song has %d)" % (index, len(scenes)), scene=index)
        return scenes[index]


def index_of(seq, item):
    for i, candidate in enumerate(seq):
        if candidate == item:
            return i
    return None
