"""Named chord patterns resolve to the same harmony in the standalone generator and the plan path."""

import pytest

from midibakery.compose.chord_templates import CHORD_TEMPLATES, template_harmony
from midibakery.compose.patterns import mood_harmony
from midibakery.compose.rhythm import Meter
from midibakery.compose.specs import ComposeRequest
from midibakery.compose.standalone import GenerateRequest, generate
from midibakery.compose.theory import MAJOR, Scale

C_MAJOR = {"root": 0, "intervals": list(MAJOR), "name": "Major"}
A_MINOR = {"root": 9, "intervals": [0, 2, 3, 5, 7, 8, 10], "name": "Minor"}


def _generate(pattern, scale=C_MAJOR, length=32, **params):
    request = GenerateRequest(context={"scale": scale, "length": length, "seed": 7}, kind="chords", params={"pattern": pattern, **params})
    return generate(request)


@pytest.mark.parametrize("scale", [C_MAJOR, A_MINOR], ids=["C", "A"])
@pytest.mark.parametrize("pattern", list(CHORD_TEMPLATES))
def test_standalone_uses_the_patterns_own_progression(pattern, scale):
    result = _generate(pattern, scale)
    tonic = Scale(scale["root"], tuple(scale["intervals"]), scale["name"])
    expected = template_harmony(CHORD_TEMPLATES[pattern], tonic, Meter(4, 4), 8).describe()
    assert result["chords"] == expected
    assert result["notes"]


def test_the_reported_case_is_a_minor_progression():
    assert _generate("uplifting_sweet")["chords"][0] == "G# (VI)"  # C-minor-rooted, not C-F-C-G
    assert _generate("dark_cinematic")["chords"][0] == "Cm (i)"


def test_explicit_rate_and_progression_take_precedence():
    default = _generate("uplifting_sweet")["chords"]
    faster = _generate("uplifting_sweet", chords_per_bar=2)["chords"]
    assert len(faster) == 2 * len(default)
    with pytest.raises(ValueError, match="not both"):  # the same validation as the plan path
        _generate("uplifting_sweet", progression="C F")


def test_default_rate_is_not_an_explicit_choice():
    spec = ComposeRequest(kind="chords", pattern="dreamy_indie", track=0, slot=0).spec()
    assert "chords_per_bar" not in spec.model_fields_set
    result = mood_harmony("dreamy_indie", Scale(0), Meter(4, 4), 4, None)
    assert len(result.segments) == 8  # the template's 2 chords per bar


def test_ignored_controls_are_reported_only_when_explicitly_supplied():
    from midibakery.compose.standalone import GenerateRequest, generate

    def run(kind, params):
        return generate(GenerateRequest.model_validate({"context": {"seed": 1}, "kind": kind, "params": params})).get("ignored")

    assert run("bass", {"pattern": next(iter(__import__("midibakery.compose.patterns", fromlist=["x"]).BASS_TEMPLATES)), "octave": 2}) == ["octave"]
    assert run("bass", {"style": "offbeat", "swing": 0.4}) == ["swing"]
    assert run("bass", {"style": "offbeat"}) is None
    assert run("bass", {"style": "syncopated", "swing": 0.4}) is None
