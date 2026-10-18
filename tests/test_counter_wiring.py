"""Counter melody through compose, plan_changes and compose_takes, against the fake LOM."""

import json

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from fake_song import DrumRackDevice
from midibakery.compose.counter import FIGURES, MODES
from midibakery.mcp import build_server

# C major lead, bar by bar: long notes with rests the counter can answer in
LEAD = [(76, 0.0, 1.5), (74, 2.0, 1.0), (72, 4.0, 2.0), (79, 7.0, 0.5), (77, 8.0, 1.5), (76, 10.0, 1.0), (74, 12.0, 3.0)]


def _payload(result):
    return json.loads(result.content[0].text)


def _clip_notes(live, track, slot):
    return live.on_main(lambda: sorted(live.song.tracks[track].clip_slots[slot].clip.notes.values(), key=lambda n: (n["start_time"], n["pitch"])))


async def _lead(client, track=1, slot=0, notes=LEAD):
    await client.call("clip.create", {"track": track, "slot": slot, "length": 16})
    if notes:
        await client.call("notes.apply", {"track": track, "slot": slot, "add": [
            {"pitch": p, "start_time": s, "duration": d} for p, s, d in notes]})


def _sounding(start, lead=LEAD):
    return next((p for p, s, d in lead if s <= start + 1e-6 < s + d - 1e-6), None)


async def test_compose_a_counter_melody_above_the_lead(client, live):
    await _lead(client)
    result = _payload(await build_server(client).call_tool("compose", {
        "kind": "melody", "track": 0, "slot": 0, "bars": 4, "seed": 3, "counter_to": {"track": 1, "slot": 0}, "chords_from": {"track": 1, "slot": 0},
    }))
    change = result["changes"][0]
    assert change["counter_to"] == "slot index 0 on track index 1" and change["main_notes"] == len(LEAD)
    assert change["counter_mode"] == "fill_the_gaps" and change["counter_register"] == "above"
    assert "chords_note" not in change  # chords were given
    notes = _clip_notes(live, 0, 0)
    assert notes and min(n["pitch"] for n in notes) > max(p for p, _, _ in LEAD) - 1
    for n in notes:
        main = _sounding(n["start_time"])
        if main is not None and n["start_time"] % 4 in (0.0, 2.0):  # strong beats keep a consonant interval
            assert (n["pitch"] - main) % 12 in (0, 3, 4, 7, 8, 9)


@pytest.mark.parametrize("mode", MODES)
async def test_every_mode_and_register_is_reachable(client, live, mode):
    await _lead(client)
    result = _payload(await build_server(client).call_tool("compose", {
        "kind": "melody", "track": 0, "slot": 0, "seed": 5, "counter_to": {"track": 1, "slot": 0},
        "counter_mode": mode, "counter_register": "below",
    }))
    change = result["changes"][0]
    assert change["counter_mode"] == mode and change["counter_register"] == "below"
    assert all(n["pitch"] < 76 for n in change["notes"]) or not change["notes"]
    if mode in FIGURES:
        assert change["notes"] and _clip_notes(live, 0, 0)


async def test_chords_are_derived_from_the_lead_when_none_are_given(client, live):
    await _lead(client)
    change = _payload(await build_server(client).call_tool("compose", {
        "kind": "melody", "track": 0, "slot": 0, "seed": 1, "counter_to": {"track": 1, "slot": 0},
    }))["changes"][0]
    assert change["chords_source"] == "clip"
    assert "derived from the main melody" in change["chords_note"]
    assert len(change["chords"]) == 4


async def test_plan_changes_counter_to_a_lead_planned_in_the_same_plan(client, live):
    plan = _payload(await build_server(client).call_tool("plan_changes", {"steps": [
        {"kind": "melody", "track": 1, "slot": 0, "bars": 4, "seed": 1},
        {"kind": "melody", "track": 0, "slot": 0, "bars": 4, "seed": 2, "counter_to": {"track": 1, "slot": 0}, "counter_mode": "harmonic_notes"},
    ]}))
    lead, counter = plan["changes"]
    assert counter["main_notes"] == lead["add"] and counter["counter_mode"] == "harmonic_notes"
    assert counter["chords"] == lead["chords"]  # one harmony for both: the lead's
    assert "chords_note" not in counter
    assert live.on_main(lambda: live.song.tracks[1].clip_slots[0].has_clip) is False


async def test_compose_takes_with_counter_to(client, live):
    await client.call("arrangement.edit", {"actions": [{"action": "add_clip", "track": 1, "start": 0, "length": 16, "name": "Lead", "notes": [
        {"pitch": p, "start_time": s, "duration": d, "velocity": 100} for p, s, d in LEAD]}]})
    summary = _payload(await build_server(client).call_tool("compose_takes", {
        "track": 0, "start_bar": 1, "bars": 4, "kind": "melody", "count": 2, "seed": 4,
        "params": {"counter_to": {"track": 1, "arrangement_clip": "Lead"}, "counter_mode": "note_layering"},
    }))
    assert summary["chords_from"] == "derived from the main melody"
    assert [t["notes"] > 0 for t in summary["takes"]] == [True, True]


async def test_errors(client, live):
    server = build_server(client)
    await client.call("track.create", {"kind": "midi", "index": 2, "name": "Drums"})
    live.on_main(lambda: live.song.tracks[2].devices.append(DrumRackDevice()))
    await _lead(client)
    await _lead(client, track=1, slot=1, notes=[])
    await client.call("clip.create", {"track": 2, "slot": 0, "length": 4})

    def call(**fields):
        return server.call_tool("compose", {"kind": "melody", "track": 0, "slot": 0, "seed": 1, **fields})

    with pytest.raises(ToolError, match="drum track"):
        await call(counter_to={"track": 2, "slot": 0})
    with pytest.raises(ToolError, match="no MIDI clip"):
        await call(counter_to={"track": 1, "slot": 5})
    with pytest.raises(ToolError, match="no notes"):
        await call(counter_to={"track": 1, "slot": 1})
    with pytest.raises(ToolError, match="clip being written"):
        await call(track=1, slot=0, if_exists="replace", counter_to={"track": 1, "slot": 0})
    with pytest.raises(ToolError, match="need counter_to"):
        await call(counter_mode="fill_the_gaps")
    with pytest.raises(ToolError, match="need counter_to"):
        await call(counter_register="below")
    with pytest.raises(ToolError, match="pattern"):
        await call(counter_to={"track": 1, "slot": 0}, pattern="trance_dotted_eighth_staircase")
    with pytest.raises(ToolError, match="counter_to"):
        await server.call_tool("compose", {"kind": "bass", "track": 0, "slot": 0, "counter_to": {"track": 1, "slot": 0}})
    with pytest.raises(ToolError, match="counter_mode"):
        await call(counter_to={"track": 1, "slot": 0}, counter_mode="polka")


async def test_the_lead_track_alone_finds_its_clip(client, live):
    # gemma: counter_to {"track": 5} for "the lead track", rejected four times for a missing slot
    await _lead(client, track=1, slot=2)
    change = _payload(await build_server(client).call_tool("compose", {
        "kind": "melody", "track": 0, "slot": 0, "bars": 4, "seed": 1, "counter_to": {"track": 1}}))["changes"][0]
    assert change["counter_to"] == "slot index 2 on track index 1"


async def test_an_arrangement_lead_by_track_or_by_its_listed_name(client, live):
    await client.call("arrangement.edit", {"actions": [
        {"action": "add_clip", "track": 1, "start": 0, "length": 16, "name": "Lift Lead",
         "notes": [{"pitch": p, "start_time": s, "duration": d} for p, s, d in LEAD]},
        {"action": "add_clip", "track": 1, "start": 16, "length": 16, "name": "Peak Lead",
         "notes": [{"pitch": p, "start_time": s, "duration": d} for p, s, d in LEAD]}]})
    server = build_server(client)
    first = _payload(await server.call_tool("compose", {
        "kind": "melody", "track": 0, "slot": 0, "bars": 4, "seed": 1, "counter_to": {"track": 1}}))["changes"][0]
    assert first["counter_to"] == "arrangement clip index 0 on track index 1"
    # gemma copied the listing "1 'Peak Lead'" as the name
    listed = _payload(await server.call_tool("compose", {
        "kind": "melody", "track": 0, "slot": 1, "bars": 4, "seed": 1,
        "counter_to": {"track": 1, "arrangement_clip": "1 Peak Lead"}}))["changes"][0]
    assert listed["counter_to"] == "arrangement clip index 1 on track index 1"


async def test_a_track_without_clips_says_so(client, live):
    with pytest.raises(ToolError, match="has no MIDI clip to read"):
        await build_server(client).call_tool("compose", {"kind": "melody", "track": 0, "slot": 0, "counter_to": {"track": 1}})
