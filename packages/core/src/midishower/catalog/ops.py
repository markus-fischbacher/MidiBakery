"""Phase-1 op catalog: session, transport, tracks, clips, notes, devices, scenes."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from midishower.catalog.registry import OpSpec, register


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
    action: Literal["play", "stop", "continue", "toggle_record"]
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
    track: TrackIndex
    slot: SlotIndex


class ClipCreate(Params):
    track: TrackIndex
    slot: SlotIndex
    length: Annotated[float, Field(gt=0, le=4096, description="Clip length in beats")] = 4.0
    name: str | None = None


class ClipSet(Params):
    track: TrackIndex
    slot: SlotIndex
    name: str | None = None
    color_index: Annotated[int, Field(ge=0, le=69)] | None = None
    looping: bool | None = None
    loop_start: Beats | None = None
    loop_end: Beats | None = None


class ClipLaunch(Params):
    track: TrackIndex
    slot: SlotIndex
    action: Literal["fire", "stop"] = "fire"


class NotesGet(Params):
    track: TrackIndex
    slot: SlotIndex
    from_time: Beats = 0.0
    time_span: Annotated[float, Field(gt=0)] | None = Field(None, description="Default: whole clip")
    from_pitch: Pitch = 0
    pitch_span: Annotated[int, Field(ge=1, le=128)] = 128


class NotesApply(Params):
    """Edit a MIDI clip as a diff, so untouched notes keep their ids and data."""

    track: TrackIndex
    slot: SlotIndex
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


class DeviceRef(Params):
    track: TrackIndex
    device: Annotated[int, Field(ge=0)]


class DeviceParamSet(Params):
    track: TrackIndex
    device: Annotated[int, Field(ge=0)]
    parameter: int | str = Field(description="Parameter index or exact name")
    value: float = Field(description="Raw parameter value within the parameter's min/max")


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
    OpSpec("transport.control", Transport, "Play, stop, continue or toggle arrangement record", read_only=False),
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
    OpSpec("device.params", DeviceRef, "Parameters of a device with ranges and display values", read_only=True),
    OpSpec("device.set_param", DeviceParamSet, "Set one device parameter", read_only=False),
    OpSpec("scene.create", SceneCreate, "Create a scene", read_only=False),
    OpSpec("scene.fire", SceneRef, "Launch a scene", read_only=False),
    OpSpec("history.step", History, "Undo or redo in Live", read_only=False),
    OpSpec("batch", Batch, "Run several ops atomically as one undo step", read_only=False, timeout=15.0),
]:
    register(spec)
