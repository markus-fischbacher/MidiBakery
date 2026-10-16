"""Variations of one part as take lanes (Live 12.2+), to comp the best one in Live.

All takes of a request share one harmony, so they can be compared bar by bar:
the chords of an arrangement clip that plays in that range (``chords_from``, or
found on a chord/pad/keys track), else a generated loop. Only the notes differ,
each take with its own seed. Nothing on the track's main lane changes.
"""

from __future__ import annotations

import random
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from midibakery.bridge.client import BridgeError
from midibakery.compose import harmony as harmony_mod
from midibakery.compose.bass import generate_bass
from midibakery.compose.chords import generate_chords
from midibakery.compose.drums import generate_drums, map_pads
from midibakery.compose.harmony import Harmony
from midibakery.compose.hook import generate_hook, make_hook
from midibakery.compose.melody import generate_melody
from midibakery.compose.notes import Note, fit_to_length
from midibakery.compose.plan import Call, Session, new_seed
from midibakery.compose.specs import SWING_UNITS, BassSpec, ChordsSpec, DrumsSpec, MelodySpec

CHORD_WORDS = ("chord", "pad", "keys", "piano", "stab")
SPECS = {"melody": MelodySpec, "bass": BassSpec, "chords": ChordsSpec, "drums": DrumsSpec}


class ArrangementClipRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    track: Annotated[int, Field(ge=0)]
    arrangement_clip: Annotated[int, Field(ge=0)]


class TakesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    track: Annotated[int, Field(ge=0, description="MIDI track that gets the take lanes")]
    start_bar: Annotated[int, Field(ge=1, description="Arrangement bar where the takes start")]
    bars: Annotated[int, Field(ge=1, le=64)] = 8
    kind: Literal["hook", "melody", "bass", "chords", "drums"] = "hook"
    count: Annotated[int, Field(ge=2, le=8)] = 4
    chords_from: ArrangementClipRef | None = Field(None, description="Follow this arrangement clip's chords (default: a chord/pad/keys track playing there)")
    params: dict[str, Any] = Field(default_factory=dict, description="Extra fields of the compose tool of this kind, e.g. {'density': 0.4}")
    seed: Annotated[int, Field(ge=0)] | None = None


async def _harmony(call: Call, session: Session, request: TakesRequest, start: float, length: float, rng: random.Random) -> tuple[Harmony, str]:
    meter, scale = session.meter, session.scale
    bars = request.bars
    arrangement = await call("arrangement.get", {})
    source = None
    if request.chords_from is not None:
        source = (request.chords_from.track, request.chords_from.arrangement_clip)
    else:
        for track in arrangement["tracks"]:
            if track["index"] == request.track or not any(w in track["name"].lower() for w in CHORD_WORDS):
                continue
            clip = next((c for c in track["clips"] if c["start"] < start + length and start < c["end"] and c["is_midi"]), None)
            if clip is not None:
                source = (track["index"], clip["index"])
                break
    if source is None:
        return harmony_mod.auto(scale, meter, bars, 1.0, rng), "generated"
    track_index, clip_index = source
    clip = next(c for t in arrangement["tracks"] if t["index"] == track_index for c in t["clips"] if c["index"] == clip_index)
    notes = (await call("notes.get", {"track": track_index, "arrangement_clip": clip_index}))["notes"]
    offset = start - clip["start"]  # takes start inside or before the chord clip
    window = [
        {**n, "start_time": n["start_time"] - offset}
        for n in notes
        if n["start_time"] + n["duration"] > offset and n["start_time"] < offset + length
    ]
    if not window:
        return harmony_mod.auto(scale, meter, bars, 1.0, rng), "generated"
    try:
        return harmony_mod.detect(window, scale, meter, bars, 1.0), f"from '{clip['name'] or 'clip'}' on track {track_index + 1}"
    except ValueError:
        return harmony_mod.auto(scale, meter, bars, 1.0, rng), "generated"


def _notes(request: TakesRequest, session: Session, harmony: Harmony, seed: int, pads: list[dict] | None) -> list[Note]:
    meter, scale, bars = session.meter, session.scale, request.bars
    rng = random.Random(seed)
    if request.kind == "hook":
        low, high = request.params.get("low", 72), request.params.get("high", 89)
        return generate_hook(make_hook(rng), harmony, scale, meter, bars, request.params.get("swing", 0.0), low, high)
    try:
        spec = SPECS[request.kind].model_validate({"track": 0, "slot": 0, **request.params})
    except ValueError as exc:
        raise BridgeError("INVALID_PARAMS", f"params: {exc}") from None
    unit = SWING_UNITS[spec.swing_unit]
    if request.kind == "drums":
        return generate_drums(meter, bars, spec.style, rng, map_pads(pads), density=spec.density, swing=spec.swing, swing_unit=unit, fills=spec.fills, chance=spec.chance)
    if request.kind == "bass":
        return generate_bass(harmony, scale, meter, bars, spec.style, rng, spec.octave, density=spec.density, swing=spec.swing, swing_unit=unit)
    if request.kind == "chords":
        return generate_chords(harmony, meter, bars, spec.rhythm, rng, spec.low, spec.high, spec.voices, swing=spec.swing, swing_unit=unit)
    return generate_melody(harmony, scale, meter, bars, rng, spec.low, spec.high, spec.density, swing=spec.swing, swing_unit=unit)


async def build_takes(call: Call, request: TakesRequest) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """The arrangement.edit actions for the take lanes, and a summary for the reply."""
    session = await Session(call).load()
    track = session.track(request.track)
    if track.get("kind") != "midi":
        raise BridgeError("INVALID_PARAMS", f"Track {request.track + 1} '{track.get('name')}' is not a MIDI track")
    bpb = session.meter.beats_per_bar
    start, length = (request.start_bar - 1) * bpb, request.bars * bpb
    base = request.seed if request.seed is not None else new_seed()
    harmony, harmony_source = await _harmony(call, session, request, start, length, random.Random(f"{base}:harmony"))
    pads = await session.drum_pads(request.track) if request.kind == "drums" else None
    actions: list[dict[str, Any]] = []
    takes = []
    for k in range(request.count):
        seed = base + k
        notes = fit_to_length(_notes(request, session, harmony, seed, pads), length)
        name = f"Take {k + 1} · {request.kind} · seed {seed}"
        actions.append({"action": "add_take_lane", "track": request.track, "name": name})
        actions.append({"action": "add_take_clip", "track": request.track, "lane": -1, "start": start, "length": length, "name": name, "notes": [n.to_spec() for n in notes]})
        takes.append({"take": k + 1, "seed": seed, "notes": len(notes)})
    summary = {
        "track": request.track,
        "bars": f"{request.start_bar}-{request.start_bar + request.bars - 1}",
        "kind": request.kind,
        "chords": harmony.describe(),
        "chords_from": harmony_source,
        "takes": takes,
        "next": "Comp in Live: show the take lanes of the track and pick or combine takes; Undo removes all takes",
    }
    return actions, summary
