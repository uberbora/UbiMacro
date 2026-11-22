"""Bring the game window to the front (Windows only).

When you press Play inside UbiMacro, UbiMacro has the focus, so the keys
would land in UbiMacro instead of the game. This finds the Roblox window and
switches to it first.
"""

import sys

GAME_TITLES = ("roblox",)


def find_window(titles=GAME_TITLES):
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    found = []
    proc_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd, _lparam):
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                if buf.value.strip().lower() in titles:
                    found.append(hwnd)
                    return False
        return True

    user32.EnumWindows(proc_type(callback), 0)
    return found[0] if found else None


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
