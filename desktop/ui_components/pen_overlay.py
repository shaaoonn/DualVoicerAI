# ui_components/pen_overlay.py
"""PenOverlay — Fullscreen transparent canvas for screen annotation.

Two-window technique for proper transparent drawing on Windows:
  render_win — Shows strokes at full opacity, transparent bg (WS_EX_TRANSPARENT)
  input_win  — Nearly invisible (alpha=1/255), captures all mouse events

Catmull-Rom curve smoothing, undo/redo, eraser, click-through toggle.
Highlighter uses stipple for semi-transparency."""

import tkinter as tk
import ctypes
import ctypes.wintypes
import struct
import os
import io
import tempfile
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

SM_XVIRTUALSCREEN  = 76
SM_YVIRTUALSCREEN  = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79


# ── Custom pen cursor (created once, cached) ────────

_PEN_CURSOR_PATH = None

def _get_pen_cursor():
    """Create a pen cursor (.cur) tilted upper-right, cached on disk."""
    global _PEN_CURSOR_PATH
    if _PEN_CURSOR_PATH and os.path.exists(_PEN_CURSOR_PATH):
        # Forward slashes for Tcl (backslashes = escape chars in Tcl)
        return "@" + _PEN_CURSOR_PATH.replace("\\", "/")
    try:
        from PIL import Image, ImageDraw

        sz = 32
        img = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        # Pen shape: tip at bottom-left (~2,29), body tilting upper-right
        # Outer outline (white for visibility on dark backgrounds)
        d.polygon([
            (1, 30), (3, 28), (26, 5), (30, 1),
            (31, 2), (29, 4), (6, 27), (4, 31)
        ], fill=None, outline=(255, 255, 255, 255))
        # Inner body (dark)
        d.polygon([
            (2, 29), (4, 27), (27, 4), (29, 2),
            (30, 3), (28, 5), (5, 28), (3, 30)
        ], fill=(30, 30, 30, 255))
        # Pen tip accent
        d.polygon([(1, 30), (2, 29), (4, 27), (3, 28)],
                  fill=(80, 80, 80, 255))
        # Tip point
        d.point((1, 30), fill=(0, 0, 0, 255))

        # Save as ICO, then patch to CUR
        buf = io.BytesIO()
        img.save(buf, format='ICO', sizes=[(32, 32)])
        data = bytearray(buf.getvalue())

        # Patch header: type 1 (ICO) → 2 (CUR)
        struct.pack_into("<H", data, 2, 2)
        # Patch directory: planes/bpp → hotspot (x=1, y=30 = pen tip)
        struct.pack_into("<H", data, 10, 1)   # Hotspot X
        struct.pack_into("<H", data, 12, 30)  # Hotspot Y

        cur_path = os.path.join(tempfile.gettempdir(), "voiceai_pen.cur")
        with open(cur_path, "wb") as f:
            f.write(data)

        _PEN_CURSOR_PATH = cur_path
        # Forward slashes for Tcl compatibility
        return "@" + cur_path.replace("\\", "/")
    except Exception as e:
        print(f"[PEN] Custom cursor failed: {e}")
        return "pencil"  # Fallback


@dataclass
class Stroke:
    """Single drawn stroke with all its data."""
    points: List[Tuple[float, float]] = field(default_factory=list)
    color: str = "#FF0000"
    width: int = 4
    is_highlighter: bool = False
    canvas_ids: List[int] = field(default_factory=list)
    smoothed_points: List[Tuple[float, float]] = field(default_factory=list)


class PenOverlay:
    """Fullscreen transparent overlay for drawing annotations on screen.

    Two-window technique:
      render_win — Shows strokes, transparent bg, click-through
      input_win  — Nearly invisible, captures mouse events

    Z-order: input_win < MAIN WIDGET < render_win < PenToolbar
    """

    TRANS_COLOR = "#010101"
    DEFAULT_COLOR = "#FF0000"
    DEFAULT_WIDTH = 4

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
        self._tool = "pen"
        self._highlighter_color = "#FFFF44"

        # EMA smoothing state
        self._ema_x = 0.0
        self._ema_y = 0.0
        self._ema_alpha = 0.35

        # Custom cursor
        self._pen_cursor = _get_pen_cursor()

        # Screen dimensions
        self._vx, self._vy, self._vw, self._vh = self._get_screen_dims()

        # Build windows (with cleanup on failure to prevent black screen)
        try:
            self._setup_render_window()
            self._setup_input_window()
            self._bind_events()
            self._parent.after(100, self._setup_win32)
        except Exception as e:
            print(f"[PEN] Init failed, cleaning up: {e}")
            self.destroy()
            raise

    # ── Window Setup ─────────────────────────────────

    def _get_screen_dims(self):
        try:
            vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
            vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
            vw = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
            vh = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
            if vw > 0 and vh > 0:
                return vx, vy, vw, vh
        except:
            pass
        try:
            return 0, 0, user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        except:
            return 0, 0, 1920, 1080

    def _setup_render_window(self):
        self._render_win = tk.Toplevel(self._parent)
        self._render_win.overrideredirect(True)
        self._render_win.attributes('-topmost', True)
        self._render_win.geometry(f"{self._vw}x{self._vh}+{self._vx}+{self._vy}")
        self._render_win.configure(bg=self.TRANS_COLOR)
        self._render_win.attributes('-transparentcolor', self.TRANS_COLOR)

        self._canvas = tk.Canvas(
            self._render_win, bg=self.TRANS_COLOR, highlightthickness=0
        )
        self._canvas.pack(fill="both", expand=True)

    def _setup_input_window(self):
        self._input_win = tk.Toplevel(self._parent)
        self._input_win.overrideredirect(True)
        self._input_win.attributes('-topmost', True)
        self._input_win.geometry(f"{self._vw}x{self._vh}+{self._vx}+{self._vy}")
        self._input_win.configure(bg='black')

        # Try custom cursor, fallback to built-in pencil
        cursor = self._pen_cursor
        try:
            self._input_canvas = tk.Canvas(
                self._input_win, bg='black',
                highlightthickness=0, cursor=cursor
            )
        except tk.TclError:
            print(f"[PEN] Custom cursor failed, using pencil fallback")
            self._pen_cursor = "pencil"
            self._input_canvas = tk.Canvas(
                self._input_win, bg='black',
                highlightthickness=0, cursor="pencil"
            )
        self._input_canvas.pack(fill="both", expand=True)

    def _setup_win32(self):
        if self._destroyed:
            return
        try:
            # Render window: click-through
            self._render_win.update_idletasks()
            rh = user32.GetParent(self._render_win.winfo_id())
            self._render_hwnd = rh
            style = user32.GetWindowLongW(rh, GWL_EXSTYLE)
            style |= (WS_EX_LAYERED | WS_EX_TRANSPARENT |
                      WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)
            user32.SetWindowLongW(rh, GWL_EXSTYLE, style)

            # Input window: captures events, alpha=1
            self._input_win.update_idletasks()
            ih = user32.GetParent(self._input_win.winfo_id())
            self._input_hwnd = ih
            style = user32.GetWindowLongW(ih, GWL_EXSTYLE)
            style |= (WS_EX_LAYERED | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)
            style &= ~WS_EX_TRANSPARENT
            user32.SetWindowLongW(ih, GWL_EXSTYLE, style)
            user32.SetLayeredWindowAttributes(ih, 0, 1, LWA_ALPHA)

            user32.SetWindowPos(rh, HWND_TOPMOST, 0, 0, 0, 0,
                                SWP_NOMOVE | SWP_NOSIZE)

            print("[PEN] Two-window setup OK")
        except Exception as e:
            print(f"[PEN] Win32 setup failed: {e}")

    # ── Events ────────────────────────────────────────

    def _bind_events(self):
        self._input_canvas.bind("<ButtonPress-1>", self._on_mouse_down)
        self._input_canvas.bind("<B1-Motion>", self._on_mouse_move)
        self._input_canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        self._input_win.bind("<Control-z>", lambda e: self.undo())
        self._input_win.bind("<Control-y>", lambda e: self.redo())
        self._input_win.bind("<Escape>", lambda e: self.close())

    def _on_mouse_down(self, event):
        x, y = event.x, event.y

        if self._tool == "eraser":
            self._erase_at(x, y)
            return

        color = self._highlighter_color if self._tool == "highlighter" else self._pen_color
        width = self._pen_width * 3 if self._tool == "highlighter" else self._pen_width
        is_hl = (self._tool == "highlighter")

        self._current_stroke = Stroke(
            points=[(x, y)], color=color, width=width,
            is_highlighter=is_hl,
        )
        self._ema_x = float(x)
        self._ema_y = float(y)

        r = max(1, width // 2)
        stipple = "gray50" if is_hl else ""
        dot_id = self._canvas.create_oval(
            x - r, y - r, x + r, y + r,
            fill=color, outline="", stipple=stipple, tags="stroke"
        )
        self._current_stroke.canvas_ids.append(dot_id)

    def _on_mouse_move(self, event):
        if not self._current_stroke:
            if self._tool == "eraser":
                self._erase_at(event.x, event.y)
            return

        raw_x, raw_y = float(event.x), float(event.y)
        a = self._ema_alpha
        x = a * raw_x + (1 - a) * self._ema_x
        y = a * raw_y + (1 - a) * self._ema_y
        self._ema_x = x
        self._ema_y = y

        pts = self._current_stroke.points
        if pts:
            dx = x - pts[-1][0]
            dy = y - pts[-1][1]
            if dx * dx + dy * dy < 9:
                return

        pts.append((x, y))
        stipple = "gray50" if self._current_stroke.is_highlighter else ""

        if len(pts) >= 4:
            smoothed = self._catmull_rom_segment(
                pts[-4], pts[-3], pts[-2], pts[-1], num_points=8
            )
            flat = []
            for p in smoothed:
                flat.extend(p)
            flat.extend([pts[-1][0], pts[-1][1]])

            if len(flat) >= 4:
                line_id = self._canvas.create_line(
                    *flat, fill=self._current_stroke.color,
                    width=self._current_stroke.width,
                    smooth=True, splinesteps=16,
                    capstyle=tk.ROUND, joinstyle=tk.ROUND,
                    stipple=stipple, tags="stroke"
                )
                self._current_stroke.canvas_ids.append(line_id)
        elif len(pts) >= 2:
            line_id = self._canvas.create_line(
                pts[-2][0], pts[-2][1], pts[-1][0], pts[-1][1],
                fill=self._current_stroke.color,
                width=self._current_stroke.width,
                capstyle=tk.ROUND, stipple=stipple, tags="stroke"
            )
            self._current_stroke.canvas_ids.append(line_id)

    def _on_mouse_up(self, event):
        if not self._current_stroke:
            return

        stroke = self._current_stroke
        self._current_stroke = None

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
                stipple = "gray50" if stroke.is_highlighter else ""
                line_id = self._canvas.create_line(
                    *flat, fill=stroke.color, width=stroke.width,
                    smooth=True, splinesteps=32,
                    capstyle=tk.ROUND, joinstyle=tk.ROUND,
                    stipple=stipple, tags="stroke"
                )
                stroke.canvas_ids = [line_id]

        self._strokes.append(stroke)
        self._undo_stack.clear()

    # ── Catmull-Rom Smoothing ─────────────────────────

    @staticmethod
    def _catmull_rom_segment(p0, p1, p2, p3, num_points=8):
        points = []
        for i in range(num_points):
            t = i / num_points
            t2 = t * t
            t3 = t2 * t
            x = 0.5 * ((2*p1[0]) + (-p0[0]+p2[0])*t +
                        (2*p0[0]-5*p1[0]+4*p2[0]-p3[0])*t2 +
                        (-p0[0]+3*p1[0]-3*p2[0]+p3[0])*t3)
            y = 0.5 * ((2*p1[1]) + (-p0[1]+p2[1])*t +
                        (2*p0[1]-5*p1[1]+4*p2[1]-p3[1])*t2 +
                        (-p0[1]+3*p1[1]-3*p2[1]+p3[1])*t3)
            points.append((x, y))
        return points

    @staticmethod
    def _rdp_simplify(points, epsilon=1.5):
        if len(points) <= 2:
            return list(points)
        start, end = points[0], points[-1]
        max_dist = 0.0
        max_idx = 0
        dx_line = end[0] - start[0]
        dy_line = end[1] - start[1]
        line_len_sq = dx_line * dx_line + dy_line * dy_line

        for i in range(1, len(points) - 1):
            px, py = points[i]
            if line_len_sq == 0:
                dist = ((px - start[0])**2 + (py - start[1])**2) ** 0.5
            else:
                t = max(0, min(1, ((px-start[0])*dx_line + (py-start[1])*dy_line) / line_len_sq))
                proj_x = start[0] + t * dx_line
                proj_y = start[1] + t * dy_line
                dist = ((px-proj_x)**2 + (py-proj_y)**2) ** 0.5
            if dist > max_dist:
                max_dist = dist
                max_idx = i

        if max_dist > epsilon:
            left = PenOverlay._rdp_simplify(points[:max_idx+1], epsilon)
            right = PenOverlay._rdp_simplify(points[max_idx:], epsilon)
            return left[:-1] + right
        return [start, end]

    def _smooth_full_stroke(self, raw_points):
        if len(raw_points) < 3:
            return list(raw_points)
        pts = self._rdp_simplify(raw_points, epsilon=1.5)
        if len(pts) < 3:
            pts = raw_points

        result = []
        for i in range(len(pts) - 1):
            p0 = pts[max(0, i-1)]
            p1 = pts[i]
            p2 = pts[min(len(pts)-1, i+1)]
            p3 = pts[min(len(pts)-1, i+2)]
            segment = self._catmull_rom_segment(p0, p1, p2, p3, num_points=10)
            result.extend(segment)
        result.append(pts[-1])
        result = self._chaikin_smooth(result, iterations=1)
        return result

    @staticmethod
    def _chaikin_smooth(points, iterations=1):
        if len(points) < 3:
            return list(points)
        pts = list(points)
        for _ in range(iterations):
            new_pts = [pts[0]]
            for i in range(len(pts) - 1):
                p0, p1 = pts[i], pts[i+1]
                new_pts.append((0.75*p0[0]+0.25*p1[0], 0.75*p0[1]+0.25*p1[1]))
                new_pts.append((0.25*p0[0]+0.75*p1[0], 0.25*p0[1]+0.75*p1[1]))
            new_pts.append(pts[-1])
            pts = new_pts
        return pts

    # ── Eraser ────────────────────────────────────────

    def _erase_at(self, x, y):
        r = 15
        items = self._canvas.find_overlapping(x-r, y-r, x+r, y+r)
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
        if not self._strokes:
            return
        stroke = self._strokes.pop()
        for cid in stroke.canvas_ids:
            self._canvas.delete(cid)
        self._undo_stack.append(stroke)

    def redo(self):
        if not self._undo_stack:
            return
        stroke = self._undo_stack.pop()
        pts = stroke.smoothed_points or stroke.points
        stroke.canvas_ids.clear()
        stipple = "gray50" if stroke.is_highlighter else ""

        if len(pts) >= 2:
            flat = []
            for p in pts:
                flat.extend(p)
            line_id = self._canvas.create_line(
                *flat, fill=stroke.color, width=stroke.width,
                smooth=True, splinesteps=32,
                capstyle=tk.ROUND, joinstyle=tk.ROUND,
                stipple=stipple, tags="stroke"
            )
            stroke.canvas_ids = [line_id]
        elif len(pts) == 1:
            r = max(1, stroke.width // 2)
            dot_id = self._canvas.create_oval(
                pts[0][0]-r, pts[0][1]-r, pts[0][0]+r, pts[0][1]+r,
                fill=stroke.color, outline="", stipple=stipple, tags="stroke"
            )
            stroke.canvas_ids = [dot_id]
        self._strokes.append(stroke)

    def clear_all(self):
        self._canvas.delete("stroke")
        self._strokes.clear()
        self._undo_stack.clear()

    # ── Click-Through Toggle ──────────────────────────

    def set_click_through(self, enabled: bool):
        if not hasattr(self, '_input_hwnd'):
            return
        try:
            style = user32.GetWindowLongW(self._input_hwnd, GWL_EXSTYLE)
            if enabled:
                style |= WS_EX_TRANSPARENT
                self._input_canvas.configure(cursor="arrow")
            else:
                style &= ~WS_EX_TRANSPARENT
                cursor = "circle" if self._tool == "eraser" else self._pen_cursor
                self._input_canvas.configure(cursor=cursor)
            user32.SetWindowLongW(self._input_hwnd, GWL_EXSTYLE, style)
            user32.SetWindowPos(
                self._input_hwnd, None, 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED
            )
            self._click_through = enabled
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
        self._tool = tool
        if self._click_through:
            return
        if tool == "eraser":
            self._input_canvas.configure(cursor="circle")
        else:
            self._input_canvas.configure(cursor=self._pen_cursor)

    def set_highlighter_color(self, color: str):
        self._highlighter_color = color

    # ── Z-Order helpers (split lift for main widget clickability) ──

    def lift_input(self):
        """Lift only the input window (goes BELOW main widget)."""
        try:
            self._input_win.lift()
        except:
            pass

    def lift_render(self):
        """Lift only the render window (goes ABOVE main widget)."""
        try:
            self._render_win.lift()
        except:
            pass

    # ── Tkinter-Compatible API ────────────────────────

    def winfo_exists(self):
        try:
            return self._render_win.winfo_exists() and self._input_win.winfo_exists()
        except:
            return False

    def attributes(self, *args, **kwargs):
        try:
            self._render_win.attributes(*args, **kwargs)
            self._input_win.attributes(*args, **kwargs)
        except:
            pass

    def lift(self):
        try:
            self._input_win.lift()
            self._render_win.lift()
        except:
            pass

    def withdraw(self):
        try:
            self._render_win.withdraw()
            self._input_win.withdraw()
        except:
            pass

    def deiconify(self):
        try:
            self._input_win.deiconify()
            self._render_win.deiconify()
        except:
            pass

    def destroy(self):
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
        return getattr(self, '_render_hwnd', None)

    def get_all_hwnds(self):
        hwnds = []
        if hasattr(self, '_render_hwnd') and self._render_hwnd:
            hwnds.append(self._render_hwnd)
        if hasattr(self, '_input_hwnd') and self._input_hwnd:
            hwnds.append(self._input_hwnd)
        return hwnds

    def close(self):
        if self._on_close:
            self._on_close()
        else:
            self.destroy()
