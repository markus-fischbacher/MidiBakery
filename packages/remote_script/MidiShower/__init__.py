"""MidiShower bridge for Ableton Live 12.

Live loads this package as a Control Surface (Settings > Link, Tempo & MIDI)
and calls create_instance(). The bridge is deliberately thin: it exposes
atomic, validated Live Object Model operations over a local, token-protected
NDJSON socket. All musical logic lives in the MidiShower core process.
"""


def create_instance(c_instance):
    from .surface import MidiShowerSurface

    return MidiShowerSurface(c_instance)
