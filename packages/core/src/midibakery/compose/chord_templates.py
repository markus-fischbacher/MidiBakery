"""The 15 emotion progressions of "15 Chord Progressions for 15 Different Emotions", as data.

Each template names a mood, the mode it is written in, the progression as roman numerals
(relative to the song's tonic) and the voicing the tutorial uses to "extract maximal
emotional energy": the roots doubled an octave down, the thirds moved up an octave, a pedal
tone on the tonic (or another scale degree) over the whole progression, seventh chords only
on some chords, and a long or short chord length.

The voice-over names the scale degrees for most moods. For "sad" the degrees are not said
(only the long chords and the downward movement), and for the major "1-7-6-5" the seventh is
read as a flat seventh; ``source`` says "described" for those two. The tutorial's example
songs are kept in ``reference`` as a hint for the sound, not as material.
"""

from __future__ import annotations

from dataclasses import dataclass

from midibakery.compose import harmony as harmony_mod
from midibakery.compose.harmony import Harmony
from midibakery.compose.notes import Note
from midibakery.compose.rhythm import Meter
from midibakery.compose.theory import MAJOR, Scale

MINOR = (0, 2, 3, 5, 7, 8, 10)


@dataclass(frozen=True)
class ChordTemplate:
    name: str
    label: str
    mood: str
    mode: str  # "major" or "minor": the scale the roman numerals are read in
    progression: str
    chords_per_bar: float = 1.0
    root_double: bool = True  # copy of the root an octave down
    third_up: bool = True  # the thirds an octave up, on top of the chord
    fifth: bool = True  # False: leave the fifth out
    pedal: tuple[int, ...] = ()  # scale degrees (0 = tonic) held over the whole progression
    anticipate: bool = False  # chords start an 8th early, on the upbeat
    articulation: str = "sustained"
    reference: str = ""
    description: str = ""
    source: str = "video"


CHORD_TEMPLATES: dict[str, ChordTemplate] = {t.name: t for t in (
    ChordTemplate(
        "uplifting_sweet", "Uplifting sweet", "uplifting", "minor", "VI i III VII", pedal=(0,),
        description="The 6, 1, 3 and 7 of the minor scale: triads with the thirds an octave up, the roots copied an octave down, and the tonic as a pedal tone because the chord changes are big.",
    ),
    ChordTemplate(
        "groove_funk", "Groove funk", "groovy", "minor", "i7 III7 iv7 iv7", articulation="upbeat",
        description="The 1, 3 and 4 of the minor scale with seventh chords (the third even as a sus2); roots down an octave, funky bass line, hits on the upbeats.",
        source="described",
    ),
    ChordTemplate(
        "dark_cinematic", "Dark cinematic", "dark", "minor", "i", chords_per_bar=0.25,
        description="The darkest, most ominous progression is a single minor chord held for the whole phrase: cinematic dark, not a song.",
    ),
    ChordTemplate(
        "dark_serious", "Dark serious", "dark", "minor", "i VI iv v", root_double=True,
        description="1 for two half notes, down to 6, 4 and up to 5 on a deep bass synth, with triads built on top: three minor chords out of four make the darker vibe. Best way: drop the thirds and fifths and keep one unchanging minor chord for the vocal.",
    ),
    ChordTemplate(
        "pure_joy", "Pure joy", "joyful", "major", "vi IV I ii", pedal=(0,), third_up=True,
        reference="works in any genre; also with a dance synth",
        description="6, 4 and 1 in a major scale, closed with one more chord, the ii (D minor in C); roots pulled down an octave, thirds on top, fifths pulled down, tonic as the pedal tone.",
    ),
    ChordTemplate(
        "funk_light", "Light funk", "groovy", "minor", "i7 VII III iv VI7 VII7", articulation="upbeat",
        description="1, 7, 3, 4, 6, 7 in a minor scale; the first, fifth and sixth chords are sevenths (not every chord, or the emotion washes out); upbeat hits, some extended, a seventh added to one chord.",
    ),
    ChordTemplate(
        "happy", "Happy", "happy", "major", "vi IV I V", fifth=False, anticipate=True,
        reference="Eric Prydz, Every Day",
        description="6, 4, 1, 5 in any major scale; the first chord is shortened so the next starts on the upbeat; roots down an octave and no fifths; a classic synth and a fun rhythm.",
    ),
    ChordTemplate(
        "sad", "Sad", "sad", "minor", "i VII VI v", chords_per_bar=0.5, pedal=(0,),
        reference="cellos on the pedal tone",
        description="Long drawn out chords (two whole notes each) moving down; roots doubled, a seventh, a ninth and a passing note; a pedal tone on the tonic and cellos to go one step further.",
        source="described",
    ),
    ChordTemplate(
        "bittersweet", "Bittersweet sad", "bittersweet", "minor", "VI VI i VII",
        reference="Porter Robinson, Language",
        description="The 6 for two whole notes, up to the 1, down to the 7 (single whole notes). Already sad before it is voiced, gorgeous in any voicing.",
    ),
    ChordTemplate(
        "dreamy_indie", "Dreamy indie", "dreamy", "minor", "i VI III II", chords_per_bar=2, pedal=(0,),
        reference="MGMT, Kids: pedal tones and pulsing roots",
        description="Half-note chords on the 1, 6, 3 and 2 of the minor scale; the diminished chord on the 2 is swapped for its major neighbour (it ruins the progression); thirds on top, roots doubled, a pulsing root and a tonic pedal for the indie nostalgia.",
    ),
    ChordTemplate(
        "sad_neutral", "Sad neutral", "neutral sad", "minor", "i VII VI VII", pedal=(0,),
        description="Whole-note chords descending 1, 7, 6, 7 in a minor scale, thirds on top. Musical sad, not cinematic; a pedal tone on the tonic crushes it deeper.",
    ),
    ChordTemplate(
        "heroic_pivot", "Heroic pivot (sad neutral turned hopeful)", "resolute", "minor", "VI VII i VII", pedal=(2,),
        description="The sad neutral progression pivoted: the first chord goes to the 6, the 6 takes the place of the 1, and the pedal tone moves to the third degree (the relative major tonic): more hopeful, more heroic.",
    ),
    ChordTemplate(
        "melancholic", "Melancholic", "melancholic", "minor", "i III v", pedal=(0, 4),
        reference="Rufus Du Sol, Innerbloom",
        description="1, 3 and 5 of a minor scale; melancholic progressions love pedal tones, notes that stay through the whole progression and carry a dreaminess; re-voice the chords up high.",
    ),
    ChordTemplate(
        "resolute_major", "Emotional toughness (descending from a major tonic)", "resolute", "major", "I bVII vi V",
        reference="David Guetta, Titanium",
        description="1, 7, 6, 5 in a major scale: it moves downward, which usually sounds sad, but starting on the major tonic it carries happy energy and standing-your-ground toughness. It gets cheesy with a cheap instrument, so voice and articulate it well.",
        source="described",
    ),
    ChordTemplate(
        "euphoric_neutral", "Euphoric neutral", "euphoric", "minor", "v VI i VII", pedal=(0, 4),
        reference="Illenium",
        description="5, 6, 1, 7 in a minor scale on a soft emotional piano: the 5, 6 and 7 are the most emotional chords of the minor scale; triads, thirds on top, a double pedal tone.",
    ),
)}


def template_scale(template: ChordTemplate, tonic: Scale) -> Scale:
    """The scale the template's roman numerals are read in, on the song's tonic."""
    if template.mode == "major":
        return Scale(tonic.root, MAJOR, "Major")
    return Scale(tonic.root, MINOR, "Minor")


def template_harmony(template: ChordTemplate, tonic: Scale, meter: Meter, bars: int) -> Harmony:
    return harmony_mod.from_progression(template.progression, template_scale(template, tonic), meter, bars, template.chords_per_bar)


def generate_chord_template(
    template: ChordTemplate, tonic: Scale, harmony: Harmony | None, meter: Meter, bars: int, octave: int = 3,
) -> dict[str, list[Note]]:
    """Voiced chords (and the pedal tone) of the template; `harmony` defaults to its own progression."""
    scale = template_scale(template, tonic)
    harmony = harmony or template_harmony(template, tonic, meter, bars)
    base = 12 * (octave + 2)  # Live C3 = 60
    chords: list[Note] = []
    early = 0.5 if template.anticipate else 0.0
    for index, segment in enumerate(harmony.segments):
        chord = segment.chord
        root = base + (chord.root - base) % 12
        pitches = [root + chord.intervals[0]]
        for tone, interval in enumerate(chord.intervals[1:], start=1):
            if tone == 2 and not template.fifth and len(chord.intervals) > 2 and interval - chord.intervals[0] in (6, 7, 8):
                continue
            pitches.append(root + interval + (12 if template.third_up and tone == 1 else 0))
        if template.root_double:
            pitches.append(root - 12)
        # Anticipated: the first chord is shortened, every later one starts an 8th early (on the upbeat)
        start = segment.start - early if index else segment.start
        length = segment.length - early if index == 0 else segment.length
        chords += [Note(p, start, max(0.25, length), 90) for p in sorted(set(pitches))]
    result = {"chords": chords}
    if template.pedal and harmony.segments:
        end = harmony.segments[-1].end
        result["pedal"] = [Note(scale.pitch(degree, octave + 1), 0.0, end, 70) for degree in template.pedal]
    return result


def describe_chords(template: ChordTemplate) -> dict[str, object]:
    return {
        "name": template.name, "label": template.label, "mood": template.mood, "mode": template.mode,
        "progression": template.progression, "chords_per_bar": template.chords_per_bar,
        "pedal": list(template.pedal), "reference": template.reference, "description": template.description,
        "source": template.source,
    }
