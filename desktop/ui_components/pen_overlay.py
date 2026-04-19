# ui_components/pen_overlay.py
"""PenOverlay — Fullscreen transparent canvas for screen annotation.

Two-window technique for proper transparent drawing on Windows:
  render_win — Shows strokes at full opacity, transparent bg (WS_EX_TRANSPARENT)
  input_win  — Nearly invisible (alpha=1/255), captures all mouse events

Drawing logic delegated to DrawingEngine (drawing_engine.py)."""

import tkinter as tk
import ctypes
import ctypes.wintypes
import struct
import os
import io
import tempfile
from typing import Optional, Callable

from ui_components.drawing_engine import Stroke, DrawingEngine

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

        # DPI-aware sizing: scale the cursor for high-DPI displays
        dpi_scale = 1.0
        try:
            import ctypes as _ct
            dpi_scale = _ct.windll.shcore.GetScaleFactorForDevice(0) / 100.0
        except Exception:
            try:
                import ctypes as _ct
                hdc = _ct.windll.user32.GetDC(0)
                dpi_x = _ct.windll.gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
                _ct.windll.user32.ReleaseDC(0, hdc)
                dpi_scale = max(1.0, dpi_x / 96.0)
            except Exception:
                dpi_scale = 1.0
        # ICO/CUR standard sizes that PIL accepts without warning
        base_sz = 32
        target = int(base_sz * dpi_scale)
        # Pick the closest valid size (16, 24, 32, 48, 64) >= target/scaled
        for std in (32, 48, 64):
            if std >= target:
                sz = std
                break
        else:
            sz = 64
        s = sz / 32.0  # scale factor relative to original 32x32 design

        def sp(x, y):
            return (int(x * s), int(y * s))

        img = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        # Thick pen: tip at bottom-left, body upper-right
        # White outer body (visible on dark backgrounds)
        d.polygon([
            sp(0, 31), sp(2, 27), sp(25, 4), sp(29, 0),
            sp(31, 2), sp(8, 25), sp(4, 29), sp(2, 31)
        ], fill=(255, 255, 255, 255))
        # Black inner body (visible on light backgrounds)
        d.polygon([
            sp(1, 29), sp(3, 27), sp(26, 4), sp(28, 2),
            sp(29, 3), sp(7, 25), sp(5, 27), sp(3, 29)
        ], fill=(20, 20, 20, 255))
        # Colored pen tip
        d.polygon([
            sp(0, 31), sp(1, 29), sp(3, 27), sp(2, 27), sp(0, 29)
        ], fill=(200, 50, 50, 255))
        # White tip dot for precision
        d.rectangle([sp(0, 30), sp(1, 31)], fill=(255, 255, 255, 255))

        # Save as ICO, then patch to CUR
        buf = io.BytesIO()
        img.save(buf, format='ICO', sizes=[(sz, sz)])
        data = bytearray(buf.getvalue())

        # Patch header: type 1 (ICO) → 2 (CUR)
        struct.pack_into("<H", data, 2, 2)
        # Patch directory: planes/bpp → hotspot (scaled tip position)
        hotspot_x = int(1 * s)
        hotspot_y = int(30 * s)
        struct.pack_into("<H", data, 10, hotspot_x)
        struct.pack_into("<H", data, 12, hotspot_y)

        cur_path = os.path.join(tempfile.gettempdir(), f"voiceai_pen_{sz}.cur")
        with open(cur_path, "wb") as f:
            f.write(data)

        _PEN_CURSOR_PATH = cur_path
        # Forward slashes for Tcl compatibility
        return "@" + cur_path.replace("\\", "/")
    except Exception as e:
        print(f"[PEN] Custom cursor failed: {e}")
        return "pencil"  # Fallback


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
    _supports_view_mode = True

    def __init__(self, parent, on_close_callback: Optional[Callable] = None):
        self._parent = parent
        self._on_close = on_close_callback
        self._destroyed = False
        self._click_through = False

        # Custom cursor
        self._pen_cursor = _get_pen_cursor()

        # Screen dimensions
        self._vx, self._vy, self._vw, self._vh = self._get_screen_dims()

        # Build windows (with cleanup on failure to prevent black screen)
        try:
            self._setup_render_window()
            self._setup_input_window()

            # Drawing engine operates on render canvas
            self._engine = DrawingEngine(self._canvas, self._parent)
            self._engine._overlay_mode = True

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
        except (OSError, ctypes.ArgumentError):
            pass
        try:
            return 0, 0, user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        except (OSError, ctypes.ArgumentError):
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
        def _on_mouse_down(event):
            if self._engine.tool in ("text", "handwrite"):
                self._grab_focus()
            self._engine.on_mouse_down(event)
        self._input_canvas.bind("<ButtonPress-1>", _on_mouse_down)
        self._input_canvas.bind("<B1-Motion>", self._engine.on_mouse_move)
        self._input_canvas.bind("<ButtonRelease-1>", self._engine.on_mouse_up)
        self._input_win.bind("<Control-z>", lambda e: self._engine.undo())
        self._input_win.bind("<Control-y>", lambda e: self._engine.redo())
        self._input_win.bind("<Escape>", lambda e: self._on_escape())
        def _on_key(event):
            self._engine.on_key(event)
            if self._engine._text_active:
                return "break"
        self._input_win.bind("<Key>", _on_key)

    def _on_escape(self):
        """Escape: finalize text if active, otherwise close."""
        if self._engine._text_active:
            self._engine.on_escape()
        else:
            self.close()

    # ── Delegated Drawing API ─────────────────────────

    def auto_place_text(self):
        self._engine.auto_place_text()
        self._input_win.focus_force()

    def set_font(self, font_family: str):
        self._engine.set_font(font_family)

    def set_hw_font(self, font_family, font_size=None):
        self._engine.set_hw_font(font_family, font_size)

    def set_text_font_size(self, size: int):
        self._engine._text_font_size = size
        if self._engine._text_active:
            self._engine._update_text_display()

    def undo(self):
        self._engine.undo()

    def redo(self):
        self._engine.redo()

    def clear_all(self):
        self._engine.clear_all()

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
                tool = self._engine.tool
                if tool == "eraser":
                    cursor = "circle"
                elif tool == "text":
                    cursor = "xterm"
                else:
                    cursor = self._pen_cursor
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
        self._engine.set_color(color)

    def set_width(self, width: int):
        self._engine.set_width(width)

    def set_tool(self, tool: str):
        self._engine.set_tool(tool)
        self._update_cursor()
        if tool in ("text", "handwrite"):
            self._grab_focus()

    def set_highlighter_color(self, color: str):
        self._engine.set_highlighter_color(color)

    def _grab_focus(self):
        """Steal OS-level focus to input window so keystrokes land here."""
        try:
            if hasattr(self, '_input_hwnd'):
                user32.SetForegroundWindow(self._input_hwnd)
            self._input_win.focus_force()
            self._input_canvas.focus_set()
        except Exception:
            pass

    def _update_cursor(self):
        if self._click_through:
            return
        tool = self._engine.tool
        if tool == "eraser":
            self._input_canvas.configure(cursor="circle")
        else:
            self._input_canvas.configure(cursor=self._pen_cursor)

    # ── Z-Order helpers (split lift for main widget clickability) ──

    def lift_input(self):
        """Lift only the input window (goes BELOW main widget)."""
        try:
            self._input_win.lift()
        except tk.TclError:
            pass

    def lift_render(self):
        """Lift only the render window (goes ABOVE main widget)."""
        try:
            self._render_win.lift()
        except tk.TclError:
            pass

    # ── Tkinter-Compatible API ────────────────────────

    def winfo_exists(self):
        try:
            return self._render_win.winfo_exists() and self._input_win.winfo_exists()
        except tk.TclError:
            return False

    def attributes(self, *args, **kwargs):
        try:
            self._render_win.attributes(*args, **kwargs)
            self._input_win.attributes(*args, **kwargs)
        except tk.TclError:
            pass

    def lift(self):
        try:
            self._input_win.lift()
            self._render_win.lift()
        except tk.TclError:
            pass

    def withdraw(self):
        try:
            self._render_win.withdraw()
            self._input_win.withdraw()
        except tk.TclError:
            pass

    def deiconify(self):
        try:
            self._input_win.deiconify()
            self._render_win.deiconify()
        except tk.TclError:
            pass

    def destroy(self):
        self._destroyed = True
        if hasattr(self, '_engine'):
            self._engine.cleanup()
        try:
            self._input_win.destroy()
        except tk.TclError:
            pass
        try:
            self._render_win.destroy()
        except tk.TclError:
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
