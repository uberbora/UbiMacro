import os
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ubimacro import macro, notify  # noqa: E402
from ubimacro.clicker import Clicker  # noqa: E402
from ubimacro.keys import make_key  # noqa: E402
from ubimacro.library import Library, ago  # noqa: E402
from ubimacro.player import Player  # noqa: E402


class Rec:
    def __init__(self):
        self.calls = []
        self.lock = threading.Lock()

    def _add(self, *c):
        with self.lock:
            self.calls.append(c + (time.perf_counter(),))

    def key(self, d, down):
        self._add("key", d["name"], down)

    def mouse_move(self, x, y):
        self._add("move", x, y)

    def mouse_button(self, b, down):
        self._add("btn", b, down)

    def scroll(self, dx, dy):
        self._add("scroll", dx, dy)


def kev(t, action, k="w"):
    return {"t": t, "type": "key", "action": action, "key": make_key(k)}


def cev(t, action, b="left"):
    return {"t": t, "type": "click", "action": action, "button": b, "x": 1, "y": 2}


class ClickerTest(unittest.TestCase):
    def test_speed_and_release(self):
        be, done, res = Rec(), threading.Event(), {}
        c = Clicker(be, on_finish=lambda n, e, r: (res.update(n=n, r=r), done.set()))
        c.start(cps=20, stop_after=0.5)
        self.assertTrue(done.wait(3))
        self.assertEqual(res["r"], "time_limit")
        self.assertTrue(7 <= res["n"] <= 12, res)
        downs = [x for x in be.calls if x[0] == "btn" and x[2]]
        ups = [x for x in be.calls if x[0] == "btn" and not x[2]]
        self.assertEqual(len(downs), len(ups))

    def test_fixed_point_and_right_button(self):
        be, done = Rec(), threading.Event()
        c = Clicker(be, on_finish=lambda *a: done.set())
        c.start(cps=10, button="right", point=(50, 60), stop_after=0.25)
        self.assertTrue(done.wait(3))
        self.assertIn(("move", 50, 60), [x[:3] for x in be.calls])
        self.assertTrue(all(x[1] == "right" for x in be.calls if x[0] == "btn"))

    def test_pause_stops_clicking(self):
        be, done, count = Rec(), threading.Event(), []
        c = Clicker(be, on_click=lambda: count.append(1), on_finish=lambda *a: done.set())
        c.start(cps=40)
        time.sleep(0.2)
        c.set_paused(True)
        time.sleep(0.1)
        n = len(count)
        time.sleep(0.3)
        self.assertLessEqual(len(count) - n, 1)
        c.set_paused(False)
        time.sleep(0.2)
        self.assertGreater(len(count), n + 2)
        c.stop()
        self.assertTrue(done.wait(2))


class PlayerPauseTest(unittest.TestCase):
    def test_pause_releases_keys_and_restarts_loop(self):
        be, done, res = Rec(), threading.Event(), {}
        p = Player(be, on_finish=lambda n, e, r: (res.update(n=n, r=r), done.set()))
        p.start([kev(0, "down"), kev(0.5, "up")], loops=1)
        time.sleep(0.15)
        p.set_paused(True)            # W is held right now
        time.sleep(0.25)
        released = [x[:3] for x in be.calls]
        self.assertEqual(released, [("key", "w", True), ("key", "w", False)])
        p.set_paused(False)
        self.assertTrue(done.wait(3))
        self.assertEqual(res, {"n": 1, "r": "done"})
        # the loop ran again from the top after the pause
        self.assertEqual([x[2] for x in be.calls], [True, False, True, False])

    def test_counts_clicks(self):
        clicks, done = [], threading.Event()
        p = Player(Rec(), on_click=lambda: clicks.append(1), on_finish=lambda *a: done.set())
        p.start([cev(0, "down"), cev(0.01, "up"), cev(0.02, "down"), cev(0.03, "up")], loops=2)
        self.assertTrue(done.wait(3))
        self.assertEqual(len(clicks), 4)

    def test_stop_after_while_paused(self):
        done, res = threading.Event(), {}
        p = Player(Rec(), on_finish=lambda n, e, r: (res.update(r=r), done.set()))
        p.start([kev(0, "down"), kev(5, "up")], stop_after=0.3)
        p.set_paused(True)
        self.assertTrue(done.wait(3))
        self.assertEqual(res["r"], "time_limit")


class TimelineModelTest(unittest.TestCase):
    def setUp(self):
        self.ev = [kev(0, "down"), cev(0.5, "down"), cev(0.55, "up"), kev(1.0, "up"),
                   kev(1.2, "down", "s"), kev(2.0, "up", "s"),
                   {"t": 2.5, "type": "scroll", "dx": 0, "dy": 1, "x": 0, "y": 0}]

    def test_pairs(self):
        bars, singles, lanes = macro.pairs(self.ev)
        self.assertEqual([(b[1], b[2]) for b in bars], [(1, 2), (0, 3), (4, 5)])
        self.assertEqual(singles, [6])
        self.assertEqual(len(lanes), 3)
        self.assertEqual(macro.partner(self.ev, 0), 3)
        self.assertEqual(macro.lane_label(lanes[0], self.ev), "W")

    def test_move_bar_keeps_length(self):
        out = macro.move_bar(self.ev, 4, 5, 0.5)
        s = [e["t"] for e in out if e.get("key", {}).get("name") == "s"]
        self.assertEqual(s, [1.7, 2.5])
        out = macro.move_bar(self.ev, 0, 3, -5)  # can't go below 0
        self.assertEqual(min(e["t"] for e in out), 0.0)

    def test_resize_never_crosses(self):
        out = macro.resize_bar(self.ev, 0, 3, -5, "end")
        w = [e["t"] for e in out if e.get("key", {}).get("name") == "w"]
        self.assertEqual(w, [0.0, 0.01])
        out = macro.resize_bar(self.ev, 4, 5, 5, "start")
        s = [e["t"] for e in out if e.get("key", {}).get("name") == "s"]
        self.assertEqual(s, [1.99, 2.0])

    def test_insert_take(self):
        take = [kev(0.3, "down", "a"), kev(0.8, "up", "a")]
        out = macro.insert_take(self.ev, 1.0, take)
        a = [e["t"] for e in out if e.get("key", {}).get("name") == "a"]
        self.assertEqual(a, [1.05, 1.55])
        s = [e["t"] for e in out if e.get("key", {}).get("name") == "s"]
        self.assertEqual(s, [1.75, 2.55])  # moved by 0.5 + 0.05

    def test_slice_from_keeps_held_keys(self):
        out = macro.slice_from(self.ev, 0.7)
        self.assertEqual(out[0]["t"], 0.0)
        self.assertEqual((out[0]["key"]["name"], out[0]["action"]), ("w", "down"))
        self.assertEqual([round(e["t"], 3) for e in out], [0.0, 0.3, 0.5, 1.3, 1.8])


class LibraryTest(unittest.TestCase):
    def test_crud(self):
        with tempfile.TemporaryDirectory() as d:
            lib = Library(d)
            a = lib.create("Punch bag", [cev(0, "down"), cev(0.1, "up")], {"loops": 0})
            b = lib.create("Punch bag", [kev(0, "down"), kev(1, "up")])
            self.assertNotEqual(a, b)
            lib.set_hotkey(a, make_key("f1"))
            lib.set_favourite(b, True)
            lib.rename(b, "Farm route")
            ents = lib.entries()
            self.assertEqual([e.name for e in ents], ["Farm route", "Punch bag"])  # favourite first
            self.assertEqual(ents[1].hotkey["name"], "f1")
            self.assertEqual(ents[1].initials(), "PB")
            c = lib.duplicate(a, "kopya")
            self.assertIsNone(lib.get(c).hotkey)
            self.assertIn("kopya", lib.get(c).name)
            lib.save_events(a, [cev(0, "down"), cev(0.2, "up"), cev(0.3, "down"), cev(0.4, "up")])
            ev, settings, meta = lib.load(a)
            self.assertEqual((len(ev), settings, meta["name"]), (4, {"loops": 0}, "Punch bag"))
            out = os.path.join(d, "..", "exported-ubimacro-test.json")
            lib.export(a, out)
            imported = lib.import_file(out)
            os.remove(out)
            self.assertEqual(lib.get(imported).name, "Punch bag 2")
            self.assertIsNone(lib.get(imported).hotkey)
            lib.delete(c)
            self.assertEqual(len(lib.entries()), 3)
            with self.assertRaises(ValueError):
                lib.load("../x")

    def test_old_files_show_up(self):
        with tempfile.TemporaryDirectory() as d:
            macro.save(os.path.join(d, "my-afk.json"), [kev(0, "down"), kev(1, "up")])
            ent = Library(d).entries()[0]
            self.assertEqual((ent.id, ent.name, ent.count), ("my-afk", "My afk", 2))

    def test_ago(self):
        words = {"never": "never", "today": "today", "yesterday": "yesterday", "days": "{n} days ago"}
        self.assertEqual(ago(time.time(), words), "today")
        self.assertEqual(ago(time.time() - 86400 * 3, words), "3 days ago")
        self.assertEqual(ago(0, words), "never")


class NotifyTest(unittest.TestCase):
    def test_versions(self):
        self.assertTrue(notify.is_newer("v1.3.0", "1.2.9"))
        self.assertFalse(notify.is_newer("v1.3.0", "1.3.0"))
        self.assertTrue(notify.is_newer("v2.0", "1.9.9"))

    def test_webhook(self):
        self.assertTrue(notify.is_webhook("https://discord.com/api/webhooks/1/abc"))
        self.assertFalse(notify.is_webhook("http://example.com"))
        self.assertEqual(notify.discord_payload("x" * 3000)["content"], "x" * 1900)


if __name__ == "__main__":
    unittest.main()
