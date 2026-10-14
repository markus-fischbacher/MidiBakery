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
from pydantic import BaseModel, Field

from midishower.bridge import BridgeClient, BridgeError
from midishower.catalog import get_op
from midishower.catalog.ops import ClipRef, Empty

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
    ("set_device_parameter", "device.set_param", "Set device parameter"),
    ("create_scene", "scene.create", "Create scene"),
    ("fire_scene", "scene.fire", "Launch scene"),
    ("undo", "history.step", "Undo / redo"),
    ("run_batch", "batch", "Run several ops as one undo step"),
]


def _signature_from_model(model: type[BaseModel]) -> inspect.Signature:
    params = []
    for name, field in model.model_fields.items():
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


def _make_tool(model: type[BaseModel], run: Callable[[dict[str, Any]], Awaitable[Any]]):
    async def tool(**kwargs: Any) -> dict[str, Any]:
        try:
            result = await run(kwargs)
        except BridgeError as exc:
            hint = f" Details: {exc.details}" if exc.details else ""
            raise ToolError(f"{exc.code}: {exc.message}.{hint}") from None
        return result if isinstance(result, dict) else {"result": result}

    signature = _signature_from_model(model)
    tool.__signature__ = signature  # type: ignore[attr-defined]
    tool.__annotations__ = {p.name: p.annotation for p in signature.parameters.values()} | {
        "return": signature.return_annotation
    }
    return tool


def build_server(client: BridgeClient | None = None) -> MCPServer:
    bridge = client or BridgeClient()
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
    return server
