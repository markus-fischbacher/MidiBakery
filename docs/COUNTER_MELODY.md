# Counter melody patterns and generator choices

A counter melody is a secondary melodic line that accompanies or answers a main melody. This document distinguishes two tutorials' suggestions from the implemented `compose` modes listed below. The generator already exists; its conservative rules are useful defaults, not universal counterpoint requirements. Sound-design suggestions are not applied.

Sources:

- **Trance** - "How to Counter Melody - Trance" (Cubase, F minor, intro pluck arpeggio, 8 bars, trance tempo). The piano roll is visible but small: rhythm, bar-by-bar contour and register can be read, individual note names mostly cannot, apart from the scale steps the voice-over names (F, G, A flat, C, B flat, D flat, E flat).
- **Separation** - "The ONLY Counter Melodies video you NEED to watch" (FL Studio, 140 bpm, part five of a melody-basics series). Several note names are readable in the piano roll (C5, C#5, D#5, F5, G#5, G5, E6, F#5 and so on), but every example is a different short melody.

Provenance follows docs/PATTERNS.md: `roll` = read from a readable piano roll, `described` = rebuilt from the voice-over. A `roll` here means the rhythm or contour was visible; exact pitches are given only where the frame showed or the voice-over named them. Treat all of it as a starting point, not a transcription. Exact source URLs and timestamps are still needed for reproducibility. Octave names quoted from the videos use their source DAWs' conventions, not necessarily Live's; implementation ranges below use Live's MIDI 60 = C3 convention.

| Technique | Count |
|---|---|
| Rhythm / placement rules | 5 |
| Pitch rules | 4 |
| Fixed figures | 2 |
| Support layers (bass answer, sound) | 2 |

## The central idea: separation

The Separation video's teaching framework emphasizes **rhythm, harmony (pitch), octave and timbre**. These are ways to make lines perceptually distinct, not necessary conditions for every counter melody. Independent lines can share an onset pattern: [first-species counterpoint](https://openmusictheory.github.io/firstSpecies.html) is a note-against-note example. Conversely, octave doubling alone may reinforce a lead rather than create an independent line. Register separation can reduce masking but cannot prevent harmonic dissonance. The Trance example uses a simpler repeating rhythm and stepwise pitch changes; it is one workable arrangement choice.

## Rhythm and placement patterns

| Name | What it is | Rule against the main melody | Provenance |
|---|---|---|---|
| `contrasting_rhythm` | Two different rhythmic patterns layered. | This strategy avoids repeating the main line's onset pattern and contrasts density; it is not a requirement for other strategies. | `described` (the roll shows the two rhythms, no readable notes) |
| `passive_over_active` | A busy ("active") main melody gets a slow ("passive") line that supports it, or the other way round. | Count onsets per bar: the counter has clearly fewer (about a third to half) with longer notes, or many more if the main line is sparse. | `described` + `roll` (long notes over a run of short ones) |
| `fill_the_gaps` | The counter plays while the main melody sustains or rests and stops when the main melody comes back. | Counter notes start inside the main melody's held notes and rests; when the main note starts, the counter sustains its last note (or stops). In the example the counter runs while the main B (and later the G#) is held, then holds its last note under the returning melody. | `roll` (main G#5 held, counter notes E6 and nearby inside the hold) |
| `dotted_eighth_pulse` | A bar-reset, dotted-eighth-inspired figure on one pitch: **six** onsets at 16th steps **1, 4, 7, 10, 13, 16**. | Cyclic gaps are 3-3-3-3-3-1 sixteenths, including the one-step gap into the next bar. This is not uninterrupted dotted eighths across bar lines. Its accents shift relative to quarter beats, but its onsets can coincide with a 16th-note arp. | `roll` rhythm interpretation; the implementation's grid is explicit here; F is named in the voice-over |
| `call_and_response` | The counter answers in the pauses between main phrases instead of playing along. | Same as `fill_the_gaps` at phrase level: the counter owns the bars/beats where the main phrase is silent. Implied by the gap examples; not taught as its own technique. | `described` (inferred from the gap examples) |

## Pitch rules

| Name | What it is | Rule against the main melody and chords | Provenance |
|---|---|---|---|
| `note_layering` | Reinforce existing melody or chord pitch classes in another octave or at another time. | Copying pitch classes preserves any existing chromatic notes too; it does not independently guarantee the key. A simultaneous octave double is a support layer, not necessarily an independent counter melody. | `roll` (the matched note is visible) + `described` |
| `harmonic_notes` | Choose another consonant note rather than doubling the main note. | This strategy favors chord tones, then scale tones, and avoids simultaneous identical pitch classes. That is the mode's constraint, not a prohibition on unisons or expressive dissonance in other music. | `roll` (ghost notes of the main melody; no two simultaneous notes share a pitch) + `described` |
| `octave_separation` | Place a line above or below the main melody's range. | The video shows a main line around C5-C6 and counter from C6 upwards (source-DAW labels). This can reduce masking, but does not guarantee consonance. The implemented register window uses a third of clearance, not a mandatory octave. | `roll` (counter from C6 over a main melody within one octave) |
| `scale_staircase` | A one-pitch figure that climbs the scale a step at a time, then returns. | Keep the rhythm fixed, change only the pitch once every one or two bars, moving by scale steps: F, G, A flat, C (top of the range), then fall back by one step before the loop restarts on the root. Fits the "build" in an eight-bar loop. | `roll` (staircase of the same figure rising over 8 bars) + `described` (named steps) |

## Fixed figures

| Name | What it is | Notes / rhythm | Provenance |
|---|---|---|---|
| `trance_dotted_eighth_staircase` | An 8-bar implementation inspired by the Trance example, not an exact transcription. | Onsets at 16th steps 1, 4, 7, 10, 13, 16 every bar. Zero-based minor-scale degrees per bar: 0, 0, 1, 1, 2, 2, 4, 4 (F, F, G, G, Ab, Ab, C, C in F minor), then the loop restarts. Register and consonance adjustment can change the final pitches. | `roll` rhythm and contour interpretation, `described` pitches |
| `echo_gap_answer` | The gap-filling answer from the Separation video: while a long main note holds, the counter plays short notes high above it, then ends on one long note. | Main note long (about 1 to 2 beats); the counter plays 3 to 4 short notes one octave and more higher, rising or falling by a step, then one longer note (E6 in the example) that sustains while the main melody re-enters. | `roll` (main G#5, counter notes up to E6) |

## Support layers

| Name | What it is | Rule | Provenance |
|---|---|---|---|
| `bass_mimic` | A bass line built by copying the counter melody's rhythm, moved to the bar start, one octave or two down. | Copy onsets and choose chord tones or passing notes. Using the third or fifth changes the relation to the counter; root doubling and parallel movement can also be intentional. Not implemented. | `roll` rhythm, `described` notes |
| `timbre_split` | Separate lines through sound choice or articulation. | Contrasting timbres can help in the same register; similar timbres can still work with distinct contours or phrasing. Unison doubling tends to merge. Not implemented. | `described` (sound-design hint only) |

## Tutorial suggestions, not universal rules

The videos favor:

- Rhythmic contrast with the main melody; shared rhythms can also support independent lines.
- It is separated by octave or timbre, or it sits in the gaps of the main melody.
- It uses the scale and the chord tones of the chord underneath (Trance: scale notes marked in green, notes outside it in orange; chord tone C is the "top" over an F root).
- Simple repeated ideas. The authors' preference for few connecting notes is aesthetic, not a limitation on effective melodic writing.
- Ideas bounce off each other: once a bass line (or another part) answers the counter melody, the whole intro feels developed.

Listening checks:

- Is the intention an independent line, a harmonized lead or a double? None is inherently wrong.
- Can both contours be heard? Adjust rhythm, register, articulation, timbre or level if masking obscures the intended line.
- Is dissonance intentional and does its treatment fit the style? Moving a line up an octave changes register, not its pitch-class relationship.
- Does the counter leave the main melody enough focus? Sustaining, stopping and playing alongside it are all possible choices.
- Judge interval and register choices in context. The Trance video's preference for B flat over C above an F root describes that example, not a general ranking.

## Generator inputs

The implemented counter melody generator reads more context than the bass/lead templates (which take chords and a scale only):

- **The main melody's notes**, read from a clip in Live (pitch, start, length). Rhythm-based rules need onsets and rests; harmonic rules need the pitch at every moment; gap rules need the held-note spans.
- **The chords** per bar (as in `compose.harmony.Harmony`) and **the scale** (`Scale`) of the song, for chord-tone and scale-step choices.
- **The grid and meter** (`Grid`, `Meter`) for the 16th-step placement, plus the bar count and, optionally, the bpm for the pulse figures.
- **Parameters**: `pattern`, register (`above`, `below`, `same`) and density (or let the rule choose it from the main melody).

Conceptual categories (implementation support is listed separately below):

| Kind | Patterns |
|---|---|
| Rule-based (read the main melody) | `contrasting_rhythm`, `passive_over_active`, `fill_the_gaps`, `call_and_response`, `note_layering`, `harmonic_notes`, `octave_separation`, `bass_mimic` |
| Fixed figure (data in the style of `lead_templates.py`, scale degrees with a mode) | `trance_dotted_eighth_staircase` (`scale` mode), `echo_gap_answer` (`root_step` or `scale` mode, placed in the main melody's gaps) |
| Mixed (a fixed rhythm, pitches from a rule) | `dotted_eighth_pulse`, `scale_staircase` |
| Hint only | `timbre_split` |

## In MidiBakery

`counter_mode` on a melody with `counter_to` (see [PATTERNS.md](PATTERNS.md#counter-melody-modes)):

| Technique | In MidiBakery |
|---|---|
| `contrasting_rhythm`, `passive_over_active`, `fill_the_gaps`, `call_and_response`, `note_layering`, `harmonic_notes` | `counter_mode` of the same name |
| `octave_separation` | `counter_register` (`above`, `below`; `same` only with onsets that never meet the main's) |
| `dotted_eighth_pulse` | `counter_mode` `dotted_eighth_pulse` |
| `scale_staircase` | `counter_mode` `scale_staircase` |
| `trance_dotted_eighth_staircase` | `counter_mode` `trance_dotted_eighth_staircase` |
| `echo_gap_answer` | `counter_mode` `echo_gap_answer` |
| `bass_mimic` | not built |
| `timbre_split` | not built (hint only) |

Ten `counter_mode` values are implemented: six rhythm/context-driven modes and four figures. The table distinguishes the remaining ideas from supported behavior; it is not a future implementation promise.

## As built: rests and register

A **phrase rest** is an implementation heuristic: silence of a beat or more before the lead's next note. Shorter staccato gaps are not filled as rests; this is not a universal definition of phrasing. Without `counter_mode`, long phrase rests (2 beats or more, a quarter of the time) select `call_and_response`; shorter rests or held notes select `fill_the_gaps`; a lead without either gets `passive_over_active`. The register aims to keep a third (not an octave) clear of the lead and stays within **MIDI 36..96 (Live C1..C6)**; without `counter_register` it chooses above when there is enough room for the counter window, otherwise below. `plan_song` leads that would play through a 4-bar phrase rest in their 4th bar, giving a counter melody a whole bar to answer in.

Strong-beat consonance, avoidance of parallel fifths/octaves and voice crossing, and the fixed register window are conservative **generator constraints**, not universal musical correctness tests. They can suppress idiomatic electronic-music doubling or dissonance. Relaxed or style-specific rules would require an explicit future mode; this assessment does not change existing notes or defaults.

**Source length.** `compose` and `plan_song` pass the lead clip's true length, so a trailing empty bar stays empty, and the counter can answer there. Only a source shorter than the target loops (as one whole-bar cycle of its own length). Without a length (standalone `generate` has none), the loop ends after the last note, as before.
