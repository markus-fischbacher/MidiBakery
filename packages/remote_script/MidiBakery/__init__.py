"""MidiBakery bridge for Ableton Live 12.

Live loads this package as a Control Surface (Settings > Link, Tempo & MIDI)
and calls create_instance(). The bridge is deliberately thin: it exposes
atomic, validated Live Object Model operations over a local, token-protected
NDJSON socket. All musical logic lives in the MidiBakery core process.
"""


def create_instance(c_instance):
    from .surface import MidiBakerySurface

    return MidiBakerySurface(c_instance)
