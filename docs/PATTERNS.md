# Named patterns for `compose`

`compose` (and `plan_changes` steps) take `pattern` for drums, bass, melody and chords. It replaces `style` (drums, bass), the generated melody, or the progression (chords). Patterns come from four tutorials; the sound design they describe is kept as a hint and is not applied.

Provenance: most voice-overs name notes and rhythms only briefly, so some rhythms are rebuilt from the description (`source: described`); patterns whose piano roll was readable say `roll`. Treat both as a starting point, not a transcription.

Tutorial names and pattern IDs are provenance hints, not claims of endorsement or verified note-for-note transcription. Exact source links and timestamps remain a documentation gap. Descriptors such as "evil", "happy" and "euphoric" are browsing labels, not guaranteed emotional effects: tempo, register, timbre, articulation, context and listener background also matter ([research overview](https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2013.00487/full)). Sound-design and automation suggestions below are not promises that a MIDI pattern applies them.

| Family | Field | Count |
|---|---|---|
| Bass | `kind: bass`, `pattern` | 23 |
| Lead | `kind: melody`, `pattern` | 22 |
| Drums (techno) | `kind: drums`, `pattern` | 6 |
| Emotion progressions | `kind: chords`, `pattern` | 15 |

A chords pattern sets the progression and the voicing (roots doubled, thirds up, pedal tone). Bass and melody that follow it in the same plan use its chords. Some templates select a different scale mode on the song's tonic or contain chromatic chords; a pattern does not guarantee that every generated pitch stays in the original song scale.

## Bass patterns

| `pattern` | What it is |
|---|---|
| `rolling_16` | Rolling bass, 16 hits per bar. The standard rolling bass: a note on every 16th, short gate. |
| `rolling_octaves` | Rolling bass with octave drama. Rolling 16ths, every second note an octave up for more drama. |
| `rolling_legato_octaves` | Rubbery legato octave roll. Same rolling pattern with octave pairs, notes overlapping (legato on a mono synth) for the rubbery sound. |
| `rolling_groove_gap` | Rolling bass without the first two notes. Delete the first two 16ths: the gap lets the kick through and adds groove. |
| `octave_jump_single` | One bass line, octave jumps. Simple and dramatic: long root notes answered by short octave jumps. |
| `octave_jump_extreme` | Extreme octave jumps (note follow). Jumps of up to two octaves; the synth's filter follows the note so the jump gets brighter. |
| `offbeat_fast` | Offbeat bass for fast tempos. At 150 bpm few notes sound fast: one bass note on every offbeat. |
| `offbeat_chord_octave` | Offbeat bass, sustained chord layer. The offbeat leaves room for a sustained bass on top that follows the chord progression; the last offbeat jumps an octave. |
| `tekkaos_phrygian` | Groovy tech house, Phrygian half notes. A short repeating figure, then half notes using the flat second of the Phrygian scale; the second bar adds an octave jump. Duck to the kick. |
| `hybrid_eighths_high` | Hybrid: 8ths low, patterns on the high bass. Eight bass notes per bar, heavily ducked to the kick, which frees the high bass for syncopated patterns; delay on the top layer. |
| `argy_fast_slow` | Fast and slow, off the grid. Few notes with long and short values mixed, played off the beat and not snapped to the grid so the groove stands out. |
| `argy_bumpy` | Same rhythm, bumpier. The fast/slow rhythm with octave bumps on the short notes. |
| `argy_up_down_high` | Up and down, pulled high. Alternating low/high 8ths; raise the register and open the filter for a slowly ascending feel. |
| `rolling_then_jump` | Less groove, more power: gaps, roll, jump. Leave spaces, start with a short roll and jump an octave; a bit of filter automation at the end of the phrase. |
| `kick_tumble` | Tumbling kick groove under any bass. A kick plus a second, very short kick create a 3-3-3-3-3-1 tumbling rhythm; any bass line can sit on top of it. |
| `rolling_bass_lead` | Rolling bass plus bass lead layer. Keep the rolling pattern and add a brighter, stronger bass lead with a different pattern; it changes the whole bar. |
| `tech_house_phrase` | Tech house phrase, developed over two bars. Phrygian: state a simple phrase in bar one (flat second on the downbeat), develop it in the next bar with a fifth an octave up. |
| `evil_semitones` | The evil semitone pattern. Start on one note, move up by a semitone, back, then one semitone below: semitones up, semitones down and one more down. |
| `evil_kick_locked` | Evil pattern locked to the kick, sidechained. Make a bass note where the kick hits and sidechain the other bass to that kick. |
| `rolling_bass` | Rolling bass. The root note, duplicated once, then once more, looped; sidechained so the kick cuts it off. The most common techno rolling bass line. |
| `offbeat_bass` | Offbeat bass. Two main notes, on the beat and off the beat, made bigger. The offbeat bass. |
| `groovy_bass` | Groovy bass with jumps. One note, a second one, then larger jumps and extended notes. Kick sidechain is one sound-design option; arrangement and envelope choices can also manage overlap. |
| `evil_spirits` | Evil spirits: semitone bass. Starts on the root and uses the power of semitones for a dark, evil bass line. |

## Lead patterns

| `pattern` | What it is |
|---|---|
| `descending_pedal` | Descending pedal-tone motif (Ben Bohmer). Fifth down to the second, restarted every bar: each note three 16ths after the last, the final one 16th restarts the loop and re-syncs to the kick. The eight bars vary at the start and the end. |
| `ascending_energy` | Ascending lead with pitch-bend inspiration. Tonic down an octave, then rising second, third, fourth, fifth; the last bar holds the second. Rising contour can suggest increased energy, but its effect depends on context. |
| `arp_third_start` | Looping arp starting on the third. Starts on the third instead of the root, falls, rises, ends on the fifth an octave up; it follows every chord of the song and keeps its pattern. |
| `half_step_trick` | Three-note figure emphasizing the half step between second and minor third, repeated with a small ending change. Returning to the root is an alternative resolution, not a mistake. |
| `bass_lead_bodzin` | Bass lead with octave jumps (Stefan Bodzin). Starts on the sixth and descends to the root in every progression, with high octave jumps and a little glide into the next note, even off-scale. |
| `top_note_complement` | Sparse top note over piano chords. A second lead above piano chords: seventh, second and third of the chord with a lot of space. Space is part of the melody. |
| `gated_vocal` | Gated vocal lead. Seventh on the first notes, the root an octave up after them; positions 1 and 3 with gaps instead of a stream of 16ths. |
| `triad_voicing_dance` | Wide triad voicing with a dancing top note (Oscar Mattke). Root, third two octaves up and fifth one octave up; long notes against short ones played off the kick every three 16ths; a little top-note dance in every second bar. Follows the bass line. |
| `chord_complement` | Lead that complements the chords. Starts on the third and mostly plays the third and fifth against the chord; one rhythm replicated through the song with small variations. |
| `lfo_chord_lead` | LFO chord lead (Lydian). Sustained chords following the bass; the movement comes from automation. Lydian (or Mixolydian, Dorian) gives a dreamy feeling instead of plain major or minor. |
| `third_of_bass` | Third of the bass line. The lead emphasizes thirds rather than roots or fifths, with 16th-grid accents beyond the kick positions. Roots and fifths are valid alternatives, not inherently boring. |
| `notes_and_chords` | Notes and chords alternating over a pedal tone. One bar plays chords, the next plays notes around a repeating pedal tone (fifth, sixth, third, second); notes and chords have a different character, so the repetition stays interesting. |
| `pitch_mod_one_note` | One note with pitch modulation. One note in different lengths on groovy 16th positions; the pitch bend gives it the movement, so it needs no melody. |
| `minor_chord_lead` | Minor chord lead with rave voicing. Tone an octave down plus third (and fifth); put the third and fifth up for the rave feeling. Lengths mix a 16th, a 32nd and an 8th. Use a different progression in the buildup and let it go at the drop. |
| `vocal_harmony_gated` | Gated vocal lead harmony. Gated notes with longer notes and gaps instead of 16ths; a second line adds a harmony voice in some bars so a chord progression emerges from the gated leads. |
| `gnarly_phrygian_bass_lead` | Gnarly bass lead in Phrygian. The flat second of Phrygian makes it dark and aggressive. Put the progression into the Phrygian scale instead of minor. |
| `emotional_pluck` | Emotional melodic techno pluck with call and response. The third of the bass an octave up as a rolling pluck with a few gaps; the complement plays tone and third an octave up in some bars only, so it is fresh each time. |
| `epic_descending_motif` | Epic descending motif. Answers the descending bass: the second and the third right above every bass note, as call and response; in the last bar of the phrase the pattern goes an octave up. |
| `one_note_lead` | One note lead over a moving bass. Two notes in an 8th rhythm that stay the same while the bass and chords change underneath; the bass does the heavy lifting. |
| `drama_octaves` | Octave-jump build-up. One note, the next an octave up, another octave up, then duplicated; add automation and the build-up carries drama. |
| `ambience_root_five_six` | Ambience: root, fifth, sixth, fifth. Count from the root to the fifth, hop to the sixth and back to the fifth, loop it: a quiet ambience for a dry techno track. |
| `ambience_chord_semitone` | Melancholic ambience: minor chord with a top semitone. Root, fifth of the minor chord, both doubled an octave up and the third on top: the melancholic ambience under a kick-only track. |

## Counter melody modes

`counter_mode` of a melody that has `counter_to` (a main melody clip). Ten values, six read the main melody's rhythm, four are figures. Provenance as in [COUNTER_MELODY.md](COUNTER_MELODY.md): `roll` = seen in the tutorials' piano roll, `described` = said in the voice-over or inferred.

| Mode | What it does | Provenance |
|---|---|---|
| `fill_the_gaps` | Plays inside the main's held notes and rests, sustains or stops when it returns. | `roll` |
| `call_and_response` | Answers in the silent beats and bars of the main. | `described` |
| `passive_over_active` | A third to half of a busy main's onsets, longer notes; more notes over a sparse one. | `described` + `roll` |
| `contrasting_rhythm` | An onset pattern that differs from the main's per bar. | `described` |
| `harmonic_notes` | Follows the main's onsets on another consonant note, never the same pitch class. | `roll` + `described` |
| `note_layering` | The main's own pitch classes an octave away, same time or delayed. | `roll` + `described` |
| `dotted_eighth_pulse` | Six onsets at 16th steps 1, 4, 7, 10, 13, 16; cyclic gaps 3-3-3-3-3-1, reset each bar, one chord tone per bar. Not continuous dotted eighths across bar lines. | `roll` rhythm interpretation |
| `scale_staircase` | The pulse climbing one scale step every one or two bars, one step back before the restart. | `roll` + `described` |
| `trance_dotted_eighth_staircase` | The Trance video's 8-bar figure, scale degrees 0 0 1 1 2 2 4 4, then the loop restarts. | `roll` rhythm, `described` pitches |
| `echo_gap_answer` | In a main note of 1.25 beats or more: 3-4 short stepwise notes, then one longer note that sustains under the re-entry. | `roll` |

All keep the register window (`counter_register`: above, below, same), avoid crossing the main and favor thirds, fifths, sixths or octaves to it on strong beats; a figure note that would clash moves to the nearest consonant scale tone. These and the parallel-fifth/octave restrictions are conservative engine choices, not universal musical rules. Shared rhythms, unisons, parallel motion and expressive dissonance can be intentional. `note_layering` may act as doubling rather than an independent line. Not built: `bass_mimic`, `timbre_split` (hint only); `octave_separation` is represented by `counter_register`, not a separate mode.

## Drum patterns (techno)

| `pattern` | What it is |
|---|---|
| `clap_16_build` | Clap on 16ths, a build-up. A normal clap on 2 and 4 becomes darker with a short attack; switch to 16ths with a rising velocity for a full-beat clap build. |
| `hat_16` | 16th hats with velocity play. One hat duplicated on all sixteen 16ths; the trick is the velocity: accents on the beat, soft between. |
| `hat_open_offbeat` | Open hat on the offbeat. The classic offbeat open hat on the 3rd 16th of every beat; boring alone, so it wants accents around it. |
| `hat_open_accents` | Open hat with accents around it. The offbeat open hat plus short closed-hat accents on the 16ths around it, which makes the pattern better. |
| `hat_triplets` | Sixteenth-note triplet hats: six hits per quarter-note beat instead of four straight sixteenths. |
| `kick_rumble` | Rumble: kick resampled to a bass. The kick routed to a second channel with lots of effects and resampled; one transient on the last quarter (laid back a little), another on the offbeat, extended, so the transition is obvious. |

## Emotion progressions (chords)

Names describe the intended preset character, not a reliable emotion classifier. Roman numerals below follow the **engine's notation**: in minor, III, VI and VII refer to natural-minor scale degrees. The suffix `7` adds the diatonic seventh where the numeral's case matches the scale's triad quality, so `III7` in C minor is **Ebmaj7**, not Eb7. For example, `groove_funk` in C minor gives Cm7, Ebmaj7, Fm7, Fm7. These conventions are not a universal Roman-numeral standard.

| `pattern` | What it is |
|---|---|
| `uplifting_sweet` | Uplifting sweet. The 6, 1, 3 and 7 of the minor scale: triads with the thirds an octave up, the roots copied an octave down, and the tonic as a pedal tone because the chord changes are big. Progression: `VI i III VII` (minor). |
| `groove_funk` | Minor-key seventh chords on degrees 1, 3 and 4, with lowered roots and upbeat hits. Progression: `i7 III7 iv7 iv7` (minor). The tutorial's sus2 suggestion is not encoded by that progression. |
| `dark_cinematic` | A single minor chord held for the phrase, leaving room for texture and orchestration. It can support a dark character, but is not inherently the "darkest" choice. Progression: `i` (minor). |
| `dark_serious` | Minor-key motion through degrees 1, 6, 4 and 5 with triads and a low register. Simplifying upper voices is an arrangement option, not the best solution for every vocal. Progression: `i VI iv v` (minor). |
| `pure_joy` | Pure joy. 6, 4 and 1 in a major scale, closed with one more chord, the ii (D minor in C); roots pulled down an octave, thirds on top, fifths pulled down, tonic as the pedal tone. Progression: `vi IV I ii` (major). |
| `funk_light` | Degrees 1, 7, 3, 4, 6, 7 in minor, with sevenths on the first, fifth and sixth chords and upbeat hits. Adding sevenths to other chords is also valid. Progression: `i7 VII III iv VI7 VII7` (minor). |
| `happy` | Happy. 6, 4, 1, 5 in any major scale; the first chord is shortened so the next starts on the upbeat; roots down an octave and no fifths; a classic synth and a fun rhythm. Progression: `vi IV I V` (major). |
| `sad` | Sad. Long drawn out chords (two whole notes each) moving down; roots doubled, a seventh, a ninth and a passing note; a pedal tone on the tonic and cellos to go one step further. Progression: `i VII VI v` (minor). |
| `bittersweet` | Degree 6 held for two whole notes, then tonic and degree 7 for one whole note each. Voicing and performance determine whether it reads as bittersweet. Progression: `VI VI i VII` (minor). |
| `dreamy_indie` | Half-note chords on degrees 1, 6, 3 and a chromatic major II, with raised thirds, doubled roots and tonic pedal. In C minor: Cm, Ab, Eb, **D major** (F# is outside C natural minor). This is an intentional color, not a correction to an invalid diminished chord. Progression: `i VI III II` (minor with chromatic II). |
| `sad_neutral` | Sad neutral. Whole-note chords descending 1, 7, 6, 7 in a minor scale, thirds on top. Musical sad, not cinematic; a pedal tone on the tonic crushes it deeper. Progression: `i VII VI VII` (minor). |
| `heroic_pivot` | Heroic pivot (sad neutral turned hopeful). The sad neutral progression pivoted: the first chord goes to the 6, the 6 takes the place of the 1, and the pedal tone moves to the third degree (the relative major tonic): more hopeful, more heroic. Progression: `VI VII i VII` (minor). |
| `melancholic` | Melancholic. 1, 3 and 5 of a minor scale; melancholic progressions love pedal tones, notes that stay through the whole progression and carry a dreaminess; re-voice the chords up high. Progression: `i III v` (minor). |
| `resolute_major` | Descending roots from a major tonic with borrowed **bVII**, not a purely diatonic major progression. In C: C, **Bb**, Am, G. "Resolute" is the intended preset character, not a guaranteed perception. Progression: `I bVII vi V` (major with borrowed bVII). |
| `euphoric_neutral` | Degrees 5, 6, 1 and 7 in minor, with triads, raised thirds and a double pedal tone. Its intended euphoric character depends on voicing, sound and performance. Progression: `v VI i VII` (minor). |

## Which controls take effect

Three intentions: **generate** a new idea, **follow** existing clips (`chords_from`, `follow_kick`, `counter_to`), **vary** existing material (transforms). A named `pattern` is a fixed figure: it reads the harmony, meter, bars and `swing`, and ignores the generic style fields. `generate` reports explicitly set fields that were not read as `ignored`; defaults are never listed.

| Kind | With `pattern` | Without `pattern` |
|---|---|---|
| `bass` | reads `swing`; ignores `style`, `octave`, `density`, `kick_relation`, `follow_kick` | `offbeat`, `walking` and `sustained` sit on fixed pulses and ignore `swing`; the other styles read it |
| `chords` | ignores `rhythm`, `low`, `high`, `voices` | all read |

A mood `pattern` supplies its own progression and, unless `chords_per_bar` is given explicitly, its own chord rate, in standalone `generate` as in `compose`. The Max MIDI Tool has no pattern menus. `plan_song` uses genre recipes, not these named patterns; a copied `clips.chords` clip is not read for harmony (see its warning).

The Max MIDI Tool sends the meter when Live's tool context provides one (unverified in real Live; otherwise 4/4) and no Drum Rack pad context (drums use General MIDI pitches). Without a clip scale it uses C major.
