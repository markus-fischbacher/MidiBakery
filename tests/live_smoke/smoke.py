"""End-to-end check against a real, running Ableton Live.

Use an empty, unsaved Live Set: the script adds a temporary MIDI track,
exercises the Phase-1 ops on it and deletes it again. Run with:

    uv run python tests/live_smoke/smoke.py --yes
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from midishower.bridge import BridgeClient, BridgeError

TRACK_NAME = "MidiShower Smoke"


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
    finally:
        await step("track.delete (cleanup)", "track.delete", {"track": track})
        await client.close()

    print("PASSED" if failures == 0 else f"{failures} FAILURE(S)")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--yes", action="store_true", help="confirm that the open Live Set may be modified")
    if not parser.parse_args().yes:
        parser.print_help()
        sys.exit(2)
    sys.exit(asyncio.run(main()))
