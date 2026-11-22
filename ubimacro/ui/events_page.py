"""Events: a timeline you can drag (or a plain list), plus an inspector and
editing tools."""

import tkinter as tk
from tkinter import ttk

import customtkinter as ctk

from . import kit
from .icons import icon
from .page import Page
from .. import macro
from .. import theme as th
from ..i18n import tr
from ..keys import display_name
from ..theme import C, R_CONTROL, R_LIST

LABEL_W, RULER_H, LANE_H, LANE_GAP, EDGE = 64, 24, 30, 8, 6
STEPS = [0.1, 0.25, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600]


def describe(e):
    typ = e.get("type")
    if typ == "key":
        return tr("ev_key_" + e.get("action", "down"), key=display_name(e.get("key")))
    if typ == "click":
        b = e.get("button", "left")
        btn = tr("btn_" + b) if tr.has("btn_" + b) else b
        return tr("ev_click_" + e.get("action", "down"), btn=btn, x=e.get("x"), y=e.get("y"))
    if typ == "move":
        return tr("ev_move", x=e.get("x"), y=e.get("y"))
    if typ == "scroll":
        return tr("ev_scroll", dy=e.get("dy"), dx=e.get("dx"))
    return str(e)


def lane_name(lane, events):
    if lane is None:
        return tr("lane_other")
    if lane[0] == "btn":
        key = "lane_" + lane[1]
        return tr(key) if tr.has(key) else lane[1]
    return macro.lane_label(lane, events)


class EventsPage(Page):
    def build(self):
        f = self.frame
        self.view = "timeline"
        self.sel = None
        self.pps = None
        self._drag = None

        head = kit.frame(f)
        head.pack(fill="x", padx=16, pady=(14, 10))
        self.view_seg = kit.segmented(head, [("timeline", tr("view_timeline")), ("list", tr("view_list"))],
                                      "timeline", self.set_view, height=32, size=13)
        self.view_seg.configure(width=180)
        self.view_seg.pack(side="right")
        tb = kit.frame(head)
        tb.pack(side="left", fill="x", expand=True)
        self.title = kit.text(tb, "", "display600", 19)
        self.title.pack(fill="x")
        self.subtitle = kit.text(tb, "", "body", 13, "muted")
        self.subtitle.pack(fill="x")

        # bottom area (packed first so the body takes what's left)
        self.hint = kit.hint(f, tr("events_hint"))
        self.hint.pack(side="bottom", fill="x", padx=16, pady=(8, 14))
        tools2 = kit.frame(f)
        tools2.pack(side="bottom", fill="x", padx=16, pady=(8, 0))
        tools1 = kit.frame(f)
        tools1.pack(side="bottom", fill="x", padx=16, pady=(10, 0))
        kit.button(tools1, tr("trim_start"), self.trim_start, "soft", height=34, size=13).pack(side="left",
                                                                                               padx=(0, 6))
        kit.button(tools1, tr("cap_pauses"), self.cap_gaps, height=34, size=13).pack(side="left", padx=(0, 6))
        kit.button(tools1, tr("undo"), self.app.undo, height=34, size=13).pack(side="left")
        kit.button(tools2, tr("record_here"), self.record_here, height=34, size=13).pack(side="left", padx=(0, 6))
        kit.button(tools2, tr("test_here"), self.test_here, height=34, size=13).pack(side="left", padx=(0, 6))
        kit.button(tools2, tr("delete"), self.delete_selected, height=34, size=13).pack(side="left")

        self._build_inspector(f)
        self.body = kit.frame(f)
        self.body.pack(fill="both", expand=True, padx=16)
        self._build_timeline(self.body)
        self._build_list(self.body)
        self.set_view("timeline")

    # ---------------------------------------------------------------- inspector
    def _build_inspector(self, f):
        ins = kit.card(f)
        ins.pack(side="bottom", fill="x", padx=16, pady=(10, 0))
        kit.eyebrow(ins, tr("selected_event")).pack(fill="x", padx=14, pady=(12, 0))
        self.sel_label = kit.text(ins, "", "body600", 15)
        self.sel_label.pack(fill="x", padx=14, pady=(2, 8))
        grid = kit.frame(ins)
        grid.pack(fill="x", padx=14, pady=(0, 13))
        grid.columnconfigure((0, 1, 2), weight=1, uniform="i")
        self.v_start, self.v_held, self.v_gap = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.entries = {}
        for i, (key, label, var, cmd) in enumerate((
                ("start", tr("starts_at"), self.v_start, self.apply_start),
                ("held", tr("held_for"), self.v_held, self.apply_held),
                ("gap", tr("pause_before"), self.v_gap, self.apply_gap))):
            box = kit.frame(grid)
            box.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 5, 0 if i == 2 else 5))
            kit.eyebrow(box, label).pack(fill="x", pady=(0, 6))
            e = kit.entry(box, var, 120)
            e.pack(fill="x")
            e.bind("<Return>", lambda _e, c=cmd: c())
            e.bind("<FocusOut>", lambda _e, c=cmd: c(quiet=True))
            self.entries[key] = e

    # ---------------------------------------------------------------- timeline
    def _build_timeline(self, parent):
        self.tl = kit.card(parent, radius=R_LIST)
        holder = kit.frame(self.tl)
        holder.pack(fill="both", expand=True, padx=10, pady=(10, 0))
        holder.rowconfigure(0, weight=1)
        holder.columnconfigure(1, weight=1)
        self.lab = tk.Canvas(holder, width=LABEL_W, highlightthickness=0, bd=0)
        self.cv = tk.Canvas(holder, highlightthickness=0, bd=0)
        self.vbar = ctk.CTkScrollbar(holder, orientation="vertical", command=self._yview,
                                     button_color=C["surface2"], button_hover_color=C["outline"])
        self.hbar = ctk.CTkScrollbar(holder, orientation="horizontal", command=self.cv.xview,
                                     button_color=C["surface2"], button_hover_color=C["outline"])
        self.cv.configure(yscrollcommand=self.vbar.set, xscrollcommand=self.hbar.set)
        self.lab.configure(yscrollcommand=self.vbar.set)
        self.lab.grid(row=0, column=0, sticky="ns")
        self.cv.grid(row=0, column=1, sticky="nsew")
        self.vbar.grid(row=0, column=2, sticky="ns")
        self.hbar.grid(row=1, column=1, sticky="ew")
        bottom = kit.frame(self.tl)
        bottom.pack(fill="x", padx=14, pady=(6, 10))
        for name, factor in (("plus", 1.5), ("minus", 1 / 1.5)):
            ctk.CTkButton(bottom, text="", image=icon(name), width=32, height=32, corner_radius=10,
                          fg_color=C["surface"], hover_color=C["surface2"], border_width=1,
                          border_color=C["outline"], command=lambda f_=factor: self.zoom(f_)).pack(side="right",
                                                                                                   padx=(6, 0))
        kit.text(bottom, tr("timeline_hint"), "body", 12, "muted", wraplength=330).pack(side="left")
        self.cv.bind("<ButtonPress-1>", self._press)
        self.cv.bind("<B1-Motion>", self._motion)
        self.cv.bind("<ButtonRelease-1>", self._release)
        self.cv.bind("<Motion>", self._hover)
        self.cv.bind("<Configure>", lambda e: self.draw())
        for w in (self.cv, self.lab):
            w.bind("<MouseWheel>", self._wheel)
            w.bind("<Shift-MouseWheel>", lambda e: self.cv.xview_scroll(-1 if e.delta > 0 else 1, "units"))
            w.bind("<Control-MouseWheel>", lambda e: self.zoom(1.25 if e.delta > 0 else 0.8))
            w.bind("<Button-4>", lambda e: self._yview("scroll", -1, "units"))
            w.bind("<Button-5>", lambda e: self._yview("scroll", 1, "units"))
        self.cv.bind("<Delete>", lambda e: self.delete_selected())

    def _yview(self, *args):
        self.cv.yview(*args)
        self.lab.yview(*args)

    def _wheel(self, e):
        self._yview("scroll", -1 if e.delta > 0 else 1, "units")

    def zoom(self, factor):
        if not self.pps:
            return
        self.pps = max(10.0, min(1500.0, self.pps * factor))
        self.draw()

    def _x(self, t):
        return 6 + t * self.pps

    def _lanes(self):
        events = self.app.events
        bars, singles, lanes = macro.pairs(events)
        lanes = list(lanes)
        other = [i for i in singles if macro.lane_of(events[i]) is None]
        if other:
            lanes.append(None)
        return bars, singles, lanes

    def draw(self):
        cv, lab = self.cv, self.lab
        cv.delete("all")
        lab.delete("all")
        surface, lane_bg = self.color("surface"), self.color("surface2")
        ink, muted, accent = self.color("ink"), self.color("muted"), self.color("accent")
        cv.configure(bg=surface)
        lab.configure(bg=surface)
        events = self.app.events
        if not events:
            cv.create_text(12, 40, text=tr("nothing_to_show"), anchor="w", fill=muted,
                           font=(th.family("body"), 11))
            cv.configure(scrollregion=(0, 0, 10, 10))
            lab.configure(scrollregion=(0, 0, 10, 10))
            return
        length = macro.duration(events)
        width = cv.winfo_width()
        if width < 150:  # not laid out yet: <Configure> draws again
            return
        if self.app.active and getattr(self, "_fit_for", None) != self.app.active.id:
            self._fit_for, self.pps = self.app.active.id, None
        if not self.pps:
            self.pps = max(10.0, min(800.0, (width - 30) / max(length, 0.5)))
        total_w = max(width, self._x(length) + 40)
        bars, singles, lanes = self._lanes()
        lane_y = {lane: RULER_H + i * (LANE_H + LANE_GAP) for i, lane in enumerate(lanes)}
        total_h = RULER_H + len(lanes) * (LANE_H + LANE_GAP)
        # ruler
        step = next((s for s in STEPS if s * self.pps >= 60), STEPS[-1])
        t, mono = 0.0, (th.family("mono"), 8)
        while self._x(t) < total_w:
            label = f"{t:g} s" if t == 0 else (f"{t:g}" if t < 60 else f"{int(t // 60)}:{int(t % 60):02d}")
            cv.create_text(self._x(t), 9, text=label, anchor="w" if t == 0 else "center", fill=muted, font=mono)
            t += step
        # lanes
        for lane, y in lane_y.items():
            cv.create_rectangle(0, y, total_w, y + LANE_H, fill=lane_bg, outline="")
            lab.create_text(0, y + LANE_H / 2, text=lane_name(lane, events), anchor="w", fill=ink,
                            font=(th.family("mono500"), 9))
        sel_pair = self._sel_pair()
        for lane, d, u in bars:
            y = lane_y[lane]
            x0 = self._x(events[d]["t"])
            x1 = max(x0 + 4, self._x(events[u]["t"]))
            selected = sel_pair is not None and sel_pair[0] == d
            cv.create_rectangle(x0, y + 4, x1, y + LANE_H - 4, fill=accent if selected else muted,
                                outline=ink if selected else "", width=2 if selected else 0,
                                tags=("item", f"d{d}", f"u{u}"))
            if selected and x1 - x0 > 16:
                for hx in (x0 + 4, x1 - 6):
                    cv.create_rectangle(hx, y + 10, hx + 2, y + LANE_H - 10, fill=self.color("accent_ink"),
                                        outline="", tags=("item", f"d{d}", f"u{u}"))
        for i in singles:
            lane = macro.lane_of(events[i])
            y = lane_y.get(lane, lane_y.get(None))
            if y is None:
                continue
            x = self._x(events[i]["t"])
            selected = sel_pair is not None and sel_pair[0] == i
            cv.create_rectangle(x, y + 4, x + 4, y + LANE_H - 4, fill=accent if selected else self.color("outline"),
                                outline=ink if selected else "", width=2 if selected else 0,
                                tags=("item", f"d{i}"))
        cv.configure(scrollregion=(0, 0, total_w, total_h + 4))
        lab.configure(scrollregion=(0, 0, LABEL_W, total_h + 4))

    def _item_at(self, e):
        x, y = self.cv.canvasx(e.x), self.cv.canvasy(e.y)
        for item in reversed(self.cv.find_overlapping(x - 2, y - 2, x + 2, y + 2)):
            tags = self.cv.gettags(item)
            if "item" in tags:
                d = next(int(t[1:]) for t in tags if t.startswith("d"))
                u = next((int(t[1:]) for t in tags if t.startswith("u")), None)
                return item, d, u, x
        return None

    def _edge(self, d, u, x):
        if u is None:
            return "move"
        x0, x1 = self._x(self.app.events[d]["t"]), self._x(self.app.events[u]["t"])
        if x1 - x0 > 16:
            if abs(x - x0) <= EDGE:
                return "start"
            if abs(x - x1) <= EDGE:
                return "end"
        return "move"

    def _hover(self, e):
        hit = self._item_at(e)
        cursor = ""
        if hit:
            mode = self._edge(hit[1], hit[2], hit[3])
            cursor = "sb_h_double_arrow" if mode in ("start", "end") else "fleur"
        self.cv.configure(cursor=cursor)

    def _press(self, e):
        self.cv.focus_set()
        hit = self._item_at(e)
        if not hit:
            self._drag = None
            return
        _item, d, u, x = hit
        self.select(d)
        self._drag = {"d": d, "u": u, "x": x, "mode": self._edge(d, u, x), "dx": 0}

    def _motion(self, e):
        if not self._drag or self.app.state != "idle":
            return
        x = self.cv.canvasx(e.x)
        dx = x - self._drag["x"]
        step = dx - self._drag["dx"]
        self._drag["dx"] = dx
        tag = f"d{self._drag['d']}"
        mode = self._drag["mode"]
        for item in self.cv.find_withtag(tag):
            x0, y0, x1, y1 = self.cv.coords(item)
            if mode == "move":
                self.cv.move(item, step, 0)
            elif mode == "end" and (x1 - x0) > 6:
                self.cv.coords(item, x0, y0, max(x0 + 4, x1 + step), y1)
            elif mode == "start" and (x1 - x0) > 6:
                self.cv.coords(item, min(x1 - 4, x0 + step), y0, x1, y1)

    def _release(self, e):
        drag, self._drag = self._drag, None
        if not drag or abs(drag["dx"]) < 3:
            return
        if self.app.state != "idle":
            self.draw()
            return
        dt = round(drag["dx"] / self.pps, 3)
        d, u = drag["d"], drag["u"]
        if drag["mode"] == "move":
            self._edit(lambda ev: macro.move_bar(ev, d, u, dt), d)
        else:
            self._edit(lambda ev: macro.resize_bar(ev, d, u, dt, drag["mode"]), d)

    # ---------------------------------------------------------------- list
    def _build_list(self, parent):
        self.lst = kit.card(parent, radius=R_LIST)
        inner = kit.frame(self.lst)
        inner.pack(fill="both", expand=True, padx=8, pady=8)
        self.tree = ttk.Treeview(inner, columns=("t", "gap", "ev"), show="headings", style="Ubi.Treeview",
                                 selectmode="extended")
        self.tree.heading("t", text=tr.upper(tr("col_time")))
        self.tree.heading("gap", text=tr.upper(tr("col_gap")))
        self.tree.heading("ev", text=tr.upper(tr("col_event")), anchor="w")
        self.tree.column("t", width=74, anchor="e", stretch=False)
        self.tree.column("gap", width=74, anchor="e", stretch=False)
        self.tree.column("ev", width=240)
        sb = ctk.CTkScrollbar(inner, command=self.tree.yview, button_color=C["surface2"],
                              button_hover_color=C["outline"])
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._tree_select)
        self.tree.bind("<Delete>", lambda e: self.delete_selected())
        self._style_tree()

    def _style_tree(self):
        style = ttk.Style(self.app.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        p = self.color
        style.configure("Ubi.Treeview", background=p("surface"), fieldbackground=p("surface"), foreground=p("ink"),
                        rowheight=28, borderwidth=0, relief="flat", font=(th.family("body"), 10))
        style.map("Ubi.Treeview", background=[("selected", p("accent_soft"))], foreground=[("selected", p("accent"))])
        style.configure("Ubi.Treeview.Heading", background=p("surface"), foreground=p("muted"), relief="flat",
                        borderwidth=0, font=(th.family("mono500"), 8))
        style.map("Ubi.Treeview.Heading", background=[("active", p("surface2"))])
        style.layout("Ubi.Treeview", [("Ubi.Treeview.treearea", {"sticky": "nswe"})])

    def _fill_tree(self):
        self.tree.delete(*self.tree.get_children())
        prev = 0.0
        for i, ev in enumerate(self.app.events[:5000]):
            self.tree.insert("", "end", iid=str(i), values=(f"{ev['t']:.3f}", f"+{ev['t'] - prev:.3f}", describe(ev)))
            prev = ev["t"]

    def _tree_select(self, _e=None):
        sel = sorted(int(i) for i in self.tree.selection())
        if sel and sel[0] != self.sel:
            self.sel = sel[0]
            self._fill_inspector()

    # ---------------------------------------------------------------- selection + editing
    def _sel_pair(self):
        if self.sel is None or self.sel >= len(self.app.events):
            return None
        other = macro.partner(self.app.events, self.sel)
        if other is None:
            return (self.sel, None)
        return (min(self.sel, other), max(self.sel, other))

    def select(self, index):
        self.sel = index
        self.draw()
        self._fill_inspector()

    def _fill_inspector(self):
        events = self.app.events
        pair = self._sel_pair()
        if not pair:
            self.sel_label.configure(text=tr("nothing_selected"))
            for v in (self.v_start, self.v_held, self.v_gap):
                v.set("")
            self.entries["held"].configure(state="disabled")
            return
        d, u = pair
        e = events[d]
        prev = events[d - 1]["t"] if d > 0 else 0.0
        self.v_start.set(f"{e['t']:.3f}")
        self.v_gap.set(f"{e['t'] - prev:.3f}")
        if u is not None:
            held = events[u]["t"] - e["t"]
            self.v_held.set(f"{held:.3f}")
            self.entries["held"].configure(state="normal")
            lane = macro.lane_of(e)
            name = lane_name(lane, events)
            self.sel_label.configure(text=tr("sel_bar", name=name, a=f"{e['t']:.3f}", b=f"{events[u]['t']:.3f}"))
        else:
            self.v_held.set("")
            self.entries["held"].configure(state="disabled")
            self.sel_label.configure(text=f"#{d + 1} · {describe(e)}")

    def _edit(self, fn, keep_index):
        """Run an editing function on a copy, keep the selection on the same
        event, and save with Undo."""
        if not self.app._editable():
            self.draw()
            return
        ev = [dict(e) for e in self.app.events]
        if keep_index is not None and keep_index < len(ev):
            ev[keep_index]["_sel"] = True
        new = fn(ev)
        idx = next((i for i, e in enumerate(new) if e.get("_sel")), None)
        for e in new:
            e.pop("_sel", None)
        self.sel = idx
        self.app.replace_events(new)

    def _read(self, var):
        from ..app import num

        return num(var.get(), None, float, 0.0)

    def apply_start(self, quiet=False):
        pair = self._sel_pair()
        v = self._read(self.v_start)
        if not pair or v is None:
            return
        d, u = pair
        delta = round(v - self.app.events[d]["t"], 4)
        if abs(delta) < 0.0005:
            return
        self._edit(lambda ev: macro.move_bar(ev, d, u, delta), d)

    def apply_held(self, quiet=False):
        pair = self._sel_pair()
        v = self._read(self.v_held)
        if not pair or pair[1] is None or v is None:
            return
        d, u = pair
        delta = round((self.app.events[d]["t"] + v) - self.app.events[u]["t"], 4)
        if abs(delta) < 0.0005:
            return
        self._edit(lambda ev: macro.resize_bar(ev, d, u, delta, "end"), d)

    def apply_gap(self, quiet=False):
        pair = self._sel_pair()
        v = self._read(self.v_gap)
        if not pair or v is None:
            return
        d = pair[0]
        prev = self.app.events[d - 1]["t"] if d > 0 else 0.0
        if abs((self.app.events[d]["t"] - prev) - v) < 0.0005:
            return
        self._edit(lambda ev: macro.set_gap(ev, d, v), d)

    def trim_start(self):
        if not self.app._editable():
            return
        before = self.app.events[0]["t"] if self.app.events else 0
        if before <= 0:
            self.app.show_toast(tr("toast_no_delay"))
            return
        self._edit(macro.trim_start, self.sel)
        self.app.show_toast(tr("toast_trimmed", t=f"{before:.3f}"))

    def cap_gaps(self):
        if not self.app._editable():
            return
        cap = float(self.s.get("cap_gap", 2.0))
        old = macro.duration(self.app.events)
        new = macro.cap_gaps(self.app.events, cap)
        saved = old - macro.duration(new)
        if saved <= 0:
            self.app.show_toast(tr("toast_no_long_pauses", t=f"{cap:g}"))
            return
        self._edit(lambda ev: macro.cap_gaps(ev, cap), self.sel)
        self.app.show_toast(tr("toast_capped", t=f"{saved:.1f}", cap=f"{cap:g}"))

    def delete_selected(self):
        if not self.app._editable():
            return
        if self.view == "list":
            idx = sorted(int(i) for i in self.tree.selection())
        else:
            pair = self._sel_pair()
            idx = [i for i in (pair or ()) if i is not None]
        if not idx:
            return
        self.sel = None
        self.app.replace_events(macro.delete(self.app.events, idx))
        self.app.show_toast(tr("toast_deleted", n=len(idx)))

    def _sel_end(self):
        pair = self._sel_pair()
        if not pair:
            return macro.duration(self.app.events)
        d, u = pair
        return self.app.events[u if u is not None else d]["t"]

    def record_here(self):
        if not self.app.events:
            self.app.on_record_button()
            return
        self.app.record_from_here(self._sel_end())

    def test_here(self):
        pair = self._sel_pair()
        at = self.app.events[pair[0]]["t"] if pair else 0.0
        self.app.test_from_here(at)

    # ---------------------------------------------------------------- page hooks
    def set_view(self, view):
        self.view = view
        if self.view_seg.get() != self.view_seg.keys[view]:
            self.view_seg.set(self.view_seg.keys[view])
        if view == "list":
            self.tl.pack_forget()
            self.lst.pack(fill="both", expand=True)
            self._fill_tree()
        else:
            self.lst.pack_forget()
            self.tl.pack(fill="both", expand=True)
            self.draw()

    def on_show(self):
        self.refresh()

    def refresh(self):
        events = self.app.events
        from ..app import fmt_length

        ent = self.app.active
        self.title.configure(text=ent.name if ent else tr("tab_events"))
        self.subtitle.configure(text=tr("macro_sub", n=len(events), length=fmt_length(macro.duration(events)))
                                if ent else tr("no_macro_selected"))
        if self.sel is not None and self.sel >= len(events):
            self.sel = None
        if self.view == "list":
            self._fill_tree()
        else:
            self.draw()
        self._fill_inspector()

    def refresh_state(self):
        pass

    def theme_changed(self):
        self._style_tree()
        self.draw()
