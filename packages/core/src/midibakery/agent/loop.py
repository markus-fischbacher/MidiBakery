"""The tool loop shared by every frontend (terminal chat, Live chat device, API)."""

from __future__ import annotations

import asyncio
import itertools
import json
import logging
import re
from typing import Any

from midibakery.agent.providers.base import Emit, Provider, ToolCall, ToolResult
from midibakery.agent.tools import COMPACT_RESULTS, ToolHost, ToolOutcome, compact_tools
from midibakery.mcp.server import INSTRUCTIONS

SYSTEM_PROMPT = (
    "You are MidiBakery, a music production assistant inside Ableton Live 12. "
    "You compose and edit MIDI and control the Live session through tools. "
    "Always answer in the language of the user's latest message and keep replies short: say what you changed or propose, "
    "with names of tracks, clips, chords and seeds where useful.\n\n"
    "Find named tracks and clips in get_session; never ask for indices. Meet a vague wish with a sensible choice. "
    "A vague wish about an existing part ('more exciting') changes that clip (transform_notes), never adds one. "
    "A track or clip the set lacks (no typo): say so, use no other.\n\n"
    "Work like a producer: keep parts in the song's scale and "
    "time signature and fitting together (bass follows kick and chords, melody follows the chords). For more than one part, or when the user wants to hear options first, "
    "use plan_changes and let them apply the preview; otherwise write directly with the compose "
    "tools. If a tool fails, fix the call instead of repeating it.\n\n"
    "Tool guide:\n" + INSTRUCTIONS
)

# For local models with a small context (e.g. 8k): the essentials of SYSTEM_PROMPT and INSTRUCTIONS.
SMALL_SYSTEM_PROMPT = (
    "You are MidiBakery, a music assistant controlling the open Ableton Live 12 set through tools. "
    "Always answer in the language of the user's latest message, briefly.\n"
    "- Call get_session first and find the tracks and clips the user names there; never ask for indices. Tracks and clip slots are zero-based indices; "
    "users count from 1, so \"track 1\" is index 0.\n"
    "- Times are in beats (quarter notes); pitch 60 = C3. Stay in the song scale.\n"
    "- compose (kind drums/bass/chords/melody) writes a new clip into a free slot (omit slot for the first free one). "
    "Give bass and melody chords_from = the chord clip (never a drums track), the bass follow_kick = the drum clip. "
    "Never overwrite a clip unless the user asks for it.\n"
    "- A song in the Arrangement: get_arrangement lists each track's clips (arrangement_clip index, start beat, name). "
    "To change one part of it, give compose or transform_notes arrangement_clip (its index or its name, "
    "e.g. 'Groove Bass') instead of slot. To vary a part of a clip, transform_notes with operation 'variation' "
    "and half 'second' (or from_bar/to_bar: bars of the clip, 1 = its first bar).\n"
    "- edit_notes and transform_notes change existing notes by note_id from get_clip. "
    "Transpose by half steps/semitones/octaves with semitones (12 = octave); steps means scale steps.\n"
    "- To play a clip, launch it with launch_clip; transport only starts or stops the whole song.\n"
    "- Every write can be undone with undo. If a tool fails, read the error, fix the call and retry it yourself. "
    "If the user declined a change (CANCELLED), nothing was written: say so, never claim it was done."
)

log = logging.getLogger("midibakery.agent")

MAX_STEPS = 24
# Small local models drift into another language over a long tool chain: each message reminds them.
LANGUAGE_REMINDER = "\n\n(Reply in the language of this message.)"
# "the language of this message" alone still got Korean and Turkish answers to English and German
# requests from gemma: name the language when the message makes it clear.
_GERMAN = frozenset("der die das den dem des und ist nicht ein eine einen auf mit für bitte soll sollen mach "
                    "schreib lösch setz spiel tausche ersetze benenne lade etwas noch auch ich du wie was zu im "
                    "vom zum zur hälfte zweite erste spur anwenden ja nein".split())
_ENGLISH = frozenset("the and is not a an on with for please should make write delete set play swap replace "
                     "rename load some it this that to of in from half second first track apply yes no".split())


# Words a reply uses to say a change was made. gemma answered "Tempo auf 128 BPM gesetzt" without calling a tool.
_CLAIM = re.compile(
    r"\b(gesetzt|geändert|gelöscht|erstellt|hinzugefügt|umbenannt|transponiert|geladen|ersetzt|angewendet|gestartet|"
    r"variiert|vertauscht|getauscht|stummgeschaltet|geschrieben|verschoben|humanisiert|"
    r"eingefügt|versehen|eingestellt|angepasst|reduziert|erhöht|verringert|gemacht|aktualisiert|aktiviert|entfernt|"
    r"changed|deleted|created|added|renamed|transposed|loaded|replaced|applied|started|muted|swapped|moved|"
    r"wrote|written|humanized|varied|updated|adjusted|lowered|raised|increased|reduced|removed)\b"
    # present tense and future: "Ich lade den Preset", "I'll load the preset", "Tempo auf 128 gesetzt"
    r"|\b(ich (lade|setze|ändere|lösche|erstelle|schreibe|mache|variiere|tausche|erhöhe|reduziere|senke|verringere|stelle|passe|füge|benenne|verschiebe|transponiere|schalte|plane|ersetze|wende|werde|füge)|i(?:'ll| will| am|'m) "
    r"(load|set|change|delete|create|write|make|vary|swap)\w*)\b", re.I)

# Words with which a user asks for a new clip. Without one, a vague wish ("mach den Bass spannender")
# is about the clip that exists: gemma composed a second clip next to it every time.
_NEW_CLIP = re.compile(
    r"\b(neu\w*|new|schreib\w*|write|erstell\w*|create|komponier\w*|compose|generier\w*|generate|"
    r"hinzu\w*|add|another|weitere\w*|zusätzlich\w*|extra|song|beat|idee\w*|ideas?|alternativ\w*|option\w*|"
    r"vorschl\w*|suggest\w*|variante\w*|versions?|takes?)\b", re.I)
_TRACK_WORD = re.compile(r"\b(tracks?|spur(en)?|kanal|channel)\b", re.I)
_CLIP_WORD = re.compile(r"\b(clips?)\b", re.I)


def deletes_wrong_thing(user_text: str, tool: str) -> bool:
    """gemma answered "Delete the clip 'Intro Kick'" with delete_track track 0."""
    return tool == "delete_track" and bool(_CLIP_WORD.search(user_text)) and not _TRACK_WORD.search(user_text)


# Things the tools cannot do. gemma lowered the master fader and reported "-14 LUFS"; models took the Lead
# track for "the vocals".
_MASTERING = re.compile(r"\b(lufs|mastern|mastering|master(e)? (den|die|das|the|my|this|diesen|dein\w*)\b)", re.I)
_VOCALS = re.compile(r"\b(vocals?|gesang|stimme|sänger\w*|singer|vox)\b", re.I)
_LESS = re.compile(r"\b(leiser|quieter|softer|lower|decrease|reduce|senk\w*|runter)\b", re.I)
_MUTE = re.compile(r"\b(stumm\w*|mute\w*|silen\w*)\b", re.I)
_MORE = re.compile(r"\b(lauter|louder|higher|increase|erhöh\w*|hoch)\b", re.I)
NO_MASTERING = ("NOT DONE: do not touch the master fader. plan_master puts a chain (EQ Eight, Glue Compressor, "
                "Limiter) on the Master; measure_master reads the Loudness Meter on it; plan_loudness + apply_plan "
                "move the Limiter toward a LUFS target.")
NO_VOCALS = ("NOT DONE: this set has no vocal track, and no other track is the vocals. "
             "Tell the user there is no vocal track; change nothing.")


def missing_thing(user_text: str, session: dict[str, Any], tool: str = "") -> str | None:
    """The refusal for a write when the user asks for mastering or for a vocal track the set lacks."""
    if _MASTERING.search(user_text) and tool not in ("apply_plan", "measure_master"):  # plan_master's chain, the meter
        return NO_MASTERING
    if _VOCALS.search(user_text) and not any(
            re.search(_VOCALS, str(t.get("name", ""))) for t in session.get("tracks", [])):
        return NO_VOCALS
    return None


def unchanged_volume(user_text: str, session: dict[str, Any], tool: str, args: dict[str, Any]) -> str | None:
    """gemma: "mach die Hats leiser" -> update_track volume 0.85, the value the track already had."""
    volume, track = args.get("volume"), args.get("track")
    relative = _LESS.search(user_text) or _MORE.search(user_text)
    if tool == "update_track" and relative and args.get("mute") is True and not _MUTE.search(user_text):
        return "NOT DONE: muting is not 'quieter'. Change volume to a value about 0.1 below the current one; do not mute."
    if tool != "update_track" or not isinstance(volume, (int, float)) or not relative:
        return None
    tracks = session.get("tracks", [])
    found = tracks[track] if isinstance(track, int) and 0 <= track < len(tracks) else next(
        (t for t in tracks if str(t.get("name", "")).lower() == str(track).lower()), None)
    current = ((found or {}).get("mixer") or {}).get("volume", (found or {}).get("volume"))
    if not isinstance(current, (int, float)) or abs(current - volume) > 0.005:
        return None
    direction = "lower" if _LESS.search(user_text) else "higher"
    return (f"NOT DONE: volume {volume} is what the track already has, so nothing would change. "
            f"A relative change needs a value {direction} than the current one (about 0.1 {direction}).")


_PART_KINDS = frozenset({"drums", "bass", "chords", "melody"})


def asks_for_new_clip(text: str) -> bool:
    return bool(_NEW_CLIP.search(text))


def existing_clip_hint(session: dict[str, Any], track: Any, slot: Any = None) -> str | None:
    """The clips a part-writing call would leave next to: names for the error that sends the model to
    transform_notes. None when the track has no clip (a new one is then the only way) or is unknown."""
    tracks = session.get("tracks", [])
    found = None
    if isinstance(track, int) and 0 <= track < len(tracks):
        found = tracks[track]
    elif isinstance(track, str):
        found = next((t for t in tracks if str(t.get("name", "")).lower() == track.lower()), None)
    if not found:
        return None
    if isinstance(slot, int) and any(c["slot"] == slot for c in found.get("clips") or []):
        return None  # an occupied slot: compose's own CONFLICT error handles it
    parts = [f"arrangement_clip '{c.get('name', '')}'" for c in found.get("arrangement_clips") or []]
    parts += [f"slot {c['slot']} '{c.get('name', '')}'" for c in sorted(found.get("clips") or [], key=lambda c: c["slot"])]
    return ", ".join(parts[:6]) or None


def claims_a_change(text: str) -> bool:
    return bool(_CLAIM.search(text)) and not text.rstrip().endswith("?")


def language_reminder(text: str) -> str:
    words = [w.strip(".,;:!?'\"()").lower() for w in text.split()]
    german = sum(w in _GERMAN for w in words) + 2 * any(c in text for c in "äöüÄÖÜß")
    english = sum(w in _ENGLISH for w in words)
    if german > english:
        return "\n\n(Antworte auf Deutsch.)"
    if english > german:
        return "\n\n(Reply in English.)"
    return LANGUAGE_REMINDER
# A model that keeps failing gets stopped early instead of burning all MAX_STEPS rounds:
SAME_FAILURE_LIMIT = 3  # the same call (tool and arguments) failed this often
FAILED_ROUNDS_LIMIT = 6  # this many rounds in a row in which every call failed
# Tools the chat page runs itself (Apply on a plan preview, the Undo button).
UI_TOOLS = frozenset({"apply_plan", "undo"})


class Agent:
    """One conversation: a provider (the model) plus a tool host (Live via MCP)."""

    def __init__(self, provider: Provider, host: ToolHost, system: str = SYSTEM_PROMPT, max_steps: int = MAX_STEPS, compact: bool = False):
        """`compact` sends short descriptions and lean schemas (see compact_tools) and shorter
        results (COMPACT_RESULTS) for small local models."""
        self.provider = provider
        self.host = host
        self.max_steps = max_steps
        self.compact = compact
        provider.configure(system, compact_tools(host.tools) if compact else host.tools)
        self._lock = asyncio.Lock()
        self._notes: list[str] = []  # what the user did through the UI, told to the model with the next message
        self._ui_ids = itertools.count(1)
        self._primed = False  # compact: the session went along with the first message

    def reset(self) -> None:
        self.provider.reset()
        self._notes.clear()
        self._primed = False

    async def _session_note(self) -> str:
        """Small models asked "which track is 'Drop Bass' on?" instead of calling get_session, even when
        told not to: the first message of a conversation brings the session along."""
        if not self.compact or self._primed or "get_session" not in self.host.names():
            return ""
        self._primed = True
        outcome = await self.host.call("get_session", {})
        if outcome.is_error or not outcome.structured:
            return ""
        return "\n\n[The Live set now (get_session):\n" + COMPACT_RESULTS["get_session"](outcome.structured) + "]"

    async def _refuse(self, user_text: str, call: ToolCall) -> str | None:
        """A write the set or the tools cannot back up (see missing_thing, unchanged_volume)."""
        if not (_MASTERING.search(user_text) or _VOCALS.search(user_text) or _LESS.search(user_text) or _MORE.search(user_text)):
            return None
        if "get_session" not in self.host.names():
            return None
        outcome = await self.host.call("get_session", {})
        if not outcome.structured:
            return None
        return missing_thing(user_text, outcome.structured, call.name) or unchanged_volume(user_text, outcome.structured, call.name, call.input)

    async def _new_clip_hint(self, call: ToolCall) -> str | None:
        """compose (or a plan_changes part step) that would add a clip without slot or arrangement_clip
        to a track that has clips, while the user did not ask for a new one."""
        steps = [call.input] if call.name == "compose" else (
            [x for x in call.input.get("steps", []) if isinstance(x, dict)] if call.name == "plan_changes" else [])
        for step in steps:
            kind = step.get("kind") if call.name == "plan_changes" else call.input.get("kind")
            if kind not in _PART_KINDS or step.get("arrangement_clip") is not None:
                continue
            outcome = await self.host.call("get_session", {})
            if not outcome.structured:
                return None
            hint = existing_clip_hint(outcome.structured, step.get("track"), step.get("slot"))
            if hint:
                return hint
        return None

    async def run_tool(self, name: str, arguments: dict[str, Any], emit: Emit) -> None:
        """A tool the user started from the UI (Apply, Undo): the same events as a model's call,
        and the model hears about it with the next message so it does not apply or undo twice."""
        async with self._lock:
            if name not in UI_TOOLS:
                await emit({"type": "error", "message": f"{name} cannot be run from the chat"})
                return
            outcome = await self._call(ToolCall(f"ui{next(self._ui_ids)}", name, arguments), emit, source="user")
            status = "failed: " + outcome.text[:200] if outcome.is_error else "done"
            self._notes.append(f"[The user ran {name} {json.dumps(arguments)} from the chat buttons: {status}]")
            await emit({"type": "done", "stop_reason": "user_tool", "usage": {}})

    async def _call(self, call: ToolCall, emit: Emit, source: str = "model") -> ToolOutcome:
        await emit({"type": "tool_call", "id": call.id, "name": call.name, "input": call.input, "source": source})
        outcome = await self.host.call(call.name, call.input)
        log.info("%s tool %s %s -> %s", source, call.name, describe_input(call.input, 400),
                 "error: " + _first_line(outcome.text) if outcome.is_error else "ok")
        await emit({
            "type": "tool_result",
            "id": call.id,
            "name": call.name,
            "source": source,
            "is_error": outcome.is_error,
            "result": outcome.structured if outcome.structured is not None else outcome.text,
        })
        if outcome.roll:
            await emit({"type": "plan", "id": call.id, "name": call.name, "roll": outcome.roll})
        return outcome

    async def send(self, text: str, emit: Emit) -> None:
        """Handle one user message until the model stops calling tools. Events go to `emit`."""
        async with self._lock:
            log.info("user %s", " ".join(text.split())[:300])
            reminder = language_reminder(text)  # from the user's words, not the notes below
            if self._notes:
                text = "\n".join(self._notes) + "\n\n" + text
                self._notes.clear()
            self.provider.add_user(text + await self._session_note() + reminder if self.compact else text)
            failures: dict[str, int] = {}
            failed_rounds = 0
            unresolved: dict[str, str] = {}  # tool -> error of a write that failed and was not redone
            wrote = False  # a write tool succeeded during this message
            nudged = False
            text_in = text
            guards = 0 if self.compact and not asks_for_new_clip(text) else 2  # twice per message: then the call goes through
            for _ in range(self.max_steps):
                try:
                    turn = await self.provider.stream_turn(emit)
                except Exception as exc:  # network, auth, rate limits: report, keep the session
                    await emit({"type": "error", "message": f"{type(exc).__name__}: {exc}"})
                    return
                if turn.error:
                    await emit({"type": "error", "message": turn.error, "stop_reason": turn.stop_reason})
                    return
                if not turn.tool_calls:
                    if not turn.text.strip() and not nudged:
                        # gemma sometimes only "thinks" and ends with no answer: the chat shows nothing
                        nudged = True
                        self.provider.add_user("[You answered nothing. Do what was asked with the tools, or answer briefly.]")
                        continue
                    if self.compact and not wrote and not unresolved and not nudged and (
                            claims_a_change(turn.text) or ("?" not in text_in and not turn.text.rstrip().endswith("?"))):
                        # a claim, or a request answered with talk only ("tausche ich gegeneinander")
                        nudged = True
                        self.provider.add_user("[No tool ran, so nothing in Live changed. If the user asked for a change, make it "
                                               "now with the tools; if it cannot be done with them, say so plainly.]")
                        continue
                    if unresolved and not nudged:
                        # gemma: transform_notes failed, then "transposed it an octave down"; once per message
                        nudged = True
                        name, error = next(iter(unresolved.items()))
                        self.provider.add_user(
                            f"[Check: {name} failed ({_first_line(error, 200)}) and changed nothing. "
                            "Fix the call and run it now, or tell the user it did not work.]")
                        continue
                    await emit({"type": "done", "stop_reason": turn.stop_reason, "usage": turn.usage})
                    return
                results = []
                stuck = None
                # Sequential on purpose: Live ops depend on each other's order (create, then fill).
                for call in turn.tool_calls:
                    if self.compact and deletes_wrong_thing(text_in, call.name):
                        refusal = "NOT DONE: the user asked to delete a clip, not a track. Delete the clip (delete_clip, or edit_arrangement delete_clip for an arrangement clip)."
                        await emit({"type": "tool_call", "id": call.id, "name": call.name, "input": call.input, "source": "model"})
                        await emit({"type": "tool_result", "id": call.id, "name": call.name, "source": "model", "is_error": True, "result": refusal})
                        results.append(ToolResult(call.id, call.name, refusal, True))
                        continue
                    if self.compact and not self.host.read_only(call.name) and (refusal := await self._refuse(text_in, call)):
                        await emit({"type": "tool_call", "id": call.id, "name": call.name, "input": call.input, "source": "model"})
                        await emit({"type": "tool_result", "id": call.id, "name": call.name, "source": "model", "is_error": True, "result": refusal})
                        results.append(ToolResult(call.id, call.name, refusal, True))
                        unresolved[call.name] = refusal  # "Hats leiser gemacht" after a refused call is a false claim
                        continue
                    if guards < 2 and (hint := await self._new_clip_hint(call)):
                        guards += 1
                        await emit({"type": "tool_call", "id": call.id, "name": call.name, "input": call.input, "source": "model"})
                        refusal = (f"NOT DONE: the user did not ask for a new clip, and this track already has {hint}. "
                                   "Change an existing clip instead: transform_notes with slot or arrangement_clip "
                                   "(operation variation for something more lively, humanize, ...), "
                                   "or compose with arrangement_clip to replace an arrangement clip. "
                                   "Only if a new clip is really wanted, repeat this call.")
                        await emit({"type": "tool_result", "id": call.id, "name": call.name, "source": "model", "is_error": True, "result": refusal})
                        results.append(ToolResult(call.id, call.name, refusal, True))
                        continue
                    outcome = await self._call(call, emit)
                    text = outcome.text
                    if self.compact and not outcome.is_error and outcome.structured and call.name in COMPACT_RESULTS:
                        text = COMPACT_RESULTS[call.name](outcome.structured)
                    results.append(ToolResult(call.id, call.name, text, outcome.is_error))
                    if not outcome.is_error and not self.host.read_only(call.name):
                        unresolved.clear()
                        wrote = True
                    if not outcome.is_error and outcome.roll:
                        wrote = True  # a preview the user applies: "plan created" is no false claim
                    # declined by the user (CANCELLED): the model only has to say so
                    if outcome.is_error and not self.host.read_only(call.name) and "CANCELLED" not in outcome.text:
                        unresolved[call.name] = outcome.text
                    if outcome.is_error:
                        key = call.name + json.dumps(call.input, sort_keys=True, default=str)
                        failures[key] = failures.get(key, 0) + 1
                        if failures[key] >= SAME_FAILURE_LIMIT:
                            stuck = f"{call.name} failed {failures[key]} times with the same arguments"
                self.provider.add_tool_results(results)
                failed_rounds = failed_rounds + 1 if all(r.is_error for r in results) else 0
                if stuck is None and failed_rounds >= FAILED_ROUNDS_LIMIT:
                    stuck = f"every tool call failed {failed_rounds} rounds in a row"
                if stuck is not None:
                    last = next(r.content for r in reversed(results) if r.is_error)
                    await emit({"type": "error", "code": "STUCK", "message": (
                        f"Stopped: {stuck}. Last error: {_first_line(last)} "
                        "Nothing more was changed. Rephrase the request (name the track and section), or try a larger model."
                    )})
                    return
            await emit({"type": "error", "message": f"Stopped after {self.max_steps} tool rounds without an answer."})


def _first_line(text: str, limit: int = 300) -> str:
    line = " ".join(text.strip().split("\n", 1)[0].split())
    return line if len(line) <= limit else line[: limit - 1] + "…"


def describe_input(value: Any, limit: int = 160) -> str:
    """Short one-line rendering of tool input for terminal output."""
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return text if len(text) <= limit else text[: limit - 1] + "…"
