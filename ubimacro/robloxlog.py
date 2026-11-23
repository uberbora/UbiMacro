"""Watch Roblox's own log file to notice server disconnects.

When the server drops you (kicked, server shut down, lost connection, the
20-minute idle kick...) the Roblox window stays open, so the only reliable
signal is the log Roblox writes to %LOCALAPPDATA%\\Roblox\\logs. The lines
we look for, as Roblox writes them:

    [FLog::Network] Disconnect reason received: 277
    [FLog::Network] Disconnection Notification. Reason: 277
    [FLog::Network] Client has been disconnected with reason: <text>
    [FLog::Network] Lost connection with reason: <text>
    [FLog::Network] Connection lost - Cannot contact server/client

"Sending disconnect with reason: 285" is NOT a disconnect alert: that's
the client leaving on purpose (you closing the game or leaving).
If Roblox changes its log format this stops noticing, and nothing else breaks.
"""

import glob
import os
import re

CODE_RE = re.compile(r"\[FLog::Network\] (?:Disconnect reason received|Disconnection Notification\. Reason): ?(-?\d+)")
TEXT_RE = re.compile(r"\[FLog::Network\] (?:Client has been disconnected|Lost connection) with reason: (.+)")
LOST_RE = re.compile(r"\[FLog::Network\] Connection lost - Cannot contact server")

# known codes -> i18n key for a short reason
# (anything else is shown with Roblox's own reason text, or just its code)
KNOWN = {
    "264": "dc_other_device", "273": "dc_other_device",
    "267": "dc_kicked", "268": "dc_kicked",
    "277": "dc_lost", "279": "dc_lost",
    "278": "dc_idle",
}


def logs_dir():
    base = os.environ.get("LOCALAPPDATA")
    return os.path.join(base, "Roblox", "logs") if base else None


def newest_log(folder):
    if not folder or not os.path.isdir(folder):
        return None
    files = glob.glob(os.path.join(folder, "*.log"))
    player = [f for f in files if "Player" in os.path.basename(f)] or files
    return max(player, key=os.path.getmtime) if player else None


def parse_lines(lines):
    """Disconnect events in some log lines: [{"code": "277" or None, "text": str or None}]."""
    events = []
    for line in lines:
        m = CODE_RE.search(line)
        if m:
            events.append({"code": m.group(1), "text": None})
            continue
        m = TEXT_RE.search(line)
        if m:
            events.append({"code": None, "text": m.group(1).strip()})
            continue
        if LOST_RE.search(line):
            events.append({"code": "277", "text": None})
    return events


def merge(events):
    """Fold the few lines Roblox writes for one disconnect into one event."""
    if not events:
        return None
    code = next((e["code"] for e in events if e["code"]), None)
    text = next((e["text"] for e in events if e["text"]), None)
    return {"code": code, "text": text}


class LogWatcher:
    """Reads only what Roblox writes after ``start()``. Call ``poll()`` about
    once a second; it returns a disconnect event or None."""

    def __init__(self, folder=None):
        self.folder = folder or logs_dir()
        self.path = None
        self.pos = 0
        self._partial = ""

    def start(self):
        self.path = newest_log(self.folder)
        self.pos = os.path.getsize(self.path) if self.path else 0
        self._partial = ""
        return self.path is not None

    def poll(self):
        newest = newest_log(self.folder)
        if newest != self.path:  # Roblox restarted: follow the new log from its start
            self.path, self.pos, self._partial = newest, 0, ""
        if not self.path:
            return None
        try:
            size = os.path.getsize(self.path)
            if size < self.pos:
                self.pos = 0
            if size == self.pos:
                return None
            with open(self.path, "r", encoding="utf-8", errors="replace") as f:
                f.seek(self.pos)
                chunk = f.read()
                self.pos = f.tell()
        except OSError:
            return None
        data = self._partial + chunk
        lines = data.split("\n")
        self._partial = lines.pop()  # last piece may be half-written
        return merge(parse_lines(lines))
