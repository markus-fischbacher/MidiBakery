"""Fake Live Object Model graph: Song, tracks, clip slots, clips, devices."""

import copy
import itertools

from Live import LiveObject

NOTE_FIELDS = ("pitch", "start_time", "duration", "velocity", "mute",
               "probability", "velocity_deviation", "release_velocity")
NATIVE_DEVICES = {"Compressor", "Operator", "Drift", "Wavetable", "Reverb", "Delay", "Auto Filter", "Drum Rack", "Simpler", "Instrument Rack", "Audio Effect Rack"}
RACK_CLASSES = {"Instrument Rack": "InstrumentGroupDevice", "Audio Effect Rack": "AudioEffectGroupDevice", "Drum Rack": "DrumGroupDevice"}


def make_device(name, track=None):
    if name not in NATIVE_DEVICES:
        raise RuntimeError("Unknown device")
    if name == "Drum Rack":
        return DrumRackDevice()
    if name in RACK_CLASSES:
        return RackDevice(name, [])
    device = Device(name)
    if name == "Auto Filter":  # Live 12's AutoFilter2, the parameters the song engine automates
        device.class_name = "AutoFilter2"
        device.parameters += [
            Parameter("Frequency", 1.0),
            PercentParameter("Resonance", 0.0),
            Parameter("Filter Type", 0.0, 0.0, 9.0, True, ("Low-pass", "High-pass", "Band-pass", "Notch", "Morph", "DJ", "Comb", "Resampling", "Notch+LP", "Vowel")),
        ]
    if name == "Compressor":
        return CompressorDevice(track)
    if name == "Reverb":
        device.parameters += [Parameter("Decay Time", 0.314), Parameter("Dry/Wet", 0.5)]
    if name == "Delay":
        device.parameters += [
            Parameter("Link", 1.0, 0.0, 1.0, True, ("Off", "On")),
            Parameter("L Sync", 1.0, 0.0, 1.0, True, ("Off", "On")),
            Parameter("L 16th", 2.0, 0.0, 7.0, True, ("1", "2", "3", "4", "5", "6", "8", "16")),
            Parameter("Feedback", 0.526),
            Parameter("Dry/Wet", 0.5),
        ]
    return device


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
        if self.is_quantized and self.value_items:  # Live shows the choice's name
            return self.value_items[int(round(value))]
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
        self.mute = False
        self.solo = False
        self.mixer_device = ChainMixer()

    def insert_device(self, name, index):  # Live 12.3+
        self.devices.insert(index, make_device(name))


class ChainMixer(LiveObject):
    def __init__(self):
        self.volume = DbParameter("Chain Volume", 0.85)
        self.panning = Parameter("Chain Panning", 0.0, -1.0, 1.0)


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
        self.visible_macro_count = 8
        self.parameters = [Parameter("Device On", 1.0, 0.0, 1.0, True, ("Off", "On"))] + [
            Parameter("Macro %d" % n, 0.0, 0.0, 127.0) for n in range(1, 17)
        ]
        if not legacy:  # insert_chain and DrumChain.in_note arrived in Live 12.3
            self.insert_chain = lambda index: self.chains.insert(index, DrumChain("Chain", 36))

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
        self.class_name = RACK_CLASSES.get(name, "InstrumentGroupDevice")
        self.chains = list(chains)
        self.visible_macro_count = 8
        self.parameters = [Parameter("Device On", 1.0, 0.0, 1.0, True, ("Off", "On"))] + [
            Parameter("Macro %d" % n, 0.0, 0.0, 127.0) for n in range(1, 17)
        ]

    def insert_chain(self, index):  # Live 12.3+
        self.chains.insert(index, Chain("Chain"))


class PercentParameter(Parameter):
    """0-1 shown as 0-100 %, like Auto Filter's Resonance in Live 12.4."""

    def str_for_value(self, value):
        return "%.0f %%" % (value * 100)


class DbParameter(Parameter):
    """Fader-like: Live shows dB, rising with the value (0.85 = 0 dB here, 0 = -inf)."""

    def str_for_value(self, value):
        if value <= 0:
            return "-inf dB"
        return "%.1f dB" % ((value - 0.85) * 40)


class Mixer(LiveObject):
    def __init__(self, sends=0):
        self.volume = DbParameter("Track Volume", 0.85)
        self.panning = Parameter("Track Panning", 0.0, -1.0, 1.0)
        self.sends = []
        self.crossfade_assign = 1  # 0 A, 1 none, 2 B
        for _ in range(sends):
            self.add_send()

    def add_send(self):
        self.sends.append(DbParameter("%s-Send" % "ABCDEFGHIJKL"[len(self.sends)], 0.0))


class RoutingType(LiveObject):
    def __init__(self, display_name, attached_object=None):
        self.display_name = display_name
        self.attached_object = attached_object


class ShownParameter(Parameter):
    """A continuous parameter Live shows through `show` (raw -> text)."""

    def __init__(self, name, value, show):
        Parameter.__init__(self, name, value)
        self.show = show

    def str_for_value(self, value):
        return self.show(value)


class CompressorDevice(Device):
    """Live 12's Compressor2 with its sidechain: sources are the Set's other tracks with an
    instrument, channels the source's taps plus each drum pad chain's."""

    def __init__(self, track):
        Device.__init__(self, "Compressor")
        self.class_name = "Compressor2"
        self.track = track
        on = ("Off", "On")
        self.parameters = [
            Parameter("Device On", 1.0, 0.0, 1.0, True, on),
            ShownParameter("Threshold", 1.0, lambda v: "%.2f dB" % (-70 + 70 * v)),
            ShownParameter("Ratio", 0.5, lambda v: "%.2f : 1" % (1 + 6 * v)),
            ShownParameter("Attack", 0.2, lambda v: "%.2f ms" % (1000 * v ** 3)),
            ShownParameter("Release", 0.2, lambda v: "%.1f ms" % (1 + 3000 * v ** 3)),
            Parameter("S/C EQ On", 0.0, 0.0, 1.0, True, on),
            Parameter("S/C EQ Type", 5.0, 0.0, 5.0, True, ("Low Shelf", "Bell", "High Shelf", "Low pass", "Peak", "High pass")),
            ShownParameter("S/C EQ Freq", 0.2, lambda v: "%.1f Hz" % (20 + 19980 * v ** 3)),
            Parameter("S/C On", 0.0, 0.0, 1.0, True, on),
        ]
        self.input_routing_type = RoutingType("No Input")
        self.input_routing_channel = RoutingType("")

    @property
    def available_input_routing_types(self):
        song = self.track.song if self.track is not None else None
        sources = [t for t in (song.tracks if song else []) if t is not self.track and t.devices and not t.unlisted_ticks]
        return [RoutingType(t.name, t) for t in sources] + [RoutingType("Main"), RoutingType("No Input")]

    @property
    def available_input_routing_channels(self):
        source = self.input_routing_type.attached_object
        if source is None:
            return [RoutingType("")]
        taps = ("Pre FX", "Post FX", "Post Mixer")
        names = list(taps)
        for device in source.devices:
            if getattr(device, "can_have_drum_pads", False):
                names += ["%s | %s | %s" % (device.name, chain.name, tap) for chain in device.chains for tap in taps]
        return [RoutingType(n) for n in names]


class MidiNote(LiveObject):
    def __init__(self, note_id, **fields):
        self.note_id = note_id
        for key in NOTE_FIELDS:
            setattr(self, key, fields[key])


class Envelope(LiveObject):
    """Breakpoints (time, value) with lines between, like Live's AutomationEnvelope."""

    def __init__(self, parameter):
        self.parameter = parameter
        self.events = []

    def create_event(self, time, value):
        self.events = sorted([e for e in self.events if abs(e[0] - time) > 1e-9] + [(time, value)])

    def delete_events_in_range(self, start, end):
        self.events = [e for e in self.events if not start <= e[0] <= end]

    def insert_step(self, time, duration, value):
        self.create_event(time, value)
        self.create_event(time + duration - 1e-6, value)

    def value_at_time(self, time):
        events = self.events
        if not events:
            return self.parameter.value
        if time <= events[0][0]:
            return events[0][1]
        for (t0, v0), (t1, v1) in zip(events, events[1:]):
            if time <= t1:
                return v0 + (v1 - v0) * (time - t0) / (t1 - t0)
        return events[-1][1]


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
        self.is_arrangement_clip = False
        self.start_time = 0.0
        self.end_time = length
        self.envelopes = {}  # parameter -> Envelope

    def automation_envelope(self, parameter):
        if self.is_arrangement_clip:  # Live 12.4 shows scripts no arrangement clip envelopes
            return None
        return self.envelopes.get(id(parameter))

    def clear_envelope(self, parameter):
        self.envelopes.pop(id(parameter), None)

    def create_automation_envelope(self, parameter):
        if self.is_arrangement_clip:  # what Live 12.4 answers for arrangement clips
            raise RuntimeError("Not a session clip or parameter belongs to another track.")
        return self.envelopes.setdefault(id(parameter), Envelope(parameter))

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


class TakeLane(LiveObject):
    """Live 12.2+: a lane of takes under a track in the Arrangement View."""

    def __init__(self, name):
        self.name = name
        self.arrangement_clips = []

    def create_midi_clip(self, start_time, length):
        clip = Clip(length)
        clip.is_arrangement_clip = True
        clip.start_time, clip.end_time = start_time, start_time + length
        self.arrangement_clips.append(clip)
        return clip


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
        self.available_input_routing_types = [RoutingType(n) for n in ("All Ins", "No Input", "Computer Keyboard")]
        self.available_input_routing_channels = [RoutingType(n) for n in ("All Channels", "Ch. 1", "Ch. 2")]
        self.available_output_routing_types = [RoutingType(n) for n in ("Master", "Sends Only")]
        self.available_output_routing_channels = [RoutingType("Track In")]
        self.input_routing_type = self.available_input_routing_types[0]
        self.input_routing_channel = self.available_input_routing_channels[0]
        self.output_routing_type = self.available_output_routing_types[0]
        self.output_routing_channel = self.available_output_routing_channels[0]
        self.devices = []
        self.clip_slots = [ClipSlot() for _ in range(scenes)]
        self.arrangement_clips = []
        self.take_lanes = []
        self.song = None  # set by Song, for Live's side effects on the play position
        self.playing_slot_index = -1
        self.fired_slot_index = -1  # -2: Clip Stop button fired (stop pending)
        self.stopped_unquantized = 0
        self.unlisted_ticks = 0

    def create_midi_clip(self, start_time, length):  # Live 12.1.10+
        clip = Clip(length)
        clip.is_arrangement_clip = True
        clip.start_time, clip.end_time = start_time, start_time + length
        self.arrangement_clips.append(clip)
        return clip

    def duplicate_clip_to_arrangement(self, clip, destination_time):
        copy_ = Clip(clip.length, clip.is_midi_clip)
        copy_.name = clip.name
        copy_.notes = copy.deepcopy(clip.notes)
        copy_.color_index = clip.color_index
        copy_.envelopes = dict(clip.envelopes)
        copy_.is_arrangement_clip = True
        copy_.start_time, copy_.end_time = destination_time, destination_time + clip.length
        self.arrangement_clips.append(copy_)
        if self.song is not None:  # like Live: the play position jumps to the end of the copy
            self.song.current_song_time = copy_.end_time
        return copy_

    def delete_clip(self, clip):
        self.arrangement_clips.remove(clip)

    def create_take_lane(self):
        lane = TakeLane("Take %d" % (len(self.take_lanes) + 1))
        self.take_lanes.append(lane)
        return lane

    def stop_all_clips(self, quantized=True):
        for slot in self.clip_slots:
            if slot.clip is not None:
                slot.clip.is_playing = slot.clip.is_triggered = False
        self.fired_slot_index = -1
        if not quantized:
            self.stopped_unquantized += 1

    def insert_device(self, name, index):
        self.devices.insert(index, make_device(name, self))


class BrowserItem(LiveObject):
    """kit: the drum pads (name -> note) a Drum Rack preset fills; device: the native device a preset is of;
    macros: the names of an Instrument Rack preset's macros."""

    def __init__(self, name, children=(), loadable=True, device=None, kit=None, macros=()):
        self.name = name
        self.children = list(children)
        self.is_loadable = loadable
        self.is_folder = not loadable
        self.is_device = device is not None and not kit and name == device
        self.uri = "query:Fake#" + name
        self.device = device
        self.kit = kit
        self.macros = macros


def _folder(name, *children):
    return BrowserItem(name, children, loadable=False)


class Browser(LiveObject):
    """A small Core Library; load_item applies on a later tick, like Live."""

    def __init__(self, song):
        self.song = song
        self.loads = []
        self._pending = None
        kit = {"Kick 909": 36, "Snare 909": 38, "Closed Hat 909": 42, "Open Hat 909": 46, "Clap 909": 39}
        self.drums = BrowserItem("drums", [
            BrowserItem("909 Core Kit.adg", device="Drum Rack", kit=kit),
            BrowserItem("808 Core Kit.adg", device="Drum Rack", kit={"Kick 808": 36, "Snare 808": 38, "Hat 808": 42}),
            _folder("Drum Hits", BrowserItem("Kick 909 Long.wav", device="Simpler")),
        ])
        self.instruments = BrowserItem("instruments", [
            BrowserItem("Drift", [_folder("Bass", BrowserItem("Sub Bass.adv", device="Drift"))], device="Drift"),
            BrowserItem("Wavetable", [_folder("Pad", BrowserItem("Warm Pad.adv", device="Wavetable"))], device="Wavetable"),
        ])
        self.audio_effects = BrowserItem("audio_effects", [BrowserItem("Reverb", device="Reverb")])
        # The House template's sounds; pad names as in Live's 909 Core Kit.
        core_909 = {"Bass Drum": 36, "Rim Shot": 37, "Snare Drum": 38, "Hand Clap": 39, "Closed Hi Hat": 42,
                    "Low Tom": 44, "Open Hi Hat": 46, "Crash": 48, "Ride": 50}
        self.packs = _folder("packs", _folder("Core Library", _folder("Racks", _folder("Drum Racks", _folder(
            "Drum Machines", BrowserItem("909 Core Kit.adg", device="Drum Rack", kit=core_909))))))
        self.sounds = _folder("sounds", _folder("Bass", BrowserItem("Basic FM House Bass.adg", device="Operator")),
                              _folder("Synth Keys", BrowserItem("106 Organ.adg", device="Wavetable"), BrowserItem("Basic Pluck Keys.adg", device="Operator")),
                              _folder("Effects", BrowserItem("Riser Basic.adg", device="Instrument Rack", macros=("Filter Cutoff", "Filter Reso", "Rise Amount"))))
        self.sounds.children[0].children.append(BrowserItem("Sub 808 Pitch Boom.adg", device="Instrument Rack", macros=("Filter Cutoff", "Volume")))
        for name in ("midi_effects", "user_library", "plugins"):
            setattr(self, name, _folder(name))

    def load_item(self, item):
        self.loads.append(item.name)
        self._pending = (self.song.view.selected_track, item)

    def tick(self):
        if self._pending is None:
            return
        track, item = self._pending
        self._pending = None
        device = make_device(item.device)
        if item.kit:
            device.name = item.name.rsplit(".", 1)[0]
            for pad, note in item.kit.items():
                device.add_pad(pad, note)
        elif item.name != item.device:
            device.name = item.name.rsplit(".", 1)[0]
        for parameter, name in zip(device.parameters[1:], item.macros):
            parameter.name = name
        instrument = device.class_name in ("DrumGroupDevice", "Drift", "Wavetable", "Operator", "Simpler", "InstrumentGroupDevice")
        replaced = [i for i, d in enumerate(track.devices) if instrument and d.class_name in ("DrumGroupDevice", "Drift", "Wavetable", "Operator", "Simpler", "InstrumentGroupDevice")]
        if replaced:
            track.devices[replaced[0]] = device
        else:
            track.devices.insert(0 if instrument else len(track.devices), device)


class Scene(LiveObject):
    def __init__(self, name=""):
        self.name = name
        self.fired = 0

    def fire(self):
        self.fired += 1


class CuePoint(LiveObject):
    def __init__(self, time):
        self.time = time
        self.name = ""


class SongView(LiveObject):
    def __init__(self, song):
        self.selected_track = song.tracks[0] if song.tracks else None
        self.selected_scene = song.scenes[0] if song.scenes else None


class Song(LiveObject):
    def __init__(self, tracks=2, scenes=8):
        self.scenes = [Scene() for _ in range(scenes)]
        self.tracks = [Track("%d-MIDI" % (i + 1), scenes=scenes) for i in range(tracks)]
        for track in self.tracks:
            track.song = self
        self.return_tracks = []
        self.cue_points = []
        self.master_track = Track("Main", scenes=0)
        self.view = SongView(self)
        self.tempo = 120.0
        self.signature_numerator = 4
        self.signature_denominator = 4
        self.is_playing = False
        self.record_mode = False
        self.metronome = False
        self._song_time = 0.0
        self._pending_time = None
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

    def stop_all_clips(self, quantized=True):
        for track in self.tracks:
            track.stop_all_clips(quantized)

    def continue_playing(self):
        self.is_playing = True

    def create_midi_track(self, index):
        track = Track("MIDI", True, len(self.scenes))
        track.unlisted_ticks = 3  # like Live: a sidechain source a few ticks later
        self._insert_track(track, index)

    def create_audio_track(self, index):
        self._insert_track(Track("Audio", False, len(self.scenes)), index)

    # Like Live: a new play position takes effect on a later tick, not when it is set.
    @property
    def current_song_time(self):
        return self._song_time

    @current_song_time.setter
    def current_song_time(self, value):
        self._pending_time = float(value)

    def tick(self):
        for track in self.tracks:
            track.unlisted_ticks = max(0, track.unlisted_ticks - 1)
        if getattr(self, "browser", None) is not None:
            self.browser.tick()
        if self._pending_time is not None:
            self._song_time, self._pending_time = self._pending_time, None

    @property
    def song_length(self):
        ends = [c.end_time for t in self.tracks for c in t.arrangement_clips] + [c.time for c in self.cue_points]
        return max(ends + [0.0])

    def set_or_delete_cue(self):
        for cue in self.cue_points:
            if cue.time == self._song_time:
                self.cue_points.remove(cue)
                return
        self.cue_points.append(CuePoint(self._song_time))

    def create_return_track(self):
        track = Track("%s-Return" % "ABCDEFGHIJKL"[len(self.return_tracks)], scenes=0)
        self.return_tracks.append(track)
        for other in self.tracks + self.return_tracks:
            while len(other.mixer_device.sends) < len(self.return_tracks):
                other.mixer_device.add_send()

    def _insert_track(self, track, index):
        track.song = self
        for _ in self.return_tracks:
            track.mixer_device.add_send()
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

    def delete_scene(self, index):
        del self.scenes[index]
        for track in self.tracks:
            del track.clip_slots[index]


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
