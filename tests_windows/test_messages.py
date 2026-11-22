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
        be.move_to_event({"rx": 0.5, "ry": 0.5})
        be.mouse_button("left", True)
        be.mouse_button("left", False)
        end = time.time() + 2
        while time.time() < end:
            root.update()
            time.sleep(0.02)
        root.destroy()
        print("received:", got)
        self.assertIn(("down", "w"), got)
        self.assertIn(("up", "w"), got)
        clicks = [g for g in got if g[0] == "click"]
        self.assertTrue(clicks)
        self.assertTrue(130 <= clicks[0][1] <= 170 and 80 <= clicks[0][2] <= 120, clicks)


if __name__ == "__main__":
    unittest.main()
