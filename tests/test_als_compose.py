"""plan_song from an imported Set: its line-up, its loops, and loops taken from another Set."""

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from als_fixtures import edm_set, four_on_the_floor, keytrack, midi_clip, note, track, write_set
from midibakery.als import library
from midibakery.compose.song import SongRequest, build_song
from midibakery.compose.structures import TEMPLATES, from_reference
from midibakery.mcp import build_server
from test_song import _plan, _studio


@pytest.fixture
def home(bridge_env):
    return bridge_env


def _import(home):
    library.run([str(edm_set(home / "Loops Demo.als"))])


def _offbeat_set(home):
    """Kick and a bass of 16ths on the off-beats: a different bass loop than the demo's one note a beat."""
    bass = midi_clip(0, 64, [keytrack(36, *(note(b * 4 + i + 0.5, 0.25) for b in range(16) for i in range(4)))])
    path = write_set(home / "Offbeat.als", [track("MidiTrack", "Kick", four_on_the_floor(16)), track("MidiTrack", "Bass", bass, id_=2)])
    library.run([str(path)])


def _clips(plan, role):
    return [a for a in plan.actions if a["name"].endswith(role.title())]


async def test_the_sets_line_up_decides_the_roles(client, live, home):
    _studio(live)
    _import(home)
    server = build_server(client)
    preview = await _plan(server, reference="Loops Demo")
    assert "chords" not in preview["tracks"]  # the Set has no chords: no track, no parts
    assert any("plays no chords" in w for w in preview["warnings"])
    assert all("chords" not in s["plays"] for s in preview["sections"])
    plays = {s["name"]: s["plays"] for s in preview["sections"]}
    assert "lead" not in plays["Intro"] and "bass" not in plays["Intro"]  # only the kick opens the Set
    assert any("lead" in p for p in plays.values())

    filled = await _plan(server, reference="Loops Demo", fill_missing=True)
    assert "chords" in filled["tracks"]


async def test_loops_of_the_set_are_played(client, live, home):
    _studio(live)
    _import(home)
    plan = await build_song(client.call, SongRequest(genre="house", reference="Loops Demo", seed=7, fx=False, sidechain=False))
    bass = _clips(plan, "bass")
    assert bass and all(n["duration"] == 0.5 for a in bass for n in a["notes"])  # the Set's half-beat notes, not the genre's recipe
    assert {round(n["start_time"] % 1, 6) for a in bass for n in a["notes"]} == {0}  # one on every beat
    lead = _clips(plan, "lead")
    assert lead and all(n["duration"] == 4.0 for a in lead for n in a["notes"])


async def test_loops_from_takes_a_role_from_another_set(client, live, home):
    _studio(live)
    _import(home)
    _offbeat_set(home)
    plan = await build_song(client.call, SongRequest(genre="house", reference="Loops Demo", loops_from={"bass": "Offbeat"}, seed=7,
                                                     fx=False, sidechain=False))
    bass = _clips(plan, "bass")
    assert {round(n["start_time"] % 1, 6) for a in bass for n in a["notes"]} == {0.5}
    assert _clips(plan, "lead") and all(n["duration"] == 4.0 for a in _clips(plan, "lead") for n in a["notes"])  # the lead is still the demo's


async def test_loops_from_errors_are_clear(client, live, home):
    _studio(live)
    _import(home)
    server = build_server(client)
    with pytest.raises(ToolError, match="no imported reference matches 'Nothing'"):
        await _plan(server, loops_from={"bass": "Nothing"})
    other = write_set(home / "Chordless.als", [track("MidiTrack", "Kick", four_on_the_floor(16))])
    library.run([str(other)])
    with pytest.raises(ToolError, match="has no bass loop"):
        await _plan(server, reference="Loops Demo", loops_from={"bass": "Chordless"})


async def test_without_a_set_nothing_changes(client, live, home):
    _studio(live)
    server = build_server(client)
    preview = await _plan(server)
    assert "chords" in preview["tracks"] and not preview["warnings"]


def test_a_bare_kick_or_no_kick_follows_the_set():
    template = TEMPLATES["house"]
    refs = [{"name": "A", "kind": "drop", "bars": 16, "elements": ["kick", "bass"]},
            {"name": "B", "kind": "drop", "bars": 16, "elements": ["drums", "lead"]}]
    from midibakery.compose.grooves import GROOVES
    out = from_reference(template, refs, True, False, frozenset(GROOVES["house"].parts))
    assert out[0].parts["drums"] == "kick_hats" and "lead" not in out[0].parts and out[0].parts["bass"]
    assert out[1].parts["drums"] == "no_kick" and "bass" not in out[1].parts and out[1].parts["lead"]


async def test_loops_from_plays_a_role_the_structure_set_lacks(client, live, home):
    _studio(live)
    _import(home)
    chordless = write_set(home / "Kicks.als", [track("MidiTrack", "Kick", four_on_the_floor(16))])
    library.run([str(chordless)])
    plan = await build_song(client.call, SongRequest(genre="house", reference="Kicks", loops_from={"bass": "Loops Demo"}, seed=7,
                                                     fx=False, sidechain=False))
    assert "bass" in plan.roles and _clips(plan, "bass")
    assert "lead" not in plan.roles  # still the Set's own line-up for the rest


async def test_genre_is_optional_with_a_reference(client, live, home):
    _studio(live)
    _import(home)
    server = build_server(client)
    from test_song import _payload
    preview = _payload(await server.call_tool("plan_song", {"reference": "Loops Demo", "seed": 7}))  # no genre: guessed from the tempo
    assert any("No genre given" in w for w in preview["warnings"])
    named = await _plan(server, reference="Loops Demo", genre="trap")
    assert not any("No genre given" in w for w in named["warnings"])


def test_genre_is_still_required_without_a_reference():
    with pytest.raises(ValueError, match="genre"):
        SongRequest()
    with pytest.raises(ValueError, match="No analyzed reference"):
        SongRequest(reference="Nothing Like This")
