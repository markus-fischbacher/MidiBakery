"""The Remote Script's own boundary check (MidiBakery/protocol.py) against the generated manifest:
nested objects and lists, bounds, alternatives. The core validates with Pydantic first; this guards
clients that talk to the bridge directly."""

import pytest
from MidiBakery.protocol import OpError, load_manifest, validate

MANIFEST = load_manifest()


def _error(op, params):
    with pytest.raises(OpError) as exc:
        validate(MANIFEST, op, params)
    assert exc.value.code == "INVALID_PARAMS"
    return exc.value


def test_nested_note_out_of_range_names_its_path():
    err = _error("notes.apply", {"track": 0, "slot": 0, "add": [
        {"pitch": 60, "start_time": 0, "duration": 1},
        {"pitch": 200, "start_time": 0, "duration": 1},
    ]})
    assert err.message == "Parameter 'add[1].pitch' must be at most 127"
    assert err.details["parameter"] == "add[1].pitch"


def test_nested_unknown_and_missing_keys():
    err = _error("notes.apply", {"track": 0, "slot": 0, "add": [{"pitch": 60, "start_time": 0, "duration": 1, "colour": 3}]})
    assert err.message == "Unknown parameter(s) in 'add[0]': colour"
    err = _error("notes.apply", {"track": 0, "slot": 0, "modify": [{"pitch": 61}]})
    assert err.message == "Missing parameter(s) in 'modify[0]': note_id"


def test_actions_are_checked_by_their_kind():
    err = _error("arrangement.edit", {"actions": [{"action": "add_clip", "track": 0, "length": 4}]})
    assert err.message == "Missing parameter(s) in 'actions[0]': start"
    err = _error("arrangement.edit", {"actions": [{"action": "explode", "track": 0}]})
    assert err.message.startswith("Parameter 'actions[0].action' must be one of 'add_clip'")
    err = _error("arrangement.edit", {"actions": [{"action": "add_clip", "track": 0, "start": 0, "length": 4,
                                                   "notes": [{"pitch": 60, "start_time": -1, "duration": 1}]}]})
    assert err.message == "Parameter 'actions[0].notes[0].start_time' must be at least 0"


def test_optional_values_and_alternatives():
    validate(MANIFEST, "device.routing", {"track": 0, "device": 0, "channel": ["Post FX", "Pre FX"], "input": None})
    err = _error("device.routing", {"track": 0, "device": 0, "channel": [1]})
    assert err.message == "Parameter 'channel' must be string or array or null"
    err = _error("device.routing", {"track": -1, "device": 0})
    assert err.message == "Parameter 'track' must be at least 0"
    err = _error("batch", {"ops": []})
    assert err.message == "Parameter 'ops' needs at least 1 item(s)"


def test_top_level_messages_stay_as_they_were():
    assert _error("track.set", {"track": 0, "bogus": 1}).message == "Unknown parameter(s): bogus"
    assert _error("notes.apply", {"slot": 0}).message.startswith("Missing parameter(s): track")
    assert _error("track.set", {"track": "zero"}).message == "Parameter 'track' must be integer"
