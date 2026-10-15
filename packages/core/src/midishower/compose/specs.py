"""Request models for the composition tools; also used as MCP tool schemas."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from midishower.compose.bass import BassStyle, KickRelation
from midishower.compose.chords import ChordRhythm
from midishower.compose.drums import DrumStyle
from midishower.compose.transform import ArpDirection, Operation

TrackIndex = Annotated[int, Field(ge=0, description="Zero-based track index")]
SlotIndex = Annotated[int, Field(ge=0, description="Zero-based clip slot (= scene) index")]
Pitch = Annotated[int, Field(ge=0, le=127)]
Seed = Annotated[
    int | None,
    Field(description="Same seed + same inputs = same notes. Omit for a fresh idea; the used seed is returned."),
]
Amount = Annotated[float, Field(ge=0, le=1)]
Swing = Annotated[float, Field(ge=0, le=1, description="Delays every off-beat swing_unit; 0 straight, 1 full triplet feel")]
SwingUnit = Annotated[Literal["1/16", "1/8"], Field(description="Note value that swings: 1/16 (house, techno) or 1/8 (hip-hop, shuffle)")]
SWING_UNITS = {"1/16": 0.25, "1/8": 0.5}


class Spec(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ClipLocation(Spec):
    track: TrackIndex
    slot: SlotIndex


class Generate(Spec):
    track: TrackIndex
    slot: Annotated[
        int | None, Field(ge=0, description="Zero-based clip slot (= scene) index. Default: the track's first free slot")
    ] = None
    bars: Annotated[int, Field(ge=1, le=64, description="Length in bars of the song's time signature")] = 4
    seed: Seed = None
    if_exists: Literal["error", "replace", "merge"] = Field(
        "error",
        description="If the slot already holds a clip: 'error', 'replace' its notes, or 'merge' (add on top)",
    )
    clip_name: str | None = None


class Harmonic(Generate):
    progression: str | None = Field(
        None,
        description="Chords as roman numerals relative to the song scale ('i VI III VII', 'ii7 V7 I') or names ('Am F C G'). "
        "Default: chords_from, else the chords of an earlier step in the same plan, else a generated functional progression.",
    )
    chords_from: ClipLocation | None = Field(None, description="Detect the chords of an existing MIDI clip and follow them")
    chords_per_bar: Annotated[float, Field(gt=0, le=4, description="1 = a chord per bar, 2 = two, 0.5 = one per two bars")] = 1.0


class DrumsSpec(Generate):
    kind: Literal["drums"] = "drums"
    style: DrumStyle = "house"
    density: Amount = 0.5
    swing: Swing = 0.0
    swing_unit: SwingUnit = "1/16"
    fills: bool = Field(True, description="Fill at the end of each 4-bar phrase")
    chance: Amount = Field(
        1.0,
        description="Like Live's note Chance for ghost notes, some hats and extra kicks: 1 = every hit "
        "always plays (default), 0.5 = the style's natural variation, 0 = twice as much; backbeats always play",
    )
    device: Annotated[int | None, Field(ge=0, description="Drum Rack device index; default: first Drum Rack")] = None


class BassSpec(Harmonic):
    kind: Literal["bass"] = "bass"
    style: BassStyle = "syncopated"
    octave: Annotated[int, Field(ge=-1, le=4, description="Live octave of the root, C1 = 36")] = 1
    follow_kick: ClipLocation | None = Field(None, description="Drum clip whose kick the bass should lock to or avoid")
    kick_relation: KickRelation = "lock"
    density: Amount = 0.5
    swing: Swing = 0.0
    swing_unit: SwingUnit = "1/16"


class ChordsSpec(Harmonic):
    kind: Literal["chords"] = "chords"
    rhythm: ChordRhythm = "sustain"
    voices: Literal[3, 4] = 3
    low: Pitch = 52
    high: Pitch = 76
    sevenths: bool = Field(False, description="Use seventh chords for a generated progression")
    swing: Swing = 0.0
    swing_unit: SwingUnit = "1/16"

    @model_validator(mode="after")
    def _range(self) -> ChordsSpec:
        if self.high - self.low < 12:
            raise ValueError("chords need a range of at least one octave (high - low >= 12)")
        return self


class MelodySpec(Harmonic):
    kind: Literal["melody"] = "melody"
    low: Pitch = 60
    high: Pitch = 84
    density: Amount = 0.5
    swing: Swing = 0.0
    swing_unit: SwingUnit = "1/16"

    @model_validator(mode="after")
    def _range(self) -> MelodySpec:
        if self.high - self.low < 7:
            raise ValueError("melody range must span at least a fifth (high - low >= 7)")
        return self


class TransformSpec(Spec):
    kind: Literal["transform"] = "transform"
    track: TrackIndex
    slot: SlotIndex
    operation: Operation
    note_ids: list[int] | None = Field(None, description="Only these notes (default: all notes in the clip)")
    amount: Amount = Field(0.5, description="humanize/variation intensity")
    grid: Annotated[float, Field(gt=0, le=4, description="quantize grid in beats (0.25 = 1/16)")] = 0.25
    strength: Amount = Field(1.0, description="quantize strength")
    swing: Swing = 0.0
    swing_unit: SwingUnit = "1/16"
    axis: Pitch | None = Field(None, description="invert: mirror pitch (default: middle of the notes' range)")
    semitones: int = Field(
        0, ge=-48, le=48,
        description="transpose: chromatic half steps (12 = one octave). Use this for 'n semitones / half steps / up an octave'",
    )
    steps: int = Field(
        0, ge=-24, le=24,
        description="transpose: diatonic scale steps in the song key (2 = up a third, not 2 semitones). Only for 'n scale steps'",
    )
    rate: Annotated[float, Field(gt=0, le=4, description="arpeggiate: step length in beats")] = 0.25
    direction: ArpDirection = "up"
    octaves: Annotated[int, Field(ge=1, le=3)] = 1
    seed: Seed = None

    @model_validator(mode="after")
    def _transpose_amount(self) -> TransformSpec:
        if self.operation == "transpose" and bool(self.semitones) == bool(self.steps):
            raise ValueError("transpose needs either semitones (chromatic, 12 = octave) or steps (scale steps in key), not both")
        return self


Step = Annotated[DrumsSpec | BassSpec | ChordsSpec | MelodySpec | TransformSpec, Field(discriminator="kind")]
