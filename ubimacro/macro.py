"""Macro data: a list of timed events, plus save/load and presets.

Event shapes (``t`` = seconds since recording started):
    {"t": 1.2, "type": "key",    "action": "down"|"up", "key": {...}}
    {"t": 1.2, "type": "click",  "action": "down"|"up", "button": "left", "x": 10, "y": 20}
    {"t": 1.2, "type": "move",   "x": 10, "y": 20}
    {"t": 1.2, "type": "scroll", "dx": 0, "dy": -1, "x": 10, "y": 20}
"""

import json

from .keys import display_name, key_id, make_key

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


def save(path, events, settings=None, meta=None):
    """Write a macro file. ``meta`` holds library info (name, hotkey, favourite...)."""
    data = {"app": "UbiMacro", "version": FORMAT_VERSION, "events": [_clean(e) for e in events]}
    if settings:
        data["settings"] = settings
    if meta:
        data["meta"] = meta
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    import os

    os.replace(tmp, path)  # never leave a half-written macro behind


def _clean(e):
    return {k: v for k, v in e.items() if not k.startswith("_")}


def load_full(path):
    """Return (events, settings, meta) from a saved macro file."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):  # bare list of events
        return normalize(data), {}, {}
    if not isinstance(data, dict):
        raise ValueError("not a macro file")
    return (normalize(data.get("events", [])), data.get("settings", {}) or {}, data.get("meta", {}) or {})


def load(path):
    """Return (events, settings) from a saved macro file."""
    events, settings, _meta = load_full(path)
    return events, settings


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


def lane_of(e):
    """Timeline lane for an event: one per key, one per mouse button, or None."""
    if e.get("type") == "key":
        return ("key",) + tuple(key_id(e.get("key") or {}))
    if e.get("type") == "click":
        return ("btn", e.get("button", "left"))
    return None


def lane_label(lane, events=None):
    if lane is None:
        return "other"
    if lane[0] == "btn":
        return lane[1]
    for e in events or []:
        if e.get("type") == "key" and lane_of(e) == lane:
            return display_name(e.get("key"))
    return str(lane[-1])


def pairs(events):
    """Match every press with its release.

    Returns (bars, singles, lanes): bars are (lane, down_index, up_index),
    singles are indexes of events with no partner (moves, scrolls, an
    unreleased key), lanes are in order of first use.
    """
    open_, bars, singles, lanes = {}, [], [], []
    for i, e in enumerate(events):
        lane = lane_of(e)
        if lane is None:
            singles.append(i)
            continue
        if lane not in lanes:
            lanes.append(lane)
        if e.get("action") == "down":
            if lane in open_:
                singles.append(open_[lane])
            open_[lane] = i
        elif lane in open_:
            bars.append((lane, open_.pop(lane), i))
        else:
            singles.append(i)
    singles.extend(open_.values())
    return bars, sorted(singles), lanes


def partner(events, index):
    """The index paired with ``index`` (press <-> release), or None."""
    bars, _s, _l = pairs(events)
    for _lane, d, u in bars:
        if index == d:
            return u
        if index == u:
            return d
    return None


def move_bar(events, down_index, up_index, delta):
    """Move a press and its release together by ``delta`` seconds."""
    idx = [down_index] if up_index is None else [down_index, up_index]
    if delta < 0:
        delta = max(delta, -events[down_index]["t"])
    return shift(events, idx, delta)


def resize_bar(events, down_index, up_index, delta, edge="end"):
    """Hold longer/shorter: move the release (edge="end") or the press
    (edge="start"), never past the other one."""
    d_t, u_t = events[down_index]["t"], events[up_index]["t"]
    if edge == "end":
        delta = max(delta, (d_t + 0.01) - u_t)
        return shift(events, [up_index], delta)
    delta = min(delta, (u_t - 0.01) - d_t)
    delta = max(delta, -d_t)
    return shift(events, [down_index], delta)


def insert_take(events, at, take, gap=0.05):
    """Put a newly recorded ``take`` in at ``at`` seconds; everything after
    moves later by the take's length."""
    take = trim_start(take)
    length = duration(take) + gap
    out = []
    for e in events:
        c = dict(e)
        if c["t"] > at:
            c["t"] = _r(c["t"] + length)
        out.append(c)
    for e in take:
        c = dict(e)
        c["t"] = _r(at + gap + c["t"])
        out.append(c)
    out.sort(key=lambda e: e["t"])
    return out


def slice_from(events, at):
    """The macro from ``at`` seconds on, starting at 0. Keys already held at
    that moment are pressed at the start so the rest plays the same."""
    bars, _s, _l = pairs(events)
    out = []
    for _lane, d, u in bars:
        if events[d]["t"] < at <= events[u]["t"]:
            c = dict(events[d])
            c["t"] = 0.0
            out.append(c)
    for e in events:
        if e["t"] >= at:
            c = dict(e)
            c["t"] = _r(e["t"] - at)
            out.append(c)
    out.sort(key=lambda e: e["t"])
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
