# ui_components/pen_overlay.py
"""PenOverlay — Fullscreen transparent canvas for screen annotation.

Two-window technique for proper transparent drawing on Windows:
  render_win — Shows strokes at full opacity, transparent bg (WS_EX_TRANSPARENT)
  input_win  — Nearly invisible (alpha=1/255), captures all mouse events

Catmull-Rom curve smoothing, undo/redo, eraser, click-through toggle."""

import tkinter as tk
import ctypes
import ctypes.wintypes
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Callable

user32 = ctypes.windll.user32

# Win32 constants
GWL_EXSTYLE        = -20
WS_EX_LAYERED      = 0x00080000
WS_EX_TRANSPARENT  = 0x00000020
WS_EX_NOACTIVATE   = 0x08000000
WS_EX_TOOLWINDOW   = 0x00000080
SWP_NOMOVE         = 0x0002
SWP_NOSIZE         = 0x0001
SWP_NOZORDER       = 0x0004
SWP_FRAMECHANGED   = 0x0020
LWA_ALPHA          = 0x00000002
HWND_TOPMOST       = -1

# Virtual screen metrics
SM_XVIRTUALSCREEN  = 76
SM_YVIRTUALSCREEN  = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79


@dataclass
class Stroke:
    """Single drawn stroke with all its data."""
    points: List[Tuple[float, float]] = field(default_factory=list)
    color: str = "#FF0000"
    width: int = 3
    is_highlighter: bool = False
    canvas_ids: List[int] = field(default_factory=list)
    smoothed_points: List[Tuple[float, float]] = field(default_factory=list)


class PenOverlay:
    """Fullscreen transparent overlay for drawing annotations on screen.

    Architecture (two-window technique):
      render_win — Toplevel with -transparentcolor + WS_EX_TRANSPARENT.
                   Shows strokes at full opacity. Transparent bg is click-through.
      input_win  — Toplevel with alpha=1/255 (nearly invisible).
                   Captures all mouse events for drawing.

    Z-order (bottom to top): input_win → render_win → PenToolbar
    Mouse events: user clicks → input_win catches → draws on render_win canvas
    """

    TRANS_COLOR = "#010101"
    DEFAULT_COLOR = "#FF0000"
    DEFAULT_WIDTH = 3

    def __init__(self, parent, on_close_callback: Optional[Callable] = None):
        self._parent = parent
        self._on_close = on_close_callback
        self._destroyed = False

        # Drawing state
        self._strokes: List[Stroke] = []
        self._undo_stack: List[Stroke] = []
        self._current_stroke: Optional[Stroke] = None
        self._click_through = False

        # Pen settings
        self._pen_color = self.DEFAULT_COLOR
        self._pen_width = self.DEFAULT_WIDTH
        self._tool = "pen"  # "pen" | "highlighter" | "eraser"
        self._highlighter_color = "#FFFF44"

        # Screen dimensions (multi-monitor)
        self._vx, self._vy, self._vw, self._vh = self._get_screen_dims()

        # Build two windows
        self._setup_render_window()
        self._setup_input_window()
        self._bind_events()
        self._parent.after(100, self._setup_win32)

    # ── Window Setup ─────────────────────────────────

    def _get_screen_dims(self):
        """Get virtual screen dimensions for multi-monitor support."""
        try:
            vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
            vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
            vw = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
            vh = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
            if vw > 0 and vh > 0:
                return vx, vy, vw, vh
        except:
            pass
        # Fallback to primary monitor
        try:
            sw = user32.GetSystemMetrics(0)
            sh = user32.GetSystemMetrics(1)
            return 0, 0, sw, sh
        except:
            return 0, 0, 1920, 1080

    def _setup_render_window(self):
        """Render window: transparent bg, shows strokes at full opacity, click-through."""
        self._render_win = tk.Toplevel(self._parent)
        self._render_win.overrideredirect(True)
        self._render_win.attributes('-topmost', True)
        self._render_win.geometry(f"{self._vw}x{self._vh}+{self._vx}+{self._vy}")
        self._render_win.configure(bg=self.TRANS_COLOR)
        self._render_win.attributes('-transparentcolor', self.TRANS_COLOR)

        # Canvas for drawing strokes (bg = transparent color → see-through)
        self._canvas = tk.Canvas(
            self._render_win, bg=self.TRANS_COLOR,
            highlightthickness=0
        )
        self._canvas.pack(fill="both", expand=True)

    def _setup_input_window(self):
        """Input window: nearly invisible (alpha=1/255), captures mouse events."""
        self._input_win = tk.Toplevel(self._parent)
        self._input_win.overrideredirect(True)
        self._input_win.attributes('-topmost', True)
        self._input_win.geometry(f"{self._vw}x{self._vh}+{self._vx}+{self._vy}")
        self._input_win.configure(bg='black')

        # Input canvas captures all mouse events
        self._input_canvas = tk.Canvas(
            self._input_win, bg='black',
            highlightthickness=0, cursor="crosshair"
        )
        self._input_canvas.pack(fill="both", expand=True)

    def _setup_win32(self):
        """Apply Win32 extended styles to both windows."""
        if self._destroyed:
            return
        try:
            # ── Render window: click-through so events pass to input_win ──
            self._render_win.update_idletasks()
            rh = user32.GetParent(self._render_win.winfo_id())
            self._render_hwnd = rh
            style = user32.GetWindowLongW(rh, GWL_EXSTYLE)
            style |= (WS_EX_LAYERED | WS_EX_TRANSPARENT |
                      WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)
            user32.SetWindowLongW(rh, GWL_EXSTYLE, style)

            # ── Input window: captures events, nearly invisible ──
            self._input_win.update_idletasks()
            ih = user32.GetParent(self._input_win.winfo_id())
            self._input_hwnd = ih
            style = user32.GetWindowLongW(ih, GWL_EXSTYLE)
            style |= (WS_EX_LAYERED | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)
            style &= ~WS_EX_TRANSPARENT  # NOT click-through — captures events
            user32.SetWindowLongW(ih, GWL_EXSTYLE, style)

            # Set alpha=1 on input window (nearly invisible but captures events)
            user32.SetLayeredWindowAttributes(ih, 0, 1, LWA_ALPHA)

            # Ensure z-order: render_win above input_win
            user32.SetWindowPos(rh, HWND_TOPMOST, 0, 0, 0, 0,
                                SWP_NOMOVE | SWP_NOSIZE)

            print("[PEN] Two-window setup OK (draw mode)")
        except Exception as e:
            print(f"[PEN] Win32 setup failed: {e}")

    # ── Events ────────────────────────────────────────

    def _bind_events(self):
        """Bind mouse events on input canvas, keyboard on input window."""
        self._input_canvas.bind("<ButtonPress-1>", self._on_mouse_down)
        self._input_canvas.bind("<B1-Motion>", self._on_mouse_move)
        self._input_canvas.bind("<ButtonRelease-1>", self._on_mouse_up)

        # Scoped keyboard shortcuts (only when overlay is active)
        self._input_win.bind("<Control-z>", lambda e: self.undo())
        self._input_win.bind("<Control-y>", lambda e: self.redo())
        self._input_win.bind("<Escape>", lambda e: self.close())

    def _on_mouse_down(self, event):
        """Start a new stroke or erase."""
        x, y = event.x, event.y

        if self._tool == "eraser":
            self._erase_at(x, y)
            return

        # Start new stroke
        color = self._highlighter_color if self._tool == "highlighter" else self._pen_color
        width = self._pen_width * 4 if self._tool == "highlighter" else self._pen_width
        self._current_stroke = Stroke(
            points=[(x, y)],
            color=color,
            width=width,
            is_highlighter=(self._tool == "highlighter"),
        )
        # Draw initial dot
        r = max(1, width // 2)
        dot_id = self._canvas.create_oval(
            x - r, y - r, x + r, y + r,
            fill=color, outline="", tags="stroke"
        )
        self._current_stroke.canvas_ids.append(dot_id)

    def _on_mouse_move(self, event):
        """Add point to current stroke, draw incrementally."""
        if not self._current_stroke:
            if self._tool == "eraser":
                self._erase_at(event.x, event.y)
            return

        x, y = event.x, event.y
        pts = self._current_stroke.points

        # Skip if too close (noise reduction)
        if pts:
            dx = x - pts[-1][0]
            dy = y - pts[-1][1]
            if dx * dx + dy * dy < 4:  # < 2px distance
                return

        pts.append((x, y))

        # Draw incrementally with smoothing
        if len(pts) >= 4:
            # Use last 4 points for Catmull-Rom
            smoothed = self._catmull_rom_segment(
                pts[-4], pts[-3], pts[-2], pts[-1], num_points=6
            )
            flat = []
            for p in smoothed:
                flat.extend(p)
            flat.extend([pts[-1][0], pts[-1][1]])

            if len(flat) >= 4:
                line_id = self._canvas.create_line(
                    *flat,
                    fill=self._current_stroke.color,
                    width=self._current_stroke.width,
                    smooth=True, splinesteps=12,
                    capstyle=tk.ROUND, joinstyle=tk.ROUND,
                    tags="stroke"
                )
                self._current_stroke.canvas_ids.append(line_id)
        elif len(pts) >= 2:
            # Simple line for first few points
            line_id = self._canvas.create_line(
                pts[-2][0], pts[-2][1], pts[-1][0], pts[-1][1],
                fill=self._current_stroke.color,
                width=self._current_stroke.width,
                capstyle=tk.ROUND,
                tags="stroke"
            )
            self._current_stroke.canvas_ids.append(line_id)

    def _on_mouse_up(self, event):
        """Finalize stroke with full Catmull-Rom smoothing."""
        if not self._current_stroke:
            return

        stroke = self._current_stroke
        self._current_stroke = None

        if len(stroke.points) < 2:
            # Single click — keep the dot
            pass

        # Re-render as single smooth line for better quality
        if len(stroke.points) >= 3:
            for cid in stroke.canvas_ids:
                self._canvas.delete(cid)
            stroke.canvas_ids.clear()

            smoothed = self._smooth_full_stroke(stroke.points)
            stroke.smoothed_points = smoothed

            flat = []
            for p in smoothed:
                flat.extend(p)

            if len(flat) >= 4:
                line_id = self._canvas.create_line(
                    *flat,
                    fill=stroke.color,
                    width=stroke.width,
                    smooth=True, splinesteps=16,
                    capstyle=tk.ROUND, joinstyle=tk.ROUND,
                    tags="stroke"
                )
                stroke.canvas_ids = [line_id]

        # Push to strokes, clear redo stack
        self._strokes.append(stroke)
        self._undo_stack.clear()

    # ── Catmull-Rom Smoothing ─────────────────────────

    @staticmethod
    def _catmull_rom_segment(p0, p1, p2, p3, num_points=8):
        """Catmull-Rom spline interpolation between p1 and p2."""
        points = []
        for i in range(num_points):
            t = i / num_points
            t2 = t * t
            t3 = t2 * t

            x = 0.5 * (
                (2 * p1[0]) +
                (-p0[0] + p2[0]) * t +
                (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 +
                (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3
            )
            y = 0.5 * (
                (2 * p1[1]) +
                (-p0[1] + p2[1]) * t +
                (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 +
                (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3
            )
            points.append((x, y))
        return points

    def _smooth_full_stroke(self, raw_points):
        """Apply Catmull-Rom smoothing to an entire stroke."""
        if len(raw_points) < 3:
            return list(raw_points)

        pts = raw_points
        result = []

        for i in range(len(pts) - 1):
            p0 = pts[max(0, i - 1)]
            p1 = pts[i]
            p2 = pts[min(len(pts) - 1, i + 1)]
            p3 = pts[min(len(pts) - 1, i + 2)]

            segment = self._catmull_rom_segment(p0, p1, p2, p3, num_points=6)
            result.extend(segment)

        # Add final point
        result.append(pts[-1])
        return result

    # ── Eraser ────────────────────────────────────────

    def _erase_at(self, x, y):
        """Erase stroke under cursor (15px radius hit-test)."""
        r = 15
        items = self._canvas.find_overlapping(x - r, y - r, x + r, y + r)
        if not items:
            return

        for stroke in self._strokes[:]:
            for cid in stroke.canvas_ids:
                if cid in items:
                    for sid in stroke.canvas_ids:
                        self._canvas.delete(sid)
                    self._strokes.remove(stroke)
                    self._undo_stack.clear()
                    return

    # ── Undo / Redo ───────────────────────────────────

    def undo(self):
        """Undo last stroke."""
        if not self._strokes:
            return
        stroke = self._strokes.pop()
        for cid in stroke.canvas_ids:
            self._canvas.delete(cid)
        self._undo_stack.append(stroke)

    def redo(self):
        """Redo last undone stroke."""
        if not self._undo_stack:
            return
        stroke = self._undo_stack.pop()
        pts = stroke.smoothed_points if stroke.smoothed_points else stroke.points
        stroke.canvas_ids.clear()

        if len(pts) >= 2:
            flat = []
            for p in pts:
                flat.extend(p)
            line_id = self._canvas.create_line(
                *flat,
                fill=stroke.color, width=stroke.width,
                smooth=True, splinesteps=16,
                capstyle=tk.ROUND, joinstyle=tk.ROUND,
                tags="stroke"
            )
            stroke.canvas_ids = [line_id]
        elif len(pts) == 1:
            r = max(1, stroke.width // 2)
            dot_id = self._canvas.create_oval(
                pts[0][0] - r, pts[0][1] - r,
                pts[0][0] + r, pts[0][1] + r,
                fill=stroke.color, outline="", tags="stroke"
            )
            stroke.canvas_ids = [dot_id]

        self._strokes.append(stroke)

    def clear_all(self):
        """Clear all strokes."""
        self._canvas.delete("stroke")
        self._strokes.clear()
        self._undo_stack.clear()

    # ── Click-Through Toggle ──────────────────────────

    def set_click_through(self, enabled: bool):
        """Toggle click-through mode (draw ↔ interact with apps below)."""
        if not hasattr(self, '_input_hwnd'):
            return
        try:
            style = user32.GetWindowLongW(self._input_hwnd, GWL_EXSTYLE)
            if enabled:
                # Make input window click-through → events pass to desktop/apps
                style |= WS_EX_TRANSPARENT
                self._input_canvas.configure(cursor="arrow")
            else:
                # Input window captures events → draw mode
                style &= ~WS_EX_TRANSPARENT
                self._input_canvas.configure(cursor="crosshair")

            user32.SetWindowLongW(self._input_hwnd, GWL_EXSTYLE, style)
            user32.SetWindowPos(
                self._input_hwnd, None, 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED
            )
            self._click_through = enabled
            print(f"[PEN] Click-through: {enabled}")
        except Exception as e:
            print(f"[PEN] Click-through toggle failed: {e}")

    @property
    def is_click_through(self):
        return self._click_through

    # ── Pen Settings ──────────────────────────────────

    def set_color(self, color: str):
        self._pen_color = color
        if self._tool != "highlighter":
            self._tool = "pen"

    def set_width(self, width: int):
        self._pen_width = width

    def set_tool(self, tool: str):
        """Set tool: 'pen', 'highlighter', 'eraser'."""
        self._tool = tool
        if tool == "eraser":
            self._input_canvas.configure(cursor="circle")
        elif tool == "highlighter":
            self._input_canvas.configure(cursor="crosshair")
        else:
            self._input_canvas.configure(cursor="crosshair")

    def set_highlighter_color(self, color: str):
        self._highlighter_color = color

    # ── Tkinter-Compatible API (used by main.py) ─────

    def winfo_exists(self):
        """Check if both windows still exist."""
        try:
            return (self._render_win.winfo_exists() and
                    self._input_win.winfo_exists())
        except:
            return False

    def attributes(self, *args, **kwargs):
        """Apply attributes to both windows."""
        try:
            self._render_win.attributes(*args, **kwargs)
            self._input_win.attributes(*args, **kwargs)
        except:
            pass

    def lift(self):
        """Lift both windows (input first, render on top)."""
        try:
            self._input_win.lift()
            self._render_win.lift()  # Render stays above input
        except:
            pass

    def withdraw(self):
        """Hide both windows."""
        try:
            self._render_win.withdraw()
            self._input_win.withdraw()
        except:
            pass

    def deiconify(self):
        """Show both windows."""
        try:
            self._input_win.deiconify()
            self._render_win.deiconify()
        except:
            pass

    def destroy(self):
        """Destroy both windows."""
        self._destroyed = True
        try:
            self._input_win.destroy()
        except:
            pass
        try:
            self._render_win.destroy()
        except:
            pass

    def get_hwnd(self):
        """Return render window HWND for fullscreen exclusion."""
        return getattr(self, '_render_hwnd', None)

    def get_all_hwnds(self):
        """Return all HWNDs (render + input) for fullscreen exclusion."""
        hwnds = []
        if hasattr(self, '_render_hwnd') and self._render_hwnd:
            hwnds.append(self._render_hwnd)
        if hasattr(self, '_input_hwnd') and self._input_hwnd:
            hwnds.append(self._input_hwnd)
        return hwnds

    # ── Cleanup ───────────────────────────────────────

    def close(self):
        """Close overlay and notify parent."""
        if self._on_close:
            self._on_close()
        else:
            self.destroy()
