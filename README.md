# MidiShower

AI composition and session control for Ableton Live 12 Suite.

See [docs/KONZEPT.md](docs/KONZEPT.md) for the architecture and roadmap.

## Layout

| Path | What |
|---|---|
| `packages/core` | `midishower` Python package: op catalog, bridge client, composition engine (`compose/`), agent loop (`agent/`), local API for Max for Live (`api/`), MCP server, CLI |
| `packages/remote_script/MidiShower` | Remote Script loaded by Live (stdlib only, Python 3.11) |
| `tests/` | Contract tests: real Remote Script + fake Live Object Model over a real socket |

## Development

```bash
uv sync
uv run pytest
uv run midishower manifest          # after changing the catalog
uv run midishower install-script --link
uv run midishower ping              # with Live running and MidiShower selected as Control Surface
```

### Chat and local API

```bash
uv run midishower chat                                  # Claude (claude-sonnet-5-5) in the terminal
uv run midishower chat --model claude-opus-5-5
uv run midishower chat --provider ollama --model qwen3:8b  # local, reduced tool set
uv run midishower api                                   # HTTP/WebSocket API for the Max for Live devices
```

The Anthropic provider reads `ANTHROPIC_API_KEY` (or an `ant auth login` profile). The API listens on
127.0.0.1:8766 and writes its port and token to `api.json` in the MidiShower config folder.

### Claude Code / Claude Desktop

```bash
claude mcp add midishower -- uv --directory /Users/maxx/Development/Ableton/MidiShower run midishower mcp
```

## License

Proprietary, all rights reserved. The source is publicly visible, but no right to use, copy, modify or distribute it is granted; see [LICENSE](LICENSE). Ableton and Ableton Live are trademarks of Ableton AG; this project is not affiliated with Ableton.
