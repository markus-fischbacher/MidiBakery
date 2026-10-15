"""MCP server exposing MidiBakery to Claude and other MCP clients.

Tools are generated from the op catalog so their schemas never drift from
what the Live bridge accepts. A few read tools combine ops to save round
trips for the model.
"""

from __future__ import annotations

import inspect
import json
from collections.abc import Awaitable, Callable
from importlib.resources import files
from typing import Annotated, Any

from mcp.server import MCPServer
from mcp.server.apps import Apps
from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from mcp_types import CallToolResult, InputRequiredResult, TextContent
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from midibakery.bridge import BridgeClient, BridgeError
from midibakery.catalog import get_op
from midibakery.catalog.ops import ClipRef, Empty
from midibakery.compose import (
    BassSpec,
    ChordsSpec,
    DrumsSpec,
    MelodySpec,
    PlanStore,
    Step,
    TransformSpec,
    apply_plan,
    build_plan,
)
from midibakery.compose.plan import Plan, new_seed
from midibakery.mcp.confirm import confirm, request_state

INSTRUCTIONS = """\
MidiBakery controls the Ableton Live 12 set that is open right now.
- Call get_session first: it returns tempo, time signature, the song's scale
  (root_note 0=C..11=B, scale_name, scale_intervals) and every track with its
  devices and clips. Tracks, clip slots, devices and scenes are addressed by
  zero-based index; indices shift when tracks or scenes are created or deleted.
  Users count from 1 as Live shows it: "track 1" or "the first clip" is index 0.
- Times and lengths are in beats (quarter notes). Pitch 60 is C3 in Live.
- Prefer notes from the song scale unless the user asks otherwise.
- edit_notes is a diff: add new notes, modify or remove existing ones by the
  note_id returned from get_clip. Never rewrite a whole clip to change a few notes.
- Use run_batch for multi-step edits; it becomes a single undo step in Live.
- Every write is undoable with the undo tool.
Composition:
- compose_drums / compose_bass / compose_chords / compose_melody write a new
  clip into an empty slot, by default the track's first free one
  (if_exists='replace' or 'merge' for existing clips).
  They follow the song scale and time signature and are reproducible: pass the
  returned seed again to get the same notes, or a new seed for a new idea.
- Make parts fit together: give bass and melody chords_from (the chord clip)
  and the bass follow_kick (the drum clip), or use plan_changes, where later
  steps see earlier ones and share their chords.
- transform_notes edits an existing clip by note_id (humanize, quantize,
  invert, arpeggiate, variation, transpose). transpose takes semitones
  (chromatic, 12 = octave) or steps (scale steps in key, 2 = a third).
- preview=true (or plan_changes) returns a diff without touching Live;
  apply_plan(plan_id) then writes it as one undo step. Clients with MCP Apps
  show the diff as a piano roll with an Apply button.
- Deleting tracks or clips and replacing a clip's notes ask the user first
  when the client supports it; a declined change returns CANCELLED.
"""

PIANO_ROLL_URI = "ui://midibakery/piano-roll.html"
UI_META = {"ui": {"resourceUri": PIANO_ROLL_URI}}
# Ops that delete something the user made; edit_notes removals are explicit by note_id and not asked.
CONFIRM_OPS = {"track.delete", "clip.delete"}

Runner = Callable[[dict[str, Any], Context | None], Awaitable[Any]]

# (tool name, op, title); annotations come from the op spec.
TOOL_OPS: list[tuple[str, str, str]] = [
    ("set_song", "song.set", "Set tempo, signature, scale or loop"),
    ("transport", "transport.control", "Play / stop / record"),
    ("create_track", "track.create", "Create track"),
    ("update_track", "track.set", "Update track"),
    ("delete_track", "track.delete", "Delete track"),
    ("create_clip", "clip.create", "Create MIDI clip"),
    ("update_clip", "clip.set", "Update clip"),
    ("delete_clip", "clip.delete", "Delete clip"),
    ("launch_clip", "clip.launch", "Launch or stop clip"),
    ("edit_notes", "notes.apply", "Edit notes (diff)"),
    ("insert_device", "device.insert", "Insert native device"),
    ("get_device_parameters", "device.params", "Get device parameters"),
    ("get_drum_pads", "drum_rack.pads", "Get Drum Rack pads"),
    ("set_device_parameter", "device.set_param", "Set device parameter"),
    ("create_scene", "scene.create", "Create scene"),
    ("fire_scene", "scene.fire", "Launch scene"),
    ("undo", "history.step", "Undo / redo"),
    ("run_batch", "batch", "Run several ops as one undo step"),
]


# (tool name, request model, title, description)
COMPOSE_TOOLS: list[tuple[str, type[BaseModel], str, str]] = [
    (
        "compose_drums",
        DrumsSpec,
        "Compose drum pattern",
        "Drum pattern in the song's time signature. Pads of the track's Drum Rack are found by name "
        "(kick, snare, hats ...); General MIDI notes are the fallback. Uses probability and velocity deviation on hats and ghost notes.",
    ),
    (
        "compose_bass",
        BassSpec,
        "Compose bass line",
        "Bass line in the song scale that follows chords (progression or chords_from) and can lock to or avoid "
        "the kick of a drum clip (follow_kick).",
    ),
    (
        "compose_chords",
        ChordsSpec,
        "Compose chord part",
        "Voice-led chord part. Without a progression a functional one (tonic, subdominant, dominant) is generated.",
    ),
    (
        "compose_melody",
        MelodySpec,
        "Compose melody",
        "Motif-based melody (A A' A B phrases) in the song scale, chord tones on strong beats.",
    ),
    (
        "transform_notes",
        TransformSpec,
        "Transform notes",
        "Change a MIDI clip as a diff by note_id: humanize, quantize, invert (diatonic), "
        "arpeggiate, variation, or transpose (semitones chromatic, steps in key).",
    ),
]


class PlanChanges(BaseModel):
    model_config = ConfigDict(extra="forbid")

    steps: list[Step] = Field(
        min_length=1,
        max_length=16,
        description="Composition steps by kind: drums, bass, chords, melody, transform (same fields as the compose_* tools)",
    )


class ApplyPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: str = Field(description="plan_id returned by plan_changes or a compose tool with preview=true")


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


def _make_tool(
    model: type[BaseModel], run: Runner, skip: tuple[str, ...] = (), extra: dict[str, Any] | None = None
):
    async def tool(ctx: Context | None = None, **kwargs: Any) -> Any:
        try:
            result = await run(kwargs, ctx)
        except BridgeError as exc:
            hint = f" Details: {exc.details}" if exc.details else ""
            raise ToolError(f"{exc.code}: {exc.message}.{hint}") from None
        except ValidationError as exc:
            # loc + msg only: echoing the full input costs context and buries the message.
            errors = "; ".join(
                f"{'.'.join(map(str, e['loc'])) or 'arguments'}: {e['msg']}" for e in exc.errors(include_url=False, include_context=False)
            )
            raise ToolError(f"INVALID_PARAMS: {errors}") from None
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


def _with_roll(plan: Plan, payload: dict[str, Any], applied: bool) -> CallToolResult:
    """Text + structured result for the model, full before/after notes in _meta for the piano-roll view."""
    roll = plan.roll() | {"applied": applied}
    if applied:
        roll.pop("plan_id")
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(payload, separators=(",", ":")))],
        structured_content=payload,
        _meta={"midibakery/roll": roll},
    )


def _piano_roll_html() -> str:
    return files("midibakery.mcp").joinpath("piano_roll.html").read_text(encoding="utf-8")


def build_server(client: BridgeClient | None = None) -> MCPServer:
    bridge = client or BridgeClient()
    plans = PlanStore()
    apps = Apps()
    apps.add_html_resource(
        PIANO_ROLL_URI,
        _piano_roll_html(),
        name="piano-roll",
        title="MidiBakery piano roll",
        description="Before/after piano roll of planned or applied note changes",
        prefers_border=True,
    )
    server = MCPServer(
        "midibakery",
        title="MidiBakery by Klirrwerk for Ableton Live",
        instructions=INSTRUCTIONS,
        version="0.1.0",
        extensions=[apps],
    )

    async def get_session(_: dict[str, Any], ctx: Context | None) -> dict[str, Any]:
        song = await bridge.call("song.get")
        tracks = await bridge.call("tracks.list")
        return {"song": song, **tracks}

    async def get_clip(args: dict[str, Any], ctx: Context | None) -> dict[str, Any]:
        clip = await bridge.call("clip.get", args)
        if clip.get("is_midi"):
            clip["notes"] = (await bridge.call("notes.get", args))["notes"]
        return clip

    async def describe(op: str, params: dict[str, Any]) -> str:
        """Human wording for a destructive op, with track and clip names."""
        try:
            tracks = (await bridge.call("tracks.list"))["tracks"]
        except BridgeError:
            tracks = []
        track = tracks[params["track"]] if 0 <= params.get("track", -1) < len(tracks) else {}
        track_name = f"track {params.get('track', 0) + 1} '{track.get('name', '?')}'"
        if op == "track.delete":
            clips = len(track.get("clips", []))
            return f"Delete {track_name} with {clips} clip(s)?"
        clip = next((c for c in track.get("clips", []) if c["slot"] == params.get("slot")), {})
        return f"Delete clip '{clip.get('name') or 'unnamed'}' in slot {params.get('slot', 0) + 1} of {track_name}?"

    read_only = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
    server.add_tool(
        _make_tool(Empty, get_session),
        name="get_session",
        title="Get Live session",
        description="Song settings (tempo, signature, scale, transport) plus all tracks with devices and clips.",
        annotations=read_only,
    )
    server.add_tool(
        _make_tool(ClipRef, get_clip),
        name="get_clip",
        title="Get clip with notes",
        description="Clip properties and, for MIDI clips, all notes with note_id, probability and velocity deviation.",
        annotations=read_only,
    )

    for tool_name, op_name, title in TOOL_OPS:
        spec = get_op(op_name)

        async def run(args: dict[str, Any], ctx: Context | None, _op: str = op_name) -> Any:
            if _op in CONFIRM_OPS:
                asked = await confirm(ctx, await describe(_op, args))
                if asked is not None:
                    return asked
            elif _op == "batch":
                risky = [item for item in args.get("ops", []) if _item_op(item) in CONFIRM_OPS]
                if risky:
                    questions = [await describe(_item_op(i), _item_params(i)) for i in risky]
                    asked = await confirm(ctx, "Run this batch? It will " + " ".join(q[0].lower() + q[1:] for q in questions))
                    if asked is not None:
                        return asked
            return await bridge.call(_op, args)

        server.add_tool(
            _make_tool(spec.params, run),
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

    async def ask_before_replacing(plan: Plan, ctx: Context | None, state: dict[str, Any] | None = None):
        removed = plan.removes_existing
        if not removed:
            return None
        clips = ", ".join(f"track {c.track + 1} slot {c.slot + 1}" for c in plan.changes if c.removes_existing)
        return await confirm(ctx, f"Replace {removed} existing note(s) in {clips}?", state)

    for tool_name, model, title, description in COMPOSE_TOOLS:

        async def compose(args: dict[str, Any], ctx: Context | None, _model: type[BaseModel] = model) -> Any:
            args = dict(args)
            preview = args.pop("preview", False)
            if args.get("seed") is None:
                # Keep the idea stable across a confirmation round trip.
                args["seed"] = request_state(ctx).get("seed", new_seed())
            spec = _model.model_validate(args)
            plan = await build_plan(bridge.call, [spec])
            if preview:
                plans.put(plan)
                return _with_roll(plan, {**plan.preview(), "next": "apply_plan(plan_id) writes this as one undo step"}, False)
            asked = await ask_before_replacing(plan, ctx, {"seed": args["seed"]})
            if asked is not None:
                return asked
            applied = await apply_plan(bridge.call, plan, verify=False)
            result = plan.preview()
            result.pop("plan_id")
            return _with_roll(plan, {**result, "applied": applied["applied"]}, True)

        server.add_tool(
            _make_tool(model, compose, skip=("kind",), extra={"preview": (Annotated[bool, PREVIEW_FIELD], False)}),
            name=tool_name,
            title=title,
            description=description,
            annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=False),
            meta=UI_META,
        )

    async def plan_changes(args: dict[str, Any], ctx: Context | None) -> Any:
        request = PlanChanges.model_validate(args)
        plan = await build_plan(bridge.call, list(request.steps))
        plans.put(plan)
        return _with_roll(plan, {**plan.preview(), "next": "apply_plan(plan_id) writes all steps as one undo step"}, False)

    async def run_plan(args: dict[str, Any], ctx: Context | None) -> Any:
        plan = plans.get(args["plan_id"])
        if plan is None:
            plans.pop(args["plan_id"])  # raises NOT_FOUND
        assert plan is not None
        asked = await ask_before_replacing(plan, ctx)
        if asked is not None:
            return asked
        plans.pop(plan.id)
        try:
            return await apply_plan(bridge.call, plan)
        except BridgeError as exc:
            if exc.code == "CONFLICT":
                plans.put(plan)
            raise

    server.add_tool(
        _make_tool(PlanChanges, plan_changes),
        name="plan_changes",
        title="Plan composition changes",
        description="Plan several composition steps (drums, bass, chords, melody, transform) without changing Live. "
        "Later steps see earlier ones: bass can follow_kick a planned drum clip, and harmonic steps without chords "
        "share the first step's chords. Returns a diff preview and a plan_id.",
        annotations=read_only,
        meta=UI_META,
    )
    server.add_tool(
        _make_tool(ApplyPlan, run_plan),
        name="apply_plan",
        title="Apply planned changes",
        description="Write a plan from plan_changes (or preview=true) to Live as one undo step. "
        "Fails with CONFLICT if a target clip changed since planning.",
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=False),
    )
    return server


def _item_op(item: Any) -> str:
    return item.op if hasattr(item, "op") else item.get("op", "")


def _item_params(item: Any) -> dict[str, Any]:
    return item.params if hasattr(item, "params") else item.get("params", {})
