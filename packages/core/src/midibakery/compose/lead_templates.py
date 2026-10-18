"""The 19 leads of the "19 Lead Patterns That Changed My Life" tutorial, as data.

A lead is a few parts (the main line plus optional layers) of notes on the 16th grid
(step 1-16 in a 4/4 bar, lengths in beats). What a note's ``degree`` means depends on the
template's ``mode``:

- ``scale``: scale degree counted from the song's tonic (0 = tonic, 4 = fifth, 7 = tonic an octave up)
- ``chord``: chord tone of the current chord (0 root, 1 third, 2 fifth, 3 seventh)
- ``root_step``: scale steps above the current chord root (the bass note), 1 = second, 2 = third

``octave`` on a note shifts it by whole octaves. Several notes on the same step make a voicing.
A part may play only in some bars of a cycle (a complement that does not play every time).

Provenance: the voice-over gives the rhythm only for some leads (e.g. the 3-3-3-3-3-1 restart of
lead 1, the half-step trick of lead 4). Where it does not, the rhythm is a plausible one in the
described style, so ``source`` says "described". The tutorial's sound design is kept as a
``sound`` hint, it is not applied by MidiBakery.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from midibakery.compose.harmony import Harmony
from midibakery.compose.notes import Note
from midibakery.compose.rhythm import Grid, Meter
from midibakery.compose.theory import Scale, octave_base

STEP = 0.25
Mode = Literal["scale", "chord", "root_step"]


@dataclass(frozen=True)
class LNote:
    step: int
    length: float
    degree: int
    octave: int = 0
    velocity: float = 100


Bar = tuple[LNote, ...]


@dataclass(frozen=True)
class Part:
    bars: tuple[Bar, ...]  # cycled
    cycle: int = 1  # the part plays in bars where bar % cycle is in `active`
    active: tuple[int, ...] = ()  # empty = every bar
    octave: int = 0  # extra octave shift of the whole part
    velocity: float = 1.0  # factor


@dataclass(frozen=True)
class LeadTemplate:
    name: str
    label: str
    mode: Mode
    parts: dict[str, Part]
    octave: int = 3  # Live octave of degree 0 / the chord root (C3 = 60)
    bpm: tuple[int, int] = (120, 130)
    genres: tuple[str, ...] = ("melodic_techno",)
    scale_hint: str = ""
    pitch_bend: bool = False  # the tutorial bends the pitch of long notes
    sound: str = ""
    description: str = ""
    source: str = "described"


def _b(*notes: tuple) -> Bar:
    return tuple(LNote(*n) for n in notes)


def _seq(steps: tuple[int, ...], length: float, degrees: tuple[int, ...], octave: int = 0, velocity: float = 100) -> Bar:
    return tuple(LNote(s, length, d, octave, velocity) for s, d in zip(steps, degrees))


def _stack(step: int, length: float, voices: tuple[tuple[int, int], ...], velocity: float = 100) -> tuple[LNote, ...]:
    return tuple(LNote(step, length, d, o, velocity) for d, o in voices)


TUMBLE = (1, 4, 7, 10, 13, 16)  # 3-3-3-3-3-1: every note three 16ths apart, the last one restarts the loop
POSITIONS = (1, 6, 11, 16)  # the 1st, 2nd, 3rd and 4th 16th of the four beats

LEADS: dict[str, LeadTemplate] = {t.name: t for t in (
    LeadTemplate(
        "descending_pedal", "Descending pedal-tone motif (Ben Bohmer)", "scale",
        {"main": Part((
            _seq(TUMBLE, 0.5, (4, 3, 2, 1, 4, 3)),
            _seq(TUMBLE, 0.5, (2, 1, 5, 4, 3, 2)),
            _seq(TUMBLE, 0.5, (4, 3, 2, 1, 4, 3)),
            _seq(TUMBLE, 0.5, (2, 1, 4, 3, 2, 1)),
        ))},
        genres=("melodic_techno", "progressive"), scale_hint="major",
        sound="Saw plus a little noise; attack randomised with a chaos LFO, filter cutoff moving; reverb, delay, OTT, sidechain.",
        description="Fifth down to the second, restarted every bar: each note three 16ths after the last, the final one 16th restarts the loop and re-syncs to the kick. The eight bars vary at the start and the end.",
        source="described+speech",
    ),
    LeadTemplate(
        "ascending_energy", "Ascending lead with pitch bend", "scale",
        {"main": Part((
            _b((1, 0.75, 0, -1), (3, 0.25, 1), (6, 0.5, 2), (8, 0.5, 3), (11, 0.75, 4), (14, 0.5, 4)),
            _b((1, 0.75, 0, -1), (3, 0.25, 1), (6, 0.5, 2), (8, 0.5, 3), (11, 0.5, 2), (14, 0.5, 0)),
            _b((1, 0.75, 0, -1), (3, 0.25, 1), (6, 0.5, 3), (8, 0.5, 4), (11, 0.75, 4), (14, 0.5, 3)),
            _b((1, 0.75, 0, -1), (3, 0.25, 1), (6, 0.5, 2), (9, 2.0, 1)),
        ))},
        genres=("melodic_techno",), scale_hint="minor", pitch_bend=True,
        sound="Two layers: a plucky saw/digital lead and a wide background saw with unison and detune; pitch bend on the held note.",
        description="Tonic knocked down an octave, then rising second, third, fourth, fifth; the last bar holds the second for tension. Going up adds energy, going down feels emotional.",
    ),
    LeadTemplate(
        "arp_third_start", "Looping arp starting on the third", "root_step",
        {"main": Part((
            _seq(tuple(range(1, 17)), 0.22, (2, 9, 8, 7, 6, 4, 6, 1, 2, 9, 8, 7, 6, 4, 1, 11)),
        ))},
        genres=("melodic_house", "melodic_techno"), scale_hint="minor",
        sound="Simple saw; the mod wheel opens the cutoff so the same arp grows over the whole song; hall reverb and echo.",
        description="Starts on the third instead of the root, falls, rises, ends on the fifth an octave up; it follows every chord of the song and keeps its pattern.",
    ),
    LeadTemplate(
        "half_step_trick", "Half-step trick", "root_step",
        {"main": Part((
            _seq((1, 4, 7, 10, 13), 0.4, (2, 1, 4, 2, 1)),
            _seq((1, 4, 7, 10, 13), 0.4, (2, 1, 4, 2, 1)),
            _seq((1, 4, 7, 10, 13), 0.4, (2, 1, 4, 2, 1)),
            _seq((1, 4, 7, 10, 13), 0.4, (2, 1, 4, 3, 1)),
        ))},
        genres=("melodic_house", "melodic_techno"), scale_hint="minor",
        sound="Detuned and centred saw pair with EQ for brightness, a rave lead (unison, detune, pluck, portamento) and a bright top layer; a piano underneath carries the rhythm.",
        description="Three notes only; the emotion lives in the half step between second and third. Repeat with a small change at the end, and keep the half step: going back to the root would lose it.",
    ),
    LeadTemplate(
        "bass_lead_bodzin", "Bass lead with octave jumps (Stefan Bodzin)", "scale",
        {"main": Part((
            _b((1, 0.75, 5), (4, 0.25, 4), (6, 0.5, 3), (8, 0.25, 0, 1), (9, 0.5, 2), (11, 0.25, 1), (13, 0.75, 0), (16, 0.25, 0, 1)),
        ), octave=-2)},
        genres=("melodic_techno", "progressive"), scale_hint="minor",
        sound="Saw (organic wavetable) cut with a multiband compressor and EQ, no reverb; sidechain for the groove.",
        description="Starts on the sixth and descends to the root in every progression, with high octave jumps and a little glide into the next note, even off-scale.",
    ),
    LeadTemplate(
        "top_note_complement", "Sparse top note over piano chords", "root_step",
        {"main": Part((
            _b((1, 2.0, 6, 1), (9, 1.5, 8, 0)),
            _b((5, 1.5, 9, 0), (13, 2.0, 8, 0)),
        ))},
        genres=("melodic_house",), scale_hint="minor",
        sound="Plucky saw, lots of reverb and a low cut: the piano and pads carry the low end.",
        description="A second lead above piano chords: seventh, second and third of the chord with a lot of space. Space is part of the melody.",
    ),
    LeadTemplate(
        "gated_vocal", "Gated vocal lead", "chord",
        {"main": Part((
            _b((1, 0.25, 3), (3, 0.25, 3), (9, 0.25, 0, 1), (11, 0.25, 0, 1)),
            _b((1, 0.25, 3), (3, 0.25, 3), (9, 0.25, 3), (12, 0.25, 0, 1)),
        ))},
        genres=("melodic_techno", "melodic_house"), scale_hint="minor",
        sound="A long stable vocal chop triggered by a gate that also triggers the chords; the gaps are the rhythm.",
        description="Seventh on the first notes, the root an octave up after them; positions 1 and 3 with gaps instead of a stream of 16ths.",
    ),
    LeadTemplate(
        "triad_voicing_dance", "Wide triad voicing with a dancing top note (Oscar Mattke)", "chord",
        {
            "main": Part((
                _stack(1, 0.5, ((0, 0), (1, 2), (2, 1))) + _stack(7, 1.5, ((0, 0), (1, 2), (2, 1))) + _stack(13, 0.25, ((0, 0), (1, 2), (2, 1))),
            )),
            "dance": Part((_b((4, 0.25, 1, 2), (10, 0.25, 2, 1), (16, 0.25, 1, 2)),), cycle=2, active=(1,)),
        },
        genres=("melodic_house",), scale_hint="minor",
        sound="Analog (Moog-like) saw without low end, reverb, delay, sidechain.",
        description="Root, third two octaves up and fifth one octave up; long notes against short ones played off the kick every three 16ths; a little top-note dance in every second bar. Follows the bass line.",
    ),
    LeadTemplate(
        "chord_complement", "Lead that complements the chords", "chord",
        {"main": Part((
            _b((1, 0.5, 1), (6, 0.25, 1), (11, 0.25, 2), (16, 0.25, 1)),
            _b((3, 0.25, 1), (6, 0.5, 0), (11, 0.25, 2), (15, 0.25, 1)),
        ))},
        genres=("melodic_techno", "melodic_house"), scale_hint="minor",
        sound="Plucky saw, a filter only for the noise, reverb and delay, EQ to bring the pluck alive.",
        description="Starts on the third and mostly plays the third and fifth against the chord; one rhythm replicated through the song with small variations.",
    ),
    LeadTemplate(
        "lfo_chord_lead", "LFO chord lead (Lydian)", "chord",
        {"main": Part((_stack(1, 3.9, ((0, 0), (1, 0), (2, 0))),))},
        genres=("melodic_techno", "progressive"), scale_hint="lydian",
        sound="Saw chord; an LFO on the cutoff whose rate is automated, variations with distortion and cutoff.",
        description="Sustained chords following the bass; the movement comes from automation. Lydian (or Mixolydian, Dorian) gives a dreamy feeling instead of plain major or minor.",
    ),
    LeadTemplate(
        "third_of_bass", "Third of the bass line", "chord",
        {"main": Part((
            _seq(POSITIONS, 0.3, (1, 1, 1, 1)),
            _seq((1, 7, 12, 14), 0.3, (1, 1, 1, 1)),
        ))},
        genres=("melodic_house", "melodic_techno"),
        sound="Plucky saw, same as the 8th trick without the octave.",
        description="The lead plays the third of every bass note: playing the bass note itself or the fifth would be boring. The groove comes from notes on positions 1, 2, 3 and 4 of the 16ths, not only with the kick.",
    ),
    LeadTemplate(
        "notes_and_chords", "Notes and chords alternating over a pedal tone", "chord",
        {
            "chords": Part((_stack(1, 0.5, ((0, 0), (1, 0), (2, 0))) + _stack(7, 0.5, ((0, 0), (1, 0), (2, 0))), ()), cycle=2, active=(0,)),
            "notes": Part((_b((1, 0.25, 0, 1), (3, 0.25, 0, 1), (6, 0.25, 2, 1), (9, 0.25, 0, 1), (11, 0.25, 1, 1), (14, 0.25, 2, 1)),), cycle=2, active=(1,)),
        },
        genres=("afro_house", "tech_house"), scale_hint="minor",
        sound="Combined sounds: distorted plucky piano, a rave-like unison lead, a deep tone, broken piano, bright power saws.",
        description="One bar plays chords, the next plays notes around a repeating pedal tone (fifth, sixth, third, second); notes and chords have a different character, so the repetition stays interesting.",
    ),
    LeadTemplate(
        "pitch_mod_one_note", "One note with pitch modulation", "chord",
        {"main": Part((
            _b((1, 0.5, 0, 1), (4, 0.25, 0, 1), (7, 0.5, 0, 1), (11, 0.25, 0, 1), (14, 0.5, 0, 1)),
            _b((2, 0.25, 0, 1), (5, 0.5, 0, 1), (9, 0.25, 0, 1), (12, 0.5, 0, 1), (16, 0.25, 0, 1)),
        ))},
        genres=("melodic_techno",), pitch_bend=True,
        sound="A pluck with a lot of reverb and delay; automated pitch bend does the melody, sidechain for rhythm.",
        description="One note in different lengths on groovy 16th positions; the pitch bend gives it the movement, so it needs no melody.",
    ),
    LeadTemplate(
        "minor_chord_lead", "Minor chord lead with rave voicing", "chord",
        {"main": Part((
            _stack(1, 0.25, ((0, -1), (1, 0), (2, 0))) + _stack(3, 0.125, ((0, -1), (1, 0), (2, 0))) + _stack(5, 0.5, ((0, -1), (1, 1), (2, 1))) + _stack(11, 0.25, ((0, -1), (1, 0))) + _stack(13, 0.5, ((0, -1), (1, 1), (2, 1))),
            _stack(1, 0.5, ((0, -1), (1, 0), (2, 0))) + _stack(4, 0.125, ((0, -1), (1, 0), (2, 0))) + _stack(7, 0.25, ((0, -1), (1, 1), (2, 1))) + _stack(11, 0.5, ((0, -1), (1, 0))) + _stack(15, 0.25, ((0, -1), (1, 1), (2, 1))),
        ))},
        genres=("melodic_techno", "progressive", "trance"), scale_hint="minor",
        sound="Rave lead: unison above 9-10 and a lot of detune, EQ to boost the sound, reverb, delay, sidechain.",
        description="Tone an octave down plus third (and fifth); put the third and fifth up for the rave feeling. Lengths mix a 16th, a 32nd and an 8th. Use a different progression in the buildup and let it go at the drop.",
    ),
    LeadTemplate(
        "vocal_harmony_gated", "Gated vocal lead harmony", "chord",
        {
            "main": Part((_b((1, 0.5, 0), (4, 0.25, 0), (7, 0.5, 0), (9, 0.25, 0), (12, 0.5, 0)), _b((1, 0.5, 0), (3, 0.25, 0), (7, 0.5, 0), (10, 0.25, 0), (13, 0.5, 0))),),
            "harmony": Part((_b((1, 0.5, 1), (4, 0.25, 1), (7, 0.5, 1), (9, 0.25, 1), (12, 0.5, 1)),), cycle=4, active=(2, 3), velocity=0.8),
        },
        genres=("melodic_techno",), scale_hint="minor",
        sound="One stable 'ooh' note chopped by a gate; the second layer wider, then wider again; auto-pan, EQ and reverb.",
        description="Gated notes with longer notes and gaps instead of 16ths; a second line adds a harmony voice in some bars so a chord progression emerges from the gated leads.",
    ),
    LeadTemplate(
        "gnarly_phrygian_bass_lead", "Gnarly bass lead in Phrygian", "scale",
        {"main": Part((
            _b((1, 0.25, 0), (4, 0.25, 1), (7, 0.25, 0), (9, 0.5, 3), (12, 0.25, 1), (15, 0.25, 0)),
            _b((1, 0.25, 0), (4, 0.25, 1), (7, 0.25, 0), (9, 0.5, 4), (12, 0.25, 3), (15, 0.25, 1)),
        ), octave=-2)},
        genres=("afro_tech", "tech_house"), scale_hint="phrygian",
        sound="Combination of gnarly kick-based tones, full and mid bass layers, EQ; atmospheres in the background.",
        description="The flat second of Phrygian makes it dark and aggressive. Put the progression into the Phrygian scale instead of minor.",
    ),
    LeadTemplate(
        "emotional_pluck", "Emotional melodic techno pluck with call and response", "chord",
        {
            "main": Part((_seq((1, 2, 4, 5, 7, 8, 10, 11, 13, 15, 16), 0.2, (1,) * 11, 1),), ),
            "complement": Part((_b((3, 0.5, 0, 1), (4, 0.5, 1, 1), (11, 0.5, 0, 1), (12, 0.5, 1, 1)),), cycle=4, active=(1, 3), velocity=0.9),
        },
        genres=("melodic_techno",), scale_hint="minor",
        sound="Stereo saw pluck with chorus, reverb, delay and EQ; complements: a plucky saw and a square with detune and noise.",
        description="The third of the bass an octave up as a rolling pluck with a few gaps; the complement plays tone and third an octave up in some bars only, so it is fresh each time.",
    ),
    LeadTemplate(
        "epic_descending_motif", "Epic descending motif", "root_step",
        {"main": Part((
            _stack(1, 0.25, ((1, 0), (2, 0))) + _stack(3, 0.25, ((1, 0), (2, 0))) + _stack(5, 0.25, ((1, 0), (2, 0))),
            _stack(1, 0.25, ((1, 0), (2, 0))) + _stack(3, 0.25, ((1, 0), (2, 0))) + _stack(5, 0.25, ((1, 0), (2, 0))),
            _stack(1, 0.25, ((1, 0), (2, 0))) + _stack(3, 0.25, ((1, 0), (2, 0))) + _stack(5, 0.25, ((1, 0), (2, 0))),
            _stack(1, 0.25, ((1, 1), (2, 1))) + _stack(3, 0.25, ((1, 1), (2, 1))) + _stack(5, 0.25, ((1, 1), (2, 1))),
        ))},
        genres=("melodic_techno", "progressive"), scale_hint="dorian",
        sound="Plucky saw plus a super saw (big unison and detune) and a sustained super saw layer for the epic feeling; reverb and delay.",
        description="Answers the descending bass: the second and the third right above every bass note, as call and response; in the last bar of the phrase the pattern goes an octave up.",
    ),
    LeadTemplate(
        "one_note_lead", "One note lead over a moving bass", "scale",
        {
            "main": Part((_seq(tuple(range(1, 17, 2)), 0.3, (4, 2, 4, 2, 4, 2, 4, 2)),)),
            "string": Part((_b((1, 3.9, 0, -1)),), velocity=0.6),
        },
        genres=("melodic_techno", "afro_house", "melodic_house"),
        sound="Plucky saw with reverb and delay; automate it, a static one-note lead gets boring. An optional one-note string plays in the background.",
        description="Two notes in an 8th rhythm that stay the same while the bass and chords change underneath; the bass does the heavy lifting.",
    ),
)}


def _fold_root(pitch_class: int, octave: int) -> int:
    base = octave_base(octave)
    return base + (pitch_class - base) % 12


def _pitch(template: LeadTemplate, part: Part, note: LNote, chord_root: int, chord_intervals: tuple[int, ...], scale: Scale) -> int:
    shift = 12 * (note.octave + part.octave)
    if template.mode == "scale":
        return scale.pitch(note.degree, template.octave) + shift
    root = _fold_root(chord_root, template.octave)
    if template.mode == "chord":
        index = note.degree
        interval = chord_intervals[index] if 0 <= index < len(chord_intervals) else chord_intervals[index % len(chord_intervals)] + 12 * (index // len(chord_intervals))
        return root + interval + shift
    return scale.step(root, note.degree) + shift


def generate_lead_template(
    template: LeadTemplate, harmony: Harmony, scale: Scale, meter: Meter, bars: int,
    swing: float = 0.0, parts: tuple[str, ...] | None = None,
) -> dict[str, list[Note]]:
    """The notes of each part (all of them, or the named ones) over `bars` bars, following the chords."""
    grid = Grid(meter, STEP, swing, 0.25)
    result: dict[str, list[Note]] = {}
    for name, part in template.parts.items():
        if parts is not None and name not in parts:
            continue
        notes: list[Note] = []
        for bar in range(bars):
            if part.active and bar % part.cycle not in part.active:
                continue
            for note in part.bars[bar % len(part.bars)]:
                t = grid.position(bar, note.step - 1)
                chord = harmony.at(t).chord
                pitch = _pitch(template, part, note, chord.root, chord.intervals, scale)
                notes.append(Note(pitch, t, note.length, max(1.0, min(127.0, note.velocity * part.velocity))))
        result[name] = notes
    return result


def describe_lead(template: LeadTemplate) -> dict[str, object]:
    return {
        "name": template.name, "label": template.label, "parts": list(template.parts), "mode": template.mode,
        "genres": list(template.genres), "scale_hint": template.scale_hint, "pitch_bend": template.pitch_bend,
        "sound": template.sound, "description": template.description, "source": template.source,
    }
