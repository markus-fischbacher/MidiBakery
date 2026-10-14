"""MCP server exposing MidiShower to Claude and other MCP clients.

Tools are generated from the op catalog so their schemas never drift from
what the Live bridge accepts. A few read tools combine ops to save round
trips for the model.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from midishower.bridge import BridgeClient, BridgeError
from midishower.catalog import get_op
from midishower.catalog.ops import ClipRef, Empty
from midishower.compose import (
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

INSTRUCTIONS = """\
MidiShower controls the Ableton Live 12 set that is open right now.
- Call get_session first: it returns tempo, time signature, the song's scale
  (root_note 0=C..11=B, scale_name, scale_intervals) and every track with its
  devices and clips. Tracks, clip slots, devices and scenes are addressed by
  zero-based index; indices shift when tracks or scenes are created or deleted.
- Times and lengths are in beats (quarter notes). Pitch 60 is C3 in Live.
- Prefer notes from the song scale unless the user asks otherwise.
- edit_notes is a diff: add new notes, modify or remove existing ones by the
  note_id returned from get_clip. Never rewrite a whole clip to change a few notes.
- Use run_batch for multi-step edits; it becomes a single undo step in Live.
- Every write is undoable with the undo tool.
Composition:
- compose_drums / compose_bass / compose_chords / compose_melody write a new
  clip into an empty slot (if_exists='replace' or 'merge' for existing clips).
  They follow the song scale and time signature and are reproducible: pass the
  returned seed again to get the same notes, or a new seed for a new idea.
- Make parts fit together: give bass and melody chords_from (the chord clip)
  and the bass follow_kick (the drum clip), or use plan_changes, where later
  steps see earlier ones and share their chords.
- transform_notes edits an existing clip by note_id (humanize, quantize,
  invert, arpeggiate, variation, transpose).
- preview=true (or plan_changes) returns a diff without touching Live;
  apply_plan(plan_id) then writes it as one undo step.
"""

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
        "Change an existing MIDI clip as a diff by note_id: humanize, quantize, invert (diatonic), "
        "arpeggiate chords, seeded variation, or transpose in key.",
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
    model: type[BaseModel], run: Callable[[dict[str, Any]], Awaitable[Any]], skip: tuple[str, ...] = (), extra: dict[str, Any] | None = None
):
    async def tool(**kwargs: Any) -> dict[str, Any]:
        try:
            result = await run(kwargs)
        except BridgeError as exc:
            hint = f" Details: {exc.details}" if exc.details else ""
            raise ToolError(f"{exc.code}: {exc.message}.{hint}") from None
        except ValidationError as exc:
            errors = exc.errors(include_url=False, include_context=False)
            raise ToolError(f"INVALID_PARAMS: {errors}") from None
        return result if isinstance(result, dict) else {"result": result}

    signature = _signature_from_model(model, skip)
    if extra:
        params = list(signature.parameters.values())
        for name, (annotation, default) in extra.items():
            params.append(inspect.Parameter(name, inspect.Parameter.KEYWORD_ONLY, default=default, annotation=annotation))
        signature = signature.replace(parameters=params)
    tool.__signature__ = signature  # type: ignore[attr-defined]
    tool.__annotations__ = {p.name: p.annotation for p in signature.parameters.values()} | {
        "return": signature.return_annotation
    }
    return tool


def build_server(client: BridgeClient | None = None) -> MCPServer:
    bridge = client or BridgeClient()
    plans = PlanStore()
    server = MCPServer(
        "midishower",
        title="MidiShower for Ableton Live",
        instructions=INSTRUCTIONS,
        version="0.1.0",
    )

    async def get_session(_: dict[str, Any]) -> dict[str, Any]:
        song = await bridge.call("song.get")
        tracks = await bridge.call("tracks.list")
        return {"song": song, **tracks}

    async def get_clip(args: dict[str, Any]) -> dict[str, Any]:
        clip = await bridge.call("clip.get", args)
        if clip.get("is_midi"):
            clip["notes"] = (await bridge.call("notes.get", args))["notes"]
        return clip

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

        async def run(args: dict[str, Any], _op: str = op_name) -> Any:
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

    for tool_name, model, title, description in COMPOSE_TOOLS:

        async def compose(args: dict[str, Any], _model: type[BaseModel] = model) -> dict[str, Any]:
            args = dict(args)
            preview = args.pop("preview", False)
            spec = _model.model_validate(args)
            plan = await build_plan(bridge.call, [spec])
            if preview:
                plans.put(plan)
                return {**plan.preview(), "next": "apply_plan(plan_id) writes this as one undo step"}
            applied = await apply_plan(bridge.call, plan, verify=False)
            result = plan.preview()
            result.pop("plan_id")
            return {**result, "applied": applied["applied"]}

        server.add_tool(
            _make_tool(model, compose, skip=("kind",), extra={"preview": (Annotated[bool, PREVIEW_FIELD], False)}),
            name=tool_name,
            title=title,
            description=description,
            annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=False),
        )

    async def plan_changes(args: dict[str, Any]) -> dict[str, Any]:
        request = PlanChanges.model_validate(args)
        plan = await build_plan(bridge.call, list(request.steps))
        plans.put(plan)
        return {**plan.preview(), "next": "apply_plan(plan_id) writes all steps as one undo step"}

    async def run_plan(args: dict[str, Any]) -> dict[str, Any]:
        plan = plans.pop(args["plan_id"])
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
