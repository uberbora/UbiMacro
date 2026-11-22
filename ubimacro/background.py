"""Background playback (experimental, Windows only).

Normal playback types into whatever window is in front, like a real
keyboard. This backend instead posts keyboard and mouse *window messages*
straight to one chosen window (e.g. Roblox), so it can sit on another screen
or behind other windows while you keep working.

Whether a game reacts to these messages is up to the game: many read input
another way (raw input) and only while they are the active window. That is
what the "background test" in Settings is for. ``fake_focus`` additionally
tells the window it has just been activated before input is sent, which
some games need before they accept input.
"""

import sys

from .keys import EXTENDED_VKS, name_to_vk

WM_ACTIVATE = 0x0006
WM_SETFOCUS = 0x0007
WM_ACTIVATEAPP = 0x001C
WM_NCACTIVATE = 0x0086
WM_KEYDOWN, WM_KEYUP = 0x0100, 0x0101
WM_SYSKEYDOWN, WM_SYSKEYUP = 0x0104, 0x0105
WM_MOUSEMOVE = 0x0200
WM_MOUSEWHEEL, WM_MOUSEHWHEEL = 0x020A, 0x020E
BUTTON_MSGS = {  # button: (down msg, up msg, MK_ flag, xbutton number)
    "left": (0x0201, 0x0202, 0x0001, 0),
    "right": (0x0204, 0x0205, 0x0002, 0),
    "middle": (0x0207, 0x0208, 0x0010, 0),
    "x1": (0x020B, 0x020C, 0x0020, 1),
    "x2": (0x020B, 0x020C, 0x0040, 2),
}
ALT_VKS = {0x12, 0xA4, 0xA5}


def key_lparam(scan, extended, down):
    lp = 1 | (scan & 0xFF) << 16
    if extended:
        lp |= 1 << 24
    if not down:
        lp |= (1 << 30) | (1 << 31)
    return lp


def point_lparam(x, y):
    return ((int(y) & 0xFFFF) << 16) | (int(x) & 0xFFFF)


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _u = ctypes.WinDLL("user32", use_last_error=True)
    _u.PostMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
    _u.PostMessageW.restype = wintypes.BOOL
    _u.MapVirtualKeyW.argtypes = (wintypes.UINT, wintypes.UINT)
    _u.MapVirtualKeyW.restype = wintypes.UINT
    _u.IsWindow.argtypes = (wintypes.HWND,)
    _u.ScreenToClient.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.POINT))
    _u.ClientToScreen.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.POINT))
    _u.GetClientRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))


class MessageBackend:
    def __init__(self, hwnd, fake_focus=True):
        if sys.platform != "win32":
            raise RuntimeError("Background playback only works on Windows")
        self.hwnd = wintypes.HWND(hwnd)
        self.fake_focus = fake_focus
        self._buttons = 0
        self._pos = None  # client coords

    # ---- helpers ---------------------------------------------------------
    def _post(self, msg, wparam=0, lparam=0):
        _u.PostMessageW(self.hwnd, msg, wparam, lparam)

    def alive(self):
        return bool(_u.IsWindow(self.hwnd))

    def _client_size(self):
        r = wintypes.RECT()
        _u.GetClientRect(self.hwnd, ctypes.byref(r))
        return max(1, r.right - r.left), max(1, r.bottom - r.top)

    def _center(self):
        w, h = self._client_size()
        return w // 2, h // 2

    def prepare(self):
        """Tell the window it is active (if fake_focus). Called at each loop start."""
        if self.fake_focus:
            self._post(WM_ACTIVATEAPP, 1, 0)
            self._post(WM_NCACTIVATE, 1, 0)
            self._post(WM_ACTIVATE, 1, 0)  # WA_ACTIVE
            self._post(WM_SETFOCUS, 0, 0)

    # ---- backend interface ----------------------------------------------
    def key(self, d, down):
        vk = name_to_vk(d)
        if vk is None:
            return
        if down and self.fake_focus:
            self._post(WM_SETFOCUS, 0, 0)
        scan = _u.MapVirtualKeyW(vk, 0)
        alt = vk in ALT_VKS
        msg = (WM_SYSKEYDOWN if down else WM_SYSKEYUP) if alt else (WM_KEYDOWN if down else WM_KEYUP)
        self._post(msg, vk, key_lparam(scan, vk in EXTENDED_VKS, down))

    def mouse_move(self, x, y):
        pt = wintypes.POINT(int(x), int(y))
        _u.ScreenToClient(self.hwnd, ctypes.byref(pt))
        self._pos = (pt.x, pt.y)
        self._post(WM_MOUSEMOVE, self._buttons, point_lparam(pt.x, pt.y))

    def move_to_event(self, ev):
        """Aim a click inside the window. Uses the position relative to the
        window recorded with the click (so it still lands right after you move
        the window to another screen), else the screen position."""
        if "rx" in ev and "ry" in ev:
            w, h = self._client_size()
            self._pos = (int(ev["rx"] * w), int(ev["ry"] * h))
            self._post(WM_MOUSEMOVE, self._buttons, point_lparam(*self._pos))
        elif "x" in ev and "y" in ev:
            self.mouse_move(ev["x"], ev["y"])

    def mouse_button(self, button, down):
        down_msg, up_msg, flag, xbtn = BUTTON_MSGS.get(button, BUTTON_MSGS["left"])
        if down and self.fake_focus:
            self._post(WM_SETFOCUS, 0, 0)
        if down:
            self._buttons |= flag
        else:
            self._buttons &= ~flag
        x, y = self._pos or self._center()
        wparam = self._buttons | (xbtn << 16)
        self._post(down_msg if down else up_msg, wparam, point_lparam(x, y))

    def scroll(self, dx, dy):
        x, y = self._pos or self._center()
        pt = wintypes.POINT(x, y)
        _u.ClientToScreen(self.hwnd, ctypes.byref(pt))  # wheel messages use screen coords
        for amount, msg in ((dy, WM_MOUSEWHEEL), (dx, WM_MOUSEHWHEEL)):
            if amount:
                wparam = ((int(amount) * 120) & 0xFFFF) << 16 | self._buttons
                self._post(msg, wparam, point_lparam(pt.x, pt.y))
