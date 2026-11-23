"""Ubi widgets for CustomTkinter: cards, labels, buttons, chips, switches,
segmented controls. Every colour is a (light, dark) pair from theme.C."""

import tkinter as tk

import customtkinter as ctk

from .. import theme as th
from ..i18n import tr
from ..theme import C, R_CARD, R_CONTROL

MONO_SPACING = 1  # Tk has no letter-spacing; mono labels are uppercase instead


def card(parent, radius=R_CARD, fill="surface", border=True):
    return ctk.CTkFrame(parent, fg_color=C[fill], corner_radius=radius,
                        border_width=1 if border else 0, border_color=C["line"])


def frame(parent):
    # height=1: an empty CTkFrame would otherwise ask for 200 px
    return ctk.CTkFrame(parent, fg_color="transparent", corner_radius=0, height=1)


def text(parent, value, role="body", size=15, color="ink", **kw):
    return ctk.CTkLabel(parent, text=value, font=th.font(role, size), text_color=C[color],
                        anchor=kw.pop("anchor", "w"), justify=kw.pop("justify", "left"), **kw)


def eyebrow(parent, value, color="muted"):
    return text(parent, tr.upper(value), "mono", 11, color)


def hint(parent, value, wrap=440):
    return text(parent, value, "body", 12, "muted", wraplength=wrap)


def section(parent, title, pady=(20, 10), padx=16, action=None, action_cmd=None):
    row = frame(parent)
    row.pack(fill="x", padx=padx, pady=pady)
    text(row, title, "display600", 19).pack(side="left")
    link = None
    if action:
        link = link_button(row, action, action_cmd)
        link.pack(side="right")
    return row, link


def link_button(parent, label, command):
    return ctk.CTkButton(parent, text=label, command=command, fg_color="transparent", hover_color=C["surface2"],
                         text_color=C["accent"], font=th.font("body600", 14), width=0, height=28,
                         corner_radius=8)


BUTTON_STYLES = {
    "primary": dict(fg_color=C["accent"], hover_color=C["accent_hover"], text_color=C["accent_ink"], border_width=0),
    "ghost": dict(fg_color=C["surface"], hover_color=C["surface2"], text_color=C["ink"], border_width=1,
                  border_color=C["outline"]),
    "soft": dict(fg_color=C["accent_soft"], hover_color=C["surface2"], text_color=C["accent"], border_width=0),
    "danger": dict(fg_color=C["loss_bg"], hover_color=C["loss_bg"], text_color=C["loss"], border_width=1,
                   border_color=C["loss"]),
    "warn": dict(fg_color=C["warn_bg"], hover_color=C["warn_bg"], text_color=C["warn"], border_width=1,
                 border_color=C["warn"]),
}


def button(parent, label, command, kind="ghost", width=0, height=38, size=14):
    role = "body700" if kind == "primary" else "body600"
    return ctk.CTkButton(parent, text=label, command=command, corner_radius=height // 2, height=height, width=width,
                         font=th.font(role, size), text_color_disabled=C["muted"], **BUTTON_STYLES[kind])


def restyle(btn, kind):
    btn.configure(**BUTTON_STYLES[kind])


def icon_button(parent, glyph, command, size=38, label=None):
    return ctk.CTkButton(parent, text=glyph, width=size, height=size, corner_radius=R_CONTROL, command=command,
                         fg_color=C["surface"], hover_color=C["surface2"], text_color=C["ink"], border_width=1,
                         border_color=C["outline"], font=th.font("body600", 16))


def entry(parent, var, width=96, height=36, placeholder=None):
    style = dict(width=width, height=height, corner_radius=R_CONTROL, fg_color=C["surface"],
                 border_color=C["outline"], border_width=1, text_color=C["ink"], placeholder_text_color=C["muted"],
                 font=th.font("body", 15))
    if not placeholder:
        return ctk.CTkEntry(parent, textvariable=var, **style)
    # CTkEntry hides its placeholder when bound to a variable, so sync by hand
    e = ctk.CTkEntry(parent, placeholder_text=placeholder, **style)
    if var.get():
        e.insert(0, var.get())
    e.bind("<KeyRelease>", lambda _e: var.set(e.get()))
    e.bind("<<Paste>>", lambda _e: e.after(10, lambda: var.set(e.get())))
    e.bind("<FocusOut>", lambda _e: var.set(e.get()), add="+")
    return e


def field(parent, label, var, width=96, on_commit=None):
    box = frame(parent)
    eyebrow(box, label).pack(fill="x", pady=(0, 6))
    e = entry(box, var, width)
    e.pack(anchor="w")
    if on_commit:
        e.bind("<Return>", lambda _e: on_commit())
        e.bind("<FocusOut>", lambda _e: on_commit())
    return box


class Switch(tk.Canvas):
    """The Ubi switch: a 40×22 pill with the knob inset 3 px, drawn on a
    canvas so it looks right on every background in both themes."""

    W, H, PAD = 40, 22, 3

    def __init__(self, parent, var, command=None, bg_key="surface"):
        super().__init__(parent, width=self.W, height=self.H, highlightthickness=0, bd=0, cursor="hand2")
        self.var, self.command, self.bg_key = var, command, bg_key
        self.enabled = True
        self.bind("<Button-1>", self._click)
        var.trace_add("write", lambda *_a: self.draw())
        ctk.AppearanceModeTracker.add(lambda _m: self.draw(), self)
        self.draw()

    def _c(self, key):
        return th.pick(ctk.get_appearance_mode(), C[key])

    def _click(self, _e):
        if not self.enabled:
            return
        self.var.set(not bool(self.var.get()))
        if self.command:
            self.command()

    def configure(self, cnf=None, **kw):
        if "state" in kw:
            self.enabled = kw.pop("state") != "disabled"
            self.configure(cursor="hand2" if self.enabled else "")
            self.draw()
        if kw or cnf:
            return super().configure(cnf, **kw)

    config = configure

    def draw(self):
        try:
            self.delete("all")
        except tk.TclError:
            return
        on = bool(self.var.get())
        w, h, p = self.W, self.H, self.PAD
        super().configure(bg=self._c(self.bg_key))
        track = self._c("accent") if on else self._c("outline")
        if not self.enabled:
            track = self._c("line")
        r = h / 2
        self.create_oval(0, 0, h, h, fill=track, outline=track)
        self.create_oval(w - h, 0, w, h, fill=track, outline=track)
        self.create_rectangle(r, 0, w - r, h, fill=track, outline=track)
        d = h - 2 * p
        x = w - p - d if on else p
        knob = "#ffffff" if ctk.get_appearance_mode() == "Light" or on else "#f1e8ee"
        self.create_oval(x, p, x + d, p + d, fill=knob, outline=knob)


def switch(parent, label, var, command, bg_key="surface"):
    if not label:
        return Switch(parent, var, command, bg_key)
    box = frame(parent)
    Switch(box, var, command, bg_key).pack(side="left")
    text(box, label, "body", 15).pack(side="left", padx=(10, 0))
    return box


class RoundButton(tk.Canvas):
    """A 44 px round icon button (play / stop) drawn on a canvas."""

    def __init__(self, parent, command, size=44, bg_key="surface"):
        super().__init__(parent, width=size, height=size, highlightthickness=0, bd=0, cursor="hand2")
        self.size, self.command, self.bg_key, self.glyph, self.hover = size, command, bg_key, "play", False
        self.bind("<Button-1>", lambda _e: command())
        self.bind("<Enter>", lambda _e: self._hover(True))
        self.bind("<Leave>", lambda _e: self._hover(False))
        ctk.AppearanceModeTracker.add(lambda _m: self.draw(), self)
        self.draw()

    def _hover(self, on):
        self.hover = on
        self.draw()

    def set_glyph(self, glyph):
        if glyph != self.glyph:
            self.glyph = glyph
            self.draw()

    def draw(self):
        mode = ctk.get_appearance_mode()
        try:
            self.delete("all")
        except tk.TclError:
            return
        s = self.size
        self.configure(bg=th.pick(mode, C[self.bg_key]))
        fill = th.pick(mode, C["accent_hover" if self.hover else "accent"])
        ink = th.pick(mode, C["accent_ink"])
        self.create_oval(0, 0, s - 1, s - 1, fill=fill, outline=fill)
        c = s / 2
        if self.glyph == "stop":
            self.create_rectangle(c - 6, c - 6, c + 6, c + 6, fill=ink, outline=ink)
        else:
            self.create_polygon(c - 4, c - 7, c + 7, c, c - 4, c + 7, fill=ink, outline=ink)


def switch_row(parent, title, sub, var, command, last=False):
    """A list row: title and sub-line on the left, a switch on the right."""
    row = frame(parent)
    row.pack(fill="x", padx=14, pady=(11, 11))
    sw = switch(row, "", var, command)
    sw.pack(side="right")
    box = frame(row)
    box.pack(side="left", fill="x", expand=True)
    text(box, title, "body", 15, wraplength=340).pack(fill="x")
    if sub:
        text(box, sub, "body", 13, "muted", wraplength=340).pack(fill="x")
    if not last:
        divider(parent)
    return sw


def divider(parent):
    ctk.CTkFrame(parent, height=1, fg_color=C["line"], corner_radius=0).pack(fill="x")


def segmented(parent, options, current, command, height=36, size=14):
    """Ubi SegmentedControl: a recessed track with the chosen segment raised."""
    labels = [lbl for _, lbl in options]
    by_label = {lbl: key for key, lbl in options}
    seg = ctk.CTkSegmentedButton(
        parent, values=labels, height=height, corner_radius=R_CONTROL, border_width=3,
        fg_color=C["surface2"], selected_color=C["surface"], selected_hover_color=C["surface"],
        unselected_color=C["surface2"], unselected_hover_color=C["line"], text_color=C["ink"],
        font=th.font("body600", size), command=lambda lbl: command(by_label[lbl]))
    seg.set(dict(options).get(current, labels[0]))
    seg.keys = dict(options)
    return seg


class Chips:
    """A row of single-choice chips (selected = accent fill)."""

    def __init__(self, parent, options, current, command, size=13):
        self.frame = frame(parent)
        self.command = command
        self.buttons = {}
        for key, label in options:
            b = ctk.CTkButton(self.frame, text=label, height=30, width=0, corner_radius=15,
                              font=th.font("body600", size), command=lambda k=key: self._pick(k))
            b.pack(side="left", padx=(0, 6))
            self.buttons[key] = b
        self.set(current)

    def _pick(self, key):
        self.set(key)
        self.command(key)

    def set(self, key):
        self.value = key
        for k, b in self.buttons.items():
            if k == key:
                b.configure(fg_color=C["accent"], hover_color=C["accent_hover"], text_color=C["accent_ink"],
                            border_width=0)
            else:
                b.configure(fg_color=C["surface"], hover_color=C["surface2"], text_color=C["ink"],
                            border_width=1, border_color=C["outline"])


def pill(parent):
    return ctk.CTkLabel(parent, text="", corner_radius=999, height=24, font=th.font("body600", 12))


def set_pill(p, label, bg, fg):
    p.configure(text=f"  {label}  ", fg_color=C[bg], text_color=C[fg])


def key_chip(parent, value, command=None, danger=False):
    kw = dict(fg_color=C["loss_bg"] if danger else C["surface2"], text_color=C["loss"] if danger else C["ink"])
    if command:
        return ctk.CTkButton(parent, text=value, command=command, corner_radius=8, height=30, width=56,
                             hover_color=C["line"], font=th.font("mono500", 13), **kw)
    return ctk.CTkLabel(parent, text=value, corner_radius=8, height=30, width=56, font=th.font("mono500", 13), **kw)


def tag(parent, initials, active=False):
    return ctk.CTkLabel(parent, text=initials, width=40, height=40, corner_radius=11,
                        fg_color=C["accent"] if active else C["surface2"],
                        text_color=C["accent_ink"] if active else C["ink"], font=th.font("mono500", 12))


def bind_click(widget, command):
    """Make a whole row clickable (frames and labels don't take commands).

    Buttons, entries, switches and other controls inside the row keep their
    own clicks. (CTk buttons are tk.Frames underneath, so they must be
    skipped explicitly or the row would swallow their clicks.)
    """
    if is_control(widget):
        return
    widget.bind("<Button-1>", lambda e: command())
    for child in widget.winfo_children():
        if isinstance(child, (ctk.CTkFrame, ctk.CTkLabel, tk.Label, tk.Frame, tk.Canvas)):
            bind_click(child, command)


def is_control(widget):
    return isinstance(widget, (ctk.CTkButton, ctk.CTkEntry, ctk.CTkSegmentedButton, ctk.CTkSwitch,
                               ctk.CTkOptionMenu, ctk.CTkScrollbar, Switch, RoundButton))


def stat_tiles(parent, items):
    """items: [(key, label)] -> {key: value label}"""
    row = frame(parent)
    row.columnconfigure(tuple(range(len(items))), weight=1, uniform="stat")
    vals = {}
    for i, (key, label) in enumerate(items):
        tile = card(row)
        tile.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 5, 0 if i == len(items) - 1 else 5))
        eyebrow(tile, label).pack(fill="x", padx=14, pady=(12, 2))
        v = text(tile, "0", "body700", 18)
        v.pack(fill="x", padx=14, pady=(0, 12))
        vals[key] = v
    return row, vals
