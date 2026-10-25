# MidiBakery as an MCP server

The **MCP server** brings MidiBakery to **Claude Desktop**, **Claude Code** or any other MCP app. You talk to Claude in its own window instead of the Chat device; Claude uses the same 13 tools to read your Live set and build songs in it.

Deutsche Version: [MCP_SERVER.de.md](MCP_SERVER.de.md) · Back to the [User Guide](USER_GUIDE.md)

## Setup

**Requirements:** MidiBakery is installed, Live is running and the **MidiBakery** Control Surface is on ([User Guide, chapter 3](USER_GUIDE.md#3-set-up-in-live)). The Chat device is not needed.

The server is the command `midibakery mcp` (stdio). **Claude Code:**

```bash
claude mcp add midibakery -- "$HOME/Library/Application Support/MidiBakery/runtime/<version>/midibakery" mcp
```

On Windows the program is in `%LOCALAPPDATA%\Programs\MidiBakery\runtime\<version>\`. From a checkout of the repository: `claude mcp add midibakery -- uv --directory <path> run midibakery mcp`.

**Claude Desktop:** **Settings > Developer > Edit Config** (`claude_desktop_config.json`), then restart Claude Desktop:

```json
{
  "mcpServers": {
    "midibakery": {
      "command": "/Users/<you>/Library/Application Support/MidiBakery/runtime/<version>/midibakery",
      "args": ["mcp"]
    }
  }
}
```

The path contains the version: adjust it after an update. For apps without stdio, `midibakery mcp --http` serves on `127.0.0.1:8765` (`--port` changes it).

**Test it:** "What is in my Live set?" Claude calls `get_session`. If that fails, run `midibakery ping`.

## Safety

- Every change is a step in Live's undo list; Claude can call `undo` itself.
- `plan_song` changes **nothing** until `apply_plan`. A song never overwrites existing Arrangement clips.
- Before deleting a clip or replacing notes MidiBakery asks (apps without question support get a `plan_id` instead and must ask you in the chat before `apply_plan`). Declined: `CANCELLED`. If you get `CANCELLED` without declining (the app shows no question), use `compose` with `preview=true`, then `apply_plan`.
- The server talks only to Live. The app you are in sees what the tools return: track and clip names, notes, tempo.

## The 13 tools

Tracks, slots and arrangement clips count from **0** (track 1 in Live = `track 0`). Time is in beats; pitch 60 = C3. Clip tools take `slot` (Session) **or** `arrangement_clip` (Arrangement: index or **name**, e.g. "Drop Bass").

| Tool | Kind | What it does |
|---|---|---|
| `get_session` | read | Tempo, signature, scale, transport and all tracks with devices and clips. |
| `get_clip` | read | A clip's properties and, for MIDI clips, all notes. |
| `get_arrangement` | read | Arrangement clips per track, locators, song length. |
| `get_reference` | read | References from the Reference Analyzer and Live Sets imported by the Set Importer: sections, key, tempo, and with `name` the per-bar lanes. |
| `plan_song` | read | Plans a **whole song**: `genre` (`house`, `melodic_techno`, `peak_time_techno`, `drum_and_bass`, `trap`), `length` (`radio`/`standard`/`extended`), `key` (e.g. `A minor`; set in Live), `progression`, `reference` (an analyzed song or imported Set), `loops_from` (`{"bass": "<Set>"}`; roles drums, bass, lead, chords), `my_loops` (the seed draws loops from the imported Sets), `seed`. Tempo follows the genre or reference; roles a Set lacks are filled from the genre. Returns a preview and a `plan_id`. |
| `apply_plan` | **asks first** (when replacing) | Writes a plan to Live. `CONFLICT` if a target changed since planning. Plans are kept in memory (the last 32). |
| `compose` | **asks first** (when replacing) | **One part** as a MIDI clip in the set's key: `kind` drums, bass, chords or melody; `bars`, `seed`, `style`, `pattern`, `density`, `swing`, `progression`, `chords_from`, `follow_kick`, `if_exists`, `preview`. With `arrangement_clip` it rewrites that clip. |
| `edit_arrangement` | write | Add MIDI clips, copy session clips, **move, swap, delete** arrangement clips, set or delete locators (transport stopped). One undo step; a clip never lands on another. |
| `create_track` | write | Create a MIDI or audio track (`kind`, `index` for the position, `name`); default: at the end. `compose` can then write into it. |
| `delete_clip` | **asks first** | Delete one clip (Session by `slot`, Arrangement by `arrangement_clip`). |
| `set_song` | write | Tempo, signature, key (`root_note`, `scale_name`, `scale_mode`), metronome, loop. |
| `transport` | write | Play, stop, continue, stop all clips, toggle arrangement record. |
| `undo` | write | Undo or redo in Live. |

## For developers

The server is `midibakery.mcp.server.build_server`; Live operations are in `midibakery.catalog` and reach the Remote Script through the bridge. The Chat device's agent uses the same tools. More in [ARCHITECTURE.md](../ARCHITECTURE.md).
