"""Macro data: a list of timed events, plus save/load and presets.

Event shapes (``t`` = seconds since recording started):
    {"t": 1.2, "type": "key",    "action": "down"|"up", "key": {...}}
    {"t": 1.2, "type": "click",  "action": "down"|"up", "button": "left", "x": 10, "y": 20}
    {"t": 1.2, "type": "move",   "x": 10, "y": 20}
    {"t": 1.2, "type": "scroll", "dx": 0, "dy": -1, "x": 10, "y": 20}
"""

import json

from .keys import display_name, make_key

FORMAT_VERSION = 1


def duration(events):
    return max((e["t"] for e in events), default=0.0)


def describe(event):
    """Short human-readable description for the event list."""
    typ = event.get("type")
    if typ == "key":
        return f"{display_name(event.get('key'))} {event.get('action')}"
    if typ == "click":
        return f"{event.get('button', '?')} click {event.get('action')} @ ({event.get('x')}, {event.get('y')})"
    if typ == "move":
        return f"move to ({event.get('x')}, {event.get('y')})"
    if typ == "scroll":
        return f"scroll dx={event.get('dx')} dy={event.get('dy')}"
    return str(event)


def save(path, events, settings=None):
    data = {"app": "UbiMacro", "version": FORMAT_VERSION, "events": events}
    if settings:
        data["settings"] = settings
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)


def load(path):
    """Return (events, settings) from a saved macro file."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):  # bare list of events
        return normalize(data), {}
    return normalize(data.get("events", [])), data.get("settings", {}) or {}


def normalize(events):
    """Drop malformed events and sort by time."""
    out = []
    for e in events:
        if not isinstance(e, dict) or "type" not in e:
            continue
        try:
            e["t"] = max(0.0, float(e.get("t", 0.0)))
        except (TypeError, ValueError):
            continue
        out.append(e)
    out.sort(key=lambda e: e["t"])
    return out


# ---------------------------------------------------------------- editing
# All editing helpers return a new, time-sorted list and never change the
# input list, so the app can keep the old one for Undo.

def _copy(events):
    return [dict(e) for e in events]


def _r(t):
    return round(max(0.0, t), 4)


def gaps(events):
    """Seconds between each event and the one before it (first: since start)."""
    out, prev = [], 0.0
    for e in events:
        out.append(e["t"] - prev)
        prev = e["t"]
    return out


def trim_start(events, keep=0.0):
    """Remove the delay before the first event (e.g. the 0.121 s from a late click)."""
    if not events:
        return []
    shift = events[0]["t"] - max(0.0, keep)
    out = _copy(events)
    for e in out:
        e["t"] = _r(e["t"] - shift)
    return out


def set_gap(events, index, gap):
    """Make the pause before event ``index`` exactly ``gap`` seconds.

    Everything after it moves by the same amount, so key holds and the
    order of events stay intact.
    """
    out = _copy(events)
    prev = out[index - 1]["t"] if index > 0 else 0.0
    delta = (prev + max(0.0, gap)) - out[index]["t"]
    for e in out[index:]:
        e["t"] = _r(e["t"] + delta)
    return out


def set_time(events, index, new_t, move_following=True):
    """Put event ``index`` at ``new_t`` seconds.

    With ``move_following`` the events after it move along (keeping their
    spacing); without it only this event moves and the list is re-sorted.
    """
    out = _copy(events)
    if move_following:
        prev = out[index - 1]["t"] if index > 0 else 0.0
        return set_gap(events, index, max(0.0, new_t) - prev)
    out[index]["t"] = _r(new_t)
    out.sort(key=lambda e: e["t"])
    return out


def shift(events, indices, delta):
    """Move the chosen events earlier/later by ``delta`` seconds."""
    chosen = set(indices)
    out = _copy(events)
    for i, e in enumerate(out):
        if i in chosen:
            e["t"] = _r(e["t"] + delta)
    out.sort(key=lambda e: e["t"])
    return out


def cap_gaps(events, max_gap):
    """Shorten every pause longer than ``max_gap`` seconds down to ``max_gap``."""
    out = _copy(events)
    removed, prev_orig = 0.0, 0.0
    for e in out:
        orig = e["t"]
        gap = orig - prev_orig
        if gap > max_gap:
            removed += gap - max_gap
        prev_orig = orig
        e["t"] = _r(orig - removed)
    return out


def delete(events, indices):
    chosen = set(indices)
    return [dict(e) for i, e in enumerate(events) if i not in chosen]


def _tap(events, t, key, hold):
    events.append({"t": round(t, 3), "type": "key", "action": "down", "key": key})
    events.append({"t": round(t + hold, 3), "type": "key", "action": "up", "key": key})
    return t + hold


def anti_afk_preset():
    """A tiny built-in macro: jump, step forward, step back.

    Loop it with a delay (e.g. 60s) and you won't get the 20-minute idle kick,
    and you end up roughly where you started.
    """
    ev = []
    t = 0.0
    t = _tap(ev, t, make_key("space", 0x20), 0.10) + 0.6
    t = _tap(ev, t, make_key("w", 0x57), 0.35) + 0.3
    _tap(ev, t, make_key("s", 0x53), 0.35)
    return ev
