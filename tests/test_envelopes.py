"""Clip automation on existing clips: targets, shapes, units, and arrangement clips."""

import pytest

from midibakery.bridge import BridgeError

KICK = {"pitch": 36, "start_time": 0.0, "duration": 0.25, "velocity": 100}


def _setup(song):
    track = song.tracks[0]
    track.insert_device("Auto Filter", 0)
    song.create_return_track()
    track.clip_slots[0].create_clip(8)
    return track


def _values(live, slot=None, arrangement=None, param=None, times=()):
    def read():
        track = live.song.tracks[0]
        clip = track.clip_slots[slot].clip if slot is not None else sorted(track.arrangement_clips, key=lambda c: c.start_time)[arrangement]
        envelope = clip.envelopes.get(id(param(track)))
        return None if envelope is None else [round(envelope.value_at_time(t), 4) for t in times]

    return live.on_main(read)


def _freq(track):
    return track.devices[0].parameters[2]  # Filter Freq, 20-20000; the fake shows the raw value


async def test_shapes_on_a_session_clip(client, live):
    live.on_main(lambda: _setup(live.song))
    result = await client.call("clip.envelope", {"track": 0, "slot": 0, "envelopes": [
        {"device": 0, "parameter": "Filter Freq", "unit": "display",
         "shapes": [{"type": "triangle", "length": 8, "from_value": 400, "to_value": 3000, "period": 4}]},
        {"parameter": "Volume", "unit": "display", "shapes": [{"type": "square", "length": 8, "from_value": 0, "to_value": -12, "period": 2}]},
        {"parameter": "Send A", "points": [[0, 0.0], [8, 0.5]]},
    ]})
    assert [e["parameter"] for e in result["envelopes"]] == ["Filter Freq", "Track Volume", "A-Send"]
    assert result["envelopes"][0]["check"] == ["562.50", "2837.50", "562.50", "2837.50", "562.50"]  # an 8th into each half
    assert _values(live, slot=0, param=_freq, times=(0, 2, 4, 6)) == [pytest.approx(400, abs=40), pytest.approx(3000, abs=40),
                                                                      pytest.approx(400, abs=40), pytest.approx(3000, abs=40)]
    volume = _values(live, slot=0, param=lambda t: t.mixer_device.volume, times=(0.5, 1.5))
    assert volume == [pytest.approx(0.85, abs=0.01), pytest.approx(0.55, abs=0.01)]  # 0 dB, then -12 dB
    assert _values(live, slot=0, param=lambda t: t.mixer_device.sends[0], times=(0, 8)) == [0.0, 0.5]


def test_shape_points():
    from MidiBakery.ops.envelopes import _shape_points

    exp = _shape_points({"type": "exp", "start": 0, "length": 8, "from_value": 0, "to_value": 1})
    assert exp[0] == (0.0, 0.0) and exp[-1] == (8.0, pytest.approx(1.0)) and exp[len(exp) // 2][1] < 0.2  # slow start
    log = _shape_points({"type": "log", "start": 0, "length": 8, "from_value": 0, "to_value": 1})
    assert log[len(log) // 2][1] > 0.8
    saw = _shape_points({"type": "saw", "start": 0, "length": 4, "from_value": 0, "to_value": 1, "period": 1})
    assert [round(t, 2) for t, _ in saw[:4]] == [0, 0.99, 1, 1.99] and saw[2][1] == 0  # rises, jumps back
    sine = _shape_points({"type": "sine", "start": 2, "length": 4, "from_value": 0, "to_value": 10, "period": 4})
    assert sine[0] == (2.0, 0.0) and max(v for _, v in sine) == pytest.approx(10) and sine[-1][1] == pytest.approx(0)


async def test_an_existing_envelope_is_replaced_or_added_to(client, live):
    live.on_main(lambda: _setup(live.song))
    args = {"track": 0, "slot": 0, "envelopes": [{"device": 0, "parameter": "Filter Freq", "points": [[0, 0.0], [4, 1.0]]}]}
    await client.call("clip.envelope", args)
    await client.call("clip.envelope", {**args, "envelopes": [{"device": 0, "parameter": "Filter Freq", "points": [[6, 0.5]]}], "clear": False})
    assert _values(live, slot=0, param=_freq, times=(0, 4, 6)) == [20.0, 20000.0, pytest.approx(10010.0)]
    await client.call("clip.envelope", {**args, "envelopes": [{"device": 0, "parameter": "Filter Freq", "points": [[6, 0.5]]}]})
    assert _values(live, slot=0, param=_freq, times=(0, 4)) == [pytest.approx(10010.0)] * 2


async def test_an_arrangement_clip_is_only_rebuilt_when_asked(client, live):
    live.on_main(lambda: _setup(live.song))
    await client.call("arrangement.edit", {"actions": [
        {"action": "add_clip", "track": 0, "start": 0, "length": 8, "name": "Plain", "notes": [KICK]},
        {"action": "add_clip", "track": 0, "start": 16, "length": 8, "name": "Drop", "notes": [KICK],
         "envelopes": [{"device": 0, "parameter": "Filter Freq", "points": [[0, 0.0], [8, 1.0]]}]},
    ]})
    send = {"parameter": "Send A", "unit": "display", "shapes": [{"type": "ramp", "start": 4, "length": 4, "from_value": -60, "to_value": -6}]}
    with pytest.raises(BridgeError, match="replace_envelopes=true") as exc:  # Live cannot tell whether it has envelopes
        await client.call("clip.envelope", {"track": 0, "arrangement_clip": 0, "envelopes": [send]})
    assert exc.value.code == "CONFLICT"
    plain = await client.call("clip.envelope", {"track": 0, "arrangement_clip": 0, "envelopes": [send], "replace_envelopes": True})
    assert "rebuilt" in plain and plain["envelopes"][0]["check"][0] == "-33.9 dB"  # read on the session copy; the fake's quietest step
    keep = {"device": 0, "parameter": "Filter Freq", "points": [[0, 0.0], [8, 1.0]]}
    await client.call("clip.envelope", {"track": 0, "arrangement_clip": 1, "envelopes": [keep, send], "replace_envelopes": True})

    def clips():
        track = live.song.tracks[0]
        return ([(c.name, c.start_time, c.end_time, len(c.notes)) for c in sorted(track.arrangement_clips, key=lambda c: c.start_time)],
                sum(s.has_clip for s in track.clip_slots))

    assert live.on_main(clips) == ([("Plain", 0.0, 8.0, 1), ("Drop", 16.0, 24.0, 1)], 1)  # the user's session clip stays
    assert _values(live, arrangement=1, param=_freq, times=(0, 4)) == [20.0, pytest.approx(10010.0, rel=0.05)]
    ramp = _values(live, arrangement=1, param=lambda t: t.mixer_device.sends[0], times=(5, 7.9))
    assert 0 < ramp[0] < ramp[1]


async def test_bad_targets(client, live):
    live.on_main(lambda: _setup(live.song))
    with pytest.raises(BridgeError, match="the mixer has no 'Send C'") as exc:
        await client.call("clip.envelope", {"track": 0, "slot": 0, "envelopes": [{"parameter": "Send C", "points": [[0, 1]]}]})
    assert exc.value.details["available"] == ["Volume", "Pan", "Send A"]
    with pytest.raises(BridgeError, match="shows no number"):
        await client.call("clip.envelope", {"track": 0, "slot": 0, "envelopes": [
            {"device": 0, "parameter": "Filter Type", "unit": "display", "points": [[0, 1]]}]})
