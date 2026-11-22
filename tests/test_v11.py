import os
import re
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ubimacro import macro  # noqa: E402
from ubimacro.i18n import STRINGS, Translator  # noqa: E402
from ubimacro.keys import make_key  # noqa: E402
from ubimacro.player import Player  # noqa: E402


def ev(t, action="down", k="w"):
    return {"t": t, "type": "key", "action": action, "key": make_key(k)}


class EditingTest(unittest.TestCase):
    def setUp(self):
        self.events = [ev(0.121), ev(0.5, "up"), ev(3.5, "down", "s"), ev(3.9, "up", "s")]

    def times(self, events):
        return [round(e["t"], 4) for e in events]

    def test_trim_start_removes_late_click_delay(self):
        out = macro.trim_start(self.events)
        self.assertEqual(self.times(out), [0.0, 0.379, 3.379, 3.779])
        self.assertEqual(self.events[0]["t"], 0.121)  # original untouched (for Undo)

    def test_set_gap_moves_following(self):
        out = macro.set_gap(self.events, 2, 0.5)  # pause before "s down" 3.0 -> 0.5
        self.assertEqual(self.times(out), [0.121, 0.5, 1.0, 1.4])

    def test_set_gap_zero_on_first_event(self):
        self.assertEqual(self.times(macro.set_gap(self.events, 0, 0))[0], 0.0)

    def test_set_time_alone_resorts(self):
        out = macro.set_time(self.events, 0, 4.0, move_following=False)
        self.assertEqual(self.times(out), [0.5, 3.5, 3.9, 4.0])
        self.assertEqual(out[-1]["action"], "down")

    def test_set_time_moving_following(self):
        out = macro.set_time(self.events, 1, 1.0)
        self.assertEqual(self.times(out), [0.121, 1.0, 4.0, 4.4])

    def test_cap_gaps(self):
        out = macro.cap_gaps(self.events, 1.0)
        self.assertEqual(self.times(out), [0.121, 0.5, 1.5, 1.9])

    def test_shift_and_delete(self):
        self.assertEqual(self.times(macro.shift(self.events, [0], -1)), [0.0, 0.5, 3.5, 3.9])
        self.assertEqual(len(macro.delete(self.events, [1, 2])), 2)

    def test_gaps(self):
        self.assertEqual([round(g, 3) for g in macro.gaps(self.events)], [0.121, 0.379, 3.0, 0.4])


class StopAfterTest(unittest.TestCase):
    def test_time_limit(self):
        done = threading.Event()
        res = {}
        p = Player(type("B", (), {"key": lambda *a: None, "mouse_move": lambda *a: None,
                                  "mouse_button": lambda *a: None, "scroll": lambda *a: None})(),
                   on_finish=lambda n, e, r: (res.update(n=n, r=r), done.set()))
        t0 = time.perf_counter()
        p.start([ev(0.0), ev(0.05, "up")], loops=0, loop_delay=0.05, stop_after=0.4)
        self.assertTrue(done.wait(3))
        took = time.perf_counter() - t0
        self.assertEqual(res["r"], "time_limit")
        self.assertGreater(res["n"], 1)
        self.assertLess(took, 0.7)


class I18nTest(unittest.TestCase):
    def test_same_keys_and_placeholders(self):
        en, trk = STRINGS["en"], STRINGS["tr"]
        self.assertEqual(set(en), set(trk))
        for k in en:
            self.assertEqual(set(re.findall(r"{(\w+)}", en[k])), set(re.findall(r"{(\w+)}", trk[k])), k)

    def test_every_key_used_in_app_exists(self):
        import glob

        root = os.path.join(os.path.dirname(__file__), "..", "ubimacro")
        used = set()
        for path in [os.path.join(root, "app.py")] + glob.glob(os.path.join(root, "ui", "*.py")):
            with open(path, encoding="utf-8") as f:
                used |= set(re.findall(r"""tr\(["']([a-z_0-9]+)["']""", f.read()))
        dynamic = {"tab_home", "tab_library", "tab_events", "tab_settings", "ev_key_down", "ev_key_up",
                   "ev_click_down", "ev_click_up", "btn_left", "btn_right", "btn_middle", "btn_x1", "btn_x2",
                   "lane_left", "lane_right", "lane_middle", "lane_x1", "lane_x2", "toast_time_limit_macro",
                   "toast_time_limit_clicker", "hk_record", "hk_play", "hk_clicker", "hk_mini", "hk_stopall",
                   "sub_ready_click", "sub_ready_hold"}
        missing = {k for k in used | dynamic if k not in STRINGS["en"] and not k.endswith("_")}
        self.assertEqual(missing, set())

    def test_formats_every_string(self):
        for lang in STRINGS:
            t = Translator(lang)
            for k, v in STRINGS[lang].items():
                names = set(re.findall(r"{(\w+)}", v))
                t(k, **{n: "1" for n in names})

    def test_turkish_upper(self):
        t = Translator("tr")
        self.assertEqual(t.upper("seçili"), "SEÇİLİ")
        self.assertEqual(t.upper("ışık"), "IŞIK")
        self.assertEqual(Translator("en").upper("time"), "TIME")


if __name__ == "__main__":
    unittest.main()
