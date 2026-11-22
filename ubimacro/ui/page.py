"""Base class for the four pages."""

import tkinter as tk

import customtkinter as ctk

from .. import theme as th
from ..theme import C


class Page:
    scrollable = False

    def __init__(self, app, parent):
        self.app = app
        self.s = app.settings
        if self.scrollable:
            self.frame = ctk.CTkScrollableFrame(parent, fg_color="transparent", corner_radius=0)
        else:
            self.frame = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=0)
        self.build()

    def build(self):
        pass

    def refresh(self):
        pass

    def refresh_state(self):
        pass

    def on_show(self):
        pass

    def tick(self):
        pass

    def theme_changed(self):
        pass

    # helpers
    def color(self, key):
        return th.pick(ctk.get_appearance_mode(), C[key])

    def bind_number(self, var, key, cast=float, lo=None, hi=None, after=None):
        """Keep a settings value in step with an entry while you type."""
        from ..app import num

        def on_write(*_a):
            v = num(var.get(), None, cast, lo, hi)
            if v is not None and v != self.s.get(key):
                self.s[key] = v
                self.app.save_settings()
                if after:
                    after()

        var.trace_add("write", on_write)

    @staticmethod
    def num_text(v):
        if isinstance(v, float) and v.is_integer():
            return str(int(v))
        return str(v)


def canvas(parent, height):
    return tk.Canvas(parent, height=height, highlightthickness=0, bd=0)
