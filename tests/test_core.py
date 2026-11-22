import os
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ubimacro import macro  # noqa: E402
from ubimacro.keys import display_name, keys_match, make_key, name_to_vk  # noqa: E402
from ubimacro.player import Player  # noqa: E402
from ubimacro.recorder import Recorder  # noqa: E402


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class FakeBackend:
    def __init__(self):
        self.calls = []
        self.lock = threading.Lock()

    def key(self, d, down):
        with self.lock:
            self.calls.append(("key", d["name"], down, time.perf_counter()))

    def mouse_move(self, x, y):
        with self.lock:
            self.calls.append(("move", x, y, time.perf_counter()))

    def mouse_button(self, b, down):
        with self.lock:
            self.calls.append(("btn", b, down, time.perf_counter()))

    def scroll(self, dx, dy):
        with self.lock:
            self.calls.append(("scroll", dx, dy, time.perf_counter()))


class Btn:
    def __init__(self, name):
        self.name = name


class KeysTest(unittest.TestCase):
    def test_vk_lookup(self):
        self.assertEqual(name_to_vk({"name": "w"}), 0x57)
        self.assertEqual(name_to_vk({"name": "f8"}), 0x77)
        self.assertEqual(name_to_vk({"name": "space"}), 0x20)

    def test_match_by_name_across_platforms(self):
        self.assertTrue(keys_match(make_key("f8"), {"name": "f8", "vk": 65477}))
        self.assertFalse(keys_match(make_key("f8"), make_key("f6")))

    def test_display(self):
        self.assertEqual(display_name(make_key("f8")), "F8")
        self.assertEqual(display_name(make_key("space")), "Space")


class RecorderTest(unittest.TestCase):
    def test_records_and_dedupes_autorepeat(self):
        clk = FakeClock()
        r = Recorder(clock=clk)
        r.start(use_mouse_listener=False)
        w = make_key("w")
        clk.t = 0.5
        r.key(w, True)
        clk.t = 0.6
        r.key(w, True)  # auto-repeat
        clk.t = 0.7
        r.key(w, True)
        clk.t = 1.5
        r.key(w, False)
        clk.t = 2.0
        r.on_click(100, 200, Btn("left"), True)
        clk.t = 2.1
        r.on_click(100, 200, Btn("left"), False)
        ev = r.stop()
        self.assertEqual([(e["type"], e.get("action")) for e in ev],
                         [("key", "down"), ("key", "up"), ("click", "down"), ("click", "up")])
        self.assertAlmostEqual(ev[1]["t"], 1.5)

    def test_closes_held_keys_and_trims_stop_click(self):
        clk = FakeClock()
        r = Recorder(clock=clk)
        r.start(use_mouse_listener=False)
        clk.t = 1.0
        r.key(make_key("a"), True)
        clk.t = 5.0
        r.on_click(10, 10, Btn("left"), True)   # click on the Stop button
        clk.t = 5.1
        r.on_click(10, 10, Btn("left"), False)
        clk.t = 5.2
        ev = r.stop(trim_trailing_clicks=True)
        self.assertEqual(len(ev), 2)
        self.assertEqual(ev[-1]["action"], "up")
        self.assertEqual(ev[-1]["key"]["name"], "a")

    def test_ignores_injected_and_moves_off(self):
        r = Recorder(clock=FakeClock())
        r.start(use_mouse_listener=False)
        r.on_click(1, 1, Btn("left"), True, True)
        r.on_move(5, 5)
        self.assertEqual(r.stop(), [])


class PlayerTest(unittest.TestCase):
    def _events(self):
        return [
            {"t": 0.00, "type": "key", "action": "down", "key": make_key("w")},
            {"t": 0.10, "type": "key", "action": "up", "key": make_key("w")},
            {"t": 0.15, "type": "click", "action": "down", "button": "left", "x": 5, "y": 6},
            {"t": 0.20, "type": "click", "action": "up", "button": "left", "x": 5, "y": 6},
        ]

    def test_plays_n_loops_with_timing(self):
        be = FakeBackend()
        done = threading.Event()
        result = {}
        p = Player(be, on_finish=lambda n, e, r: (result.update(n=n, e=e, r=r), done.set()))
        t0 = time.perf_counter()
        p.start(self._events(), loops=2, loop_delay=0.1)
        self.assertTrue(done.wait(3))
        self.assertEqual(result, {"n": 2, "e": None, "r": "done"})
        keys = [c for c in be.calls if c[0] == "key"]
        self.assertEqual(len(keys), 4)
        gap = keys[1][3] - keys[0][3]
        self.assertGreater(gap, 0.08)
        self.assertLess(gap, 0.2)
        # 2 loops of 0.2s + 0.1s delay
        self.assertGreater(be.calls[-1][3] - t0, 0.45)
        self.assertIn(("move", 5, 6), [c[:3] for c in be.calls])

    def test_stop_releases_held_keys(self):
        be = FakeBackend()
        done = threading.Event()
        events = [
            {"t": 0.0, "type": "key", "action": "down", "key": make_key("w")},
            {"t": 10.0, "type": "key", "action": "up", "key": make_key("w")},
        ]
        p = Player(be, on_finish=lambda n, e, r: done.set())
        p.start(events, loops=0)
        time.sleep(0.1)
        p.stop()
        self.assertTrue(done.wait(2))
        self.assertEqual([c[:3] for c in be.calls], [("key", "w", True), ("key", "w", False)])

    def test_speed(self):
        be = FakeBackend()
        done = threading.Event()
        p = Player(be, on_finish=lambda n, e, r: done.set())
        t0 = time.perf_counter()
        p.start([{"t": 0.4, "type": "key", "action": "down", "key": make_key("a")},
                 {"t": 0.4, "type": "key", "action": "up", "key": make_key("a")}], loops=1, speed=4)
        self.assertTrue(done.wait(2))
        self.assertLess(be.calls[0][3] - t0, 0.2)


class MacroFileTest(unittest.TestCase):
    def test_roundtrip_and_preset(self):
        ev = macro.anti_afk_preset()
        self.assertTrue(all(e["type"] == "key" for e in ev))
        self.assertEqual(len(ev), 6)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "m.json")
            macro.save(p, ev, {"loops": 3})
            ev2, s = macro.load(p)
        self.assertEqual(ev, ev2)
        self.assertEqual(s, {"loops": 3})


if __name__ == "__main__":
    unittest.main()
