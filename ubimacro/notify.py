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


def discord_payload(text):
    return {"content": text[:1900], "username": "UbiMacro"}


def is_webhook(url):
    url = (url or "").strip()
    return url.startswith("https://") and "/api/webhooks/" in url


def send_discord(url, text, done=None):
    """POST a message to a Discord webhook. ``done(ok, error)`` is called from
    the worker thread."""
    def run():
        try:
            if not is_webhook(url):
                raise ValueError("not a Discord webhook link")
            req = urllib.request.Request(
                url.strip(), data=json.dumps(discord_payload(text)).encode("utf-8"),
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
