# MidiBakery – Concept: AI control and composition for Ableton Live 12 Suite

MidiBakery is a tool by Klirrwerk.

## Context

`ableton-mcp` (fork jpoindexter) shows the idea: an LLM controls Ableton Live through an MCP server and a Remote Script. But the implementation is not viable for a product:
- LOM reads run outside Live's main thread.
- There is no message framing; errors are reported as `success`.
- Three tool lists are maintained by hand (MCP, REST, M4L), and the execution module in the M4L device is a stub.
- The old notes API destroys note IDs and undo steps.
- There are no events, and the "AI helpers" are plain random generators.

MidiBakery takes only the idea and rebuilds it: as a **commercial product**, in **Python**, for **Claude via MCP, chat directly in Live, and local LLMs (LM Studio, Ollama)**, with a focus on **composition/MIDI and session remote control**.

Starting point on your machine: Live **12.4.6 Suite** (Python 3.11 in the Remote Script host, `ableton.v3` available) and Max **9.2.0**.

Key findings from the research:
- **Live 12 LOM:**
  - `Song.scale_name`, `scale_mode`, `scale_intervals` and `root_note`, plus `tuning_system`
  - `Track.create_midi_clip` (12.1.10)
  - Take lanes via the API (12.2)
  - Clip automation in the Arrangement: Live creates envelopes only on Session clips. An `add_clip` with `envelopes` is therefore created in a free slot and copied into the Arrangement. The values are absolute (measured in Live 12.4.6).
  - `clip.envelope` (tool `write_clip_envelope`) writes envelopes on existing clips. Targets are device parameters (also in racks) and the track's mixer (Volume, Pan, Send A …). Values go in as 0–1 or in Live's display units (Hz, s, dB, %); the conversion reads Live's own display as a table. The Remote Script turns shapes (ramp, exp, log, sine, triangle, saw, square) into points. Live 12.4.6 does not expose envelopes of Arrangement clips to any script: `automation_envelope` returns nothing there, and creating one is not possible. An Arrangement clip is therefore rebuilt via a Session slot, with its notes and only the envelopes passed in. Live also does not reveal whether it has any (`has_envelopes` is always False there), so the op always requires `replace_envelopes=true` for Arrangement clips. Live 12.4.6 also has no `create_event`: envelopes are created as sixteenth-note steps (`insert_step`).
  - `Track.insert_device` / `RackDevice.insert_chain` / `DrumChain.in_note` (12.3): native devices can be inserted without the browser
  - `SimplerDevice.replace_sample` (12.4)
  - `Application.browser.load_item`: loads kits and presets like a double-click on the selected track. An instrument or kit replaces the instrument, an effect is appended, and each load is its own undo step. In Live 12.4.6, Live crashed when a freshly loaded rack was replaced right away. `browser.load` therefore waits until the chain is stable and leaves at least 1 s between two loads. `plan_song` loads the genre's kit and presets from the Core Library onto new tracks and places the drum notes on the kit's pads.
  - A batch that inserts devices and then sets their parameters is two undo steps in Live 12.4; separate batches are one each. `plan_master` therefore writes two batches.
  - In Live 12.4.6, `Song.create_return_track` closes the open undo step: whatever a batch changes after the last new return is a second step. `plan_song` counts this when rolling back.
  - Notes API with IDs (`get_notes_extended`, `add_new_notes`, `apply_note_modifications`), plus Probability and Velocity Deviation
- **Max 9.1+:**
  - Node for Max uses Node 22; the `v8` and `v8ui` objects run ES6+.
  - MIDI Tools (`live.miditool.in/out`, Generator/Transformation) get context with scale, grid and seed.
  - Node itself has no direct access to the Live API; that only works via `v8`.
- **Ableton Extensions SDK** (JS/TS, beta since 12.4.5): an official new path. The docs are only accessible with beta sign-up, so it is planned here as a future adapter and not as the base.
- **MCP spec 2026-07-28:**
  - The protocol is stateless; there are `server/discover` and `subscriptions/listen`.
  - Instead of elicitation there is `input_required`; long jobs run via the Tasks extension.
  - Sampling, Roots and Logging are deprecated.
  - MCP Apps (`ui://`) allow custom UIs, such as a piano roll preview.
  - Python SDK v2 is called `MCPServer` (formerly `FastMCP`).
- **Tool count:** With more than 30–50 tools, the hit rate drops. A few coarse tools, resources and plan/apply are better.
- **Competition:**
  - Producer Pal (M4L, GPL, free)
  - ulm0/ableton-live-mcp (Extensions SDK)
  - AbletonOSC derivatives
  - SMYLZ Producer (commercial, installed on your machine)
  - Anthropic's official Ableton connector only provides docs and does not control Live.
  - **Differentiation:** musically intelligent composition engine, clean undo/diff behavior, MIDI Tools directly in the Clip View, usable locally and offline.

## Implementation options (overview)

| | A: Remote Script + Python core + M4L frontends (**recommended**) | B: Extensions SDK (TS) | C: Pure M4L (Node + v8) |
|---|---|---|---|
| Language | Python (core), Python 3.11 (bridge), JS only for the UI | TypeScript | JavaScript |
| LOM coverage | complete, incl. listeners | broad according to Ableton, details unclear (beta) | complete via `v8`, bridge to Node required |
| Persistence/headless | runs permanently, without UI | execution model unclear | only while the device is in the set |
| Composition in Python (music21, numpy …) | yes | no | no |
| Commercial risks | low, established path | beta, SDK license terms unclear | low, but Producer Pal is a strong free competitor |

**Recommendation: A.** The bridge gets its own interface (`LiveBackend`) so that B can be added later as a second adapter.

## Recommended architecture (option A)

```
Claude Desktop/Code ─MCP (stdio | Streamable HTTP)─┐
Ollama / Anthropic API ◄── agent loop ─────────────┤
M4L chat device (v8ui + Node) ─WebSocket───────────┤
M4L MIDI Tools (Generator/Transform) ─WebSocket────┤
                                                    ▼
                        midibakery-core (Python 3.12+, uv)
                         ├─ catalog/  single source of truth (Pydantic schemas of all ops)
                         ├─ bridge/   async client, NDJSON + request IDs, events
                         ├─ compose/  music engine (theory, generators, transformations)
                         ├─ agent/    provider abstraction (Anthropic, Ollama), tool loop
                         ├─ mcp/      MCP server (spec 2026-07-28, Python SDK v2)
                         └─ api/      local HTTP/WebSocket server for M4L
                                                    │ TCP 127.0.0.1, token auth, NDJSON
                                                    ▼
                  MidiBakery Remote Script (ableton.v3, no third-party dependencies)
                         ├─ op registry (decorator, schema-validated)
                         ├─ MainThreadExecutor (queue → schedule_message)
                         ├─ listeners → event stream
                         └─ undo bracket (begin/end_undo_step)
```

### Guiding principle: "dumb bridge, smart core"
- **Remote Script:**
  - As small as possible, standard library only; it runs in Live's Python 3.11.
  - It executes atomic LOM ops, validates them and reports structured errors (`code`, `message`, `details`).
  - **All** LOM access runs on the main thread: socket thread → queue → `schedule_message(0, drain)`.
  - Results return via a future with a request ID; a timeout aborts the op instead of silently running it later.
- **Batch op:** Several ops run in **one** main-thread tick and as **one** undo step.
- **Framing:** NDJSON with `{"id","op","params"}` and `{"id","ok","result"|"error"}`, plus events as `{"event","data"}`.
- **Security:** The bridge binds only to loopback. At startup it generates a token and stores it in `~/Library/Application Support/MidiBakery/`; the core reads it from there.

### Single source of truth: `catalog/`
- Each op is defined once: name, Pydantic parameters, result schema, `read_only` / `destructive`, timeout class and category.
- From this, the following is generated:
  1. the op manifest of the Remote Script registry (JSON, which the bridge validates against)
  2. MCP tools incl. `outputSchema` and annotations
  3. tool definitions for Ollama and the Anthropic API
  4. the TypeScript types for the M4L clients
- A CI check ensures that the bridge registry and the catalog match.

### Tool design for LLMs (~25–35 tools instead of 200)
- **Resources / read tools:**
  - `session_overview` (tempo, scale, tracks, scenes, selection)
  - `track_detail`, `clip_notes`, `device_params`, `browser_search`
  - Data is fetched compactly; pagination and field filters are optional.
- **Coarse write tools:**
  - `edit_tracks`, `edit_clips`, `edit_notes` (diff via note IDs: add/modify/remove)
  - `devices` (insert/param/rack), `transport`, `scenes`, `mixer`, `arrangement`
- **Composition tools:**
  - `compose` (kind drums, bass, chords or melody; four separate tools until part B of the review), `transform_notes` (humanize, quantize, invert, arpeggiate, variation)
  - All are scale- and context-aware and reproducible via a seed.
- **Plan/apply:**
  - `plan_changes` returns a preview as a diff (with MCP Apps also as a piano roll).
  - `apply_plan` executes the plan as one undo step.
  - Destructive ops require confirmation via `input_required`.
- **Escape hatch:** `lom_call` (path / property / function) for power users. Off by default, can be enabled in the settings.

### Composition engine `compose/` (core differentiation)
- **Music theory:**
  - Scales come from `Song.scale_intervals` instead of hardcoded lists.
  - Chords, functional harmony, voice leading and rhythm grids (incl. time signature and swing).
- **Drum mapping:** Drum Rack pads are detected by name and `DrumChain.in_note`, not by fixed GM notes.
- **Generators:**
  - rule-based and context-aware (existing clips as context: detect chords, bass follows kick)
  - seed-based
  - Probability and Velocity Deviation are used.
- **Optional ML stage:** small local models, e.g. for groove extraction. Only from phase 3 on.
- **Libraries:** pure Python or numpy first. The licenses of music21 (BSD) and others are checked.

### Frontends in Live (Max 9)
1. **MidiBakery Chat (audio/MIDI effect AMXD):**
   - `v8ui` as the chat UI, Node for Max as WebSocket client to the core.
   - The agent logic runs in the core, not in the device.
   - The device shows plan diffs and has an Apply/Undo button.
2. **MidiBakery MIDI Tools (Generator + Transformation):**
   - `live.miditool.in` → Node → core `compose/*` → `live.miditool.out`.
   - This makes AI generators usable directly in the Clip View, and they get scale, grid and seed from Live.
   - Same code as the MCP composition tools.

### Agent / LLM providers (`agent/`)
- Provider interface with three implementations: **Anthropic** (default `claude-sonnet-5-5`, selectable `claude-opus-5-5` and `claude-haiku-5-5`), **LM Studio** (OpenAI-compatible server) and **Ollama** (both local).
- The tool loop uses the same catalog tools. Local models get the same tools in compact mode (short schemas and results); a reduced tool set for models with a small context is optional.
- During implementation, the `claude-api` skill reference is used for SDK usage.

## Commercial aspects
- **License:** proprietary. No code from ableton-mcp (MIT) and **none from Producer Pal (GPL-3.0)**, only ideas. Dependencies only under permissive licenses (license scan in CI).
- **Trademark:** only "for Ableton Live", no Ableton logo; no claims that the product officially comes from Ableton.
- **Distribution:**
  - signed and notarized macOS installer (`.pkg`), later also Windows.
  - The installer copies the Remote Script into `User Library/Remote Scripts`, the AMXDs into the User Library, and the core as a bundled app (e.g. PyInstaller or `uv` bundle) with a menu bar status.
- **Licensing:**
  - License key with an offline grace period.
  - The license server is a separate topic for later; Cloudflare Workers are one possible option for it.
- **Version matrix:**
  - At least Live 12.3, because of `insert_device`; feature flags detect what each Live version can do.
  - Testing is done against 12.3, 12.4.x and Max 9.1/9.2.
- **Telemetry:** opt-in only. The core's crash logs are stored locally.

## Project structure (original plan; current layout: README)
```
MidiBakery/
├─ pyproject.toml / uv workspace
├─ packages/core/src/midibakery/{catalog,bridge,compose,agent,mcp,api}/
├─ packages/remote_script/MidiBakery/  (__init__.py, registry.py, executor.py, ops/*.py, listeners.py)
├─ packages/m4l/{chat,miditools}/      (.maxpat sources, v8/Node JS, build script → .amxd)
├─ tools/codegen/                      (catalog → manifest, MCP, TS types)
├─ tests/{unit,contract,live_smoke}/
└─ installer/
```
`ableton-mcp/` stays only as a reference and is not included; add it to `.gitignore` or move it out.

## Roadmap
1. **Foundation (MVP core):**
   - Catalog plus codegen.
   - Remote Script with registry, MainThreadExecutor, NDJSON and token.
   - ~15 ops: read the session, create tracks/clips, notes via diff, tempo/transport, insert device.
   - Core bridge client.
   - MCP server over stdio for Claude Desktop/Code.
2. **Composition:** `compose/` with drums, bass, chords, melody and transform; plan/apply with undo; MCP Apps preview.
3. **Live frontends:** chat AMXD and MIDI Tools AMXDs, agent loop with Anthropic and Ollama.
4. **Coverage & events:** mixer/routing, racks, Arrangement, take lanes, listener events via `subscriptions/listen`.
   - Order, one PR each: events → mixer/routing → racks → Arrangement → take lanes.
   - Events: at first only a status line in the chat device (transport, tempo, scale, what is playing).
   - Arrangement: the engine builds whole song structures (intro, build, drop, break …), with its own structure templates per genre.
   - Take lanes: `compose_takes` places several variations of a part (hook, melody, bass, chords, drums) over the same chords in separate take lanes, so you can comp in Live. One undo removes all takes. This needs Live 12.2 or newer; in Live the lanes are only visible via "Show Take Lanes" (⌘⌥U).
5. **Productization:** installer, signing, license, docs, beta program.
6. **Optional:** Extensions SDK adapter, as soon as the SDK docs are accessible and stable.

## Implementation status (October 2026, version 0.3.0)

The roadmap is done except for item 5; the plan above stays as the rationale, and the implementation differs from it in a few places.

| Roadmap | Status |
|---|---|
| 1 Foundation | done: catalog, Remote Script, bridge client, MCP server over stdio. The catalog has 40 MCP tools instead of the planned 25–35; for local models the budget for schemas is almost used up (see ARCHITECTURE.md) |
| 2 Composition | done: `compose` (drums, bass, chords, melody), `transform_notes` (humanize, quantize, invert, arpeggiate, variation, transpose; also on parts of a clip), `plan_changes` and `apply_plan` with preview, MCP Apps piano roll |
| 3 Frontends | done: chat device with Anthropic, LM Studio and Ollama; Generator and Transform as MIDI Tools; plus the Reference Analyzer device |
| 4 Coverage | done: events and status line, mixer and routing, racks, Arrangement (clips also by name, move, swap, locators), whole songs from genre templates (`plan_song`, five genres, optionally based on an analyzed reference song), take lanes (`compose_takes`) |
| 5 Productization | partly: installers for macOS (`.pkg`) and Windows (Inno Setup) and the signed update service on Cloudflare are in place. **Open:** signing and notarization of the installers (the certificates are missing), switching on the license check (built, but switched off; price, number of machines and payment processor are still open) and the beta program. The user guide is in `docs/user/` |
| 6 Optional | not started |

Deviations from the plan:
- The license server is no longer a "topic for later": it runs as part of the update service (`services/updates`).
- The chat UI is an HTML page in `jweb` (not `v8ui`); keyboard input goes into a native Max text field, because Live does not pass keys to `jweb`.
- The device shows plan diffs with Apply and an Undo button; take lanes need Live 12.2 or newer.
- The MIDI Tools talk to the API over HTTP, not over WebSocket.
- The Remote Script does not use `ableton.v3`. It is a plain control surface object with the standard library only.
- There is no `schedule_message` executor. Live calls `update_display()` about every 100 ms, and that tick runs the queued jobs within a 30 ms budget. Ops that need several ticks (locators, song position) continue there as generators.
- There are no LOM listeners. Events come from polling: `update_display()` reads a compact state about every 200 ms and sends it when it changes (`state.py`).
- The catalog generates the Remote Script's manifest (`midibakery manifest`, checked in CI) and the MCP and agent tool schemas. No TypeScript types are generated: the devices talk to the API, not to the catalog.
- There is no `LiveBackend` interface. The core talks to the Remote Script through `BridgeClient`, and an Extensions SDK adapter (phase 6) would start there.
- The `lom_call` escape hatch was not built.
- The dependency license scan in CI and the menu bar status of the app were not built.

## Verification
- **Unit:** `compose/` (deterministic via seed, theory checks), catalog schemas, codegen snapshots (`uv run pytest`).
- **Contract:** A fake LOM (Python 3.11) loads the real Remote Script, and every catalog op is tested against its schema and error codes. This closes the gap in ableton-mcp, where the Remote Script was untested.
- **Live smoke:** A script connects to the running Live 12.4.6 and runs ops in a test set: create → check → undo → check.
- **MCP:** Acceptance with MCP Inspector and Claude Code (`claude mcp add midibakery …`), with prompts like "4-bar deep house pattern in the session scale".
- **M4L:** Load the AMXDs in Live and test chat and MIDI Tool apply in the Clip View.
- **Stability:** 1,000 ops in a batch without a crash, no LOM calls outside the main thread (assertion in the executor).

## First implementation step after approval
Phase 1: repo scaffold (uv workspace), catalog with ~15 ops, Remote Script with `ableton.v3`, bridge client and MCP server over stdio. End-to-end test: Claude Code creates a MIDI clip in the session scale.
