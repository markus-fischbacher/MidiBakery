"""MCP server exposing MidiBakery to Claude and other MCP clients.

Tools are generated from the op catalog so their schemas never drift from
what the Live bridge accepts. A few read tools combine ops to save round
trips for the model.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import secrets
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated, Any

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from mcp_types import CallToolResult, InputRequiredResult, TextContent
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from midibakery import __version__, license
from midibakery.bridge import BridgeClient, BridgeError
from midibakery.catalog import get_op
from midibakery.catalog.ops import ArrangementTool, ClipRef, Empty
from midibakery.compose import ComposeRequest, PlanStore, apply_plan, build_plan
from midibakery.compose.patterns import bass_names, drum_names, lead_names, mood_names
from midibakery.compose.plan import Plan, new_seed
from midibakery.compose.rollback import locators as read_locators, restore_locators, undo_edit
from midibakery.compose.references import find_reference, load_references
from midibakery.compose.song import SongPlan, SongRequest, apply_song, build_song
from midibakery.mcp.confirm import confirm, request_state

INSTRUCTIONS = """\
MidiBakery builds EDM song sketches in the Ableton Live 12 set that is open right now.
- A whole song: plan_song, then apply_plan; say which tracks it used and created. "Again, different" = plan_song
  again without seed; "seed 42" = that seed. get_reference lists the analyzed songs and imported Sets; plan_song(reference=name)
  follows one. "X but with the bass/lead/drums/chords of Set Y" = reference X + loops_from {"bass": "Y"}.
- get_session first when you need tracks or clips. Tracks and clips are zero-based; users count from 1 ("track 1" = index 0).
  Times are beats (quarter notes); bar n starts at beat (n-1) * beats per bar.
- compose rewrites one part: give the arrangement clip by index or name ('Drop Bass'); it replaces that clip's notes, by seed.
  Other chords in half a clip: compose chords on that clip with a progression naming every bar.
- edit_arrangement moves, copies or deletes arrangement clips and locators; undo takes back any write.
- Deleting clips and replacing notes ask the user first; a declined change returns CANCELLED.
"""

# plan_song's options the model does not see: they keep these values (a song sketch with everything on).
SONG_DEFAULTS: dict[str, Any] = {"set_tempo": True, "fill_missing": True}
SONG_HIDDEN = ("minutes", "start_bar", "roles", "clips", "create_missing", "sounds", "mix", "fx", "sidechain",
               "sidechain_mode", "set_tempo", "fill_missing")

# Ops that delete something the user made.
CONFIRM_OPS = {"clip.delete"}

Runner = Callable[[dict[str, Any], Context | None], Awaitable[Any]]

# (tool name, op, title); annotations come from the op spec.
TOOL_OPS: list[tuple[str, str, str]] = [
    ("set_song", "song.set", "Set tempo, signature, scale or loop"),
    ("transport", "transport.control", "Play / stop / stop all clips / record"),
    ("create_track", "track.create", "Create track"),
    ("delete_clip", "clip.delete", "Delete clip"),
    ("get_arrangement", "arrangement.get", "Get arrangement clips and locators"),
    ("undo", "history.step", "Undo / redo"),
]


COMPOSE_DESCRIPTION = (
        "Write one part as a new MIDI clip in the song scale and time signature. kind drums: pattern on the track's "
        "Drum Rack pads (found by name, General MIDI fallback); bass: follows the chords and can lock to or avoid a "
        "drum clip's kick (follow_kick); chords: voice-led, a functional progression unless given one; melody: motifs "
        "(A A' A B), chord tones on strong beats. Fields tagged (kind) are only for those kinds. "
        "pattern replaces style/progression with a named one: drums " + ", ".join(drum_names()) + "; bass " + ", ".join(bass_names())
        + "; melody " + ", ".join(lead_names()) + "; chords (emotion) " + ", ".join(mood_names()) + "."
)


class ApplyPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: str = Field(description="plan_id returned by plan_song or by compose with preview=true")


PREVIEW_FIELD = Field(False, description="Only return the planned diff and a plan_id; nothing changes until apply_plan")


def _signature_from_model(model: type[BaseModel], skip: tuple[str, ...] = ()) -> inspect.Signature:
    params = []
    for name, field in model.model_fields.items():
        if name in skip:
            continue
        if field.is_required():
            default = inspect.Parameter.empty
        elif field.default_factory is not None:
            default = field.default_factory()
        else:
            default = field.default
        # Keep constraints and description, but let the signature own the default.
        annotation = Annotated[(field.annotation, Field(description=field.description), *field.metadata)]
        params.append(inspect.Parameter(name, inspect.Parameter.KEYWORD_ONLY, default=default, annotation=annotation))
    return inspect.Signature(params, return_annotation=dict[str, Any])


# The newest server's plans: a track a song plan creates is unknown to Live until apply_plan (see build_server)
_unapplied_track: Callable[[int], str | None] = lambda index: None


def _make_tool(
    model: type[BaseModel], run: Runner, skip: tuple[str, ...] = (), extra: dict[str, Any] | None = None,
    free: bool = False,
):
    """free: usable without a license (reading Live, undo); everything else needs the trial or a license."""

    async def tool(ctx: Context | None = None, **kwargs: Any) -> Any:
        if not free:
            try:
                license.require()
            except license.LicenseError as exc:
                raise ToolError(f"LICENSE_REQUIRED: {exc} Run `midibakery license` or use the Chat device.") from None
        try:
            result = await run(kwargs, ctx)
        except BridgeError as exc:
            hint = f" Details: {exc.details}" if exc.details else ""
            track = exc.details.get("track") if exc.code == "NOT_FOUND" and isinstance(exc.details, dict) else None
            if isinstance(track, int) and exc.message.startswith("No track index") and (planned := _unapplied_track(track)):
                hint = f" {planned}"
            raise ToolError(f"{exc.code}: {exc.message}.{hint}") from None
        except ValidationError as exc:
            raise ToolError(f"INVALID_PARAMS: {_validation_message(exc, model)}") from None
        if isinstance(result, dict | CallToolResult | InputRequiredResult):
            return result
        return {"result": result}

    signature = _signature_from_model(model, skip)
    params = [inspect.Parameter("ctx", inspect.Parameter.KEYWORD_ONLY, default=None, annotation=Context | None)]
    params += list(signature.parameters.values())
    for name, (annotation, default) in (extra or {}).items():
        params.append(inspect.Parameter(name, inspect.Parameter.KEYWORD_ONLY, default=default, annotation=annotation))
    signature = signature.replace(parameters=params)
    tool.__signature__ = signature  # type: ignore[attr-defined]
    tool.__annotations__ = {p.name: p.annotation for p in signature.parameters.values()} | {
        "return": signature.return_annotation
    }
    return tool


def _validation_message(exc: ValidationError, model: type[BaseModel]) -> str:
    """loc + msg only: echoing the full input costs context and buries the message. An unknown field
    names the fields the tool does take, so a model can fix the call instead of guessing again."""
    parts = []
    for e in exc.errors(include_url=False, include_context=False):
        where = ".".join(map(str, e["loc"])) or "arguments"
        if e["type"] == "extra_forbidden":
            parts.append(f"{where}: unknown field")
        else:
            parts.append(f"{where}: {e['msg']}")
    if any(e["type"] == "extra_forbidden" and len(e["loc"]) == 1 for e in exc.errors()):
        parts.append("fields of this tool: " + ", ".join(model.model_fields))
    return "; ".join(parts)


def with_arrangement(session: dict[str, Any], arrangement: dict[str, Any]) -> dict[str, Any]:
    """The Arrangement in bars next to the Session View: locators, and per track its arrangement clips
    (the index compose takes as arrangement_clip). A song from plan_song lives there;
    without this a model only sees the slots and writes a new clip instead of changing the section."""
    song = session["song"]
    bpb = song.get("signature_numerator", 4) * 4 / (song.get("signature_denominator", 4) or 4)
    bar = lambda beat: round(beat / bpb, 2) + 1  # noqa: E731
    clips = {t["index"]: t.get("clips", []) for t in arrangement.get("tracks", [])}
    tracks = [
        {**t, "arrangement_clips": [
            {"index": c["index"], "name": c.get("name", ""), "start_bar": bar(c["start"]), "bars": round((c["end"] - c["start"]) / bpb, 2)}
            for c in clips.get(t["index"], [])
        ]} if clips.get(t["index"]) else t
        for t in session.get("tracks", [])
    ]
    locators = [{"name": c["name"], "bar": bar(c["time"])} for c in arrangement.get("locators", [])]
    return {**session, "tracks": tracks, **({"locators": locators} if locators else {})}


def _clip_label(change: Any) -> str:
    """As the user counts: track 2 slot 1, track 2 arrangement clip 3."""
    if change.place.start is not None:
        return f"track {change.track + 1} at bar {change.info.get('bar', change.place.start)}"
    if change.place.in_arrangement:
        return f"track {change.track + 1} arrangement clip {change.place.arrangement_clip + 1}"
    return f"track {change.track + 1} slot {change.slot + 1}"


def _with_roll(plan: Plan, payload: dict[str, Any], applied: bool) -> CallToolResult:
    """Text + structured result for the model, full before/after notes in _meta for the chat page's piano roll."""
    roll = plan.roll() | {"applied": applied}
    if applied:
        roll.pop("plan_id")
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(payload, separators=(",", ":")))],
        structured_content=payload,
        _meta={"midibakery/roll": roll},
    )


def _track_identity(tracks: list[dict[str, Any]]) -> tuple[Any, ...]:
    return tuple((t.get("id"), t.get("name"), t.get("kind"), tuple((c["slot"], c["name"], c["length"]) for c in t.get("clips", [])))
                 for t in tracks)


@dataclass
class PendingCall:
    """A destructive call a client without elicitation made: kept until apply_plan, after the user said yes."""

    id: str
    op: str
    args: dict[str, Any]
    message: str
    tracks: tuple[Any, ...]

    def preview(self) -> dict[str, Any]:
        return {"plan_id": self.id, "not_applied": self.message, "next": "Ask the user exactly this; only after a yes, "
                "apply_plan(plan_id) runs it (one undo step). This client cannot show a confirmation dialog."}


def build_server(client: BridgeClient | None = None, all_song_options: bool = False) -> MCPServer:
    """all_song_options: plan_song takes every SongRequest field with its own default (tests, scripts);
    without it the model sees the few that shape a sketch and the rest keep SONG_DEFAULTS."""
    bridge = client or BridgeClient()
    plans = PlanStore()

    def unapplied_track(index: int) -> str | None:
        song = next((p for p in reversed(plans.pending()) if isinstance(p, SongPlan)
                     and any(t.new and t.index == index for t in p.roles.values())), None)
        if song is None:
            return None
        name = next(t.name for t in song.roles.values() if t.new and t.index == index)
        return (f"Track index {index} '{name}' comes from song plan {song.id}, which is not applied yet: "
                f"apply_plan({song.id}) first (or ask the user to press Apply), then this call works")

    global _unapplied_track
    _unapplied_track = unapplied_track
    server = MCPServer(
        "midibakery",
        title="MidiBakery by Klirrwerk for Ableton Live",
        instructions=INSTRUCTIONS,
        version=__version__,
    )

    async def get_session(_: dict[str, Any], ctx: Context | None) -> dict[str, Any]:
        song, tracks = await asyncio.gather(bridge.call("song.get"), bridge.call("tracks.list"))
        session = {"song": song, **tracks}
        try:
            arrangement = await bridge.call("arrangement.get")
        except BridgeError:
            return session
        return with_arrangement(session, arrangement)

    async def get_clip(args: dict[str, Any], ctx: Context | None) -> dict[str, Any]:
        clip = await bridge.call("clip.get", args)
        if clip.get("is_midi"):
            clip["notes"] = (await bridge.call("notes.get", args))["notes"]
        return clip

    async def call_op(op: str, args: dict[str, Any]) -> Any:
        return await bridge.call(op, args)

    async def defer(op: str, args: dict[str, Any], message: str) -> dict[str, Any]:
        tracks = _track_identity((await bridge.call("tracks.list"))["tracks"])
        pending = PendingCall(secrets.token_hex(4), op, args, message, tracks)
        plans.put(pending)  # type: ignore[arg-type]  # apply_plan tells pending calls apart
        return pending.preview()

    async def describe(op: str, params: dict[str, Any]) -> str:
        """Human wording for deleting a clip, with track and clip names."""
        try:
            tracks = (await bridge.call("tracks.list"))["tracks"]
        except BridgeError:
            tracks = []
        track = tracks[params["track"]] if 0 <= params.get("track", -1) < len(tracks) else {}
        track_name = f"track {params.get('track', 0) + 1} '{track.get('name', '?')}'"
        ref = params.get("arrangement_clip")
        if ref is not None:
            # by index or by name ('Intro Kick'): name it as the user sees it
            try:
                clips = (await bridge.call("arrangement.get", {"track": params["track"]}))["tracks"][0]["clips"]
            except (BridgeError, KeyError, IndexError):
                clips = []
            wanted = str(ref).strip().casefold()
            clip = next((c for c in clips if c["index"] == ref or str(c.get("name", "")).strip().casefold() == wanted), None)
            if clip is None:
                clip = next((c for c in clips if isinstance(ref, str) and wanted in str(c.get("name", "")).casefold()), None)
            if clip is None:
                return f"Delete arrangement clip {ref!r} of {track_name}?"
            return f"Delete arrangement clip '{clip.get('name') or 'unnamed'}' (index {clip['index']}) of {track_name}?"
        clip = next((c for c in track.get("clips", []) if c["slot"] == params.get("slot")), {})
        return f"Delete clip '{clip.get('name') or 'unnamed'}' in slot {params.get('slot', 0) + 1} of {track_name}?"

    read_only = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
    server.add_tool(
        _make_tool(Empty, get_session, free=True),
        name="get_session",
        title="Get Live session",
        description="Song settings (tempo, signature, scale, transport) plus all tracks with devices and clips.",
        annotations=read_only,
    )
    server.add_tool(
        _make_tool(ClipRef, get_clip, free=True),
        name="get_clip",
        title="Get clip with notes",
        description="Clip properties and, for MIDI clips, all notes with note_id, probability and velocity deviation.",
        annotations=read_only,
    )

    async def get_reference(args: dict[str, Any], ctx: Context | None) -> dict[str, Any]:
        return read_references(ReferenceQuery.model_validate(args).name)

    server.add_tool(
        _make_tool(ReferenceQuery, get_reference, free=True),
        name="get_reference",
        title="Get reference song analysis",
        description="Sections (start bar, length, kick, elements), key and tempo of reference songs analyzed by the "
        "MidiBakery Reference Analyzer device or imported from Live Sets by the Set Importer. " + inspect.cleandoc(ReferenceQuery.__doc__ or ""),
        annotations=read_only,
    )

    async def edit_arrangement(args: dict[str, Any], ctx: Context | None) -> dict[str, Any]:
        # One tool for the model; two ops for Live: locators need ticks of their own (see arrangement.locators).
        actions = ArrangementTool.model_validate(args).model_dump(exclude_none=True)["actions"]
        clips = [a for a in actions if a["action"] not in ("set_locator", "delete_locator")]
        locators = [a for a in actions if a["action"] in ("set_locator", "delete_locator")]
        result: dict[str, Any] = {}
        song = await bridge.call("song.get")
        # All or nothing: locators first (restored from a snapshot, Live makes each its own undo step),
        # then the clips (one undo step, on top of the stack when they fail).
        before = await read_locators(bridge.call) if locators else []
        if locators:
            try:
                result["locators"] = (await bridge.call("arrangement.locators", {"actions": locators}))["locators"]
            except BridgeError as exc:
                await restore_locators(bridge.call, exc, before)
                raise
        if clips:
            try:
                result.update(await bridge.call("arrangement.edit", {"actions": clips}))
            except BridgeError as exc:
                await undo_edit(bridge.call, exc)
                if locators:
                    await restore_locators(bridge.call, exc, before)
                raise
        # Copying a session clip moves Live's play position to the copy's end; put it back where the user was.
        if not song["is_playing"] and (await bridge.call("song.get"))["current_song_time"] != song["current_song_time"]:
            await bridge.call("song.position", {"beat": song["current_song_time"]})
        return result

    server.add_tool(
        _make_tool(ArrangementTool, edit_arrangement),
        name="edit_arrangement",
        title="Add, copy, move, swap or delete arrangement clips and locators",
        description="Add MIDI clips with notes, copy session clips, move, swap or delete arrangement clips, set or delete locators. "
        + inspect.cleandoc(ArrangementTool.__doc__ or ""),
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
    )

    for tool_name, op_name, title in TOOL_OPS:
        spec = get_op(op_name)

        async def run(args: dict[str, Any], ctx: Context | None, _op: str = op_name) -> Any:
            if _op in CONFIRM_OPS:
                asked = await confirm(ctx, await describe(_op, args), later=lambda m: defer(_op, args, m))
                if asked is not None:
                    return asked
            return await call_op(_op, args)

        server.add_tool(
            _make_tool(spec.params, run, free=spec.read_only or op_name == "history.step"),
            name=tool_name,
            title=title,
            description=" ".join(filter(None, [spec.summary + ".", inspect.cleandoc(spec.params.__doc__ or "")])),
            annotations=ToolAnnotations(
                readOnlyHint=spec.read_only,
                destructiveHint=spec.destructive,
                idempotentHint=False,
                openWorldHint=False,
            ),
        )

    async def ask_before_replacing(plan: Plan, ctx: Context | None, state: dict[str, Any] | None = None, defer_plan: bool = False):
        removed = plan.removes_existing
        if not removed:
            return None
        clips = ", ".join(_clip_label(c) for c in plan.changes if c.removes_existing)

        async def later(message: str) -> CallToolResult:
            plans.put(plan)
            return _with_roll(plan, {**plan.preview(), "not_applied": message, "next": "Ask the user exactly this; only "
                                     "after a yes, apply_plan(plan_id) writes it. This client cannot show a confirmation dialog."}, False)

        # apply_plan is itself the go-ahead for a plan the user saw
        return await confirm(ctx, f"Replace {removed} existing note(s) in {clips}?", state, later if defer_plan else None)

    async def compose(args: dict[str, Any], ctx: Context | None) -> Any:
        args = dict(args)
        preview = args.pop("preview", False)
        if args.get("seed") is None:
            # Keep the idea stable across a confirmation round trip.
            args["seed"] = request_state(ctx).get("seed", new_seed())
        spec = ComposeRequest.model_validate(args).spec()
        plan = await build_plan(bridge.call, [spec])
        if preview:
            plans.put(plan)
            return _with_roll(plan, {**plan.preview(), "next": "apply_plan(plan_id) writes this as one undo step"}, False)
        asked = await ask_before_replacing(plan, ctx, {"seed": args["seed"]}, defer_plan=True)
        if asked is not None:
            return asked
        applied = await apply_plan(bridge.call, plan, verify=False)
        result = plan.preview()
        result.pop("plan_id")
        extra = {k: applied[k] for k in ("instruments", "warnings") if k in applied}
        return _with_roll(plan, {**result, "applied": applied["applied"], **extra}, True)

    server.add_tool(
        _make_tool(ComposeRequest, compose, extra={"preview": (Annotated[bool, PREVIEW_FIELD], False)}),
        name="compose",
        title="Compose a part",
        description=COMPOSE_DESCRIPTION,
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=False),
    )

    async def plan_song(args: dict[str, Any], ctx: Context | None) -> Any:
        song = await build_song(bridge.call, SongRequest.model_validate(args if all_song_options else {**SONG_DEFAULTS, **args}))
        plans.put(song)  # type: ignore[arg-type]  # apply_plan tells songs and clip plans apart
        return song.preview()

    async def run_plan(args: dict[str, Any], ctx: Context | None) -> Any:
        plan = plans.get(args["plan_id"])
        if plan is None and plans.was_applied(args["plan_id"]):
            return {"ok": True, "already_applied": True,
                    "message": f"Plan {args['plan_id']} is already in Live (applied from its preview); nothing more to do."}
        if plan is None:
            plans.pop(args["plan_id"])  # raises NOT_FOUND
        assert plan is not None
        if isinstance(plan, SongPlan):
            plans.pop(plan.id)
            result = await apply_song(bridge.call, plan)
            plans.applied(plan.id)
            return result
        if isinstance(plan, PendingCall):
            plans.pop(plan.id)
            if _track_identity((await bridge.call("tracks.list"))["tracks"]) != plan.tracks:
                raise BridgeError("CONFLICT", f"Tracks or clips changed since {plan.id} was prepared ({plan.message}); call the tool again")
            result = await call_op(plan.op, plan.args)
            plans.applied(plan.id)
            return result
        asked = await ask_before_replacing(plan, ctx)
        if asked is not None:
            return asked
        plans.pop(plan.id)
        try:
            result = await apply_plan(bridge.call, plan)
        except BridgeError as exc:
            if exc.code == "CONFLICT":
                plans.put(plan)
            raise
        plans.applied(plan.id)
        return result

    server.add_tool(
        _make_tool(SongRequest, plan_song, skip=() if all_song_options else SONG_HIDDEN),
        name="plan_song",
        title="Plan a whole song in the Arrangement View",
        description="Full song sketch from a genre template or a reference: intro, builds, drops, breaks, outro "
        "with locators, on the drum/bass/chords/lead tracks (found by Drum Rack or name; missing ones are created), "
        "after the last arrangement clip, at the genre's or the reference's tempo. "
        "Preview and plan_id for apply_plan; nothing changes before that.",
        annotations=read_only,
    )
    server.add_tool(
        _make_tool(ApplyPlan, run_plan),
        name="apply_plan",
        title="Apply planned changes",
        description="Write a plan from plan_song (or compose with preview=true) to Live as one undo step. "
        "Fails with CONFLICT if a target clip changed since planning.",
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=False),
    )
    return server


class ReferenceQuery(BaseModel):
    """Without name: every analyzed reference, newest first. With name: the best match, with lanes
    (per bar: kick 0-1; low, bass, mid, high, energy in dB below the song's peak). A section the device
    merged from neighbours of the same kind lists its phrases (where the sound changes within it)."""

    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(None, description="Part of the song, file or track name")


def read_references(name: str | None = None) -> dict[str, Any]:
    """The Reference device's analyses (<MidiBakery folder>/references/*.json)."""
    if name:
        found = find_reference(name)
        if found is None:
            raise ToolError(f"No analyzed reference matches '{name}'")
        return found
    found = load_references()
    brief = ("name", "track", "tempo", "warped", "key", "first_bar", "bars")

    def section(s: dict[str, Any]) -> dict[str, Any]:
        out = {k: s.get(k) for k in ("name", "start_bar", "bars", "kick", "elements")}
        if s.get("phrases"):  # a merged section: where its phrases start
            out["phrases"] = [p.get("start_bar") for p in s["phrases"]]
        return out

    return {"references": [{**{k: r.get(k) for k in brief}, "sections": [section(s) for s in r.get("sections", [])]}
                           for r in found]}

