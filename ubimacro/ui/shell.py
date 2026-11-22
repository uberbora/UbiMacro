"""The window frame: top bar, tabs, the four pages, toasts and mini mode."""

import tkinter as tk

import customtkinter as ctk

from . import kit
from .icons import icon
from ..i18n import tr
from ..theme import C, R_CONTROL

PAGES = ("home", "library", "events", "settings")


class Shell:
    def __init__(self, app):
        self.app = app
        self.root = app.root
        self._toast_job = None
        self.mini = None

    # ---- building --------------------------------------------------------
    def build(self):
        from .events_page import EventsPage
        from .home import HomePage
        from .library_page import LibraryPage
        from .settings_page import SettingsPage

        self.frame = kit.frame(self.root)
        self.frame.pack(fill="both", expand=True)

        top = kit.frame(self.frame)
        top.pack(fill="x", padx=16, pady=(14, 10))
        mark = kit.frame(top)
        mark.pack(side="left")
        kit.text(mark, "Ubi", "display800", 24).pack(side="left")
        kit.text(mark, "Macro", "display800", 24, "accent").pack(side="left")
        for name, cmd in (("theme", self.app_toggle_theme), ("mini", self.show_mini)):
            ctk.CTkButton(top, text="", image=icon(name), width=38, height=38, corner_radius=R_CONTROL,
                          fg_color=C["surface"], hover_color=C["surface2"], border_width=1,
                          border_color=C["outline"], command=cmd).pack(side="right", padx=(8, 0))

        self.tabs = kit.segmented(self.frame, [(p, tr("tab_" + p)) for p in PAGES], self.app.page, self.show_page,
                                  height=38)
        self.tabs.pack(fill="x", padx=16)

        self.pages = {
            "home": HomePage(self.app, self.frame),
            "library": LibraryPage(self.app, self.frame),
            "events": EventsPage(self.app, self.frame),
            "settings": SettingsPage(self.app, self.frame),
        }
        self.toast_label = ctk.CTkLabel(self.root, text="", fg_color=C["ink"], text_color=C["bg"], corner_radius=18,
                                        bg_color=C["bg"], height=36, font=kit.th.font("body600", 14))
        self._apply_topmost()
        self.show_page(self.app.page)
        self.refresh_all()

    def rebuild(self):
        if self._toast_job:
            self.root.after_cancel(self._toast_job)
            self._toast_job = None
        self.toast_label.destroy()
        self.frame.destroy()
        mini_open = self.mini is not None
        self.hide_mini()
        self.build()
        if mini_open:
            self.show_mini()

    def show_page(self, key):
        self.app.page = key
        label = self.tabs.keys[key]
        if self.tabs.get() != label:
            self.tabs.set(label)
        for k, page in self.pages.items():
            if k == key:
                page.frame.pack(fill="both", expand=True, pady=(6, 0))
                page.on_show()
            else:
                page.frame.pack_forget()

    # ---- refresh hooks the controller calls -----------------------------
    def refresh_all(self):
        for p in self.pages.values():
            p.refresh()
        self.refresh_state()

    def refresh_events(self):
        self.pages["home"].refresh_macro()
        self.pages["events"].refresh()
        self.pages["library"].refresh()

    def refresh_state(self):
        self.pages["home"].refresh_state()
        self.pages["events"].refresh_state()
        if self.mini:
            self.mini.refresh()

    def refresh_hotkeys(self):
        self.pages["settings"].refresh_hotkeys()
        self.pages["library"].refresh()
        self.pages["home"].refresh_state()

    def refresh_clicker(self):
        self.pages["home"].refresh_clicker()
        if self.mini:
            self.mini.refresh()

    def refresh_update(self):
        self.pages["home"].refresh_update()

    def tick(self):
        if self.app.state in ("playing", "clicking", "recording"):
            self.pages["home"].tick()
            if self.mini:
                self.mini.refresh()

    def theme_changed(self):
        for p in self.pages.values():
            p.theme_changed()

    # ---- theme / window --------------------------------------------------
    def app_toggle_theme(self):
        mode = "light" if ctk.get_appearance_mode().lower() == "dark" else "dark"
        self.app.set_theme(mode)
        self.pages["settings"].sync_theme(mode)

    def _apply_topmost(self):
        try:
            self.root.attributes("-topmost", bool(self.app.settings["topmost"]))
        except tk.TclError:
            pass

    def apply_topmost(self):
        self._apply_topmost()

    def show_main(self):
        self.hide_mini()
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
        except tk.TclError:
            pass

    # ---- toast -----------------------------------------------------------
    def toast(self, message, ms=2600):
        if self._toast_job:
            self.root.after_cancel(self._toast_job)
        self.toast_label.configure(text=f"   {message}   ")
        self.toast_label.place(relx=0.5, rely=1.0, y=-18, anchor="s")
        self.toast_label.lift()
        self._toast_job = self.root.after(ms, self._hide_toast)
        if self.mini:
            self.mini.flash(message)

    def _hide_toast(self):
        self._toast_job = None
        try:
            self.toast_label.place_forget()
        except tk.TclError:
            pass

    # ---- mini mode -------------------------------------------------------
    def show_mini(self):
        from .mini import MiniWindow

        if self.mini is None:
            self.mini = MiniWindow(self.app)
        self.root.withdraw()

    def hide_mini(self):
        if self.mini is not None:
            self.mini.destroy()
            self.mini = None

    def toggle_mini(self):
        if self.mini is not None:
            self.show_main()
        else:
            self.show_mini()
