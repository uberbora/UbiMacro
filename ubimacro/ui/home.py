"""Home: status hero, Macro / Auto-clicker modes, stats, playback settings."""

import tkinter as tk

import customtkinter as ctk

from . import kit
from .icons import icon
from .page import Page, canvas
from .. import macro
from ..i18n import tr
from ..theme import C, R_CONTROL, R_HERO


class HomePage(Page):
    scrollable = True

    def build(self):
        f = self.frame
        self.editing_playback = False

        # update banner (shown only when a newer release exists)
        self.banner_holder = kit.frame(f)
        self.banner_holder.pack(fill="x")

        # hero
        hero = ctk.CTkFrame(f, fg_color=C["accent"], corner_radius=R_HERO)
        hero.pack(fill="x", padx=16, pady=(8, 0))
        row = kit.frame(hero)
        row.pack(fill="x", padx=20, pady=(18, 0))
        kit.eyebrow(row, tr("status"), "accent_ink").pack(side="left")
        self.pill = kit.pill(row)
        self.pill.pack(side="right")
        self.hero_big = kit.text(hero, "", "display800", 34, "accent_ink")
        self.hero_big.pack(fill="x", padx=20, pady=(6, 0))
        self.hero_sub = kit.text(hero, "", "body", 13, "accent_ink", wraplength=420)
        self.hero_sub.pack(fill="x", padx=20, pady=(2, 18))

        self.mode_seg = kit.segmented(f, [("macro", tr("mode_macro")), ("clicker", tr("mode_clicker"))],
                                      self.s["mode"], self.set_mode)
        self.mode_seg.pack(fill="x", padx=16, pady=(12, 0))

        self.macro_panel = kit.frame(f)
        self.clicker_panel = kit.frame(f)
        self._build_macro_panel(self.macro_panel)
        self._build_clicker_panel(self.clicker_panel)
        self._show_mode()

    # ---------------------------------------------------------------- macro panel
    def _build_macro_panel(self, p):
        self.active_card = kit.card(p)
        self.active_card.pack(fill="x", padx=16, pady=(12, 0))

        acts = kit.frame(p)
        acts.pack(fill="x", padx=16, pady=(12, 0))
        acts.columnconfigure((0, 1, 2), weight=1, uniform="a")
        self.b_record = kit.button(acts, "", self.app.on_record_button, height=44)
        self.b_play = kit.button(acts, "", self.app.on_play_button, "primary", height=44)
        self.b_mini = kit.button(acts, tr("mini_mode"), lambda: self.app.ui.show_mini(), height=44)
        for i, b in enumerate((self.b_record, self.b_play, self.b_mini)):
            b.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 5, 0 if i == 2 else 5))

        row, self.stats = kit.stat_tiles(p, [("loops", tr("stat_loops")), ("clicks", tr("stat_clicks")),
                                             ("today", tr("stat_today"))])
        row.pack(fill="x", padx=16, pady=(10, 0))

        _row, self.pb_link = kit.section(p, tr("playback"), action=tr("edit"), action_cmd=self.toggle_playback)
        self.pb_holder = kit.frame(p)
        self.pb_holder.pack(fill="x", padx=16)
        from ..app import PAUSE_SUPPORTED

        self.pb_hint = kit.hint(p, tr("pause_hint") if PAUSE_SUPPORTED else tr("playback_hint"))
        self.pb_hint.pack(fill="x", padx=16, pady=(10, 20))

        self.v_loops = tk.StringVar(value=self.num_text(self.s["loops"]))
        self.v_delay = tk.StringVar(value=self.num_text(self.s["loop_delay"]))
        self.v_speed = tk.StringVar(value=self.num_text(self.s["speed"]))
        self.v_humanize = tk.StringVar(value=self.num_text(self.s["humanize"]))
        self.v_stop_after = tk.StringVar(value=self.num_text(self.s["stop_after"]))
        self.bind_number(self.v_loops, "loops", int, 0)
        self.bind_number(self.v_delay, "loop_delay", float, 0)
        self.bind_number(self.v_speed, "speed", float, 0.1, 10)
        self.bind_number(self.v_humanize, "humanize", int, 0, 50)
        self.bind_number(self.v_stop_after, "stop_after", float, 0)

    def _render_active(self):
        for w in self.active_card.winfo_children():
            w.destroy()
        ent = self.app.active
        if not ent:
            box = kit.frame(self.active_card)
            box.pack(fill="x", padx=14, pady=13)
            kit.text(box, tr("empty_title"), "body600", 15).pack(fill="x")
            kit.text(box, tr("empty_text", rec=self.app.hk("record")), "body", 13, "muted",
                     wraplength=400).pack(fill="x", pady=(2, 10))
            kit.button(box, tr("preset"), self.app.add_preset, "soft", height=34).pack(anchor="w")
            return
        row = kit.frame(self.active_card)
        row.pack(fill="x", padx=14, pady=(13, 0))
        kit.tag(row, ent.initials()).pack(side="left")
        ctk.CTkButton(row, text=tr("change"), command=lambda: self.app.ui.show_page("library"),
                      fg_color="transparent", hover_color=C["surface2"], text_color=C["accent"],
                      font=kit.th.font("body600", 14), width=0, height=28).pack(side="right")
        box = kit.frame(row)
        box.pack(side="left", fill="x", expand=True, padx=12)
        kit.text(box, ent.name, "body600", 15).pack(fill="x")
        sub = tr("macro_sub", n=len(self.app.events), length=_length(self.app.events))
        if ent.hotkey:
            sub += " · " + tr("hotkey_x", key=kit_display(ent.hotkey))
        kit.text(box, sub, "body", 13, "muted").pack(fill="x")
        self.strip = canvas(self.active_card, 34)
        self.strip.pack(fill="x", padx=14, pady=(12, 13))
        self.strip.bind("<Configure>", lambda e: self.draw_strip())
        self.draw_strip()

    def draw_strip(self):
        c = getattr(self, "strip", None)
        if c is None or not c.winfo_exists():
            return
        c.delete("all")
        c.configure(bg=self.color("surface"))
        w, h = max(c.winfo_width(), 10), 34
        c.create_rectangle(0, 0, w, h, fill=self.color("surface2"), outline="")
        events = self.app.events
        length = max(macro.duration(events), 0.001)
        bars, singles, _l = macro.pairs(events)
        for lane, d, u in bars:
            x0 = 4 + (w - 8) * events[d]["t"] / length
            x1 = max(x0 + 3, 4 + (w - 8) * events[u]["t"] / length)
            if lane[0] == "btn":
                c.create_rectangle(x0, 20, x1, 28, fill=self.color("accent"), outline="")
            else:
                c.create_rectangle(x0, 6, x1, 14, fill=self.color("muted"), outline="")
        for i in singles:
            x = 4 + (w - 8) * events[i]["t"] / length
            c.create_rectangle(x, 20, x + 2, 28, fill=self.color("outline"), outline="")

    def toggle_playback(self):
        self.editing_playback = not self.editing_playback
        self.render_playback()

    def render_playback(self):
        for w in self.pb_holder.winfo_children():
            w.destroy()
        self.pb_link.configure(text=tr("done") if self.editing_playback else tr("edit"))
        s = self.s
        if self.editing_playback:
            c = kit.card(self.pb_holder)
            c.pack(fill="x")
            grid = kit.frame(c)
            grid.pack(fill="x", padx=14, pady=14)
            grid.columnconfigure((0, 1), weight=1, uniform="f")
            fields = [(tr("repeat"), self.v_loops), (tr("wait_between"), self.v_delay), (tr("speed"), self.v_speed),
                      (tr("humanize"), self.v_humanize), (tr("stop_after"), self.v_stop_after)]
            for i, (label, var) in enumerate(fields):
                kit.field(grid, label, var, 130).grid(row=i // 2, column=i % 2, sticky="w",
                                                      pady=(0 if i < 2 else 14, 0))
            kit.hint(c, tr("playback_fields_hint")).pack(fill="x", padx=14, pady=(0, 14))
            return
        chips = [tr("chip_forever") if s["loops"] == 0 else tr("chip_times", n=s["loops"]),
                 tr("chip_wait", s=self.num_text(s["loop_delay"])),
                 tr("chip_speed", x=self.num_text(s["speed"]))]
        if s["humanize"]:
            chips.append(tr("chip_humanize", n=s["humanize"]))
        if s["stop_after"]:
            chips.append(tr("chip_stop_after", t=_minutes(s["stop_after"])))
        for start in range(0, len(chips), 3):
            row = kit.frame(self.pb_holder)
            row.pack(fill="x", pady=(0 if start == 0 else 6, 0))
            for label in chips[start:start + 3]:
                ctk.CTkLabel(row, text=f"  {label}  ", fg_color=C["surface2"], corner_radius=15, height=30,
                             text_color=C["ink"], font=kit.th.font("body600", 13)).pack(side="left", padx=(0, 6))

    # ---------------------------------------------------------------- clicker panel
    def _build_clicker_panel(self, p):
        c = kit.card(p, radius=18)
        c.pack(fill="x", padx=16, pady=(12, 0))
        top = kit.frame(c)
        top.pack(fill="x", padx=14, pady=(14, 0))
        for name, d in (("plus", 1), ("minus", -1)):
            ctk.CTkButton(top, text="", image=icon(name), width=44, height=44, corner_radius=R_CONTROL,
                          fg_color=C["surface"], hover_color=C["surface2"], border_width=1,
                          border_color=C["outline"], command=lambda d=d: self.app.change_cps(d)).pack(
                side="right", padx=(8, 0))
        box = kit.frame(top)
        box.pack(side="left", fill="x", expand=True)
        kit.eyebrow(box, tr("speed_label")).pack(fill="x")
        line = kit.frame(box)
        line.pack(fill="x")
        self.cps_label = kit.text(line, "", "display800", 32)
        self.cps_label.pack(side="left")
        kit.text(line, tr("clicks_a_second"), "body", 15, "muted").pack(side="left", padx=(8, 0), pady=(8, 0))

        grid = kit.frame(c)
        grid.pack(fill="x", padx=14, pady=(14, 0))
        grid.columnconfigure((0, 1), weight=1, uniform="g")
        b1 = kit.frame(grid)
        b1.grid(row=0, column=0, sticky="w")
        kit.eyebrow(b1, tr("button_label")).pack(fill="x", pady=(0, 6))
        self.btn_chips = kit.Chips(b1, [("left", tr("btn_left")), ("right", tr("btn_right"))],
                                   self.s["click_button"], lambda k: self.app.set_setting("click_button", k))
        self.btn_chips.frame.pack(anchor="w")
        b2 = kit.frame(grid)
        b2.grid(row=0, column=1, sticky="w")
        kit.eyebrow(b2, tr("key_works_as")).pack(fill="x", pady=(0, 6))
        self.mode_chips = kit.Chips(b2, [("toggle", tr("on_off")), ("hold", tr("hold"))], self.s["click_mode"],
                                    self._set_click_mode)
        self.mode_chips.frame.pack(anchor="w")

        wbox = kit.frame(c)
        wbox.pack(fill="x", padx=14, pady=(14, 0))
        kit.eyebrow(wbox, tr("click_where")).pack(fill="x", pady=(0, 6))
        self.where_chips = kit.Chips(wbox, [("mouse", tr("where_mouse")), ("point", tr("where_point"))],
                                     self.s["click_where"], self._set_where)
        self.where_chips.frame.pack(anchor="w")
        self.spot_row = kit.frame(wbox)
        self.spot_label = kit.text(self.spot_row, "", "body", 13, "muted")
        self.spot_label.pack(side="left")
        kit.button(self.spot_row, tr("pick_spot"), self.app.pick_spot, height=32, size=13).pack(side="right")

        line = ctk.CTkFrame(c, height=1, fg_color=C["line"], corner_radius=0)
        line.pack(fill="x", padx=14, pady=(14, 0))
        self.v_vary = tk.BooleanVar(value=self.s["click_vary"])
        vrow = kit.frame(c)
        vrow.pack(fill="x", padx=14, pady=12)
        kit.switch(vrow, "", self.v_vary, lambda: (self.app.set_setting("click_vary", bool(self.v_vary.get())),
                                                   self.refresh_clicker())).pack(side="right")
        vb = kit.frame(vrow)
        vb.pack(side="left", fill="x", expand=True)
        kit.text(vb, tr("vary_title"), "body", 15).pack(fill="x")
        self.vary_sub = kit.text(vb, "", "body", 13, "muted", wraplength=330)
        self.vary_sub.pack(fill="x")

        acts = kit.frame(p)
        acts.pack(fill="x", padx=16, pady=(12, 0))
        acts.columnconfigure(0, weight=2)
        acts.columnconfigure(1, weight=1)
        self.b_click = kit.button(acts, "", self.app.on_clicker_button, "primary", height=44)
        self.b_click.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        kit.button(acts, tr("mini_mode"), lambda: self.app.ui.show_mini(), height=44).grid(row=0, column=1,
                                                                                            sticky="ew", padx=(5, 0))
        row, self.cstats = kit.stat_tiles(p, [("clicks", tr("stat_clicks")), ("today", tr("stat_today"))])
        row.pack(fill="x", padx=16, pady=(10, 0))
        kit.hint(p, tr("clicker_hint")).pack(fill="x", padx=16, pady=(10, 20))

    def _set_click_mode(self, k):
        self.app.set_setting("click_mode", k)
        self.refresh_state()

    def _set_where(self, k):
        self.app.set_setting("click_where", k)
        self.refresh_clicker()

    # ---------------------------------------------------------------- modes
    def set_mode(self, mode):
        if self.app.state in ("playing", "clicking", "recording", "countdown"):
            self.mode_seg.set(self.mode_seg.keys[self.s["mode"]])
            self.app.show_toast(tr("toast_busy"))
            return
        self.app.set_setting("mode", mode)
        if self.mode_seg.get() != self.mode_seg.keys[mode]:
            self.mode_seg.set(self.mode_seg.keys[mode])
        self._show_mode()
        self.refresh_state()

    def _show_mode(self):
        if self.s["mode"] == "clicker":
            self.macro_panel.pack_forget()
            self.clicker_panel.pack(fill="x")
        else:
            self.clicker_panel.pack_forget()
            self.macro_panel.pack(fill="x")

    # ---------------------------------------------------------------- refresh
    def refresh(self):
        self.refresh_macro()
        self.refresh_clicker()
        self.render_playback()
        self.refresh_update()
        self.refresh_state()

    def refresh_macro(self):
        self._render_active()

    def refresh_clicker(self):
        s = self.s
        self.cps_label.configure(text=str(s["cps"]))
        self.btn_chips.set(s["click_button"])
        self.mode_chips.set(s["click_mode"])
        self.where_chips.set(s["click_where"])
        if s["click_where"] == "point":
            pt = s.get("click_point")
            self.spot_label.configure(text=tr("spot_at", x=pt[0], y=pt[1]) if pt else tr("spot_none"))
            self.spot_row.pack(fill="x", pady=(8, 0))
        else:
            self.spot_row.pack_forget()
        cps = s["cps"]
        if s["click_vary"]:
            lo, hi = max(1, round(cps * 0.85)), max(1, round(cps * 1.15))
            self.vary_sub.configure(text=tr("vary_on", lo=lo, hi=hi))
        else:
            self.vary_sub.configure(text=tr("vary_off", n=cps))

    def refresh_update(self):
        for w in self.banner_holder.winfo_children():
            w.destroy()
        info = self.app.update_info
        if not info:
            return
        b = ctk.CTkFrame(self.banner_holder, fg_color=C["warn_bg"], corner_radius=14)
        b.pack(fill="x", padx=16, pady=(8, 0))
        ctk.CTkButton(b, text=tr("download"), command=self.app.open_update, fg_color="transparent",
                      hover_color=C["warn_bg"], text_color=C["warn"], font=kit.th.font("body600", 14), width=0,
                      height=28).pack(side="right", padx=8, pady=8)
        kit.text(b, tr("update_banner", tag=info[0]), "body600", 14, "warn").pack(side="left", padx=14, pady=10)

    def refresh_state(self):
        a, s = self.app, self.s
        st = a.state
        clicker_mode = s["mode"] == "clicker"
        # pill
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
        self._hero_text()
        # macro buttons
        self.b_record.configure(
            text=("■ " + tr("stop_recording")) if st == "recording" else ("● " + tr("record")),
            state="normal" if st in ("idle", "recording", "countdown") else "disabled",
            text_color=C["loss"] if st in ("idle", "recording", "countdown") else C["muted"])
        play_off = st not in ("idle", "playing")
        self.b_play.configure(text=("■ " + tr("stop")) if st == "playing" else ("▶ " + tr("play")),
                              state="disabled" if play_off else "normal",
                              fg_color=C["surface2"] if play_off else C["accent"])
        click_off = st not in ("idle", "clicking")
        self.b_click.configure(text=("■ " + tr("stop_clicking")) if st == "clicking" else ("▶ " + tr("start_clicking")),
                               state="disabled" if click_off else "normal",
                               fg_color=C["surface2"] if click_off else C["accent"])
        self.tick()

    def _hero_text(self):
        a, s = self.app, self.s
        st = a.state
        big, sub, timer = "", "", False
        info = a.run_info()
        if st == "countdown":
            big = a.countdown_text or ""
            sub = a.countdown_sub or tr("sub_switch")
        elif st == "recording":
            big = tr("st_recording")
            sub = tr("sub_recording_n", n=a.recorder.event_count, rec=a.hk("record"))
        elif st in ("playing", "clicking"):
            from ..app import fmt_clock, fmt_int

            timer = True
            big = fmt_clock(a.run_elapsed())
            if a.paused:
                sub = tr("sub_paused_input") if a.pause_reason == "input" else tr("sub_paused_front")
            elif st == "playing":
                total = "∞" if not info["total"] else str(info["total"])
                sub = tr("sub_playing", name=info["name"], n=info["loops"] + 1, total=total, play=a.hk("play"))
            else:
                sub = tr("sub_clicking", n=fmt_int(info["clicks"]), cps=s["cps"], key=a.hk("clicker"))
            if s["stop_after"] and not a.paused:
                left = max(0, s["stop_after"] * 60 - a.run_elapsed())
                sub += " · " + tr("sub_left", t=fmt_clock(left))
        elif s["mode"] == "clicker":
            big = tr("st_ready_click")
            sub = tr("sub_ready_hold" if s["click_mode"] == "hold" else "sub_ready_click", key=a.hk("clicker"))
        else:
            big = tr("st_ready")
            sub = (tr("sub_ready", rec=a.hk("record"), play=a.hk("play"), stop=a.hk("stopall")) if a.events
                   else tr("sub_empty", rec=a.hk("record")))
        size = 44 if timer else 34
        if getattr(self, "_big_size", None) != size:
            self._big_size = size
            self.hero_big.configure(font=kit.th.font("display800", size))
        self.hero_big.configure(text=big)
        self.hero_sub.configure(text=sub)

    def tick(self):
        from ..app import fmt_int

        a = self.app
        info = a.run_info()
        self.stats["loops"].configure(text=fmt_int(info["loops"]))
        self.stats["clicks"].configure(text=fmt_int(info["clicks"]))
        mins = int(a.today_seconds() // 60)
        today = tr("hour_min", h=mins // 60, m=mins % 60) if mins >= 60 else tr("mins", m=mins)
        self.stats["today"].configure(text=today)
        self.cstats["clicks"].configure(text=fmt_int(info["clicks"]))
        self.cstats["today"].configure(text=today)
        if a.state in ("playing", "clicking", "recording", "countdown"):
            self._hero_text()

    def theme_changed(self):
        self.draw_strip()


def _length(events):
    from ..app import fmt_length

    return fmt_length(macro.duration(events))


def _minutes(m):
    from ..app import fmt_length

    return fmt_length(m * 60)


def kit_display(hk):
    from ..keys import display_name

    return display_name(hk)
