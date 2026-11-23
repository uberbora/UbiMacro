import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ubimacro import notify, robloxlog  # noqa: E402
from ubimacro.history import History  # noqa: E402
from ubimacro.i18n import STRINGS  # noqa: E402

# real lines as Roblox writes them (from public logs)
SERVER_KICK = [
    "2022-09-07T23:50:53.214Z,2.214371,254c,7 [FLog::Network] Disconnect reason received: 280",
    "2022-09-07T23:50:53.214Z,2.214371,254c,7 [FLog::Network] Disconnection Notification. Reason: 280",
    "2022-09-07T23:50:53.226Z,2.226390,17d8,7 [FLog::Network] Client has been disconnected with reason: "
    "Disconnected from game, please reconnect",
]
YOU_LEFT = [
    "2024-01-26T13:45:13.201Z,41.201645,30f4,7 [FLog::Network] Time to disconnect replication data: 0.173700",
    "2024-01-26T13:45:13.202Z,41.202641,30f4,7 [FLog::Network] Sending disconnect with reason: 285",
    "2024-01-26T13:45:13.356Z,41.356415,30f4,7 [FLog::Network] NetworkClient:Remove",
]
LOST = [
    "[FLog::Network] AckTimeout: Last Packet received time: 20004 ms",
    "[FLog::Network] Connection lost - Cannot contact server/client",
]


class RobloxLogTest(unittest.TestCase):
    def test_parse(self):
        ev = robloxlog.merge(robloxlog.parse_lines(SERVER_KICK))
        self.assertEqual(ev, {"code": "280", "text": "Disconnected from game, please reconnect"})
        self.assertIsNone(robloxlog.merge(robloxlog.parse_lines(YOU_LEFT)))  # leaving on purpose isn't an alert
        self.assertEqual(robloxlog.merge(robloxlog.parse_lines(LOST))["code"], "277")

    def test_watcher_reads_only_new_lines_and_follows_new_logs(self):
        with tempfile.TemporaryDirectory() as d:
            old = os.path.join(d, "0.1_20261123T000000Z_Player_AAA_last.log")
            with open(old, "w") as f:
                f.write("\n".join(SERVER_KICK) + "\n")  # an old disconnect, before we started
            w = robloxlog.LogWatcher(d)
            self.assertTrue(w.start())
            self.assertIsNone(w.poll())
            with open(old, "a") as f:
                f.write("\n".join(YOU_LEFT) + "\n")
            self.assertIsNone(w.poll())
            with open(old, "a") as f:
                f.write(SERVER_KICK[0] + "\n" + SERVER_KICK[2][:40])  # second line half-written
            self.assertEqual(w.poll(), {"code": "280", "text": None})
            with open(old, "a") as f:
                f.write(SERVER_KICK[2][40:] + "\n")
            self.assertEqual(w.poll()["text"], "Disconnected from game, please reconnect")
            time.sleep(0.05)
            new = os.path.join(d, "0.1_20261123T010000Z_Player_BBB_last.log")
            with open(new, "w") as f:
                f.write(LOST[1] + "\n")
            os.utime(new, (time.time() + 5, time.time() + 5))
            self.assertEqual(w.poll()["code"], "277")

    def test_no_logs_folder(self):
        w = robloxlog.LogWatcher(os.path.join(tempfile.gettempdir(), "no-such-roblox-logs"))
        self.assertFalse(w.start())
        self.assertIsNone(w.poll())

    def test_known_codes_have_text(self):
        for key in set(robloxlog.KNOWN.values()):
            self.assertIn(key, STRINGS["en"])
            self.assertIn(key, STRINGS["tr"])


class AlertTest(unittest.TestCase):
    def test_fill(self):
        self.assertEqual(notify.fill("**{macro}** ran {time} {nope} {", {"macro": "X", "time": "2 h"}),
                         "**X** ran 2 h {nope} {")

    def test_payload_with_ping(self):
        p = notify.discord_payload("body", "Title", 0xB3361B, " 1234 5678 ")
        self.assertEqual(p["content"], "<@12345678>")
        self.assertEqual(p["allowed_mentions"], {"users": ["12345678"]})
        self.assertEqual(p["embeds"][0]["color"], 0xB3361B)
        self.assertNotIn("content", notify.discord_payload("body", "Title", 1, None))
        self.assertEqual(notify.discord_payload("b", "T", 1, None)["allowed_mentions"], {"parse": []})

    def test_every_alert_has_text(self):
        for k in notify.ALERTS:
            for lang in ("en", "tr"):
                for prefix in ("alert_title_", "alert_sub_", "alert_text_"):
                    self.assertIn(prefix + k, STRINGS[lang])
            filled = notify.fill(STRINGS["en"]["alert_text_" + k],
                                 {p: "x" for p in notify.PLACEHOLDERS})
            self.assertNotIn("{", filled, k)

    def test_defaults(self):
        d = notify.default_alerts()
        self.assertEqual(set(d), set(notify.ALERTS))
        self.assertTrue(d["closed"]["on"] and d["closed"]["ping"])
        self.assertFalse(d["status"]["on"])


class HistoryTest(unittest.TestCase):
    def test_add_limit_clear(self):
        with tempfile.TemporaryDirectory() as d:
            h = History(os.path.join(d, "history.json"))
            self.assertEqual(h.entries(), [])
            for i in range(105):
                h.add(f"Run {i}", "macro", time.time(), 9000, loops=i, clicks=2 * i, end="stopped")
            e = h.entries()
            self.assertEqual(len(e), 100)
            self.assertEqual(e[0]["name"], "Run 104")  # newest first
            self.assertEqual(e[0]["seconds"], 9000)
            self.assertGreater(h.total_today(), 0)
            h.clear()
            self.assertEqual(h.entries(), [])

    def test_broken_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "history.json")
            with open(p, "w") as f:
                f.write("{not json")
            self.assertEqual(History(p).entries(), [])


if __name__ == "__main__":
    unittest.main()
