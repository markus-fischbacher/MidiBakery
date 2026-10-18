"""Op handler registry and shared Live Object Model lookups."""

from .protocol import ErrorCode, OpError

HANDLERS = {}


def op(name, multi_tick=False):
    """multi_tick: the handler is a generator that yields while Live applies a change;
    the executor advances it once per update_display() tick and replies with its return value."""

    def decorate(fn):
        if name in HANDLERS:
            raise ValueError("duplicate handler for %s" % name)
        fn.multi_tick = multi_tick
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

    def where(self, track_index):
        """A track as errors name it: zero-based like every op parameter, with its name, e.g.
        "track index 2 'Bass'". Users count from 1, so the index word keeps models from mixing them up."""
        tracks = self.song.tracks
        if 0 <= track_index < len(tracks):
            return "track index %d '%s'" % (track_index, tracks[track_index].name)
        return "track index %d" % track_index

    def track(self, index):
        tracks = self.song.tracks
        if not 0 <= index < len(tracks):
            raise OpError(ErrorCode.NOT_FOUND, "No track index %d (song has %d tracks: 0-%d)" % (index, len(tracks), len(tracks) - 1), track=index)
        return tracks[index]

    def clip_slot(self, track_index, slot_index):
        slots = self.track(track_index).clip_slots
        if not 0 <= slot_index < len(slots):
            raise OpError(ErrorCode.NOT_FOUND, "No slot index %d on %s (it has %d)" % (slot_index, self.where(track_index), len(slots)), slot=slot_index)
        return slots[slot_index]

    def clip(self, track_index, slot_index):
        slot = self.clip_slot(track_index, slot_index)
        if not slot.has_clip:
            raise OpError(ErrorCode.NOT_FOUND, "Slot index %d on %s is empty" % (slot_index, self.where(track_index)), track=track_index, slot=slot_index)
        return slot.clip

    def arrangement_clips(self, track_index):
        """The track's arrangement clips in time order; `arrangement_clip` indices count in this order."""
        track = self.track(track_index)
        if not hasattr(track, "arrangement_clips"):
            raise OpError(ErrorCode.UNSUPPORTED, "No arrangement clips on %s (a group or return track)" % self.where(track_index))
        return sorted(track.arrangement_clips, key=lambda c: c.start_time)

    def clip_at(self, params):
        """The clip a request names: a session `slot` or an `arrangement_clip` index."""
        index = params.get("arrangement_clip")
        if index is None:
            return self.clip(params["track"], params["slot"])
        clips = self.arrangement_clips(params["track"])
        if not 0 <= index < len(clips):
            raise OpError(
                ErrorCode.NOT_FOUND,
                "No arrangement_clip index %d on %s (it has %d)" % (index, self.where(params["track"]), len(clips)),
                track=params["track"],
            )
        return clips[index]

    def midi_clip_at(self, params):
        clip = self.clip_at(params)
        if not clip.is_midi_clip:
            raise OpError(ErrorCode.INVALID_PARAMS, "That clip on %s is not a MIDI clip" % self.where(params["track"]))
        return clip

    def midi_clip(self, track_index, slot_index):
        clip = self.clip(track_index, slot_index)
        if not clip.is_midi_clip:
            raise OpError(ErrorCode.INVALID_PARAMS, "The clip in slot index %d on %s is not a MIDI clip" % (slot_index, self.where(track_index)))
        return clip

    def return_track(self, index):
        returns = self.song.return_tracks
        if not 0 <= index < len(returns):
            raise OpError(ErrorCode.NOT_FOUND, "No return_track index %d (song has %d return tracks)" % (index, len(returns)), return_track=index)
        return returns[index]

    def device_owner(self, params):
        """(track, where) whose chain params mean: the master, a return track or a track."""
        if params.get("master"):
            return self.song.master_track, "the master track"
        if params.get("return_track") is not None:
            return self.return_track(params["return_track"]), "return_track index %d" % params["return_track"]
        return self.track(params["track"]), self.where(params["track"])

    def device(self, params):
        """The device params name: on params["track"], params["return_track"] or the master, or inside
        racks: chain_path alternates chain and device indices below it, e.g. (1, 0) = the first device
        in the rack's second chain."""
        owner, where = self.device_owner(params)
        devices = owner.devices
        device_index, chain_path = params["device"], params.get("chain_path")
        if not 0 <= device_index < len(devices):
            raise OpError(ErrorCode.NOT_FOUND, "No device index %d on %s (it has %d)" % (device_index, where, len(devices)), device=device_index)
        device = devices[device_index]
        path = list(chain_path or ())
        if len(path) % 2:
            raise OpError(ErrorCode.INVALID_PARAMS, "chain_path needs chain, device pairs")
        for chain_index, inner_index in zip(path[0::2], path[1::2]):
            chain = self.chain(device, chain_index)
            inner = list(chain.devices)
            if not 0 <= inner_index < len(inner):
                raise OpError(ErrorCode.NOT_FOUND, "No device index %d in chain index %d of '%s'" % (inner_index, chain_index, device.name))
            device = inner[inner_index]
        return device

    def chain(self, rack, chain_index):
        if not getattr(rack, "can_have_chains", False):
            raise OpError(ErrorCode.INVALID_PARAMS, "'%s' is not a rack" % rack.name)
        chains = list(rack.chains)
        if not 0 <= chain_index < len(chains):
            raise OpError(
                ErrorCode.NOT_FOUND,
                "No chain index %d in '%s' (it has %d; add_chain creates one)" % (chain_index, rack.name, len(chains)),
            )
        return chains[chain_index]

    def scene(self, index):
        scenes = self.song.scenes
        if not 0 <= index < len(scenes):
            raise OpError(ErrorCode.NOT_FOUND, "No scene index %d (song has %d scenes)" % (index, len(scenes)), scene=index)
        return scenes[index]


def index_of(seq, item):
    for i, candidate in enumerate(seq):
        if candidate == item:
            return i
    return None
