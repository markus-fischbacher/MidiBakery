"""Agent loop, tool host and providers, without calling a real model."""

import json

import httpx2 as httpx
from anthropic.types import Message, TextBlock, ToolUseBlock, Usage

from midibakery.agent import REDUCED_TOOLS, SMALL_SYSTEM_PROMPT, SMALL_TOOLS, SYSTEM_PROMPT, Agent, ToolHost
from midibakery.agent.providers.anthropic import FALLBACK_BETA, AnthropicProvider
from midibakery.agent.providers.base import Provider, ToolCall, Turn
from midibakery.agent.providers import make_provider
from midibakery.agent.providers.base import ToolResult
from midibakery.agent.providers.ollama import OllamaProvider, inline_refs
from midibakery.agent.providers.openai_compat import OpenAICompatProvider
from midibakery.agent.loop import language_reminder
from midibakery.agent.tools import ToolSpec, compact_schema, compact_session, lift_nested
from midibakery.mcp import build_server


class ScriptedProvider(Provider):
    """Plays back prepared turns and records what the loop sends."""

    name = "scripted"
    model = "script"

    def __init__(self, turns):
        self.turns = list(turns)
        self.users = []
        self.results = []
        self.system = None
        self.tools = []

    def configure(self, system, tools):
        self.system, self.tools = system, tools

    def add_user(self, text):
        self.users.append(text)

    def reset(self):
        self.users = []

    async def stream_turn(self, emit):
        turn = self.turns.pop(0)
        if turn.text:
            await emit({"type": "text", "text": turn.text})
        return turn

    def add_tool_results(self, results):
        self.results.append(results)


def tool_turn(*calls):
    return Turn("tool_use", [ToolCall(f"t{i}", name, args) for i, (name, args) in enumerate(calls)])


async def run(server, provider, text, confirm=None, allowed=None):
    events = []

    async def emit(event):
        events.append(event)

    async def default_confirm(message):
        events.append({"type": "confirm", "message": message})
        return True

    async with ToolHost(server, confirm or default_confirm, allowed) as host:
        await Agent(provider, host).send(text, emit)
    return events


# --------------------------------------------------------------------------
# Loop + tool host against the fake LOM
# --------------------------------------------------------------------------


async def test_loop_runs_tools_and_streams_events(client, live):
    provider = ScriptedProvider([
        tool_turn(("get_session", {})),
        tool_turn(("compose", {"kind": "drums", "track": 0, "slot": 0, "seed": 3, "bars": 2})),
        Turn("end_turn", text="Done: 2 bars of house drums on track 1."),
    ])
    events = await run(build_server(client), provider, "Make drums")
    kinds = [e["type"] for e in events]
    assert kinds == ["tool_call", "tool_result", "tool_call", "tool_result", "plan", "text", "done"]
    assert provider.users == ["Make drums"]
    assert "MidiBakery" in provider.system and "get_session" in {t.name for t in provider.tools}
    session_result = provider.results[0][0]
    assert not session_result.is_error and json.loads(session_result.content)["song"]["tempo"] == 120
    assert events[4]["roll"]["applied"] is True
    assert live.on_main(lambda: len(live.song.tracks[0].clip_slots[0].clip.notes)) > 0


async def test_tool_errors_go_back_to_the_model(client, live):
    provider = ScriptedProvider([
        tool_turn(("no_such_tool", {}), ("delete_track", "not an object"), ("delete_track", {"track": 99})),
        Turn("end_turn", text="Sorry."),
    ])
    await run(build_server(client), provider, "break things")
    errors = provider.results[0]
    assert [r.is_error for r in errors] == [True, True, True]
    assert "Unknown tool" in errors[0].content and "JSON object" in errors[1].content and "NOT_FOUND" in errors[2].content


async def test_unknown_arguments_are_named_not_dropped(client, live):
    await client.call("clip.create", {"track": 1, "slot": 0, "length": 4})
    await client.call("notes.apply", {"track": 1, "slot": 0, "add": [{"pitch": 60, "start_time": 0.0, "duration": 1}]})
    provider = ScriptedProvider([
        tool_turn(("transform_notes", {"track": 1, "slot": 0, "operation": "transpose", "sembitimes": 2})),
        tool_turn(("transform_notes", {"track": 1, "slot": 0, "operation": "transpose"})),
        Turn("end_turn", text="Sorry."),
    ])
    await run(build_server(client), provider, "2 semitones up")
    typo, missing = provider.results[0][0], provider.results[1][0]
    assert typo.is_error and "'sembitimes' (did you mean 'semitones'?)" in typo.content
    assert missing.is_error and "transpose needs either semitones" in missing.content and "'input'" not in missing.content
    assert live.on_main(lambda: [n["pitch"] for n in live.song.tracks[1].clip_slots[0].clip.notes.values()]) == [60]


async def test_confirmation_is_asked_through_the_frontend(client, live):
    asked = []

    async def decline(message):
        asked.append(message)
        return False

    provider = ScriptedProvider([tool_turn(("delete_track", {"track": 0})), Turn("end_turn", text="Kept it.")])
    await run(build_server(client), provider, "delete track 1", confirm=decline)
    assert asked == ["Delete track 1 '1-MIDI' with 0 clip(s)?"]
    assert provider.results[0][0].is_error and "CANCELLED" in provider.results[0][0].content
    assert live.on_main(lambda: len(live.song.tracks)) == 2


async def test_reduced_tool_set_and_step_limit(client, live):
    provider = ScriptedProvider([tool_turn(("get_session", {}))] * 30)
    events = []

    async def emit(event):
        events.append(event)

    async def yes(message):
        return True

    async with ToolHost(build_server(client), yes, REDUCED_TOOLS) as host:
        assert host.names() == set(REDUCED_TOOLS)
        await Agent(provider, host, max_steps=3).send("loop", emit)
    assert events[-1]["type"] == "error" and "3 tool rounds" in events[-1]["message"]


# --------------------------------------------------------------------------
# Anthropic provider with a stub SDK client
# --------------------------------------------------------------------------


class _Delta:
    def __init__(self, kind, text):
        self.type = kind
        if kind == "text_delta":
            self.text = text
        else:
            self.thinking = text


class _Event:
    def __init__(self, kind, text):
        self.type = "content_block_delta"
        self.delta = _Delta(kind, text)


class _Stream:
    def __init__(self, events, message):
        self._events, self._message = events, message

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def __aiter__(self):
        async def gen():
            for e in self._events:
                yield e
        return gen()

    async def get_final_message(self):
        return self._message


class StubAnthropic:
    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []
        outer = self

        class _Messages:
            def stream(self, **params):
                outer.requests.append(params)
                reply = outer.replies.pop(0)
                if isinstance(reply, Exception):
                    raise reply
                return _Stream(*reply)

        class _Beta:
            messages = _Messages()

        self.beta = _Beta()
        self.messages = _Messages()


def _message(content, stop):
    return Message.model_construct(
        id="msg_1", type="message", role="assistant", model="claude-sonnet-5-5", content=content,
        stop_reason=stop, stop_sequence=None,
        usage=Usage.model_construct(input_tokens=10, output_tokens=5, cache_read_input_tokens=7, cache_creation_input_tokens=0),
    )


TOOLS = [ToolSpec("b_tool", "B", {"type": "object", "properties": {}}), ToolSpec("a_tool", "A", {"type": "object", "properties": {}})]


async def test_anthropic_request_shape_streaming_and_history():
    tool_use = ToolUseBlock.model_construct(type="tool_use", id="tu_1", name="a_tool", input={"x": 1})
    stub = StubAnthropic([
        ([_Event("thinking_delta", "hmm"), _Event("text_delta", "Let me look.")],
         _message([TextBlock.model_construct(type="text", text="Let me look."), tool_use], "tool_use")),
    ])
    provider = AnthropicProvider(client=stub)
    provider.configure("SYSTEM", TOOLS)
    provider.add_user("hi")
    events = []

    async def emit(e):
        events.append(e)

    turn = await provider.stream_turn(emit)
    assert events == [{"type": "thinking", "text": "hmm"}, {"type": "text", "text": "Let me look."}]
    assert [(c.id, c.name, c.input) for c in turn.tool_calls] == [("tu_1", "a_tool", {"x": 1})]
    assert turn.usage["cache_read_input_tokens"] == 7

    request = stub.requests[0]
    assert request["model"] == "claude-sonnet-5-5"
    assert request["cache_control"] == {"type": "ephemeral"}
    assert request["thinking"]["type"] == "adaptive" and request["output_config"] == {"effort": "medium"}
    assert request["betas"] == [FALLBACK_BETA] and request["fallbacks"] == "default"
    assert request["system"] == [{"type": "text", "text": "SYSTEM"}]
    assert all(t["eager_input_streaming"] for t in request["tools"])
    assert provider.messages[-1]["role"] == "assistant" and provider.messages[-1]["content"][1] is tool_use

    from midibakery.agent.providers.base import ToolResult

    provider.add_tool_results([ToolResult("tu_1", "a_tool", "ok")])
    assert provider.messages[-1] == {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "tu_1", "content": "ok", "is_error": False}]}


async def test_anthropic_truncated_tool_call_and_refusal_are_not_run():
    tool_use = ToolUseBlock.model_construct(type="tool_use", id="tu_1", name="a_tool", input={})
    stub = StubAnthropic([
        ([], _message([tool_use], "max_tokens")),
        ([], _message([], "refusal")),
    ])
    provider = AnthropicProvider(client=stub, fallbacks=False)
    provider.configure("S", TOOLS)
    provider.add_user("x")

    async def emit(e):
        pass

    cut = await provider.stream_turn(emit)
    assert cut.error and not cut.tool_calls
    assert provider.messages[-1]["role"] == "user"  # the truncated turn is not kept
    refused = await provider.stream_turn(emit)
    assert refused.error and refused.stop_reason == "refusal"
    assert "betas" not in stub.requests[0]


async def test_anthropic_retries_unparseable_tool_json():
    stub = StubAnthropic([ValueError("bad json"), ([], _message([TextBlock.model_construct(type="text", text="ok")], "end_turn"))])
    provider = AnthropicProvider(client=stub)
    provider.configure("S", TOOLS)
    provider.add_user("x")

    async def emit(e):
        pass

    turn = await provider.stream_turn(emit)
    assert turn.text == "ok" and len(stub.requests) == 2


# --------------------------------------------------------------------------
# Ollama provider against a mock transport
# --------------------------------------------------------------------------


def test_inline_refs():
    schema = {
        "type": "object",
        "properties": {"loc": {"$ref": "#/$defs/Loc", "description": "where"}, "items": {"type": "array", "items": {"$ref": "#/$defs/Loc"}}},
        "$defs": {"Loc": {"type": "object", "properties": {"track": {"type": "integer"}}}},
    }
    resolved = inline_refs(schema)
    assert "$defs" not in json.dumps(resolved) and "$ref" not in json.dumps(resolved)
    assert resolved["properties"]["loc"]["properties"]["track"] == {"type": "integer"}
    assert resolved["properties"]["loc"]["description"] == "where"


async def test_ollama_streams_text_and_tool_calls():
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        lines = [
            {"message": {"role": "assistant", "content": "Okay"}, "done": False},
            {"message": {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "a_tool", "arguments": {"x": 2}}}]}, "done": False},
            {"message": {"role": "assistant", "content": ""}, "done": True, "prompt_eval_count": 12, "eval_count": 3},
        ]
        return httpx.Response(200, content="\n".join(json.dumps(l) for l in lines).encode())

    provider = OllamaProvider(client=httpx.AsyncClient(transport=httpx.MockTransport(handler)), base_url="http://ollama.test")
    provider.configure("SYS", TOOLS)
    provider.add_user("hi")
    events = []

    async def emit(e):
        events.append(e)

    turn = await provider.stream_turn(emit)
    assert events == [{"type": "text", "text": "Okay"}]
    assert [(c.name, c.input) for c in turn.tool_calls] == [("a_tool", {"x": 2})]
    assert turn.usage == {"input_tokens": 12, "output_tokens": 3, "model": provider.model}
    body = seen[0]
    assert body["messages"][0] == {"role": "system", "content": "SYS"} and body["stream"] is True
    assert body["tools"][0]["function"]["name"] == "b_tool"

    from midibakery.agent.providers.base import ToolResult

    provider.add_tool_results([ToolResult(turn.tool_calls[0].id, "a_tool", "boom", is_error=True)])
    assert provider.messages[-2]["tool_calls"][0]["function"]["name"] == "a_tool"
    assert provider.messages[-1] == {"role": "tool", "content": "ERROR: boom", "tool_name": "a_tool"}


async def test_ollama_unreachable_is_a_turn_error():
    def handler(request):
        raise httpx.ConnectError("refused", request=request)

    provider = OllamaProvider(client=httpx.AsyncClient(transport=httpx.MockTransport(handler)), base_url="http://ollama.test")
    provider.configure("S", TOOLS)
    provider.add_user("x")

    async def emit(e):
        pass

    turn = await provider.stream_turn(emit)
    assert turn.error and "ollama serve" in turn.error


# --------------------------------------------------------------------------
# LM Studio (OpenAI-compatible) provider against a mock transport
# --------------------------------------------------------------------------


def sse(*chunks):
    return httpx.Response(200, content=("".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n").encode())


def lmstudio(handler):
    return OpenAICompatProvider(client=httpx.AsyncClient(transport=httpx.MockTransport(handler)), base_url="http://lmstudio.test/v1")


async def test_lmstudio_streams_text_and_joins_tool_call_fragments():
    seen = []

    def handler(request):
        seen.append((str(request.url), json.loads(request.content)))
        delta = lambda **d: {"choices": [{"index": 0, "delta": d, "finish_reason": None}]}  # noqa: E731
        return sse(
            delta(role="assistant", content="Ok"),
            delta(reasoning_content="think"),
            delta(tool_calls=[{"index": 0, "id": "c1", "type": "function", "function": {"name": "a_tool", "arguments": ""}}]),
            delta(tool_calls=[{"index": 0, "function": {"arguments": '{"x":'}}]),
            delta(tool_calls=[{"index": 1, "id": "c2", "type": "function", "function": {"name": "b_tool", "arguments": "{}"}}]),
            delta(tool_calls=[{"index": 0, "function": {"arguments": " 2}"}}]),
            {"choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}]},
            {"choices": [], "usage": {"prompt_tokens": 40, "completion_tokens": 9}},
        )

    provider = lmstudio(handler)
    provider.configure("SYS", TOOLS)
    provider.add_user("hi")
    events = []

    async def emit(e):
        events.append(e)

    turn = await provider.stream_turn(emit)
    assert events == [{"type": "text", "text": "Ok"}, {"type": "thinking", "text": "think"}]
    assert turn.stop_reason == "tool_use"
    assert [(c.id, c.name, c.input) for c in turn.tool_calls] == [("c1", "a_tool", {"x": 2}), ("c2", "b_tool", {})]
    assert turn.usage == {"input_tokens": 40, "output_tokens": 9, "model": provider.model}
    url, body = seen[0]
    assert url == "http://lmstudio.test/v1/chat/completions"
    assert body["stream"] is True and body["messages"][0] == {"role": "system", "content": "SYS"}
    assert body["tools"][0] == {"type": "function", "function": {"name": "b_tool", "description": "B", "parameters": {"type": "object", "properties": {}}}}

    provider.add_tool_results([ToolResult("c1", "a_tool", "boom", is_error=True), ToolResult("c2", "b_tool", "fine")])
    assert provider.messages[-3]["tool_calls"][0] == {"id": "c1", "type": "function", "function": {"name": "a_tool", "arguments": '{"x": 2}'}}
    assert provider.messages[-2:] == [
        {"role": "tool", "tool_call_id": "c1", "content": "ERROR: boom"},
        {"role": "tool", "tool_call_id": "c2", "content": "fine"},
    ]


async def test_lmstudio_plain_answer_and_http_error():
    replies = [
        sse({"choices": [{"index": 0, "delta": {"content": "Hallo"}, "finish_reason": "stop"}]}),
        httpx.Response(400, json={"error": "The number of tokens to keep from the initial prompt is greater than the context length."}),
    ]
    provider = lmstudio(lambda request: replies.pop(0))
    provider.configure("S", [])
    provider.add_user("x")

    async def emit(e):
        pass

    turn = await provider.stream_turn(emit)
    assert (turn.stop_reason, turn.text, turn.tool_calls) == ("end_turn", "Hallo", [])
    assert provider.messages[-1] == {"role": "assistant", "content": "Hallo"}
    turn = await provider.stream_turn(emit)
    # what to do instead of LM Studio's own words (qwen loaded on first use with an 8k context)
    assert turn.error and "too small a context" in turn.error and "-c 32768" in turn.error


async def test_lmstudio_unreachable_is_a_turn_error(monkeypatch):
    def handler(request):
        raise httpx.ConnectError("refused", request=request)

    monkeypatch.setenv("LMSTUDIO_HOST", "localhost:9999")
    provider = OpenAICompatProvider(client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    assert provider.base_url == "http://localhost:9999"
    provider.configure("S", TOOLS)
    provider.add_user("x")

    async def emit(e):
        pass

    turn = await provider.stream_turn(emit)
    assert turn.error and "localhost:9999" in turn.error and "lms server start" in turn.error


def test_make_provider_lmstudio():
    provider = make_provider("lmstudio", "google/gemma-4-e4b")
    assert (provider.name, provider.model) == ("lmstudio", "google/gemma-4-e4b")


def test_compact_schema():
    schema = {
        "type": "object",
        "title": "toolArguments",
        "properties": {
            "title": {"type": "string", "title": "Title", "default": None},
            "seed": {"anyOf": [{"type": "integer"}, {"type": "null"}], "default": None, "description": "Same seed, same notes. Omit for a new idea."},
            "bars": {"type": "integer", "minimum": 1, "maximum": 64, "default": 4},
        },
    }
    assert compact_schema(schema) == {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "seed": {"type": "integer", "description": "Same seed, same notes."},
            "bars": {"type": "integer"},
        },
    }


def test_compact_schema_drops_enum_listings_and_dangling_examples():
    schema = {"properties": {
        "rhythm": {"enum": ["sustain", "pulse"], "description": "(chords) sustain (default) or pulse"},
        "voices": {"enum": [3, 4], "description": "3 (default) or 4"},
        "mode": {"enum": ["a", "b"], "description": "How it plays. a or b."},
        "clip": {"type": "string", "description": "A clip in the Arrangement, e.g. 'Verse'. Or its index."},
    }}
    assert compact_schema(schema)["properties"] == {
        "rhythm": {"enum": ["sustain", "pulse"], "description": "(chords)"},
        "voices": {"enum": [3, 4]},
        "mode": {"enum": ["a", "b"], "description": "How it plays."},
        "clip": {"type": "string", "description": "A clip in the Arrangement."},
    }


async def test_small_profile_fits_and_is_compact(client):
    provider = ScriptedProvider([Turn("end_turn", text="ok")])

    async def emit(e):
        pass

    async def no(message):
        return False

    async with ToolHost(build_server(client), no, SMALL_TOOLS) as host:
        Agent(provider, host, SMALL_SYSTEM_PROMPT, compact=True)
    assert "plan_changes" not in {t.name for t in provider.tools} and len(provider.tools) == len(SMALL_TOOLS)
    assert "launch_clip" in {t.name for t in provider.tools}  # transport alone cannot play a clip
    compact = json.dumps([t.input_schema for t in provider.tools])
    assert "$ref" not in compact and '"title"' not in compact and "if_exists" not in compact
    # Measured against Gemma 4 E4B in LM Studio: ~3.7k of 8192 tokens incl. descriptions. Keep it there.
    assert len(compact) + len(SMALL_SYSTEM_PROMPT) < 14000


SESSION = {
    "song": {"tempo": 120.0, "signature_numerator": 4, "signature_denominator": 4, "root_note": 9, "scale_name": "Minor",
             "scene_count": 8, "is_playing": False, "loop": True, "loop_start": 0.0, "loop_length": 16.0},
    "tracks": [
        {"index": 0, "id": 11, "name": "Drums", "kind": "midi", "color_index": 3, "mute": False, "solo": False, "arm": False,
         "volume": 0.85, "pan": 0.0, "devices": [{"index": 0, "name": "909 Core Kit", "class_name": "DrumGroupDevice"}],
         "clips": [{"slot": 0, "name": "Beat", "length": 8.0, "is_midi": True, "is_playing": False},
                   {"slot": 1, "name": "Fill", "length": 4.0, "is_midi": True, "is_playing": False}]},
        {"index": 1, "id": 12, "name": "Chord Stabs", "kind": "midi", "color_index": 5, "mute": False, "solo": False, "arm": False,
         "volume": 0.85, "pan": 0.0, "devices": [{"index": 0, "name": "Drift", "class_name": "Drift"}],
         "clips": [{"slot": 3, "name": "Stabs", "length": 16.0, "is_midi": True, "is_playing": True}]},
        {"index": 2, "id": 13, "name": "Vox", "kind": "audio", "color_index": 1, "mute": False, "solo": False, "arm": None,
         "volume": 0.85, "pan": 0.0, "devices": [], "clips": []},
    ],
}


def test_compact_session():
    text = compact_session(SESSION)
    assert text.splitlines() == [
        "Song: 120 BPM, 4/4, scale A Minor, 8 slots per track (0-7).",
        "Tracks (index 'name' [kind, devices]; free slots; clips as slot 'name' length):",
        "0 'Drums' [drums, 909 Core Kit]; free slots 2-7; clips 0 'Beat' 2 bars, 1 'Fill' 1 bars",
        "1 'Chord Stabs' [midi, Drift]; free slots 0-2,4-7; clips 3 'Stabs' 4 bars",
        "2 'Vox' [audio]; free slots 0-7; no clips",
        "No other tracks (vocals, guitar, ...): say so, use none.",
    ]
    assert len(text) * 2 < len(json.dumps(SESSION))


async def test_small_profile_shortens_get_session(client, live):
    async def yes(message):
        return True

    async def emit(e):
        pass

    results = {}
    for compact in (False, True):
        provider = ScriptedProvider([tool_turn(("get_session", {})), Turn("end_turn", text="ok")])
        async with ToolHost(build_server(client), yes, SMALL_TOOLS) as host:
            await Agent(provider, host, SMALL_SYSTEM_PROMPT, compact=compact).send("what is in the set?", emit)
        results[compact] = provider.results[0][0].content
    assert json.loads(results[False])["song"]["tempo"] == 120  # full JSON for Claude
    assert results[True].startswith("Song: 120 BPM, 4/4") and "0 '1-MIDI' [midi]; free slots 0-7; no clips" in results[True]


async def test_full_tool_set_stays_within_the_local_budget(client):
    # Local models get every tool (compact). With a 32k context the prompt must leave room for the
    # conversation: ~33k characters for 30 tools was ~10k tokens with Gemma 4 E4B. Grow tools, not this.
    provider = ScriptedProvider([Turn("end_turn", text="ok")])

    async def no(message):
        return False

    async with ToolHost(build_server(client), no, None) as host:
        Agent(provider, host, SYSTEM_PROMPT, compact=True)
    payload = json.dumps([{"name": t.name, "description": t.description, "input_schema": t.input_schema} for t in provider.tools])
    assert {"get_mixer", "update_mixer", "create_return_track"} <= {t.name for t in provider.tools}
    assert len(payload) + len(SYSTEM_PROMPT) < 36000


async def test_a_model_repeating_a_failing_call_is_stopped(client, live):
    # A local model that keeps sending the same wrong call: stopped after 3, not after 24 rounds
    bad = ("compose", {"kind": "bass", "track": 1, "arrangement_clip": 7})
    provider = ScriptedProvider([tool_turn(bad)] * 30)
    events = await run(build_server(client), provider, "more bass variation in the groove")
    assert len(provider.results) == 3
    assert events[-1]["type"] == "error" and events[-1]["code"] == "STUCK"
    assert "compose failed 3 times with the same arguments" in events[-1]["message"]
    assert "No arrangement clip index 7" in events[-1]["message"]


async def test_a_model_failing_in_every_round_is_stopped(client, live):
    provider = ScriptedProvider([tool_turn(("compose", {"kind": "bass", "track": 1, "arrangement_clip": i})) for i in range(30)])
    events = await run(build_server(client), provider, "vary the bass")
    assert len(provider.results) == 6 and events[-1]["code"] == "STUCK" and "6 rounds in a row" in events[-1]["message"]


def test_compact_session_shows_the_arrangement():
    from midibakery.mcp.server import with_arrangement

    arrangement = {"locators": [{"index": 0, "name": "Drop", "time": 0.0}, {"index": 1, "name": "Groove", "time": 32.0}],
                   "tracks": [{"index": 1, "name": "Chord Stabs", "clips": [
                       {"index": 0, "name": "Drop Bass", "start": 0.0, "end": 32.0, "is_midi": True},
                       {"index": 1, "name": "Groove Bass", "start": 32.0, "end": 128.0, "is_midi": True}]}]}
    session = with_arrangement(SESSION, arrangement)
    assert session["tracks"][1]["arrangement_clips"][1] == {"index": 1, "name": "Groove Bass", "start_bar": 9, "bars": 24}
    assert session["locators"] == [{"name": "Drop", "bar": 1}, {"name": "Groove", "bar": 9}]
    lines = compact_session(session).splitlines()
    assert lines[2] == "Arrangement sections (locators): Drop bar 1, Groove bar 9."
    assert lines[4].endswith("; arrangement clips 0 'Drop Bass' 8 bars (song bars 1-8), 1 'Groove Bass' 24 bars (song bars 9-32)")
    assert "arrangement_clip=<index or name>" in lines[-2]
    assert compact_session(SESSION).splitlines()[2].startswith("0 'Drums'")  # no arrangement: as before


def test_language_reminder_names_the_language():
    # gemma answered English and German requests in Korean and Turkish with the generic reminder
    assert "Deutsch" in language_reminder("Variiere die zweite Hälfte des Clips 'Breakdown Bass' ein wenig.")
    assert "Deutsch" in language_reminder("Lösch den Clip 'Intro Kick'.")
    assert "English" in language_reminder("Create a variation for the clip 'Breakdown Bass'. The second half should change.")
    assert "language of this message" in language_reminder("ok")


def test_invented_sub_objects_are_lifted():
    # gemma: {"operation": "transpose", "range": {"semitones": 12}} and "operation_note": {...}
    schema = {"properties": {"track": {}, "operation": {}, "semitones": {}, "chords_from": {}}}
    assert lift_nested(schema, {"track": 1, "operation": "transpose", "range": {"semitones": 12}}) == {
        "track": 1, "operation": "transpose", "semitones": 12}
    # an object of unknown fields, or one that would overwrite a set parameter, stays (and is reported)
    assert "range" in lift_nested(schema, {"semitones": 2, "range": {"semitones": 12}})
    assert "x" in lift_nested(schema, {"x": {"y": 1}})


async def test_a_model_claiming_a_failed_write_is_asked_to_fix_it(client, live):
    # gemma: transform_notes failed, then "I transposed the Lead Riff an octave down"
    bad = ("transform_notes", {"track": 1, "slot": 0, "operation": "transpose", "semitones": 99})
    provider = ScriptedProvider([tool_turn(bad), Turn("end_turn", text="Done, an octave down."), Turn("end_turn", text="That did not work.")])
    events = await run(build_server(client), provider, "play the lead an octave lower")
    assert provider.users[-1].startswith("[Check: transform_notes failed") and "changed nothing" in provider.users[-1]
    assert events[-1]["type"] == "done" and not provider.turns  # asked once, then the model's answer stands


async def test_an_empty_answer_gets_one_more_try(client, live):
    provider = ScriptedProvider([Turn("end_turn", text=""), Turn("end_turn", text="Loaded 106 Organ.")])
    events = await run(build_server(client), provider, "load an organ preset on the chords")
    assert provider.users[-1].startswith("[You answered nothing")
    assert events[-1]["type"] == "done" and not provider.turns


async def test_local_models_get_the_session_with_the_first_message(client, live):
    # gemma asked "which track is 'Drop Bass' on?" instead of calling get_session
    provider = ScriptedProvider([Turn("end_turn", text="ok?")] * 3)

    async def emit(event):
        pass

    async def no(message):
        return False

    async with ToolHost(build_server(client), no) as host:
        agent = Agent(provider, host, compact=True)
        await agent.send("rename 'Drop Bass' to 'Main Bass'", emit)
        await agent.send("and the intro?", emit)
        first, second = provider.users
        agent.reset()
        await agent.send("hi", emit)
    (after_reset,) = provider.users
    assert "[The Live set now (get_session):\nSong: 120 BPM" in first and "1 '2-MIDI'" in first
    assert "get_session" not in second and "get_session" in after_reset


async def test_a_change_claimed_without_a_tool_is_questioned(client, live):
    # gemma: "Tempo auf 128 BPM gesetzt." and no tool call
    provider = ScriptedProvider([Turn("end_turn", text="Tempo auf 128 BPM gesetzt."), tool_turn(("set_song", {"tempo": 128})),
                                 Turn("end_turn", text="Jetzt wirklich: 128 BPM.")])

    async def emit(event):
        pass

    async def yes(message):
        return True

    async with ToolHost(build_server(client), yes) as host:
        await Agent(provider, host, compact=True).send("Setz das Tempo auf 128 BPM.", emit)
    assert provider.users[-1].startswith("[No tool ran") and not provider.turns
    assert live.on_main(lambda: live.song.tempo) == 128


def test_claims_a_change():
    from midibakery.agent.loop import claims_a_change

    assert claims_a_change("Tempo auf 128 BPM gesetzt.") and claims_a_change("I renamed the clip.")
    assert not claims_a_change("OK. What would you like me to do?") and not claims_a_change("Soll ich es löschen?")
    # gemma: "Tempo auf 128 BPM eingestellt." and "Ich lade den Organ-Preset" without a call
    assert claims_a_change("Tempo auf 128 BPM eingestellt.") and claims_a_change("Ich lade den Organ-Preset auf die Spur.")
    assert claims_a_change("I'll load the organ preset.")
    assert not claims_a_change("I cannot set a loudness target; Live has no mastering tool.")


async def _compact_send(client, provider, text):
    events = []

    async def emit(event):
        events.append(event)

    async def yes(message):
        return True

    async with ToolHost(build_server(client), yes) as host:
        await Agent(provider, host, compact=True).send(text, emit)
    return events


async def test_a_vague_wish_changes_the_clip_instead_of_composing_a_new_one(client, live):
    # gemma: "Mach den Bass spannender" -> compose into a free slot, every time
    await client.call("clip.create", {"track": 1, "slot": 0, "length": 8.0, "name": "Bass Loop"})
    compose = ("compose", {"kind": "bass", "track": 1})
    provider = ScriptedProvider([tool_turn(compose), tool_turn(("transform_notes", {"track": 1, "slot": 0, "operation": "variation"})),
                                 Turn("end_turn", text="Variiert.")])
    events = await _compact_send(client, provider, "Mach den Bass spannender.")
    refusal = next(e for e in events if e["type"] == "tool_result" and e["name"] == "compose")
    assert refusal["is_error"] and "slot 0 'Bass Loop'" in refusal["result"] and "did not ask for a new clip" in refusal["result"]
    assert live.on_main(lambda: [s.clip is not None for s in live.song.tracks[1].clip_slots][:2]) == [True, False]


async def test_a_new_clip_is_composed_when_the_user_asks_for_one(client, live):
    await client.call("clip.create", {"track": 1, "slot": 0, "length": 8.0, "name": "Bass Loop"})
    provider = ScriptedProvider([tool_turn(("compose", {"kind": "bass", "track": 1})), Turn("end_turn", text="Neue Bassline.")])
    events = await _compact_send(client, provider, "Schreib eine neue Bassline.")
    assert not any(e["type"] == "tool_result" and e["is_error"] for e in events)
    assert live.on_main(lambda: [s.clip is not None for s in live.song.tracks[1].clip_slots][:2]) == [True, True]


async def test_the_new_clip_guard_lets_a_repeated_call_through(client, live):
    # twice per message: a model that insists gets its clip
    await client.call("clip.create", {"track": 1, "slot": 0, "length": 8.0, "name": "Bass Loop"})
    compose = ("compose", {"kind": "bass", "track": 1})
    provider = ScriptedProvider([tool_turn(compose), tool_turn(compose), tool_turn(compose), Turn("end_turn", text="Neu.")])
    await _compact_send(client, provider, "Mach den Bass spannender.")
    assert live.on_main(lambda: [s.clip is not None for s in live.song.tracks[1].clip_slots][:2]) == [True, True]


async def test_deleting_an_arrangement_clip_by_name_asks_with_its_name(client, live):
    # gemma: delete_clip {"arrangement_clip": "Intro Kick"} crashed the confirmation; edit_arrangement took no names
    await client.call("arrangement.edit", {"actions": [
        {"action": "add_clip", "track": 0, "start": 0, "length": 4, "name": "Intro Kick"},
        {"action": "add_clip", "track": 0, "start": 8, "length": 4, "name": "Drop Kick"},
        {"action": "add_clip", "track": 0, "start": 16, "length": 4, "name": "Outro Kick"},
    ]})
    provider = ScriptedProvider([tool_turn(("delete_clip", {"track": 0, "arrangement_clip": "Intro Kick"})),
                                 tool_turn(("edit_arrangement", {"actions": [{"action": "delete_clip", "track": 0, "clip": "outro kick"}]})),
                                 Turn("end_turn", text="Deleted.")])
    events = await run(build_server(client), provider, "delete Intro Kick and Outro Kick")
    assert {"type": "confirm", "message": "Delete arrangement clip 'Intro Kick' (index 0) of track 1 '1-MIDI'?"} in events
    assert not any(e.get("is_error") for e in events if e["type"] == "tool_result")
    assert [c["name"] for c in (await client.call("arrangement.get", {}))["tracks"][0]["clips"]] == ["Drop Kick"]


async def test_deleting_a_clip_is_not_answered_with_delete_track(client, live):
    # gemma: "Delete the clip 'Intro Kick'" -> delete_track {"track": 0}
    provider = ScriptedProvider([tool_turn(("delete_track", {"track": 0})), Turn("end_turn", text="Could not.")])
    before = live.on_main(lambda: len(live.song.tracks))
    events = await _compact_send(client, provider, "Delete the clip 'Intro Kick'.")
    refusal = next(e for e in events if e["type"] == "tool_result")
    assert refusal["is_error"] and "not a track" in refusal["result"]
    assert live.on_main(lambda: len(live.song.tracks)) == before
    # naming the track as well keeps delete_track available
    from midibakery.agent.loop import deletes_wrong_thing

    assert not deletes_wrong_thing("Lösch die Spur und den Clip", "delete_track")
    assert deletes_wrong_thing("Lösch den Clip 'Intro Kick'", "delete_track")


async def test_a_request_answered_with_talk_only_is_nudged_once(client, live):
    # gemma: "Tausche ... tausche ich gegeneinander." / "wird nun mit dem Sound versehen" and no tool call
    provider = ScriptedProvider([Turn("end_turn", text="Die Chords-Spur wird nun mit dem Sound versehen."),
                                 Turn("end_turn", text="Das kann ich mit meinen Tools nicht.")])
    await _compact_send(client, provider, "Lade ein Orgel-Preset auf die Chords-Spur.")
    assert provider.users[-1].startswith("[No tool ran") and not provider.turns
    # a question from the user is answered without a nudge
    provider = ScriptedProvider([Turn("end_turn", text="Eine Oktave sind 12 Halbtöne.")])
    await _compact_send(client, provider, "Wie viele Halbtöne ist eine Oktave?")
    assert not provider.turns and not provider.users[-1].startswith("[No tool ran")


async def test_the_new_clip_guard_covers_a_free_slot_on_a_track_with_clips(client, live):
    # gemma: compose into slot 1 beside the 'Hats Loop' in slot 0
    await client.call("clip.create", {"track": 1, "slot": 0, "length": 8.0, "name": "Hats Loop"})
    provider = ScriptedProvider([tool_turn(("compose", {"kind": "drums", "track": 1, "slot": 1})), Turn("end_turn", text="Nicht möglich.")])
    events = await _compact_send(client, provider, "Make the hats groove more.")
    assert next(e for e in events if e["type"] == "tool_result")["is_error"]
    assert live.on_main(lambda: [s.clip is not None for s in live.song.tracks[1].clip_slots][:2]) == [True, False]


SET_WITH_HATS = {"tracks": [{"index": 0, "name": "Drums", "volume": 0.85}, {"index": 1, "name": "Hats", "volume": 0.7}]}


def test_a_relative_volume_wish_must_change_the_value():
    from midibakery.agent.loop import unchanged_volume

    # gemma: "mach die Hats leiser" -> volume 0.85 on a track already at 0.85
    assert "nothing would change" in unchanged_volume("Mach die Drums leiser.", SET_WITH_HATS, "update_track", {"track": 0, "volume": 0.85})
    assert unchanged_volume("Mach die Hats leiser.", SET_WITH_HATS, "update_track", {"track": "Hats", "volume": 0.6}) is None
    assert "not 'quieter'" in unchanged_volume("Mach die Hats leiser.", SET_WITH_HATS, "update_track", {"track": 1, "mute": True})
    assert unchanged_volume("Setz die Hats auf 0.7.", SET_WITH_HATS, "update_track", {"track": 1, "volume": 0.7}) is None  # absolute wish


def test_update_track_says_how_to_change_volume_relatively():
    from midibakery.catalog.ops import TrackSet

    assert "current value -/+ 0.1" in json.dumps(TrackSet.model_json_schema()["properties"]["volume"])


def test_mastering_and_a_missing_vocal_track_are_refused():
    from midibakery.agent.loop import NO_MASTERING, NO_VOCALS, missing_thing

    assert missing_thing("Master den Song auf -14 LUFS.", SET_WITH_HATS) == NO_MASTERING
    # plan_master's chain is the way to master: its apply_plan goes through
    assert missing_thing("Master den Song.", SET_WITH_HATS, "apply_plan") is None
    assert missing_thing("Wie viele LUFS hat der Song?", SET_WITH_HATS, "measure_master") is None
    assert missing_thing("Make the vocals louder.", SET_WITH_HATS) == NO_VOCALS
    assert missing_thing("Make the vocals louder.", {"tracks": [{"name": "Lead Vocals"}]}) is None
    assert missing_thing("Mach die Hats leiser.", SET_WITH_HATS) is None


async def test_the_agent_refuses_a_write_for_a_missing_vocal_track(client, live):
    provider = ScriptedProvider([tool_turn(("update_track", {"track": 3, "volume": 0.95})),
                                 Turn("end_turn", text="Es gibt keine Gesangsspur.")])
    events = await _compact_send(client, provider, "Make the vocals louder.")
    result = next(e for e in events if e["type"] == "tool_result" and e["name"] == "update_track")
    assert result["is_error"] and "no vocal track" in result["result"]


async def test_a_plan_waits_for_apply_without_a_nudge(client, live):
    # gemma: plan_song, "You can apply this plan with apply_plan(...)", then the nudge made it apply the song unasked
    provider = ScriptedProvider([
        Turn("tool_use", tool_calls=[ToolCall("t1", "plan_master", {"genre": "house"})]),
        Turn("end_turn", text="Here is the master chain. Apply it when you like."),
    ])
    await _compact_send(client, provider, "Leg eine Master-Kette für House an.")
    assert not provider.turns and not any(u.startswith("[No tool ran") for u in provider.users)
    assert live.on_main(lambda: len(live.song.master_track.devices)) == 0
