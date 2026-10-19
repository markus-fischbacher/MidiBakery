# MidiBakery as an MCP server

The **MCP server** lets you control Ableton Live from **Claude Desktop**, **Claude Code** or any other MCP-capable app. You don't need the Chat device: you talk to Claude in its own window, and Claude uses the MidiBakery tools to read and change your Live set.

Deutsche Version: [MCP_SERVER.de.md](MCP_SERVER.de.md) · Back to the [User Guide](USER_GUIDE.md)

**Contents**

- Part A: [In short](#part-a-in-short) – what it is, setup, what you can say
- Part B: [Reference of all 40 tools](#part-b-reference-of-all-38-tools)

---

## Part A: In short

### Chat device or MCP server?

MidiBakery offers two ways to the same abilities:

| | Chat device in Live | MCP server |
|---|---|---|
| Where you type | in Live, in the **MidiBakery Chat** device | in Claude Desktop or Claude Code |
| Which AI | Claude (own API key), LM Studio, Ollama | the AI of the app you are in (e.g. your Claude subscription) |
| Tools | the same 38 | the same 38 |
| Preview cards | in the Chat device, with **Apply** | as a piano roll in the app (if it supports "MCP Apps"), otherwise as text |
| For whom | beginners, everything inside Live | people who already work with Claude, or like the terminal |

Both use the same connection to Live (the Remote Script). The MCP server therefore needs **the Remote Script in Live** ([User Guide, chapter 4](USER_GUIDE.md#4-set-up-in-live)), but no MidiBakery API key and not the Chat device.

### Setup

**Requirements:** MidiBakery is installed ([chapter 3](USER_GUIDE.md#3-install-and-update)), Live is running and the **MidiBakery** Control Surface is on.

The server is the command `midibakery mcp`. Apps start it themselves and talk to it over standard input/output (stdio). You only give them the command.

**Claude Code** (terminal), from the installed app:

```bash
claude mcp add midibakery -- "$HOME/Library/Application Support/MidiBakery/runtime/<version>/midibakery" mcp
```

(`<version>` is the installed version, e.g. `0.3.0`; on Windows the program is in `%LOCALAPPDATA%\Programs\MidiBakery\runtime\<version>\`.) If you have checked out the repository yourself:

```bash
claude mcp add midibakery -- uv --directory <path to the repository> run midibakery mcp
```

**Claude Desktop:** open **Settings > Developer > Edit Config**. The file is `claude_desktop_config.json` (macOS: `~/Library/Application Support/Claude/`, Windows: `%APPDATA%\Claude\`). Add:

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

Quit Claude Desktop completely and start it again. The tools icon in the chat then lists "midibakery" with 40 tools.

**Note on updates:** the installed program lives in a folder named after its version. After a MidiBakery update the path points to the new version: adjust it (Claude Code: `claude mcp remove midibakery`, then add it again).

**As a network service** (for apps that cannot do stdio): `midibakery mcp --http` serves the server on `127.0.0.1:8765` (`--port` changes it). It is reachable from your computer only.

**Test it:** ask Claude "What is in my Live set?" Claude calls `get_session` and describes your set. If that fails: is Live running? Is the Remote Script on? In a terminal, `midibakery ping` checks the connection.

### What you can say

All examples from the [User Guide (chapter 7)](USER_GUIDE.md#7-examples-what-you-can-ask) work the same way. A few typical conversations:

- **Overview:** "Look at my Live set and tell me what is missing." (Claude reads tracks, clips and devices.)
- **Parts:** "Write four bars of techno drums on track 1 and a bassline that follows the kick."
- **Preview first:** "Plan bass, chords and melody for tracks 2 to 4 and show me a preview first." The preview appears as a piano roll (before/after). **When you agree, Claude writes it with `apply_plan`.**
- **A whole song:** "Build a melodic techno track, standard length, from bar 1."
- **Editing:** "Transpose 'Drop Bass' down an octave, second half only."
- **Mixing:** "Add a reverb return and send the melody into it at -12 dB."
- **Reference:** "Use the reference song '…' that I analyzed as the template for the structure."

The difference from the Chat device: Claude Desktop and Claude Code can do **more** than MidiBakery (read files, write text, search the web). For example: "Read the chords from this text file and write them as a clip."

### Safety: what happens before something is deleted?

- **Undo:** every change is a step in Live's undo list (⌘Z / Ctrl+Z). Claude can call the `undo` tool itself.
- **Asking first:** before **deleting tracks or clips** and before **replacing existing notes** (`compose`, `transform_notes`, `apply_plan`) MidiBakery asks. Apps that support questions (most do) show you a confirmation. If you decline, nothing changes and Claude receives `CANCELLED`. A song plan never overwrites existing Arrangement clips.
- **Apps without question support** cannot show the confirmation, so nothing is deleted or replaced right away: Claude gets the question and a `plan_id` back, has to ask you in the chat, and only `apply_plan` then does it. If tracks or clips changed in between, `apply_plan` refuses with `CONFLICT`.
- **Preview before change:** whole songs (`plan_song`) and plans (`plan_changes`) change **nothing** until `apply_plan` is called.
- **What stays on your computer:** the server only talks to Live. The app you are in (Claude) does see what the tools return: track and clip names, notes, tempo.

---

## Part B: Reference of all 40 tools

Conventions Claude knows (from the instructions the server sends along):

- **Counting:** tracks, slots, devices and scenes are **zero-based** (track 1 in Live = `track 0`). Creating or deleting shifts the numbers.
- **Time** in beats (quarter notes); bar *n* starts at beat (n-1) × beats per bar. **Pitch** 60 = C3. Key: `root_note` 0 = C to 11 = B.
- **Session or Arrangement:** clip tools take `slot` (Session) **or** `arrangement_clip` (Arrangement: index in time order or **name**, e.g. "Groove Bass"), never both.
- **Volume and sends** in dB as Live shows them.
- **Racks:** devices inside racks via `chain_path` [chain, device, …]. Return tracks via `return_track` instead of `track`.

The **Kind** column says: **read** (changes nothing), **write**, **asks first** (a question before changing, in apps that support it).

### Reading and overview

| Tool | Kind | What it does |
|---|---|---|
| `get_session` | read | Song settings (tempo, signature, scale, transport) and all tracks with devices and clips. **The first call of every session.** |
| `get_clip` | read | Properties of a clip and, for MIDI clips, **all notes** with `note_id`, probability and velocity deviation. Parameters: `track`, `slot` or `arrangement_clip`. |
| `get_arrangement` | read | Arrangement clips per track (start, end), locators, song length. Optional `track`. |
| `get_reference` | read | Reference songs analyzed by the Reference Analyzer: sections, key, tempo; with `name` also the per-bar lanes (kick, low, mid, high, energy). Without `name`: all, newest first. |
| `get_mixer` | read | Volume, pan, sends, mute/solo, crossfader and routing of tracks, returns and master. `options` lists the valid routing names. |
| `get_device_parameters` | read | Parameters of a device with ranges and displayed values. |
| `get_rack` | read | Chains (devices, mixer, drum pad note) and macros of a rack. |
| `get_drum_pads` | read | Filled pads of a Drum Rack with note and name. |
| `find_browser_items` | read | Finds presets, kits and devices in Live's browser by name (`query`, `category`, `limit`, `loadable_only`). |

### Song and playback

| Tool | Kind | What it does |
|---|---|---|
| `set_song` | write | Tempo, signature (`signature_numerator`/`signature_denominator`), key (`root_note`, `scale_name`, `scale_mode`), metronome, loop (`loop`, `loop_start`, `loop_length`). |
| `transport` | write | `action`: play, stop, continue, stop all session clips or toggle arrangement record; `from_beat` as start. |
| `launch_clip` | write | Fire or stop a session clip. |
| `create_scene` / `fire_scene` | write | Create a scene (`index`, `name`) / launch a scene. |
| `undo` | write | Undo or redo in Live (`action`). |

### Tracks and clips

| Tool | Kind | What it does |
|---|---|---|
| `create_track` | write | Create a MIDI or audio track (`kind`, `index`, `name`). |
| `update_track` | write | Rename, recolor (`color_index`), mute, solo, arm, volume, pan. |
| `delete_track` | **asks first** | Delete a track with all its clips. |
| `create_clip` | write | Create an empty MIDI clip in a session slot (`length`, `name`). |
| `update_clip` | write | Rename, recolor, loop (`looping`, `loop_start`, `loop_end`). |
| `delete_clip` | **asks first** | Delete one clip (Session by `slot`, Arrangement by `arrangement_clip`). |
| `edit_notes` | write (marked "destructive", no question) | Add (`add`), modify (`modify`) or remove (`remove`) notes **as a diff** by `note_id`. Untouched notes keep their data and ids. |
| `write_clip_envelope` | write | Write clip automation (points or shapes) onto an existing clip; device parameters and the track mixer (volume, pan, sends). `clear`, `replace_envelopes`. |
| `edit_arrangement` | write | In the Arrangement: add MIDI clips with notes, copy session clips, **move, swap, delete** clips, set or delete locators. Locators first (transport must be stopped), then the clip actions (one undo step). All or nothing: if an action fails, the clips are undone and the locators put back as they were. A clip never lands on another one. Take lanes: `compose_takes`. |

### Mixer, devices, sounds

| Tool | Kind | What it does |
|---|---|---|
| `update_mixer` | write | Volume (`volume` normalised or `volume_db`), pan, sends, mute, solo, crossfader, routing (`input_routing`, `input_channel`, `output_routing`, `output_channel`). For tracks, returns and master. |
| `create_return_track` | write | Create a return track, optionally with a Live device (`device`). |
| `insert_device` | write | Insert a native Live device (`name`, `index`) on a track, a return (`return_track`) or the master (`master`). |
| `load_browser_item` | write | Load a browser item onto a track (`path`); an instrument or kit replaces the existing instrument. |
| `set_device_parameter` | write | Set one device parameter (`parameter`, `value` or `display`). |
| `update_rack` | write | Set macros, edit chains or add a chain. |
| `run_batch` | **asks first** if it contains a deletion | Several operations **atomically as one undo step** (`ops`, `label`). If one fails, the ones that already ran are undone. |

### Composing and editing

| Tool | Kind | What it does |
|---|---|---|
| `compose` | **asks first** (when replacing) | **One part** as a new MIDI clip in the set's key and time signature. `kind`: `drums` (pattern on the Drum Rack pads), `bass` (follows the chords, locks to or avoids the kick), `chords` (voice-led), `melody` (motifs A A' A B). Key fields: `bars`, `seed`, `style`, `density`, `swing`, `progression`, `chords_from`, `follow_kick`, `counter_to` + `counter_mode` + `counter_register` (melody: counter melody to that clip; modes `fill_the_gaps`, `call_and_response`, `passive_over_active`, `contrasting_rhythm`, `harmonic_notes`, `note_layering`, the figures `dotted_eighth_pulse`, `scale_staircase`, `trance_dotted_eighth_staircase`, `echo_gap_answer`; register `above`, `below`, `same`; a lead in the Arrangement, given by clip name such as `Breakdown Lead`, gets a counter clip at the same bars for every clip of that name, on `track` without `slot`), `if_exists` (`error`, `replace`, `merge`), `preview`. Details in [chapter 8 of the guide](USER_GUIDE.md#8-composing-parts-and-whole-songs). |
| `transform_notes` | **asks first** (when replacing) | Edits a clip **as a diff**: `humanize`, `quantize`, `invert` (diatonic), `arpeggiate`, `variation`, `transpose` (`semitones` chromatic **or** `steps` in key). Only part of it: `half` (`first`/`second`) or `from_bar`/`to_bar` (bars **of the clip**), or `note_ids`. `preview` shows what would happen first. |
| `plan_changes` | read | Plans several steps (drums, bass, chords, melody, transform) **without changing anything**. Later steps see earlier ones (the bass can follow a planned kick; chords are shared). Returns a preview and a `plan_id`. |
| `plan_song` | read | Plans a **whole song** from a genre (`house`, `melodic_techno`, `peak_time_techno`, `drum_and_bass`, `trap`): sections, locators, tracks (missing ones are created), optionally mix, automation, sidechain, FX. Fields: `length` (`radio`/`standard`/`extended`) or `minutes`, `start_bar`, `roles`, `clips`, `create_missing`, `sounds`, `mix`, `fx`, `sidechain`, `counter` (a Counter track with a counter melody to every lead clip), `progression`, `set_tempo`, `reference`, `seed`. Returns a preview and a `plan_id`; **nothing changes until `apply_plan`**. |
| `measure_master` | read | Reads the **Master's loudness** from the MidiBakery Loudness Meter device (last device on the Master): momentary, short-term and integrated LUFS (BS.1770), sample peak, seconds measured, whether Live is playing. `reset=true` restarts integrated and peak. Without the device: an error saying where it is in the browser. |
| `plan_loudness` | read | One **round toward a target loudness**: reads the Loudness Meter's integrated value (at least 30 s since the reset) and plans the Master Limiter's input gain (at most 6 dB per round, +12 dB in total). `target`: a genre or `streaming` (-14 LUFS), or `target_lufs`. Within 0.5 LU it reports `on_target`. `apply_plan` sets the value in one undo step and resets the meter. |
| `plan_master` | read | Plans a **master chain** (EQ Eight low cut, Glue Compressor, Limiter at -1 dB true peak) with the genre's settings (`genre`, optional; `ceiling_db`). A starting point: it hears nothing and makes nothing louder. Returns a preview and a `plan_id`; `apply_plan` writes it in two undo steps. A Master that has a Limiter, EQ Eight or Glue Compressor is left alone. |
| `apply_plan` | **asks first** (when replacing notes) | Writes a plan to Live as **one undo step**, or runs a deletion or replacement that waited for your OK (apps without question support). Fails with `CONFLICT` if a target clip changed since planning; then plan again. A failed write is undone. Plans live in the server's memory (the last 32): after a restart, plan again. |
| `compose_takes` | write | Several **variations** of one part (`kind`: hook, melody, bass, chords, drums; `count`) over the same chords, each on its own **take lane** in the Arrangement (Live 12.2+), to comp in Live. One undo step. |

### Preview (piano roll)

`compose` and `transform_notes` show the change with `preview=true` without writing; `plan_changes` and `plan_song` always do. In apps that understand **MCP Apps** a small **piano roll** (before/after, resource `ui://midibakery/piano-roll.html`) appears. Other apps get a text summary. Writing happens only with `apply_plan`.

### Errors you may see

| Message | Meaning |
|---|---|
| `CANCELLED` | You declined the question; nothing was changed. |
| `CONFLICT` | A target changed since the preview, or a clip would land on another one. Plan again. |
| Connection to Live | Live is not running or the Remote Script is off ([Troubleshooting](USER_GUIDE.md#14-troubleshooting)). |
| Input rejected | A value does not fit (e.g. `slot` **and** `arrangement_clip`, `to_bar` before `from_bar`, chord range under one octave). The message says what to change; Claude usually fixes it itself. |

### For developers

- Commands: `midibakery mcp` (stdio), `midibakery mcp --http [--port 8765]`.
- The server is `midibakery.mcp.server.build_server`; the operations on Live are in the catalog `midibakery.catalog` and reach the Remote Script through the bridge (port 47681, token in `bridge.json`). More in [ARCHITECTURE.md](../ARCHITECTURE.md).
- The chat agent (`midibakery chat` in the terminal, or the Chat device) uses the same tools; they are **not** maintained twice.
