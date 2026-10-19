"""What each track of a Set does: kick, drums, bass, chords, lead, fx, sidechain, or unknown.

Order of evidence: the track's name, then its instrument (a Drum Rack is drums), then the pitch range
of its notes. A track none of that places is "unknown": better unlabeled than guessed.
"""

from __future__ import annotations

from statistics import median

from midibakery.als.reader import Song, Track
from midibakery.compose.drums import classify_pad

# First match wins: "Kick Rumble" is a kick, "Acid Fx" an fx, "Bass Reverb" (a return) is none of them.
NAME_WORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("sidechain", ("sidechain", "trigger", "ghost", "sc comp", "duck")),
    ("kick", ("kick", "bd ", "bassdrum")),
    ("fx", ("riser", "uplift", "impact", "sweep", "fx", "noise", "crash", "downlifter", "transition", "whoosh",
            "boom", "reverse", "texture", "atmo", "ambience", "foley")),
    ("drums", ("drum", "hat", "clap", "snare", "perc", "ride", "shaker", "tom", "cymbal", "rim", "top loop",
               "loop", "hit")),
    ("bass", ("bass", "sub", "808", "rumble", "reese")),
    ("chords", ("chord", "pad", "key", "piano", "stab", "organ", "string", "rhodes", "harmony")),
    ("lead", ("lead", "melody", "synth", "arp", "pluck", "riff", "hook", "bell", "vocal", "vox", "horn", "marimba",
              "squeak")),
)
MELODIC = ("bass", "chords", "lead")
PLAYING_ROLES = ("kick", "drums", "bass", "chords", "lead", "fx")


def _from_name(name: str) -> str | None:
    text = f" {name.lower()} "
    for role, words in NAME_WORDS:
        if any(w in text for w in words):
            return role
    return None


def _drum_rack_role(track: Track) -> str | None:
    for device in track.devices:
        if device.kind == "Drum Rack" and device.pads:
            roles = {classify_pad(p.name) for p in device.pads if p.name}
            return "kick" if roles == {"kick"} else "drums"
    return None


def _from_notes(track: Track) -> str | None:
    pitches = [n.pitch for c in track.clips for n in c.notes]
    if not pitches:
        return None
    middle = median(pitches)
    return "bass" if middle < 52 else "lead"


def track_role(track: Track) -> str:
    if track.kind in ("group", "return"):
        return track.kind
    named = _from_name(track.name)
    if named:
        return named
    if track.kind == "midi":
        return _drum_rack_role(track) or _from_notes(track) or "unknown"
    return "unknown"


def assign(song: Song) -> dict[int, str]:
    """Track index -> role."""
    return {t.index: track_role(t) for t in song.tracks}
