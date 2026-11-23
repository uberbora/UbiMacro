"""Sounds, Discord messages and the update check. Everything network-related
runs in a background thread and never blocks the window."""

import json
import sys
import threading
import urllib.request

REPO = "uberbora/UbiMacro"
RELEASES_URL = f"https://github.com/{REPO}/releases/latest"


def play_sound(kind="start", bell=None):
    """kind: start / stop / alert. Uses Windows sounds, else the Tk bell."""
    if sys.platform == "win32":
        def run():
            try:
                import winsound

                if kind == "alert":
                    for _ in range(3):
                        winsound.Beep(1200, 220)
                        winsound.Beep(800, 220)
                elif kind == "start":
                    winsound.Beep(880, 90)
                    winsound.Beep(1320, 110)
                else:
                    winsound.Beep(1320, 90)
                    winsound.Beep(880, 110)
            except Exception:
                pass

        threading.Thread(target=run, daemon=True).start()
    elif bell:
        bell()


ALERTS = ("closed", "disconnected", "finished", "status", "paused", "started", "stopped")
# (on by default, ping by default, embed colour)
ALERT_DEFAULTS = {
    "closed": (True, True, 0xB3361B),
    "disconnected": (True, True, 0xB3361B),
    "finished": (True, False, 0x0E7447),
    "status": (False, False, 0xB01F7A),
    "paused": (False, True, 0x8A5E00),
    "started": (False, False, 0x0E7447),
    "stopped": (False, False, 0x64575F),
}
PLACEHOLDERS = ("macro", "time", "loops", "clicks", "reason", "date")


def fill(template, values):
    """Fill {placeholders}; unknown ones and stray braces are left as typed."""
    import re

    return re.sub(r"\{(\w+)\}", lambda m: str(values[m.group(1)]) if m.group(1) in values else m.group(0),
                  template or "")


def default_alerts():
    return {k: {"on": on, "ping": ping, "text": ""} for k, (on, ping, _c) in ALERT_DEFAULTS.items()}


def discord_payload(text, title=None, color=None, ping_user=None):
    """A Discord message: an embed card, plus an @mention when ``ping_user``."""
    if title is None:  # plain message (kept for simple uses)
        return {"content": text[:1900], "username": "UbiMacro"}
    import datetime

    embed = {"title": title[:250], "description": text[:3900], "footer": {"text": "UbiMacro"},
             "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    if color is not None:
        embed["color"] = int(color)
    payload = {"username": "UbiMacro", "embeds": [embed], "allowed_mentions": {"parse": []}}
    uid = "".join(ch for ch in str(ping_user or "") if ch.isdigit())
    if uid:
        payload["content"] = f"<@{uid}>"
        payload["allowed_mentions"] = {"users": [uid]}
    return payload


def is_webhook(url):
    url = (url or "").strip()
    return url.startswith("https://") and "/api/webhooks/" in url


def send_discord(url, text, done=None, title=None, color=None, ping_user=None):
    """POST a message to a Discord webhook. ``done(ok, error)`` is called from
    the worker thread."""
    def run():
        try:
            if not is_webhook(url):
                raise ValueError("not a Discord webhook link")
            body = discord_payload(text, title, color, ping_user)
            req = urllib.request.Request(
                url.strip(), data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "UbiMacro"}, method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                ok = 200 <= resp.status < 300
            if done:
                done(ok, None)
        except Exception as e:
            if done:
                done(False, e)

    threading.Thread(target=run, daemon=True).start()


def parse_version(v):
    nums = []
    for part in str(v).lstrip("vV").split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        nums.append(int(digits) if digits else 0)
    return tuple(nums + [0] * (3 - len(nums)))[:3]


def is_newer(latest, current):
    return parse_version(latest) > parse_version(current)


def check_update(current, done):
    """``done(tag, url)`` if a newer release exists, ``done(None, None)`` if
    not or if GitHub can't be reached (e.g. the repo is private)."""
    def run():
        try:
            req = urllib.request.Request(
                f"https://api.github.com/repos/{REPO}/releases/latest",
                headers={"Accept": "application/vnd.github+json", "User-Agent": "UbiMacro"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            tag = data.get("tag_name") or ""
            if tag and is_newer(tag, current):
                done(tag, data.get("html_url") or RELEASES_URL)
                return
        except Exception:
            pass
        done(None, None)

    threading.Thread(target=run, daemon=True).start()
