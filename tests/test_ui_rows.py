"""The ⋯ / star / key buttons in a Library row must keep their own clicks
(1.3.0 bug: the row's click handler swallowed them)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _tk():
    try:
        import customtkinter as ctk

        root = ctk.CTk()
        root.geometry('200x150+0+0')
        return ctk, root
    except Exception:
        return None, None


class RowClickTest(unittest.TestCase):
    def test_buttons_in_a_clickable_row_keep_their_clicks(self):
        ctk, root = _tk()
        if root is None:
            self.skipTest("no display")
        from ubimacro.ui import kit

        hits = []
        row = kit.frame(root)
        row.pack()
        label = kit.text(row, "Punch bag")
        label.pack()
        more = ctk.CTkButton(row, text="...", command=lambda: hits.append("menu"))
        more.pack()
        kit.bind_click(row, lambda: hits.append("row"))
        root.update()
        # the row must not put its own click handler on the button's parts
        for part in (more._canvas, getattr(more, "_text_label", None)):
            if part is not None:
                self.assertEqual(part.bind("<Button-1>"), "", part)
        # ...while plain parts of the row still select it
        label._label.event_generate("<Button-1>", x=2, y=2)
        root.update()
        root.destroy()
        self.assertEqual(hits, ["row"])


if __name__ == "__main__":
    unittest.main()
