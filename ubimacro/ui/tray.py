"""Optional tray icon (needs pystray). Used when "Close to the tray" is on."""

from ..i18n import tr

try:
    import pystray
    from PIL import Image, ImageDraw
except Exception:  # pragma: no cover - pystray is optional
    pystray = None


def tray_image():
    """UbiMacro's tray icon: a magenta rounded square with a play triangle."""
    s = 64
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((2, 2, s - 2, s - 2), radius=14, fill=(176, 31, 122, 255))
    d.polygon([(24, 17), (47, 32), (24, 47)], fill=(255, 255, 255, 255))
    return img


class Tray:
    def __init__(self, app):
        self.app = app
        self.icon = None
        self.available = pystray is not None

    def _menu(self):
        q = self.app.q
        return pystray.Menu(
            pystray.MenuItem(tr("tray_open"), lambda: q.put(("tray", "show")), default=True),
            pystray.MenuItem(tr("tray_play"), lambda: q.put(("tray", "play"))),
            pystray.MenuItem(tr("tray_clicker"), lambda: q.put(("tray", "clicker"))),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(tr("tray_quit"), lambda: q.put(("tray", "quit"))),
        )

    def show(self):
        if not self.available or self.icon is not None:
            return
        try:
            self.icon = pystray.Icon("UbiMacro", tray_image(), "UbiMacro", self._menu())
            self.icon.run_detached()
        except Exception:
            self.icon = None
            self.available = False

    def refresh(self):
        if self.icon is not None:
            st = self.app.state
            label = {"playing": tr("pill_on"), "clicking": tr("pill_clicking"),
                     "recording": tr("st_recording")}.get(st)
            try:
                self.icon.title = f"UbiMacro · {label}" if label else "UbiMacro"
            except Exception:
                pass

    def rebuild(self):
        if self.icon is not None:
            try:
                self.icon.menu = self._menu()
                self.icon.update_menu()
            except Exception:
                pass

    def stop(self):
        if self.icon is not None:
            try:
                self.icon.stop()
            except Exception:
                pass
            self.icon = None
