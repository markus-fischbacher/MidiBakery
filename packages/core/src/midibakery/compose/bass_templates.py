"""Named bass patterns from the "19 Bass Patterns Changed My Life" tutorial, as data.

Steps count 1-16 in a 4/4 bar of 16ths (step 1 = beat 1, 5 = beat 2 ...), lengths are in
beats; a length longer than the gap to the next note overlaps it (legato / glide on a mono
synth). Intervals are semitones above the chord root and may be negative (the evil pattern
moves by semitones below the root). A template with a ``layer`` has a second voice, usually
a bright or sustained part on top; ``sidechain`` says the tutorial ducks the bass to the
kick: the notes do not change, it is a mixing hint returned with the notes.

Provenance: the video shows most patterns only for a few seconds. Where a piano roll is
readable the rhythm comes from it (``source="roll"``); otherwise it is built from what the
voice-over says (``source="described"``), so treat those as a starting point.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from midibakery.compose.harmony import Harmony
from midibakery.compose.notes import Note
from midibakery.compose.rhythm import Grid, Meter

STEP = 0.25


@dataclass(frozen=True)
class TNote:
    step: int
    length: float
    interval: int = 0
    velocity: float = 100


Bar = tuple[TNote, ...]


@dataclass(frozen=True)
class BassTemplate:
    name: str
    label: str
    genres: tuple[str, ...]
    bpm: tuple[int, int]
    bars: tuple[Bar, ...]  # one bar per entry, cycled
    low: int = 33  # MIDI range the root is folded into
    high: int = 45
    layer: tuple[Bar, ...] = ()
    layer_low: int = 45
    layer_high: int = 57
    straight: bool = True
    swing: float = 0.0  # used when not straight
    sidechain: bool = False
    note_follow: bool = False  # filter cutoff follows the note (extreme octave jumps)
    description: str = ""
    source: str = "described"  # "roll" or "described"


def _run(steps: tuple[int, ...], length: float, interval: int | tuple[int, ...] = 0, velocity: float = 100) -> Bar:
    intervals = (interval,) * len(steps) if isinstance(interval, int) else interval
    return tuple(TNote(s, length, i, velocity) for s, i in zip(steps, intervals))


ALL16 = tuple(range(1, 17))
EIGHTHS = tuple(range(1, 17, 2))
OFFBEAT = (3, 7, 11, 15)

BASS_TEMPLATES: dict[str, BassTemplate] = {t.name: t for t in (
    BassTemplate(
        "rolling_16", "Rolling bass, 16 hits per bar", ("techno", "tech_house", "psy"), (125, 140),
        (_run(ALL16, 0.2),),
        description="The standard rolling bass: a note on every 16th, short gate.", source="roll",
    ),
    BassTemplate(
        "rolling_octaves", "Rolling bass with octave drama", ("techno", "tech_house"), (125, 140),
        (_run(ALL16, 0.2, (0, 12) * 8),),
        description="Rolling 16ths, every second note an octave up for more drama.",
    ),
    BassTemplate(
        "rolling_legato_octaves", "Rubbery legato octave roll", ("techno", "tech_house"), (125, 140),
        (_run(ALL16, 0.3, (0, 0, 12, 12) * 4),),
        description="Same rolling pattern with octave pairs, notes overlapping (legato on a mono synth) for the rubbery sound.",
    ),
    BassTemplate(
        "rolling_groove_gap", "Rolling bass without the first two notes", ("techno", "tech_house"), (125, 140),
        (_run(ALL16[2:], 0.2),),
        description="Delete the first two 16ths: the gap lets the kick through and adds groove.", source="roll",
    ),
    BassTemplate(
        "octave_jump_single", "One bass line, octave jumps", ("techno", "melodic_techno"), (122, 135),
        ((TNote(1, 1.25), TNote(6, 0.5, 12), TNote(9, 1.25), TNote(14, 0.5, 12)),),
        description="Simple and dramatic: long root notes answered by short octave jumps.", source="roll",
    ),
    BassTemplate(
        "octave_jump_extreme", "Extreme octave jumps (note follow)", ("techno", "bass_music"), (122, 140),
        ((TNote(1, 1.25), TNote(6, 0.5, 24), TNote(9, 1.25), TNote(14, 0.5, 12)),),
        low=29, high=41, note_follow=True,
        description="Jumps of up to two octaves; the synth's filter follows the note so the jump gets brighter.",
    ),
    BassTemplate(
        "offbeat_fast", "Offbeat bass for fast tempos", ("hard_techno", "trance", "hardstyle"), (145, 160),
        (_run(OFFBEAT, 0.5),),
        description="At 150 bpm few notes sound fast: one bass note on every offbeat.", source="roll",
    ),
    BassTemplate(
        "offbeat_chord_octave", "Offbeat bass, sustained chord layer", ("hard_techno", "trance"), (145, 160),
        (_run(OFFBEAT[:-1], 0.5) + (TNote(15, 0.5, 12),),),
        layer=((TNote(1, 3.9, 12, 80),),),
        description="The offbeat leaves room for a sustained bass on top that follows the chord progression; the last offbeat jumps an octave.",
    ),
    BassTemplate(
        "tekkaos_phrygian", "Groovy tech house, Phrygian half notes", ("tech_house", "techno"), (124, 132),
        (
            (TNote(1, 0.25), TNote(3, 0.25), TNote(5, 0.5), TNote(8, 0.5, 1), TNote(13, 1.0)),
            (TNote(1, 0.25), TNote(3, 0.25), TNote(5, 0.5), TNote(8, 0.5, 1), TNote(13, 0.5), TNote(15, 0.5, 12)),
        ),
        low=29, high=40, sidechain=True,
        description="A short repeating figure, then half notes using the flat second of the Phrygian scale; the second bar adds an octave jump. Duck to the kick.",
        source="roll",
    ),
    BassTemplate(
        "hybrid_eighths_high", "Hybrid: 8ths low, patterns on the high bass", ("hybrid", "tech_house", "bass_music"), (128, 140),
        (_run(EIGHTHS, 0.4, 0, 100),),
        layer=(
            (TNote(3, 0.25, 12), TNote(8, 0.25, 15), TNote(11, 0.25, 12), TNote(14, 0.25, 17)),
            (TNote(3, 0.25, 12), TNote(6, 0.25, 15), TNote(11, 0.25, 12), TNote(16, 0.25, 19)),
        ),
        sidechain=True,
        description="Eight bass notes per bar, heavily ducked to the kick, which frees the high bass for syncopated patterns; delay on the top layer.",
    ),
    BassTemplate(
        "argy_fast_slow", "Fast and slow, off the grid", ("progressive", "melodic_techno"), (122, 130),
        ((TNote(3, 1.0), TNote(8, 0.25), TNote(10, 0.5), TNote(15, 0.25)),),
        straight=False, swing=0.12, low=24, high=36,
        description="Few notes with long and short values mixed, played off the beat and not snapped to the grid so the groove stands out.",
        source="roll",
    ),
    BassTemplate(
        "argy_bumpy", "Same rhythm, bumpier", ("progressive", "melodic_techno"), (122, 130),
        ((TNote(3, 1.0), TNote(8, 0.25, 12), TNote(10, 0.5), TNote(15, 0.25, 12)),),
        straight=False, swing=0.12, low=24, high=36,
        description="The fast/slow rhythm with octave bumps on the short notes.",
    ),
    BassTemplate(
        "argy_up_down_high", "Up and down, pulled high", ("progressive", "melodic_techno"), (122, 130),
        (_run(EIGHTHS, 0.4, (0, 12) * 4),),
        low=36, high=48,
        description="Alternating low/high 8ths; raise the register and open the filter for a slowly ascending feel.",
    ),
    BassTemplate(
        "rolling_then_jump", "Less groove, more power: gaps, roll, jump", ("techno", "peak_time_techno"), (128, 138),
        ((TNote(1, 0.2), TNote(2, 0.2), TNote(3, 0.2), TNote(4, 0.2), TNote(9, 0.9, 12), TNote(13, 0.2), TNote(14, 0.2)),),
        description="Leave spaces, start with a short roll and jump an octave; a bit of filter automation at the end of the phrase.",
        source="roll",
    ),
    BassTemplate(
        "kick_tumble", "Tumbling kick groove under any bass", ("techno", "tech_house"), (126, 136),
        ((TNote(1, 0.4), TNote(4, 0.4), TNote(7, 0.4), TNote(10, 0.4), TNote(13, 0.4), TNote(16, 0.2)),),
        sidechain=True,
        description="A kick plus a second, very short kick create a 3-3-3-3-3-1 tumbling rhythm; any bass line can sit on top of it.",
    ),
    BassTemplate(
        "rolling_bass_lead", "Rolling bass plus bass lead layer", ("techno", "tech_house"), (126, 138),
        (_run((2, 3, 4, 6, 7, 8, 10, 11, 12, 14, 15, 16), 0.2),),
        layer=(_run(EIGHTHS, 0.2, 12, 92),),
        description="Keep the rolling pattern and add a brighter, stronger bass lead with a different pattern; it changes the whole bar.",
        source="roll",
    ),
    BassTemplate(
        "tech_house_phrase", "Tech house phrase, developed over two bars", ("tech_house",), (124, 132),
        (
            (TNote(1, 0.25, 1), TNote(3, 0.25), TNote(5, 0.25), TNote(7, 0.25), TNote(9, 0.25), TNote(12, 0.25), TNote(14, 0.25), TNote(16, 0.25)),
            (TNote(1, 0.25), TNote(3, 0.25), TNote(5, 0.25), TNote(8, 0.5, 7), TNote(9, 0.25), TNote(11, 0.25, 1), TNote(12, 0.25), TNote(14, 0.25), TNote(16, 0.25)),
        ),
        low=31, high=43,
        description="Phrygian: state a simple phrase in bar one (flat second on the downbeat), develop it in the next bar with a fifth an octave up.",
        source="roll",
    ),
    BassTemplate(
        "evil_semitones", "The evil semitone pattern", ("bass_music", "hard_techno", "dubstep"), (135, 150),
        ((TNote(1, 0.9), TNote(5, 0.9, 1), TNote(9, 1.0), TNote(13, 0.9, -1)),),
        low=29, high=41,
        description="Start on one note, move up by a semitone, back, then one semitone below: semitones up, semitones down and one more down.",
        source="roll",
    ),
    BassTemplate(
        "evil_kick_locked", "Evil pattern locked to the kick, sidechained", ("bass_music", "hard_techno"), (135, 150),
        ((TNote(1, 0.25), TNote(4, 0.25), TNote(7, 0.25, 1), TNote(11, 0.25), TNote(13, 0.25, -1)),),
        low=29, high=41, sidechain=True,
        description="Make a bass note where the kick hits and sidechain the other bass to that kick.",
    ),
)}


def _fold(pitch_class: int, low: int, high: int) -> int:
    pitch = low + (pitch_class - low) % 12
    return pitch if pitch <= high else pitch - 12


def _voice(bars_pattern: tuple[Bar, ...], harmony: Harmony, meter: Meter, bars: int, grid: Grid, low: int, high: int) -> list[Note]:
    notes = []
    for bar in range(bars):
        for note in bars_pattern[bar % len(bars_pattern)]:
            t = grid.position(bar, note.step - 1)
            root = _fold(harmony.at(t).chord.root, low, high)
            notes.append(Note(root + note.interval, t, note.length, note.velocity))
    return notes


def generate_bass_template(template: BassTemplate, harmony: Harmony, meter: Meter, bars: int, swing: float | None = None) -> dict[str, list[Note]]:
    """``{"main": notes}`` and, for a template with a second voice, ``"layer"``: both on the chord roots."""
    grid = Grid(meter, STEP, 0.0 if template.straight and swing is None else (template.swing if swing is None else swing), 0.25)
    result = {"main": _voice(template.bars, harmony, meter, bars, grid, template.low, template.high)}
    if template.layer:
        result["layer"] = _voice(template.layer, harmony, meter, bars, grid, template.layer_low, template.layer_high)
    return result


def describe_template(template: BassTemplate) -> dict[str, object]:
    return {
        "name": template.name, "label": template.label, "genres": list(template.genres), "bpm": list(template.bpm),
        "layers": 2 if template.layer else 1, "sidechain": template.sidechain, "note_follow": template.note_follow,
        "description": template.description, "source": template.source,
    }


def pick_template(genre: str, rng: random.Random) -> BassTemplate:
    matching = [t for t in BASS_TEMPLATES.values() if genre in t.genres]
    return rng.choice(matching or list(BASS_TEMPLATES.values()))
