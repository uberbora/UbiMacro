"""The UbiMacro window, built on the Ubi design system (CustomTkinter)."""

import json
import os
import queue
import subprocess
import sys
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

from . import __version__, macro
from . import theme as th
from .i18n import tr
from .keys import display_name, key_to_dict, keys_match, make_key
from .player import Player
from .recorder import Recorder
from .theme import C, R_CARD, R_CONTROL, R_HERO, R_LIST
from .winfocus import find_window, focus_game, list_windows, relative_to_foreground, system_language

DEFAULTS = {
    "lang": None,          # filled from the system language on first run
    "theme": "dark",       # Ubi desktop apps default to dark
    "record_hotkey": make_key("f8"),
    "play_hotkey": make_key("f6"),
    "loops": 0,
    "speed": 1.0,
    "loop_delay": 0.0,
    "humanize": 0,
    "stop_after": 0.0,     # minutes, 0 = never
    "move_to_clicks": True,
    "record_moves": False,
    "auto_trim": True,     # remove the delay before the first event after recording
    "focus_game": True,    # bring Roblox to the front when Play is pressed in the app
    "countdown": 3,
    "cap_gap": 2.0,
    "topmost": True,
    "background": False,   # experimental: send input to one window with window messages
    "bg_window": "Roblox",
    "fake_focus": True,
}

IS_WINDOWS = sys.platform == "win32"

PLAYBACK_KEYS = ("loops", "speed", "loop_delay", "humanize", "stop_after", "move_to_clicks")
UNDO_LIMIT = 50


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


def num(var, default, cast=float, lo=None, hi=None):
    try:
        v = cast(str(var.get()).replace(",", ".").strip())
    except (ValueError, TypeError, tk.TclError):
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
        self.last_macro_path = os.path.join(self.cfg_dir, "last_macro.json")
        self.settings = self._load_settings()
        tr.set_lang(self.settings["lang"])
        ctk.set_appearance_mode(self.settings["theme"])

        self.events = []
        self.undo_stack = []
        self.state = "idle"            # idle / countdown / recording / playing
        self.page = "home"
        self.capturing = None          # "record" / "play" while choosing a hotkey
        self._hotkeys_down = set()
        self._countdown_left = 0
        self._countdown_job = None
        self._countdown_then = None
        self._play_started = 0.0
        self._loop_now = 0
        self._loop_total = 0
        self._loops_done = 0
        self._toast_job = None
        self._armed_job = None
        self._mode_seen = None

        self.recorder = Recorder(relative_fn=relative_to_foreground)
        self._testing = False
        self.player = Player(
            backend,
            on_progress=lambda n, total: self.q.put(("progress", n, total)),
            on_finish=lambda done, err, reason: self.q.put(("finished", done, err, reason)),
        )

        self._make_vars()
        self._load_last_macro()
        root.configure(fg_color=C["bg"])
        root.minsize(460, 640)
        root.geometry("500x820")
        root.bind_all("<Control-z>", lambda e: self.undo())
        self._build()
        self._start_keyboard_listener()
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.after(30, self._poll)

    def _load_settings(self):
        s = dict(DEFAULTS)
        try:
            with open(self.settings_path, "r", encoding="utf-8") as f:
                s.update(json.load(f))
        except (OSError, ValueError):
            pass
        if s.get("lang") not in ("en", "tr"):
            s["lang"] = system_language()
        if s.get("theme") not in ("system", "light", "dark"):
            s["theme"] = "dark"
        return s

    def _make_vars(self):
        s = self.settings
        self.v_loops = tk.StringVar(value=str(s["loops"]))
        self.v_speed = tk.StringVar(value=str(s["speed"]))
        self.v_delay = tk.StringVar(value=str(s["loop_delay"]))
        self.v_humanize = tk.StringVar(value=str(s["humanize"]))
        self.v_stop_after = tk.StringVar(value=str(s["stop_after"]))
        self.v_countdown = tk.StringVar(value=str(s["countdown"]))
        self.v_cap = tk.StringVar(value=str(s["cap_gap"]))
        self.v_move_clicks = tk.BooleanVar(value=s["move_to_clicks"])
        self.v_record_moves = tk.BooleanVar(value=s["record_moves"])
        self.v_auto_trim = tk.BooleanVar(value=s["auto_trim"])
        self.v_focus_game = tk.BooleanVar(value=s["focus_game"])
        self.v_topmost = tk.BooleanVar(value=s["topmost"])
        self.v_move_following = tk.BooleanVar(value=True)
        self.v_background = tk.BooleanVar(value=s["background"] and IS_WINDOWS)
        self.v_bg_window = tk.StringVar(value=s["bg_window"])
        self.v_fake_focus = tk.BooleanVar(value=s["fake_focus"])
        self.v_ev_time = tk.StringVar()
        self.v_ev_gap = tk.StringVar()

    def _read_vars(self):
        s = self.settings
        s["loops"] = num(self.v_loops, 0, int, 0)
        s["speed"] = num(self.v_speed, 1.0, float, 0.1, 10.0)
        s["loop_delay"] = num(self.v_delay, 0.0, float, 0.0)
        s["humanize"] = num(self.v_humanize, 0, int, 0, 50)
        s["stop_after"] = num(self.v_stop_after, 0.0, float, 0.0)
        s["countdown"] = num(self.v_countdown, 3, int, 0, 30)
        s["cap_gap"] = num(self.v_cap, 2.0, float, 0.0)
        s["move_to_clicks"] = bool(self.v_move_clicks.get())
        s["record_moves"] = bool(self.v_record_moves.get())
        s["auto_trim"] = bool(self.v_auto_trim.get())
        s["focus_game"] = bool(self.v_focus_game.get())
        s["topmost"] = bool(self.v_topmost.get())
        s["background"] = bool(self.v_background.get()) and IS_WINDOWS
        s["bg_window"] = self.v_bg_window.get().strip() or "Roblox"
        s["fake_focus"] = bool(self.v_fake_focus.get())
        return s

    def _save_settings(self):
        self._read_vars()
        try:
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=1)
        except OSError:
            pass

    # ================================================================ widget kit
    def card(self, parent, radius=R_CARD, fill="surface", border=True):
        return ctk.CTkFrame(parent, fg_color=C[fill], corner_radius=radius,
                            border_width=1 if border else 0, border_color=C["line"])

    def text(self, parent, value, role="body", size=15, color="ink", **kw):
        return ctk.CTkLabel(parent, text=value, font=th.font(role, size), text_color=C[color],
                            anchor=kw.pop("anchor", "w"), justify=kw.pop("justify", "left"), **kw)

    def eyebrow(self, parent, value, color="muted"):
        return self.text(parent, tr.upper(value), "mono", 11, color)

    def hint(self, parent, value):
        return self.text(parent, value, "body", 12, "muted", wraplength=440)

    def section(self, parent, title, pady=(22, 10)):
        lbl = self.text(parent, title, "display600", 19)
        lbl.pack(fill="x", padx=16, pady=pady)
        return lbl

    def button(self, parent, label, command, kind="ghost", width=0, height=38):
        styles = {
            "primary": dict(fg_color=C["accent"], hover_color=C["accent_hover"], text_color=C["accent_ink"],
                            border_width=0),
            "ghost": dict(fg_color=C["surface"], hover_color=C["surface2"], text_color=C["ink"],
                          border_width=1, border_color=C["outline"]),
            "danger": dict(fg_color=C["loss_bg"], hover_color=C["loss_bg"], text_color=C["loss"],
                           border_width=1, border_color=C["loss"]),
            "soft": dict(fg_color=C["accent_soft"], hover_color=C["surface2"], text_color=C["accent"],
                         border_width=0),
        }
        role = "body700" if kind == "primary" else "body600"
        return ctk.CTkButton(parent, text=label, command=command, corner_radius=height // 2, height=height,
                             width=width, font=th.font(role, 14), text_color_disabled=C["muted"],
                             **styles[kind])

    def entry(self, parent, var, width=96):
        return ctk.CTkEntry(parent, textvariable=var, width=width, height=36, corner_radius=R_CONTROL,
                            fg_color=C["surface"], border_color=C["outline"], border_width=1,
                            text_color=C["ink"], font=th.font("body", 15))

    def field(self, parent, label, var, width=96):
        box = ctk.CTkFrame(parent, fg_color="transparent")
        self.eyebrow(box, label).pack(fill="x", pady=(0, 6))
        self.entry(box, var, width).pack(anchor="w")
        return box

    def switch(self, parent, label, var, command=None):
        return ctk.CTkSwitch(parent, text=label, variable=var, command=command or self._save_settings,
                             font=th.font("body", 15), text_color=C["ink"], progress_color=C["accent"],
                             fg_color=C["outline"], button_color=("#ffffff", "#f1e8ee"),
                             button_hover_color=("#f6f0f4", "#ffffff"), switch_width=40, switch_height=22)

    def segmented(self, parent, options, current, command, height=36):
        """Ubi SegmentedControl: a recessed track with the chosen segment raised."""
        labels = [lbl for _, lbl in options]
        by_label = {lbl: key for key, lbl in options}
        seg = ctk.CTkSegmentedButton(
            parent, values=labels, height=height, corner_radius=R_CONTROL, border_width=3,
            fg_color=C["surface2"], selected_color=C["surface"], selected_hover_color=C["surface"],
            unselected_color=C["surface2"], unselected_hover_color=C["line"], text_color=C["ink"],
            font=th.font("body600", 14), command=lambda lbl: command(by_label[lbl]),
        )
        seg.set(dict(options)[current])
        return seg

    # ================================================================ layout
    def _build(self):
        self.shell = ctk.CTkFrame(self.root, fg_color="transparent", corner_radius=0)
        self.shell.pack(fill="both", expand=True)

        # TopBar: wordmark + theme switch
        top = ctk.CTkFrame(self.shell, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(14, 10))
        mark = ctk.CTkFrame(top, fg_color="transparent")
        mark.pack(side="left")
        self.text(mark, "Ubi", "display800", 24).pack(side="left")
        self.text(mark, "Macro", "display800", 24, "accent").pack(side="left")
        self.b_theme = ctk.CTkButton(top, text="◐", width=38, height=38, corner_radius=R_CONTROL,
                                     fg_color=C["surface"], hover_color=C["surface2"], text_color=C["ink"],
                                     border_width=1, border_color=C["outline"], font=th.font("body600", 16),
                                     command=self.toggle_theme)
        self.b_theme.pack(side="right")

        # Tabs
        self.tabs = self.segmented(
            self.shell, [("home", tr("tab_home")), ("events", tr("tab_events")), ("settings", tr("tab_settings"))],
            self.page, self.show_page, height=38)
        self.tabs.pack(fill="x", padx=16)

        self.pages = {
            "home": ctk.CTkScrollableFrame(self.shell, fg_color="transparent", corner_radius=0),
            "events": ctk.CTkFrame(self.shell, fg_color="transparent", corner_radius=0),
            "settings": ctk.CTkScrollableFrame(self.shell, fg_color="transparent", corner_radius=0),
        }
        self._build_home(self.pages["home"])
        self._build_events(self.pages["events"])
        self._build_settings(self.pages["settings"])

        self.toast = ctk.CTkLabel(self.root, text="", fg_color=C["ink"], text_color=C["bg"], corner_radius=18,
                                  bg_color=C["bg"],
                                  height=36, font=th.font("body600", 14))
        self._style_tree()
        self._apply_topmost()
        self.show_page(self.page)
        self._refresh_events()
        self._set_state(self.state)

    def rebuild(self):
        """Rebuild the whole window (after a language change)."""
        self._read_vars()
        if self._toast_job:
            self.root.after_cancel(self._toast_job)
            self._toast_job = None
        self.toast.destroy()
        self.shell.destroy()
        self._build()

    def show_page(self, key):
        self.page = key
        labels = {"home": tr("tab_home"), "events": tr("tab_events"), "settings": tr("tab_settings")}
        if self.tabs.get() != labels[key]:
            self.tabs.set(labels[key])
        for k, frame in self.pages.items():
            if k == key:
                frame.pack(fill="both", expand=True, pady=(6, 0))
            else:
                frame.pack_forget()

    # ---------------------------------------------------------------- home
    def _build_home(self, page):
        # HeroCard: the status
        hero = ctk.CTkFrame(page, fg_color=C["accent"], corner_radius=R_HERO)
        hero.pack(fill="x", padx=16, pady=(8, 0))
        row = ctk.CTkFrame(hero, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(18, 0))
        self.eyebrow(row, tr("status"), "accent_ink").pack(side="left")
        self.pill = ctk.CTkLabel(row, text="", corner_radius=999, height=24, font=th.font("body600", 12))
        self.pill.pack(side="right")
        self.hero_title = self.text(hero, "", "display800", 34, "accent_ink")
        self.hero_title.pack(fill="x", padx=20, pady=(6, 0))
        self.hero_sub = self.text(hero, "", "body", 13, "accent_ink", wraplength=420)
        self.hero_sub.pack(fill="x", padx=20, pady=(2, 18))

        # Actions
        acts = ctk.CTkFrame(page, fg_color="transparent")
        acts.pack(fill="x", padx=16, pady=(12, 0))
        acts.columnconfigure((0, 1, 2), weight=1, uniform="a")
        self.b_record = self.button(acts, "", self.on_record_button, "ghost", height=44)
        self.b_play = self.button(acts, "", self.on_play_button, "primary", height=44)
        self.b_stop = self.button(acts, tr("stop"), self.stop_all, "ghost", height=44)
        for i, b in enumerate((self.b_record, self.b_play, self.b_stop)):
            b.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 5, 0 if i == 2 else 5))

        # StatTiles
        stats = ctk.CTkFrame(page, fg_color="transparent")
        stats.pack(fill="x", padx=16, pady=(10, 0))
        stats.columnconfigure((0, 1, 2), weight=1, uniform="s")
        self.stat_vals = {}
        for i, (key, label) in enumerate((("events", tr("stat_events")), ("length", tr("stat_length")),
                                          ("loops", tr("stat_loops")))):
            tile = self.card(stats)
            tile.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 5, 0 if i == 2 else 5))
            self.eyebrow(tile, label).pack(fill="x", padx=14, pady=(12, 2))
            v = self.text(tile, "0", "body700", 18)
            v.pack(fill="x", padx=14, pady=(0, 12))
            self.stat_vals[key] = v

        # Playback
        self.section(page, tr("playback"))
        pb = self.card(page)
        pb.pack(fill="x", padx=16)
        grid = ctk.CTkFrame(pb, fg_color="transparent")
        grid.pack(fill="x", padx=14, pady=14)
        grid.columnconfigure((0, 1), weight=1, uniform="f")
        fields = [
            (tr("repeat"), self.v_loops), (tr("wait_between"), self.v_delay),
            (tr("speed"), self.v_speed), (tr("humanize"), self.v_humanize),
            (tr("stop_after"), self.v_stop_after),
        ]
        for i, (label, var) in enumerate(fields):
            self.field(grid, label, var, 130).grid(row=i // 2, column=i % 2, sticky="w", pady=(0 if i < 2 else 14, 0))
        self.hint(pb, tr("playback_hint")).pack(fill="x", padx=14, pady=(0, 14))

        # Macro
        self.section(page, tr("macro"))
        mrow = ctk.CTkFrame(page, fg_color="transparent")
        mrow.pack(fill="x", padx=16)
        mrow.columnconfigure((0, 1), weight=1, uniform="m")
        self.b_save = self.button(mrow, tr("save"), self.save_macro)
        self.b_load = self.button(mrow, tr("load"), self.load_macro)
        self.b_preset = self.button(mrow, tr("preset"), self.load_preset, "soft")
        self.b_clear = self.button(mrow, tr("clear"), self.clear_macro)
        for i, b in enumerate((self.b_save, self.b_load, self.b_preset, self.b_clear)):
            b.grid(row=i // 2, column=i % 2, sticky="ew", padx=(0 if i % 2 == 0 else 5, 0 if i % 2 else 5),
                   pady=(0 if i < 2 else 10, 0))
        self.hint(page, tr("macro_hint")).pack(fill="x", padx=16, pady=(10, 0))
        self.home_hotkeys = self.hint(page, "")
        self.home_hotkeys.pack(fill="x", padx=16, pady=(6, 20))

    # ---------------------------------------------------------------- events
    def _build_events(self, page):
        head = ctk.CTkFrame(page, fg_color="transparent")
        head.pack(fill="x", padx=16, pady=(14, 10))
        self.text(head, tr("events_title"), "display600", 19).pack(side="left")
        self.ev_count = self.text(head, "", "body", 13, "muted")
        self.ev_count.pack(side="right")

        tools = ctk.CTkFrame(page, fg_color="transparent")
        tools.pack(fill="x", padx=16, side="bottom", pady=(0, 14))
        self.hint(tools, tr("events_hint")).pack(fill="x", pady=(10, 0), side="bottom")
        trow = ctk.CTkFrame(tools, fg_color="transparent")
        trow.pack(fill="x", side="bottom", pady=(10, 0))
        self.button(trow, tr("trim_start"), self.trim_start, "soft").pack(side="left", padx=(0, 8))
        self.button(trow, tr("undo"), self.undo).pack(side="left", padx=(0, 8))
        self.b_delete = self.button(trow, tr("delete_selected"), self.delete_selected)
        self.b_delete.pack(side="left")
        caprow = ctk.CTkFrame(tools, fg_color="transparent")
        caprow.pack(fill="x", side="bottom", pady=(10, 0))
        self.text(caprow, tr("cap_label"), "body", 14).pack(side="left")
        self.entry(caprow, self.v_cap, 64).pack(side="left", padx=8)
        self.text(caprow, tr("seconds_short"), "body", 14, "muted").pack(side="left")
        self.button(caprow, tr("apply"), self.cap_gaps).pack(side="right")

        # Editor for the selected event
        ed = self.card(tools)
        ed.pack(fill="x", side="bottom")
        self.eyebrow(ed, tr("selected_event")).pack(fill="x", padx=14, pady=(12, 0))
        self.ev_desc = self.text(ed, tr("nothing_selected"), "body600", 15)
        self.ev_desc.pack(fill="x", padx=14, pady=(2, 8))
        frow = ctk.CTkFrame(ed, fg_color="transparent")
        frow.pack(fill="x", padx=14)
        for col, (label, var, cmd) in enumerate(((tr("time_s"), self.v_ev_time, self.apply_time),
                                                 (tr("pause_before_s"), self.v_ev_gap, self.apply_gap))):
            box = ctk.CTkFrame(frow, fg_color="transparent")
            box.grid(row=0, column=col, sticky="w", padx=(0, 18))
            self.eyebrow(box, label).pack(fill="x", pady=(0, 6))
            line = ctk.CTkFrame(box, fg_color="transparent")
            line.pack(anchor="w")
            e = self.entry(line, var, 90)
            e.pack(side="left")
            e.bind("<Return>", lambda _e, c=cmd: c())
            self.button(line, tr("set"), cmd, "primary", height=36).pack(side="left", padx=(6, 0))
        self.switch(ed, tr("move_following"), self.v_move_following, command=lambda: None).pack(
            anchor="w", padx=14, pady=(12, 14))

        # The event list
        lst = self.card(page, radius=R_LIST)
        lst.pack(fill="both", expand=True, padx=16, pady=(0, 10))
        inner = ctk.CTkFrame(lst, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=8, pady=8)
        self.tree = ttk.Treeview(inner, columns=("t", "gap", "ev"), show="headings", style="Ubi.Treeview",
                                 selectmode="extended")
        self.tree.heading("t", text=tr.upper(tr("col_time")))
        self.tree.heading("gap", text=tr.upper(tr("col_gap")))
        self.tree.heading("ev", text=tr.upper(tr("col_event")), anchor="w")
        self.tree.column("t", width=78, anchor="e", stretch=False)
        self.tree.column("gap", width=78, anchor="e", stretch=False)
        self.tree.column("ev", width=240)
        sb = ctk.CTkScrollbar(inner, command=self.tree.yview, button_color=C["surface2"],
                              button_hover_color=C["outline"])
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._on_select())
        self.tree.bind("<Delete>", lambda e: self.delete_selected())

    def _style_tree(self):
        mode = ctk.get_appearance_mode()
        self._mode_seen = mode
        p = lambda k: th.pick(mode, C[k])  # noqa: E731
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Ubi.Treeview", background=p("surface"), fieldbackground=p("surface"),
                        foreground=p("ink"), rowheight=28, borderwidth=0, relief="flat",
                        font=(th.family("body"), 10))
        style.map("Ubi.Treeview", background=[("selected", p("accent_soft"))],
                  foreground=[("selected", p("accent"))])
        style.configure("Ubi.Treeview.Heading", background=p("surface"), foreground=p("muted"),
                        relief="flat", borderwidth=0, font=(th.family("mono500"), 8))
        style.map("Ubi.Treeview.Heading", background=[("active", p("surface2"))])
        style.layout("Ubi.Treeview", [("Ubi.Treeview.treearea", {"sticky": "nswe"})])

    # ---------------------------------------------------------------- settings
    def _settings_block(self, page, title):
        self.section(page, title)
        blk = self.card(page)
        blk.pack(fill="x", padx=16)
        return blk

    def _build_settings(self, page):
        self.section(page, tr("language"), pady=(14, 10))
        self.segmented(page, [("en", "English"), ("tr", "Türkçe")], self.settings["lang"], self.set_language).pack(
            fill="x", padx=16)

        self.section(page, tr("theme"))
        self.theme_seg = self.segmented(
            page, [("system", tr("theme_system")), ("light", tr("theme_light")), ("dark", tr("theme_dark"))],
            self.settings["theme"], self.set_theme)
        self.theme_seg.pack(fill="x", padx=16)

        blk = self._settings_block(page, tr("hotkeys"))
        self.hk_labels = {}
        for i, (which, label) in enumerate((("record", tr("hk_record")), ("play", tr("hk_play")))):
            row = ctk.CTkFrame(blk, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=(14 if i == 0 else 8, 14 if i == 1 else 0))
            self.text(row, label, "body", 15).pack(side="left")
            self.button(row, tr("change"), lambda w=which: self.begin_capture(w), height=32).pack(side="right")
            chip = ctk.CTkLabel(row, text="", fg_color=C["surface2"], corner_radius=8, height=30, width=70,
                                text_color=C["ink"], font=th.font("mono500", 13))
            chip.pack(side="right", padx=10)
            self.hk_labels[which] = chip
        self.hint(page, tr("hotkeys_hint")).pack(fill="x", padx=16, pady=(8, 0))

        blk = self._settings_block(page, tr("recording"))
        self.switch(blk, tr("record_moves"), self.v_record_moves).pack(anchor="w", padx=14, pady=(14, 0))
        self.switch(blk, tr("auto_trim"), self.v_auto_trim).pack(anchor="w", padx=14, pady=(12, 0))
        row = ctk.CTkFrame(blk, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=14)
        self.text(row, tr("countdown"), "body", 15, wraplength=300).pack(side="left")
        e = self.entry(row, self.v_countdown, 64)
        e.pack(side="right")
        e.bind("<FocusOut>", lambda _e: self._save_settings())

        blk = self._settings_block(page, tr("playback"))
        self.switch(blk, tr("focus_game"), self.v_focus_game).pack(anchor="w", padx=14, pady=(14, 0))
        self.switch(blk, tr("move_to_clicks"), self.v_move_clicks).pack(anchor="w", padx=14, pady=14)
        self.hint(page, tr("focus_hint")).pack(fill="x", padx=16, pady=(8, 0))

        self._build_background(page)

        blk = self._settings_block(page, tr("window"))
        self.switch(blk, tr("topmost"), self.v_topmost, command=self._on_topmost).pack(anchor="w", padx=14, pady=14)

        blk = self._settings_block(page, tr("storage"))
        row = ctk.CTkFrame(blk, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=14)
        self.text(row, tr("storage_text"), "body", 13, "muted", wraplength=260).pack(side="left")
        self.button(row, tr("open_folder"), self.open_folder, height=34).pack(side="right")

        self.text(page, f"UbiMacro {__version__}", "mono", 11, "muted").pack(fill="x", padx=16, pady=(18, 20))
        self._refresh_hotkey_labels()

    def _build_background(self, page):
        blk = self._settings_block(page, tr("background"))
        sw = self.switch(blk, tr("bg_switch"), self.v_background, command=self._on_background)
        sw.pack(anchor="w", padx=14, pady=(14, 0))
        row = ctk.CTkFrame(blk, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(12, 0))
        self.eyebrow(row, tr("bg_window")).pack(anchor="w", pady=(0, 6))
        line = ctk.CTkFrame(row, fg_color="transparent")
        line.pack(fill="x")
        self.win_menu = ctk.CTkOptionMenu(
            line, variable=self.v_bg_window, values=[self.v_bg_window.get()], height=36, corner_radius=R_CONTROL,
            fg_color=C["surface2"], button_color=C["surface2"], button_hover_color=C["line"], text_color=C["ink"],
            dropdown_fg_color=C["surface"], dropdown_hover_color=C["surface2"], dropdown_text_color=C["ink"],
            font=th.font("body", 14), dropdown_font=th.font("body", 13), dynamic_resizing=False, width=250,
            command=lambda _v: self._save_settings())
        self.win_menu.pack(side="left", fill="x", expand=True)
        self.button(line, tr("refresh"), self.refresh_windows, height=36).pack(side="left", padx=(8, 0))
        self.switch(blk, tr("fake_focus"), self.v_fake_focus).pack(anchor="w", padx=14, pady=(12, 0))
        self.b_bg_test = self.button(blk, tr("bg_test"), self.run_background_test, "primary")
        self.b_bg_test.pack(fill="x", padx=14, pady=14)
        self.hint(page, tr("bg_hint") if IS_WINDOWS else tr("bg_windows_only")).pack(fill="x", padx=16, pady=(8, 0))
        if not IS_WINDOWS:
            for w in (sw, self.win_menu, self.b_bg_test):
                w.configure(state="disabled")
        self.refresh_windows(quiet=True)

    def refresh_windows(self, quiet=False):
        titles = []
        for _hwnd, title in list_windows():
            if title not in titles and title != self.root.title():
                titles.append(title)
        current = self.v_bg_window.get()
        roblox = [t for t in titles if t.lower() == "roblox"]
        others = sorted((t for t in titles if t.lower() != "roblox"), key=str.lower)
        values = roblox + others
        if current not in values:
            values.insert(0, current)
        self.win_menu.configure(values=values[:40] or ["Roblox"])
        if not quiet:
            self.show_toast(tr("toast_windows", n=len(titles)))

    def _on_background(self):
        self._save_settings()
        if self.settings["background"]:
            self.show_toast(tr("toast_bg_on", name=self.settings["bg_window"]))
        self._set_state(self.state)

    def _make_backend(self, force_background=False):
        """The input backend for the next playback, or None if it can't start."""
        s = self._read_vars()
        if not (s["background"] or force_background):
            return self.backend
        if not IS_WINDOWS:
            self.show_toast(tr("bg_windows_only"))
            return None
        hwnd = find_window([s["bg_window"]])
        if not hwnd:
            self.show_toast(tr("toast_no_window", name=s["bg_window"]))
            return None
        from .background import MessageBackend

        return MessageBackend(hwnd, fake_focus=s["fake_focus"])

    def run_background_test(self):
        """Count down, then send a jump, a 1 s walk and three clicks to the
        chosen window with window messages, while another window is in front."""
        if self.state != "idle":
            self.show_toast(tr("toast_busy"))
            return
        if self._make_backend(force_background=True) is None:
            return
        self._start_countdown(5, self._run_background_test_now)
        self.hero_sub.configure(text=tr("sub_test_switch"))
        self.show_page("home")

    def _run_background_test_now(self):
        backend = self._make_backend(force_background=True)
        if backend is None:
            return
        space, w = make_key("space", 0x20), make_key("w", 0x57)
        events = [
            {"t": 0.0, "type": "key", "action": "down", "key": space},
            {"t": 0.15, "type": "key", "action": "up", "key": space},
            {"t": 0.6, "type": "key", "action": "down", "key": w},
            {"t": 1.6, "type": "key", "action": "up", "key": w},
        ]
        for i in range(3):
            t = 2.0 + i * 0.4
            events += [{"t": t, "type": "click", "action": "down", "button": "left"},
                       {"t": t + 0.08, "type": "click", "action": "up", "button": "left"}]
        self._testing = True
        self.player.backend = backend
        self._loop_now, self._loop_total, self._loops_done = 1, 1, 0
        self._play_started = time.time()
        if self.player.start(events, loops=1):
            self._set_state("playing", tr("st_testing"))

    # ================================================================ small updates
    def show_toast(self, message, ms=2600):
        if self._toast_job:
            self.root.after_cancel(self._toast_job)
        self.toast.configure(text=f"   {message}   ")
        self.toast.place(relx=0.5, rely=1.0, y=-18, anchor="s")
        self.toast.lift()
        self._toast_job = self.root.after(ms, self._hide_toast)

    def _hide_toast(self):
        self._toast_job = None
        self.toast.place_forget()

    def _refresh_hotkey_labels(self):
        for which, chip in self.hk_labels.items():
            if self.capturing == which:
                chip.configure(text=tr("press_key"), fg_color=C["accent_soft"], text_color=C["accent"])
            else:
                chip.configure(text=display_name(self.settings[which + "_hotkey"]), fg_color=C["surface2"],
                               text_color=C["ink"])
        self.home_hotkeys.configure(text=tr("hotkeys_line", rec=self._hk("record"), play=self._hk("play")))

    def _hk(self, which):
        return display_name(self.settings[which + "_hotkey"])

    def _refresh_events(self):
        n = len(self.events)
        if hasattr(self, "tree"):
            self.tree.delete(*self.tree.get_children())
            limit = 5000
            prev = 0.0
            for i, ev in enumerate(self.events[:limit]):
                gap = ev["t"] - prev
                prev = ev["t"]
                self.tree.insert("", "end", iid=str(i),
                                 values=(f"{ev['t']:.3f}", f"+{gap:.3f}", self.describe(ev)))
            self.ev_count.configure(text=tr("n_events", n=n) + (f" · {tr('showing_first', n=limit)}" if n > limit else ""))
            self._on_select()
        if hasattr(self, "stat_vals"):
            self.stat_vals["events"].configure(text=str(n))
            self.stat_vals["length"].configure(text=tr("secs", s=f"{macro.duration(self.events):.1f}"))
            self.stat_vals["loops"].configure(text=str(self._loops_done))

    def describe(self, e):
        typ = e.get("type")
        if typ == "key":
            return tr("ev_key_" + e.get("action", "down"), key=display_name(e.get("key")))
        if typ == "click":
            btn = tr("btn_" + e.get("button", "left")) if tr.has("btn_" + e.get("button", "")) else e.get("button")
            return tr("ev_click_" + e.get("action", "down"), btn=btn, x=e.get("x"), y=e.get("y"))
        if typ == "move":
            return tr("ev_move", x=e.get("x"), y=e.get("y"))
        if typ == "scroll":
            return tr("ev_scroll", dy=e.get("dy"), dx=e.get("dx"))
        return str(e)

    def _set_state(self, state, title=None, sub=None):
        self.state = state
        pills = {
            "idle": (tr("pill_ready"), "accent_soft", "accent"),
            "countdown": (tr("pill_wait"), "warn_bg", "warn"),
            "recording": ("● " + tr("pill_rec"), "loss_bg", "loss"),
            "playing": ("▶ " + tr("pill_on"), "gain_bg", "gain"),
        }
        ptext, pbg, pfg = pills[state]
        self.pill.configure(text=f"  {ptext}  ", fg_color=C[pbg], text_color=C[pfg])
        titles = {"idle": tr("st_ready"), "countdown": tr("st_get_ready"), "recording": tr("st_recording"),
                  "playing": tr("st_playing")}
        subs = {
            "idle": tr("sub_ready", rec=self._hk("record"), play=self._hk("play")) if self.events
            else tr("sub_empty", rec=self._hk("record")),
            "countdown": tr("sub_switch"),
            "recording": tr("sub_recording", rec=self._hk("record")),
            "playing": tr("sub_playing", play=self._hk("play")),
        }
        if state == "idle" and self.events and self.settings.get("background"):
            subs["idle"] = tr("sub_ready_bg", play=self._hk("play"), name=self.settings["bg_window"])
        self.hero_title.configure(text=title or titles[state])
        self.hero_sub.configure(text=sub or subs[state])
        self.b_record.configure(
            text=("■ " + tr("stop_recording")) if state == "recording" else ("● " + tr("record")),
            state="normal" if state != "playing" else "disabled",
            text_color=C["loss"] if state != "playing" else C["muted"])
        play_off = state in ("recording", "countdown")
        self.b_play.configure(text=("■ " + tr("stop_playing")) if state == "playing" else ("▶ " + tr("play")),
                              state="disabled" if play_off else "normal",
                              fg_color=C["surface2"] if play_off else C["accent"])
        self.b_stop.configure(state="normal" if state != "idle" else "disabled")

    # ================================================================ theme / language / window
    def set_theme(self, mode):
        self.settings["theme"] = mode
        ctk.set_appearance_mode(mode)
        self.root.after(50, self._style_tree)
        self._save_settings()

    def toggle_theme(self):
        mode = "light" if ctk.get_appearance_mode().lower() == "dark" else "dark"
        self.set_theme(mode)
        self.theme_seg.set({"light": tr("theme_light"), "dark": tr("theme_dark")}[mode])

    def set_language(self, lang):
        if lang == tr.lang:
            return
        self.settings["lang"] = lang
        tr.set_lang(lang)
        self._save_settings()
        self.rebuild()

    def _on_topmost(self):
        self._apply_topmost()
        self._save_settings()

    def _apply_topmost(self):
        try:
            self.root.attributes("-topmost", bool(self.v_topmost.get()))
        except tk.TclError:
            pass

    def open_folder(self):
        path = os.path.join(self.cfg_dir, "macros")
        try:
            if sys.platform == "win32":
                os.startfile(path)  # noqa: S606
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception:
            self.show_toast(path)

    # ================================================================ keyboard listener
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

    # ================================================================ event loop
    def _poll(self):
        try:
            while True:
                self._handle(self.q.get_nowait())
        except queue.Empty:
            pass
        if self.state == "recording":
            self.hero_sub.configure(text=tr("sub_recording_n", rec=self._hk("record"), n=self.recorder.event_count))
        elif self.state == "playing":
            total = "∞" if self._loop_total == 0 else str(self._loop_total)
            if not self._testing:
                where = (" · " + tr("in_background", name=self.settings["bg_window"])) if self.settings.get(
                    "background") else ""
                self.hero_sub.configure(text=tr("sub_playing_n", play=self._hk("play"), n=self._loop_now,
                                                total=total, time=fmt_duration(time.time() - self._play_started))
                                        + where)
        if ctk.get_appearance_mode() != self._mode_seen:  # "System" theme flipped
            self._style_tree()
        self.root.after(100, self._poll)

    def _handle(self, msg):
        kind = msg[0]
        if kind == "hotkey":
            self.on_hotkey(msg[1])
        elif kind == "captured":
            self.finish_capture(msg[1])
        elif kind == "progress":
            self._loop_now, self._loop_total = msg[1], msg[2]
            self._loops_done = msg[1] - 1
            self.stat_vals["loops"].configure(text=str(self._loops_done))
        elif kind == "finished":
            done, err, reason = msg[1], msg[2], msg[3]
            self._loops_done = done
            self.stat_vals["loops"].configure(text=str(done))
            if self._testing:
                self._testing = False
                self._set_state("idle")
                self.show_toast(tr("toast_test_done"), ms=9000)
            elif self.state == "playing":
                self._set_state("idle")
                if reason == "time_limit":
                    self.show_toast(tr("toast_time_limit", n=done))
                elif reason == "done":
                    self.show_toast(tr("toast_finished", n=done))
            if err:
                messagebox.showerror("UbiMacro", tr("err_playback", err=err))

    # ================================================================ hotkeys
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
            elif self.state == "countdown":
                self.cancel_countdown()
            elif self.state == "idle":
                self.start_playback()  # the game already has focus when you use the hotkey

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
                self.show_toast(tr("toast_hotkey_taken"))
            else:
                self.settings[which + "_hotkey"] = d
                self._hotkeys_down.add(which)  # the key is still physically down
                self._save_settings()
                self.show_toast(tr("toast_hotkey_set", key=display_name(d)))
        self._refresh_hotkey_labels()
        self._set_state(self.state)

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
        self._set_state("countdown", tr("st_starts_in", n=self._countdown_left))
        self._countdown_left -= 1
        self._countdown_job = self.root.after(1000, self._tick_countdown)

    def cancel_countdown(self):
        if self._countdown_job:
            self.root.after_cancel(self._countdown_job)
            self._countdown_job = None
        self._countdown_then = None
        self._set_state("idle")

    # ================================================================ recording
    def on_record_button(self):
        if self.state == "idle":
            self.start_recording(countdown=True)
        elif self.state == "recording":
            self.stop_recording(from_button=True)
        elif self.state == "countdown":
            self.cancel_countdown()

    def start_recording(self, countdown):
        # No "overwrite?" dialog: it would pop up over the game. If nothing is
        # recorded the previous macro is kept, and Undo brings it back anyway.
        s = self._read_vars()
        if countdown and s["countdown"] > 0:
            self._start_countdown(s["countdown"], self._begin_recording)
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
        self._set_state("idle")
        if not events:
            self.show_toast(tr("toast_nothing"))
            return
        if self.settings.get("auto_trim", True):
            events = macro.trim_start(events)
        self._replace_events(events)
        self._set_state("idle")
        self.show_toast(tr("toast_recorded", n=len(events)))

    # ================================================================ playback
    def on_play_button(self):
        if self.state == "playing":
            self.stop_playback()
        elif self.state == "idle":
            if not self.events:
                self.show_toast(tr("toast_no_macro"))
                return
            s = self._read_vars()
            if s["background"]:
                self.start_playback()
            elif s["focus_game"] and focus_game():
                self.root.after(350, self.start_playback)   # let the game take focus first
            elif s["countdown"] > 0:
                self._start_countdown(s["countdown"], self.start_playback)
            else:
                self.start_playback()

    def start_playback(self):
        if not self.events:
            self.show_toast(tr("toast_no_macro"))
            return
        s = self._read_vars()
        self._save_settings()
        backend = self._make_backend()
        if backend is None:
            return
        self.player.backend = backend
        self._loop_now, self._loop_total, self._loops_done = 1, s["loops"], 0
        self._play_started = time.time()
        ok = self.player.start(
            self.events, loops=s["loops"], speed=s["speed"], loop_delay=s["loop_delay"],
            humanize=s["humanize"] / 100.0, move_to_clicks=s["move_to_clicks"],
            stop_after=s["stop_after"] * 60.0,
        )
        if ok:
            self._set_state("playing")

    def stop_playback(self):
        self.player.stop(wait=True)
        self._set_state("idle")
        self.show_toast(tr("toast_stopped"))

    def stop_all(self):
        if self.state == "recording":
            self.stop_recording(from_button=True)
        elif self.state == "countdown":
            self.cancel_countdown()
        elif self.state == "playing":
            self.stop_playback()

    # ================================================================ editing
    def _replace_events(self, events, undoable=True):
        if undoable:
            self.undo_stack.append(self.events)
            del self.undo_stack[:-UNDO_LIMIT]
        self.events = events
        self._refresh_events()
        self._autosave()

    def _editable(self):
        if self.state != "idle":
            self.show_toast(tr("toast_busy"))
            return False
        return True

    def undo(self):
        if isinstance(self.root.focus_get(), (tk.Entry,)):
            return  # let Ctrl+Z work inside text fields
        if not self._editable():
            return
        if not self.undo_stack:
            self.show_toast(tr("toast_nothing_undo"))
            return
        self.events = self.undo_stack.pop()
        self._refresh_events()
        self._autosave()
        self._set_state("idle")
        self.show_toast(tr("toast_undone"))

    def _selected(self):
        return sorted(int(i) for i in self.tree.selection())

    def _on_select(self):
        sel = self._selected() if hasattr(self, "tree") else []
        if not sel or sel[0] >= len(self.events):
            self.ev_desc.configure(text=tr("nothing_selected"))
            self.v_ev_time.set("")
            self.v_ev_gap.set("")
            return
        i = sel[0]
        e = self.events[i]
        prev = self.events[i - 1]["t"] if i > 0 else 0.0
        label = f"#{i + 1} · {self.describe(e)}"
        if len(sel) > 1:
            label += " · " + tr("n_selected", n=len(sel))
        self.ev_desc.configure(text=label)
        self.v_ev_time.set(f"{e['t']:.3f}")
        self.v_ev_gap.set(f"{e['t'] - prev:.3f}")

    def _reselect(self, index):
        if 0 <= index < len(self.events):
            self.tree.selection_set(str(index))
            self.tree.see(str(index))

    def apply_time(self):
        sel = self._selected()
        if not sel or not self._editable():
            return
        t = num(self.v_ev_time, None, float, 0.0)
        if t is None:
            self.show_toast(tr("toast_bad_number"))
            return
        target = self.events[sel[0]]
        self._replace_events(macro.set_time(self.events, sel[0], t, bool(self.v_move_following.get())))
        idx = next((i for i, e in enumerate(self.events) if e.get("type") == target.get("type")
                    and abs(e["t"] - round(t, 4)) < 1e-6), sel[0])
        self._reselect(idx)
        self.show_toast(tr("toast_time_set", t=f"{t:.3f}"))

    def apply_gap(self):
        sel = self._selected()
        if not sel or not self._editable():
            return
        g = num(self.v_ev_gap, None, float, 0.0)
        if g is None:
            self.show_toast(tr("toast_bad_number"))
            return
        self._replace_events(macro.set_gap(self.events, sel[0], g))
        self._reselect(sel[0])
        self.show_toast(tr("toast_gap_set", t=f"{g:.3f}"))

    def trim_start(self):
        if not self.events or not self._editable():
            return
        before = self.events[0]["t"]
        if before <= 0:
            self.show_toast(tr("toast_no_delay"))
            return
        self._replace_events(macro.trim_start(self.events))
        self.show_toast(tr("toast_trimmed", t=f"{before:.3f}"))

    def cap_gaps(self):
        if not self.events or not self._editable():
            return
        cap = num(self.v_cap, None, float, 0.0)
        if cap is None:
            self.show_toast(tr("toast_bad_number"))
            return
        old = macro.duration(self.events)
        new_events = macro.cap_gaps(self.events, cap)
        saved = old - macro.duration(new_events)
        if saved <= 0:
            self.show_toast(tr("toast_no_long_pauses", t=f"{cap:g}"))
            return
        self._save_settings()
        self._replace_events(new_events)
        self.show_toast(tr("toast_capped", t=f"{saved:.1f}"))

    def delete_selected(self):
        sel = self._selected()
        if not sel or not self._editable():
            return
        self._replace_events(macro.delete(self.events, sel))
        self._reselect(min(sel[0], len(self.events) - 1))
        self.show_toast(tr("toast_deleted", n=len(sel)))

    # ================================================================ macro files
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

    def save_macro(self):
        if not self.events:
            self.show_toast(tr("toast_nothing_save"))
            return
        path = filedialog.asksaveasfilename(
            parent=self.root, initialdir=os.path.join(self.cfg_dir, "macros"), defaultextension=".json",
            filetypes=[(tr("file_type"), "*.json"), (tr("all_files"), "*.*")])
        if not path:
            return
        s = self._read_vars()
        try:
            macro.save(path, self.events, {k: s[k] for k in PLAYBACK_KEYS})
            self.show_toast(tr("toast_saved", name=os.path.basename(path)))
        except OSError as e:
            messagebox.showerror("UbiMacro", tr("err_save", err=e))

    def load_macro(self):
        if not self._editable():
            return
        path = filedialog.askopenfilename(
            parent=self.root, initialdir=os.path.join(self.cfg_dir, "macros"),
            filetypes=[(tr("file_type"), "*.json"), (tr("all_files"), "*.*")])
        if not path:
            return
        try:
            events, settings = macro.load(path)
        except (OSError, ValueError) as e:
            messagebox.showerror("UbiMacro", tr("err_load", err=e))
            return
        for key, var in (("loops", self.v_loops), ("speed", self.v_speed), ("loop_delay", self.v_delay),
                         ("humanize", self.v_humanize), ("stop_after", self.v_stop_after)):
            if key in settings:
                var.set(str(settings[key]))
        if "move_to_clicks" in settings:
            self.v_move_clicks.set(bool(settings["move_to_clicks"]))
        self._replace_events(events)
        self._set_state("idle")
        self.show_toast(tr("toast_loaded", name=os.path.basename(path)))

    def load_preset(self):
        if not self._editable():
            return
        if num(self.v_delay, 0.0) < 1:
            self.v_delay.set("60")
        self.v_loops.set("0")
        self._replace_events(macro.anti_afk_preset())
        self._set_state("idle")
        self.show_toast(tr("toast_preset"))

    def clear_macro(self):
        """Ubi pattern: the first click arms the button, the second one clears."""
        if not self.events or not self._editable():
            return
        if self._armed_job is None:
            self.b_clear.configure(text=tr("clear_confirm"), fg_color=C["loss_bg"], text_color=C["loss"],
                                   border_color=C["loss"], hover_color=C["loss_bg"])
            self._armed_job = self.root.after(3000, self._disarm_clear)
            return
        self._disarm_clear()
        self._replace_events([])
        self._set_state("idle")
        self.show_toast(tr("toast_cleared"))

    def _disarm_clear(self):
        if self._armed_job:
            self.root.after_cancel(self._armed_job)
        self._armed_job = None
        try:
            self.b_clear.configure(text=tr("clear"), fg_color=C["surface"], text_color=C["ink"],
                                   border_color=C["outline"], hover_color=C["surface2"])
        except tk.TclError:
            pass

    # ================================================================ shutdown
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
