# ui_components/dropdown_arrow.py
"""Tiny "▼" indicator widget that lives below each main toolbar button.

Visually disappears into the toolbar gradient (background colour matches
`toolbar_bg`) until hovered. Fires `command()` on a clean click.

The click-vs-drag detection mirrors `SpectrumButton._on_down/_motion/_up`
so the user can't accidentally trigger the dropdown by trying to drag
the widget — they get a 5px threshold.
"""

from __future__ import annotations

import tkinter as tk


class DropdownArrow(tk.Canvas):
    """Small canvas widget showing a triangular ▼ marker."""

    # Glyph palette
    _IDLE_FG    = "#9BA3C7"   # subdued blue-grey, matches dim toolbar text
    _HOVER_FG   = "#FFFFFF"
    _ACTIVE_FG  = "#FFD700"   # gold (matches SpectrumButton's label gold)
    # Subtle 1px highlight stripe at top to suggest a seam vs button row
    _SEAM_FG    = "#404778"

    def __init__(self, parent, command=None, toolbar_bg: str = "#2E305E",
                  width: int = 72, height: int = 14, **kw):
        super().__init__(parent, bg=toolbar_bg, highlightthickness=0,
                         cursor="hand2", **kw)
        # Set dimensions via configure (passing width/height directly to
        # super().__init__ collides with internal Tk widget-name handling
        # in some Python builds — produced "invalid command name 72").
        self.configure(width=width, height=height)
        self._toolbar_bg = toolbar_bg
        self.command = command
        self._cur_w = width
        self._cur_h = height
        self._hover = False
        self._active = False
        self._pressed = False
        self._press_x = 0
        self._press_y = 0
        self._drag_started = False

        self._draw()
        self.bind("<Button-1>", self._on_down)
        self.bind("<B1-Motion>", self._on_motion)
        self.bind("<ButtonRelease-1>", self._on_up)
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))

    # ── Public API ───────────────────────────────────────────────

    def resize(self, width: int, height: int) -> None:
        self._cur_w = width
        self._cur_h = height
        self.config(width=width, height=height)
        self._draw()

    def set_active(self, active: bool) -> None:
        """Highlight the arrow while its dropdown popup is open."""
        if self._active == active:
            return
        self._active = active
        self._draw()

    # ── Drawing ──────────────────────────────────────────────────

    def _glyph_color(self) -> str:
        if self._active:
            return self._ACTIVE_FG
        if self._hover:
            return self._HOVER_FG
        return self._IDLE_FG

    def _draw(self) -> None:
        self.delete("all")
        w, h = self._cur_w, self._cur_h
        # Subtle top-of-arrow seam line (looks like a join between the
        # button row and the arrow row — sells the "dock" feel).
        self.create_line(0, 0, w, 0, fill=self._SEAM_FG)
        # Triangle. Centred horizontally; sized to ~60% of available
        # height to leave breathing room above + below.
        cx = w // 2
        tri_h = max(3, int(h * 0.45))
        tri_w = max(4, int(h * 0.65))
        cy = h // 2 + 1
        pts = (
            cx - tri_w // 2, cy - tri_h // 2,
            cx + tri_w // 2, cy - tri_h // 2,
            cx,              cy + tri_h // 2 + 1,
        )
        self.create_polygon(pts, fill=self._glyph_color(), outline="")

    def _set_hover(self, on: bool) -> None:
        if self._hover == on:
            return
        self._hover = on
        self._draw()

    # ── Click-vs-drag (mirrors SpectrumButton) ───────────────────

    def _on_down(self, e):
        self._pressed = True
        self._drag_started = False
        self._press_x = e.x_root
        self._press_y = e.y_root

    def _on_motion(self, e):
        if self._pressed and not self._drag_started:
            if (abs(e.x_root - self._press_x) > 5
                    or abs(e.y_root - self._press_y) > 5):
                self._drag_started = True

    def _on_up(self, e):
        clean_click = (self._pressed
                       and not self._drag_started
                       and self.command is not None)
        self._pressed = False
        self._drag_started = False
        if clean_click:
            try:
                self.command()
            except Exception as ex:
                print(f"[DropdownArrow] command failed: {ex}")
