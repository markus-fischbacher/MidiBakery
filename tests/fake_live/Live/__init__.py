"""Minimal stand-in for Live's embedded `Live` module, for contract tests.

Only what the MidiShower Remote Script touches is modelled. Every attribute
access on a LiveObject asserts it happens on the thread registered as Live's
main thread, so tests catch LOM calls from socket threads.
"""

import threading

from . import Application, Clip  # noqa: F401

MAIN_THREAD = {"ident": None}


class OffMainThreadAccess(AssertionError):
    pass


class LiveObject(object):
    def __getattribute__(self, name):
        ident = MAIN_THREAD["ident"]
        if ident is not None and not name.startswith("__") and threading.get_ident() != ident:
            raise OffMainThreadAccess("LOM access to %s.%s off the main thread" % (type(self).__name__, name))
        return object.__getattribute__(self, name)
