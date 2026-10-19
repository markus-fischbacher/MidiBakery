# MidiBakery – User Guide

For musicians who use Ableton Live 12 and are new to music production. You don't need to program anything. Everything here can be done in Live and in MidiBakery's chat.

Deutsche Version (ausführlicher): [BENUTZERHANDBUCH.md](BENUTZERHANDBUCH.md)

**Contents**

1. [What is MidiBakery?](#1-what-is-midibakery)
2. [What you need](#2-what-you-need)
3. [Install and update](#3-install-and-update)
4. [Set up in Live](#4-set-up-in-live)
5. [Choose an AI](#5-choose-an-ai)
6. [The chat: first steps](#6-the-chat-first-steps)
7. [Examples: what you can ask](#7-examples-what-you-can-ask)
8. [Composing parts and whole songs](#8-composing-parts-and-whole-songs)
9. [Editing clips](#9-editing-clips)
10. [The Arrangement](#10-the-arrangement)
11. [The Reference Analyzer](#11-the-reference-analyzer)
12. [Mixing and sounds](#12-mixing-and-sounds)
13. [Generator and Transform without the chat](#13-generator-and-transform-without-the-chat)
14. [Troubleshooting](#14-troubleshooting)
15. [FAQ](#15-faq)
16. [Using MidiBakery from Claude Desktop or Claude Code](#16-using-midibakery-from-claude-desktop-or-claude-code)

---

## 1. What is MidiBakery?

MidiBakery is an AI assistant that lives **inside** Ableton Live 12. You write what you want in plain sentences, e.g. "Make me four bars of deep house drums on track 1", and it puts the notes straight into your Live set. It can:

- **Compose parts:** drums, bass, chords and melodies, fitting the key and time signature of your set.
- **Build whole songs:** intro, build, drop, break and outro in the Arrangement, from recipes for five genres (house, melodic techno, peak-time techno, drum & bass, trap).
- **Change existing clips:** vary, transpose, humanize, change only the second half.
- **Control Live:** tracks, clips, tempo, mixer, effects, automation.
- **Take a reference song apart:** the *Reference Analyzer* device shows how a song is built, and MidiBakery can build your song after it.

MidiBakery creates **MIDI notes** (and loads sounds from Live's library). It does not create audio or load samples of its own.

Everything MidiBakery does is a step in Live's undo list. You can always take it back.

You see four parts in Live:

| Part | Purpose |
|---|---|
| **Remote Script** "MidiBakery" | the connection to Live (invisible, set once) |
| **MidiBakery Chat** | the chat device: this is where you talk to the AI |
| **MidiBakery Generator** and **MidiBakery Transform** | two tools in the clip view, without AI and without chat |
| **MidiBakery Reference Analyzer** | analyzes a reference song |
| **MidiBakery Loudness Meter** | measures the Master's loudness (LUFS) |

## 2. What you need

- **Ableton Live 12 Suite** (Live 12.3 or newer; take lanes need 12.2 or newer). The Suite includes **Max for Live**, which the devices need.
- **macOS** (Apple Silicon or Intel) or **Windows**.
- **An AI** ([chapter 5](#5-choose-an-ai)): either a key for the Claude API (internet needed) or a local model on your computer (no internet, no cost per question).
- The MidiBakery installer (chapter 3).

## 3. Install and update

Both installers install for your user account only. You don't need an administrator password. Before you start: **close Live.**

### macOS

1. Download `MidiBakery-<version>-macos-arm64.pkg` (Apple Silicon: all Macs from 2020 with M1 or newer) or `MidiBakery-<version>-macos-x64.pkg` (Intel Macs).
2. Double-click it and follow the installer.
3. **If macOS refuses to open it** ("cannot be opened because it is from an unidentified developer"): the installers are not yet notarized by Apple. That is normal for this version. Open **System Settings > Privacy & Security**, scroll down and click **Open Anyway** next to the message about MidiBakery. Alternatively: right-click the file > **Open**.
4. At the end the installer tells you what to do next (chapter 4).

The program goes to `~/Library/Application Support/MidiBakery/`, the Remote Script and devices to your Live **User Library**.

### Windows

1. Download `MidiBakery-<version>-windows-x64-setup.exe`.
2. Double-click and follow the setup.
3. **If Windows warns you** ("Windows protected your PC"): the Windows setup is not signed yet either. Click **More info > Run anyway**.

The program goes to `%LOCALAPPDATA%\Programs\MidiBakery\`. You can remove it later like any program under **Settings > Apps**.

### Updating

Once a day MidiBakery asks `updates.klirrwerk.com` whether a newer version exists. Only the version, operating system, processor type and update channel are sent.

1. If there is an update, the **Chat device** shows a line "MidiBakery … is available" at the top.
2. Click **Install**. MidiBakery downloads the installer, checks its signature and opens it. **Later** hides the notice.
3. Follow the installer. It updates the existing installation and keeps your settings.
4. **Restart Live.**

To switch the update check off: `midibakery update --disable` in a terminal (back on: `--enable`). To only check without installing: `midibakery update --check`. The program is at `~/Library/Application Support/MidiBakery/runtime/<version>/midibakery` (macOS) or `%LOCALAPPDATA%\Programs\MidiBakery\runtime\<version>\` (Windows).

### Uninstalling

Windows: **Settings > Apps > MidiBakery**. macOS: in a terminal, `~/Library/Application Support/MidiBakery/runtime/<version>/midibakery uninstall` (with `--purge` it also deletes settings and the stored Claude key). It removes exactly what the installation wrote, and nothing of your music.

## 4. Set up in Live

### Step 1: Turn on the Remote Script (first time only)

1. **Start Live** (always restart after installing).
2. Open the preferences: macOS **Live > Settings** (⌘,), Windows **Options > Preferences** (Ctrl+,).
3. Choose **Link, Tempo & MIDI**.
4. Under **Control Surface**, pick **MidiBakery** in a free row. Input and Output can stay on *None*.

This also makes Live start the MidiBakery API (the "brain" in the background). It runs as long as Live runs.

### Step 2: Find the devices

The devices are in the **User Library** in Live's browser (left, or search for "MidiBakery"):

| Device | Folder | Type |
|---|---|---|
| MidiBakery Chat | Presets > MIDI Effects > Max MIDI Effect > MidiBakery | MIDI effect |
| MidiBakery Reference Analyzer | Presets > Audio Effects > Max Audio Effect > MidiBakery | audio effect |
| MidiBakery Loudness Meter | Presets > Audio Effects > Max Audio Effect > MidiBakery | audio effect |
| MidiBakery Generator | MIDI Tools > Max Generators | MIDI Tool |
| MidiBakery Transform | MIDI Tools > Max Transformations | MIDI Tool |

### Step 3: Put the Chat device on a track

1. Create a **MIDI track** (⌘⇧T / Ctrl+Shift+T).
2. Drag **MidiBakery Chat** onto it. A chat window appears in the device view. MIDI notes on that track pass through unchanged; the device doesn't interfere.
3. A status line at the top shows the connection. If "Connecting…" stays for long, see [chapter 14](#14-troubleshooting).

You need the device only **once** per set, on any MIDI track. It's nice to keep a track named "Chat" for it.

### Step 4: Test

Type "Hello" into the input field on the right of the device and press Enter. If the AI answers, you're ready. If a key is requested: on to chapter 5.

Every device has an **About** button showing the versions of device, API and Remote Script. They should match.

## 5. Choose an AI

The Chat device has a **model menu** with the Claude models and any local models MidiBakery found. You can switch at any time.

| | Claude (Anthropic) | Local models (LM Studio or Ollama) |
|---|---|---|
| Internet | required | not required |
| Cost | per use, on your Anthropic account | none, but your computer works |
| Privacy | track names, notes and tempo of your set go to Anthropic | everything stays on your computer |
| Quality | very reliable | depends on model and computer; small models make more mistakes |
| Setup | enter an API key | install a program, load a model |

### Option A: Claude with your own API key

By default MidiBakery uses **Claude Sonnet 5.5**. The menu also offers Claude Opus 5.5 and Claude Haiku 5.5.

1. Create an account at Anthropic (console.anthropic.com), add a payment method and create a key under **API Keys**. It starts with `sk-ant-`. A Claude subscription for claude.ai is something else and is not enough: the API is billed separately.
2. Pick a Claude model in the menu. A **Key** button appears at the top right of the chat.
3. Click **Key**. Then enter the key **in the input field on the right of the device** (not in the chat window) and press Enter. The key isn't displayed and never sent to a model. The browser window (*Pop out*) has its own field.
4. MidiBakery checks the key with Anthropic and stores it in the **macOS Keychain** (service "MidiBakery") or the **Windows Credential Manager**. The button then reads "Key ✓".
5. To remove it: **Key** > **Remove**.

MidiBakery also knows the environment variable `ANTHROPIC_API_KEY` and a profile from `ant auth login`; in a terminal, `midibakery auth set-key` works too.

### Option B: Local models with LM Studio

1. Install **LM Studio** (lmstudio.ai) and download a model that supports tool use. Qwen or Gemma models are examples. Try which one runs well on your machine.
2. Start the **local server**: in LM Studio, tab **Developer**, "Start Server", or `lms server start` in a terminal. MidiBakery expects it on `127.0.0.1:1234` (the default).
3. **Important: load the model with a large context.** MidiBakery sends the model the description of all its tools. That takes a lot of room ("context"). LM Studio loads models with a small default that isn't enough. Load it like this:

   ```bash
   lms load <model name> -c 32768
   ```

   For example `lms load qwen/qwen3-8b -c 32768`. `lms ls` shows the exact model name. In the LM Studio interface the same is **My Models** > the model's settings > **Context Length** = at least 32768.
   If the context is too small, the chat tells you in an error ("… too small a context for MidiBakery's tools. Load it with a context length of at least 32768 …"). Reload the model and send your message again.
4. Open the chat's **model menu**: it now lists "LM Studio · <model name>". Pick it.

### Option C: Local models with Ollama

1. Install **Ollama** (ollama.com) and pull a model, e.g. `ollama pull qwen3:8b`. Ollama must be running (`ollama serve` or the Ollama app); MidiBakery expects it on `127.0.0.1:11434`.
2. Pick "Ollama · <model name>" in the model menu.
3. If the model works imprecisely, Ollama's default context may be too small. Raise it in Ollama.

### Tips for local models

- Local models get **all** tools, in a compact form. They make mistakes more easily than Claude. You notice when the model claims something but nothing happened in Live. MidiBakery often notices this itself and pushes back.
- Name the track and section ("Drop Bass"). Short, clear requests work better than long ones.
- One task at a time.
- For big requests like whole songs, a larger model (or Claude) is more reliable.
- If nothing helps: press **New** (forgets the conversation) and rephrase.

## 6. The chat: first steps

The Chat device window:

| Element | Meaning |
|---|---|
| **Dot and status line** (top) | connection to the API; next to it what Live is doing: tempo, key, what's playing |
| **Model menu** | which AI answers |
| **Stop** | cancels the running answer |
| **Undo** | takes back the last change in Live (same as ⌘Z in Live) |
| **Key** | Claude key (Claude models only) |
| **Copy** | copies the whole conversation (thoughts, tool calls, answers) to the clipboard |
| **New** | forgets the conversation and starts over (your set stays as it is) |
| **Pop out** (right in the device) | opens the same chat in the browser, with more room |
| **Input field** (right in the device) | where you type; Enter sends |

**Important:** Live doesn't pass keyboard input to the chat window. You can only type in the **input field on the right of the device**. In the browser window (*Pop out*) the page has its own input field.

**Copying:** ⌘C doesn't work in the chat window inside Live. Click an answer or a thought block instead and it is copied, or use **Copy** for everything.

**Language:** the AI answers in the language of your last message. Just write English or German.

### A first request

1. Create a MIDI track with a Drum Rack (e.g. a Drum Rack from the browser under *Drums*).
2. Write: **"Make four bars of house drums on track 2."** (You count tracks from 1, as Live shows them.)
3. You see the AI calling tools ("Running compose …"). Then a new clip sits in the first free slot of the track.
4. Play the clip. Don't like it? **Undo**.
5. Write: **"Again, different."** – a new idea (a different "seed").

### Preview, Apply and confirmation

MidiBakery writes in two ways:

- **Directly:** a single part ("Make a bassline") is written at once. If existing notes would be replaced, the chat asks first with **Apply** and **Cancel**.
- **With a preview:** several parts together, whole songs and anything where you say "show me first" appear as a **card in the chat**: a small piano roll of what will be added or, for songs, a timeline of the sections. **Nothing in Live has changed yet.** **Apply** writes it. The card then reads "✓ applied · Undo reverts it". If you don't want it, just leave the card.

You can order the preview explicitly: "Show me a preview of … first."

**Apply is a single undo step**, even if many parts are written together. For whole songs (which also create tracks, effects and returns) there can be a few undo steps: press Undo several times until everything is gone.

If a target clip changed between preview and Apply, MidiBakery refuses (message `CONFLICT`). Ask for a new preview.

**Safety questions:** before **deleting tracks or clips** and **replacing notes** MidiBakery always asks with Apply/Cancel. If you decline, nothing happens and the AI tells you.

### Undo

- The **Undo** button in the chat, or ⌘Z / Ctrl+Z in Live.
- Every write by MidiBakery is its own step (a batch counts as one).
- "Undo that" works in the chat too.

## 7. Examples: what you can ask

You can mix English and German. Name tracks and clips ("Bass", "Intro Kick") or use numbers ("track 3", counted from 1 as in Live).

### Questions and overview

- "What is in my set?" / "Welche Spuren habe ich?"
- "What tempo and key is the song in?"
- "Show me the notes of the clip on track 2."
- "Which clips are in the Arrangement?"
- "What does the bass play in the drop?"

### Drums, bass, chords, melody

- "Make 4 bars of deep house drums on track 1."
- "Write eight bars of techno drums, sparser and with some swing."
- "Trap drums with lots of hi-hats, 2 bars."
- "A bassline that locks to the kick."
- "A bass that avoids the kick and only plays between the hits."
- "A calm, long bassline with held notes."
- "Four chords in the key of the set, one chord per bar."
- "Chords i – VI – III – VII, as stabs, with seventh chords." (Roman numerals relate to the set's key; "Am F C G" works too.)
- "A melody over these chords."
- "A melody between C4 and C6, not too many notes."
- "Make bass, chords and melody together, fitting the drums on track 1." (several parts: comes as a preview)

### Changing clips

- "Transpose the clip on track 3 down an octave."
- "Up 3 semitones."
- "Up two steps in the key." (scale steps, see chapter 9)
- "Give the bass a little variation."
- "Vary only the second half."
- "Humanize the drums so they sound less rigid."
- "Quantize the melody to sixteenths."
- "Play the chords as an arpeggio, ascending, in sixteenths."
- "Invert the melody." (mirrored within the key)

### The Arrangement

- "Build me a house song, standard length, in the set's key."
- "A melodic techno track, about 6 minutes, with the genre's tempo."
- "A drum & bass song as a radio edit."
- "Give me four takes for the bass in the drop to comp from." (take lanes, chapter 10)
- "Vary the 'Drop Bass'."
- "Swap 'Intro Bass' and 'Drop Bass'."
- "Move 'Break Chords' to bar 41."
- "Delete the clip 'Outro Hats'."
- "Set a marker 'Drop' at bar 33." (locator)

### Controlling Live

- "Set the tempo to 126."
- "Set the key to A minor."
- "Rename track 4 to 'Lead' and color it red."
- "Create a new MIDI track."
- "Launch the clip in slot 2 on track 1." / "Play the song." / "Stop."
- "Launch scene 3."

### Mixing and sounds

- "Pull track 2 down by 3 dB."
- "Pan the hi-hats slightly right."
- "Mute track 5." / "Solo the bass."
- "Add a reverb return."
- "Send the melody into the reverb at -12 dB."
- "Load a 909 kit." (MidiBakery searches Live's browser)
- "Add an Auto Filter on the bass."
- "Sweep the chords' filter cutoff upwards over four bars." (clip automation)
- "Show me the compressor's parameters on track 3."
- "Set up a master chain for house." (preview, then Apply; see chapter 12)

### Help and learning

- "Why does my bass sound muddy?" — the AI can give hints and read mixer values, but it doesn't hear the sound. Decide with your ears.
- "What is a drop?" — it will gladly explain.

### Good requests

- **Concrete:** track, length, style. "4 bars of house drums on track 1" beats "Make something cool".
- **One part at a time** when you want precision; **several parts or a song** when you want something to continue from, fast.
- **Say what's missing:** "The bass is too busy", "More air in the drums" – the AI adjusts density, swing or style.
- **Seed:** every idea has a number (seed). "Use seed 42" brings the same notes back. If you liked an idea, ask for its seed.

## 8. Composing parts and whole songs

### Single parts

A part is written as a **new clip into the first free slot** of a track. Existing clips aren't overwritten unless you ask (MidiBakery then asks back). A MIDI track without an instrument gets one after the notes: a 909 kit, Analogue Bass, Analog Soft Pad or Basic Pluck Keys from the Core Library (else Live's own Drum Rack, Drift, Wavetable or Operator).

| Part | Main knobs (all can be requested in plain words) |
|---|---|
| **Drums** | Style: house, techno, hiphop, trap, rock, breakbeat. Density, swing, fills at the end of each four-bar phrase, "chance" (how random ghost notes and some hi-hats are). Notes go to the pads of the track's **Drum Rack**; pads without a sound are skipped. |
| **Bass** | Style: syncopated, sustained, pulse, offbeat, octave, walking. Octave. Follows the chords and, on request, the kick of a drum clip (lock or avoid). |
| **Chords** | Rhythm: sustain, pulse, offbeat, stabs. 3 or 4 voices, pitch range, seventh chords, own progression. |
| **Melody** | Density, pitch range, follows the chords. Can also be a [counter melody](#counter-melody) to a lead. |

Common: **length** in bars (default 4), **swing** (how far off-beats lean back), **seed** (reproducible).

**How parts fit together:** bass and melody follow the chords of a clip ("fitting the chords on track 3"). The bass follows the kick of a drum clip. If you ask for several parts in one request, they share the same chord progression.

Everything is **in the key and time signature of your set**. So set key (*Scale* in Live) and tempo first.

### Counter melody

A second melody that answers a lead you already have. Ask: *"Write a counter melody to the lead in slot 1 of track 2"*. It goes into a new clip, the lead stays as it is. Without chords given, they are taken from the lead's notes. The lead can also be a clip planned earlier in the same request.

A lead in the Arrangement, as `plan_song` writes it: ask *"Write a counter melody to the Breakdown Lead clips on a new MIDI track"*. Every clip of that name gets a counter clip at the same bars and length on the other track (named *Breakdown Counter*), each over the chords of the chord or pad clip playing there. The lead track alone answers the whole song. Asking again gives those clips new notes instead of a second layer.

Modes (say them in words, default is the first):

- **fill_the_gaps**: plays only where the lead holds a note or rests.
- **call_and_response**: answers in the silent beats and bars of the lead.
- **passive_over_active**: calm long notes over a busy lead (more notes over a sparse one).
- **contrasting_rhythm**: sparse where the lead is dense and the other way round.
- **harmonic_notes**: moves with the lead's rhythm on a fitting other note.
- **note_layering**: the lead's own notes an octave away, same time or delayed.

Four fixed figures (the lead only sets register and clashes; they ignore its rhythm):

- **dotted_eighth_pulse**: a steady dotted-eighth pulse (3-3-3-3-3-1) on one chord tone per bar.
- **scale_staircase**: the same pulse climbing one scale step every one or two bars, one step back before the loop restarts.
- **trance_dotted_eighth_staircase**: the Trance tutorial's 8-bar figure: the pulse on scale degrees 1, 2, 3 and 5, two bars each.
- **echo_gap_answer**: in long notes of the lead (1.25 beats or more) three or four short notes moving by a step, then one longer note that keeps sounding when the lead comes back. Over a lead without long notes it writes nothing.

Register (`counter_register`): **above** the lead (default), **below** it, or **same** (then it never starts together with the lead). On strong beats it plays thirds, fifths, sixths or octaves to the lead.  A figure note that would clash on a strong beat moves to the nearest fitting scale tone.

### Whole songs by genre

You name the genre, MidiBakery plans the song, shows a **preview** (timeline of sections) and on **Apply** writes it to the **Arrangement**.

| Genre | Tempo (with "set the genre's tempo") | Sections (standard length) |
|---|---|---|
| **House** | 124 BPM | Intro, Build, Drop, Break, Build 2, Drop 2, Outro |
| **Melodic Techno** | 122 BPM | Intro, Build, Drop, Breakdown, Build 2, Climax, Outro |
| **Peak-Time Techno** | 128 BPM | Intro, Groove, Lift, Peak, Breakdown, Peak 2, Lift 2, Peak 3, Stripped Outro |
| **Drum & Bass** | 174 BPM | Intro, Build, Drop, Breakdown, Build 2, Drop 2, Outro |
| **Trap** | 145 BPM | Intro, Build, Drop, Verse, Build 2, Drop 2, Outro |

**Length:** *radio* (short: intro, break and outro halved), *standard*, *extended* (intro and outro doubled, DJ-friendly) or a target time in minutes ("about 5 minutes").

**What MidiBakery does:**

- **Tracks:** it looks for existing tracks for drums (a track with a Drum Rack), bass, chords and lead (by names like "Bass/Sub/808", "Chords/Pad/Keys", "Lead/Melody/Synth"). Missing tracks are created with a fitting kit and presets from the Core Library, named by their role (Drums, Bass, Chords, Lead, Riser, Impact); the silent Sidechain track goes first in the Set. **Name your tracks accordingly beforehand** if you want to keep your own sounds. "Use track 3 as the bass" assigns a role.
- **Notes:** structure and patterns follow recipes per genre (see [GENRES.md](../GENRES.md), German): drums with ghost notes and fills, a changing bass, a second harmony in the break, a hook that develops. Dynamics rise and fall with each section's energy.
- **Markers:** it sets **locators** at the sections.
- **Mix (on):** a reverb and a delay return (existing ones are reused), levels and sends for new tracks.
- **Automation (on):** filter sweeps, delay throws.
- **Sidechain (on):** bass and pads duck under the kick, via a silent helper track.
- **FX (on):** a riser before each drop and an impact on the drop's downbeat.
- **Start:** after the last clip in the Arrangement, or at a bar you name ("from bar 17"). **It never overwrites existing Arrangement clips**; it tells you the first free bar instead.

You can switch parts off: "without sidechain", "without risers", "don't create new tracks", "without mix returns", "with empty instruments instead of preset sounds".

More wishes: "with the progression i VI III VII", "set the genre's tempo", "use my drum clip from slot 1 for the drums" (a session clip is copied into every fitting section).

**Limits:** the song must be in **4/4** (otherwise MidiBakery says: set 4/4 first). MidiBakery cannot create or load breaks, samples (Amen, vocal chops) or your own audio clips. A song from a recipe sounds genre-typical; it becomes **good** through your listening and your arranging afterwards.

After Apply everything stays editable: these are ordinary MIDI clips and tracks.

## 9. Editing clips

MidiBakery changes existing notes as a **diff**: only what changes is touched. The rest keeps its probability, velocity deviation and undo history. There are six operations:

| Operation | What happens | Example |
|---|---|---|
| **Variation** | a bit of something new: notes change, drop out or get added. *Amount* sets how much. | "Vary the bass slightly." |
| **Transpose** | higher or lower. **Semitones** (12 = an octave) or **scale steps** in the key (2 steps = a third). | "One octave lower." / "5 semitones up." / "Two steps up in the key." |
| **Humanize** | small deviations in timing and velocity | "Loosen up the hi-hats." |
| **Quantize** | pull notes onto the grid (sixteenths etc.), with strength and swing | "Quantize to eighths, 70%." |
| **Invert** | mirror the melody, within the key | "Mirror the melody." |
| **Arpeggiate** | chords become runs (up, down, up-down, random; step length, 1–3 octaves) | "Arpeggio in sixteenths, up-down." |

**Only part of the clip:** "the first/second **half**", or by bars **of the clip**: "bars 3 to 4". The first bar of the *clip* is bar 1, not the bar in the song. Example: "Vary only the second half of the Drop Bass."

**Which clip?**

- A **session clip**: name track and slot ("clip on track 2, slot 1").
- An **Arrangement clip**: the clip's **name**, e.g. "Groove Bass" or "Drop Chords". Partial names work if unambiguous (case doesn't matter). Songs from `plan_song` name their clips after section and part. You find the names in the Arrangement or ask "which clips are in the Arrangement?".

**Rewrite instead of change:** "Rewrite the bass in the drop" replaces the notes of the Arrangement clip over its whole length (with a question first). The result lands in the same clip.

**Single notes:** "Delete the note on beat 3", "Make the last note longer": possible, but clicking in Live's piano roll is often faster.

## 10. The Arrangement

**Managing clips** (all by chat, one undo step per request; a clip never lands on another):

- **Move:** "Move 'Break Chords' to bar 41." A clip can only be moved if it isn't trimmed and not a loop.
- **Swap:** "Swap 'Intro Bass' and 'Drop Bass'." Both clips trade their start points.
- **Delete:** "Delete 'Outro Hats'." (with a question first)
- **Copy from the Session:** "Copy the clip from slot 2 on track 3 into the Arrangement at bar 9."
- **Create new:** MIDI clips with notes in the Arrangement.
- **Markers (locators):** "Set a marker 'Drop' at bar 33", "delete the marker at bar 17". The **transport must be stopped** for this; MidiBakery restores the playback position afterwards.

**Take lanes for comping** (Live 12.2 or newer): several **variations of a part** (hook, melody, bass, chords or drums) over the same chords, each on its **own take lane** of a track. You listen through them and pick the best bits in Live.

- Request: "Give me 4 takes for the melody in bars 17 to 24 on track 3." Default: 4 takes, 8 bars, hook.
- Live shows the lanes only with **Show Take Lanes** (⌘⌥U / Ctrl+Alt+U).
- One undo removes all takes.

## 11. The Reference Analyzer

It looks at a **reference song** you like and shows how it is built: sections (intro, build, drop, break, outro), key, tempo and per bar the energy of kick, lows, mids and highs. You learn how long an intro typically is and when the drop arrives. And you can ask MidiBakery to build **your song after this structure**.

### Analyze

1. Create an **audio track** and drag the reference song into the **Arrangement** (not the Session view).
2. Drag **MidiBakery Reference Analyzer** onto that track.
3. Press **Analyze**. The device computes inside Live (nothing is uploaded).
4. You see the sections, key and tempo and below them four lanes: **Kick, Lows, Mids, Hats**.

**File formats:** on macOS the device also reads MP3, AAC etc. (via the system tool `afconvert`). On Windows only **WAV** works: convert the song to WAV first.

**Warped and unwarped clips:** if the clip is *warped* in Live, the device uses Live's bars. An **unwarped** clip runs at its own tempo; the device detects tempo and first beat itself, warps the clip onto your grid (bar 1 on a bar line, your set tempo stays) and analyzes again. If that fails, it says so: warp by hand (1.1.1 on the first beat) and press **Analyze** again.

### Settings

- **Genre** (Auto or one of the five genres): sets the section names (e.g. "Lift/Peak" for peak-time techno), the phrase length (16 bars for drum & bass) and settles half or double tempo.
- **Sensitivity** (0–100 each, default 50, for Kick, Lows, Mids, Hats): how finely the song is split. At **100** every change found becomes a section. At **50** similar neighbours merge into one section (four breaks in a row are one long break). Lower: a drop and its groove become one. The **ratio** of the four fields decides what counts as a change: "Hats 30, the rest 100" lets hi-hat changes pass, "only Kick high" splits the song where the kick stops and returns. The analysis reruns by itself when you let go of a field.
- **Lock** (on): when one field changes, the others move by the same amount.
- **Set Locators:** sets markers at the sections in the Arrangement. The transport must be stopped.
- **Remove Locators:** removes all markers within the clip's range.

The device stores results in the MidiBakery folder under `references/`. The chat reads them from there.

### Use it in the chat

- "Which references have I analyzed?" / "What is the structure of my reference song?"
- "Build me a peak-time techno song after the reference '<part of the name>'." – section order and lengths follow the reference, snapped to the genre's grid. MidiBakery takes **only the structure**, not the sound of the reference.
- "… and use the reference's tempo and key."
- An **unwarped** reference works only if your song plays at the same tempo (otherwise an error message).

## 12. Mixing and sounds

MidiBakery can read and set Live parameters. It **hears nothing**. You make the timing and sound decisions.

- **Mixer:** volume and sends in dB (as Live shows them), pan, mute, solo, crossfader, routing (inputs and outputs, by the names in Live). For tracks, returns and master.
- **Returns:** create return tracks, optionally with a Live effect ("reverb return").
- **Devices:** insert native Live devices, read and set their parameters (names and value ranges are shown in the chat), also inside racks. Read and change macros and chains of a rack.
- **Loading sounds:** "Load a 909 kit", "a pad sound": MidiBakery searches Live's browser (Core Library) by name and loads it onto the chosen track. An instrument or kit replaces the existing instrument; an effect is appended. If nothing matches all words, it tries part of them.
- **Reading drum pads:** which pad has which note?
- **Automation:** clip automation for device parameters and the track mixer (volume, pan, sends): ramps, sine, triangle etc. "Sweep the cutoff up over 8 bars." In the Arrangement MidiBakery rebuilds the clip for this; the notes stay, existing envelopes of that clip are replaced.
- **Sidechain, reverb, delay and filters for whole songs:** handled by `plan_song` (chapter 8).
- **Master chain:** "Set up a master chain for house" puts EQ Eight, Glue Compressor and Limiter with the genre's settings at the end of the Master track. It is a **starting point, not a finished master**. What the devices do:
  - The EQ cuts low rumble: 30 Hz, or 20 Hz for drum & bass and trap.
  - The Glue Compressor gently "glues" the mix (2:1, attack 30 ms, release Auto). Play the loudest part and turn its **threshold** until the needle shows 1–2 dB.
  - The Limiter catches peaks at -1 dB true peak. It does **not** make the song louder.
  - As with songs you get a preview first and write with **Apply**. Pressing **Undo** twice removes the chain.
  - If your Master already has a Limiter, EQ Eight or Glue Compressor, MidiBakery leaves it alone.
  - Where the settings come from: [GENRES.md](../GENRES.md#master-kette-plan_master) (German).
- **Measuring loudness:** drag the **MidiBakery Loudness Meter** device (browser: Audio Effects › Max Audio Effect › MidiBakery) onto the Master track as its **last device**, after the Limiter. While Live plays it shows:
  - **Momentary** (the last 0.4 s), **Short-term** (the last 3 s) and **Integrated** (everything since the start or a reset) in LUFS, after ITU-R BS.1770 / EBU R 128.
  - **Peak**: the highest sample peak since the reset in dB. A true peak can be up to about 0.5 dB higher.
  - **Reset** restarts Integrated and Peak. For a number to compare: reset, then play the whole song (or the drop).
  - In the chat: "How loud is the song?" MidiBakery reads the device with `measure_master`. Without the device on the Master, MidiBakery names no LUFS figure.
  - The values are a good approximation, not a calibrated meter: Max reads the blocks on its scheduler's 100 ms clock.
- **Bringing the song to a target loudness:** "Make the song as loud as house" or "to -14 LUFS for Spotify". This needs the master chain and the Loudness Meter on the Master. It works in rounds:
  1. Reset the meter, play the song (or at least 30 s of the loudest part).
  2. MidiBakery proposes how many dB to change the Limiter's **Input Gain** (at most 6 dB per round) and writes it with **Apply**. One undo takes it back.
  3. The meter starts again: play again, then the next round. Within 0.5 LU of the target, MidiBakery says so.
  - Targets: house -8, melodic techno -8.8, peak-time techno -7.7, drum & bass -6.3, trap -8.4, streaming -14 LUFS. They are medians of released tracks ([GENRES.md](../GENRES.md#lautheitsziele-plan_loudness), German), not rules.
  - Louder here means more limiting. Listen for pumping and flat drums; MidiBakery never gives the Limiter more than +12 dB.

For ear questions ("sounds muddy") you get hints but no measurement. For accurate audio analysis use Live's own analyzers.

## 13. Generator and Transform without the chat

The two devices **MidiBakery Generator** and **MidiBakery Transform** need no chat and no AI, only the running API (so the Remote Script, chapter 4). They are Live **MIDI Tools** and appear in the clip view of a MIDI clip under **Generate** and **Transform**. They work on the **selected time range** of the clip, in the clip's key (Live 12.2 or newer).

**Generator**

| Control | Meaning |
|---|---|
| **Part** | Drums, Bass, Chords, Melody |
| **Style / Rhythm** (second menu) | style of the chosen part (Drums: House, Techno, Hip-Hop, Trap, Rock, Breakbeat; Bass: Sustained, Pulse, Offbeat, Octave, Walking, Syncopated; Chords: Sustain, Pulse, Offbeat, Stabs) |
| **Density**, **Swing**, **Chance** (drums only) | density, swing, randomness of ghost notes |
| **Seed** and **Dice** | the idea; Dice rolls a new one |
| **Replace** (default: on) | clears the selected range before the new notes go in. A generator can otherwise only add in Live. |

**Transform:** **Operation** (Humanize, Quantize, Invert, Arpeggiate, Variation, Transpose), **Amount**, **Semis** (semitones for Transpose), **Arp Rate** (1/32 to 1/4), **Seed** and **Dice**. If an operation changes nothing, the reason is in the device's status line (for example "No chords to arpeggiate").

On first use the device briefly shows "Working …". The result arrives a moment later in the same cycle.

## 14. Troubleshooting

### The chat stays on "Connecting…" or the dot is red

1. **Is the Remote Script on?** Preferences > Link, Tempo & MIDI > Control Surface = **MidiBakery** (chapter 4). Restart Live after installing.
2. **Is the API running?** In a terminal (program from the installation folder, chapter 3): `midibakery ping`. It should confirm the connection to Live.
3. **Reload the device:** delete the Chat device from the track and drag it in again (the chat page reloads only that way after an update).
4. **Another program holds port 8766:** quit it or restart Live.
5. **Two versions:** if an API of an older version is still running, MidiBakery replaces it on start. If that fails, quit Live and start it again.

### "No Claude key" / NO_API_KEY

You picked a Claude model but haven't stored a key yet: press **Key** (chapter 5). If the key is wrong, the chat says "INVALID_KEY" ("That does not look like a Claude API key", or rejected by Anthropic).

### "Cannot reach LM Studio" / "Cannot reach Ollama"

The server isn't running. LM Studio: tab **Developer** > start the server, or `lms server start`. Ollama: `ollama serve` (or start the Ollama app). If it runs on another computer or port, use the environment variables `LMSTUDIO_HOST` or `OLLAMA_HOST`. The model menu lists local models only when the server is reachable.

### "… too small a context for MidiBakery's tools"

LM Studio loaded the model with too little context. Reload: `lms load <model> -c 32768` (chapter 5).

### The model answers in another language

Local models sometimes lose the language. MidiBakery reminds them with every message. If that doesn't help: write "Answer in English" or press **New**.

### The AI says "done" but nothing happened in Live

This happens occasionally with small local models. Check Live's tracks and clips (not just the chat). Then ask: "Did you really write it? Do it now with the tools." The chat shows every tool call ("Running …" and a check mark or an error); if it's missing, nothing happened.

### "Stopped: … failed 3 times" (STUCK)

The model made the same error three times, or everything failed for six rounds in a row. MidiBakery stops before doing further harm. Nothing more was changed. Rephrase (name track and section), make the request smaller, or use a bigger model or Claude.

### "Stopped after 24 tool rounds"

The request was too big for the model. Split it up.

### "CONFLICT"

Something changed between preview and Apply, or a clip would land on another. Ask for a new preview, or name a free place.

### "LICENSE_REQUIRED"

Only affects versions where the license check is on (see chapter 15). Then: **Start trial** or **Enter key** in the chat.

### The song plan refuses

- "plan_song needs 4/4": set the time signature to 4/4.
- It names "the first free bar": clips already sit there; pick a later start.
- Unwarped reference: possible only at the reference's tempo (chapter 11).

### Markers can't be set

The transport must be stopped. Press Stop and try again.

### Take lanes are missing

They need Live 12.2 or newer. Show them with **Show Take Lanes** (⌘⌥U / Ctrl+Alt+U).

### A device doesn't load / "Max for Live not available"

The devices need **Max for Live** (part of the Live Suite). Check in Preferences > **Max for Live** that it is enabled.

### Where do I look?

The files are in the MidiBakery folder: macOS `~/Library/Application Support/MidiBakery/`, Windows `%APPDATA%\MidiBakery\`. Useful for a support conversation (keys and tokens are masked or not included):

| File | Content |
|---|---|
| `api.log` | timestamps, each of your messages and each tool call with errors: this is where you see why a chat went wrong |
| `device-chat.log` | the Chat device |
| `device-miditool.log` | Generator and Transform |
| `device-reference.log` | Reference Analyzer |
| Live's `Log.txt` | messages of the Remote Script (starting with "MidiBakery:") |

**Copy** in the chat gives you the whole conversation including tool calls, handy for bug reports.

## 15. FAQ

**Does MidiBakery change my projects without asking?**
Only on your request. Every step is an undo step. Deleting and replacing ask first. A whole song comes as a preview first.

**What does it cost?**
Claude: API use at your Anthropic rate (input and output per token; a short request costs little, conversations with a lot of set content more). Local models: nothing. On the MidiBakery license: the license check is **off** in this version; everything works without trial and without key. Once it is switched on, there will be a **30-day trial**, after that a license key (usable permanently, 12 months of updates, on two computers). Without a valid license MidiBakery still reads your set and does undo, but creates and changes nothing. Your set is never touched. You enter the key in the chat under **Enter key**.

**Which data leaves my computer?**
With **Claude**: everything the AI reads to work, i.e. track and clip names, notes, tempo, key, devices. With **LM Studio or Ollama**: nothing, everything stays local. The daily **update check** sends version, operating system, processor type and channel (off: `midibakery update --disable`). The Reference Analyzer's analysis runs entirely inside Live.

**Does it work with Live Standard or Intro?**
The devices need Max for Live (Suite, or Standard with the Max for Live add-on). It is tested with Live 12 Suite.

**Can MidiBakery create audio or load samples?**
No, only MIDI, and it loads sounds from Live's browser. It cannot load samples and breaks.

**Can the AI "hear" my music?**
No. It works with notes and parameters. The Reference Analyzer analyzes numerically, but the AI doesn't hear.

**Why does MidiBakery create tracks and returns for songs?**
So that the result sounds right after one request: kit, bass, pad, lead, reverb, delay, sidechain. "Without new tracks" and "without mix" switch that off.

**Why does the song sound generic?**
Because recipes are conventions. Use them as scaffolding: swap sounds, change chords, vary clips, and listen. A reference song you like helps with the structure.

**I have several Live sets open.**
MidiBakery controls the set that is currently open and active.

**Can I use MidiBakery with Claude Desktop or Claude Code?**
Yes: see chapter 16.

**How do I remove it?**
Chapter 3, "Uninstalling".

## 16. Using MidiBakery from Claude Desktop or Claude Code

The MCP server brings the same 40 tools to Claude Desktop, Claude Code and other MCP apps. You then chat in their window instead of the Chat device. The setup, a plain-language explanation and the reference of every tool are in **[MCP_SERVER.md](MCP_SERVER.md)** (German: [MCP-SERVER.md](MCP-SERVER.md)).
