"""complexity="rich" (the default): answer, layers, extra FX, less rigid sections; "simple" keeps the old song."""

import json

from fake_song import DrumRackDevice
from midibakery.mcp import build_server
from test_song import references  # noqa: F401  (the fixture)


def _payload(result):
    content = result[0] if isinstance(result, tuple) else result
    if hasattr(content, "structured_content") and content.structured_content:
        return content.structured_content
    items = content.content if hasattr(content, "content") else content
    return json.loads(items[0].text)


def _studio(live):
    def setup():
        rack = DrumRackDevice()
        for name, note in (("Kick", 36), ("Snare", 38), ("Clap", 39), ("Closed Hat", 42), ("Open Hat", 46), ("Ride", 51)):
            rack.add_pad(name, note)
        live.song.tracks[0].devices.append(rack)
        live.song.tracks[0].name = "Drums"
        live.song.tracks[1].name = "Bass"

    live.on_main(setup)


async def _plan(server, **args):
    return _payload(await server.call_tool("plan_song", {"genre": "house", "seed": 7, "sidechain": False, **args}))


async def _clips(client, track):
    """(name, start, length, notes with absolute start) of every arrangement clip on a track."""
    arrangement = await client.call("arrangement.get", {})
    out = []
    for index, clip in enumerate(arrangement["tracks"][track]["clips"]):
        notes = (await client.call("notes.get", {"track": track, "arrangement_clip": index}))["notes"]
        out.append((clip["name"], clip["start"], clip["end"] - clip["start"], [{**n, "start_time": n["start_time"] + clip["start"]} for n in notes]))
    return out


async def test_rich_adds_voices_and_simple_does_not(client, live):
    _studio(live)
    server = build_server(client, all_song_options=True)
    rich = await _plan(server, complexity="rich")
    simple = await _plan(server, complexity="simple")
    assert {"answer", "lead2", "bass2", "sweep"} <= set(rich["tracks"])
    assert not {"answer", "lead2", "bass2", "sweep"} & set(simple["tracks"])
    assert rich["clips"] > simple["clips"]
    assert rich["sections"] != simple["sections"]


async def test_rich_is_deterministic_per_seed_and_varies_between_seeds(client, live):
    _studio(live)
    server = build_server(client, all_song_options=True)
    shape = lambda p: [(s["name"], s["bars"]) for s in p["sections"]]
    a, b = await _plan(server, seed=3), await _plan(server, seed=3)
    assert shape(a) == shape(b) and a["clips"] == b["clips"]
    shapes = {tuple(shape(await _plan(server, seed=seed))) for seed in range(1, 9)}
    assert len(shapes) > 3  # the layout is not one fixed song


async def test_the_answer_plays_in_the_rests_of_the_lead_and_layers_share_its_rhythm(client, live):
    _studio(live)
    server = build_server(client, all_song_options=True)
    preview = await _plan(server)
    await server.call_tool("apply_plan", {"plan_id": preview["plan_id"]})
    lead = [n for c in await _clips(client, preview["tracks"]["lead"]["track"]) for n in c[3]]
    answer = [n for c in await _clips(client, preview["tracks"]["answer"]["track"]) for n in c[3]]
    layer = [n for c in await _clips(client, preview["tracks"]["lead2"]["track"]) for n in c[3]]
    assert answer and layer
    for n in answer:
        assert not any(l["start_time"] < n["start_time"] < l["start_time"] + l["duration"] - 1e-6 for l in lead)
    lead_starts = {round(n["start_time"], 3) for n in lead}
    assert {round(n["start_time"], 3) for n in layer} <= lead_starts


async def test_extra_fx_tracks_do_not_overlap_and_clips_stay_few(client, live):
    _studio(live)
    server = build_server(client, all_song_options=True)
    preview = await _plan(server, fx=True)
    assert preview["clips"] <= 256
    await server.call_tool("apply_plan", {"plan_id": preview["plan_id"]})
    for role in ("riser", "sweep", "impact"):
        clips = await _clips(client, preview["tracks"][role]["track"])
        assert clips, (role, preview["tracks"].get(role), preview.get("warnings"))
        spans = sorted((c[1], c[1] + c[2]) for c in clips)
        assert all(a[1] <= b[0] + 1e-6 for a, b in zip(spans, spans[1:]))


async def test_the_kick_stays_on_the_grid(client, live):
    _studio(live)
    server = build_server(client, all_song_options=True)
    preview = await _plan(server)
    await server.call_tool("apply_plan", {"plan_id": preview["plan_id"]})
    for _, _, _, notes in await _clips(client, 0):
        kicks = [n for n in notes if n["pitch"] == 36]
        assert all(abs(n["start_time"] * 4 - round(n["start_time"] * 4)) < 1e-6 for n in kicks)


async def test_a_reference_still_decides_the_sections(client, live, references):
    _studio(live)
    server = build_server(client, all_song_options=True)
    rich = await _plan(server, genre="peak_time_techno", reference="signal", minutes=3, complexity="rich")
    simple = await _plan(server, genre="peak_time_techno", reference="signal", minutes=3, complexity="simple")
    assert [(s["name"], s["bar"], s["bars"]) for s in rich["sections"]] == [(s["name"], s["bar"], s["bars"]) for s in simple["sections"]]
    assert "answer" in rich["tracks"] or "lead2" in rich["tracks"]
