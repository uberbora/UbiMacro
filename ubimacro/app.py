"""UbiMacro's controller: state, hotkeys, recording, playback, the
auto-clicker, pausing, alerts, stats and the macro library. The screens live
in ubimacro/ui/ and call into this."""

import json
import os
import queue
import subprocess
import sys
import time
import tkinter as tk
import webbrowser
from datetime import date
from tkinter import filedialog, messagebox

import customtkinter as ctk

from . import __version__, macro, notify
from . import theme as th
from .clicker import Clicker
from .i18n import tr
from .keys import display_name, key_to_dict, keys_match, make_key
from .history import History
from .library import Library
from .player import Player
from .recorder import Recorder
from .theme import C
from .robloxlog import KNOWN as DC_KNOWN, LogWatcher
from .winfocus import find_window, focus_game, game_in_front, system_language, window_exists

IS_WINDOWS = sys.platform == "win32"
PAUSE_SUPPORTED = IS_WINDOWS  # needs pynput's "injected" flag to tell your input from ours
CPS_STEPS = [1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40, 50]
APP_HOTKEYS = ("record", "play", "clicker", "mini", "stopall")

DEFAULTS = {
    "lang": None, "theme": "dark", "mode": "macro", "active_macro": None,
    "record_hotkey": make_key("f8"), "play_hotkey": make_key("f6"), "clicker_hotkey": make_key("f7"),
    "mini_hotkey": make_key("f9"), "stopall_hotkey": make_key("end"),
    # playback
    "loops": 0, "speed": 1.0, "loop_delay": 0.0, "humanize": 0, "stop_after": 0.0,
    "move_to_clicks": True, "focus_game": True,
    # recording
    "record_moves": False, "auto_trim": True, "countdown": 3, "cap_gap": 2.0,
    # auto-clicker
    "cps": 12, "click_button": "left", "click_mode": "toggle", "click_where": "mouse", "click_point": None,
    "click_vary": True,
    # safety
    "pause_on_input": True, "resume_after": 5, "notify_closed": True, "only_front": False,
    # notifications
    "sounds": True, "webhook": "", "discord_user": "", "alerts": None,
    "status_every": 30, "paused_after": 10,
    # window
    "topmost": True, "start_mini": False, "close_to_tray": False, "check_updates": True,
    "today": {"day": "", "seconds": 0.0},
}


def config_dir():
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    path = os.path.join(base, "UbiMacro")
    os.makedirs(os.path.join(path, "macros"), exist_ok=True)
    return path


def fmt_clock(seconds):
    seconds = int(max(0, seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def fmt_length(seconds):
    if seconds < 60:
        return tr("secs", s=f"{seconds:.1f}")
    m, s = divmod(int(seconds), 60)
    if m < 60:
        return tr("min_sec", m=m, s=s) if s else tr("mins", m=m)
    h, m = divmod(m, 60)
    return tr("hour_min", h=h, m=m) if m else tr("hours", h=h)


def fmt_int(n):
    return f"{int(n):,}".replace(",", "." if tr.lang == "tr" else ",")


def num(value, default, cast=float, lo=None, hi=None):
    try:
        v = cast(str(value).replace(",", ".").strip())
    except (ValueError, TypeError):
        return default
    if lo is not None:
        v = max(lo, v)
    if hi is not None:
        v = min(hi, v)
    return v


class App:
    # ================================================================ setup
    def __init__(self, root, backend):
        self.root = root
        self.backend = backend
        self.q = queue.Queue()
        self.cfg_dir = config_dir()
        self.settings_path = os.path.join(self.cfg_dir, "settings.json")
        self.settings = self._load_settings()
        tr.set_lang(self.settings["lang"])
        ctk.set_appearance_mode(self.settings["theme"])
        self.library = Library(os.path.join(self.cfg_dir, "macros"))
        self.history = History(os.path.join(self.cfg_dir, "history.json"))
        self._migrate_last_macro()

        self.events, self.active, self.undo_stack = [], None, []
        self.state = "idle"          # idle / countdown / recording / playing / clicking
        self.paused = False
        self.pause_reason = None
        self.countdown_text = None
        self.countdown_sub = None
        self.page = "home"
        self.capturing = None        # ("app", "record") / ("macro", id)
        self._keys_down = set()
        self._countdown_job = None
        self._countdown_then = None
        self._countdown_left = 0
        self._take_at = None         # "record from here"
        self._run = {"started": 0.0, "loops": 0, "total": 0, "clicks": 0, "name": "", "kind": "macro",
                     "ended": True}
        self._log_watch = None
        self._last_status = 0.0
        self._paused_since = None
        self._paused_alerted = False
        self._last_input = 0.0
        self._mouse_pos = None
        self._watch_hwnd = None
        self._last_front_check = 0.0
        self._front_ok = True
        self._last_watch = 0.0
        self._last_tick = time.time()
        self._last_settings_save = time.time()
        self._mode_seen = ctk.get_appearance_mode()
        self.update_info = None
        self._macro_hotkeys = {}

        self.recorder = Recorder()
        self.player = Player(
            backend,
            on_progress=lambda n, total: self.q.put(("progress", n, total)),
            on_finish=lambda done, err, reason: self.q.put(("finished", done, err, reason)),
            on_click=self._count_click)
        self.clicker = Clicker(backend, on_click=self._count_click,
                               on_finish=lambda n, err, reason: self.q.put(("clicker_done", n, err, reason)))

        self._load_active(self.settings.get("active_macro"))
        root.configure(fg_color=C["bg"])
        root.minsize(470, 660)
        root.geometry("500x840")
        root.title("UbiMacro")
        root.bind_all("<Control-z>", lambda e: self.undo())
        from .ui.shell import Shell
        from .ui.tray import Tray

        self.tray = Tray(self)
        self.ui = Shell(self)
        self.ui.build()
        self._refresh_macro_hotkeys()
        self._start_listeners()
        root.protocol("WM_DELETE_WINDOW", self.on_close_request)
        if self.settings["check_updates"]:
            notify.check_update(__version__, lambda tag, url: self.q.put(("update", tag, url, False)))
        if self.settings["start_mini"]:
            root.after(300, self.ui.show_mini)
        root.after(50, self._poll)

    def _load_settings(self):
        s = json.loads(json.dumps(DEFAULTS))
        try:
            with open(self.settings_path, "r", encoding="utf-8") as f:
                saved = json.load(f)
            for k in ("background", "bg_window", "fake_focus"):  # 1.2 leftovers
                saved.pop(k, None)
            s.update(saved)
        except (OSError, ValueError):
            pass
        if s.get("lang") not in ("en", "tr"):
            s["lang"] = system_language()
        if s.get("theme") not in ("system", "light", "dark"):
            s["theme"] = "dark"
        if s.get("mode") not in ("macro", "clicker"):
            s["mode"] = "macro"
        legacy = s.pop("notify_finished", None)  # 1.3 had one switch for "finished"
        alerts = notify.default_alerts()
        if isinstance(s.get("alerts"), dict):
            for k, v in s["alerts"].items():
                if k in alerts and isinstance(v, dict):
                    alerts[k].update({kk: v[kk] for kk in ("on", "ping", "text") if kk in v})
        elif legacy is not None:
            alerts["finished"]["on"] = bool(legacy)
        s["alerts"] = alerts
        return s

    def save_settings(self):
        try:
            tmp = self.settings_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=1, ensure_ascii=False)
            os.replace(tmp, self.settings_path)
        except OSError:
            pass

    def set_setting(self, key, value, save=True):
        self.settings[key] = value
        if save:
            self.save_settings()

    def _migrate_last_macro(self):
        """1.0–1.2 kept one macro in last_macro.json: bring it into the library."""
        old = os.path.join(self.cfg_dir, "last_macro.json")
        if os.path.exists(old) and not self.library.entries():
            try:
                events, _s = macro.load(old)
                if events:
                    mid = self.library.create(tr("my_macro"), events)
                    self.settings["active_macro"] = mid
            except (OSError, ValueError):
                pass
        if os.path.exists(old):
            try:
                os.replace(old, old + ".old")
            except OSError:
                pass

    # ================================================================ active macro
    def _load_active(self, mid):
        entries = self.library.entries()
        ids = [e.id for e in entries]
        if mid not in ids:
            mid = ids[0] if ids else None
        self.active = next((e for e in entries if e.id == mid), None)
        self.events = []
        if mid:
            try:
                self.events, _s, _m = self.library.load(mid)
            except (OSError, ValueError):
                self.events = []
        self.undo_stack = []
        self.settings["active_macro"] = mid

    def set_active(self, mid, toast=True):
        if self.state in ("recording", "playing", "countdown"):
            self.show_toast(tr("toast_busy"))
            return
        self._load_active(mid)
        self.save_settings()
        self.ui.refresh_all()
        if toast and self.active:
            self.show_toast(tr("toast_active", name=self.active.name))

    def replace_events(self, events, undoable=True):
        if not self.active:
            return
        if undoable:
            self.undo_stack.append(self.events)
            del self.undo_stack[:-50]
        self.events = events
        try:
            self.library.save_events(self.active.id, events)
            self.active = self.library.get(self.active.id) or self.active
        except (OSError, ValueError) as e:
            messagebox.showerror("UbiMacro", tr("err_save", err=e))
        self.ui.refresh_events()

    def undo(self):
        if isinstance(self.root.focus_get(), tk.Entry):
            return
        if not self._editable():
            return
        if not self.undo_stack:
            self.show_toast(tr("toast_nothing_undo"))
            return
        self.replace_events(self.undo_stack.pop(), undoable=False)
        self.show_toast(tr("toast_undone"))

    def _editable(self):
        if self.state != "idle":
            self.show_toast(tr("toast_busy"))
            return False
        if not self.active:
            self.show_toast(tr("toast_no_macro"))
            return False
        return True

    # ================================================================ library actions
    def _refresh_macro_hotkeys(self):
        self._macro_hotkeys = {e.id: e.hotkey for e in self.library.entries() if e.hotkey}

    def library_changed(self):
        if self.active:
            self.active = self.library.get(self.active.id)
            if not self.active:
                self._load_active(None)
        self._refresh_macro_hotkeys()
        self.ui.refresh_all()

    def rename_macro(self, mid):
        ent = self.library.get(mid)
        if not ent:
            return
        dlg = ctk.CTkInputDialog(text=tr("rename_prompt"), title=tr("rename"))
        try:
            dlg.attributes("-topmost", True)  # the main window may be "always on top"
        except tk.TclError:
            pass
        name = dlg.get_input()
        if name and name.strip():
            self.library.rename(mid, name.strip()[:60])
            self.library_changed()
            self.show_toast(tr("toast_renamed", name=name.strip()[:60]))

    def duplicate_macro(self, mid):
        new = self.library.duplicate(mid, tr("copy_word"))
        self.library_changed()
        self.show_toast(tr("toast_duplicated", name=self.library.get(new).name))

    def delete_macro(self, mid):
        ent = self.library.get(mid)
        if not ent or not messagebox.askyesno("UbiMacro", tr("delete_confirm", name=ent.name)):
            return
        self.library.delete(mid)
        if self.active and self.active.id == mid:
            self._load_active(None)
            self.save_settings()
        self.library_changed()
        self.show_toast(tr("toast_deleted_macro", name=ent.name))

    def toggle_favourite(self, mid):
        ent = self.library.get(mid)
        if ent:
            self.library.set_favourite(mid, not ent.favourite)
            self.library_changed()

    def export_macro(self, mid):
        ent = self.library.get(mid)
        if not ent:
            return
        path = filedialog.asksaveasfilename(parent=self.root, initialfile=ent.id + ".json",
                                            defaultextension=".json",
                                            filetypes=[(tr("file_type"), "*.json"), (tr("all_files"), "*.*")])
        if path:
            try:
                self.library.export(mid, path)
                self.show_toast(tr("toast_exported", name=os.path.basename(path)))
            except OSError as e:
                messagebox.showerror("UbiMacro", tr("err_save", err=e))

    def import_macro(self):
        path = filedialog.askopenfilename(parent=self.root,
                                          filetypes=[(tr("file_type"), "*.json"), (tr("all_files"), "*.*")])
        if not path:
            return
        try:
            mid = self.library.import_file(path)
        except (OSError, ValueError) as e:
            messagebox.showerror("UbiMacro", tr("err_load", err=e))
            return
        self.library_changed()
        self.set_active(mid, toast=False)
        self.show_toast(tr("toast_imported", name=self.active.name))

    def add_preset(self):
        name = self.library.unique_name(tr("preset_name"))
        mid = self.library.create(name, macro.anti_afk_preset())
        if self.settings["loop_delay"] < 1:
            self.settings["loop_delay"] = 60.0
        self.settings["loops"] = 0
        self.library_changed()
        self.set_active(mid, toast=False)
        self.show_toast(tr("toast_preset"))

    def clear_macro_hotkey(self, mid):
        self.library.set_hotkey(mid, None)
        self.library_changed()

    # ================================================================ hotkeys
    def hotkey(self, which):
        return self.settings.get(which + "_hotkey")

    def hk(self, which):
        return display_name(self.hotkey(which))

    def begin_capture(self, target):
        if self.state != "idle":
            self.show_toast(tr("toast_busy"))
            return
        self.capturing = target
        self.ui.refresh_hotkeys()

    def _key_in_use(self, d, exclude):
        for name in APP_HOTKEYS:
            if ("app", name) != exclude and keys_match(d, self.hotkey(name)):
                return True
        for mid, hk in self._macro_hotkeys.items():
            if ("macro", mid) != exclude and keys_match(d, hk):
                return True
        return False

    def finish_capture(self, d):
        target, self.capturing = self.capturing, None
        if target and d.get("name") != "esc":
            if self._key_in_use(d, target):
                self.show_toast(tr("toast_hotkey_taken"))
            else:
                if target[0] == "app":
                    self.settings[target[1] + "_hotkey"] = d
                    self.save_settings()
                else:
                    self.library.set_hotkey(target[1], d)
                    self._refresh_macro_hotkeys()
                self._keys_down.add(target)
                self.show_toast(tr("toast_hotkey_set", key=display_name(d)))
        self.library_changed()

    def _match_hotkey(self, d):
        for name in APP_HOTKEYS:
            if keys_match(d, self.hotkey(name)):
                return ("app", name)
        for mid, hk in list(self._macro_hotkeys.items()):
            if keys_match(d, hk):
                return ("macro", mid)
        return None

    def _start_listeners(self):
        from pynput import keyboard, mouse

        self.kb_listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        self.kb_listener.daemon = True
        self.kb_listener.start()
        self.mouse_listener = mouse.Listener(on_move=self._on_mouse_move, on_click=self._on_mouse_click,
                                             on_scroll=self._on_mouse_scroll)
        self.mouse_listener.daemon = True
        self.mouse_listener.start()

    def _on_press(self, key, injected=False):
        if injected or key is None:
            return
        try:
            d = key_to_dict(key)
        except Exception:
            return
        if self.capturing:
            self.q.put(("captured", d))
            return
        hk = self._match_hotkey(d)
        if hk:
            if hk not in self._keys_down:
                self._keys_down.add(hk)
                self.q.put(("hotkey", hk))
            return
        if self.state in ("playing", "clicking"):
            self._last_input = time.time()
        self.recorder.key(d, True)

    def _on_release(self, key, injected=False):
        if injected or key is None:
            return
        try:
            d = key_to_dict(key)
        except Exception:
            return
        hk = self._match_hotkey(d)
        if hk:
            self._keys_down.discard(hk)
            self.q.put(("hotkey_up", hk))
            return
        self.recorder.key(d, False)

    def _on_mouse_move(self, x, y, injected=False):
        if injected or self.state not in ("playing", "clicking"):
            if not injected:
                self._mouse_pos = (x, y)
            return
        if self._mouse_pos is None:
            self._mouse_pos = (x, y)
        elif abs(x - self._mouse_pos[0]) + abs(y - self._mouse_pos[1]) > 12:
            self._mouse_pos = (x, y)
            self._last_input = time.time()

    def _on_mouse_click(self, x, y, button, pressed, injected=False):
        if not injected and pressed and self.state in ("playing", "clicking"):
            self._last_input = time.time()

    def _on_mouse_scroll(self, x, y, dx, dy, injected=False):
        if not injected and self.state in ("playing", "clicking"):
            self._last_input = time.time()

    def on_hotkey(self, hk, down=True):
        kind, name = hk
        if kind == "macro":
            if down:
                self._macro_hotkey(name)
            return
        if name == "clicker":
            self._clicker_hotkey(down)
            return
        if not down:
            return
        if name == "stopall":
            self.stop_all(toast=True)
        elif name == "mini":
            self.ui.toggle_mini()
        elif name == "record":
            if self.state == "idle":
                self.start_recording(countdown=False)
            elif self.state == "recording":
                self.stop_recording()
            elif self.state == "countdown":
                self.cancel_countdown()
        elif name == "play":
            if self.state == "playing":
                self.stop_playback()
            elif self.state == "recording":
                self.stop_recording()
                self.start_playback()
            elif self.state == "countdown":
                self.cancel_countdown()
            elif self.state == "idle":
                self.start_playback()

    def _macro_hotkey(self, mid):
        if self.state == "playing" and self.active and self.active.id == mid:
            self.stop_playback()
            return
        if self.state == "playing":
            self._end_run("stopped")
            self.player.stop(wait=True)
            self._set_state("idle")
        if self.state != "idle":
            return
        if not self.active or self.active.id != mid:
            self.set_active(mid, toast=False)
        self.start_playback()

    def _clicker_hotkey(self, down):
        if self.settings["click_mode"] == "hold":
            if down and self.state == "idle":
                self.start_clicker()
            elif not down and self.state == "clicking":
                self.stop_clicker()
        elif down:
            if self.state == "clicking":
                self.stop_clicker()
            elif self.state == "idle":
                self.start_clicker()

    # ================================================================ event loop
    def _count_click(self):
        self._run["clicks"] += 1

    def _poll(self):
        try:
            while True:
                self._handle(self.q.get_nowait())
        except queue.Empty:
            pass
        now = time.time()
        if self.state in ("playing", "clicking"):
            self._update_pause(now)
            if not self.paused:
                self._add_today(now - self._last_tick)
            if now - self._last_watch > 1.0:
                self._last_watch = now
                self._watch_game(now)
        self._last_tick = now
        if now - self._last_settings_save > 60:
            self._last_settings_save = now
            self.save_settings()
        self.ui.tick()
        if ctk.get_appearance_mode() != self._mode_seen:
            self._mode_seen = ctk.get_appearance_mode()
            self.ui.theme_changed()
        self.root.after(100, self._poll)

    def _add_today(self, dt):
        today = date.today().isoformat()
        t = self.settings.setdefault("today", {"day": today, "seconds": 0.0})
        if t.get("day") != today:
            t["day"], t["seconds"] = today, 0.0
        t["seconds"] = float(t.get("seconds", 0.0)) + max(0.0, min(dt, 5.0))

    def today_seconds(self):
        t = self.settings.get("today") or {}
        return t.get("seconds", 0.0) if t.get("day") == date.today().isoformat() else 0.0

    def _update_pause(self, now):
        s = self.settings
        reason = None
        if s["pause_on_input"] and PAUSE_SUPPORTED and now - self._last_input < num(s["resume_after"], 5, float, 1):
            reason = "input"
        if s["only_front"] and IS_WINDOWS:
            if now - self._last_front_check > 0.3:
                self._last_front_check = now
                self._front_ok = game_in_front()
            if not self._front_ok:
                reason = reason or "front"
        paused = reason is not None
        if paused != self.paused or reason != self.pause_reason:
            self.paused, self.pause_reason = paused, reason
            self.player.set_paused(paused)
            self.clicker.set_paused(paused)
            self.ui.refresh_state()

    def _handle(self, msg):
        kind = msg[0]
        if kind == "hotkey":
            self.on_hotkey(msg[1], True)
        elif kind == "hotkey_up":
            self.on_hotkey(msg[1], False)
        elif kind == "captured":
            self.finish_capture(msg[1])
        elif kind == "progress":
            self._run["loops"], self._run["total"] = msg[1] - 1, msg[2]
        elif kind == "finished":
            done, err, reason = msg[1], msg[2], msg[3]
            if not self._run["ended"] and self._run["kind"] == "macro":
                self._run["loops"] = done
                self._end_run(reason)
            if self.state == "playing":
                self._set_state("idle")
            if err:
                messagebox.showerror("UbiMacro", tr("err_playback", err=err))
        elif kind == "clicker_done":
            n, err, reason = msg[1], msg[2], msg[3]
            if not self._run["ended"] and self._run["kind"] == "clicker":
                self._end_run(reason)
            if self.state == "clicking":
                self._set_state("idle")
            if err:
                messagebox.showerror("UbiMacro", tr("err_playback", err=err))
        elif kind == "update":
            tag, url, manual = msg[1], msg[2], msg[3]
            self.update_info = (tag, url) if tag else None
            self.ui.refresh_update()
            if manual:
                self.show_toast(tr("toast_update", tag=tag) if tag else tr("toast_up_to_date"))
        elif kind == "webhook":
            self.show_toast(tr("toast_webhook_ok") if msg[1] else tr("toast_webhook_fail"))
        elif kind == "webhook_quiet":
            pass
        elif kind == "tray":
            self._tray_action(msg[1])

    # ================================================================ state
    def _set_state(self, state, countdown_text=None):
        self.state = state
        if state not in ("playing", "clicking"):
            self.paused, self.pause_reason = False, None
        if state != "countdown":
            self.countdown_sub = None
        self.countdown_text = countdown_text
        self.ui.refresh_state()
        self.tray.refresh()

    def _begin_run(self, name, kind):
        self._run = {"started": time.time(), "loops": 0, "total": 0, "clicks": 0, "name": name, "kind": kind,
                     "ended": False}
        self._last_input = 0.0
        self._mouse_pos = None
        self._last_tick = time.time()
        self._front_ok = True
        self._last_status = time.time()
        self._paused_since, self._paused_alerted = None, False
        watch = self.settings["notify_closed"] and IS_WINDOWS
        self._watch_hwnd = find_window() if watch else None
        self._log_watch = None
        if watch:
            try:
                lw = LogWatcher()
                if lw.start():
                    self._log_watch = lw
            except Exception:
                self._log_watch = None
        if self.settings["sounds"]:
            notify.play_sound("start", self.root.bell)
        self.alert("started")

    def run_elapsed(self):
        if not self._run["started"]:
            return 0.0
        end = self._run.get("ended_at") or time.time()
        return end - self._run["started"]

    def run_info(self):
        return dict(self._run)

    def _end_run(self, reason, detail=None):
        """Every run ends here exactly once: history, sounds, toasts, alerts.
        reason: done / time_limit / stopped / closed / disconnected / error."""
        if self._run.get("ended", True):
            return
        self._run["ended"] = True
        self._run["ended_at"] = time.time()
        info = dict(self._run)
        elapsed = self.run_elapsed()
        try:
            self.history.add(info["name"], info["kind"], info["started"], elapsed, info["loops"], info["clicks"],
                             reason)
        except OSError:
            pass
        self._watch_hwnd, self._log_watch = None, None
        if reason in ("closed", "disconnected"):
            notify.play_sound("alert", self.root.bell)
        elif self.settings["sounds"]:
            notify.play_sound("stop", self.root.bell)
        count = info["loops"] if info["kind"] == "macro" else info["clicks"]
        if reason == "time_limit":
            self.show_toast(tr("toast_time_limit_" + info["kind"], n=fmt_int(count)))
        elif reason == "done" and info["kind"] == "macro":
            self.show_toast(tr("toast_finished", n=count))
        if reason in ("done", "time_limit"):
            self.alert("finished", reason=tr("end_" + reason))
        elif reason == "stopped":
            self.alert("stopped")
        elif reason == "closed":
            self.alert("closed")
        elif reason == "disconnected":
            self.alert("disconnected", reason=detail or tr("dc_unknown"))
        self.ui.refresh_history()

    def _watch_game(self, now):
        """Once a second while running: Roblox closed? disconnected? status
        update due? paused too long?"""
        if self._watch_hwnd and not window_exists(self._watch_hwnd):
            self._game_gone("closed")
            return
        if self._log_watch:
            ev = self._log_watch.poll()
            if ev:
                self._game_gone("disconnected", self.disconnect_reason(ev))
                return
        a = self.settings["alerts"]
        every = num(self.settings.get("status_every"), 30, float, 1) * 60
        if a["status"]["on"] and now - self._last_status >= every:
            self._last_status = now
            self.alert("status")
        if self.paused:
            if self._paused_since is None:
                self._paused_since = now
            limit = num(self.settings.get("paused_after"), 10, float, 1) * 60
            if not self._paused_alerted and now - self._paused_since >= limit and a["paused"]["on"]:
                self._paused_alerted = True
                self.alert("paused")
        else:
            self._paused_since, self._paused_alerted = None, False

    @staticmethod
    def disconnect_reason(ev):
        code, text = ev.get("code"), ev.get("text")
        if code in DC_KNOWN:
            label = tr(DC_KNOWN[code])
        elif text:
            label = text
        else:
            label = tr("dc_unknown")
        return f"{label} ({tr('dc_code', code=code)})" if code else label

    def _game_gone(self, reason, detail=None):
        self._end_run(reason, detail)
        self.stop_all()
        key = "toast_game_closed" if reason == "closed" else "toast_disconnected"
        self.show_toast(tr(key, reason=detail or ""), ms=10000)
        self.ui.show_main()

    # ---- Discord alerts -----------------------------------------------------
    def alert_values(self, reason=""):
        info = self._run
        from datetime import datetime

        return {"macro": info.get("name") or "", "time": fmt_length(self.run_elapsed()),
                "loops": fmt_int(info.get("loops", 0)), "clicks": fmt_int(info.get("clicks", 0)),
                "reason": reason, "date": datetime.now().strftime("%d.%m.%Y %H:%M")}

    def alert_text(self, kind):
        custom = (self.settings["alerts"].get(kind) or {}).get("text") or ""
        return custom.strip() or tr("alert_text_" + kind)

    def alert(self, kind, reason="", test=False, done=None):
        """Send one Discord alert if it's switched on (or always, for a test)."""
        conf = self.settings["alerts"].get(kind) or {}
        url = self.settings.get("webhook", "")
        if not (test or conf.get("on")) or not notify.is_webhook(url):
            return False
        values = self.alert_values(reason or (tr("alert_test_reason") if test else ""))
        if test and self.state not in ("playing", "clicking"):
            values.update({"macro": "Punch bag", "time": fmt_length(5400), "loops": fmt_int(214),
                           "clicks": fmt_int(1070)})
        text = notify.fill(self.alert_text(kind), values)
        title = tr("alert_title_" + kind)
        color = notify.ALERT_DEFAULTS[kind][2]
        ping = self.settings.get("discord_user") if conf.get("ping") else None
        notify.send_discord(url, text, done, title=title, color=color, ping_user=ping)
        return True

    def test_alert(self, kind):
        if not notify.is_webhook(self.settings.get("webhook", "")):
            self.show_toast(tr("toast_webhook_bad"))
            return
        self.alert(kind, test=True, done=lambda ok, err: self.q.put(("webhook", ok, err)))

    def test_webhook(self):
        url = self.settings.get("webhook", "")
        if not notify.is_webhook(url):
            self.show_toast(tr("toast_webhook_bad"))
            return
        notify.send_discord(url, tr("msg_test"), lambda ok, err: self.q.put(("webhook", ok, err)),
                            title=tr("alert_title_test"), color=0xB01F7A,
                            ping_user=self.settings.get("discord_user"))

    def clear_history(self):
        self.history.clear()
        self.ui.refresh_history()
        self.show_toast(tr("toast_history_cleared"))

    def check_updates_now(self):
        self.show_toast(tr("toast_checking"))
        notify.check_update(__version__, lambda tag, url: self.q.put(("update", tag, url, True)))

    def open_update(self):
        webbrowser.open(self.update_info[1] if self.update_info else notify.RELEASES_URL)

    # ================================================================ countdown
    def _start_countdown(self, seconds, then):
        self._countdown_left = seconds
        self._countdown_then = then
        self._tick_countdown()

    def _tick_countdown(self):
        if self._countdown_left <= 0:
            self._countdown_job = None
            then, self._countdown_then = self._countdown_then, None
            self._set_state("idle")
            if then:
                then()
            return
        sub = self.countdown_sub
        self._set_state("countdown", tr("st_starts_in", n=self._countdown_left))
        self.countdown_sub = sub
        self.ui.refresh_state()
        self._countdown_left -= 1
        self._countdown_job = self.root.after(1000, self._tick_countdown)

    def cancel_countdown(self):
        if self._countdown_job:
            self.root.after_cancel(self._countdown_job)
            self._countdown_job = None
        self._countdown_then = None
        self._take_at = None
        self._set_state("idle")

    def _from_window(self, then):
        """Started with a button in this window: bring the game forward first,
        else count down so you can switch yourself."""
        if self.settings["focus_game"] and focus_game():
            self.root.after(350, then)
        elif self.settings["countdown"] > 0:
            self._start_countdown(int(self.settings["countdown"]), then)
        else:
            then()

    # ================================================================ recording
    def on_record_button(self):
        if self.state == "idle":
            self.start_recording(countdown=True)
        elif self.state == "recording":
            self.stop_recording(from_button=True)
        elif self.state == "countdown":
            self.cancel_countdown()

    def record_from_here(self, at):
        if not self._editable():
            return
        self._take_at = at
        self.start_recording(countdown=True)

    def start_recording(self, countdown):
        n = int(self.settings["countdown"])
        if countdown and n > 0:
            self._start_countdown(n, self._begin_recording)
        else:
            self._begin_recording()

    def _begin_recording(self):
        self.recorder.record_moves = bool(self.settings["record_moves"])
        try:
            self.recorder.start()
        except Exception as e:
            messagebox.showerror("UbiMacro", tr("err_record", err=e))
            self._set_state("idle")
            return
        self._set_state("recording")

    def stop_recording(self, from_button=False):
        events = self.recorder.stop(trim_trailing_clicks=from_button)
        take_at, self._take_at = self._take_at, None
        self._set_state("idle")
        if not events:
            self.show_toast(tr("toast_nothing"))
            return
        if self.settings["auto_trim"] or take_at is not None:
            events = macro.trim_start(events)
        if take_at is not None and self.active:
            self.replace_events(macro.insert_take(self.events, take_at, events))
            self.show_toast(tr("toast_take", n=len(events)))
            return
        name = self.library.unique_name(tr("recording_name"))
        mid = self.library.create(name, events)
        self.library_changed()
        self.set_active(mid, toast=False)
        self.show_toast(tr("toast_recorded", n=len(events), name=name))

    # ================================================================ playback
    def on_play_button(self):
        if self.state == "playing":
            self.stop_playback()
        elif self.state == "idle":
            if not self.events:
                self.show_toast(tr("toast_no_macro"))
                return
            self._from_window(self.start_playback)

    def test_from_here(self, at):
        if not self._editable():
            return
        events = macro.slice_from(self.events, at)
        if events:
            self._from_window(lambda: self.start_playback(events=events, loops=1))

    def start_playback(self, events=None, loops=None):
        events = events or self.events
        if not events:
            self.show_toast(tr("toast_no_macro"))
            return
        if self.state != "idle":
            return
        s = self.settings
        n = s["loops"] if loops is None else loops
        ok = self.player.start(events, loops=n, speed=s["speed"], loop_delay=s["loop_delay"],
                               humanize=s["humanize"] / 100.0, move_to_clicks=s["move_to_clicks"],
                               stop_after=s["stop_after"] * 60.0)
        if ok:
            self._begin_run(self.active.name if self.active else "", "macro")
            self._run["total"] = n
            if self.active:
                try:
                    self.library.mark_used(self.active.id)
                except (OSError, ValueError):
                    pass
            self._set_state("playing")

    def stop_playback(self):
        self.player.stop(wait=True)

    # ================================================================ auto-clicker
    def on_clicker_button(self):
        if self.state == "clicking":
            self.stop_clicker()
        elif self.state == "idle" and self._clicker_ready():
            self._from_window(self.start_clicker)

    def _clicker_ready(self):
        if self.settings["click_where"] == "point" and not self.settings.get("click_point"):
            self.show_toast(tr("toast_pick_first"))
            return False
        return True

    def start_clicker(self):
        if self.state != "idle" or not self._clicker_ready():
            return
        s = self.settings
        point = tuple(s["click_point"]) if s["click_where"] == "point" and s.get("click_point") else None
        ok = self.clicker.start(cps=s["cps"], button=s["click_button"], vary=0.15 if s["click_vary"] else 0.0,
                                point=point, stop_after=s["stop_after"] * 60.0)
        if ok:
            self._begin_run(tr("autoclicker"), "clicker")
            self._set_state("clicking")

    def stop_clicker(self):
        self.clicker.stop(wait=True)

    def change_cps(self, direction):
        cur = self.settings["cps"]
        if direction > 0:
            nxt = next((c for c in CPS_STEPS if c > cur), CPS_STEPS[-1])
        else:
            nxt = next((c for c in reversed(CPS_STEPS) if c < cur), CPS_STEPS[0])
        self.set_setting("cps", nxt)
        self.ui.refresh_clicker()

    def pick_spot(self):
        if self.state != "idle":
            self.show_toast(tr("toast_busy"))
            return

        def grab():
            from pynput import mouse

            x, y = mouse.Controller().position
            self.settings["click_point"] = [int(x), int(y)]
            self.settings["click_where"] = "point"
            self.save_settings()
            self.ui.refresh_clicker()
            self.show_toast(tr("toast_spot", x=int(x), y=int(y)))
            self.ui.show_main()

        self.countdown_sub = tr("sub_pick_spot")
        self._start_countdown(3, grab)

    # ================================================================ stop all
    def stop_all(self, toast=False):
        was = self.state
        if self.state == "recording":
            self.stop_recording(from_button=False)
        elif self.state == "countdown":
            self.cancel_countdown()
        elif self.state == "playing":
            self._end_run("stopped")
            self.player.stop(wait=True)
            self._set_state("idle")
        elif self.state == "clicking":
            self._end_run("stopped")
            self.clicker.stop(wait=True)
            self._set_state("idle")
        if toast and was in ("playing", "clicking"):
            self.show_toast(tr("toast_stopped"))
        if self.state != "idle":
            self._set_state("idle")

    # ================================================================ misc
    def show_toast(self, message, ms=2600):
        self.ui.toast(message, ms)

    def set_theme(self, mode):
        self.set_setting("theme", mode)
        ctk.set_appearance_mode(mode)

    def set_language(self, lang):
        if lang == tr.lang:
            return
        self.set_setting("lang", lang)
        tr.set_lang(lang)
        self.ui.rebuild()
        self.tray.rebuild()

    def open_folder(self):
        path = os.path.join(self.cfg_dir, "macros")
        try:
            if IS_WINDOWS:
                os.startfile(path)  # noqa: S606
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception:
            self.show_toast(path)

    def _tray_action(self, action):
        if action == "show":
            self.ui.show_main()
        elif action == "play":
            self.on_hotkey(("app", "play"))
        elif action == "clicker":
            if self.state == "clicking":
                self.stop_clicker()
            elif self.state == "idle":
                self.start_clicker()
        elif action == "quit":
            self.quit()

    def on_close_request(self):
        if self.settings["close_to_tray"] and self.tray.available:
            self.ui.hide_mini()
            self.root.withdraw()
            self.tray.show()
            return
        self.quit()

    def quit(self):
        if self.state in ("playing", "clicking"):
            self._end_run("stopped")
        try:
            self.player.stop(wait=True)
            self.clicker.stop(wait=True)
            if self.recorder.active:
                self.recorder.stop()
            self.kb_listener.stop()
            self.mouse_listener.stop()
        except Exception:
            pass
        self.tray.stop()
        self.save_settings()
        self.root.destroy()


def enable_dpi_awareness():
    """Make mouse coordinates match real screen pixels on scaled displays."""
    if not IS_WINDOWS:
        return
    import ctypes

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def main():
    enable_dpi_awareness()
    th.load_fonts()
    root = ctk.CTk()
    root.title("UbiMacro")
    th.resolve_families(root)
    try:
        from .backends import get_backend

        backend = get_backend()
    except ImportError:
        root.withdraw()
        messagebox.showerror("UbiMacro", "The 'pynput' package is missing.\nRun:  pip install -r requirements.txt")
        return
    App(root, backend)
    root.mainloop()
