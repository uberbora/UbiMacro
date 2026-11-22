"""Input backends used for playback.

On Windows we call SendInput directly and send *hardware scancodes*. Roblox
(and many other games) read raw/scancode input and often ignore the
virtual-key events that most Python automation libraries send, so this is
what makes the playback actually register in-game.

Elsewhere we fall back to pynput's controllers.
"""

import sys

from .keys import EXTENDED_VKS, name_to_vk


def get_backend():
    if sys.platform == "win32":
        return WindowsBackend()
    return PynputBackend()


class PynputBackend:
    def __init__(self):
        from pynput import keyboard, mouse

        self._kb = keyboard.Controller()
        self._mouse = mouse.Controller()
        self._Key = keyboard.Key
        self._KeyCode = keyboard.KeyCode
        self._Button = mouse.Button

    def _to_key(self, d):
        name = d.get("name")
        if name in self._Key.__members__:
            return self._Key[name]
        if d.get("char"):
            return self._KeyCode.from_char(d["char"])
        if d.get("vk") is not None:
            return self._KeyCode.from_vk(d["vk"])
        if name and len(name) == 1:
            return self._KeyCode.from_char(name)
        return None

    def key(self, d, down):
        k = self._to_key(d)
        if k is None:
            return
        (self._kb.press if down else self._kb.release)(k)

    def mouse_move(self, x, y):
        self._mouse.position = (x, y)

    def mouse_button(self, button, down):
        b = getattr(self._Button, button, self._Button.left)
        (self._mouse.press if down else self._mouse.release)(b)

    def scroll(self, dx, dy):
        self._mouse.scroll(dx, dy)


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    ULONG_PTR = ctypes.c_size_t

    INPUT_MOUSE = 0
    INPUT_KEYBOARD = 1
    KEYEVENTF_EXTENDEDKEY = 0x0001
    KEYEVENTF_KEYUP = 0x0002
    KEYEVENTF_SCANCODE = 0x0008
    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_ABSOLUTE = 0x8000
    MOUSEEVENTF_VIRTUALDESK = 0x4000
    MOUSEEVENTF_WHEEL = 0x0800
    MOUSEEVENTF_HWHEEL = 0x1000
    BUTTON_FLAGS = {
        "left": (0x0002, 0x0004, 0),
        "right": (0x0008, 0x0010, 0),
        "middle": (0x0020, 0x0040, 0),
        "x1": (0x0080, 0x0100, 1),
        "x2": (0x0080, 0x0100, 2),
    }

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]

    class _INPUTUNION(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]

    class INPUT(ctypes.Structure):
        _anonymous_ = ("u",)
        _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]

    _user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
    _user32.SendInput.restype = wintypes.UINT
    _user32.MapVirtualKeyW.argtypes = (wintypes.UINT, wintypes.UINT)
    _user32.MapVirtualKeyW.restype = wintypes.UINT


class WindowsBackend:
    def __init__(self):
        try:  # 1 ms timer resolution so playback timing is tight
            ctypes.WinDLL("winmm").timeBeginPeriod(1)
        except Exception:
            pass

    def _send(self, inp):
        _user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    def key(self, d, down):
        vk = name_to_vk(d)
        if vk is None:
            return
        up_flag = 0 if down else KEYEVENTF_KEYUP
        scan = _user32.MapVirtualKeyW(vk, 0)  # MAPVK_VK_TO_VSC
        inp = INPUT(type=INPUT_KEYBOARD)
        if scan:
            flags = KEYEVENTF_SCANCODE | up_flag
            if vk in EXTENDED_VKS:
                flags |= KEYEVENTF_EXTENDEDKEY
            inp.ki = KEYBDINPUT(0, scan, flags, 0, 0)
        else:  # no scancode (e.g. media keys): send the virtual key
            inp.ki = KEYBDINPUT(vk, 0, up_flag, 0, 0)
        self._send(inp)

    def mouse_move(self, x, y):
        gsm = _user32.GetSystemMetrics
        vx, vy, vw, vh = gsm(76), gsm(77), gsm(78), gsm(79)  # virtual desktop
        nx = int(round((x - vx) * 65535 / max(vw - 1, 1)))
        ny = int(round((y - vy) * 65535 / max(vh - 1, 1)))
        inp = INPUT(type=INPUT_MOUSE)
        inp.mi = MOUSEINPUT(nx, ny, 0, MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK, 0, 0)
        self._send(inp)

    def mouse_button(self, button, down):
        down_f, up_f, data = BUTTON_FLAGS.get(button, BUTTON_FLAGS["left"])
        inp = INPUT(type=INPUT_MOUSE)
        inp.mi = MOUSEINPUT(0, 0, data, down_f if down else up_f, 0, 0)
        self._send(inp)

    def scroll(self, dx, dy):
        for amount, flag in ((dy, MOUSEEVENTF_WHEEL), (dx, MOUSEEVENTF_HWHEEL)):
            if amount:
                inp = INPUT(type=INPUT_MOUSE)
                inp.mi = MOUSEINPUT(0, 0, (int(amount) * 120) & 0xFFFFFFFF, flag, 0, 0)
                self._send(inp)
