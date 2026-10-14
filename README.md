# MidiShower

AI composition and session control for Ableton Live 12 Suite.

See [docs/KONZEPT.md](docs/KONZEPT.md) for the architecture and roadmap.

## Layout

| Path | What |
|---|---|
| `packages/core` | `midishower` Python package: op catalog, bridge client, composition engine (`compose/`), MCP server, CLI |
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

### Claude Code / Claude Desktop

```bash
claude mcp add midishower -- uv --directory /Users/maxx/Development/Ableton/MidiShower run midishower mcp
```

## License

Proprietary, all rights reserved. The source is publicly visible, but no right to use, copy, modify or distribute it is granted; see [LICENSE](LICENSE). Ableton and Ableton Live are trademarks of Ableton AG; this project is not affiliated with Ableton.
