"""Bring the game window to the front (Windows only).

When you press Play inside UbiMacro, UbiMacro has the focus, so the keys
would land in UbiMacro instead of the game. This finds the Roblox window and
switches to it first.
"""

import sys

GAME_TITLES = ("roblox",)


def list_windows():
    """Visible top-level windows with a title: [(hwnd, title), ...]."""
    if sys.platform != "win32":
        return []
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    out = []
    proc_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd, _lparam):
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                if buf.value.strip():
                    out.append((hwnd, buf.value.strip()))
        return True

    user32.EnumWindows(proc_type(callback), 0)
    return out


def find_window(titles=GAME_TITLES):
    """Find a window whose title matches one of ``titles`` (exact first, then contains)."""
    wins = list_windows()
    wanted = [t.lower() for t in titles]
    for hwnd, title in wins:
        if title.lower() in wanted:
            return hwnd
    for hwnd, title in wins:
        if any(w and w in title.lower() for w in wanted):
            return hwnd
    return None


def relative_to_foreground(x, y):
    """Where (x, y) falls inside the foreground window, as fractions (0..1) of
    its client area, or None. Recorded with clicks so background playback can
    aim at the same spot even after the window moves."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        pt = wintypes.POINT(int(x), int(y))
        user32.ScreenToClient(hwnd, ctypes.byref(pt))
        r = wintypes.RECT()
        user32.GetClientRect(hwnd, ctypes.byref(r))
        w, h = r.right - r.left, r.bottom - r.top
        if w <= 0 or h <= 0 or not (0 <= pt.x < w and 0 <= pt.y < h):
            return None
        return round(pt.x / w, 4), round(pt.y / h, 4)
    except Exception:
        return None


def focus_game(titles=GAME_TITLES):
    """Return True if a game window was found and brought to the front."""
    hwnd = find_window(titles)
    if not hwnd:
        return False
    import ctypes

    user32 = ctypes.windll.user32
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    user32.SetForegroundWindow(hwnd)
    return True


def system_language():
    """'tr' if Windows (or the locale) is Turkish, else 'en'."""
    try:
        if sys.platform == "win32":
            import ctypes

            if ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF == 0x1F:
                return "tr"
            return "en"
        import locale

        loc = (locale.getlocale()[0] or "").lower()
        return "tr" if loc.startswith("tr") else "en"
    except Exception:
        return "en"
