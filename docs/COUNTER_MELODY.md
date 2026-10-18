# Counter melody patterns (analysis for a future generator)

A counter melody is a second melody that answers the main melody. This document collects what two tutorials teach about it, as rules and figures a `compose` generator could reproduce. It is the analysis step only; no generator exists yet. Sound design is kept as a hint and is not applied.

Sources:

- **Trance** - "How to Counter Melody - Trance" (Cubase, F minor, intro pluck arpeggio, 8 bars, trance tempo). The piano roll is visible but small: rhythm, bar-by-bar contour and register can be read, individual note names mostly cannot, apart from the scale steps the voice-over names (F, G, A flat, C, B flat, D flat, E flat).
- **Separation** - "The ONLY Counter Melodies video you NEED to watch" (FL Studio, 140 bpm, part five of a melody-basics series). Several note names are readable in the piano roll (C5, C#5, D#5, F5, G#5, G5, E6, F#5 and so on), but every example is a different short melody.

Provenance follows docs/PATTERNS.md: `roll` = read from a readable piano roll, `described` = rebuilt from the voice-over. A `roll` here means the rhythm or contour was visible; exact pitches are given only where the frame showed or the voice-over named them. Treat all of it as a starting point, not a transcription.

| Technique | Count |
|---|---|
| Rhythm / placement rules | 5 |
| Pitch rules | 4 |
| Fixed figures | 2 |
| Support layers (bass answer, sound) | 2 |

## The central idea: separation

The Separation video says a counter melody only works when it is separated from the main melody, through four things: **rhythm, harmony (pitch), octave and timbre**. Rhythm is the one that is always needed; the others can be mixed in. The Trance video reaches the same result by ear: keep the counter line in or just outside the main melody's range, give it a simpler, steadier rhythm, and let it step through the scale.

## Rhythm and placement patterns

| Name | What it is | Rule against the main melody | Provenance |
|---|---|---|---|
| `contrasting_rhythm` | Two different rhythmic patterns layered. The bounce comes from the contrast. | The counter line must not repeat the main line's onset pattern. If the main melody is dense, the counter is sparse, and vice versa. | `described` (the roll shows the two rhythms, no readable notes) |
| `passive_over_active` | A busy ("active") main melody gets a slow ("passive") line that supports it, or the other way round. | Count onsets per bar: the counter has clearly fewer (about a third to half) with longer notes, or many more if the main line is sparse. | `described` + `roll` (long notes over a run of short ones) |
| `fill_the_gaps` | The counter plays while the main melody sustains or rests and stops when the main melody comes back. | Counter notes start inside the main melody's held notes and rests; when the main note starts, the counter sustains its last note (or stops). In the example the counter runs while the main B (and later the G#) is held, then holds its last note under the returning melody. | `roll` (main G#5 held, counter notes E6 and nearby inside the hold) |
| `dotted_eighth_pulse` | A steady dotted-eighth figure on one pitch: notes three 16ths apart, five per bar, closed by two 16ths. | Against a 16th-note arpeggio the dotted-eighth spacing drifts across the grid and so never lines up with the arpeggio's pattern. Same 3-3-3-3-3-1 spacing the lead patterns use. | `roll` (rhythm: equal spacing, a close at the bar end); the F pitch is named in the voice-over |
| `call_and_response` | The counter answers in the pauses between main phrases instead of playing along. | Same as `fill_the_gaps` at phrase level: the counter owns the bars/beats where the main phrase is silent. Implied by the gap examples; not taught as its own technique. | `described` (inferred from the gap examples) |

## Pitch rules

| Name | What it is | Rule against the main melody and chords | Provenance |
|---|---|---|---|
| `note_layering` | The counter plays chord/melody notes that are already there, in another octave or at another time. | Notes are the same pitch classes as the main melody (or the chord under it), moved by an octave or delayed. It cannot be off key; it adds no separation by itself, so combine it with another octave or rhythm. Example: main hits C, the counter hits C an octave away at the same time. | `roll` (the matched note is visible) + `described` |
| `harmonic_notes` | Instead of doubling the main note, the counter picks another note that sounds good with it. | At every moment the counter's pitch is a different, consonant scale note against the main note and chord: never the same pitch class at the same time (the roll shows the notes overlapping in time but never on one pitch). Pick from chord tones first, then scale tones. | `roll` (ghost notes of the main melody; no two simultaneous notes share a pitch) + `described` |
| `octave_separation` | The counter lives an octave or more away from the main melody. | Main melody sits in about one octave (e.g. C5-C6); the counter starts at C6 and above, a whole octave clear, so the lines cannot clash. Can also go below. | `roll` (counter from C6 over a main melody within one octave) |
| `scale_staircase` | A one-pitch figure that climbs the scale a step at a time, then returns. | Keep the rhythm fixed, change only the pitch once every one or two bars, moving by scale steps: F, G, A flat, C (top of the range), then fall back by one step before the loop restarts on the root. Fits the "build" in an eight-bar loop. | `roll` (staircase of the same figure rising over 8 bars) + `described` (named steps) |

## Fixed figures

| Name | What it is | Notes / rhythm | Provenance |
|---|---|---|---|
| `trance_dotted_eighth_staircase` | The Trance video's counter melody, as a fixed 8-bar figure in the song's minor key: dotted-eighth pulse (see `dotted_eighth_pulse`) rising F, G, A flat, C and coming back. | 16th grid, steps 1, 4, 7, 10, 13 plus a close of two 16ths at 15-16; pitch per bar in scale degrees (minor, tonic 0): bars 1-2 degree 0, bars 3-4 degree 1, bars 5-6 degree 2, bars 7-8 degree 4 (the roll shows the line rising about every two bars), then down to 2 or 1 before the root. Dropping the whole line an octave puts it inside the main melody's range ("operating inside the melody") with a few notes poking out above; leave it up for clear separation. | `roll` for the rhythm and contour, `described` for the pitches |
| `echo_gap_answer` | The gap-filling answer from the Separation video: while a long main note holds, the counter plays short notes high above it, then ends on one long note. | Main note long (about 1 to 2 beats); the counter plays 3 to 4 short notes one octave and more higher, rising or falling by a step, then one longer note (E6 in the example) that sustains while the main melody re-enters. | `roll` (main G#5, counter notes up to E6) |

## Support layers

| Name | What it is | Rule | Provenance |
|---|---|---|---|
| `bass_mimic` | A bass line built by copying the counter melody's rhythm, moved to the bar start, one octave or two down. | Copy the counter's onsets, then change pitches to chord tones of the current chord (F minor: F root, C fifth, A flat third), with a passing dissonance (B flat, D flat) allowed on a weak position and a return to the root F at the end. Using the third or fifth instead of the root avoids a "cheesy" parallel with the counter. Bass and counter then bounce off each other. | `roll` for the rhythm (groups of short notes in the bass rows follow the counter), `described` for the notes |
| `timbre_split` | Counter melody on a different sound, or the same sound in a different octave. | Same octave only works if the timbre differs (thin bright pluck vs. soft flute; sustained string vs. spiccato). Same sound, same octave, same pitch merges into a thicker main melody. | `described` (hint only; MidiBakery does not apply sound design) |

## General rules the videos state

When a counter melody works:

- It has a different rhythm from the main melody. This is the one hard requirement (Separation video).
- It is separated by octave or timbre, or it sits in the gaps of the main melody.
- It uses the scale and the chord tones of the chord underneath (Trance: scale notes marked in green, notes outside it in orange; chord tone C is the "top" over an F root).
- It is simple. Both authors say not to over-complicate: a few notes, repeated, beat a clever run. Connecting notes that run through the scale are optional ("not much of a fan").
- Ideas bounce off each other: once a bass line (or another part) answers the counter melody, the whole intro feels developed.

What to avoid:

- Same rhythm as the main melody (the counter just becomes a double).
- Same register with the same sound (it masks the main melody or smears it). The Trance video's fix: same register only for a "merge" effect, with another sound.
- Hitting the same note at the same time as the main melody when the aim is harmony (that is layering, not a counter line).
- Notes that clash with the lead: when a counter melody "rubs the wrong way", change or delete the offending notes and move the line up an octave.
- Counter notes that stay on while the main melody is the focus: the counter steps back (sustains or stops) when the main note comes in.
- Too far above the chord: the Trance video tries the C above the F root and finds it "a bit too far"; B flat works better for a small dissonance.

## Generator inputs

A counter melody generator is a function of the main melody, so it needs more than the bass/lead templates (which take chords and a scale only):

- **The main melody's notes**, read from a clip in Live (pitch, start, length). Rhythm-based rules need onsets and rests; harmonic rules need the pitch at every moment; gap rules need the held-note spans.
- **The chords** per bar (as in `compose.harmony.Harmony`) and **the scale** (`Scale`) of the song, for chord-tone and scale-step choices.
- **The grid and meter** (`Grid`, `Meter`) for the 16th-step placement, plus the bar count and, optionally, the bpm for the pulse figures.
- **Parameters**: `pattern`, register (`above`, `below`, `same`) and density (or let the rule choose it from the main melody).

Which patterns are rule-based and which are fixed:

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

A first generator needs only one input beyond what `compose` has today: the main melody read from a clip. With that, `fill_the_gaps`, `harmonic_notes` and `octave_separation` cover most of what both videos show; the fixed figures are cheap to add as templates.
