"""Library: every saved macro, its hotkey, favourites, and row actions."""

import tkinter as tk

import customtkinter as ctk

from . import kit
from .icons import icon
from .page import Page
from ..i18n import tr
from ..keys import display_name
from ..library import ago
from ..theme import C, R_CONTROL, R_LIST


class LibraryPage(Page):
    def build(self):
        f = self.frame
        self.filter = "all"
        top = kit.frame(f)
        top.pack(fill="x", padx=16, pady=(16, 0))
        kit.button(top, "+ " + tr("record_new"), self._record_new, "primary", height=40).pack(side="right")
        sbox = ctk.CTkFrame(top, fg_color=C["surface"], border_width=1, border_color=C["outline"],
                            corner_radius=R_CONTROL, height=40)
        sbox.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkLabel(sbox, text="", image=icon("search", "muted"), width=20).pack(side="left", padx=(10, 0))
        self.search = ctk.CTkEntry(sbox, placeholder_text=tr("search"), border_width=0, fg_color="transparent",
                                   text_color=C["ink"], placeholder_text_color=C["muted"],
                                   font=kit.th.font("body", 15), height=36)
        self.search.pack(side="left", fill="x", expand=True, padx=(4, 8))
        self.search.bind("<KeyRelease>", lambda _e: self.refresh())

        frow = kit.frame(f)
        frow.pack(fill="x", padx=16, pady=(10, 0))
        self.chips = kit.Chips(frow, [("all", tr("filter_all")), ("fav", tr("filter_fav")),
                                      ("builtin", tr("filter_builtin"))], "all", self._set_filter)
        self.chips.frame.pack(side="left")
        kit.link_button(frow, tr("import"), self.app.import_macro).pack(side="right")

        self.list_area = ctk.CTkScrollableFrame(f, fg_color="transparent", corner_radius=0)
        self.list_area.pack(fill="both", expand=True, pady=(4, 0))

    def _record_new(self):
        self.app.ui.show_page("home")
        if self.s["mode"] != "macro":
            self.app.ui.pages["home"].set_mode("macro")
        self.app.on_record_button()

    def _set_filter(self, key):
        self.filter = key
        self.refresh()

    def on_show(self):
        self.refresh()

    def refresh(self):
        for w in self.list_area.winfo_children():
            w.destroy()
        area = self.list_area
        q = self.search.get().strip().lower()
        entries = [e for e in self.app.library.entries() if not q or q in (e.name or "").lower()]
        if self.filter == "fav":
            entries = [e for e in entries if e.favourite]
        if self.filter != "builtin":
            kit.section(area, tr("your_macros"), pady=(12, 10), padx=12)
            if entries:
                lst = kit.card(area, radius=R_LIST)
                lst.pack(fill="x", padx=12)
                for i, e in enumerate(entries):
                    self._row(lst, e, last=i == len(entries) - 1, first=i == 0)
            else:
                box = kit.card(area)
                box.pack(fill="x", padx=12)
                title = tr("no_results") if q or self.filter == "fav" else tr("empty_title")
                kit.text(box, title, "body600", 15).pack(fill="x", padx=14, pady=(13, 0))
                kit.text(box, tr("library_empty", rec=self.app.hk("record")), "body", 13, "muted",
                         wraplength=400).pack(fill="x", padx=14, pady=(2, 13))
        if self.filter != "fav" and (not q or q in tr("preset_name").lower()):
            kit.section(area, tr("builtin"), pady=(20, 10), padx=12)
            lst = kit.card(area, radius=R_LIST)
            lst.pack(fill="x", padx=12)
            row = kit.frame(lst)
            row.pack(fill="x", padx=14, pady=13)
            kit.tag(row, "AFK").pack(side="left")
            kit.text(row, "›", "body", 18, "muted").pack(side="right")
            box = kit.frame(row)
            box.pack(side="left", fill="x", expand=True, padx=12)
            kit.text(box, tr("preset_name"), "body600", 15).pack(fill="x")
            kit.text(box, tr("preset_sub"), "body", 13, "muted").pack(fill="x")
            kit.bind_click(row, self.app.add_preset)
        kit.hint(area, tr("library_hint"), wrap=430).pack(fill="x", padx=12, pady=(12, 0))
        if self.filter == "all" and not q:
            self._history(area)
        else:
            kit.frame(area).pack(pady=8)

    # ---------------------------------------------------------------- recent runs
    def _history(self, area):
        from datetime import datetime

        from ..app import fmt_int, fmt_length

        runs = self.app.history.entries()[:15]
        kit.section(area, tr("recent_runs"), pady=(22, 10), padx=12,
                    action=tr("clear") if runs else None, action_cmd=self.app.clear_history)
        if not runs:
            kit.hint(area, tr("recent_empty"), wrap=430).pack(fill="x", padx=12, pady=(0, 16))
            return
        lst = kit.card(area, radius=R_LIST)
        lst.pack(fill="x", padx=12, pady=(0, 16))
        pills = {"done": ("end_done", "gain_bg", "gain"), "time_limit": ("end_time_limit", "gain_bg", "gain"),
                 "stopped": ("end_stopped", "surface2", "ink"), "closed": ("end_closed", "loss_bg", "loss"),
                 "disconnected": ("end_disconnected", "loss_bg", "loss"), "error": ("end_error", "loss_bg", "loss")}
        for i, r in enumerate(runs):
            row = kit.frame(lst)
            row.pack(fill="x", padx=14, pady=10)
            label, bg, fg = pills.get(r.get("end"), pills["stopped"])
            p = kit.pill(row)
            kit.set_pill(p, tr(label), bg, fg)
            p.pack(side="right")
            box = kit.frame(row)
            box.pack(side="left", fill="x", expand=True, padx=(0, 8))
            when = datetime.fromtimestamp(r.get("start", 0)).strftime("%d.%m.%Y %H:%M")
            kit.text(box, tr("run_title", name=r.get("name") or "?", time=fmt_length(r.get("seconds", 0))),
                     "body600", 15, wraplength=290).pack(fill="x")
            count = (tr("n_loops", n=fmt_int(r.get("loops", 0))) if r.get("kind") == "macro"
                     else tr("n_clicks", n=fmt_int(r.get("clicks", 0))))
            kit.text(box, f"{when} · {count}", "body", 13, "muted").pack(fill="x")
            if i < len(runs) - 1:
                ctk.CTkFrame(lst, height=1, fg_color=C["line"], corner_radius=0).pack(fill="x", padx=14)

    def refresh_history(self):
        self.refresh()

    def _row(self, parent, e, last, first=False):
        active = self.app.active is not None and self.app.active.id == e.id
        row = ctk.CTkFrame(parent, fg_color=C["accent_soft"] if active else "transparent", corner_radius=12)
        row.pack(fill="x", padx=5, pady=(5 if first else 0, 5 if last else 0))
        inner = kit.frame(row)
        inner.pack(fill="x", padx=9, pady=8)
        kit.tag(inner, e.initials(), active=active).pack(side="left")

        more = ctk.CTkButton(inner, text="", image=icon("more", "muted"), width=32, height=32, corner_radius=8,
                             fg_color="transparent", hover_color=C["surface2"])
        more.configure(command=lambda b=more, ent=e: self._menu(b, ent))
        more.pack(side="right")
        ctk.CTkButton(inner, text="", image=icon("star_on" if e.favourite else "star",
                                                  "accent" if e.favourite else "muted"),
                      width=32, height=32, corner_radius=8, fg_color="transparent", hover_color=C["surface2"],
                      command=lambda m=e.id: self.app.toggle_favourite(m)).pack(side="right")
        capturing = self.app.capturing == ("macro", e.id)
        if capturing:
            chip_text = tr("press_key")
        elif e.hotkey:
            chip_text = display_name(e.hotkey)
        else:
            chip_text = tr("set_key")
        chip = kit.key_chip(inner, chip_text, command=lambda m=e.id: self.app.begin_capture(("macro", m)))
        if capturing:
            chip.configure(fg_color=C["accent_soft"], text_color=C["accent"])
        elif not e.hotkey:
            chip.configure(fg_color="transparent", text_color=C["muted"], font=kit.th.font("body", 13))
        chip.pack(side="right", padx=(0, 4))

        box = kit.frame(inner)
        box.pack(side="left", fill="x", expand=True, padx=12)
        title = kit.frame(box)
        title.pack(fill="x")
        kit.text(title, e.name, "body600", 15).pack(side="left")
        if active:
            kit.text(title, tr.upper(tr("active")), "mono", 10, "accent").pack(side="left", padx=(6, 0))
        from ..app import fmt_length

        words = {"never": tr("used_never"), "today": tr("used_today"), "yesterday": tr("used_yesterday"),
                 "days": tr("used_days")}
        kit.text(box, tr("row_sub", n=e.count, length=fmt_length(e.length or 0), used=ago(e.last_used, words)),
                 "body", 13, "muted").pack(fill="x")
        kit.bind_click(box, lambda m=e.id: self.app.set_active(m))
        kit.bind_click(inner, lambda m=e.id: self.app.set_active(m))
        for w in (row, inner, box):
            w.bind("<Button-3>", lambda ev, ent=e: self._menu_at(ev.x_root, ev.y_root, ent))
        if not last:
            ctk.CTkFrame(parent, height=1, fg_color=C["line"], corner_radius=0).pack(fill="x", padx=14)

    def _menu(self, button, e):
        self._menu_at(button.winfo_rootx(), button.winfo_rooty() + button.winfo_height(), e)

    def _menu_at(self, x, y, e):
        m = tk.Menu(self.frame, tearoff=0, bg=self.color("surface"), fg=self.color("ink"),
                    activebackground=self.color("surface2"), activeforeground=self.color("ink"), bd=1,
                    font=(kit.th.family("body"), 10))
        m.add_command(label=tr("use_this"), command=lambda: self.app.set_active(e.id))
        m.add_command(label=tr("rename"), command=lambda: self.app.rename_macro(e.id))
        m.add_command(label=tr("duplicate"), command=lambda: self.app.duplicate_macro(e.id))
        m.add_command(label=tr("change_key"), command=lambda: self.app.begin_capture(("macro", e.id)))
        if e.hotkey:
            m.add_command(label=tr("remove_key"), command=lambda: self.app.clear_macro_hotkey(e.id))
        m.add_command(label=tr("export"), command=lambda: self.app.export_macro(e.id))
        m.add_separator()
        m.add_command(label=tr("delete"), foreground=self.color("loss"), command=lambda: self.app.delete_macro(e.id))
        try:
            m.tk_popup(x, y)
        finally:
            m.grab_release()
