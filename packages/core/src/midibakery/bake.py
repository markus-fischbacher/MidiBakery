"""One-button songs for the Bake device: plan_song and apply_plan in one step, without a model.

``Bake`` writes a new song after the last arrangement clip. ``again`` replaces the song baked last
with another seed (its clips and locators are deleted, the tracks it used stay); ``back`` replaces
it with the seed before. What was baked last lives in this process: after a restart of the API
the next bake starts a new song.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from midibakery.bridge import BridgeError
from midibakery.compose.plan import new_seed
from midibakery.compose.references import load_references
from midibakery.compose.rollback import undo
from midibakery.compose.song import SongRequest, apply_song, build_song
from midibakery.compose import user_patterns

Call = Callable[..., Awaitable[dict[str, Any]]]
GENRES = ("house", "melodic_techno", "peak_time_techno", "drum_and_bass", "trap")
LENGTHS = ("radio", "standard", "extended")
EPSILON = 1e-6


@dataclass
class Baked:
    """The song baked last: where it is and which tracks it wrote to (by track id, indices shift)."""

    settings: dict[str, Any]
    seed: int
    start: float  # beats
    end: float
    beats_per_bar: float
    track_ids: list[Any]
    locators: list[float]
    seeds: list[int] = field(default_factory=list)  # every seed baked at this place, oldest first


def options() -> dict[str, Any]:
    """What the page offers: genres, lengths, the analyzed and imported references, whether there are own loops."""
    refs = [{"name": r.get("name"), "source": r.get("source", "audio"), "genre": r.get("genre"), "tempo": r.get("tempo")}
            for r in load_references() if r.get("name")]
    return {"genres": list(GENRES), "lengths": list(LENGTHS), "references": refs, "my_loops": bool(user_patterns.entries())}


def _settings(body: dict[str, Any]) -> dict[str, Any]:
    genre, length, reference = body.get("genre"), body.get("length") or "standard", body.get("reference") or None
    if genre is not None and genre not in GENRES:
        raise ValueError(f"genre: one of {', '.join(GENRES)}")
    if length not in LENGTHS:
        raise ValueError(f"length: one of {', '.join(LENGTHS)}")
    if genre is None and reference is None:
        raise ValueError("choose a genre or a reference")
    return {"genre": genre, "length": length, "reference": reference, "my_loops": bool(body.get("my_loops"))}


class Baker:
    def __init__(self, call: Call):
        self.call = call
        self.last: Baked | None = None
        self._lock = asyncio.Lock()

    def state(self) -> dict[str, Any]:
        last = self.last
        if last is None:
            return {"baked": None}
        return {"baked": {**last.settings, "seed": last.seed, "bars": f"{int(last.start / last.beats_per_bar) + 1}-"
                          f"{int(last.end / last.beats_per_bar)}", "can_go_back": len(last.seeds) > 1}}

    async def bake(self, body: dict[str, Any]) -> dict[str, Any]:
        """body: genre, length, reference, my_loops, seed (optional) and mode: new, again or back."""
        mode = body.get("mode") or "new"
        if mode not in ("new", "again", "back"):
            raise ValueError("mode: new, again or back")
        async with self._lock:
            last = self.last if mode != "new" else None
            if mode == "back" and (last is None or len(last.seeds) < 2):
                raise ValueError("nothing to go back to")
            settings = last.settings if mode == "back" and last else _settings(body)
            seeds = list(last.seeds) if last else []
            if mode == "back":
                seeds.pop()
                seed = seeds[-1]
            else:
                seed = int(body["seed"]) if body.get("seed") is not None else new_seed()
                seeds.append(seed)
            start_bar = int(last.start / last.beats_per_bar) + 1 if last else None
            cleared = await self._clear(last) if last else 0
            try:
                result, baked = await self._write(settings, seed, start_bar)
            except (BridgeError, ValueError) as exc:
                error = exc if isinstance(exc, BridgeError) else BridgeError("INVALID_PARAMS", str(exc))
                # the old song comes back, unless the new one could not take itself back
                if cleared and error.details.get("rolled_back") is not False:
                    await undo(self.call, error, cleared, "the previous song is back")
                if error is exc:
                    raise
                raise error from exc
            baked.seeds = seeds
            self.last = baked
            return {**result, "seed": seed, **self.state()}

    async def _write(self, settings: dict[str, Any], seed: int, start_bar: int | None) -> tuple[dict[str, Any], Baked]:
        request = SongRequest.model_validate({**settings, "seed": seed, "set_tempo": True, "fill_missing": True,
                                              **({"start_bar": start_bar} if start_bar else {})})
        plan = await build_song(self.call, request)
        result = await apply_song(self.call, plan)
        tracks = (await self.call("tracks.list", {}))["tracks"]
        ids = [tracks[t.index].get("id") for t in plan.roles.values() if t.index < len(tracks)]
        locators = [a["time"] for a in plan.locators if a.get("action") == "set_locator"]
        result = {**result, "tempo": plan.bpm, "scale": plan.scale, "genre": plan.template.label,
                  **({"warnings": plan.warnings + result.get("warnings", [])} if plan.warnings else {})}
        return result, Baked(settings, seed, plan.start, plan.end, plan.beats_per_bar, ids, locators)

    async def _clear(self, last: Baked) -> int:
        """Delete the last song's clips (one undo step) and locators (one step each): the undo steps taken."""
        tracks = (await self.call("tracks.list", {}))["tracks"]
        index = {t.get("id"): i for i, t in enumerate(tracks)}
        arrangement = await self.call("arrangement.get", {})
        actions = []
        for entry in arrangement["tracks"]:
            if entry["index"] not in {index.get(i) for i in last.track_ids}:
                continue
            for clip in sorted(entry["clips"], key=lambda c: c["index"], reverse=True):  # later indices first: no shift
                if last.start - EPSILON <= clip["start"] < last.end - EPSILON:
                    actions.append({"action": "delete_clip", "track": entry["index"], "clip": clip["index"]})
        if not actions:
            return 0
        await self.call("arrangement.edit", {"actions": actions})
        stale = [{"action": "delete_locator", "time": loc["time"]} for loc in arrangement["locators"]
                 if any(abs(loc["time"] - t) < EPSILON for t in last.locators)]
        song = await self.call("song.get", {})
        if stale and not song.get("is_playing"):  # locators only with the transport stopped, as the song sets them
            await self.call("arrangement.locators", {"actions": stale})
            return 1 + len(stale)
        return 1
