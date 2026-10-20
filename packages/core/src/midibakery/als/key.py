"""The key of a Set: from the scale Live 12 clips are set to, else from the notes (Krumhansl-Kessler).

A guess ends with "?" ("G minor?"), the same convention as the Reference Analyzer: relative keys share their
notes, so a close call between them is not certain.
"""

from __future__ import annotations

from collections import Counter

from midibakery.als.reader import Song
from midibakery.als.roles import MELODIC
from midibakery.compose.theory import NOTE_NAMES

MAJOR_PROFILE = (6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88)
MINOR_PROFILE = (6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17)
LIVE_SCALES = {0: "major", 1: "minor"}  # Live 12's scale list starts Major, Minor, Dorian, ...
CLEAR_MARGIN = 0.08  # the best fit must beat the best unrelated key by this much to be certain


def _correlation(histogram: list[float], profile: tuple[float, ...], shift: int) -> float:
    rotated = [profile[(i - shift) % 12] for i in range(12)]
    mean_h, mean_p = sum(histogram) / 12, sum(rotated) / 12
    num = sum((h - mean_h) * (p - mean_p) for h, p in zip(histogram, rotated))
    den = (sum((h - mean_h) ** 2 for h in histogram) * sum((p - mean_p) ** 2 for p in rotated)) ** 0.5
    return num / den if den else 0.0


def _relative(root: int, mode: str) -> int:
    return (root + 3) % 12 if mode == "minor" else (root + 9) % 12


def from_notes(song: Song, roles: dict[int, str]) -> str | None:
    histogram = [0.0] * 12
    for track in song.tracks:
        if roles.get(track.index) not in MELODIC:
            continue
        for clip in track.clips:
            for note in clip.notes:
                histogram[note.pitch % 12] += min(note.duration, 4.0)
    if sum(histogram) <= 0:
        return None
    scored = sorted(((_correlation(histogram, profile, root), root, mode)
                     for root in range(12) for mode, profile in (("major", MAJOR_PROFILE), ("minor", MINOR_PROFILE))),
                    reverse=True)
    best, root, mode = scored[0]
    related = _relative(root, mode)
    rival = next(score for score, r, m in scored[1:] if not (r == related and m != mode))
    certain = best - rival >= CLEAR_MARGIN
    return f"{NOTE_NAMES[root]} {mode}{'' if certain else '?'}"


def from_clips(song: Song) -> str | None:
    """The scale Live 12 clips are 'in key' with, when the Set uses one."""
    votes = Counter(t.scale for t in song.tracks if t.scale and t.scale[1].isdigit() and int(t.scale[1]) in LIVE_SCALES)
    if not votes:
        return None
    (root, name), _ = votes.most_common(1)[0]
    return f"{NOTE_NAMES[root % 12]} {LIVE_SCALES[int(name)]}"


def detect(song: Song, roles: dict[int, str]) -> str:
    return from_clips(song) or from_notes(song, roles) or "?"
