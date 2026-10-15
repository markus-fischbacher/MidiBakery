"""Fake Live Object Model graph: Song, tracks, clip slots, clips, devices."""

import copy
import itertools

from Live import LiveObject

NOTE_FIELDS = ("pitch", "start_time", "duration", "velocity", "mute",
               "probability", "velocity_deviation", "release_velocity")
NATIVE_DEVICES = {"Operator", "Drift", "Wavetable", "Reverb", "Auto Filter", "Drum Rack", "Simpler"}


class Parameter(LiveObject):
    def __init__(self, name, value, minimum=0.0, maximum=1.0, quantized=False, items=()):
        self.name = name
        self.value = value
        self.min = minimum
        self.max = maximum
        self.is_quantized = quantized
        self.is_enabled = True
        self.value_items = list(items)

    def str_for_value(self, value):
        return "%.2f" % value


class Device(LiveObject):
    can_have_drum_pads = False
    can_have_chains = False

    def __init__(self, name):
        self.name = name
        self.class_name = name.replace(" ", "")
        self.parameters = [
            Parameter("Device On", 1.0, 0.0, 1.0, True, ("Off", "On")),
            Parameter("Volume", 0.5, 0.0, 1.0),
            Parameter("Filter Freq", 1000.0, 20.0, 20000.0),
        ]


class Chain(LiveObject):
    def __init__(self, name, devices=()):
        self.name = name
        self.devices = list(devices)


class DrumChain(Chain):
    """Live 12.3+ chain with in_note."""

    def __init__(self, name, in_note):
        Chain.__init__(self, name)
        self.in_note = in_note


class DrumPad(LiveObject):
    def __init__(self, note):
        self.note = note
        self.name = "Empty"
        self.chains = []


class DrumRackDevice(Device):
    """legacy=True models Live < 12.3: chains have no in_note, pads carry the mapping."""

    can_have_drum_pads = True
    can_have_chains = True

    def __init__(self, name="Drum Rack", legacy=False):
        Device.__init__(self, name)
        self.class_name = "DrumGroupDevice"
        self.legacy = legacy
        self.chains = []
        self.drum_pads = [DrumPad(n) for n in range(128)]

    def add_pad(self, name, note):
        chain = Chain(name) if self.legacy else DrumChain(name, note)
        self.chains.append(chain)
        pad = self.drum_pads[note]
        pad.name = name
        pad.chains = [chain]


class RackDevice(Device):
    can_have_chains = True

    def __init__(self, name, chains):
        Device.__init__(self, name)
        self.chains = list(chains)


class Mixer(LiveObject):
    def __init__(self):
        self.volume = Parameter("Track Volume", 0.85)
        self.panning = Parameter("Track Panning", 0.0, -1.0, 1.0)


class MidiNote(LiveObject):
    def __init__(self, note_id, **fields):
        self.note_id = note_id
        for key in NOTE_FIELDS:
            setattr(self, key, fields[key])


class Clip(LiveObject):
    _ids = itertools.count(1)

    def __init__(self, length, is_midi=True):
        self.name = ""
        self.length = length
        self.is_midi_clip = is_midi
        self.looping = True
        self.loop_start = 0.0
        self.loop_end = length
        self.start_marker = 0.0
        self.end_marker = length
        self.color_index = 0
        self.is_playing = False
        self.is_triggered = False
        self.launch_mode = 0  # 0 Trigger, 1 Gate, 2 Toggle, 3 Repeat
        self.signature_numerator = 4
        self.signature_denominator = 4
        self.notes = {}  # note_id -> dict

    def get_notes_extended(self, from_pitch, pitch_span, from_time, time_span):
        return [
            MidiNote(note_id, **copy.deepcopy(n))
            for note_id, n in self.notes.items()
            if from_pitch <= n["pitch"] < from_pitch + pitch_span and from_time <= n["start_time"] < from_time + time_span
        ]

    def apply_note_modifications(self, notes):
        for note in notes:
            if note.note_id in self.notes:
                self.notes[note.note_id] = dict((k, getattr(note, k)) for k in NOTE_FIELDS)

    def remove_notes_by_id(self, ids):
        for note_id in ids:
            self.notes.pop(note_id, None)

    def add_new_notes(self, specs):
        ids = []
        for spec in specs:
            note_id = next(Clip._ids)
            self.notes[note_id] = dict((k, getattr(spec, k)) for k in NOTE_FIELDS)
            ids.append(note_id)
        return tuple(ids)


class ClipSlot(LiveObject):
    def __init__(self):
        self.clip = None
        self.fired = 0

    @property
    def has_clip(self):
        return self.clip is not None

    def create_clip(self, length):
        if self.clip is not None:
            raise RuntimeError("slot not empty")
        self.clip = Clip(length)

    def delete_clip(self):
        self.clip = None

    def fire(self):
        self.fired += 1
        clip = self.clip
        if clip is None:
            return
        if clip.launch_mode == 2 and (clip.is_playing or clip.is_triggered):
            clip.is_playing = clip.is_triggered = False
        else:
            clip.is_triggered = True

    def stop(self):
        pass


class Track(LiveObject):
    _ptrs = itertools.count(0x7000)

    def __init__(self, name, midi=True, scenes=8):
        self._live_ptr = next(Track._ptrs)
        self.name = name
        self.has_midi_input = midi
        self.is_foldable = False
        self.can_be_armed = True
        self.arm = False
        self.mute = False
        self.solo = False
        self.color_index = 0
        self.mixer_device = Mixer()
        self.devices = []
        self.clip_slots = [ClipSlot() for _ in range(scenes)]
        self.playing_slot_index = -1
        self.fired_slot_index = -1  # -2: Clip Stop button fired (stop pending)
        self.stopped_unquantized = 0

    def stop_all_clips(self, quantized=True):
        for slot in self.clip_slots:
            if slot.clip is not None:
                slot.clip.is_playing = slot.clip.is_triggered = False
        self.fired_slot_index = -1
        if not quantized:
            self.stopped_unquantized += 1

    def insert_device(self, name, index):
        if name not in NATIVE_DEVICES:
            raise RuntimeError("Unknown device")
        self.devices.insert(index, DrumRackDevice() if name == "Drum Rack" else Device(name))


class Scene(LiveObject):
    def __init__(self, name=""):
        self.name = name
        self.fired = 0

    def fire(self):
        self.fired += 1


class SongView(LiveObject):
    def __init__(self, song):
        self.selected_track = song.tracks[0] if song.tracks else None
        self.selected_scene = song.scenes[0] if song.scenes else None


class Song(LiveObject):
    def __init__(self, tracks=2, scenes=8):
        self.scenes = [Scene() for _ in range(scenes)]
        self.tracks = [Track("%d-MIDI" % (i + 1), scenes=scenes) for i in range(tracks)]
        self.return_tracks = []
        self.view = SongView(self)
        self.tempo = 120.0
        self.signature_numerator = 4
        self.signature_denominator = 4
        self.is_playing = False
        self.record_mode = False
        self.metronome = False
        self.current_song_time = 0.0
        self.loop = False
        self.loop_start = 0.0
        self.loop_length = 16.0
        self.root_note = 0
        self.scale_name = "Major"
        self.scale_mode = False
        self.scale_intervals = (0, 2, 4, 5, 7, 9, 11)
        self.can_undo = False
        self.can_redo = False
        self.undo_depth = 0
        self.undo_steps = 0
        self.undo_calls = 0

    def begin_undo_step(self):
        self.undo_depth += 1

    def end_undo_step(self):
        self.undo_depth -= 1
        if self.undo_depth == 0:
            self.undo_steps += 1
            self.can_undo = True

    def undo(self):
        self.undo_calls += 1

    def redo(self):
        pass

    def start_playing(self):
        self.is_playing = True

    def stop_playing(self):
        self.is_playing = False

    def continue_playing(self):
        self.is_playing = True

    def create_midi_track(self, index):
        self._insert_track(Track("MIDI", True, len(self.scenes)), index)

    def create_audio_track(self, index):
        self._insert_track(Track("Audio", False, len(self.scenes)), index)

    def _insert_track(self, track, index):
        if index == -1:
            self.tracks.append(track)
        else:
            self.tracks.insert(index, track)

    def delete_track(self, index):
        del self.tracks[index]

    def create_scene(self, index):
        scene = Scene()
        if index == -1:
            self.scenes.append(scene)
        else:
            self.scenes.insert(index, scene)
        for track in self.tracks:
            track.clip_slots.insert(len(track.clip_slots) if index == -1 else index, ClipSlot())


class CInstance(object):
    """What Live passes to create_instance()."""

    def __init__(self, song):
        self._song = song
        self.messages = []
        self.log = []

    def song(self):
        return self._song

    def show_message(self, message):
        self.messages.append(message)

    def log_message(self, message):
        self.log.append(message)

    def instance_identifier(self):
        return 0
