# MidiBakery – User Guide

MidiBakery builds EDM song sketches in Ableton Live 12 for inspiration: drums, bass, chords and a lead in the Arrangement, after a genre recipe or after a Live Set you like. You then listen, swap sounds and keep what works.

Deutsche Version: [BENUTZERHANDBUCH.md](BENUTZERHANDBUCH.md)

**Contents**

1. [What you get](#1-what-you-get)
2. [Install and update](#2-install-and-update)
3. [Set up in Live](#3-set-up-in-live)
4. [Choose an AI](#4-choose-an-ai)
5. [Build a song](#5-build-a-song)
6. [Songs after your own Sets (Set Importer)](#6-songs-after-your-own-sets-set-importer)
7. [Songs after an audio file (Reference Analyzer)](#7-songs-after-an-audio-file-reference-analyzer)
8. [Changing the result](#8-changing-the-result)
9. [Troubleshooting](#9-troubleshooting)
10. [FAQ](#10-faq)

---

## 1. What you get

| Part | Purpose |
|---|---|
| **Remote Script** "MidiBakery" | the connection to Live (set once in the preferences) |
| **MidiBakery Chat** | where you ask for songs, in plain sentences |
| **MidiBakery Set Importer** | reads Live Sets (`.als`) into references and loops |
| **MidiBakery Reference Analyzer** | estimates the sections, key and tempo of an audio file (e.g. an MP3) |

MidiBakery writes **MIDI notes** and loads sounds from Live's Core Library. It does not create audio or load samples. Every change is a step in Live's undo list.

You need **Ableton Live 12 Suite** (12.3 or newer; Max for Live is part of Suite), macOS or Windows, and an AI: a Claude API key or a local model (chapter 4).

## 2. Install and update

Close Live first. Both installers install for your user account only, without an administrator password.

- **macOS:** `MidiBakery-<version>-macos-arm64.pkg` (Apple Silicon) or `-macos-x64.pkg` (Intel). If macOS refuses to open it (not notarized yet): **System Settings > Privacy & Security > Open Anyway**.
- **Windows:** `MidiBakery-<version>-windows-x64-setup.exe`. If Windows warns: **More info > Run anyway**.

**Updates:** once a day MidiBakery asks `updates.klirrwerk.com` for a newer version (sent: version, operating system, processor type, channel). The Chat device then shows "MidiBakery … is available": **Install** downloads, checks and opens the installer. Restart Live afterwards. Off: `midibakery update --disable`.

**Uninstall:** Windows **Settings > Apps > MidiBakery**. macOS: `~/Library/Application Support/MidiBakery/runtime/<version>/midibakery uninstall` (`--purge` also deletes settings and the stored key). Your music is never touched.

## 3. Set up in Live

1. **Start Live** (restart after every install).
2. **Settings > Link, Tempo & MIDI > Control Surface:** pick **MidiBakery** in a free row. Input and Output stay *None*. Live now also starts the MidiBakery API in the background.
3. In the browser under **User Library** (or search "MidiBakery"):

| Device | Folder |
|---|---|
| MidiBakery Chat | Presets > MIDI Effects > Max MIDI Effect > MidiBakery |
| MidiBakery Set Importer | Presets > MIDI Effects > Max MIDI Effect > MidiBakery |
| MidiBakery Reference Analyzer | Presets > Audio Effects > Max Audio Effect > MidiBakery |

4. Drag **MidiBakery Chat** onto any MIDI track (MIDI passes through unchanged). Type "Hello" into the **input field on the right of the device** and press Enter.

Live passes no keyboard input to the chat window itself: type only in the input field on the right, or press **Pop out** to use the chat in your browser. Every device has an **About** button with the versions of device, API and Remote Script; they should match.

## 4. Choose an AI

The chat's **model menu** lists the Claude models and any local models found. You can switch at any time.

| | Claude | LM Studio or Ollama |
|---|---|---|
| Internet | required | not required |
| Cost | per use, on your Anthropic account | none |
| Privacy | track names, notes and tempo go to Anthropic | everything stays on your computer |
| Quality | very reliable | depends on the model; small ones make more mistakes |

**Claude:** create a key at console.anthropic.com (starts with `sk-ant-`; a claude.ai subscription is not enough). Pick a Claude model, click **Key**, enter the key in the input field on the right and press Enter. It is stored in the macOS Keychain or Windows Credential Manager. `ANTHROPIC_API_KEY` and `midibakery auth set-key` work too.

**LM Studio:** download a model with tool use (Qwen or Gemma, for example), start the local server (tab **Developer**, or `lms server start`) and load the model with enough context:

```bash
lms load <model name> -c 32768
```

**Ollama:** `ollama pull qwen3:8b`, keep Ollama running, pick "Ollama · <model>" in the menu.

Local models get the same tools in a compact form. Name tracks and clips, ask one thing at a time, and press **New** if a conversation goes astray.

## 5. Build a song

Write for example:

- "Build me a house song with a random seed, set the genre's tempo and create new tracks."
- "Again, different." (a new seed: other bass, chords, drum groove and hook)
- "Use seed 42." (the same notes again)
- "Melodic techno, about 6 minutes." / "Drum and bass, radio edit, in A minor."
- "Use the progression i - VI - III - VII." (Roman numerals relate to the Set's key; "Am F C G" works too)

You get a **preview card**: a timeline of the sections. Nothing in Live has changed yet. **Apply** writes the song into the Arrangement after the last clip there; existing clips are never overwritten.

| Genre | Tempo | Sections (standard length) |
|---|---|---|
| **House** | 124 | Intro, Build, Drop, Break, Build 2, Drop 2, Outro |
| **Melodic Techno** | 122 | Intro, Build, Drop, Breakdown, Build 2, Climax, Outro |
| **Peak-Time Techno** | 128 | Intro, Groove, Lift, Peak, Breakdown, Peak 2, Lift 2, Peak 3, Stripped Outro |
| **Drum & Bass** | 174 | Intro, Build, Drop, Breakdown, Build 2, Drop 2, Outro |
| **Trap** | 145 | Intro, Build, Drop, Verse, Build 2, Drop 2, Outro |

**Length:** radio, standard, extended (DJ-friendly) or a time in minutes.

What MidiBakery does on Apply:

- **Tracks:** it uses tracks named like Drums (or with a Drum Rack), Bass/Sub/808, Chords/Pad/Keys and Lead/Melody/Synth. Missing ones are created with a kit and presets from the Core Library. Name your tracks this way to keep your own sounds.
- **Tempo:** the genre's tempo (or the reference's), with a little spread per seed.
- **Notes:** drums with ghost notes and fills, a bass that follows the chords, a hook that develops, dynamics that follow each section's energy. The seed picks the bass pattern, the chord loop and the drum groove.
- **Arrangement:** locators at the sections, a reverb and a delay return, sidechain pumping on bass and pads, risers before and impacts on the drops.

Apply may take a few undo steps (tracks, returns, clips): press **Undo** until everything is gone.

**Limits:** 4/4 only. No samples, breaks or vocals. A recipe sounds genre-typical; it becomes yours through listening, swapping sounds and arranging.

## 6. Songs after your own Sets (Set Importer)

Free example Live Sets and your own projects are the best inspiration. The **Set Importer** reads `.als` files exactly (notes and clips, no audio analysis) and stores everything on your computer.

1. Drag **MidiBakery Set Importer** onto any MIDI track.
2. Press **Folder...** (many Sets; `Backup` folders are skipped) or **Set...** (one file). The Sets appear with tempo and key.
3. Click a Set to see its sections and which roles play where. Click the genre chip to set its genre. Untick what you don't want and press **Import**.
4. The **Library** tab lists everything imported with its loops; **Delete** removes a Set.

An import gives you:

- **A reference:** the Set's sections, tempo, key and line-up (which roles play in each section).
- **Loops:** bass, lead and drum figures the Set repeats, and its chord progression, named like `my_soundasapound_bass_1`. They follow your song's key. The Set's notes are never copied as a whole.

Then ask:

- "Build a song after 'Sound as a Pound'." (structure, tempo and the Set's own loops; without a genre MidiBakery uses the one you set in the importer)
- "After 'Phantom', but with the bass of 'Sound as a Pound'." (`loops_from`: drums, bass, lead or chords from another Set)
- "A house song with my own loops." (`my_loops`: the seed draws drums, bass, lead and chords from your imported Sets; "Again, different" draws another mix)
- "Which Sets have I imported?"

Roles a Set never plays are filled in from the genre. Chord loops of Sets you tagged with a genre also join that genre's progressions.

**Limits:** 4/4 Sets only. Drums played as audio give no drum loops. Sections are an estimate from the clips: check them in the Library view.

## 7. Songs after an audio file (Reference Analyzer)

For a song you only have as audio (MP3, WAV): the Analyzer estimates sections, key, tempo and per-bar energy. It is a rough guide, not ground truth.

1. Drag the song onto an **audio track** in the **Arrangement**.
2. Drag **MidiBakery Reference Analyzer** onto that track and press **Analyze**. Everything runs inside Live.
3. You see the sections, key, tempo and four lanes: **Kick, Lows, Mids, Hats**.

On Windows only **WAV** works. An unwarped clip is warped onto your grid automatically; if that fails, warp it by hand (1.1.1 on the first beat) and analyze again.

- **Genre** guides section names and phrase lengths.
- **Sensitivity** (Kick, Lows, Mids, Hats): higher splits the song more finely; **Lock** moves all four together.
- **Set Locators** / **Remove Locators** put the sections into the Arrangement (transport stopped).

Then: "Build me a peak-time techno song after the reference '<part of the name>'." Only the structure is taken, not the sound.

## 8. Changing the result

- "Rewrite the bass in 'Drop 2'." (the notes of that Arrangement clip are replaced, after a question)
- "Make 8 bars of techno drums on track 1." / "A bassline that locks to the kick." (a new Session clip)
- "Move 'Break Chords' to bar 41." / "Swap 'Intro Bass' and 'Drop Bass'." / "Delete 'Outro Hats'."
- "Set a marker 'Drop' at bar 33." (transport stopped)
- "Set the tempo to 126." / "Play." / "Stop." / "Undo that."

Fine edits, mixing and sound design are faster in Live itself.

## 9. Troubleshooting

**"Connecting…" stays or the dot is red:** check the Control Surface (chapter 3), run `midibakery ping` in a terminal, remove and re-add the Chat device, restart Live.

**NO_API_KEY / INVALID_KEY:** press **Key** and enter a valid Claude key.

**"Cannot reach LM Studio / Ollama":** start the server (`lms server start`, `ollama serve`). Other host or port: `LMSTUDIO_HOST`, `OLLAMA_HOST`.

**"… too small a context":** reload the model with `lms load <model> -c 32768`.

**The AI says "done" but nothing changed:** a small local model. Every tool call shows in the chat; without one nothing happened. Ask "Do it now with the tools", or use a bigger model or Claude.

**"Stopped: … failed 3 times" / "Stopped after 24 tool rounds":** rephrase, make the request smaller, or use a bigger model.

**CONFLICT:** something changed between preview and Apply. Ask again.

**"plan_song needs 4/4":** set the time signature to 4/4.

**LICENSE_REQUIRED:** only when the license check is on: **Start trial** or **Enter key** in the chat.

**Logs:** macOS `~/Library/Application Support/MidiBakery/`, Windows `%APPDATA%\MidiBakery\`: `api.log` (every message and tool call), `device-chat.log`, `device-importer.log`, `device-reference.log`; Live's `Log.txt` for the Remote Script. **Copy** in the chat copies the whole conversation for a bug report.

## 10. FAQ

**Does MidiBakery change my project without asking?** Only on request; a song comes as a preview first, deleting and replacing ask first, everything is undoable.

**What does it cost?** Claude: API use on your Anthropic account. Local models: nothing. The MidiBakery license check is **off** in this version.

**Which data leaves my computer?** With Claude: what the AI reads (track and clip names, notes, tempo, key). With local models: nothing. The update check sends version, OS, processor and channel.

**Can the AI hear my music?** No. It works with notes. Decide with your ears.

**Claude Desktop or Claude Code?** The MCP server offers the same 12 tools there: see [MCP_SERVER.md](MCP_SERVER.md).
