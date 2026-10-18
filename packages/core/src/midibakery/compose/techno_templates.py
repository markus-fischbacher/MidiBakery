"""Techno patterns from the "19 Techno Patterns Changed My Life in 4 mins" tutorial, as data.

The video is a quick-fire mix: drum patterns (claps, hats), bass patterns, an ambience, a
melodic chord progression. Each entry says what it is (``kind``):

- ``drums``: hits per role on the 16th grid (the roles map to Drum Rack pads like the drum generator)
- ``bass``: points to a bass template (bass_templates.py), plus what the tutorial adds to it
- ``lead``: a lead template (lead_templates.py), played as ambience or build-up
- ``chords``: a roman numeral progression and the voicing the tutorial uses

The voice-over is short and the speech recognition is rough, so names and rhythms are read
from the described steps. The tutorial does not number its patterns; this set is what the
transcript names. Sound design (sidechain, resampling, detune) is kept as a ``hint``.
"""

from __future__ import annotations

from dataclasses import dataclass

from midibakery.compose.drums import DrumMap
from midibakery.compose.lead_templates import LNote, LeadTemplate, Part
from midibakery.compose.notes import Note, dedupe
from midibakery.compose.rhythm import Grid, Meter

STEP = 0.25


@dataclass(frozen=True)
class DrumHit:
    role: str
    step: float  # 1-based 16th step of the bar; fractions place triplets and laid-back hits
    velocity: float = 100
    length: float = 0.25


@dataclass(frozen=True)
class TechnoPattern:
    name: str
    label: str
    kind: str  # drums | bass | lead | chords
    description: str
    hint: str = ""
    bars: tuple[tuple[DrumHit, ...], ...] = ()  # drums: one bar per entry, cycled
    ref: str = ""  # bass: name in BASS_TEMPLATES; lead: name in TECHNO_LEADS
    progression: str = ""  # chords: roman numerals, "min" scale
    voicing: str = ""
    bpm: tuple[int, int] = (126, 140)


def _hits(role: str, steps, velocity=100, length: float = 0.25) -> tuple[DrumHit, ...]:
    return tuple(DrumHit(role, s, velocity if isinstance(velocity, (int, float)) else velocity[i], length) for i, s in enumerate(steps))


SIXTEENTHS = tuple(range(1, 17))
TRIPLETS = tuple(1 + i * (2 / 3) for i in range(24))  # six per beat: 16th-note triplets
# Every 4th hat louder, the rest soft, like "play with the velocities"
HAT_VELOCITY = tuple(110 if (s - 1) % 4 == 0 else 72 if (s - 1) % 2 == 0 else 55 for s in SIXTEENTHS)
CLAP_RAMP = tuple(round(55 + 4.5 * i) for i in range(16))

TECHNO_LEADS: dict[str, LeadTemplate] = {t.name: t for t in (
    LeadTemplate(
        "drama_octaves", "Octave-jump build-up", "scale",
        {"main": Part((
            tuple(LNote(s, 0.45, 0, o, v) for s, o, v in ((1, 0, 70), (3, 1, 80), (5, 2, 90), (7, 2, 100), (9, 0, 80), (11, 1, 90), (13, 2, 100), (15, 2, 110))),
        ))},
        genres=("techno",), bpm=(130, 140),
        sound="Automate filter or reverb on top so the build-up is much stronger.",
        description="One note, the next an octave up, another octave up, then duplicated; add automation and the build-up carries drama.",
    ),
    LeadTemplate(
        "ambience_root_five_six", "Ambience: root, fifth, sixth, fifth", "scale",
        {"main": Part((
            (LNote(1, 3.9, 0, 0, 80), LNote(1, 3.9, 4, 0, 80)),
            (LNote(1, 3.9, 0, 0, 80), LNote(1, 3.9, 5, 0, 80)),
            (LNote(1, 3.9, 0, 0, 80), LNote(1, 3.9, 4, 0, 80)),
            (LNote(1, 3.9, 0, 0, 80), LNote(1, 3.9, 5, 0, 80)),
        ))},
        genres=("techno",), bpm=(128, 138), scale_hint="minor",
        sound="Soft pad or drone; the sixth is the note that lifts it.",
        description="Count from the root to the fifth, hop to the sixth and back to the fifth, loop it: a quiet ambience for a dry techno track.",
    ),
    LeadTemplate(
        "ambience_chord_semitone", "Melancholic ambience: minor chord with a top semitone", "chord",
        {"main": Part((
            (LNote(1, 3.9, 0, 0, 70), LNote(1, 3.9, 2, 0, 70), LNote(1, 3.9, 0, 1, 70), LNote(1, 3.9, 2, 1, 70), LNote(1, 3.9, 1, 2, 60)),
        ))},
        genres=("techno",), bpm=(128, 138), scale_hint="minor",
        sound="Wide pad with a lot of reverb.",
        description="Root, fifth of the minor chord, both doubled an octave up and the third on top: the melancholic ambience under a kick-only track.",
    ),
)}

TECHNO: dict[str, TechnoPattern] = {p.name: p for p in (
    TechnoPattern(
        "clap_16_build", "Clap on 16ths, a build-up", "drums",
        "A normal clap on 2 and 4 becomes darker with a short attack; switch to 16ths with a rising velocity for a full-beat clap build.",
        hint="Dark clap with attack; velocity rises through the bar.",
        bars=(_hits("clap", SIXTEENTHS, CLAP_RAMP, 0.2),),
    ),
    TechnoPattern(
        "hat_16", "16th hats with velocity play", "drums",
        "One hat duplicated on all sixteen 16ths; the trick is the velocity: accents on the beat, soft between.",
        hint="Randomise velocity, fade in, detune the pitch a little.",
        bars=(_hits("closed_hat", SIXTEENTHS, HAT_VELOCITY, 0.15),),
    ),
    TechnoPattern(
        "hat_open_offbeat", "Open hat on the offbeat", "drums",
        "The classic offbeat open hat on the 3rd 16th of every beat; boring alone, so it wants accents around it.",
        bars=(_hits("open_hat", (3, 7, 11, 15), 100, 0.4),),
    ),
    TechnoPattern(
        "hat_open_accents", "Open hat with accents around it", "drums",
        "The offbeat open hat plus short closed-hat accents on the 16ths around it, which makes the pattern better.",
        bars=(_hits("open_hat", (3, 7, 11, 15), 100, 0.4) + _hits("closed_hat", (1, 2, 4, 5, 6, 8, 9, 10, 12, 13, 14, 16), (80, 50, 60, 80, 50, 60, 80, 50, 60, 80, 50, 60), 0.12),),
    ),
    TechnoPattern(
        "hat_triplets", "Triplet hats", "drums",
        "For those who enjoy triplets: six hats per beat instead of four; you can alter the 16th pattern by mixing the two.",
        bars=(tuple(DrumHit("closed_hat", s, 100 if i % 6 == 0 else 70 if i % 3 == 0 else 55, 0.12) for i, s in enumerate(TRIPLETS)),),
    ),
    TechnoPattern(
        "rolling_bass", "Rolling bass", "bass",
        "The root note, duplicated once, then once more, looped; sidechained so the kick cuts it off. The most common techno rolling bass line.",
        hint="Sidechain to the kick.", ref="rolling_16",
    ),
    TechnoPattern(
        "offbeat_bass", "Offbeat bass", "bass",
        "Two main notes, on the beat and off the beat, made bigger. The offbeat bass.",
        ref="offbeat_fast",
    ),
    TechnoPattern(
        "groovy_bass", "Groovy bass with jumps", "bass",
        "One note, a second one, then jumps (and bigger jumps), extend the notes, loop it; extend the pattern again to make it groove. Never forget to sidechain the kick.",
        hint="Sidechain to the kick.", ref="octave_jump_single",
    ),
    TechnoPattern(
        "evil_spirits", "Evil spirits: semitone bass", "bass",
        "Starts on the root and uses the power of semitones for a dark, evil bass line.",
        ref="evil_semitones",
    ),
    TechnoPattern(
        "kick_rumble", "Rumble: kick resampled to a bass", "drums",
        "The kick routed to a second channel with lots of effects and resampled; one transient on the last quarter (laid back a little), another on the offbeat, extended, so the transition is obvious.",
        hint="Resample the processed kick, polish it.",
        bars=(_hits("kick", (1, 5, 9, 13), 110, 0.3) + (DrumHit("kick", 14.4, 100, 0.35), DrumHit("kick", 11, 90, 0.5)),),
    ),
    TechnoPattern(
        "ambience_root_five_six", "Ambience: root, fifth, sixth, fifth", "lead",
        "Count from the root to the fifth, hop to the sixth, come back to the fifth and loop.",
        ref="ambience_root_five_six",
    ),
    TechnoPattern(
        "ambience_chord_semitone", "Melancholic ambience chord", "lead",
        "Root and fifth of C minor doubled, the third on top, semitones up.",
        ref="ambience_chord_semitone",
    ),
    TechnoPattern(
        "drama_octaves", "Octave-jump build-up", "lead",
        "A note, then octave jumps, duplicated, with automation: much stronger build-up.",
        ref="drama_octaves",
    ),
    TechnoPattern(
        "melodic_641", "Melodic 6-4-1", "chords",
        "Count to six, build a triad, count to four, build a triad, then the root key: 6-4-1, one of the most used progressions in melodic techno. Separate the notes into an arpeggio and lead the voices smoothly.",
        progression="VI iv i", voicing="triads, then arpeggiated with voice leading",
    ),
)}


def generate_techno_drums(pattern: TechnoPattern, meter: Meter, bars: int, drum_map: DrumMap, swing: float = 0.0) -> list[Note]:
    """The hits of a drums pattern over `bars` bars, mapped to the pads of `drum_map`."""
    if pattern.kind != "drums":
        raise ValueError(f"{pattern.name} is a {pattern.kind} pattern, not drums")
    grid = Grid(meter, STEP, swing, 0.25)
    notes: list[Note] = []
    for bar in range(bars):
        for hit in pattern.bars[bar % len(pattern.bars)]:
            pitch = drum_map.note(hit.role)
            if pitch is None or hit.step - 1 >= grid.steps_per_bar:
                continue
            index = int(hit.step - 1)
            if hit.step - 1 == index:
                start = grid.position(bar, index)
            else:  # triplets and laid-back hits sit between grid steps, unswung
                start = bar * meter.beats_per_bar + (hit.step - 1) * STEP
            notes.append(Note(pitch, round(start, 6), hit.length, hit.velocity))
    return dedupe(notes)


def describe_techno(pattern: TechnoPattern) -> dict[str, object]:
    return {
        "name": pattern.name, "label": pattern.label, "kind": pattern.kind, "ref": pattern.ref or None,
        "progression": pattern.progression or None, "hint": pattern.hint, "description": pattern.description,
    }
