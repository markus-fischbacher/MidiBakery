"""Op catalog: session, transport, tracks, clips, notes, devices, drum racks, scenes, mixer and routing."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from midibakery.catalog.registry import OpSpec, register


class Params(BaseModel):
    model_config = ConfigDict(extra="forbid")


TrackIndex = Annotated[int, Field(ge=0, description="Zero-based index into song.tracks")]
SlotIndex = Annotated[int, Field(ge=0, description="Zero-based clip slot (= scene) index")]
Pitch = Annotated[int, Field(ge=0, le=127, description="MIDI pitch, 60 = C3 in Live")]
Beats = Annotated[float, Field(ge=0, description="Position or length in beats (quarter notes)")]


# --------------------------------------------------------------------------
# Shared value models
# --------------------------------------------------------------------------


class NoteIn(BaseModel):
    """A note to add. Fields map 1:1 to Live.Clip.MidiNoteSpecification."""

    model_config = ConfigDict(extra="forbid")

    pitch: Pitch
    start_time: Beats
    duration: Annotated[float, Field(gt=0, description="Length in beats")]
    velocity: Annotated[float, Field(ge=1, le=127)] = 100
    mute: bool = False
    probability: Annotated[float, Field(ge=0, le=1)] = 1.0
    velocity_deviation: Annotated[float, Field(ge=-127, le=127)] = 0
    release_velocity: Annotated[float, Field(ge=0, le=127)] = 64


class NoteChange(BaseModel):
    """Partial update of an existing note, addressed by its Live note_id."""

    model_config = ConfigDict(extra="forbid")

    note_id: int
    pitch: Pitch | None = None
    start_time: Beats | None = None
    duration: Annotated[float, Field(gt=0)] | None = None
    velocity: Annotated[float, Field(ge=1, le=127)] | None = None
    mute: bool | None = None
    probability: Annotated[float, Field(ge=0, le=1)] | None = None
    velocity_deviation: Annotated[float, Field(ge=-127, le=127)] | None = None
    release_velocity: Annotated[float, Field(ge=0, le=127)] | None = None


# --------------------------------------------------------------------------
# Params per op
# --------------------------------------------------------------------------


class Empty(Params):
    pass


class SongSet(Params):
    tempo: Annotated[float, Field(ge=20, le=999)] | None = None
    signature_numerator: Annotated[int, Field(ge=1, le=99)] | None = None
    signature_denominator: Literal[1, 2, 4, 8, 16] | None = None
    root_note: Annotated[int, Field(ge=0, le=11, description="0 = C ... 11 = B")] | None = None
    scale_name: str | None = Field(None, description="Live scale name, e.g. 'Major', 'Minor', 'Dorian'")
    scale_mode: bool | None = Field(None, description="Enable Live's Scale Mode highlighting/folding")
    metronome: bool | None = None
    loop: bool | None = None
    loop_start: Beats | None = None
    loop_length: Annotated[float, Field(gt=0)] | None = None


class Transport(Params):
    action: Literal["play", "stop", "continue", "stop_clips", "toggle_record"] = Field(description="stop_clips = Stop All Clips in the Session View (quantized, transport keeps running)")
    from_beat: Beats | None = Field(None, description="Jump here before 'play'")


class TrackCreate(Params):
    kind: Literal["midi", "audio"] = "midi"
    index: int = Field(-1, ge=-1, description="Insert position, -1 = append")
    name: str | None = None


class TrackRef(Params):
    track: TrackIndex


class TrackSet(Params):
    track: TrackIndex
    name: str | None = None
    color_index: Annotated[int, Field(ge=0, le=69)] | None = None
    mute: bool | None = None
    solo: bool | None = None
    arm: bool | None = None
    volume: Annotated[float, Field(ge=0, le=1, description="Normalised fader value; 0.85 = 0 dB")] | None = None
    pan: Annotated[float, Field(ge=-1, le=1)] | None = None


class ClipRef(Params):
    """A session clip by `slot`, or an Arrangement View clip by `arrangement_clip` (index in time order)."""

    track: TrackIndex
    slot: SlotIndex | None = None
    arrangement_clip: Annotated[int, Field(ge=0, description="Arrangement clip index on the track, in time order")] | None = None

    @model_validator(mode="after")
    def _one_clip(self):
        if (self.slot is None) == (self.arrangement_clip is None):
            raise ValueError("give either slot or arrangement_clip")
        return self


class ClipCreate(Params):
    track: TrackIndex
    slot: SlotIndex
    length: Annotated[float, Field(gt=0, le=4096, description="Clip length in beats")] = 4.0
    name: str | None = None


class ClipSet(ClipRef):
    name: str | None = None
    color_index: Annotated[int, Field(ge=0, le=69)] | None = None
    looping: bool | None = None
    loop_start: Beats | None = None
    loop_end: Beats | None = None


class ClipLaunch(Params):
    track: TrackIndex
    slot: SlotIndex
    action: Literal["fire", "stop"] = "fire"


class NotesGet(ClipRef):
    from_time: Beats = 0.0
    time_span: Annotated[float, Field(gt=0)] | None = Field(None, description="Default: whole clip")
    from_pitch: Pitch = 0
    pitch_span: Annotated[int, Field(ge=1, le=128)] = 128


class NotesApply(ClipRef):
    """Edit a MIDI clip as a diff, so untouched notes keep their ids and data."""

    add: list[NoteIn] = Field(default_factory=list)
    modify: list[NoteChange] = Field(default_factory=list)
    remove: list[int] = Field(default_factory=list, description="note_ids to delete")

    @model_validator(mode="after")
    def _not_empty(self) -> NotesApply:
        if not (self.add or self.modify or self.remove):
            raise ValueError("notes.apply needs at least one of add, modify, remove")
        return self


class DeviceInsert(Params):
    track: TrackIndex
    name: str = Field(description="Native Live device name as shown in the browser, e.g. 'Operator', 'Drift', 'Reverb'")
    index: int = Field(-1, ge=-1, description="Position in the chain, -1 = end")


BrowserCategory = Literal["drums", "instruments", "audio_effects", "midi_effects", "sounds", "packs", "user_library", "plugins"]


class BrowserSearch(Params):
    query: str = Field(min_length=1, description="Words that must all be in the item name, e.g. '909 kit', 'reese bass'")
    category: BrowserCategory | Literal["all"] = "all"
    limit: int = Field(20, ge=1, le=100)
    loadable_only: bool = True


class BrowserLoad(Params):
    track: TrackIndex
    path: list[str] = Field(min_length=2, description="Browser path from browser.search, e.g. ['drums', '909 Core Kit.adg']")


ChainPath = Annotated[
    list[Annotated[int, Field(ge=0)]],
    Field(max_length=8, description="Into racks: chain, device pairs below `device`, e.g. [1, 0] = first device of chain 2"),
]


ReturnIndex = Annotated[int, Field(ge=0, description="Zero-based index into the return tracks (A = 0)")]


class DeviceRef(Params):
    """A device on a track or, with return_track instead of track, on a return track."""

    track: TrackIndex | None = None
    return_track: ReturnIndex | None = None
    device: Annotated[int, Field(ge=0)]
    chain_path: ChainPath = Field(default_factory=list)

    @model_validator(mode="after")
    def _one_owner(self) -> DeviceRef:
        if (self.track is None) == (self.return_track is None):
            raise ValueError("give either track or return_track")
        return self


class DrumPadsGet(Params):
    track: TrackIndex
    device: Annotated[int, Field(ge=0)] | None = Field(
        None, description="Drum Rack device index; default: first Drum Rack on the track (also inside racks)"
    )


class DeviceParamSet(DeviceRef):
    parameter: int | str = Field(description="Parameter index or exact name")
    value: float = Field(description="Raw parameter value within the parameter's min/max")


class MixerTarget(Params):
    """Exactly one of track, return_track or master."""

    track: TrackIndex | None = None
    return_track: ReturnIndex | None = None
    master: bool = False

    def _targets(self) -> int:
        return (self.track is not None) + (self.return_track is not None) + bool(self.master)


class MixerGet(MixerTarget):
    options: bool = Field(False, description="Also list the available input/output routings and channels (single target only)")

    @model_validator(mode="after")
    def _one_or_none(self) -> MixerGet:
        if self._targets() > 1:
            raise ValueError("give at most one of track, return_track, master (none = the whole mixer)")
        if self.options and not self._targets():
            raise ValueError("options needs a track, return_track or master")
        return self


class SendSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    return_track: ReturnIndex
    value: Annotated[float, Field(ge=0, le=1, description="Normalised send level")] | None = None
    db: Annotated[float, Field(le=6, description="Send level in dB as Live shows it, e.g. -12")] | None = None

    @model_validator(mode="after")
    def _one_level(self) -> SendSet:
        if (self.value is None) == (self.db is None):
            raise ValueError("give either value or db for a send")
        return self


class MixerSet(MixerTarget):
    volume: Annotated[float, Field(ge=0, le=1, description="Normalised fader value; 0.85 = 0 dB")] | None = None
    volume_db: Annotated[float, Field(le=6, description="Fader in dB as Live shows it, e.g. -6")] | None = None
    pan: Annotated[float, Field(ge=-1, le=1)] | None = None
    sends: list[SendSet] = Field(default_factory=list)
    mute: bool | None = None
    solo: bool | None = None
    crossfade: Literal["A", "none", "B"] | None = None
    input_routing: str | None = Field(None, description="Input type as Live names it, e.g. 'All Ins', 'No Input', a track name")
    input_channel: str | None = Field(None, description="Input channel as Live names it, e.g. 'All Channels', 'Post FX'")
    output_routing: str | None = Field(None, description="Output type as Live names it, e.g. 'Master', 'Sends Only', a track name")
    output_channel: str | None = Field(None, description="Output channel as Live names it, e.g. 'Track In'")

    @model_validator(mode="after")
    def _valid(self) -> MixerSet:
        if self._targets() != 1:
            raise ValueError("give exactly one of track, return_track, master")
        if self.volume is not None and self.volume_db is not None:
            raise ValueError("give volume or volume_db, not both")
        changes = self.model_dump(exclude={"track", "return_track", "master"}, exclude_none=True, exclude_defaults=True)
        if not changes:
            raise ValueError("mixer.set needs at least one change")
        if self.master and (self.sends or self.mute is not None or self.solo is not None or self.crossfade is not None):
            raise ValueError("the master track has no mute, solo, sends or crossfade assignment")
        return self


class ReturnCreate(Params):
    name: str | None = None
    device: str | None = Field(None, description="Native device for the return, e.g. 'Reverb', 'Delay', 'Echo' (Live 12.3+)")


class MacroSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    macro: Annotated[int, Field(ge=1, le=16)]
    value: Annotated[float, Field(ge=0, le=127)]


class ChainEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    mute: bool | None = None
    solo: bool | None = None
    volume_db: Annotated[float, Field(le=6)] | None = None
    pan: Annotated[float, Field(ge=-1, le=1)] | None = None
    in_note: Pitch | None = Field(None, description="Drum Rack only: the pad note that plays this chain")
    insert_devices: list[str] = Field(default_factory=list, description="Native devices to append, e.g. ['Simpler'] or ['Operator', 'Reverb']")


class ChainChange(ChainEdit):
    chain: Annotated[int, Field(ge=0)]


class RackSet(DeviceRef):
    macros: list[MacroSet] = Field(default_factory=list)
    chains: list[ChainChange] = Field(default_factory=list)
    add_chain: ChainEdit | None = Field(None, description="Append a chain (Live 12.3+), e.g. a Drum Rack pad: {in_note: 36, insert_devices: ['Simpler']}")

    @model_validator(mode="after")
    def _not_empty(self) -> RackSet:
        if not (self.macros or self.chains or self.add_chain is not None):
            raise ValueError("rack.set needs macros, chains or add_chain")
        return self


class ArrangementGet(Params):
    track: TrackIndex | None = Field(None, description="Only this track (default: all tracks)")


class Envelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device: Annotated[int, Field(ge=0, description="Device index on the clip's track")]
    parameter: str = Field(description="Exact parameter name")
    points: list[tuple[float, float]] = Field(min_length=1, max_length=512, description="[beat in clip, 0-1 of the parameter range]; lines between")


class AddClip(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["add_clip"]
    track: TrackIndex
    start: Beats
    length: Annotated[float, Field(gt=0, le=4096, description="Beats")]
    name: str | None = None
    color_index: Annotated[int, Field(ge=0, le=69)] | None = None
    notes: list[NoteIn] = Field(default_factory=list, description="Notes, start_time relative to the clip start")
    envelopes: list[Envelope] = Field(default_factory=list, max_length=8, description="Clip automation; values are absolute while the clip plays")


class CopySessionClip(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["copy_session_clip"]
    track: TrackIndex
    slot: SlotIndex
    start: Beats


class DeleteArrangementClip(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["delete_clip"]
    track: TrackIndex
    clip: Annotated[int, Field(ge=0, description="arrangement_clip index from arrangement.get")]


class AddTakeLane(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["add_take_lane"]
    track: TrackIndex
    name: str | None = None


class AddTakeClip(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["add_take_clip"]
    track: TrackIndex
    lane: Annotated[int, Field(ge=-1, description="Take lane index; -1 = the lane created last in this edit")]
    start: Beats
    length: Annotated[float, Field(gt=0, le=4096, description="Beats")]
    name: str | None = None
    notes: list[NoteIn] = Field(default_factory=list, description="Notes, start_time relative to the clip start")


class SetLocator(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["set_locator"]
    time: Beats
    name: str | None = None


class DeleteLocator(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["delete_locator"]
    time: Beats


ClipAction = Annotated[AddClip | CopySessionClip | DeleteArrangementClip | AddTakeLane | AddTakeClip, Field(discriminator="action")]
LocatorAction = Annotated[SetLocator | DeleteLocator, Field(discriminator="action")]


class ArrangementEdit(Params):
    """Clip actions run in order as one undo step; a clip never lands on an existing one (CONFLICT)."""

    actions: list[ClipAction] = Field(min_length=1, max_length=256)


class ArrangementLocators(Params):
    """Set (and name) or delete locators. Needs a stopped transport; the play position is restored."""

    actions: list[LocatorAction] = Field(min_length=1, max_length=64)


class SongPosition(Params):
    beat: Beats


class ArrangementTool(Params):
    """Clip actions first (one undo step), then locators (transport must be stopped). A clip never lands on an existing one.
    For take lanes use compose_takes."""

    actions: list[
        Annotated[AddClip | CopySessionClip | DeleteArrangementClip | SetLocator | DeleteLocator, Field(discriminator="action")]
    ] = Field(min_length=1, max_length=256)


class SceneCreate(Params):
    index: int = Field(-1, ge=-1, description="Insert position, -1 = append")
    name: str | None = None


class SceneRef(Params):
    scene: Annotated[int, Field(ge=0)]


class History(Params):
    action: Literal["undo", "redo"]


class BatchItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: str
    params: dict[str, Any] = Field(default_factory=dict)


class Batch(Params):
    """Run several ops in one Live main-thread tick and one undo step."""

    ops: list[BatchItem] = Field(min_length=1, max_length=256)
    label: str | None = Field(None, description="Shown in logs; Live has no undo-step names")


# --------------------------------------------------------------------------
# Registration
# --------------------------------------------------------------------------

for spec in [
    OpSpec("live.health", Empty, "Bridge and Live version, supported ops", read_only=True, timeout=2.0),
    OpSpec("song.get", Empty, "Tempo, signature, scale, transport and loop state", read_only=True),
    OpSpec("song.set", SongSet, "Change tempo, signature, scale or loop settings", read_only=False),
    OpSpec("transport.control", Transport, "Play, stop, continue, stop all session clips or toggle arrangement record", read_only=False),
    OpSpec("tracks.list", Empty, "All tracks with mixer state, devices and clip slots", read_only=True),
    OpSpec("track.create", TrackCreate, "Create a MIDI or audio track", read_only=False),
    OpSpec("track.set", TrackSet, "Rename, recolor or change mixer state of a track", read_only=False),
    OpSpec("track.delete", TrackRef, "Delete a track", read_only=False, destructive=True),
    OpSpec("clip.create", ClipCreate, "Create an empty MIDI clip in a session slot", read_only=False),
    OpSpec("clip.get", ClipRef, "Clip properties", read_only=True),
    OpSpec("clip.set", ClipSet, "Rename, recolor or change loop of a clip", read_only=False),
    OpSpec("clip.delete", ClipRef, "Delete a session clip", read_only=False, destructive=True),
    OpSpec("clip.launch", ClipLaunch, "Fire or stop a session clip", read_only=False),
    OpSpec("notes.get", NotesGet, "Read notes with ids, probability and velocity deviation", read_only=True),
    OpSpec("notes.apply", NotesApply, "Add, modify and remove notes by id", read_only=False, destructive=True),
    OpSpec("device.insert", DeviceInsert, "Insert a native Live device", read_only=False, min_live=(12, 3, 0)),
    OpSpec("browser.search", BrowserSearch, "Find presets, kits and devices in Live's browser by name", read_only=True, timeout=30.0),
    OpSpec("browser.load", BrowserLoad, "Load a browser item onto a track (an instrument or kit replaces the instrument)", read_only=False, timeout=10.0),
    OpSpec("device.params", DeviceRef, "Parameters of a device with ranges and display values", read_only=True),
    OpSpec("drum_rack.pads", DrumPadsGet, "Filled Drum Rack pads with their MIDI note and name", read_only=True),
    OpSpec("device.set_param", DeviceParamSet, "Set one device parameter", read_only=False),
    OpSpec("mixer.get", MixerGet, "Volume, pan, sends, mute/solo, crossfade and routing of tracks, returns and master", read_only=True),
    OpSpec("mixer.set", MixerSet, "Change volume (normalised or dB), pan, sends, mute/solo, crossfade or routing", read_only=False),
    OpSpec("return.create", ReturnCreate, "Create a return track, optionally with a native device", read_only=False),
    OpSpec("rack.get", DeviceRef, "Chains (devices, mixer, drum pad note) and macros of a rack", read_only=True),
    OpSpec("rack.set", RackSet, "Set macros, edit chains, or add a chain to a rack", read_only=False),
    OpSpec("arrangement.get", ArrangementGet, "Arrangement clips per track (start, end), locators, song length", read_only=True),
    OpSpec("arrangement.edit", ArrangementEdit, "Add MIDI clips with notes, copy session clips or delete arrangement clips", read_only=False, timeout=15.0, min_live=(12, 1, 10)),
    OpSpec("arrangement.locators", ArrangementLocators, "Set, name or delete arrangement locators", read_only=False, timeout=30.0),
    OpSpec("song.position", SongPosition, "Move the play position and wait until Live applied it", read_only=False, timeout=5.0),
    OpSpec("scene.create", SceneCreate, "Create a scene", read_only=False),
    OpSpec("scene.fire", SceneRef, "Launch a scene", read_only=False),
    OpSpec("history.step", History, "Undo or redo in Live", read_only=False),
    OpSpec("batch", Batch, "Run several ops atomically as one undo step", read_only=False, timeout=15.0),
]:
    register(spec)
