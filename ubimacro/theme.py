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
    "bg":          ("#f3eef2", "#120d11"),   # page
    "surface":     ("#ffffff", "#1b141a"),   # cards, lists, inputs
    "surface2":    ("#ebe3ea", "#271d25"),   # recessed fills, segmented track, pressed
    "line":        ("#ded4dc", "#33272f"),   # 1px hairlines (decorative)
    "outline":     ("#8c7f8a", "#75646f"),   # input and switch borders, passes 3:1
    "ink":         ("#1d1219", "#f1e8ee"),
    "muted":       ("#64575f", "#ab9ba6"),
    "accent":      ("#b01f7a", "#ff7ac6"),   # UbiMacro magenta
    "accent_hover": ("#971a68", "#ff94d1"),
    "accent_ink":  ("#ffffff", "#120d11"),
    "accent_soft": ("#fadcee", "#3d1a30"),
    "gain":        ("#0e7447", "#4cc48a"),   # playing, done
    "gain_bg":     ("#dcf1e6", "#14301f"),
    "warn":        ("#8a5e00", "#f2b35b"),   # countdown, heads-up
    "warn_bg":     ("#fbebd2", "#3a2a12"),
    "loss":        ("#b3361b", "#ff8a6b"),   # recording, delete, errors (orange-red, clear of the magenta)
    "loss_bg":     ("#fbe4dc", "#3a1d15"),
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
    folder = os.path.join(assets_dir(), "fonts")
    paths = [os.path.join(folder, n) for n in FONT_FILES if os.path.exists(os.path.join(folder, n))]
    if sys.platform == "win32":
        # FR_PRIVATE: only this process sees them, nothing is installed. Unlike
        # CustomTkinter's loader we leave them enumerable, so we can check
        # they really loaded.
        import ctypes

        add_font = ctypes.windll.gdi32.AddFontResourceExW
        for path in paths:
            try:
                add_font(ctypes.c_wchar_p(path), 0x10, 0)
            except Exception:
                pass
        return
    try:
        from customtkinter import FontManager
    except ImportError:
        return
    for path in paths:
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
