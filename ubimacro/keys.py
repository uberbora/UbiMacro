"""Helpers for turning keys into plain, JSON-friendly dicts and back.

A key is stored as a dict like ``{"name": "w", "vk": 87, "char": "w"}``.
``vk`` is the Windows virtual-key code (when available), which is what the
Windows playback backend uses to look up the hardware scancode.
"""

import sys

# Virtual keys that need the "extended key" flag when sent as scancodes.
EXTENDED_VKS = {
    0x21, 0x22, 0x23, 0x24,  # page up, page down, end, home
    0x25, 0x26, 0x27, 0x28,  # arrows
    0x2C, 0x2D, 0x2E,        # print screen, insert, delete
    0x5B, 0x5C, 0x5D,        # left win, right win, apps
    0x6F,                    # numpad divide
    0x90,                    # num lock
    0xA3, 0xA5,              # right ctrl, right alt
}

# Fallback name -> Windows virtual-key code, for keys stored without a vk.
NAME_TO_VK = {
    "space": 0x20, "enter": 0x0D, "tab": 0x09, "esc": 0x1B, "backspace": 0x08,
    "shift": 0xA0, "shift_l": 0xA0, "shift_r": 0xA1,
    "ctrl": 0xA2, "ctrl_l": 0xA2, "ctrl_r": 0xA3,
    "alt": 0xA4, "alt_l": 0xA4, "alt_r": 0xA5, "alt_gr": 0xA5,
    "caps_lock": 0x14, "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "home": 0x24, "end": 0x23, "page_up": 0x21, "page_down": 0x22,
    "insert": 0x2D, "delete": 0x2E,
}
for _i in range(1, 25):
    NAME_TO_VK[f"f{_i}"] = 0x6F + _i  # F1 = 0x70


def key_to_dict(key):
    """Convert a pynput key object into a plain dict."""
    from pynput import keyboard

    if isinstance(key, keyboard.Key):
        d = {"name": key.name}
        vk = getattr(key.value, "vk", None)
        if vk is not None:
            d["vk"] = int(vk)
        return d

    vk = getattr(key, "vk", None)
    ch = getattr(key, "char", None)
    d = {}
    if vk is not None:
        d["vk"] = int(vk)
    if ch is not None and len(ch) == 1 and ch.isprintable():
        d["char"] = ch
    if sys.platform == "win32" and vk is not None and (0x30 <= vk <= 0x39 or 0x41 <= vk <= 0x5A):
        # Letters/digits: name from the vk so Shift/Ctrl don't change it.
        name = chr(vk).lower()
    elif "char" in d:
        name = d["char"].lower()
    elif vk is not None:
        name = f"vk{vk}"
    else:
        name = "unknown"
    d["name"] = name
    return d


def name_to_vk(d):
    """Best-effort Windows vk for a key dict."""
    if d.get("vk") is not None:
        return int(d["vk"])
    name = (d.get("name") or "").lower()
    if name in NAME_TO_VK:
        return NAME_TO_VK[name]
    if len(name) == 1 and (name.isalpha() or name.isdigit()):
        return ord(name.upper())
    return None


def key_id(d):
    """A hashable identity for a key dict."""
    if d.get("vk") is not None:
        return ("vk", int(d["vk"]))
    return ("name", d.get("name"))


def keys_match(a, b):
    if not a or not b:
        return False
    na, nb = a.get("name"), b.get("name")
    if _good_name(na) and _good_name(nb):
        # Names are stable across platforms (vk codes are not, outside Windows).
        return na == nb
    if a.get("vk") is not None and b.get("vk") is not None:
        return int(a["vk"]) == int(b["vk"])
    return a.get("name") == b.get("name")


def _good_name(n):
    return bool(n) and n != "unknown" and not (n.startswith("vk") and n[2:].isdigit())


def display_name(d):
    if not d:
        return "None"
    n = d.get("name") or "?"
    if len(n) <= 3:
        return n.upper()
    return n.replace("_", " ").title()


def make_key(name, vk=None):
    """Build a key dict by hand (used for presets)."""
    d = {"name": name}
    if vk is None:
        vk = name_to_vk(d)
    if vk is not None:
        d["vk"] = vk
    if len(name) == 1:
        d["char"] = name
    return d
