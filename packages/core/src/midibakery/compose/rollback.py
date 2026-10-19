"""Taking back what a failed write already did, so a change lands whole or not at all.

A batch (or an ``arrangement.edit``) stops at its first failing op but keeps what
already ran, inside its undo step. The Remote Script does not undo it itself:
undoing a step that changed nothing would revert the user's previous action. The
core knows from ``completed`` in the error whether anything ran, and undoes then.

Locators are different: Live makes each one its own undo step, and a locator that
timed out may still land, so their undo steps cannot be counted. They are
restored by comparing them with a snapshot instead.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from midibakery.bridge import BridgeError

Call = Callable[..., Awaitable[dict[str, Any]]]


def completed(error: BridgeError) -> int:
    """How many ops (batch) or actions (arrangement.edit) ran before the failure."""
    done = error.details.get("completed")
    if isinstance(done, list):
        return len(done)
    return done if isinstance(done, int) else 0


def batch_steps(ops: list[str], done: int) -> int:
    """Undo steps the first `done` ops of a batch left: one, but Live 12.4 closes the step when it
    creates a return track, so what follows the last new return is a second one (measured)."""
    if not done:
        return 0
    last_return = max((i for i, op in enumerate(ops[:done]) if op == "return.create"), default=None)
    return 2 if last_return is not None and last_return < done - 1 else 1


async def undo(call: Call, error: BridgeError, steps: int, unchanged: str = "Live is unchanged") -> None:
    """Undo `steps` steps and say so in the error. Sets details['rolled_back'] (False if the undo
    itself failed), so callers further up do not undo the same steps again."""
    if not steps:
        return
    try:
        for _ in range(steps):
            await call("history.step", {"action": "undo"})
    except BridgeError as undo_error:
        error.details["rolled_back"] = False
        error.message += f" (undoing the {steps} step(s) that had already run failed: {undo_error.message}; check Live's undo history)"
        return
    error.details["rolled_back"] = True
    error.message += f"; the {steps} step(s) that had already run were undone, {unchanged}"


async def undo_batch(call: Call, error: BridgeError, ops: list[str]) -> None:
    await undo(call, error, batch_steps(ops, completed(error)))


async def undo_edit(call: Call, error: BridgeError) -> None:
    """arrangement.edit is one undo step for all its actions."""
    await undo(call, error, 1 if completed(error) else 0)


async def locators(call: Call) -> list[dict[str, Any]]:
    return (await call("arrangement.get", {}))["locators"]


async def restore_locators(call: Call, error: BridgeError, before: list[dict[str, Any]]) -> None:
    """Set, delete and rename locators until they match `before` again."""
    try:
        now = {loc["time"]: loc["name"] for loc in await locators(call)}
        was = {loc["time"]: loc["name"] for loc in before}
        actions = [{"action": "delete_locator", "time": t} for t in now if t not in was]
        actions += [{"action": "set_locator", "time": t, "name": name} for t, name in was.items() if now.get(t) != name]
        if actions:
            await call("arrangement.locators", {"actions": actions})
    except BridgeError as restore_error:
        error.details["locators_restored"] = False
        error.message += f" (restoring the locators failed: {restore_error.message}; check them in Live)"
        return
    if actions:
        error.details["locators_restored"] = True
        error.message += "; the locators were put back as they were"
