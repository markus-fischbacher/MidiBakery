"""Core client <-> real Remote Script over a real socket, against the fake LOM."""

import asyncio
import json
import socket

import pytest

from midibakery.bridge import BridgeError, discovery_path


async def test_health_lists_supported_ops(client):
    health = await client.call("live.health")
    assert health["live"] == [12, 4, 6]
    assert "notes.apply" in health["ops"]
    assert client.live_version == (12, 4, 6)


def test_wrong_token_is_rejected(live):
    info = json.loads(discovery_path().read_text())
    with socket.create_connection(("127.0.0.1", info["port"]), timeout=2) as sock:
        sock.sendall(b'{"hello":"nope","protocol":1}\n')
        reply = json.loads(sock.makefile().readline())
    assert reply["hello"] == "denied"
    assert reply["error"]["code"] == "UNAUTHORIZED"


def test_discovery_file_is_private(live):
    assert discovery_path().stat().st_mode & 0o777 == 0o600


async def test_song_get_and_set_scale(client, live):
    await client.call("song.set", {"tempo": 128, "root_note": 9, "scale_name": "Minor"})
    song = await client.call("song.get")
    assert song["tempo"] == 128
    assert song["root_note"] == 9 and song["scale_name"] == "Minor"
    assert song["scale_intervals"] == [0, 2, 4, 5, 7, 9, 11]
    assert live.on_main(lambda: live.song.undo_steps) == 1


async def test_track_and_clip_lifecycle(client, live):
    created = await client.call("track.create", {"kind": "midi", "name": "Bass"})
    track = created["track"]
    clip = await client.call("clip.create", {"track": track, "slot": 0, "length": 8, "name": "Riff"})
    assert clip["length"] == 8 and clip["name"] == "Riff"
    tracks = (await client.call("tracks.list"))["tracks"]
    assert tracks[track]["name"] == "Bass"
    assert tracks[track]["clips"] == [{"slot": 0, "name": "Riff", "length": 8, "is_midi": True, "is_playing": False}]

    with pytest.raises(BridgeError) as exc:
        await client.call("clip.create", {"track": track, "slot": 0})
    assert exc.value.code == "CONFLICT"

    await client.call("clip.delete", {"track": track, "slot": 0})
    with pytest.raises(BridgeError) as exc:
        await client.call("clip.get", {"track": track, "slot": 0})
    assert exc.value.code == "NOT_FOUND"


@pytest.mark.parametrize("launch_mode", [0, 2])
async def test_fire_starts_a_clip_live_already_counts_as_playing(client, live, launch_mode):
    await client.call("clip.create", {"track": 1, "slot": 5, "length": 4})
    clip = live.on_main(lambda: live.song.tracks[1].clip_slots[5].clip)

    def stale_playing():
        clip.launch_mode = launch_mode
        clip.is_playing = True

    live.on_main(stale_playing)
    await client.call("clip.launch", {"track": 1, "slot": 5})
    assert live.on_main(lambda: clip.is_playing or clip.is_triggered)
    assert live.on_main(lambda: clip.launch_mode) == launch_mode


async def test_fire_resumes_a_toggle_clip_left_playing_by_a_transport_stop(client, live):
    await client.call("clip.create", {"track": 1, "slot": 6, "length": 4})
    clip = live.on_main(lambda: live.song.tracks[1].clip_slots[6].clip)

    def stopped_with_clip_playing():
        clip.launch_mode = 2
        clip.is_playing = True
        live.song.is_playing = False

    live.on_main(stopped_with_clip_playing)
    await client.call("clip.launch", {"track": 1, "slot": 6})
    assert live.on_main(lambda: clip.is_playing)
    assert live.on_main(lambda: live.song.is_playing)
    assert live.on_main(lambda: live.song.tracks[1].clip_slots[6].fired) == 0


async def test_notes_diff_keeps_untouched_notes(client, live):
    await client.call("clip.create", {"track": 0, "slot": 1, "length": 4})
    added = (await client.call("notes.apply", {
        "track": 0, "slot": 1,
        "add": [
            {"pitch": 60, "start_time": 0, "duration": 1, "probability": 0.5},
            {"pitch": 64, "start_time": 1, "duration": 1, "velocity_deviation": 20},
            {"pitch": 67, "start_time": 2, "duration": 1},
        ],
    }))["added"]
    assert len(added) == 3

    result = await client.call("notes.apply", {
        "track": 0, "slot": 1,
        "modify": [{"note_id": added[1], "velocity": 50}],
        "remove": [added[2]],
    })
    assert result == {"added": [], "modified": 1, "removed": 1}

    notes = (await client.call("notes.get", {"track": 0, "slot": 1}))["notes"]
    assert [n["note_id"] for n in notes] == added[:2]
    assert notes[0]["probability"] == 0.5
    assert notes[1]["velocity"] == 50 and notes[1]["velocity_deviation"] == 20


async def test_notes_apply_with_unknown_id_changes_nothing(client, live):
    await client.call("clip.create", {"track": 0, "slot": 2, "length": 4})
    added = (await client.call("notes.apply", {
        "track": 0, "slot": 2, "add": [{"pitch": 60, "start_time": 0, "duration": 1}],
    }))["added"]
    with pytest.raises(BridgeError) as exc:
        await client.call("notes.apply", {
            "track": 0, "slot": 2,
            "modify": [{"note_id": added[0], "pitch": 72}],
            "remove": [999999],
        })
    assert exc.value.code == "NOT_FOUND"
    assert exc.value.details["note_ids"] == [999999]
    notes = (await client.call("notes.get", {"track": 0, "slot": 2}))["notes"]
    assert notes[0]["pitch"] == 60


async def test_core_rejects_invalid_params_before_sending(client):
    with pytest.raises(BridgeError) as exc:
        await client.call("notes.apply", {"track": 0, "slot": 0, "add": [{"pitch": 200, "start_time": 0, "duration": 1}]})
    assert exc.value.code == "INVALID_PARAMS"
    with pytest.raises(BridgeError) as exc:
        await client.call("notes.apply", {"track": 0, "slot": 0})
    assert exc.value.code == "INVALID_PARAMS"


def _raw_request(op, params):
    info = json.loads(discovery_path().read_text())
    with socket.create_connection(("127.0.0.1", info["port"]), timeout=3) as sock:
        reader = sock.makefile()
        sock.sendall(json.dumps({"hello": info["token"], "protocol": 1}).encode() + b"\n")
        assert json.loads(reader.readline())["hello"] == "ok"
        sock.sendall(json.dumps({"id": 1, "op": op, "params": params}).encode() + b"\n")
        return json.loads(reader.readline())


def test_bridge_validates_at_its_own_boundary(live):
    reply = _raw_request("track.set", {"track": "zero"})
    assert reply["error"]["code"] == "INVALID_PARAMS"
    reply = _raw_request("track.set", {"track": 0, "bogus": 1})
    assert reply["error"]["code"] == "INVALID_PARAMS"
    reply = _raw_request("song.explode", {})
    assert reply["error"]["code"] == "UNKNOWN_OP"
    reply = _raw_request("track.set", {"track": 99, "mute": True})
    assert reply["error"]["code"] == "NOT_FOUND"


async def test_batch_is_one_undo_step(client, live):
    before = live.on_main(lambda: live.song.undo_steps)
    result = await client.call("batch", {"ops": [
        {"op": "track.create", "params": {"name": "Keys"}},
        {"op": "song.set", "params": {"tempo": 100}},
        {"op": "scene.create", "params": {"name": "Drop"}},
    ]})
    assert len(result["results"]) == 3
    assert live.on_main(lambda: live.song.undo_steps) == before + 1
    assert live.on_main(lambda: live.song.undo_depth) == 0


async def test_batch_failure_reports_index_and_closes_undo_step(client, live):
    with pytest.raises(BridgeError) as exc:
        await client.call("batch", {"ops": [
            {"op": "song.set", "params": {"tempo": 90}},
            {"op": "track.delete", "params": {"track": 50}},
            {"op": "song.set", "params": {"tempo": 95}},
        ]})
    assert exc.value.code == "NOT_FOUND"
    assert exc.value.details["index"] == 1
    assert len(exc.value.details["completed"]) == 1
    assert live.on_main(lambda: live.song.undo_depth) == 0
    assert live.on_main(lambda: live.song.tempo) == 90


async def test_device_insert_and_parameters(client):
    inserted = await client.call("device.insert", {"track": 0, "name": "Drift"})
    assert inserted["device"] == 0
    params = (await client.call("device.params", {"track": 0, "device": 0}))["parameters"]
    assert params[2]["name"] == "Filter Freq"
    updated = await client.call("device.set_param", {"track": 0, "device": 0, "parameter": "Filter Freq", "value": 500})
    assert updated["value"] == 500
    with pytest.raises(BridgeError) as exc:
        await client.call("device.set_param", {"track": 0, "device": 0, "parameter": 2, "value": 1e9})
    assert exc.value.code == "INVALID_PARAMS"
    with pytest.raises(BridgeError) as exc:
        await client.call("device.insert", {"track": 0, "name": "NotADevice"})
    assert exc.value.code == "NOT_FOUND"


async def test_device_insert_unsupported_before_live_12_3(bridge_env):
    from conftest import LiveHarness
    from midibakery.bridge import BridgeClient

    harness = LiveHarness(version=(12, 2, 5)).start()
    client = BridgeClient()
    try:
        with pytest.raises(BridgeError) as exc:
            await client.call("device.insert", {"track": 0, "name": "Drift"})
        assert exc.value.code == "UNSUPPORTED"
    finally:
        await client.close()
        harness.stop()


async def test_expired_request_times_out_instead_of_running_late(client, live, monkeypatch):
    from midibakery.catalog import OPS
    from midibakery.catalog.registry import OpSpec

    spec = OPS["song.set"]
    monkeypatch.setitem(OPS, "song.set", OpSpec(spec.name, spec.params, spec.summary, spec.read_only, timeout=0.2))
    await client.call("live.health")  # connect first
    live.paused.set()
    with pytest.raises(BridgeError) as exc:
        await client.call("song.set", {"tempo": 77})
    assert exc.value.code == "TIMEOUT"
    live.paused.clear()
    await asyncio.sleep(0.1)
    assert live.on_main(lambda: live.song.tempo) != 77


def test_fake_lom_rejects_access_off_the_main_thread(live):
    """Guards the guard: the contract tests above only prove main-thread safety if this fires."""
    from Live import OffMainThreadAccess

    with pytest.raises(OffMainThreadAccess):
        live.song.tempo
