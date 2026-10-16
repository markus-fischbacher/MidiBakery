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

    def device(self, track_index, device_index, chain_path=()):
        """A device on the track, or inside racks: chain_path alternates chain and device
        indices below it, e.g. (1, 0) = the first device in the rack's second chain."""
        devices = self.track(track_index).devices
        if not 0 <= device_index < len(devices):
            raise OpError(ErrorCode.NOT_FOUND, "No device %d on track %d" % (device_index, track_index), device=device_index)
        device = devices[device_index]
        path = list(chain_path or ())
        if len(path) % 2:
            raise OpError(ErrorCode.INVALID_PARAMS, "chain_path needs chain, device pairs")
        for chain_index, inner_index in zip(path[0::2], path[1::2]):
            chain = self.chain(device, chain_index)
            inner = list(chain.devices)
            if not 0 <= inner_index < len(inner):
                raise OpError(ErrorCode.NOT_FOUND, "No device %d in chain %d of '%s'" % (inner_index, chain_index, device.name))
            device = inner[inner_index]
        return device

    def chain(self, rack, chain_index):
        if not getattr(rack, "can_have_chains", False):
            raise OpError(ErrorCode.INVALID_PARAMS, "'%s' is not a rack" % rack.name)
        chains = list(rack.chains)
        if not 0 <= chain_index < len(chains):
            raise OpError(
                ErrorCode.NOT_FOUND,
                "No chain %d in '%s' (it has %d; add_chain creates one)" % (chain_index, rack.name, len(chains)),
            )
        return chains[chain_index]

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
