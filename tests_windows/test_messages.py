"""Windows-only: check the background backend's messages reach a real window."""
import os
import sys
import time
import tkinter as tk
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@unittest.skipUnless(sys.platform == "win32", "Windows only")
class MessageBackendTest(unittest.TestCase):
    def test_keys_and_clicks_arrive(self):
        from ubimacro.background import MessageBackend
        from ubimacro.keys import make_key

        root = tk.Tk()
        root.geometry("300x200+50+50")
        got = []
        root.bind("<KeyPress>", lambda e: got.append(("down", e.keysym.lower())))
        root.bind("<KeyRelease>", lambda e: got.append(("up", e.keysym.lower())))
        root.bind("<ButtonPress-1>", lambda e: got.append(("click", e.x, e.y)))
        root.bind("<ButtonRelease-1>", lambda e: got.append(("release", e.x, e.y)))
        root.update()
        root.focus_force()
        root.update()
        be = MessageBackend(root.winfo_id(), fake_focus=False)
        self.assertTrue(be.alive())
        be.key(make_key("w", 0x57), True)
        be.key(make_key("w", 0x57), False)
        end = time.time() + 2
        while time.time() < end:
            root.update()
            time.sleep(0.02)
        root.destroy()
        print("received:", got)
        self.assertIn(("down", "w"), got)
        self.assertIn(("up", "w"), got)

    def test_click_messages_are_encoded_right(self):
        """Tk ignores posted clicks (it checks the real button state), so use a
        bare Win32 window that records every message it gets."""
        import ctypes
        from ctypes import wintypes

        from ubimacro.background import MessageBackend

        u = ctypes.WinDLL("user32")
        k = ctypes.WinDLL("kernel32")
        LRESULT = ctypes.c_ssize_t
        WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
        u.DefWindowProcW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
        u.DefWindowProcW.restype = LRESULT
        seen = []

        def proc(hwnd, msg, wp, lp):
            if 0x0200 <= msg <= 0x020E:
                seen.append((msg, wp & 0xFFFF, lp & 0xFFFF, (lp >> 16) & 0xFFFF))
            return u.DefWindowProcW(hwnd, msg, wp, lp)

        cb = WNDPROC(proc)

        class WNDCLASSW(ctypes.Structure):
            _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                        ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE),
                        ("hIcon", wintypes.HICON), ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                        ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]

        hinst = k.GetModuleHandleW(None)
        wc = WNDCLASSW(0, cb, 0, 0, hinst, None, None, None, None, "UbiMacroTestWnd")
        self.assertTrue(u.RegisterClassW(ctypes.byref(wc)))
        u.CreateWindowExW.restype = wintypes.HWND
        u.CreateWindowExW.argtypes = (wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                      ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HWND,
                                      wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID)
        hwnd = u.CreateWindowExW(0, "UbiMacroTestWnd", "test", 0x10CF0000, 100, 100, 400, 300,
                                 None, None, hinst, None)
        self.assertTrue(hwnd)

        be = MessageBackend(hwnd, fake_focus=True)
        be.prepare()
        be.move_to_event({"rx": 0.5, "ry": 0.25})
        be.mouse_button("left", True)
        be.mouse_button("left", False)
        be.mouse_button("right", True)
        be.mouse_button("right", False)

        msg = wintypes.MSG()
        end = time.time() + 1
        while time.time() < end:
            while u.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                u.TranslateMessage(ctypes.byref(msg))
                u.DispatchMessageW(ctypes.byref(msg))
            time.sleep(0.02)
        u.DestroyWindow(hwnd)
        print("seen:", [(hex(m), wp, x, y) for m, wp, x, y in seen])

        downs = [s for s in seen if s[0] == 0x0201]
        ups = [s for s in seen if s[0] == 0x0202]
        rdowns = [s for s in seen if s[0] == 0x0204]
        self.assertEqual(len(downs), 1)
        self.assertEqual(len(ups), 1)
        self.assertEqual(len(rdowns), 1)
        self.assertEqual(downs[0][1] & 0x1, 1)      # MK_LBUTTON held on the down message
        self.assertEqual(ups[0][1] & 0x1, 0)        # and released on the up
        x, y = downs[0][2], downs[0][3]
        self.assertTrue(150 <= x <= 250 and 40 <= y <= 90, (x, y))  # middle-top of the client area


if __name__ == "__main__":
    unittest.main()
