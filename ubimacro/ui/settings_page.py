"""Settings: language, theme, hotkeys, safety, recording, playback,
notifications, window, updates and storage."""

import tkinter as tk

import customtkinter as ctk

from . import kit
from .page import Page
from .. import __version__
from ..i18n import tr
from ..keys import display_name

HOTKEY_ROWS = (("record", "hk_record"), ("play", "hk_play"), ("clicker", "hk_clicker"), ("mini", "hk_mini"),
               ("stopall", "hk_stopall"))


class SettingsPage(Page):
    scrollable = True

    def build(self):
        from ..app import IS_WINDOWS, PAUSE_SUPPORTED

        f, s = self.frame, self.s
        self.vars = {}

        top = kit.frame(f)
        top.pack(fill="x", padx=16, pady=(14, 0))
        top.columnconfigure((0, 1), weight=1, uniform="lt")
        lb = kit.frame(top)
        lb.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        kit.eyebrow(lb, tr("language")).pack(fill="x", pady=(0, 6))
        kit.segmented(lb, [("en", "English"), ("tr", "Türkçe")], s["lang"], self.app.set_language,
                      size=13).pack(fill="x")
        tb = kit.frame(top)
        tb.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        kit.eyebrow(tb, tr("theme")).pack(fill="x", pady=(0, 6))
        self.theme_seg = kit.segmented(tb, [("system", tr("theme_system")), ("light", tr("theme_light")),
                                            ("dark", tr("theme_dark"))], s["theme"], self.app.set_theme, size=13)
        self.theme_seg.pack(fill="x")

        # hotkeys
        kit.section(f, tr("hotkeys"))
        blk = kit.card(f)
        blk.pack(fill="x", padx=16)
        self.hk_chips = {}
        for i, (which, label) in enumerate(HOTKEY_ROWS):
            row = kit.frame(blk)
            row.pack(fill="x", padx=14, pady=10)
            kit.text(row, tr(label), "body", 15).pack(side="left")
            kit.button(row, tr("change_short"), lambda w=which: self.app.begin_capture(("app", w)), height=32,
                       size=13).pack(side="right")
            chip = kit.key_chip(row, "", danger=which == "stopall")
            chip.pack(side="right", padx=10)
            self.hk_chips[which] = chip
            if i < len(HOTKEY_ROWS) - 1:
                kit.divider(blk)
        kit.hint(f, tr("hotkeys_hint")).pack(fill="x", padx=16, pady=(8, 0))

        # safety
        kit.section(f, tr("safety"))
        blk = kit.card(f)
        blk.pack(fill="x", padx=16)
        sw = self._switch_row(blk, "pause_on_input", tr("pause_input"),
                              tr("pause_input_sub") if PAUSE_SUPPORTED else tr("windows_only"), last=True)
        if not PAUSE_SUPPORTED:
            sw.configure(state="disabled")
        row = kit.frame(blk)
        row.pack(fill="x", padx=14, pady=(0, 11))
        kit.text(row, tr("resume_after"), "body", 13, "muted").pack(side="left")
        self.v_resume = tk.StringVar(value=self.num_text(s["resume_after"]))
        self.bind_number(self.v_resume, "resume_after", float, 1, 600)
        kit.entry(row, self.v_resume, 64, 32).pack(side="right")
        kit.divider(blk)
        sw = self._switch_row(blk, "notify_closed", tr("closed_title"),
                              tr("closed_sub") if IS_WINDOWS else tr("windows_only"))
        if not IS_WINDOWS:
            sw.configure(state="disabled")
        sw = self._switch_row(blk, "only_front", tr("front_title"),
                              tr("front_sub") if IS_WINDOWS else tr("windows_only"), last=True)
        if not IS_WINDOWS:
            sw.configure(state="disabled")

        # recording
        kit.section(f, tr("recording"))
        blk = kit.card(f)
        blk.pack(fill="x", padx=16)
        self._switch_row(blk, "record_moves", tr("record_moves"), None)
        self._switch_row(blk, "auto_trim", tr("auto_trim"), tr("auto_trim_sub"))
        self._number_row(blk, "countdown", tr("countdown"), int, 0, 30)
        kit.divider(blk)
        self._number_row(blk, "cap_gap", tr("cap_limit"), float, 0, 3600)

        # playback
        kit.section(f, tr("playback"))
        blk = kit.card(f)
        blk.pack(fill="x", padx=16)
        self._switch_row(blk, "focus_game", tr("focus_game"), tr("focus_game_sub"))
        self._switch_row(blk, "move_to_clicks", tr("move_to_clicks"), tr("move_to_clicks_sub"), last=True)

        # notifications
        kit.section(f, tr("notifications"))
        blk = kit.card(f)
        blk.pack(fill="x", padx=16)
        self._switch_row(blk, "sounds", tr("sounds"), tr("sounds_sub"))
        box = kit.frame(blk)
        box.pack(fill="x", padx=14, pady=(11, 11))
        kit.eyebrow(box, tr("webhook")).pack(fill="x", pady=(0, 6))
        line = kit.frame(box)
        line.pack(fill="x")
        self.v_webhook = tk.StringVar(value=s.get("webhook", ""))
        self.v_webhook.trace_add("write", lambda *_a: self.app.set_setting("webhook", self.v_webhook.get().strip()))
        kit.entry(line, self.v_webhook, 200, placeholder="https://discord.com/api/webhooks/…").pack(
            side="left", fill="x", expand=True)
        kit.button(line, tr("test"), self.app.test_webhook, height=36, size=13).pack(side="left", padx=(8, 0))
        kit.text(box, tr("webhook_sub"), "body", 12, "muted", wraplength=400).pack(fill="x", pady=(6, 0))
        kit.divider(blk)
        self._switch_row(blk, "notify_finished", tr("notify_finished"), tr("notify_finished_sub"), last=True)

        # window
        kit.section(f, tr("window"))
        blk = kit.card(f)
        blk.pack(fill="x", padx=16)
        self._switch_row(blk, "topmost", tr("topmost"), None, after=self.app.ui.apply_topmost)
        self._switch_row(blk, "start_mini", tr("start_mini"), None)
        sw = self._switch_row(blk, "close_to_tray", tr("close_to_tray"),
                              tr("close_to_tray_sub") if self.app.tray.available else tr("tray_missing"), last=True)
        if not self.app.tray.available:
            sw.configure(state="disabled")

        # updates
        kit.section(f, tr("updates"))
        blk = kit.card(f)
        blk.pack(fill="x", padx=16)
        self._switch_row(blk, "check_updates", tr("check_updates"), None)
        row = kit.frame(blk)
        row.pack(fill="x", padx=14, pady=11)
        kit.text(row, tr("version_x", v=__version__), "body", 15).pack(side="left")
        kit.button(row, tr("check_now"), self.app.check_updates_now, height=32, size=13).pack(side="right")

        # storage
        kit.section(f, tr("storage"))
        blk = kit.card(f)
        blk.pack(fill="x", padx=16)
        row = kit.frame(blk)
        row.pack(fill="x", padx=14, pady=13)
        kit.button(row, tr("open_folder"), self.app.open_folder, height=32, size=13).pack(side="right")
        kit.text(row, tr("storage_text"), "body", 13, "muted", wraplength=270).pack(side="left")
        kit.text(f, f"UbiMacro {__version__}", "mono", 11, "muted").pack(fill="x", padx=16, pady=(18, 20))
        self.refresh_hotkeys()

    def _switch_row(self, parent, key, title, sub, last=False, after=None):
        var = tk.BooleanVar(value=bool(self.s.get(key)))
        self.vars[key] = var

        def changed():
            self.app.set_setting(key, bool(var.get()))
            if after:
                after()

        return kit.switch_row(parent, title, sub, var, changed, last=last)

    def _number_row(self, parent, key, title, cast, lo, hi):
        row = kit.frame(parent)
        row.pack(fill="x", padx=14, pady=11)
        var = tk.StringVar(value=self.num_text(self.s[key]))
        self.bind_number(var, key, cast, lo, hi)
        kit.entry(row, var, 64, 32).pack(side="right")
        kit.text(row, title, "body", 15, wraplength=330).pack(side="left")

    def refresh_hotkeys(self):
        from ..theme import C

        for which, chip in self.hk_chips.items():
            if self.app.capturing == ("app", which):
                chip.configure(text=tr("press_key"), fg_color=C["accent_soft"], text_color=C["accent"])
            else:
                danger = which == "stopall"
                chip.configure(text=display_name(self.app.hotkey(which)),
                               fg_color=C["loss_bg"] if danger else C["surface2"],
                               text_color=C["loss"] if danger else C["ink"])

    def refresh(self):
        self.refresh_hotkeys()

    def sync_theme(self, mode):
        self.theme_seg.set(self.theme_seg.keys[mode])
