# MidiBakery: Project Recap and Open Tasks

As of 2026-10-19, version 0.3.0, main at `0aeeeea`. Written as a briefing for an outside review.

## 1. What it is

MidiBakery (brand: Klirrwerk) adds AI composition and session control to **Ableton Live 12 Suite**. There are two ways to use it:

- **Chat device in Live** (Max for Live). It works with Anthropic Claude, where the user brings their own API key, or with local models through LM Studio or Ollama (gemma, qwen).
- **MCP server** (stdio) for Claude Desktop and Claude Code. It exposes 40 tools.

The target user is a production beginner. Musical decisions follow sourced conventions (`docs/GENRES.md`, `docs/PATTERNS.md`, `docs/COUNTER_MELODY.md`) instead of guesses.

## 2. Architecture

The design rule is "dumb bridge, smart core" (details: `docs/ARCHITECTURE.md`).

| Part | Path | Role |
|---|---|---|
| Remote Script | `packages/remote_script/MidiBakery` | Loaded by Live. Python 3.11, stdlib only. Registry of ops, main-thread executor, NDJSON over a socket with a token. |
| Core | `packages/core/src/midibakery` | `catalog/`: single source of truth for ops and schemas. `bridge/`: client. `compose/`: composition engine. `agent/`: LLM loop. `api/`: local HTTP API for the devices. `mcp/`: MCP server. Also the CLI, the installer, licensing and updates. |
| M4L devices | `packages/m4l` | Chat (HTML in `jweb` plus a native text field), MIDI Tools (Generator, Transform), Reference Analyzer, Loudness Meter (BS.1770, writes `meter.json`). |
| Packaging | `packaging/` | PyInstaller app, macOS `.pkg`, Windows Inno Setup, signed update manifest. |
| Update and license service | `services/updates` | Cloudflare Worker + R2 + D1 on `updates.klirrwerk.com`. |
| Tests | `tests/` | Unit tests plus contract tests: the real Remote Script against a fake Live Object Model over a real socket. 752 passed, 1 skipped. |

Key mechanisms:

- **Plan/apply.** `plan_*` tools change nothing. They return a preview and a `plan_id`, and `apply_plan` writes the plan as one undo step. A `CONFLICT` error means a target changed after planning. The `PlanStore` lives in process memory, so plans are lost when Live restarts. `compose` writes directly unless `preview=true`.
- **Safety.** Deleting or replacing asks first. Notes are edited as diffs by `note_id`.
- **Local models.** Schemas are compact: only the first sentence of each description is kept. Payload plus system prompt must stay under about 36,000 characters, and that budget is almost used up.
- **Install.** `midibakery install` (or `--link` in development) copies the Remote Script, the devices and the API launcher into the User Library. **Restart Live afterwards.** The chat API process starts with Live, so without a restart it keeps running stale code.

## 3. Feature state

Roadmap phases 1–4 are done (`docs/CONCEPT.md`):

- **Session control:** tracks, clips, notes, mixer and routing, devices, racks, the browser, clip envelopes, the arrangement (add, move, swap and delete clips; locators), scenes, transport, undo, `run_batch`.
- **Composition:**
  - `compose` writes drums, bass, chords and melody.
  - Named patterns come from tutorials.
  - `transform_notes` does humanize, quantize, invert, arpeggiate, variation and transpose.
  - `plan_changes` plans several steps together.
  - `compose_takes` writes variations to take lanes (Live 12.2 or newer).
- **Whole songs:** `plan_song` builds a song from one of five genres: house, melodic_techno, peak_time_techno, drum_and_bass, trap. It can follow an analyzed reference song. It covers sections, locators, tracks by role, mix, automation, sidechain, FX and, new, a counter melody.
- **Mastering:**
  - `plan_master` sets up a chain: EQ Eight, Glue Compressor, and a Limiter at -1 dB true peak.
  - The Loudness Meter device feeds `measure_master`.
  - `plan_loudness` moves the Limiter toward a target loudness in rounds of at most 6 dB.
  - Targets (LUFS): house -8.0, melodic_techno -8.8, peak_time_techno -7.7, drum_and_bass -6.3, trap -8.4, streaming -14.
- **Counter melody** (`compose/counter.py`):
  - Ten modes: six rule modes and four figures.
  - `resolve()` picks the mode and register from how busy the lead is.
  - The counter answers in the lead's phrase rests (silences of one beat or more).
  - The register stays a third clear of the lead, between MIDI notes 36 and 96.
  - With arrangement leads, it writes one counter clip at the same bars as each lead clip, harmonized to the chord clip under it.
- **Productization (phase 5), partly done:**
  - Done: installers for macOS and Windows, and the signed update service (live, 0.3.0 published).
  - Licensing is built (30-day trial, 2 seats, 12 months of updates) but turned **off**.

### Recent PRs (55–69)

| PR | What |
|---|---|
| 55 | Loudness Meter: status line, silence shows no reading |
| 56 | `plan_loudness`: genre loudness targets in rounds |
| 57–59 | Docs: plan_loudness checked in Live; CI skips Markdown-only changes; counter melody analysis |
| 60 | Counter melody generator module; room in the local tool budget |
| 61 | `counter_to` wired into compose, plan_changes and compose_takes |
| 62 | Counter figures: pulse, staircase, trance, echo answer |
| 63 | Counter from the chat: a track alone finds its clip; listed clip names |
| 64 | Counter to arrangement leads: clips at the same bars |
| 65 | A sidechain or FX track is never taken as the lead; a clip name finds its track |
| 66 | Song tracks named by role only ("Lead", not "Peak-Time Techno Lead"); the sidechain track goes first |
| 67 | `compose` gives an empty MIDI track an instrument |
| 68 | The counter follows the lead's phrases (rests, register cap, auto mode); `plan_song` leads leave answer space (2 beats) |
| 69 | `plan_song counter=true`: a counter track in one call; hint "apply_plan first" when a tool uses a track from an unapplied plan |

## 4. How to test

```bash
uv sync
uv run pytest
uv run midibakery install --link
```

After the install, restart Live and choose MidiBakery as the Control Surface. Then:

```bash
uv run midibakery ping
```

## 5. Open tasks

### A. Verify in Live (highest priority)

None of PRs 64–69 has been heard in Live with a local model (gemma) yet. Restart Live first, then check:

1. **Counter melody to arrangement leads.** Clips should appear at the same bars as each lead clip, and they should be audible.
2. **Auto mode.** On sparse Build and Breakdown leads, the counter should answer in call_and_response. On busy Drop leads it should sit as passive_over_active. Its pitch should be around E5–A5, not 96 or higher.
3. **Answer space.** New `plan_song` leads should leave a gap of about 2 beats at phrase ends, and the result should still sound musical.
4. **`plan_song` with `counter=true`.** Check the flow from the chat (gemma): one preview, then `apply_plan`, and the agent stops there.
5. **The "apply_plan first" hint.** It should break the loop where the agent composes onto tracks of an unapplied plan.

### B. Known issues

- The `plan_song` preview lists a new sidechain track at its old (last) index; only `apply_plan` moves it to index 0. The preview and the result disagree.
- Above high leads the counter register is narrow, about 9 semitones under the cap of MIDI 96.
- `compose` drums on an empty track load the 909 Core Kit, but the pattern's notes are not remapped to that kit's pads.
- Loudness Meter: it showed a sample peak of 0.0 dBFS while the rendered file had +1.32 dB. Not yet clear whether the cause is the meter or the measuring method.
- The user's test Set has stray clips from failed chat runs: gemma's bass in track 1 slot 1, a melody in track 2 slot 1, old counter clips, and an empty clip at bar 1. The user should clean these up by hand.

### C. Robustness with small local models

- The genre "techno" is not accepted; only `melodic_techno` and `peak_time_techno` are. An alias or a clearer error would help.
- `set_song` with a minor key: the model forgets `scale_name: "Minor"`. The description now says so, but this is not verified.
- The agent sometimes keeps going after a preview instead of asking or applying.
- The agent takes track indices from plan previews before the plan is applied (partly fixed in PR 69).
- The tool budget for local models is nearly full, so every new tool or field costs room.

### D. Housekeeping

- Leftover worktrees and branches from finished sessions:
  - `claude/counter-melody-analysis-60fe66` and `claude/counter-melody-figures-e77591`, both with worktrees under `.claude/worktrees/`.
  - Remote branches: `arrangement-counter`, `ci-skip-markdown`, `claude/counter-melody-generator-313a1d`, `claude/counter-melody-wiring-ea02ba`.
  - Force-deleting them needs the owner's OK.

### E. Product (phase 5), waiting on the owner

- Sign and notarize the installers. This needs an Apple Developer ID and a Windows signing certificate.
- Set up the GitHub `release` environment and the Cloudflare secrets for automated releases (`services/updates/README.md`).
- Licensing: decide the price, the seat count and the merchant of record (EU VAT). The webhook is not built yet; licenses are issued by hand with `issue_license.py`. `PURCHASE_URL` is not set. Licensing stays off until the owner says so.
- A beta program.

### F. Ideas, not started

- Counter melody:
  - `bass_mimic`: the counter echoes the bass.
  - `timbre_split`: split the counter by sound.
  - A counter inside `compose_takes` for arrangement leads.
- Reference-track workflow. The owner gave three Peak-Time references: Y-Traxx – Mystery Land (Spektre Remix), Katoff – The Signal, and T78 – Nezquik. The goal is to compare sections, entries and density with generated songs. Genre templates should not be tuned by guesswork in the meantime.
- Movement through filters and automation (for example in Peak-Time). The engine cannot write it yet.
- Phase 6: an Extensions SDK adapter, once that SDK is documented.

## 6. Suggested review questions

- Is plan/apply with an in-memory `PlanStore` robust enough? Plans are lost on restart, and only stale-clip conflicts are detected.
- Are 40 tools too many for local models? Would fewer, more general tools work better within the 36,000-character budget?
- Counter melody: are the rule choices in `resolve()` (lead density to mode and register) musically sound?
- Do the contract tests (fake Live Object Model) cover enough of Live's real behavior? See the undo quirks noted in `docs/CONCEPT.md`.
