"""Line icons drawn with Pillow, following the Ubi icon recipe: a 24×24
grid, round 1.8 strokes, no fills (except where the meaning needs one).
Each icon is a CTkImage with a light and a dark version."""

from PIL import Image, ImageDraw

from ..theme import C

S = 4  # supersampling: draw at 4× and shrink for smooth lines
_cache = {}


def _canvas():
    img = Image.new("RGBA", (24 * S, 24 * S), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def _p(*pts):
    return [(x * S, y * S) for x, y in pts]


def _w():
    return int(round(1.8 * S))


def _line(d, color, *pts):
    pts = _p(*pts)
    d.line(pts, fill=color, width=_w(), joint="curve")
    r = _w() / 2
    for x, y in (pts[0], pts[-1]):
        d.ellipse((x - r, y - r, x + r, y + r), fill=color)


def _rect(d, color, x0, y0, x1, y1, r=2, fill=False):
    box = (x0 * S, y0 * S, x1 * S, y1 * S)
    if fill:
        d.rounded_rectangle(box, radius=r * S, fill=color)
    else:
        d.rounded_rectangle(box, radius=r * S, outline=color, width=_w())


def _draw(name, color):
    img, d = _canvas()
    if name == "mini":
        _rect(d, color, 3, 5, 21, 19)
        _rect(d, color, 12, 12, 19, 17, 1)
    elif name == "theme":
        d.ellipse((4 * S, 4 * S, 20 * S, 20 * S), outline=color, width=_w())
        d.pieslice((4 * S, 4 * S, 20 * S, 20 * S), -90, 90, fill=color)
    elif name in ("star", "star_on"):
        pts = _p((12, 3.5), (14.6, 8.9), (20.5, 9.6), (16.1, 13.6), (17.3, 19.5), (12, 16.5), (6.7, 19.5),
                 (7.9, 13.6), (3.5, 9.6), (9.4, 8.9))
        if name == "star_on":
            d.polygon(pts, fill=color)
        d.line(pts + [pts[0]], fill=color, width=_w(), joint="curve")
    elif name == "more":
        for x in (6, 12, 18):
            d.ellipse(((x - 1.6) * S, (12 - 1.6) * S, (x + 1.6) * S, (12 + 1.6) * S), fill=color)
    elif name == "expand":
        _line(d, color, (14, 4), (20, 4), (20, 10))
        _line(d, color, (10, 20), (4, 20), (4, 14))
        _line(d, color, (20, 4), (13, 11))
        _line(d, color, (4, 20), (11, 13))
    elif name == "stop":
        _rect(d, color, 6, 6, 18, 18, 2, fill=True)
    elif name == "play":
        d.polygon(_p((8, 5), (19, 12), (8, 19)), fill=color)
    elif name == "search":
        d.ellipse((5 * S, 5 * S, 17 * S, 17 * S), outline=color, width=_w())
        _line(d, color, (15.5, 15.5), (20, 20))
    elif name == "plus":
        _line(d, color, (12, 5), (12, 19))
        _line(d, color, (5, 12), (19, 12))
    elif name == "minus":
        _line(d, color, (5, 12), (19, 12))
    return img.resize((24 * 2, 24 * 2), Image.LANCZOS)


def icon(name, color="ink", size=18):
    """A CTkImage of icon ``name`` in theme colour ``color`` (light/dark)."""
    import customtkinter as ctk

    key = (name, color, size)
    if key not in _cache:
        light, dark = C[color]
        _cache[key] = ctk.CTkImage(light_image=_draw(name, light), dark_image=_draw(name, dark), size=(size, size))
    return _cache[key]
