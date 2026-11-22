"""The macro library: every macro is one .json file in the macros folder.

Each file keeps its own name, hotkey, favourite flag and last-used time in
its "meta" block, so macros copied in by hand (or saved by older versions)
show up automatically.
"""

import os
import re
import shutil
import time
from datetime import datetime

from . import macro


class Entry:
    __slots__ = ("id", "path", "name", "hotkey", "favourite", "last_used", "created", "count", "length")

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))

    def initials(self):
        words = re.findall(r"[^\W_]+", self.name or "", re.UNICODE)
        if len(words) >= 2:
            return (words[0][0] + words[1][0]).upper()
        return (self.name or "?")[:2].upper()


def _slug(name):
    s = re.sub(r"[^\w-]+", "-", (name or "macro").strip().lower(), flags=re.UNICODE).strip("-")
    return s[:40] or "macro"


class Library:
    def __init__(self, folder):
        self.folder = folder
        os.makedirs(folder, exist_ok=True)

    # ---- reading ---------------------------------------------------------
    def _path(self, mid):
        if not mid or "/" in mid or "\\" in mid or mid.startswith("."):
            raise ValueError("bad macro id")
        return os.path.join(self.folder, mid + ".json")

    def entries(self):
        out = []
        for fn in os.listdir(self.folder):
            if not fn.endswith(".json") or fn.startswith("."):
                continue
            mid = fn[:-5]
            path = os.path.join(self.folder, fn)
            try:
                events, _s, meta = macro.load_full(path)
            except (OSError, ValueError):
                continue
            out.append(Entry(
                id=mid, path=path, name=meta.get("name") or mid.replace("-", " ").capitalize(),
                hotkey=meta.get("hotkey"), favourite=bool(meta.get("favourite")),
                last_used=meta.get("last_used") or 0, created=meta.get("created") or os.path.getmtime(path),
                count=len(events), length=macro.duration(events)))
        out.sort(key=lambda e: (not e.favourite, -(e.last_used or 0), (e.name or "").lower()))
        return out

    def get(self, mid):
        for e in self.entries():
            if e.id == mid:
                return e
        return None

    def load(self, mid):
        """(events, settings, meta) of one macro."""
        return macro.load_full(self._path(mid))

    # ---- writing ---------------------------------------------------------
    def _unique_id(self, name):
        base = _slug(name)
        mid, n = base, 2
        while os.path.exists(os.path.join(self.folder, mid + ".json")):
            mid = f"{base}-{n}"
            n += 1
        return mid

    def unique_name(self, base):
        names = {(e.name or "").lower() for e in self.entries()}
        if base.lower() not in names:
            return base
        n = 2
        while f"{base} {n}".lower() in names:
            n += 1
        return f"{base} {n}"

    def create(self, name, events, settings=None, meta=None):
        mid = self._unique_id(name)
        m = dict(meta or {})
        m.update({"name": name, "created": m.get("created") or time.time()})
        macro.save(self._path(mid), events, settings, m)
        return mid

    def _update_meta(self, mid, **changes):
        events, settings, meta = self.load(mid)
        meta.update(changes)
        meta = {k: v for k, v in meta.items() if v is not None}
        macro.save(self._path(mid), events, settings, meta)

    def save_events(self, mid, events, settings=None):
        _e, old_settings, meta = self.load(mid)
        macro.save(self._path(mid), events, settings if settings is not None else old_settings, meta)

    def rename(self, mid, name):
        self._update_meta(mid, name=name.strip() or "Macro")

    def set_hotkey(self, mid, hotkey):
        self._update_meta(mid, hotkey=hotkey)

    def set_favourite(self, mid, fav):
        self._update_meta(mid, favourite=bool(fav))

    def mark_used(self, mid):
        self._update_meta(mid, last_used=time.time())

    def duplicate(self, mid, copy_word="copy"):
        events, settings, meta = self.load(mid)
        name = self.unique_name(f"{meta.get('name') or mid} ({copy_word})")
        meta = {k: v for k, v in meta.items() if k not in ("hotkey", "last_used", "created")}
        return self.create(name, events, settings, meta)

    def delete(self, mid):
        os.remove(self._path(mid))

    def export(self, mid, dest):
        shutil.copyfile(self._path(mid), dest)

    def import_file(self, src):
        events, settings, meta = macro.load_full(src)
        if not events:
            raise ValueError("this file has no events")
        name = meta.get("name") or os.path.splitext(os.path.basename(src))[0]
        meta = {k: v for k, v in meta.items() if k not in ("hotkey",)}
        return self.create(self.unique_name(name), events, settings, meta)


def ago(ts, words):
    """'today' / 'yesterday' / 'N days ago' / a date, from a timestamp."""
    if not ts:
        return words["never"]
    d = (datetime.now().date() - datetime.fromtimestamp(ts).date()).days
    if d <= 0:
        return words["today"]
    if d == 1:
        return words["yesterday"]
    if d < 30:
        return words["days"].format(n=d)
    return datetime.fromtimestamp(ts).strftime("%d.%m.%Y")
