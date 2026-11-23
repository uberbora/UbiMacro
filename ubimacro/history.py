"""A short history of past runs: what ran, when, for how long and how it ended."""

import json
import os
import time

LIMIT = 100


class History:
    def __init__(self, path):
        self.path = path

    def entries(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return [e for e in data if isinstance(e, dict)] if isinstance(data, list) else []
        except (OSError, ValueError):
            return []

    def add(self, name, kind, start, seconds, loops=0, clicks=0, end="stopped"):
        items = self.entries()
        items.insert(0, {"name": name, "kind": kind, "start": float(start), "seconds": round(float(seconds), 1),
                         "loops": int(loops), "clicks": int(clicks), "end": end})
        del items[LIMIT:]
        self._write(items)
        return items[0]

    def clear(self):
        self._write([])

    def _write(self, items):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=1, ensure_ascii=False)
        os.replace(tmp, self.path)

    def total_today(self):
        start = time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, -1))
        return sum(e["seconds"] for e in self.entries() if e.get("start", 0) >= start)
