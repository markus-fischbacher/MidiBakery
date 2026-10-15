"""Agent loop, tool host and providers, without calling a real model."""

import json

import httpx2 as httpx
from anthropic.types import Message, TextBlock, ToolUseBlock, Usage

from midishower.agent import REDUCED_TOOLS, Agent, ToolHost
from midishower.agent.providers.anthropic import FALLBACK_BETA, AnthropicProvider
from midishower.agent.providers.base import Provider, ToolCall, Turn
from midishower.agent.providers.ollama import OllamaProvider, inline_refs
from midishower.agent.tools import ToolSpec
from midishower.mcp import build_server


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
        tool_turn(("compose_drums", {"track": 0, "slot": 0, "seed": 3, "bars": 2})),
        Turn("end_turn", text="Done: 2 bars of house drums on track 1."),
    ])
    events = await run(build_server(client), provider, "Make drums")
    kinds = [e["type"] for e in events]
    assert kinds == ["tool_call", "tool_result", "tool_call", "tool_result", "plan", "text", "done"]
    assert provider.users == ["Make drums"]
    assert "MidiShower" in provider.system and "get_session" in {t.name for t in provider.tools}
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

    from midishower.agent.providers.base import ToolResult

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

    from midishower.agent.providers.base import ToolResult

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
