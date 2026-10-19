# Genre recipes for the song engine

Starting points for House, Melodic Techno, Peak-Time Techno, Drum & Bass and EDM Trap, compiled from trade articles and tutorials (as of October 2026). The templates in `packages/core/src/midibakery/compose/structures.py` and the generators implement selected recipes, not definitions of these genres or guarantees of professional results.

**How to read the evidence:**
- **●** several cited sources describe the approach; agreement among tutorials is not independent validation
- **◐** one source or differing examples; the variants are listed
- **○** an editorial suggestion without an explicit source

These markers describe sourcing, not musical correctness. An **observed example** describes a particular track or tutorial; a **preset choice** is an engine default; an **implemented constraint** is a software limit, not a rule of music. The implementation table below records defaults. Standards and professional guidance used in this review are linked under [Review sources](#review-sources); the older genre source lists are research leads, not a fully traceable bibliography. Unlinked article claims and tutorial reconstructions still need exact URLs and, for videos, timestamps before being presented as verified transcriptions.

**Notation:**
- Steps count within a bar of 16 sixteenths, step 1 = beat 1. Step 5 is beat 2, step 9 beat 3, step 13 beat 4. The offbeats are 3, 7, 11 and 15.
- MIDI notes are as in Live: 60 = C3. Sources name octaves differently, so registers here are converted via frequency.
- Swing uses two different conventions here: an **MPC-style ratio** has 50 % = straight and about 66.7 % = triplets. The engine's **swing strength** runs from 0 = straight to 1 = triplets: 0.6 gives a 60 % ratio; 0.15 gives about 52.5 %. Live's Groove Pool Timing and Global Amount scale a selected groove and have no universal conversion to either convention. Unspecified percentages quoted from tutorials cannot be converted without knowing their controls.

Recipes are conventions, not laws. Judge the result with listening and level-matched references. The Reference Analyzer estimates sections, key and tempo from audio; its band-energy lanes are proxies, not isolated instruments. Verify its labels and grid before using `plan_song` with `reference` to follow the estimated structure (see below).

---

## Common starting points for these templates

- **●** Sections commonly use multiples of 8 bars, often 16 or 32; shorter, extended and asymmetric phrases also work.
- **●** Small changes every 4 to 8 bars and larger changes every 16 bars are useful defaults, not a schedule every track must follow.
- **●** Fills and drop-outs often anticipate a phrase change.
- **●** Sparse drum-led intros and outros can help DJ mixing. Bass content and the order of exits depend on the track and mix strategy.
- **●** Removing the kick or leaving silence before a drop is one way to create contrast; continuous transitions are valid too.
- **●** A second drop can develop the first through variation, subtraction or a change in energy; it need not be louder or busier.
- **●** Velocity accents can separate main hits from ghosts. Constant kick velocity can be intentional. MIDI velocity percentages are not dB: loudness and timbre depend on the instrument's velocity response.
- **●** Kick and bass need compatible timing, envelopes and spectral balance. Gaps, overlap, sound selection, EQ and sidechain are alternative or complementary tools; sidechain is not mandatory.
- **●** Minor-key loops with 2 to 4 chords over 2 to 8 bars are common in these examples, but major, modal, chromatic and single-note material are valid.
- **●** A recognizable motif with repetition and variation helps establish a hook. Register, rhythm and timbre can separate it from other parts without always placing it an octave above the chords.
- **●** Useful checks are development, intentional density, phrase contrast and low-end clarity. Straight grids and repeated velocities are not mistakes by themselves.

---

## House

A family of mainstream, deep and tech house. Deep house is slower and jazzier, with seventh and ninth chords. Tech house is drier and more percussive; the hook is often a tuned percussion riff.

**Tempo and swing**
- **●** The selected examples center on 120–128 BPM: deep house 120–124, mainstream 124–126, tech house 125–128. These are reference ranges, not genre boundaries.
- **◐** Sixteenth swing at an MPC-style ratio of 55–65 % is one approach. The engine default is **strength 0.6, equivalent to 60 %**. Swinging several parts together is an option, not a requirement. The previously cited 75 % example needs its original control convention verified and is outside the engine's current triplet-limited range.

**Structure** (phrases 8/16/32)
- **●** Intro 16–32 bars, drums first. Elektronauts recommends a sparser 8–16 bars with at most 2–3 elements.
- **◐** A common scheme: intro 16–32, build 8–16, drop 32, breakdown 16–32, drop 2 32, outro 16–32.
- **◐** Length: an analysis of 63 records gave a median of 4:31 for extended mixes and 3:31 for radio edits. Club mixes are often 6–7 minutes long (○).

**Arrangement**
- **◐** Native Instruments: beat and chords from bar 1, an organ from bar 9, the first lead line from bar 17. A riser every 16 bars, an FX hit when the bass enters.
- **●** Risers over 8 or 16 bars that resolve exactly on a phrase boundary. Add a filter sweep, a snare roll and, in the breakdown, no kick.
- **◐** Fills (909 toms and snare) every 8 bars, slightly different each time. The strongest signal is saved for the biggest change.

**Drums**
- **●** Kick on 1, 5, 9, 13.
- **●** Clap or snare on 5 and 13, often two claps layered. At Attack a few milliseconds early.
- **●** Open hat on the offbeats 3, 7, 11, 15, quieter than the kick (NI: velocity 83).
- **◐** Closed hat: at Loopmasters on the 1st, 2nd and 4th sixteenth of each beat; the 3rd stays free for the open hat. At Attack (Soulful), on the other hand, on the beats.
- **◐** Shaker on all 16 steps with varying velocity, quiet. It carries the swing.
- **◐** In tech house additionally a ride on every beat.
- **◐** Ghost notes: a clap about 6 dB quieter on the first sixteenth after the last clap of a 2-bar loop. In tech house, ghost snares just before the kicks.
- **◐** Variation: crash at the start of each 2-bar sequence, open hat only in the second half of the drop, fill every 8 bars.

**Bass**
- **●** Between the kicks or on the offbeats (steps 3, 7, 11, 15), with sidechain to the kick.
- **◐** Note length: short on the beat (about 60 % of a sixteenth), long on the offbeat (90–100 %). Monophonic, no overlapping notes.
- **◐** Register: root at about 35–70 Hz, i.e. **MIDI 25–37**. A layer one octave higher can be added.
- **●** Follows the chord roots and sometimes moves to the third.

**Harmony**
- **●** Mostly minor. Deep house uses m7, maj7 and m9 chords.
- **◐** Progressions from the sources: two chords (i–bVII), i–v–iv, i–bIII–v. 1–2 chords per bar in loops over 2 or 4 bars.
- **◐** Stabs: short chord hits (m7/m9) with a short envelope, about a sixteenth to an eighth long (○). Pads sit in the background.
- **◐** Close voicing so the loop flows. About C3–C5, i.e. MIDI 60–84 (○). Pads with a low-pass around 400 Hz.

**Lead and hook** (thinly sourced)
- **◐** Sparse. Call and response: the call short, the response longer and at a different pitch. A variation follows 4 bars later.
- **◐** In tech house the hook is often a tuned percussion riff (clave, cowbell).
- **○** Motifs over 2–4 bars, 3–8 notes per bar, mostly chord tones, rests on the one, about an octave above the chords.

**Sounds** (native Live devices)
- Drum Rack with a 909, 808 or CR-78 kit.
- Bass with Simpler (MS2 filter, drive), Drift or Analog.
- Chord stabs with an organ or electric piano sound: Operator, Electric, Wavetable or Simpler with a chord sample.
- Effects: Reverb, Echo, Auto Filter.

**Filter sweeps** (Auto Filter, clip automation)

| Section | Drums (high-pass) | Chords (low-pass) |
|---|---|---|
| Intro | open | from bar 9: 150 Hz → 20 kHz, opens late |
| Build, Build 2 | 20 → 400 Hz or 500 Hz | open |
| Break | 150 Hz, thin | 200 Hz → 20 kHz, opens late |
| Outro | open (kick stays for the DJ) | 20 kHz → 150 Hz over 8 bars |

The drops are open. In the break the chords' resonance rises with the cutoff from 5 to 40 %. Delay throws: in the drop the lead throws into the delay on the last beat of every 8th bar.

**Sources:** Ableton Learning Music (tempo); EDMProd "Classic Deep House"; Native Instruments "Deep House Track"; Attack Magazine Beat Dissected (Soulful Deep House, Deep Tech House, Chugging Tech House, Dusted Deep House); Attack Passing Notes (Deep House Chords); Attack Deconstructed (Tiga "Bugatti"); Mixed In Key (arrangement); Mixgraph (intro, riser); Loopmasters (Tech House Beat & Bass); The Producer School and Boombox (tech house basslines); Mode Audio (Deep House Chords); MusicRadar (m9 chords, hooks); EDMProd (call and response); Violet Recording (House); forums: Gearspace, Elektronauts, KVR, DJTechTools (weaker sourcing).

---

## Melodic Techno

The melodic techno examples (e.g. Afterlife: Anyma, ARTBAT, Stephan Bodzin) emphasize harmonic loops, pads and an arpeggio or lead hook. Raw and industrial approaches are outside this preset's scope; tempo and tonality alone do not define the boundary between styles.

**Tempo and swing**
- **●** The selected slower examples use 120–125 BPM; the engine default is 122. Attack's deep melodic beat sits at 120–123. This is not a limit on the genre.
- **◐** Light swing on hats and percussion, with a straight kick, is the preset choice. The engine uses **strength 0.1, about 51.7 % MPC-style ratio**. Attack's quoted 10 % and Beatportal's "subtle" are not interchangeable measurements without the original groove settings.

**Structure**
- **●** Sections are multiples of 8 bars. DJ intro and outro with 16–32 bars of drums and percussion.
- **◐** Beatportal: intro 16 (kick, hats, atmosphere), build 16 (adding bass, pads, FX), drop 16, breakdown 16 (only pads and FX), climax 16.

**Arrangement**
- **◐** Native Instruments:
  - Bars 1–8: kick, hats, percussion, pad.
  - From bar 9: clap, shaker, rim, noise and bass.
  - From bar 17: lead.
  - From bar 25: shaker and rim drop out.
- **●** Open the pad filter over 16 bars, sweep the bass low-pass through breakdowns and builds. Risers and impacts sparingly, a sub drop before each drop (Beatportal).

**Drums**
- **●** Kick on 1, 5, 9, 13, clap on 5 and 13. Attack instead uses a syncopated clap at the end of every second bar, plus a double hit every 4 bars.
- **●** Closed hat on the offbeats plus a quiet sixteenth layer. Shaker in sixteenths, the rim slightly ahead of the upbeats.

**Bass**
- **●** Follows the chord roots. NI changes the root every 2 bars.
- **◐** Suggested register about MIDI 32–48 (Live G#0–C2, about 52–131 Hz); octave names in source DAWs may differ.

**Harmony**
- **●** 1 chord per 1–2 bars in a loop over 4–8 bars. Examples: Am–F–C–G, Am–Dm–Em–C.
- **◐** Pads in 2–3 layers (bright, mid, low) with slow attack. Natural minor, alternatively Phrygian or Dorian.

**Lead**
- **◐** Simple arpeggio in the key. NI keeps a 1-bar rhythm with short stutter notes and shifts it onto the chord tones every 2 bars.
- **○** Sixteenth grid, 4–10 notes per bar, MIDI 60–84.

**Sounds:** Pads and leads with Wavetable or Drift, long reverb and delay (1/8 or 3/16). Bass with Analog or Drift.

**Filter sweeps** (Auto Filter, clip automation): slow opening is part of the genre's long builds.

| Section | Drums (high-pass) | Pads (low-pass) | Arp (low-pass) |
|---|---|---|---|
| Intro | open | 150 Hz → 3 kHz | – |
| Build | open for 12 bars, then 20 → 200 Hz | 3 → 20 kHz, opens late | from bar 9: 500 Hz → 2 kHz |
| Drop | open | open | 800 Hz → 6 kHz over 16 bars, back to 3 kHz |
| Breakdown | – | 150 Hz → 8 kHz, opens late | 600 Hz → 2.5 kHz |
| Build 2 | 20 → 350 Hz | open | 2.5 → 10 kHz |
| Climax | open | open | 2 → 12 kHz |
| Outro | open | 12 kHz → 150 Hz over 8 bars | – |

In the build the pads' resonance rises from 10 to 35 %. Delay throws: in the breakdown the arp throws into the delay on the last beat of every 8th bar.

**Sources:** Beatportal (Melodic House & Techno: Anyma, Miss Monique, ARTBAT, Stephan Bodzin); Native Instruments (Melodic Techno); Attack Magazine (Deep Melodic/Progressive Techno).

---

## Peak-Time Techno

The peak-time preset draws on the Beatport category "Peak Time / Driving" and selected material associated with Adam Beyer, Amelie Lens, Charlotte de Witte, Enrico Sangiuliano, Layton Giordani and Eli Brown. It emphasizes percussion, gradual change and limited harmonic movement. This is one approach within a broad category; big drops and more harmonic material also occur.

**Tempo and swing**
- **●** The selected examples include 126–132 BPM, with 128 as the template starting point, and faster material around 135–138. There is no hard 140 BPM boundary between peak-time and hard techno: era, sound and scene also matter.
- **●** The tempo has been rising for years: long around 127, then the wave at 150 and above (Attack, MusicTech).
- **●** A straight kick and bass with lightly swung hats, shakers and percussion is the preset choice. The engine uses **strength 0.15, about 52.5 % MPC-style ratio**; the quoted 0–20 % tutorial amounts are control-dependent.
- Default: **128 BPM** like the reference below.

**Structure** (sections as multiples of 8 bars, usually 16 or 32)
- **◐** EDMProd: DJ intro, breakdown, drop, drop variation (32+), breakdown, drop, outro, each 16–32 bars.
- **◐** Beatportal (converted at 128 BPM): intro ~32, build ~32, drop ~16, breakdown ~32, drop 2 ~32, outro breaking down.
- **◐** Proposal for the engine, about 192–224 bars (6–7 minutes at 130 BPM): intro 32, groove A 32, breakdown 1 16, peak 1 32, groove B 16–32, breakdown 2 16–32, peak 2 32, outro 32.
- **●** Intro and outro with 16–32 bars of drums only. In the outro the bass goes first, and it is not a copy of the intro.
- **●** Something changes every 8 bars; every 16 bars a fill or impact marks the phrase. Per 8 or 16 bars only one dimension changes (filter, decay or accent).
- **◐** Breakdowns of 8, 16 or 32 bars (Attack: 24 = 3 × 8, or 32). The kick is out. Percussion, clap, offbeat hat, a high-pass-filtered bass, texture and the hook keep running.
- **●** Tension without a big drop: the peak runs at least 32 bars, optionally with mini breaks of 1–2 bars inside. Often it is enough to briefly remove kick or bass; a riser is not needed.

**References** (analysis from October 2026; per-bar onset and band-energy estimates, not isolated kick, bass or synth measurements. Tempo/key and the musical interpretations below need listening verification; melodies cannot be transcribed from these lanes):
- Y-Traxx – Mystery Land (Spektre Remix): 128 BPM, A minor, 7:30, about 232 bars.
- Katoff – The Signal: 126 BPM, D# minor; only a 3-minute version without DJ intro and outro.
- T78 – Nezquik (Original Mix): 128 BPM, A minor, 7:00, about 220 bars.

Working interpretations of all three (not independent source-separation results):
- **●** Before each big drop the bass goes first for about 8 bars, then the kick is filtered out over 3–5 bars. The last 2–3 bars run without kick, and exactly then the synth is loudest.
- **●** In the outro the bass goes first, then the kick; at the end the hats remain.

Working interpretations of two of three:
- **◐** After a breakdown the hats come in late: 8–16 bars of kick, bass and synth with few hats, then full (Katoff, T78).
- **◐** After a peak, 8 bars of only kick and bass, without hats and synth (Spektre, T78).
- **◐** In the breakdown without kick the bass keeps rumbling quietly (Katoff, T78).

Individual-track interpretations:
- **◐** T78 removes kick and bass for one bar at the end of many 8- and 16-bar phrases.
- **◐** Katoff puts a synth accent at the start of every 8-bar phrase in the groove and, in the breakdown, plays the synth alternating 2 bars on, 2 bars off, with 2 bars of silence before the drop.

The template combines the three, 224 bars, i.e. 7:00 at 128 BPM:

| Bars | Section | What happens | Model |
|---|---|---|---|
| 1–32 | Intro | Kick and hats, the bass after 16 bars | Spektre |
| 33–48 | Groove | Synth accent on every phrase start, 1-bar pause of kick and bass at the end of each phrase | Katoff, T78 |
| 49–64 | Lift | 8 bars without bass, then the stabs come in, the kick goes after 12 bars | all three |
| 65–96 | Peak | Everything plays, 1-bar pause at the end of every 16 bars | T78 |
| 97–120 | Breakdown | Without kick: rumble bass, the hats go after 8 bars, synth alternating, 2 bars of silence | Katoff, Spektre |
| 121–152 | Peak 2 | 8 bars with few hats, then full | Katoff, T78 |
| 153–160 | Lift 2 | Without bass, the kick goes, the acid line stays | all three |
| 161–176 | Peak 3 | Everything plays | T78 |
| 177–184 | Stripped | Only kick and bass | Spektre, T78 |
| 185–224 | Outro | 24 bars of groove without hook, then the bass goes, then the kick, finally the hats remain | all three |

In the references the kick is often filtered out instead of ending hard. The engine does this with one Auto Filter per track whose cutoff it automates per clip (`sweeps` in the template):

| Section | Drums (high-pass) | Chords (low-pass) | Lead (low-pass) |
|---|---|---|---|
| Lift | open for 8 bars, then 20 → 300 Hz | 200 Hz → 20 kHz, opens late | 600 Hz → 2.5 kHz |
| Peak | open: the kick is fully there at once | open | 400 Hz → 5 kHz over 24 bars, back to 1.5 kHz |
| Breakdown | 250 Hz, thin | 150 Hz → 9 kHz, opens late | 800 Hz → 3 kHz |
| Peak 2 | open | open | 800 Hz → 8 kHz over 16 bars, back to 2 kHz |
| Lift 2 | 20 → 400 Hz | open | 2 → 12 kHz |
| Peak 3 | open | open | 6 → 3 kHz |

Resonance: in the lift it rises on the chords from 0 to 50 %. The acid line gets sharper in the peaks (Peak 20 → 60 % over 24 bars, back to 30 %; Peak 2 30 → 70 %, back to 40 %; Lift 2 40 → 75 %). Delay throws: the chords throw into the delay in groove and breakdown on the last beat of every 8th bar.

Every clip of a filtered track gets an envelope, even if it is only "open". That way no filter from the previous section stays stuck.

Instead of a straight line, a section can also run a curve or wave: `300>8000~exp` starts slowly and opens fast at the end (`~log` the other way round), `400>3000~sine/2` oscillates between both values every 2 bars (also `triangle`, `saw`, `square`).

**Arrangement**
- **●** Introduce elements one at a time. Rides only come in the drop. The hook is already hinted at in the intro, quiet and filtered.
- **●** The last 8 bars of a breakdown:
  - Riser, clap roll and accelerating percussion.
  - The snare roll gets louder and denser, 32nds at the end.
  - The lows are filtered away with a high-pass until the drop.
  - A sub drop hit on the one of the drop.
- **◐** Clap rolls in sixteenths in bar 4 from beat 2, every 4 bars (EDMProd).
- **◐** Kick edits: extra kicks, the kick removed at the end of a section, reverse kicks.
- **●** "The moment": the hook (stab or lead) is introduced in the breakdown and comes back with full force in the drop. Save the strongest lead for the last drop.

**Drums**
- **●** Kick on 1, 5, 9, 13, short and punchy. It runs through, except in the breakdown.
- **◐** Ghost kick on step 4 and/or 12. "Rolling" variant: quiet offbeat kicks on 3, 4, 7, 8, 11, 12, 15, 16, about 10 dB quieter (Attack).
- **◐** Clap, here the sources disagree:
  - Beatportal: sparingly on 5 and 13.
  - EDMProd: no house clap, but syncopated snares around steps 1–2 and 7–8 in a 2-bar cycle.
  - Charlotte de Witte does without claps entirely and layers up to seven hat and cymbal sounds.
  - Default: clap optional and sparse.
- **●** Closed hats in continuous sixteenths with "dancing" velocity. Offbeat hat (often open) on 3, 7, 11, 15. An open hat on 2 and 4 with gaps, one of them late by about 50 %.
- **◐** Ride on every eighth (odd steps), quieter on beats 1 and 3 so it ducks against the kick.
- **◐** Percussion: toms alternating in sixteenths. Rim on the kick steps and on 6 and 14, a low tom on 14. Ghost claps around the main clap.
- **○** Velocity: kick 127, main hits 100–115, hats alternating around 70 and 100, ghosts 30–55.
- **○** Variation: a 1-bar core, a 4-bar turnaround (fill in the last 2 beats), a section change every 8 or 16 bars.
- **◐** Rumble is sound design: a sub or rumble tail under a punchy transient, a sixteenth delay on a copy of the kick, filtered and distorted.

**Bass**
- **●** **Rolling sixteenths**; the first sixteenth of each beat stays free for the kick: steps 2–4, 6–8, 10–12, 14–16. Usually one note, occasionally another. Variant: offbeats only (3, 7, 11, 15).
- **◐** A top bass with the same rhythm and octave jumps. EDMProd jumps an octave on every second repetition.
- **◐** Note length: a sixteenth with 70–90 % gate, short gaps (Producer School). EDMProd uses 99 %.
- **●** Register:
  - Sub MIDI 28–36 (41–65 Hz).
  - Rolling mid bass MIDI 36–48 (65–131 Hz). Attack's main note sits at 98 Hz, i.e. MIDI 43.
  - Acid one octave above the bass.
- **●** Tuning a sustained, pitched kick to the root is one approach, not a requirement for every kick. Check its decay and interaction with the bass as well as pitch; matching pitch alone does not ensure phase compatibility. MIDI 30–35 is about 46–62 Hz. Attack's F example is 43.65 Hz, MIDI 29 (Live F0).

**Stabs, synths and hooks**
- **●** Hook: a 1–2-bar loop, minimal and repetitive. It moves via cutoff, resonance and LFO, not via new notes. A 3-note motif (root, fifth, minor seventh) with rests.
- **●** **Parallel stabs:**
  - A minor triad shape is shifted as a block, even out of the key, always in the same inversion.
  - Each hit is one sixteenth long, mostly off the one.
  - 2 bars become 4 by muting or moving 1–2 hits.
  - ○ About 3–6 hits per bar.
- **●** **Acid** in 303 style: a sawtooth or square-wave sound with a repeating sequence. Selective slides and accents are one way to create contrast; slide behavior depends on the instrument and is not restricted to short notes. Cutoff and resonance provide movement.
- **◐** Riff variation: change one parameter every 8–16 bars or swap one note every 8 bars; the core stays.
- **◐** Register of the stabs MIDI 60–79 (C3–G4).
- **●** Vocals as short, repeated snippets, often also toward the end.

**Harmony**
- **●** Some examples have little harmonic movement and emphasize texture or percussion. A single-note riff, drone or chromatically shifted stab is not necessarily atonal; use "atonal" only when no tonal center is established.
- **●** Minor, e.g. F minor or E minor. One chord or a drone is standard. A shift between two chords adds movement.
- **◐** A minor triad in root position, optionally with the root doubled an octave higher. Chords, if at all, appear in the breakdown.

**Sounds** (native Live devices)
- Kick: Drum Rack with a 909 sample or Kick Analog, Drum Buss with "Boom" on the root, Saturator.
- Rumble: kick send into Echo (1/16) and Hybrid Reverb, then Auto Filter (low-pass ~80 Hz), then Roar.
- Mid bass: Analog or Drift (sawtooth, short filter envelope). EQ Eight with high-pass around 65 Hz and low-pass around 350 Hz, Multiband Dynamics instead of OTT, Compressor with sidechain to the kick.
- Acid: Drift or Analog, mono and legato, resonant low-pass, plus Roar and Saturator.
- Stabs: Wavetable with detuned saws or square, Roar, Echo ping-pong, Hybrid Reverb (~1.5 s).
- FM hits: Operator. Vocals and textures: Simpler. Filter sweeps: Auto Filter.

**Checks before finishing:** unintended distortion, low-end masking, an outro that does not serve the intended mix, too many layers too early, and slides or accents that have lost their contrast. Sidechain and arranging into a limiter are workflow choices, not requirements or mistakes by themselves.

**Sources:** Beatportal (peak-time/driving in the style of Layton Giordani, Eli Brown, Adam Beyer); Mixed In Key (techno arrangement); EDMProd (How to Make Techno); The Producer School (Drumcode Beats); Attack Magazine (Rolling Techno, Big Beat Techno, Warehouse Rolling Bass, Parallel Chord Stabs, Techno Synth Stabs, Effective Breakdown, tempo trend); MusicTech (Sam Paganini); Lost Stories Academy (DJ-friendly); Production Music Live (Techno); Skiddle (interview with Charlotte de Witte); Aulart (kick tuning, Hannes Bieger); Roland (TB-303); Elektronauts and Ableton forum (weaker sourcing).

---

## Drum & Bass

Three flavors:
- **Liquid:** pads, Rhodes, groove via velocity and micro-timing.
- **Dancefloor:** poppy chords.
- **Neurofunk:** Reese and FM basses, short stabs and a focus on sound design. This need not be atonal.

**Tempo and swing**
- **●** 170–176 BPM, standard **174**. Liquid 170–176, neuro 172–174, halftime 170–175 (feels like ~87).
- **◐** Swing on hats with straight kick and main snare is one approach; shuffled breaks and micro-timed snares are also valid. The cited 52–60 % range is MPC-style. The engine's lighter default is **strength 0.1, about 51.7 % MPC-style ratio**.

**Structure** (phrases 4/8/16/32/64)
- **●** Intro 16–32, build 8–16, drop 32–64, breakdown 16–32 without drums, build 2 8–16, drop 2 32–64 (harder, different bass), outro 16–32. About 256 bars, just under 6 minutes. At 174 BPM one bar lasts about 1.38 seconds.
- **◐** KAN template: intro 32, build 16, drop 64 (2 × 32), middle part 16–32, breakdown 32, build 16, drop 2 64, outro 32. Shorter versions (EDMProd Liquid: 6 × 16 = 96 bars) and radio edits of 3–4 minutes are also common.
- **●** Small changes every 4–8 bars, bigger ones every 16 bars. Drop 1 often consists of 4 phrases of 16 bars, each with something added or left out.
- **●** Intro and outro with drums and percussion, little or no sub, mids sparse in the intro.

**Arrangement**
- **◐** Something new in the intro every 8–16 bars. At KAN the first bass hit comes in bar 17.
- **●** Build: noise riser, opening filter, snare roll (sixteenths to 32nds, velocity from 50 to 100 %, possibly 1–2 semitones up), extra hats. Build 2 is more dramatic than build 1.
- **◐** EDMProd Liquid: drums fully out 4 bars before the drop, the kick in quarters, then eighths, then sixteenths. Crash on beat 1 of the drop.
- **●** Short silence before each drop. Don't put every change on bar 1 of a section.

**Drums**
- **●** Two-step: **kick on 1 and 11, snare on 5 and 13**. KAN puts the second kick on 9.
- **◐** Variants: rolling/liquid with kick on 1 and 7 and a break loop over all 16 steps. Halftime with kick on 1 and 7, snare on 9. Amen/jungle with kick on 1, 3, 11, 12 and ghosts on 8, 10, 16.
- **●** Ghost snares on 3, 8, 10, 16, velocity 30–50. A "skip" snare on step 12 every second bar at 50–70. At most 1–2 ghost kicks per 2 bars.
- **◐** Hats in eighths or sixteenths at 70–80 % with random velocity (KAN: alternating 100/70). Ride in eighths.
- **◐** Main snares: the first about 90 %, the second 100 %.
- **◐** Variation: shuffles in every fourth bar, a ghost kick at the end of every eighth bar, leave out the first kick every second bar.
- **●** Breaks (Amen, Think, Apache) chopped and rearranged, filtered from 150–200 Hz, layered under kick and snare. This needs samples; the API cannot load any.

**Bass**
- **●** Two layers: a sub (sine or triangle, mono, release 300–600 ms) and a mid or Reese bass (two detuned saws, filter, distortion, filtered from 80–100 Hz).
- **●** Suggested sub register: **MIDI 27–32** (Live D#0–G#0, about 39–52 Hz). This is not a lower limit: choose register, harmonics and key for the material and playback system rather than assuming particular keys guarantee weight.
- **◐** Liquid: long, sustained notes that follow the chords. Neuro and jump-up: one-note basslines with rhythmic variation. Keep sub notes short, with sidechain.
- **◐** EDMProd Liquid: a 4-bar line as a 16-bar loop, an extra run in every second 4-bar block, the last 2 beats of the 16 bars muted.

**Harmony**
- **●** Mostly minor. Liquid uses m7 and maj7 chords in Dorian or natural minor.
- **●** Progressions: i–VI–III–VII with **2 bars per chord**, i–III–VI–iv (liquid), i–VII–VI–VII, i–iv–v. Pad loops with 2–3 chords.
- **◐** One suggested chord register is **MIDI 48–72 (Live C2–C4)**. Higher voicings also work; avoid low-register density when it masks the bass rather than imposing a universal lowest note.
- **●** Liquid with sustained pads, Rhodes or piano. Neuro with short stabs and drones. Dancefloor with poppy chords.

**Lead and melody** (thinly sourced)
- **◐** A 4–8-bar loop that returns with variation, plus syncopation and triplets. Only one hook. At EDMProd an 8-bar bell counter-melody, repeated an octave higher.
- **◐** Call and response over about half a bar. Passing and neighbor tones can add motion; a chord-tone-only melody is also valid and does not determine the genre.

**Sounds**
- Sub: Operator or Drift (sine).
- Reese: Analog with two oscillators detuned by ±0.27 semitones, mono (Attack's patch), alternatively Wavetable.
- Neuro bass: Operator or Wavetable with Roar or Saturator.
- Pads: Wavetable or Drift.
- Keys: Electric.
- Bell or pluck leads: Simpler or Operator.
- Breaks: Simpler in Slice mode.

**Filter sweeps** (Auto Filter, clip automation)

| Section | Drums (high-pass) | Chords (low-pass) |
|---|---|---|
| Intro | open | 200 Hz → 20 kHz, opens late |
| Build | 20 → 500 Hz | open |
| Breakdown | – | 150 Hz → 8 kHz, opens late; resonance 0 → 35 % |
| Build 2 | 20 → 600 Hz | 8 → 20 kHz |
| Outro | open | 20 kHz → 150 Hz over 16 bars |

Delay throws: in the drop the lead throws into the delay on the last beat of every 8th bar.

**Sources:** KAN Samples (DnB Drums, Arrangement, Chord Progressions); DnB Academy (Drum Patterns, BPM & Structure); EDMProd (How to Make DnB, Liquid DnB); Attack Magazine (Raw DnB, Incessant DnB Beat, Reese Bass Redux); Unison (DnB Drum Patterns, How to Make DnB); Violet Recording (DnB); Beatportal (Sub Focus / Delta Heavy); iZotope (Basslines); Beat Kitchen (Swing); MusicRadar (Liquid Chords, excerpt only); forums: DnB Forum, DJTechTools (weaker sourcing).

---

## Trap (EDM and festival trap)

Festival trap, not hip-hop trap, with the same roots. Sourcing is thinner than for the other genres: the MusicRadar articles could not be retrieved, and Attack, Sound On Sound and Ableton had nothing trap-specific.

**Tempo and swing**
- **●** 140–150 BPM with a halftime feel (feels like 70–75), harder styles up to 160. Figures range from 128 to 170.
- **◐** Light swing on 808 and hats or individual timing edits are options. The engine uses **strength 0.12, about 52 % MPC-style ratio**. The cited 8–15 % tutorial amounts need their original control convention to be comparable. Velocity and timing variation are optional, not compulsory humanization.

**Structure** (phrases 4/8)
- **◐** Cymatics: intro 4, verse 8, build 4–8, drop 16, breakdown/verse 8, build 4–8, drop 2 16–32, outro 8.
- **◐** EDMProd: intro 8–16, build 8–16, drop 16–32, variation 16, outro 16.
- **◐** Total 2–3.5 minutes, shorter than house or techno.
- **○** Something changes every 4–8 bars.

**Arrangement**
- **◐** EDMProd example: kick from bar 9 only on the one. From bar 13 it gets denser (every 2 beats, then every beat, then every half beat), with a high-pass sweep running along. Pad and keys come in just before the drop, a tom fill one beat before it.
- **●** Snare roll in eighths, then sixteenths, then 32nds into the drop, plus rising pitch, risers and noise.
- **●** Bass out just before the drop, silence before the drop (one beat or less), a vocal chop right before it, occasionally fake drops.
- **○** Kick and 808 muted in the last 1–2 beats before the drop. No source says this explicitly.

**Drums**
- **●** Snare or clap on **step 9** (beat 3 at the written fast tempo, e.g. 140 BPM). The same recurring backbeat can be counted on beats 2 and 4 at **half that tempo** (70 BPM), across two fast-tempo bars.
- **◐** Kick on 1, an extra kick just before the snare (around step 8) and offbeat kicks. Don't overload.
- **●** Hats as a base pattern in eighths or sixteenths. **Rolls** in 32nds or 64ths before snares and at the end of the bar, plus **triplets** (1/8T, 1/16T). Vary the pitch of rolls and raise the velocity into the next bar.
- **◐** An open hat on an offbeat, cut off by the next closed hat. Before a big roll, one or two bars of straight hats.
- **◐** Rims and shakers layered on kick or snare, tom fills.

**808**
- **●** One 808 note under each kick, plus a few notes leading into the next bar that answer the snare. Don't fill every sixteenth.
- **◐** Monophonic and legato with overlapping notes for glides, at most 1–2 glides per bar, toward an accent. No source gives a glide time.
- **●** Follows key and roots: start on the root, move to the fifth, lower in the drop. Mostly stays within one octave.
- **◐** Suggested register **MIDI 28–43** (Live E0–G1, about 41–98 Hz). Choose key and register for the sample's tuning and playback system. Mono low end and kick sidechain are useful options, not a fixed 150 Hz rule or a requirement.

**Harmony**
- **●** Minor: natural minor, harmonic minor, Phrygian or Dorian.
- **◐** Progressions: i–VI–v–i, i–v–iv, i–III–V–iv, i–iv–v, i–III–VI–VII, often just two chords. Loops over 2–4 bars.
- **◐** Leave out the root when the 808 plays it. Keep third, seventh and extensions; chord notes short against the 808.
- **◐** Piano or bell on top, muted pads underneath.
- **○** 1 chord per 1–2 bars.

**Lead and hook**
- **●** Short 2-bar motif in a 2–4-bar loop, sparse, dark, minor. Use melodies rather sparingly.
- **◐** Above the 808. The lead line starts on the fifth or seventh instead of the root.
- **◐** EDMProd drop lead: every second root hit with a slide of +12, the first note delayed by 2 beats, variation on every second repetition.
- **●** Brass or horn stabs in the drop.

**Sounds**
- 808: Simpler with a long tuned sample and Saturator, or Operator with sine and pitch envelope.
- Drums: Drum Rack with Drum Buss.
- Lead: Wavetable or Analog with detuned saws.
- Brass stabs: Wavetable or Analog with a fast filter envelope.
- Plucks and bells: Operator or Drift.
- Pads: Drift or Wavetable.
- Vocal chops: Simpler.

**Filter sweeps** (Auto Filter, clip automation)

| Section | Drums (high-pass) | Chords (low-pass) |
|---|---|---|
| Intro | open | 200 Hz → 20 kHz, opens late |
| Build, Build 2 | 20 → 300 Hz or 400 Hz | open |
| Outro | open | 20 kHz → 150 Hz |

Delay throws: the lead throws in the drop, the chords in the verse, each on the last beat of every 8th bar.

**Sources:** Future Proof Music School (Festival Trap, Trap Beat in 10 Minutes, Genre Explorer); EDMProd (How to Make Trap); Cymatics (How to Make Trap); eMastered (Trap Drum Patterns, Trap Chord Progressions); Violet Recording (Trap Beats, 808 Patterns); Loopmasters (Top 10 Trap Tips); RouteNote (build-ups, drops); UJAM (Swells & Brass Stabs); Native Instruments (Hip-Hop Chord Progressions).

---

## What the engine implements and what it doesn't

State after the rework to follow the recipes (`compose/grooves.py`, `compose/hook.py`, templates in `compose/structures.py`).

**Implemented**

| Topic | Implementation |
|---|---|
| Drums | Lanes as data per genre (steps, velocity, ghost notes, cycles), swing only on the lanes allowed to swing; varying fills every 8 bars, a roll into new sections, hat and clap rolls (Trap, Peak-Time); lanes without a matching pad in the kit are dropped |
| Arrangement | Parts enter and leave within a section (`"kick_hats:8,groove"`), one beat of silence before drops, drums out 4 bars before the D&B drop, the bass leaves the outro first, late lanes (open hat, ride) only in the second half of the drop |
| Bass | Patterns per genre: House offbeat, Peak-Time rolling sixteenths, Melodic between the kicks, D&B sub long, Trap 808 under the kicks with glide; registers from the recipes |
| Harmony | Genre loops by key (major/minor), seventh chords for House and Liquid, parallel minor stabs with chord shift for Peak-Time, Trap without root |
| Lead | House, D&B, Trap: hook with call/response; Melodic: arpeggio; Peak-Time: acid line that evolves every 8 bars and rises in the last peak |
| Structure | Templates after the recipes (tempo: House 124, Melodic Techno 122, Peak-Time 128, D&B 174, Trap 145 BPM, set with `set_tempo`); lengths radio/standard/extended or minutes; with `reference`, section order and lengths follow a song analyzed by the Reference Analyzer, snapped to the genre's phrase grid (an unwarped song only at its own tempo); section types without a counterpart in the genre fall back to a related one |
| Sounds | New tracks get the genre's kit and presets from the Core Library; the drum notes land on the kit's pads |
| Mix | One reverb and one delay return (the song uses existing ones), fader levels and sends per role for new tracks; existing tracks keep their fader and only send into new returns. Reverb decay and delay time per genre, e.g. Melodic Techno 4.5 s, House 1.8 s |
| Automation | Auto Filter sweeps per clip in all genres, plus resonance sweeps (acid in Peak-Time, pads in breaks and builds). Delay throws: a role's send jumps to -4 dB on the last beat of every 8th bar and then falls back to its level |
| Sidechain | Optional silent-trigger ducking. Default `sidechain_mode="pumping"` plays the genre's main kick steps across the whole song, even during kick rests (House, Melodic, Peak-Time every beat, D&B steps 1 and 11, Trap 1, 8 and 11). `follow_kick` instead derives triggers from the planned drum MIDI, including fills, variations and note-free passages. It is not audio detection: track mute, filters, instrument envelopes and later edits can change what is heard. A dedicated silent "Sidechain" track (Operator, fader at -inf) keys Compressors Post FX. Preset ratio 4:1, attack 1 ms; threshold/release: House bass -24 / chords -18 dB, 160 ms; Melodic -22 / -16 dB, 200 ms; Peak-Time -24 / -20 dB, 120 ms; D&B bass only -18 dB, 90 ms; Trap 808 only -14 dB, 100 ms. These settings do not guarantee gain reduction |
| FX | A riser fills the last bars (at most 8) before every drop that follows a different section, and ends at the pause before it; volume and filter macro rise exponentially. An impact (Sub 808 Pitch Boom) hits the one of the drop. Riser presets: House and Trap Riser Basic, Melodic and Peak-Time Hyper Riser, D&B ENCOM Riser |

**Still open**

| Topic | Why |
|---|---|
| Comparison with real tracks | how good a song sounds is so far only checked by ear. A reference song only sets section order and lengths (`reference`); the engine does not compare sounds and notes against it |
| More genres | Trance, Dubstep, Hardstyle etc. can be added as templates once there is a recipe |
| Other time signatures | the grooves are 16-step bars; `plan_song` therefore needs 4/4 and reports otherwise |

All cutoff frequencies, resonance values, sends, dynamics settings and section timings above are preset choices. They do not establish optimal settings for arbitrary instruments, samples or mixes. A genre label does not substitute for listening.

## Master chain (`plan_master`)

`plan_master` defaults to three native devices at the end of the master track: EQ Eight, Glue Compressor, Limiter. Set `low_cut=false` or `glue=false` to omit those stages; both false produces a Limiter-only chain. The defaults remain unchanged. This is a preset to audition, not finished mastering, because MidiBakery does not hear the song. It adds no Limiter input gain, but filtering, compression and limiting can still change level, timbre and transients. It does not measure loudness (LUFS). The table describes preset settings, not settings every mix needs.

| Device | Setting | House, Melodic Techno, Peak-Time Techno | Drum & Bass, Trap |
|---|---|---|---|
| EQ Eight | Low Cut (band 1) | 30 Hz, 12 dB/octave | 20 Hz, 48 dB/octave |
| Glue Compressor | Ratio, Attack, Release | 2:1, 30 ms, Auto | same |
| Glue Compressor | Threshold | -10 dB as a starting value | same |
| Glue Compressor | Sidechain EQ | High Pass 150 Hz | same |
| Limiter | Ceiling, mode | -1 dB, True Peak (adjustable -3 to -0.1 dB) | same |
| Limiter | Input Gain | 0 dB | same |

- **Professional guidance:** Spotify recommends below -1 dBTP and below -2 dBTP for masters louder than -14 LUFS. The current -1 dB default is therefore not the recommended Spotify ceiling for the louder genre presets. Set `ceiling_db` to -2 dB or lower for that use and verify the rendered file with a true-peak meter.
- **Preset choice:** Glue at 2:1, attack 30 ms, release Auto. A slower attack may preserve more transient energy, but the result depends on the signal. If subtle bus compression is wanted, audition around 1–2 dB gain reduction in loud passages; bypassing compression is valid.
- **Preset choice:** a 150 Hz high-pass in the Glue detector reduces its sensitivity to low frequencies. It does not guarantee the absence of pumping.
- **Professional guidance:** filter the master only when the result helps. A 20–30 Hz low cut can remove unwanted subsonic energy but can also attenuate wanted bass and change phase and transients; a 30 Hz cut is not inherently inaudible. A 48 dB/octave slope is not automatically preferable for sub-heavy music. Compare level-matched with bypass, and consider a gentler cut, a shelf or no filter.
- **Implemented control:** low cut and Glue are included by default but can each be omitted. No automatic analysis establishes whether either is needed.
- **○** Glue threshold -10 dB is an uncalibrated starting value. Input level determines gain reduction; the threshold alone cannot predict it. Adjust while listening or bypass the compressor.
- **○** Limiter Input Gain 0 dB is intentional: making it louder without measuring would be guesswork.

Measured in Live 12.4:
- The parameter names of the three devices.
- Glue Attack, Ratio and Release are steps (raw 0–6, 0–2, 0–6).
- A batch that inserts devices and then sets their parameters leaves two undo steps. `apply_plan` therefore writes the chain in two batches; two undo steps remove it.

`plan_master` does not add a chain to a master that already has a Limiter, an EQ Eight or a Glue Compressor. Other devices there stay before the chain; the MidiBakery Loudness Meter stays after it.

**Sources:**
- Violet Recording (bus compressors, mastering compressors)
- MusicHub (compressor settings)
- Ableton forum (Glue Compressor on the master)
- Production Advice (Spotify true peak)
- Flux (true peak limiting)
- AES TD1008, only via summaries
- Soundbridge (sub bass)
- Richie ZXY (mastering drum & bass)
- Gearspace, weaker sourcing (808, high-pass filters, master bus compression)


## Measuring loudness (`measure_master`)

The Max for Live device **MidiBakery Loudness Meter** sits as the last device on the master and approximates the ITU-R BS.1770-4 loudness algorithm. `measure_master` reads its values; compliance with the full meter specification has not been established.

- **Identity and status:** every reset and sample-rate change creates a distinct `measurement_id`; readings include `since` and `sample_rate`. `reading_fresh` (and the compatibility alias `measuring`) indicates recent file updates, not playback; `is_playing` comes from Live's transport. A raw reading has unknown scope and `coverage_verified=false`.
- **K-filter:** two biquad~ per channel (pre-filter as high shelf, then RLB high-pass). `loudness.js` computes the coefficients for the current sample rate using the libebur128 formulas; at 48 kHz they are the table values from BS.1770 (a test checks this).
- **Blocks:** average~ rms over 100 ms per channel, read every 100 ms. Momentary = the last 4 blocks (400 ms), short-term = the last 30 (3 s), as EBU Tech 3341 defines them.
- **Integrated:** every 400 ms block (75 % overlap) since the reset; gates at -70 LUFS absolute and 10 LU below the mean of the blocks that pass the absolute gate.
- **Analytical check:** a 997 Hz sine at 0 dBFS in one channel gives -3.01 LUFS (test with the same filter chain in Node).
- **Checked in Live (Live 12.4, 48 kHz):** a mastered reference song (5 min, MP3) showed -11.3 LUFS integrated; pyloudnorm measures the same file offline at -11.34 LUFS.
- **Limits:** sample peak instead of true peak. Intersample peaks can exceed sample peaks by more than 0.5 dB; this meter cannot verify a true-peak ceiling. Max reads the blocks at the scheduler rate, not sample-accurately: an approximation, not a calibrated or independently certified meter. One reference-file comparison is not a conformance test.

## Loudness targets (`plan_loudness`)

`plan_loudness` proposes Limiter gain adjustments toward a selected loudness reference. This is not an assessment of mastering quality. One round:
1. Reset the meter and play the **whole song once** for comparison with whole-track integrated references, then explicitly declare `scope="whole_song"` in `plan_loudness`. Coverage remains **user-declared, not verified**: elapsed time and repeated loops cannot prove complete playback. Omitted/unknown scope is rejected. An excerpt requires `scope="excerpt"` and an explicit `target_lufs`; named genre/streaming targets cannot be used for excerpts. Excerpts need at least 30 s; a declared complete song can be shorter but needs at least 0.4 s and a finite integrated reading.
2. It proposes adding the difference to the target to the Limiter's **Input Gain**, at most 6 dB per round and no increases beyond +12 dB total input gain. A pre-existing gain above +12 dB can still be reduced without exceeding the 6 dB step limit. Above +6 dB it warns about possible heavy limiting; this is an input-gain heuristic, not a gain-reduction measurement.
3. `apply_plan` sets the value (one undo step) and resets the meter; then you play the song again.

Limiting may absorb part of an input gain increase, so the loudness response is signal-dependent. After each change, reset and measure the same complete playback again. `on_target` means the reading is within ±0.5 LU for the declared scope; results include `measurement_scope`, `scope_source="user_declared"` and `coverage_verified=false`. It does not guarantee convergence or acceptable dynamics. Planning rejects stale readings and a meter that is not last. Apply rejects a changed measurement identity/sample rate/reset time, pending reset, replaced meter/Limiter, changed Master device list or changed Limiter parameters. New readings from the same session are allowed. The ceiling setting is unchanged, but the sample-peak meter does not independently verify true peak. Stop if transients, distortion or pumping worsen, even if the number is below the reference.

**Upgrade:** update the core, Remote Script and Loudness Meter together and restart Live/reload the device. Older meters lack measurement IDs and older scripts lack device identities; loudness planning reports an explicit upgrade error rather than silently weakening its guards.

**Kick-following limits:** `follow_kick` needs an identifiable named kick pad (including the loaded kit on a new drum track). Copied Session drum clips must be MIDI, start at 0 and have loop start 0 / loop end equal to length; consolidate other clips first. Probabilistic kick notes are rejected because independent trigger probability would not reliably match them. Copied drum notes/timing are rechecked before apply. Use `pumping` for unsupported sources; there is no silent fallback.

The genre presets below are published reference figures, not industry standards. The House and Techno values reproduce a vendor's reported stereo measurements of a selected corpus; the Drum & Bass figure has only partly described methodology, and Trap has no open dataset. The figures have not been independently reproduced here. An excerpt measurement is not interchangeable with their full-track integrated values.

| Target | LUFS | Range | Basis | Rating |
|---|---|---|---|---|
| House | -8.0 | -9.0 to -7.1 (middle 50 %) | TrackSensei, 54 tracks | vendor-reported corpus; selection bias, not a standard |
| Melodic Techno | -8.8 | -9.9 to -8.0 (middle 50 %) | TrackSensei, 56 tracks | vendor-reported corpus; selection bias, not a standard |
| Peak-Time Techno | -7.7 | – | TrackSensei, 308 tracks | vendor-reported corpus; selection bias, not a standard |
| Drum & Bass | -6.3 | -9.0 to -4.0 (middle 80 %) | WeFoundDNB, 101 tracks | reported reference; method only partly described |
| Trap | -8.4 | -9.4 to -7.3 | blog measurements and mastering guides | weak: no open dataset or verified median |
| Streaming | -14.0 | – | Spotify for Artists | official Normal playback level and mastering recommendation; not a universal streaming requirement |

TrackSensei explicitly notes that its own scale (mono sum) sits about 3.3 LU lower for its corpus. The table uses its published stereo values; 3.3 LU is not a universal mono-to-stereo conversion. Choose a musically appropriate range with level-matched references, not the median at any cost. Spotify's -14 LUFS is its Normal playback normalization level and also its published mastering recommendation, not a requirement shared by all streaming services. For Spotify masters louder than -14 LUFS, its recommendation is true peak below -2 dB; `plan_master` currently defaults to -1 dB, configurable via `ceiling_db`.

A check of our own: Katoff – The Signal (Extended, VANDIT Alternative), a melodic track, measures -11.3 LUFS, i.e. quieter than the median, but within the spread of released tracks.

Checked in Live 12.4, the same song with the House chain on the master, target Melodic Techno (-8.8 LUFS):

| Round | Input Gain | Integrated |
|---|---|---|
| before (chain, gain 0) | 0.0 dB | -13.9 LUFS |
| 1 | +5.1 dB | -9.4 LUFS |
| 2 | +5.7 dB | -9.0 LUFS, on target |

In this reported example the chain reduced integrated loudness by 2.6 LU. The first +5.1 dB input-gain change increased the reading by 4.5 LU, consistent with nonlinear dynamics processing; this difference is not a measurement of Limiter gain reduction. The reported peak stayed at -1.0 dB, which does not independently establish a true-peak ceiling. This single example does not establish behavior for other songs.

**Sources:**
- [TrackSensei, "563 Techno & House Tracks: Real LUFS Data"](https://tracksensei.com/blog/we-analyzed-563-techno-house-tracks) (vendor methodology and selection limits)
- WeFoundDNB, "How Loud Should Drum & Bass Be? LUFS From the Pros and 101 Measured Tracks"; [reference library](https://wefounddnb.com/tools/reference-tracks) (the numerical summary still needs a reproducible dataset/method reference)
- Violet Recording (hip-hop mastering), TrackScore (genre bands)
- [Spotify for Artists, "Loudness normalization"](https://support.spotify.com/us/artists/article/loudness-normalization/)

## Loudness measurement sources

- ITU-R BS.1770-4 (K-filter, gating, calibration)
- EBU R 128 and EBU Tech 3341 (momentary, short-term, integrated)
- libebur128 (coefficients for arbitrary sample rates)

## Gaps

- **Lead density and stab length** are hardly given in numbers by the sources. The values above are conventions (○) and should be adjusted by ear.
- **Note grids from Attack's "Beat Dissected"** only exist as images. The step positions come from the texts and from other sources.
- **Sound techniques** such as rumble, Reese and sidechain are sound design. The engine hints at them through rests, density and velocity; it builds sidechain as a Compressor driven by a silent trigger track. It writes filter sweeps and resonance as clip automation of an Auto Filter, delay throws as send automation, risers as a preset with envelopes on volume and filter macro.
- **Breaks and samples** (Amen, vocal chops, 808 samples) cannot be loaded by Live's API.

## Assessment and implementation impact

The October 2026 review supports the engine as a controllable musical sketching assistant, not an autonomous professional composer or mastering engineer. The follow-up implementation preserves default musical notes, target values and processing presets, adds opt-in controls, and intentionally requires explicit scope for loudness planning.

| Finding | Current implementation | Follow-up |
|---|---|---|
| Excerpt versus full-track loudness | Explicit declared scope, scope-labelled results and measurement/device guards; no duration-based coverage inference | **Implemented.** Automatic transport/range-based verification remains a separate extension, not claimed here |
| True peak | The meter reports sample peaks; the Limiter has a configurable true-peak ceiling | **Measurement work needed** to verify dBTP: use a validated true-peak meter or implement and validate oversampling. Until then, do not claim ceiling compliance from the meter |
| Limiting safeguards | Gain changes remain capped at 6 dB per round and +12 dB total; runtime warnings now identify input gain as a heuristic | **Guidance corrected.** Signal-based gain-reduction assessment and listening remain needed |
| Master filtering and compression | `low_cut` and `glue` can omit stages; existing defaults preserved | **Implemented.** Explicit ceiling control remains; runtime guidance warns about Spotify's louder-master recommendation rather than silently changing settings |
| Sidechain | Default continuous pumping plus opt-in `follow_kick` from planned MIDI | **Implemented.** This follows planned notes, not actual audio or subsequent edits |
| Counter melodies and harmony | Conservative register/consonance constraints and named chromatic progressions are intentional | No correction to notes is required by this review; less restrictive counterpoint would be an optional mode, not a silent replacement |
| Swing, pitch labels and pulse descriptions | The current timing and MIDI numbers are consistent with the corrected explanations | Documentation corrections only; extending swing beyond a triplet feel would be a separate feature |
| Reference analysis | Section, key and kick-presence labels are estimates, not source separation or musical ground truth | Validate against manually annotated tracks and let producers verify the result before using it as structure |
| Professional-quality claims | Functional tests and a few listening/measurement examples do not establish release quality | Use level-matched references, producer listening evaluations across substyles and EBU meter tests before stronger claims. Synthetic DSP tests cover 44.1, 48, 88.2, 96 and 192 kHz; the EBU ZIP download returned HTTP 403 during this implementation, so no EBU conformance pass is claimed. Actual Live scheduler/device verification remains outstanding |

## Review sources

Public sources checked for the assessment (October 2026); these support the distinctions above, not every older genre-specific recipe:

- [Ableton Live manual: Using Grooves](https://www.ableton.com/en/live-manual/12/using-grooves/) — Timing and Global Amount scale the selected groove, rather than defining a universal swing ratio.
- [Open Music Theory: First-species counterpoint](https://openmusictheory.github.io/firstSpecies.html) — independent lines can share rhythm; these classical exercise rules are not mandatory for electronic music.
- [Eerola et al. (2013): Emotional expression in music](https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2013.00487/full) — emotion depends on multiple musical cues, not a progression alone.
- [Sound On Sound: How steep should I make a high-pass filter?](https://www.soundonsound.com/sound-advice/q-how-steep-should-make-high-pass-filter) — filtering affects phase, transients and note balance as well as spectrum.
- [Sound On Sound: What mastering can and can't do](https://www.soundonsound.com/techniques/what-mastering-can-cant-do) — intervention should serve the material, not a mandatory processing chain.
- [iZotope: What is a true peak limiter?](https://www.izotope.com/community/blog/true-peak-limiter) — true-peak behavior and delivery tradeoffs.
- [ITU-R BS.1770](https://www.itu.int/rec/R-REC-BS.1770/en), [EBU Tech 3341](https://tech.ebu.ch/publications/tech3341) and the [EBU loudness test set](https://tech.ebu.ch/publications/ebu_loudness_test_set) — loudness algorithms, meter behavior and validation material.
- [Spotify loudness normalization](https://support.spotify.com/us/artists/article/loudness-normalization/) and [TrackSensei corpus/methodology](https://tracksensei.com/blog/we-analyzed-563-techno-house-tracks) — official playback guidance versus descriptive vendor measurements.
