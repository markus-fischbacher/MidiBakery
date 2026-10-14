"""End-to-end check against a real, running Ableton Live.

Use an empty, unsaved Live Set: the script adds a temporary MIDI track,
exercises the Phase-1 ops and the Phase-2 composition engine (plan, apply as
one undo step, transform, undo) on it and deletes it again. Run with:

    uv run python tests/live_smoke/smoke.py --yes
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from midishower.bridge import BridgeClient, BridgeError
from midishower.compose import BassSpec, ChordsSpec, DrumsSpec, MelodySpec, TransformSpec, apply_plan, build_plan
from midishower.compose.theory import Scale

TRACK_NAME = "MidiShower Smoke"
COMPOSE_SLOTS = (1, 2, 3, 4)  # drums, chords, bass, melody


async def main() -> int:
    client = BridgeClient()
    failures = 0

    async def step(label: str, op: str, params: dict | None = None):
        nonlocal failures
        try:
            result = await client.call(op, params or {})
            print(f"  ok    {label}")
            return result
        except BridgeError as exc:
            failures += 1
            print(f"  FAIL  {label}: {exc} {json.dumps(exc.details) if exc.details else ''}")
            return None

    health = await step("health", "live.health")
    if health is None:
        return 1
    print(f"Live {'.'.join(map(str, health['live']))}, bridge {health['bridge']}, {len(health['ops'])} ops")

    song = await step("song.get", "song.get")
    if song:
        print(f"  tempo {song['tempo']}, scale {song.get('root_note')} {song.get('scale_name')} {song.get('scale_intervals')}")
    original_tempo = song["tempo"] if song else 120.0

    created = await step("track.create", "track.create", {"kind": "midi", "name": TRACK_NAME})
    if created is None:
        return 1
    track = created["track"]
    try:
        await step("clip.create", "clip.create", {"track": track, "slot": 0, "length": 4, "name": "smoke"})
        added = await step("notes.apply add (probability, velocity deviation)", "notes.apply", {
            "track": track, "slot": 0,
            "add": [
                {"pitch": 60, "start_time": 0, "duration": 1, "probability": 0.5},
                {"pitch": 64, "start_time": 1, "duration": 1, "velocity_deviation": 20},
                {"pitch": 67, "start_time": 2, "duration": 1},
            ],
        })
        if added:
            ids = added["added"]
            await step("notes.apply modify+remove", "notes.apply", {
                "track": track, "slot": 0,
                "modify": [{"note_id": ids[1], "velocity": 50}],
                "remove": [ids[2]],
            })
            notes = await step("notes.get", "notes.get", {"track": track, "slot": 0})
            if notes:
                got = [(n["pitch"], n["velocity"], n["probability"], n["velocity_deviation"]) for n in notes["notes"]]
                expected = [(60, 100.0, 0.5, 0.0), (64, 50.0, 1.0, 20.0)]
                if got != expected:
                    failures += 1
                    print(f"  FAIL  note round trip: {got} != {expected}")
                else:
                    print("  ok    note round trip keeps ids, probability and deviation")
        await step("clip.set loop", "clip.set", {"track": track, "slot": 0, "loop_start": 0, "loop_end": 2})
        device = await step("device.insert Drift", "device.insert", {"track": track, "name": "Drift"})
        if device:
            params = await step("device.params", "device.params", {"track": track, "device": device["device"]})
            if params:
                p = next((p for p in params["parameters"] if not p["is_quantized"] and p["is_enabled"]), None)
                if p:
                    mid = (p["min"] + p["max"]) / 2
                    await step(f"device.set_param '{p['name']}'", "device.set_param",
                               {"track": track, "device": device["device"], "parameter": p["index"], "value": mid})
        await step("batch", "batch", {"ops": [
            {"op": "song.set", "params": {"tempo": 123}},
            {"op": "track.set", "params": {"track": track, "volume": 0.7, "pan": -0.2}},
        ]})
        await step("history undo (batch)", "history.step", {"action": "undo"})
        after = await step("song.get after undo", "song.get")
        if after and after["tempo"] != original_tempo:
            failures += 1
            print(f"  FAIL  undo did not restore tempo: {after['tempo']} != {original_tempo}")
        # Not `failures += await ...`: step() increments failures while the await runs.
        compose_failures = await compose_checks(client, track, step, after or song or {})
        failures += compose_failures
    finally:
        await step("track.delete (cleanup)", "track.delete", {"track": track})
        await client.close()

    print("PASSED" if failures == 0 else f"{failures} FAILURE(S)")
    return 0 if failures == 0 else 1


async def compose_checks(client: BridgeClient, track: int, step, song: dict) -> int:
    """Phase 2: drum pads, plan without side effects, apply as one undo step, transform diff, undo."""
    failures = 0

    def fail(message: str) -> None:
        nonlocal failures
        failures += 1
        print(f"  FAIL  {message}")

    if song.get("scene_count", 0) <= max(COMPOSE_SLOTS):
        fail(f"compose needs {max(COMPOSE_SLOTS) + 1} scenes, the set has {song.get('scene_count')}")
        return failures
    created = await step("track.create (drums)", "track.create", {"kind": "midi", "name": TRACK_NAME + " Drums"})
    if created is None:
        return failures + 1
    drum_track = created["track"]
    try:
        await _compose_on(client, track, drum_track, step, song, fail)
    finally:
        await step("track.delete drums (cleanup)", "track.delete", {"track": drum_track})
    return failures


async def _composed_slots(client: BridgeClient, tracks: tuple[int, ...]) -> list[tuple[int, int]]:
    listed = (await client.call("tracks.list"))["tracks"]
    return [(t, c["slot"]) for t in tracks for c in listed[t]["clips"] if c["slot"] in COMPOSE_SLOTS]


async def _compose_on(client: BridgeClient, track: int, drum_track: int, step, song: dict, fail) -> None:
    rack = await step("device.insert Drum Rack", "device.insert", {"track": drum_track, "name": "Drum Rack"})
    if rack:
        pads = await step("drum_rack.pads", "drum_rack.pads", {"track": drum_track})
        if pads is not None:
            print(f"        {len(pads['pads'])} filled pads (empty rack -> GM fallback)")

    drums, chords, bass, melody = COMPOSE_SLOTS
    steps = [
        DrumsSpec(track=drum_track, slot=drums, bars=2, seed=11, style="house"),
        ChordsSpec(track=track, slot=chords, bars=2, seed=12, progression="I vi IV V"),
        BassSpec(track=track, slot=bass, bars=2, seed=13, follow_kick={"track": drum_track, "slot": drums}),
        MelodySpec(track=track, slot=melody, bars=2, seed=14),
    ]
    try:
        plan = await build_plan(client.call, steps)
        again = await build_plan(client.call, steps)
    except BridgeError as exc:
        fail(f"plan_changes: {exc}")
        return
    print(f"  ok    plan {plan.id}: {plan.preview()['op_count']} ops, scale {plan.scale}, {plan.meter}")
    if [c.add for c in plan.changes] != [c.add for c in again.changes]:
        fail("same seeds produced different notes")
    else:
        print("  ok    same seeds -> same notes")
    if await _composed_slots(client, (track, drum_track)):
        fail("planning changed the set")

    try:
        await apply_plan(client.call, plan)
        print("  ok    apply_plan (one batch)")
    except BridgeError as exc:
        fail(f"apply_plan: {exc} {json.dumps(exc.details) if exc.details else ''}")
        return

    scale = Scale.from_song(song)
    length = 2 * song["signature_numerator"] * 4 / song["signature_denominator"]
    for change in plan.changes:
        got = await step(f"notes.get {change.kind}", "notes.get", {"track": change.track, "slot": change.slot})
        if not got:
            continue
        notes = got["notes"]
        if len(notes) != len(change.add):
            fail(f"{change.kind}: {len(notes)} notes in Live, {len(change.add)} planned")
        if change.kind != "drums" and not all(scale.contains(n["pitch"]) for n in notes):
            fail(f"{change.kind}: notes outside {scale.describe()}")
        if not all(0 <= n["start_time"] < length for n in notes):
            fail(f"{change.kind}: notes outside the clip")
        if change.kind == "drums" and not any(n["probability"] < 1 or n["velocity_deviation"] for n in notes):
            fail("drums: no probability / velocity deviation")

    before = (await client.call("notes.get", {"track": track, "slot": melody}))["notes"]
    try:
        transform = await build_plan(client.call, [TransformSpec(track=track, slot=melody, operation="humanize", amount=1.0, seed=5)])
        await apply_plan(client.call, transform)
    except BridgeError as exc:
        fail(f"transform_notes: {exc}")
        return
    after = (await client.call("notes.get", {"track": track, "slot": melody}))["notes"]
    if {n["note_id"] for n in after} != {n["note_id"] for n in before}:
        fail("humanize changed note ids (should be a diff)")
    elif after == before:
        fail("humanize changed nothing")
    else:
        print(f"  ok    humanize modified {len(transform.changes[0].modify)} notes by id")

    await step("history undo (transform)", "history.step", {"action": "undo"})
    undone = (await client.call("notes.get", {"track": track, "slot": melody}))["notes"]
    if undone != before:
        fail("undo did not restore the melody before humanize")
    await step("history undo (compose plan)", "history.step", {"action": "undo"})
    left = await _composed_slots(client, (track, drum_track))
    if left:
        fail(f"one undo did not remove the composed clips (left: {left})")
    else:
        print("  ok    one undo removed all composed clips")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--yes", action="store_true", help="confirm that the open Live Set may be modified")
    if not parser.parse_args().yes:
        parser.print_help()
        sys.exit(2)
    sys.exit(asyncio.run(main()))
