# MidiBakery

By Klirrwerk. AI composition and session control for Ableton Live 12 Suite.

See [docs/KONZEPT.md](docs/KONZEPT.md) for the concept and roadmap, and [docs/ARCHITEKTUR.md](docs/ARCHITEKTUR.md) for how the Remote Script, the core (MCP server, API, agent) and the Max for Live devices work together.

## Layout

| Path | What |
|---|---|
| `packages/core` | `midibakery` Python package: op catalog, bridge client, composition engine (`compose/`), agent loop (`agent/`), local API for Max for Live (`api/`), MCP server, CLI |
| `packages/remote_script/MidiBakery` | Remote Script loaded by Live (stdlib only, Python 3.11) |
| `packages/m4l` | Max for Live devices: build script and sources (chat device, MIDI Tools) |
| `tests/` | Contract tests: real Remote Script + fake Live Object Model over a real socket |

## Development

```bash
uv sync
uv run pytest
uv run midibakery manifest          # after changing the catalog
uv run midibakery install-script --link
uv run midibakery ping              # with Live running and MidiBakery selected as Control Surface
```

### Chat and local API

```bash
uv run midibakery chat                                  # Claude (claude-sonnet-5-5) in the terminal
uv run midibakery chat --model claude-opus-5-5
uv run midibakery chat --provider ollama --model qwen3:8b  # local: all tools, compact schemas (--small for 8k context)
uv run midibakery chat --provider lmstudio --model google/gemma-4-e4b  # LM Studio server (LMSTUDIO_HOST, default 127.0.0.1:1234)
uv run midibakery api                                   # HTTP/WebSocket API for the Max for Live devices
```

The Anthropic provider reads `ANTHROPIC_API_KEY` (or an `ant auth login` profile). The API listens on
127.0.0.1:8766 and writes its port and token to `api.json` in the MidiBakery config folder.

### Max for Live devices

```bash
uv run python packages/m4l/build.py --install   # builds the .amxd files into Live's User Library
uv run midibakery install-script --api-provider lmstudio  # the devices talk to the API, which now starts with Live
```

The Remote Script starts the API when Live loads it and stops it when Live quits (`launcher.json` and
`api.log` in the config folder; `--no-api` turns this off). An API that already runs on the port is used as is.
Live does not see your shell's environment, so the Anthropic provider needs an `ant auth login` profile there.

- **MidiBakery Chat** (Max for Live > Max MIDI Effect > MidiBakery): chat with the agent in the device view;
  MIDI passes through. *Pop out* opens the same chat in the browser.
- **MidiBakery Generator / Transform** (clip view, Generate / Transform panels, Live 12.2+): the composition
  engine on the selected time range, in the clip's scale. MIDI Tools must answer synchronously, so the first
  apply shows "Working..." and the result follows a moment later in the same apply cycle.

### Claude Code / Claude Desktop

```bash
claude mcp add midibakery -- uv --directory /Users/maxx/Development/Ableton/MidiBakery run midibakery mcp
```

## License

Proprietary, all rights reserved. The source is publicly visible, but no right to use, copy, modify or distribute it is granted; see [LICENSE](LICENSE). Ableton and Ableton Live are trademarks of Ableton AG; this project is not affiliated with Ableton.
