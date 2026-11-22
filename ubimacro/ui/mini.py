"""Mini mode: a small always-on-top bar to keep over the game."""

import sys
import tkinter as tk

import customtkinter as ctk

from . import kit
from .icons import icon
from ..i18n import tr
from ..theme import C, R_CONTROL

KEY = "#010203"  # made transparent on Windows so the bar's corners are round


class MiniWindow:
    def __init__(self, app):
        self.app = app
        self.win = ctk.CTkToplevel(app.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        if sys.platform == "win32":
            self.win.configure(fg_color=KEY)
            try:
                self.win.attributes("-transparentcolor", KEY)
            except tk.TclError:
                pass
        else:
            self.win.configure(fg_color=C["bg"])
        x = app.settings.get("mini_x")
        y = app.settings.get("mini_y")
        if x is None or y is None:
            x = app.root.winfo_screenwidth() - 440
            y = 40
        self.win.geometry(f"420x76+{int(x)}+{int(y)}")
        self._flash_job = None

        self.bar = ctk.CTkFrame(self.win, fg_color=C["surface"], corner_radius=18, border_width=1,
                                border_color=C["line"], bg_color=KEY if sys.platform == "win32" else C["bg"])
        self.bar.pack(fill="both", expand=True)
        inner = kit.frame(self.bar)
        inner.pack(fill="both", expand=True, padx=(14, 12), pady=10)
        self.pill = kit.pill(inner)
        self.pill.pack(side="left")
        ctk.CTkButton(inner, text="", image=icon("expand"), width=44, height=44, corner_radius=R_CONTROL,
                      fg_color="transparent", hover_color=C["surface2"], border_width=1, border_color=C["outline"],
                      command=app.ui.show_main).pack(side="right")
        self.action = kit.RoundButton(inner, self._action)
        self.action.pack(side="right", padx=(0, 8))
        box = kit.frame(inner)
        box.pack(side="left", fill="both", expand=True, padx=12)
        self.big = kit.text(box, "", "body600", 15)
        self.big.pack(fill="x")
        self.sub = kit.text(box, "", "body", 12, "muted")
        self.sub.pack(fill="x")
        for w in (self.bar, inner, box, self.big, self.sub, self.pill):
            w.bind("<ButtonPress-1>", self._start_move)
            w.bind("<B1-Motion>", self._move)
            w.bind("<ButtonRelease-1>", self._end_move)
        self.refresh()

    # dragging
    def _start_move(self, e):
        self._dx, self._dy = e.x_root - self.win.winfo_x(), e.y_root - self.win.winfo_y()

    def _move(self, e):
        self.win.geometry(f"+{e.x_root - self._dx}+{e.y_root - self._dy}")

    def _end_move(self, _e):
        self.app.settings["mini_x"], self.app.settings["mini_y"] = self.win.winfo_x(), self.win.winfo_y()
        self.app.save_settings()

    def _action(self):
        a = self.app
        if a.state == "playing":
            a.stop_playback()
        elif a.state == "clicking":
            a.stop_clicker()
        elif a.state in ("recording", "countdown"):
            a.stop_all()
        elif a.settings["mode"] == "clicker":
            a.on_clicker_button()
        else:
            a.on_play_button()

    def flash(self, message):
        """Show a toast inside the bar for a moment."""
        if self._flash_job:
            self.win.after_cancel(self._flash_job)
        self.sub.configure(text=message)
        self._flash_job = self.win.after(2500, self._end_flash)

    def _end_flash(self):
        self._flash_job = None
        self.refresh()

    def refresh(self):
        from ..app import fmt_clock, fmt_int

        a, s = self.app, self.app.settings
        st = a.state
        info = a.run_info()
        if st in ("playing", "clicking") and a.paused:
            kit.set_pill(self.pill, "❚❚ " + tr("pill_paused"), "warn_bg", "warn")
        else:
            label, bg, fg = {
                "idle": (tr("pill_ready"), "accent_soft", "accent"),
                "countdown": (tr("pill_wait"), "warn_bg", "warn"),
                "recording": ("● " + tr("pill_rec"), "loss_bg", "loss"),
                "playing": ("▶ " + tr("pill_on"), "gain_bg", "gain"),
                "clicking": ("▶ " + tr("pill_clicking"), "gain_bg", "gain"),
            }[st]
            kit.set_pill(self.pill, label, bg, fg)
        running = st in ("playing", "clicking", "recording", "countdown")
        self.action.set_glyph("stop" if running else "play")
        if st in ("playing", "clicking"):
            self.big.configure(text=fmt_clock(a.run_elapsed()), font=kit.th.font("display800", 22))
            if st == "playing":
                sub = tr("mini_playing", n=info["loops"] + 1, key=a.hk("play"))
            else:
                sub = tr("mini_clicking", n=fmt_int(info["clicks"]), key=a.hk("clicker"))
        else:
            self.big.configure(font=kit.th.font("body600", 15))
            if st == "countdown":
                self.big.configure(text=a.countdown_text or "")
                sub = a.countdown_sub or tr("sub_switch")
            elif st == "recording":
                self.big.configure(text=tr("st_recording"))
                sub = tr("mini_recording", key=a.hk("record"))
            elif s["mode"] == "clicker":
                self.big.configure(text=tr("mini_clicker_title", n=s["cps"]))
                sub = tr("mini_clicker_sub", key=a.hk("clicker"))
            else:
                name = a.active.name if a.active else tr("empty_title")
                self.big.configure(text=name)
                sub = tr("mini_macro_sub", key=a.hk("play"), rec=a.hk("record"))
        if not self._flash_job:
            self.sub.configure(text=sub)

    def destroy(self):
        try:
            self.win.destroy()
        except tk.TclError:
            pass
