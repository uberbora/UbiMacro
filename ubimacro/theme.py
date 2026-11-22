"""UbiMacro's look, from the Ubi design system.

Colours are UbiMacro's own ``macro-*`` tokens, mapped onto the shared Ubi
roles (bg, surface, surface2, line, ink, muted, accent, signals). Each value
is a (light, dark) pair, which CustomTkinter switches between by itself.
Every text pair passes 4.5:1 in both themes (lowest: warn on warn-bg, 4.87:1).

Fonts are the three Ubi families, shipped in ``assets/fonts`` and loaded
privately for this process, so nothing gets installed on the PC.
"""

import os
import sys

C = {
    "bg":          ("#eeedf3", "#0f0d16"),   # page
    "surface":     ("#ffffff", "#18151f"),   # cards, lists, inputs
    "surface2":    ("#e5e3ee", "#231f2e"),   # recessed fills, segmented track, pressed
    "line":        ("#d9d6e4", "#2d2839"),   # 1px hairlines (decorative)
    "outline":     ("#878199", "#6a6380"),   # input borders, passes 3:1
    "ink":         ("#16131f", "#ebe8f3"),
    "muted":       ("#5d586c", "#a19bb2"),
    "accent":      ("#5b3fd0", "#a995ff"),   # UbiMacro violet
    "accent_hover": ("#4c33b5", "#9a84f5"),
    "accent_ink":  ("#ffffff", "#0f0d16"),
    "accent_soft": ("#e6e0fb", "#2a2347"),
    "gain":        ("#0e7447", "#4cc48a"),   # playing, done
    "gain_bg":     ("#dcf1e6", "#14301f"),
    "warn":        ("#8a5e00", "#f2b35b"),   # countdown, heads-up
    "warn_bg":     ("#fbebd2", "#3a2a12"),
    "loss":        ("#b8302a", "#ff7c72"),   # recording, delete, errors
    "loss_bg":     ("#fbe3e1", "#3a1b19"),
}

# Radius scale (px)
R_BADGE, R_CONTROL, R_CARD, R_LIST, R_HERO = 4, 12, 14, 16, 22

FONT_FILES = [
    "Figtree-Regular.ttf", "Figtree-SemiBold.ttf", "Figtree-Bold.ttf",
    "BricolageGrotesque-SemiBold.ttf", "BricolageGrotesque-ExtraBold.ttf",
    "DMMono-Regular.ttf", "DMMono-Medium.ttf",
]

# role -> (Ubi family, fallback family)
FAMILIES = {
    "body": ("Figtree", "Segoe UI"),
    "body600": ("Figtree SemiBold", "Segoe UI Semibold"),
    "body700": ("Figtree Bold", "Segoe UI"),
    "display600": ("Bricolage Grotesque SemiBold", "Segoe UI Semibold"),
    "display800": ("Bricolage Grotesque ExtraBold", "Segoe UI Black"),
    "mono": ("DM Mono", "Consolas"),
    "mono500": ("DM Mono Medium", "Consolas"),
}

_resolved = {}


def pick(mode, pair):
    """Choose the light or dark half of a colour pair."""
    return pair[1] if str(mode).lower() == "dark" else pair[0]


def assets_dir():
    base = getattr(sys, "_MEIPASS", None)
    if base and os.path.isdir(os.path.join(base, "ubimacro", "assets")):
        return os.path.join(base, "ubimacro", "assets")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


def load_fonts():
    """Register the bundled fonts for this process. Call before creating the window."""
    try:
        from customtkinter import FontManager
    except ImportError:
        return
    folder = os.path.join(assets_dir(), "fonts")
    for name in FONT_FILES:
        path = os.path.join(folder, name)
        if os.path.exists(path):
            try:
                FontManager.load_font(path)
            except Exception:
                pass


def resolve_families(root):
    """Work out which families are really available (after the window exists)."""
    import tkinter.font as tkfont

    available = {f.lower() for f in tkfont.families(root)}
    for role, (ubi, fallback) in FAMILIES.items():
        _resolved[role] = ubi if ubi.lower() in available else fallback
    return dict(_resolved)


def family(role):
    return _resolved.get(role) or FAMILIES[role][1]


def font(role, size):
    """A CTkFont for a type role. Fallback fonts get bold where the role is heavy."""
    import customtkinter as ctk

    fam = family(role)
    weight = "normal"
    if fam == FAMILIES[role][1] and role in ("body700", "display800"):
        weight = "bold"
    return ctk.CTkFont(family=fam, size=size, weight=weight)
