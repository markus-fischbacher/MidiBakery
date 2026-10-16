"""Live's browser: find presets, kits and devices by name and load them onto a track.

The browser tree is large (the Core Library alone has thousands of items), so a
search walks it a chunk per tick and stops after a node budget.
"""

import time

from ..protocol import ErrorCode, OpError
from ..registry import op

CATEGORIES = ("drums", "instruments", "audio_effects", "midi_effects", "sounds", "packs", "user_library", "plugins")
NODES_PER_TICK = 400
MAX_NODES = 40000
LOAD_TICKS = 50  # ~5 s: Live loads a kit's samples on a later tick
SETTLE_TICKS = 5  # the chain must stay unchanged this long before a load counts as done
COOLDOWN_SECONDS = 1.0  # between loads: Live 12.4 crashed when a rack was swapped right after it loaded
_last_load = [0.0]


def _browser():
    import Live

    return Live.Application.get_application().browser


def _roots(browser, category):
    names = CATEGORIES if category == "all" else (category,)
    roots = [(name, getattr(browser, name, None)) for name in names]
    return [(name, item) for name, item in roots if item is not None]


def _children(item):
    try:
        return list(item.children)
    except Exception:
        return []


def _entry(path, item):
    return {"name": item.name, "path": path, "uri": getattr(item, "uri", ""), "is_device": bool(getattr(item, "is_device", False))}


@op("browser.search", multi_tick=True)
def browser_search(ctx, params):
    """Items whose name contains every word of `query`, breadth first so shallow
    items (kits, devices) come before deep ones (single samples, presets in packs)."""
    terms = params["query"].lower().split()
    limit = params.get("limit", 20)
    loadable = params.get("loadable_only", True)
    queue = [([name], item) for name, item in _roots(_browser(), params.get("category", "all"))]
    found, visited = [], 0
    while queue and len(found) < limit and visited < MAX_NODES:
        path, item = queue.pop(0)
        visited += 1
        if len(path) > 1:
            name = item.name.lower()
            if all(t in name for t in terms) and (item.is_loadable or not loadable):
                found.append(_entry(path, item))
        queue.extend((path + [child.name], child) for child in _children(item))
        if visited % NODES_PER_TICK == 0:
            yield
    return {"items": found, "visited": visited, "complete": not queue}


def _item_at(path):
    if not path or path[0] not in CATEGORIES:
        raise OpError(ErrorCode.INVALID_PARAMS, "path must start with a category: %s" % ", ".join(CATEGORIES))
    item = getattr(_browser(), path[0])
    for depth, name in enumerate(path[1:], 1):
        match = next((c for c in _children(item) if c.name == name), None)
        if match is None:
            raise OpError(ErrorCode.NOT_FOUND, "No browser item '%s' in %s" % (name, "/".join(path[:depth])),
                          available=[c.name for c in _children(item)][:40])
        item = match
    if not item.is_loadable:
        raise OpError(ErrorCode.INVALID_PARAMS, "'%s' cannot be loaded (a folder?)" % "/".join(path))
    return item


def _chain(track):
    return [(d.name, d.class_name) for d in track.devices]


@op("browser.load", multi_tick=True)
def browser_load(ctx, params):
    """Load the item like a double-click in the browser with the track selected: an
    instrument or kit replaces the track's instrument, an effect is appended."""
    track = ctx.track(params["track"])
    item = _item_at(params["path"])
    before = _chain(track)
    while time.monotonic() - _last_load[0] < COOLDOWN_SECONDS:
        yield
    view = ctx.song.view
    selected = view.selected_track
    view.selected_track = track
    try:
        _browser().load_item(item)
        for _ in range(LOAD_TICKS):
            if _chain(track) != before:
                break
            yield
        else:
            raise OpError(ErrorCode.LIVE_ERROR, "Live did not load '%s' onto track %d" % (item.name, params["track"]))
        settled, last = 0, _chain(track)
        while settled < SETTLE_TICKS:  # a kit's chains and samples fill in after the rack appears
            yield
            now = _chain(track)
            settled, last = (settled + 1, last) if now == last else (0, now)
    finally:
        _last_load[0] = time.monotonic()
        view.selected_track = selected  # the user's selection stays
    return {
        "loaded": item.name,
        "devices": [{"index": i, "name": d.name, "class_name": d.class_name} for i, d in enumerate(track.devices)],
    }
