"""The UbiMacro window (Tkinter)."""

import json
import os
import queue
import sys
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import __version__, macro
from .keys import display_name, key_to_dict, keys_match, make_key
from .player import Player
from .recorder import Recorder

COLORS = {
    "idle": ("#2b2d31", "#e6e6e6"),
    "countdown": ("#8a6d00", "#ffffff"),
    "recording": ("#b3261e", "#ffffff"),
    "playing": ("#1e7a3a", "#ffffff"),
}

DEFAULTS = {
    "record_hotkey": make_key("f8"),
    "play_hotkey": make_key("f6"),
    "loops": 0,
    "speed": 1.0,
    "loop_delay": 0.0,
    "humanize": 0,
    "move_to_clicks": True,
    "record_moves": False,
    "countdown": 3,
    "topmost": True,
}

PLAYBACK_KEYS = ("loops", "speed", "loop_delay", "humanize", "move_to_clicks")


def config_dir():
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    path = os.path.join(base, "UbiMacro")
    os.makedirs(os.path.join(path, "macros"), exist_ok=True)
    return path


def fmt_duration(seconds):
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


class App:
    def __init__(self, root, backend):
        self.root = root
        self.backend = backend
        self.q = queue.Queue()
        self.cfg_dir = config_dir()
        self.settings_path = os.path.join(self.cfg_dir, "settings.json")
        self.last_macro_path = os.path.join(self.cfg_dir, "last_macro.json")
        self.settings = self._load_settings()

        self.events = []
        self.state = "idle"
        self.capturing = None          # "record" / "play" while choosing a hotkey
        self._hotkeys_down = set()
        self._countdown_left = 0
        self._countdown_job = None
        self._play_started = 0.0
        self._loop_text = ""

        self.recorder = Recorder()
        self.player = Player(
            backend,
            on_progress=lambda n, total: self.q.put(("progress", n, total)),
            on_finish=lambda done, err: self.q.put(("finished", done, err)),
        )

        self._build_ui()
        self._load_last_macro()
        self._start_keyboard_listener()
        self._set_state("idle")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(30, self._poll)

    # ------------------------------------------------------------------ settings
    def _load_settings(self):
        s = dict(DEFAULTS)
        try:
            with open(self.settings_path, "r", encoding="utf-8") as f:
                s.update(json.load(f))
        except (OSError, ValueError):
            pass
        return s

    def _save_settings(self):
        self._read_vars()
        try:
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=1)
        except OSError:
            pass

    def _read_vars(self):
        def get(var, default, cast):
            try:
                return cast(var.get())
            except (tk.TclError, ValueError, TypeError):
                return default

        s = self.settings
        s["loops"] = max(0, get(self.v_loops, 0, int))
        s["speed"] = min(10.0, max(0.1, get(self.v_speed, 1.0, float)))
        s["loop_delay"] = max(0.0, get(self.v_delay, 0.0, float))
        s["humanize"] = min(50, max(0, get(self.v_humanize, 0, int)))
        s["countdown"] = min(30, max(0, get(self.v_countdown, 3, int)))
        s["move_to_clicks"] = bool(self.v_move_clicks.get())
        s["record_moves"] = bool(self.v_record_moves.get())
        s["topmost"] = bool(self.v_topmost.get())
        return s

    def _apply_playback_settings(self, d):
        if "loops" in d:
            self.v_loops.set(d["loops"])
        if "speed" in d:
            self.v_speed.set(d["speed"])
        if "loop_delay" in d:
            self.v_delay.set(d["loop_delay"])
        if "humanize" in d:
            self.v_humanize.set(d["humanize"])
        if "move_to_clicks" in d:
            self.v_move_clicks.set(bool(d["move_to_clicks"]))

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        r = self.root
        r.title(f"UbiMacro {__version__}")
        r.minsize(440, 600)
        s = self.settings
        pad = {"padx": 8, "pady": 4}

        self.status = tk.Label(r, text="", font=("Segoe UI", 13, "bold"), pady=10)
        self.status.pack(fill="x")
        self.substatus = ttk.Label(r, text="", anchor="center")
        self.substatus.pack(fill="x", pady=(4, 0))

        btns = ttk.Frame(r)
        btns.pack(fill="x", **pad)
        self.b_record = ttk.Button(btns, text="● Record", command=self.on_record_button)
        self.b_play = ttk.Button(btns, text="▶ Play", command=self.on_play_button)
        self.b_stop = ttk.Button(btns, text="■ Stop", command=self.stop_all)
        for b in (self.b_record, self.b_play, self.b_stop):
            b.pack(side="left", expand=True, fill="x", padx=3, ipady=4)

        # Hotkeys
        hk = ttk.LabelFrame(r, text="Hotkeys (work while the game is focused)")
        hk.pack(fill="x", **pad)
        self.l_rec_hk = ttk.Label(hk, width=12)
        self.l_play_hk = ttk.Label(hk, width=12)
        ttk.Label(hk, text="Record / stop recording:").grid(row=0, column=0, sticky="w", padx=6, pady=3)
        self.l_rec_hk.grid(row=0, column=1, sticky="w")
        ttk.Button(hk, text="Change", command=lambda: self.begin_capture("record")).grid(row=0, column=2, padx=6)
        ttk.Label(hk, text="Play / stop playing:").grid(row=1, column=0, sticky="w", padx=6, pady=3)
        self.l_play_hk.grid(row=1, column=1, sticky="w")
        ttk.Button(hk, text="Change", command=lambda: self.begin_capture("play")).grid(row=1, column=2, padx=6)
        hk.columnconfigure(1, weight=1)
        self._refresh_hotkey_labels()

        # Playback
        pb = ttk.LabelFrame(r, text="Playback")
        pb.pack(fill="x", **pad)
        self.v_loops = tk.StringVar(value=str(s["loops"]))
        self.v_speed = tk.StringVar(value=str(s["speed"]))
        self.v_delay = tk.StringVar(value=str(s["loop_delay"]))
        self.v_humanize = tk.StringVar(value=str(s["humanize"]))
        self.v_move_clicks = tk.BooleanVar(value=s["move_to_clicks"])
        rows = [
            ("Repeat (0 = forever):", self.v_loops, 0, 1000000, 1),
            ("Speed (1 = normal):", self.v_speed, 0.25, 10, 0.25),
            ("Wait between loops (sec):", self.v_delay, 0, 3600, 5),
            ("Humanize timing (± %):", self.v_humanize, 0, 50, 5),
        ]
        for i, (label, var, lo, hi, inc) in enumerate(rows):
            ttk.Label(pb, text=label).grid(row=i, column=0, sticky="w", padx=6, pady=2)
            ttk.Spinbox(pb, textvariable=var, from_=lo, to=hi, increment=inc, width=10).grid(
                row=i, column=1, sticky="w", padx=6
            )
        ttk.Checkbutton(pb, text="Move mouse to recorded click positions", variable=self.v_move_clicks).grid(
            row=len(rows), column=0, columnspan=2, sticky="w", padx=6, pady=2
        )

        # Recording
        rc = ttk.LabelFrame(r, text="Recording")
        rc.pack(fill="x", **pad)
        self.v_record_moves = tk.BooleanVar(value=s["record_moves"])
        self.v_countdown = tk.StringVar(value=str(s["countdown"]))
        ttk.Checkbutton(rc, text="Also record mouse movement (not just clicks)", variable=self.v_record_moves).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=6, pady=2
        )
        ttk.Label(rc, text="Countdown when using the Record button (sec):").grid(row=1, column=0, sticky="w", padx=6)
        ttk.Spinbox(rc, textvariable=self.v_countdown, from_=0, to=30, width=6).grid(row=1, column=1, sticky="w")

        # Macro file
        mf = ttk.LabelFrame(r, text="Macro")
        mf.pack(fill="both", expand=True, **pad)
        row = ttk.Frame(mf)
        row.pack(fill="x", pady=3)
        for text, cmd in (("Save…", self.save_macro), ("Load…", self.load_macro),
                          ("Anti-AFK preset", self.load_preset), ("Clear", self.clear_macro)):
            ttk.Button(row, text=text, command=cmd).pack(side="left", expand=True, fill="x", padx=3)
        self.info = ttk.Label(mf, text="")
        self.info.pack(fill="x", padx=6)

        tv_frame = ttk.Frame(mf)
        tv_frame.pack(fill="both", expand=True, padx=4, pady=3)
        self.tree = ttk.Treeview(tv_frame, columns=("t", "ev"), show="headings", height=8)
        self.tree.heading("t", text="Time (s)")
        self.tree.heading("ev", text="Event")
        self.tree.column("t", width=80, anchor="e", stretch=False)
        self.tree.column("ev", width=300)
        sb = ttk.Scrollbar(tv_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        ttk.Button(mf, text="Delete selected events", command=self.delete_selected).pack(fill="x", padx=4, pady=(0, 4))

        bottom = ttk.Frame(r)
        bottom.pack(fill="x", **pad)
        self.v_topmost = tk.BooleanVar(value=s["topmost"])
        ttk.Checkbutton(bottom, text="Keep window on top", variable=self.v_topmost, command=self._apply_topmost).pack(
            side="left"
        )
        self._apply_topmost()

    def _apply_topmost(self):
        try:
            self.root.attributes("-topmost", bool(self.v_topmost.get()))
        except tk.TclError:
            pass

    def _refresh_hotkey_labels(self):
        rec = "press a key…" if self.capturing == "record" else display_name(self.settings["record_hotkey"])
        play = "press a key…" if self.capturing == "play" else display_name(self.settings["play_hotkey"])
        self.l_rec_hk.config(text=rec)
        self.l_play_hk.config(text=play)

    def _refresh_events(self):
        self.tree.delete(*self.tree.get_children())
        limit = 3000
        for i, ev in enumerate(self.events[:limit]):
            self.tree.insert("", "end", iid=str(i), values=(f"{ev['t']:.3f}", macro.describe(ev)))
        n = len(self.events)
        extra = f" (showing first {limit})" if n > limit else ""
        self.info.config(text=f"{n} events · {macro.duration(self.events):.1f} s long{extra}")

    def _set_state(self, state, text=None):
        self.state = state
        bg, fg = COLORS[state]
        rec_hk = display_name(self.settings["record_hotkey"])
        play_hk = display_name(self.settings["play_hotkey"])
        default = {
            "idle": "Ready",
            "countdown": "Get ready…",
            "recording": f"● RECORDING — press {rec_hk} to stop",
            "playing": f"▶ PLAYING — press {play_hk} to stop",
        }[state]
        self.status.config(text=text or default, bg=bg, fg=fg)
        if state == "idle":
            self.substatus.config(text=f"{rec_hk} = record · {play_hk} = play/stop")
        busy = state != "idle"
        self.b_record.config(text="■ Stop recording" if state == "recording" else "● Record",
                             state="normal" if state in ("idle", "recording", "countdown") else "disabled")
        self.b_play.config(state="disabled" if state in ("recording", "countdown") else "normal",
                           text="■ Stop playing" if state == "playing" else "▶ Play")
        self.b_stop.config(state="normal" if busy else "disabled")

    # ------------------------------------------------------------------ keyboard listener
    def _start_keyboard_listener(self):
        from pynput import keyboard

        self.kb_listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        self.kb_listener.daemon = True
        self.kb_listener.start()

    def _hotkey_for(self, d):
        for name in ("record", "play"):
            if keys_match(d, self.settings.get(name + "_hotkey")):
                return name
        return None

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
        hk = self._hotkey_for(d)
        if hk:
            if hk not in self._hotkeys_down:
                self._hotkeys_down.add(hk)
                self.q.put(("hotkey", hk))
            return
        self.recorder.key(d, True)

    def _on_release(self, key, injected=False):
        if injected or key is None:
            return
        try:
            d = key_to_dict(key)
        except Exception:
            return
        hk = self._hotkey_for(d)
        if hk:
            self._hotkeys_down.discard(hk)
            return
        self.recorder.key(d, False)

    # ------------------------------------------------------------------ event loop
    def _poll(self):
        try:
            while True:
                msg = self.q.get_nowait()
                self._handle(msg)
        except queue.Empty:
            pass
        if self.state == "recording":
            self.substatus.config(text=f"{self.recorder.event_count} events recorded")
        elif self.state == "playing":
            self.substatus.config(text=f"{self._loop_text} · running for {fmt_duration(time.time() - self._play_started)}")
        self.root.after(50, self._poll)

    def _handle(self, msg):
        kind = msg[0]
        if kind == "hotkey":
            self.on_hotkey(msg[1])
        elif kind == "captured":
            self.finish_capture(msg[1])
        elif kind == "progress":
            n, total = msg[1], msg[2]
            self._loop_text = f"Loop {n} / {'∞' if total == 0 else total}"
        elif kind == "finished":
            done, err = msg[1], msg[2]
            if self.state == "playing":
                self._set_state("idle")
                self.substatus.config(text=f"Finished · {done} loop(s) completed")
            if err:
                messagebox.showerror("UbiMacro", f"Playback stopped because of an error:\n{err}")

    # ------------------------------------------------------------------ hotkeys
    def on_hotkey(self, name):
        if name == "record":
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
            elif self.state == "idle":
                self.start_playback()

    def begin_capture(self, which):
        if self.state != "idle":
            return
        self.capturing = which
        self._refresh_hotkey_labels()

    def finish_capture(self, d):
        which = self.capturing
        self.capturing = None
        if which and d.get("name") != "esc":
            other = "play" if which == "record" else "record"
            if keys_match(d, self.settings[other + "_hotkey"]):
                messagebox.showwarning("UbiMacro", "That key is already used by the other hotkey.")
            else:
                self.settings[which + "_hotkey"] = d
                self._hotkeys_down.add(which)  # the key is still physically down
                self._save_settings()
        self._refresh_hotkey_labels()
        self._set_state(self.state)

    # ------------------------------------------------------------------ recording
    def on_record_button(self):
        if self.state == "idle":
            self.start_recording(countdown=True)
        elif self.state == "recording":
            self.stop_recording(from_button=True)
        elif self.state == "countdown":
            self.cancel_countdown()

    def start_recording(self, countdown):
        # No "overwrite?" dialog: it would pop up over the game. If nothing gets
        # recorded, the previous macro is kept.
        s = self._read_vars()
        if countdown and s["countdown"] > 0:
            self._countdown_left = s["countdown"]
            self._tick_countdown()
        else:
            self._begin_recording()

    def _tick_countdown(self):
        if self._countdown_left <= 0:
            self._countdown_job = None
            self._begin_recording()
            return
        self._set_state("countdown", f"Recording starts in {self._countdown_left}…")
        self.substatus.config(text="Switch to your game now")
        self._countdown_left -= 1
        self._countdown_job = self.root.after(1000, self._tick_countdown)

    def cancel_countdown(self):
        if self._countdown_job:
            self.root.after_cancel(self._countdown_job)
            self._countdown_job = None
        self._set_state("idle")

    def _begin_recording(self):
        self.recorder.record_moves = bool(self.settings["record_moves"])
        try:
            self.recorder.start()
        except Exception as e:
            messagebox.showerror("UbiMacro", f"Could not start recording:\n{e}")
            self._set_state("idle")
            return
        self._set_state("recording")

    def stop_recording(self, from_button=False):
        events = self.recorder.stop(trim_trailing_clicks=from_button)
        self._set_state("idle")
        if not events:
            self.substatus.config(text="Nothing was recorded — previous macro kept")
            return
        self.events = events
        self._refresh_events()
        self._autosave()
        self.substatus.config(text=f"Recorded {len(events)} events — press {display_name(self.settings['play_hotkey'])} to play")

    # ------------------------------------------------------------------ playback
    def on_play_button(self):
        if self.state == "playing":
            self.stop_playback()
        elif self.state == "idle":
            self.start_playback()

    def start_playback(self):
        if not self.events:
            self.substatus.config(text="No macro yet — record one or load the Anti-AFK preset")
            return
        s = self._read_vars()
        self._save_settings()
        self._loop_text = "Loop 1"
        self._play_started = time.time()
        ok = self.player.start(
            self.events,
            loops=s["loops"],
            speed=s["speed"],
            loop_delay=s["loop_delay"],
            humanize=s["humanize"] / 100.0,
            move_to_clicks=s["move_to_clicks"],
        )
        if ok:
            self._set_state("playing")

    def stop_playback(self):
        self.player.stop(wait=True)
        self._set_state("idle")
        self.substatus.config(text="Stopped")

    def stop_all(self):
        if self.state == "recording":
            self.stop_recording(from_button=True)
        elif self.state == "countdown":
            self.cancel_countdown()
        elif self.state == "playing":
            self.stop_playback()

    # ------------------------------------------------------------------ macro files
    def _autosave(self):
        try:
            macro.save(self.last_macro_path, self.events)
        except OSError:
            pass

    def _load_last_macro(self):
        if os.path.exists(self.last_macro_path):
            try:
                self.events, _ = macro.load(self.last_macro_path)
            except (OSError, ValueError):
                self.events = []
        self._refresh_events()

    def save_macro(self):
        if not self.events:
            messagebox.showinfo("UbiMacro", "There is nothing to save yet.")
            return
        path = filedialog.asksaveasfilename(
            parent=self.root,
            initialdir=os.path.join(self.cfg_dir, "macros"),
            defaultextension=".json",
            filetypes=[("UbiMacro macro", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        s = self._read_vars()
        try:
            macro.save(path, self.events, {k: s[k] for k in PLAYBACK_KEYS})
            self.substatus.config(text=f"Saved to {os.path.basename(path)}")
        except OSError as e:
            messagebox.showerror("UbiMacro", f"Could not save:\n{e}")

    def load_macro(self):
        if self.state != "idle":
            return
        path = filedialog.askopenfilename(
            parent=self.root,
            initialdir=os.path.join(self.cfg_dir, "macros"),
            filetypes=[("UbiMacro macro", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            events, settings = macro.load(path)
        except (OSError, ValueError) as e:
            messagebox.showerror("UbiMacro", f"Could not load that file:\n{e}")
            return
        self.events = events
        self._apply_playback_settings(settings)
        self._refresh_events()
        self._autosave()
        self.substatus.config(text=f"Loaded {os.path.basename(path)}")

    def load_preset(self):
        if self.state != "idle":
            return
        self.events = macro.anti_afk_preset()
        try:
            if float(self.v_delay.get() or 0) < 1:
                self.v_delay.set("60")
        except ValueError:
            self.v_delay.set("60")
        self.v_loops.set("0")
        self._refresh_events()
        self._autosave()
        self.substatus.config(text="Anti-AFK preset loaded: jump + step forward/back every 60 s")

    def clear_macro(self):
        if self.state != "idle" or not self.events:
            return
        if messagebox.askyesno("UbiMacro", "Clear the current macro?"):
            self.events = []
            self._refresh_events()
            self._autosave()

    def delete_selected(self):
        if self.state != "idle":
            return
        sel = {int(i) for i in self.tree.selection()}
        if not sel:
            return
        self.events = [e for i, e in enumerate(self.events) if i not in sel]
        self._refresh_events()
        self._autosave()

    # ------------------------------------------------------------------ shutdown
    def on_close(self):
        try:
            self.player.stop(wait=True)
            if self.recorder.active:
                self.recorder.stop()
            self.kb_listener.stop()
        except Exception:
            pass
        self._save_settings()
        self.root.destroy()


def enable_dpi_awareness():
    """Make mouse coordinates match real screen pixels on scaled displays."""
    if sys.platform != "win32":
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
    root = tk.Tk()
    try:
        from .backends import get_backend

        backend = get_backend()
    except ImportError:
        root.withdraw()
        messagebox.showerror("UbiMacro", "The 'pynput' package is missing.\nRun:  pip install -r requirements.txt")
        return
    App(root, backend)
    root.mainloop()
