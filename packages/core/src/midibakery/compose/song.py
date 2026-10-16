"""A whole song in the Arrangement View from a genre template.

``build_song`` reads the Set, maps the roles (drums, bass, chords, lead) to
tracks, generates every section's parts with the existing generators and
returns a :class:`SongPlan`: new tracks, arrangement clips with notes, locators.
Nothing changes in Live until ``apply_song``.

- Roles go to existing tracks first: drums to a track with a Drum Rack, the
  others by track name (bass/sub/808, chord/pad/keys, lead/melody/synth).
  Missing melodic roles get a new track with a native synth; missing drums a
  new track with an empty Drum Rack (Live's API cannot load a kit).
- One harmony for the song, a second one for breaks. Sections of the same kind
  share their notes; a section with ``variation`` gets its own.
- The bass follows the kick of its section's drums. Energy sets density and velocity.
- A session clip can stand in for a role (``clips``): it is copied, looped, into
  every section where that role plays.
- Nothing lands on top of an existing arrangement clip: the plan refuses and
  names the first free bar instead.
- Automation: a role the style filters gets an Auto Filter (the track's last one,
  else a new one at the end of its chain) and every one of its clips an envelope
  of the cutoff, so a sweep never carries over into the next section.
"""

from __future__ import annotations

import math
import random
import secrets
from dataclasses import dataclass, field, replace
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from midibakery.bridge.client import BridgeError
from midibakery.compose import harmony as harmony_mod
from midibakery.compose.bass import generate_bass
from midibakery.compose.chords import generate_chords
from midibakery.compose.drums import DrumMap, generate_drums, map_pads
from midibakery.compose.harmony import Harmony
from midibakery.compose.notes import Note, fit_to_length
from midibakery.compose.plan import Call, Session, new_seed
from midibakery.compose.rhythm import Meter
from midibakery.compose.grooves import BASS, CHORDS, GROOVES, generate_groove, generate_recipe_bass, generate_recipe_chords, seventh_harmony
from midibakery.compose.hook import generate_acid, generate_arp, generate_hook, make_acid, make_arp, make_hook
from midibakery.compose.structures import ROLES, TEMPLATES, Section, Template, parse_segments, sized
from midibakery.compose.theory import Scale, diatonic_chord

NEW_TRACK_DEVICES = {"drums": "Drum Rack", "bass": "Drift", "chords": "Wavetable", "lead": "Operator"}
ROLE_WORDS = {
    "bass": ("bass", "sub", "808"),
    "chords": ("chord", "pad", "keys", "piano", "stab"),
    "lead": ("lead", "melody", "synth", "arp", "pluck"),
}
DRUM_PARTS = {
    "full": None,
    "no_kick": {"snare", "clap", "rim", "closed_hat", "pedal_hat", "open_hat", "shaker", "perc", "ride", "crash"},
    "kick_hats": {"kick", "closed_hat", "pedal_hat", "open_hat", "shaker"},
    "sparse": {"kick", "closed_hat", "rim", "shaker"},
    "kick_only": {"kick", "rim"},
    "drive": {"kick", "clap", "rim", "open_hat"},
}
PHRASE = 8  # bars
FILTER_TYPES = {"Low-pass": 0, "High-pass": 1}  # Auto Filter (Live 12) "Filter Type" values
OPEN_HZ = {"Low-pass": 20000.0, "High-pass": 20.0}
EPSILON = 1e-6


class UseClip(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["drums", "bass", "chords", "lead"]
    track: Annotated[int, Field(ge=0)]
    slot: Annotated[int, Field(ge=0)]


class SongRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    genre: Literal["house", "melodic_techno", "peak_time_techno", "drum_and_bass", "trap"]
    length: Literal["radio", "standard", "extended"] = "standard"
    minutes: Annotated[float, Field(ge=0.5, le=20, description="Target duration; overrides length")] | None = None
    start_bar: Annotated[int, Field(ge=1, description="Arrangement bar to start at (default: after the last clip)")] | None = None
    roles: dict[Literal["drums", "bass", "chords", "lead"], Annotated[int, Field(ge=0)]] = Field(
        default_factory=dict, description="Role -> track index; others are found by Drum Rack or track name"
    )
    clips: list[UseClip] = Field(default_factory=list, description="Session clips to use for a role instead of generating it")
    create_missing: bool = Field(True, description="New tracks with native synths for roles no track has")
    progression: str | None = Field(None, description="Main chords, e.g. 'i VI III VII'; default: generated")
    set_tempo: bool = Field(False, description="Set the genre's tempo (e.g. House 124, D&B 174)")
    seed: Annotated[int, Field(ge=0)] | None = None


@dataclass
class RoleTrack:
    role: str
    index: int
    name: str
    new: bool = False
    device: str | None = None
    filter: str | None = None  # Auto Filter type the song sweeps
    filter_device: int | None = None  # its index on the track
    filter_new: bool = False


@dataclass
class SongPlan:
    id: str
    template: Template
    sections: tuple[Section, ...]
    starts: list[float]  # beat of each section
    start: float
    end: float
    roles: dict[str, RoleTrack]
    actions: list[dict[str, Any]]
    locators: list[dict[str, Any]]
    tempo: float | None
    seed: int
    scale: str
    meter: str
    beats_per_bar: float
    track_identity: tuple
    bpm: float = 120.0  # the tempo the song will play at (the Set's, or the genre's with set_tempo)
    harmony: dict[str, list[str]] = field(default_factory=dict)
    notes: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def preview(self) -> dict[str, Any]:
        bpb = self.beats_per_bar
        sections = []
        for section, start in zip(self.sections, self.starts):
            sections.append({
                "name": section.name,
                "bar": int(start / bpb) + 1,
                "bars": section.bars,
                "energy": section.energy,
                "plays": {role: part for role, part in section.parts.items() if role in self.roles},
            })
        return {
            "plan_id": self.id,
            "genre": self.template.label,
            "scale": self.scale,
            "time_signature": self.meter,
            "tempo": self.tempo,
            "bpm": self.bpm,
            "duration": _duration((self.end - self.start) / self.bpm * 60),
            "bars": int((self.end - self.start) / bpb),
            "from_bar": int(self.start / bpb) + 1,
            "seed": self.seed,
            "tracks": {r: {"track": t.index, "name": t.name, **({"new": True, "device": t.device} if t.new else {}), **_filter_info(t)} for r, t in self.roles.items()},
            "sections": sections,
            "harmony": self.harmony,
            "notes": self.notes,
            "clips": len(self.actions),
            "warnings": self.warnings,
            "next": "apply_plan(plan_id) writes the song to the Arrangement View",
        }


def _duration(seconds: float) -> str:
    minutes, rest = divmod(int(round(seconds)), 60)
    return f"{minutes}:{rest:02d}"


def _filter_info(t: RoleTrack) -> dict[str, str]:
    if t.filter is None:
        return {}
    return {"automation": f"Auto Filter {t.filter} cutoff" + (" (new device)" if t.filter_new and not t.new else "")}


def _fraction(hz: float) -> float:
    """Auto Filter's Frequency: 0-1 is 20 Hz-20 kHz, logarithmic (measured in Live 12.4)."""
    return min(1.0, max(0.0, math.log(max(hz, 20.0) / 20.0) / math.log(1000.0)))


def _sweep(spec: str | None, section_bars: int, first: int, clip_length: float, bpb: float, open_hz: float) -> list[list[float]]:
    """Envelope points [beat in clip, 0-1] from a sweep spec ("20:8,20>300"); open without one."""
    if not spec:
        return [[0.0, _fraction(open_hz)]]
    points: list[list[float]] = []
    for name, offset, bars in parse_segments(spec, section_bars):
        start_hz, _, end_hz = name.partition(">")
        a = open_hz if start_hz == "-" else float(start_hz)
        b = a if not end_hz else float(end_hz)
        t0 = min(clip_length, max(0.0, (offset - first) * bpb))
        t1 = min(clip_length, max(0.0, (offset + bars - first) * bpb))
        if t1 <= t0:
            continue
        if points and abs(points[-1][0] - t0) < EPSILON and abs(points[-1][1] - _fraction(a)) > EPSILON:
            t0 += 0.01  # a jump: Live keeps one value per time
        if not points or abs(points[-1][0] - t0) > EPSILON:
            points.append([round(t0, 3), round(_fraction(a), 4)])
        points.append([round(t1, 3), round(_fraction(b), 4)])
    return points or [[0.0, _fraction(open_hz)]]


def _auto_filter(track: dict[str, Any]) -> int | None:
    devices = track.get("devices", [])
    return next((d.get("index", i) for i, d in reversed(list(enumerate(devices))) if str(d.get("class_name", "")).startswith("AutoFilter")), None)


def _is_drum_track(track: dict[str, Any]) -> bool:
    return any(d.get("class_name") == "DrumGroupDevice" for d in track.get("devices", []))


def _assign_roles(session: Session, request: SongRequest) -> tuple[dict[str, RoleTrack], list[str]]:
    tracks = session.tracks
    roles: dict[str, RoleTrack] = {}
    used: set[int] = set()
    warnings: list[str] = []
    for role, index in request.roles.items():
        track = session.track(index)
        if track.get("kind") != "midi":
            raise BridgeError("INVALID_PARAMS", f"roles.{role}: track {index + 1} '{track.get('name')}' is not a MIDI track")
        roles[role] = RoleTrack(role, index, track.get("name", ""))
        used.add(index)
    for clip in request.clips:
        if clip.role not in roles:
            roles[clip.role] = RoleTrack(clip.role, clip.track, session.track(clip.track).get("name", ""))
            used.add(clip.track)
    for role in ROLES:
        if role in roles:
            continue
        candidates = [t for t in tracks if t["index"] not in used and t.get("kind") == "midi"]
        if role == "drums":
            match = next((t for t in candidates if _is_drum_track(t)), None)
        else:
            words = ROLE_WORDS[role]
            match = next((t for t in candidates if not _is_drum_track(t) and any(w in t.get("name", "").lower() for w in words)), None)
        if match is not None:
            roles[role] = RoleTrack(role, match["index"], match.get("name", ""))
            used.add(match["index"])
    missing = [r for r in ROLES if r not in roles]
    if missing and not request.create_missing:
        warnings.append(f"No track for {', '.join(missing)}: those parts are left out (create_missing=false)")
        return roles, warnings
    template = TEMPLATES[request.genre]
    devices = {**NEW_TRACK_DEVICES, **template.style.devices}
    for offset, role in enumerate(missing):
        roles[role] = RoleTrack(role, len(tracks) + offset, f"{template.label} {role.title()}", new=True, device=devices[role])
        if role == "drums":
            warnings.append("The new drum track gets an empty Drum Rack: drop a kit on it (Live's API cannot load samples)")
    return roles, warnings


def _filter_drums(notes: list[Note], drum_map: DrumMap, part: str) -> list[Note]:
    keep = DRUM_PARTS.get(part)
    if keep is None:
        return notes
    by_pitch = {pitch: role for role, pitch in drum_map.notes.items()}
    return [n for n in notes if by_pitch.get(n.pitch) in keep]


def _energize(notes: list[Note], energy: float) -> list[Note]:
    factor = 0.75 + 0.25 * energy
    return [replace(n, velocity=max(1.0, min(127.0, n.velocity * factor))) for n in notes]


def _free_from(arrangement: dict[str, Any], track_indices: set[int]) -> float:
    ends = [c["end"] for t in arrangement.get("tracks", []) if t["index"] in track_indices for c in t["clips"]]
    return max(ends + [0.0])


def _overlap(arrangement: dict[str, Any], track: int, start: float, end: float) -> dict[str, Any] | None:
    for t in arrangement.get("tracks", []):
        if t["index"] != track:
            continue
        for clip in t["clips"]:
            if clip["start"] < end - EPSILON and start < clip["end"] - EPSILON:
                return clip
    return None


def _from(harmony: Harmony, start: float, length: float) -> Harmony:
    """The part of a harmony from `start` for `length` beats, shifted to begin at 0."""
    segments = []
    for segment in harmony.segments:
        begin, end = max(segment.start, start), min(segment.end, start + length)
        if end > begin + EPSILON:
            segments.append(harmony_mod.Segment(begin - start, end - begin, segment.chord))
    return Harmony(tuple(segments), harmony.source)


def _harmonies(request: SongRequest, style, scale: Scale, meter, r: random.Random) -> tuple[Harmony, Harmony]:
    """Main loop and break loop: the request's progression, or two different genre loops."""
    pool = list(style.progressions["minor" if _is_minor(scale) else "major"]) if len(scale) == 7 else []
    r.shuffle(pool)
    loops = [harmony_mod.timeline([diatonic_chord(scale, d) for d in degrees], meter, 8, style.chords_per_bar, "progression") for degrees in pool[:2]]
    if not loops:  # pentatonic and other scales: the generic generator
        loops = [harmony_mod.auto(scale, meter, 8, style.chords_per_bar, r) for _ in range(2)]
    if len(loops) == 1:
        loops.append(loops[0])
    if request.progression:
        try:
            loops[0] = harmony_mod.from_progression(request.progression, scale, meter, 8, style.chords_per_bar)
        except ValueError as exc:
            raise BridgeError("INVALID_PARAMS", str(exc)) from None
    return loops[0], loops[1]


def _is_minor(scale: Scale) -> bool:
    return len(scale.intervals) >= 3 and scale.intervals[2] == 3


async def build_song(call: Call, request: SongRequest) -> SongPlan:
    session = await Session(call).load()
    arrangement = await call("arrangement.get", {})
    template = TEMPLATES[request.genre]
    style = template.style
    meter, scale = session.meter, session.scale
    bpb = meter.beats_per_bar
    tempo = float(session.song.get("tempo", style.tempo))
    if request.set_tempo:
        tempo = style.tempo
    sections = sized(template, request.length, request.minutes, bpb, tempo)
    seed = request.seed if request.seed is not None else new_seed()

    roles, warnings = _assign_roles(session, request)
    existing = {t.index for t in roles.values() if not t.new}
    if request.start_bar is not None:
        start = (request.start_bar - 1) * bpb
    else:
        # After the last clip on any track: songs follow each other, they never play over one another.
        free = _free_from(arrangement, {t["index"] for t in arrangement.get("tracks", [])})
        start = -(-free // bpb) * bpb  # next bar line
    starts, cursor = [], start
    for section in sections:
        starts.append(cursor)
        cursor += section.bars * bpb
    end = cursor
    for role_track in roles.values():
        if role_track.new:
            continue
        clash = _overlap(arrangement, role_track.index, start, end)
        if clash is not None:
            first_free = -(-_free_from(arrangement, existing) // bpb) + 1
            raise BridgeError(
                "CONFLICT",
                f"Track {role_track.index + 1} '{role_track.name}' already has '{clash['name'] or 'a clip'}' at beats "
                f"{clash['start']:g}-{clash['end']:g}; start at bar {int(first_free)} or later (or leave start_bar out)",
                {"track": role_track.index, "first_free_bar": int(first_free)},
            )

    def rng(*key: object) -> random.Random:
        return random.Random(":".join(str(k) for k in (seed, *key)))

    main, alt = _harmonies(request, style, scale, meter, rng("harmony"))

    drum_map = map_pads(None)
    drums = roles.get("drums")
    if drums is not None and not drums.new:
        drum_map = map_pads(await session.drum_pads(drums.index))
    kick_pitch = drum_map.note("kick")
    swing = style.swing

    use = {c.role: c for c in request.clips}
    for role, kind in style.filters.items():
        target = roles.get(role)
        if target is None or role in use:
            continue
        target.filter = kind
        if target.new:
            target.filter_device, target.filter_new = 1, True  # after the instrument
        else:
            found = _auto_filter(session.track(target.index))
            target.filter_new = found is None
            target.filter_device = len(session.track(target.index).get("devices", [])) if found is None else found
            if found is not None:
                warnings.append(f"Track {target.index + 1}: its Auto Filter is set to {kind} for the song's sweeps")
    loops: dict[str, float] = {}
    for role, clip in use.items():
        found = next((c for c in session.track(clip.track).get("clips", []) if c["slot"] == clip.slot), None)
        if found is None:
            raise BridgeError("NOT_FOUND", f"clips: no clip in slot {clip.slot + 1} of track {clip.track + 1}")
        loops[role] = float(found["length"])

    cache: dict[tuple, list[Note]] = {}
    actions: list[dict[str, Any]] = []
    counts: dict[str, int] = {r: 0 for r in roles}
    groove = GROOVES.get(request.genre)
    if groove is not None:
        swing = groove.swing
    hook = make_hook(rng("hook"))
    arp = make_arp(rng("arp"))
    acid = make_acid(rng("acid"))

    def part_notes(role: str, part: str, section: Section, harmony: Harmony, bars: int, offset_bars: int, kick: list[float] | None) -> list[Note]:
        r = rng(section.kind, section.variation, role, part, bars, offset_bars)
        if role == "drums":
            if groove is not None and part in groove.parts:
                return generate_groove(
                    groove, part, meter, bars, r, drum_map, section.energy,
                    fill_at_end=section.fill and offset_bars + bars == section.bars,
                    crash=section.kind == "drop" and offset_bars == 0,
                    long_part=bars >= 16 and part == "full",
                    phrase_offset=offset_bars,
                )
            notes = generate_drums(meter, bars, style.drums, r, drum_map, density=0.25 + 0.6 * section.energy, swing=swing, fills=section.fill)
            return _energize(_filter_drums(notes, drum_map, {"groove": "full"}.get(part, part)), section.energy)
        if role == "bass":
            if part == "rumble":
                return _rumble(harmony, meter, bars)
            if request.genre in BASS:
                return generate_recipe_bass(BASS[request.genre], harmony, meter, bars, swing, r)
            relation = "avoid" if style.bass in ("offbeat", "pulse") else "lock"
            return _energize(generate_bass(harmony, scale, meter, bars, style.bass, r, style.bass_octave, kick or None, relation, 0.3 + 0.5 * section.energy, swing), section.energy)
        if role == "chords":
            if request.genre in CHORDS:
                pattern = CHORDS[request.genre]
                chords = seventh_harmony(harmony, scale) if pattern.sevenths else harmony
                notes = generate_recipe_chords(pattern, chords, meter, bars, swing, stabs=part in ("stabs", "on", "tease", "accent"), pad=part not in ("tease", "accent"))
                if part == "accent":  # one hit to open each phrase (the "signal" in a groove)
                    notes = _accents(notes, meter, offset_bars)
                if part == "tease":  # the hook hinted at, quieter (Peak-Time: "die Hook im Intro andeuten")
                    notes = [replace(n, velocity=max(1.0, n.velocity - 28)) for n in notes]
                return notes
            rhythm = style.break_chords if part in ("sustain", "pad") else style.chord_rhythm
            return _energize(generate_chords(harmony, meter, bars, rhythm, r, swing=swing), section.energy)
        low, high = style.lead_range
        tease = part in ("tease", "sparse")
        if style.lead == "arp":
            return generate_arp(arp, harmony, scale, meter, bars, swing, low, high, tease, velocity=82 + 12 * section.energy)
        if style.lead == "acid":
            return generate_acid(acid, harmony, meter, bars, low, high, tease, r, lift=section.kind == "drop" and section.variation > 0)
        flip = section.variation % 2 == 1
        return generate_hook(hook, harmony, scale, meter, bars, swing, low, high, tease=tease, velocity=88 + 12 * section.energy, flip=flip)

    for section, at in zip(sections, starts):
        harmony: Harmony = (alt if section.kind == "break" else main).for_length(meter, section.bars)
        section_kick: list[float] | None = None
        for role in ROLES:
            spec = section.parts.get(role)
            if spec is None or role not in roles:
                continue
            target = roles[role]
            segments = parse_segments(spec, section.bars)
            playing = [seg for seg in segments if seg[0] != "-"]
            if not playing:
                continue
            first = playing[0][1]
            until = playing[-1][1] + playing[-1][2]  # a part may stop before the section ends
            clip_length = (until - first) * bpb
            if role in use:
                loop = loops[role]
                for part, offset, bars in playing:
                    copies = int((bars * bpb + EPSILON) // loop) if loop > 0 else 0
                    for k in range(copies):
                        actions.append({"action": "copy_session_clip", "track": target.index, "slot": use[role].slot, "start": at + offset * bpb + k * loop})
                continue
            cache_key = (section.kind, section.variation, section.bars, role, spec, section.pause_every)
            if cache_key not in cache:
                notes: list[Note] = []
                for part, offset, bars in playing:
                    seg_harmony = _from(harmony, offset * bpb, bars * bpb)
                    seg_notes = part_notes(role, part, section, seg_harmony, bars, offset, section_kick)
                    seg_notes = fit_to_length(seg_notes, bars * bpb)
                    notes += [replace(n, start_time=n.start_time + (offset - first) * bpb) for n in seg_notes]
                if section.pause_every and role in ("drums", "bass"):
                    notes = _breathe(notes, role, section.pause_every, first, bpb, kick_pitch)
                if section.rest_beats and until == section.bars:
                    cut = clip_length - section.rest_beats
                    notes = fit_to_length([n for n in notes if n.start_time < cut - EPSILON], cut)
                cache[cache_key] = fit_to_length(notes, clip_length)
            notes = cache[cache_key]
            if role == "drums" and kick_pitch is not None:
                section_kick = [n.start_time + first * bpb for n in notes if n.pitch == kick_pitch]
            counts[role] += len(notes)
            action = {
                "action": "add_clip",
                "track": target.index,
                "start": at + first * bpb,
                "length": clip_length,
                "name": f"{section.name} {role.title()}",
                "notes": [n.to_spec() for n in notes],
            }
            if target.filter is not None:
                points = _sweep(section.sweeps.get(role), section.bars, first, clip_length, bpb, OPEN_HZ[target.filter])
                action["envelopes"] = [{"device": target.filter_device, "parameter": "Frequency", "points": points}]
            actions.append(action)
    locators = [{"action": "set_locator", "time": at, "name": section.name} for section, at in zip(sections, starts)]
    if len(actions) > 256:
        raise BridgeError("INVALID_PARAMS", f"The song needs {len(actions)} clips; use a shorter length or fewer copied clips (max 256)")
    return SongPlan(
        secrets.token_hex(4), template, sections, starts, start, end, roles, actions, locators,
        style.tempo if request.set_tempo else None, seed, scale.describe(), f"{meter.numerator}/{meter.denominator}", bpb,
        tuple((t.get("id"), t.get("name"), t.get("kind")) for t in session.tracks),
        tempo,
        {"main": main.describe()[: max(1, round(8 * style.chords_per_bar))], "break": alt.describe()[: max(1, round(8 * style.chords_per_bar))]},
        counts, warnings,
    )


def _rumble(harmony: Harmony, meter: Meter, bars: int) -> list[Note]:
    """A quiet low pulse between the kicks for kick-less breaks: the root on each off-beat 8th."""
    bpb = meter.beats_per_bar
    notes = []
    for beat in range(int(bars * bpb)):
        t = beat + 0.5
        root = 28 + (harmony.at(t).chord.root - 28) % 12
        notes.append(Note(root, t, 0.45, 58))
    return notes


def _accents(notes: list[Note], meter: Meter, offset_bars: int) -> list[Note]:
    """Only the first hit of each 8-bar phrase, louder."""
    bpb = meter.beats_per_bar
    kept = []
    first: dict[int, float] = {}
    for n in notes:
        phrase = int((n.start_time / bpb + offset_bars) // PHRASE)
        first[phrase] = min(first.get(phrase, n.start_time), n.start_time)
    for n in notes:
        phrase = int((n.start_time / bpb + offset_bars) // PHRASE)
        if abs(n.start_time - first[phrase]) < EPSILON and n.start_time / bpb + offset_bars - phrase * PHRASE < 1:
            kept.append(replace(n, velocity=min(127.0, n.velocity + 14), duration=max(n.duration, 0.5)))
    return kept


def _breathe(notes: list[Note], role: str, every: int, first_bar: int, bpb: float, kick_pitch: int | None) -> list[Note]:
    """Take kick and bass out of the last bar of every `every` bars of the section (T78, Spektre)."""
    def paused(n: Note) -> bool:
        bar = first_bar + int(n.start_time // bpb)
        return (bar + 1) % every == 0 and (role == "bass" or n.pitch == kick_pitch)
    return [n for n in notes if not paused(n)]


async def apply_song(call: Call, plan: SongPlan) -> dict[str, Any]:
    """New tracks (one undo step), then all clips (one undo step), then locators and tempo."""
    tracks = (await call("tracks.list", {}))["tracks"]
    if tuple((t.get("id"), t.get("name"), t.get("kind")) for t in tracks) != plan.track_identity:
        raise BridgeError("CONFLICT", f"Tracks changed since song plan {plan.id} was made; plan again")
    arrangement = await call("arrangement.get", {})
    for role_track in plan.roles.values():
        if not role_track.new and _overlap(arrangement, role_track.index, plan.start, plan.end) is not None:
            raise BridgeError("CONFLICT", f"Track {role_track.index + 1} has new arrangement clips in the song's range; plan again")
    song = await call("song.get", {})
    undo_steps = 0
    new = [t for t in plan.roles.values() if t.new]
    ops: list[dict[str, Any]] = []
    for t in sorted(new, key=lambda t: t.index):
        ops.append({"op": "track.create", "params": {"kind": "midi", "name": t.name}})
        ops.append({"op": "device.insert", "params": {"track": t.index, "name": t.device}})
    for t in plan.roles.values():
        if t.filter is None:
            continue
        if t.filter_new:
            ops.append({"op": "device.insert", "params": {"track": t.index, "name": "Auto Filter"}})
        ops.append({"op": "device.set_param", "params": {"track": t.index, "device": t.filter_device, "parameter": "Filter Type", "value": FILTER_TYPES[t.filter]}})
    if ops:
        await call("batch", {"ops": ops, "label": f"MidiBakery song {plan.id}: tracks"})
        undo_steps += 1
    if plan.tempo is not None:
        await call("song.set", {"tempo": plan.tempo})
        undo_steps += 1
    result = await call("arrangement.edit", {"actions": plan.actions})
    undo_steps += 1
    if not song["is_playing"]:
        await call("arrangement.locators", {"actions": plan.locators})
        if (await call("song.get", {}))["current_song_time"] != song["current_song_time"]:
            await call("song.position", {"beat": song["current_song_time"]})
    return {
        "plan_id": plan.id,
        "song": f"{plan.template.label}, bars {int(plan.start / plan.beats_per_bar) + 1}-{int(plan.end / plan.beats_per_bar)}",
        "clips": len(result["results"]),
        "new_tracks": [{"track": t.index, "name": t.name, "device": t.device} for t in new],
        "automation": {r: f"track {t.index + 1}, device {t.filter_device + 1}" for r, t in plan.roles.items() if t.filter is not None},
        "locators": len(plan.locators) if not song["is_playing"] else "skipped: stop the transport and plan again for locators",
        "undo": f"{undo_steps} undo step(s) for tracks/tempo/clips; each locator is its own step",
    }
