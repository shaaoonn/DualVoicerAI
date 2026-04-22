# ui/editor_window.py
"""EditorWindow - Built-in image/PDF editor with permanent annotations.

Multi-page editor using DrawingEngine. No built-in toolbar - uses
the same PenToolbar as the pen overlay, so tools aren't duplicated.
Supports opening images/PDFs, importing pages, exporting to PDF/PNG/JPG,
and saving in internal .dvai format."""

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import json
import base64
import os
import io
import sys
import struct
import threading
from typing import List, Optional

from PIL import Image, ImageTk, ImageDraw, ImageFont, ImageChops
from ui_components.drawing_engine import Stroke, DrawingEngine
from ui_components.pen_overlay import _get_pen_cursor
from ui_components.selection_manager import SelectionManager
try:
    from i18n import tr
except Exception:
    def tr(key, **kwargs):
        return kwargs and key.format(**kwargs) or key

try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False


# ── Page Size Presets ──────────────────────────────

PAGE_PRESETS = {
    "A4":       (794, 1123),
    "Legal":    (794, 1346),
    "HD (16:9)":(1920, 1080),
    "4K":       (3840, 2160),
    "Book (6×9\")": (576, 864),
    "Square":   (1080, 1080),
}

GAP = 30          # pixels between pages
BG_COLOR = "#2B2B35"
PAGE_SHADOW = "#1A1A22"
SESSION_FILE = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')),
                            'DualVoicer', 'editor_session.dvai')


class EditorPage:
    """One page in the editor - has its own DrawingEngine."""

    def __init__(self, canvas: tk.Canvas, parent_widget,
                 width: int, height: int, y_offset: int,
                 bg_image: Optional[Image.Image] = None):
        self.width = width
        self.height = height
        self.y_offset = y_offset
        self.bg_image = bg_image
        self._bg_tk = None
        self._bg_canvas_id = None
        self._rect_id = None
        self._canvas = canvas
        self._parent = parent_widget
        self._shadow_id = None

        # Drop shadow
        self._shadow_id = canvas.create_rectangle(
            4, y_offset + 4, width + 4, y_offset + height + 4,
            fill=PAGE_SHADOW, outline="", tags="page_bg"
        )
        # Page rectangle
        self._rect_id = canvas.create_rectangle(
            0, y_offset, width, y_offset + height,
            fill="white", outline="#444", width=1, tags="page_bg"
        )

        # Background image
        if bg_image:
            self._set_bg_image(bg_image)

        # DrawingEngine for this page
        self.engine = DrawingEngine(canvas, parent_widget)

    def _set_bg_image(self, img: Image.Image):
        self.bg_image = img
        self._bg_tk = ImageTk.PhotoImage(img)
        if self._bg_canvas_id:
            self._canvas.delete(self._bg_canvas_id)
        self._bg_canvas_id = self._canvas.create_image(
            0, self.y_offset, anchor="nw", image=self._bg_tk, tags="page_bg"
        )
        self._canvas.tag_lower("page_bg")

    def cleanup(self):
        self.engine.cleanup()

    def composite(self, skip_text=False) -> Image.Image:
        """Render page to PIL Image (bg + strokes).
        Reads actual canvas item coordinates to handle zoom correctly."""
        result = Image.new("RGBA", (self.width, self.height), (255, 255, 255, 255))

        if self.bg_image:
            bg = self.bg_image.convert("RGBA")
            result.paste(bg, (0, 0))

        # Get page rect in current (possibly zoomed) canvas coords
        page_coords = self._canvas.coords(self._rect_id)
        if len(page_coords) >= 4:
            px1, py1, px2, py2 = page_coords
            zw = px2 - px1
            zh = py2 - py1
        else:
            px1, py1 = 0.0, float(self.y_offset)
            zw, zh = float(self.width), float(self.height)

        sx = self.width / zw if zw > 0 else 1.0
        sy = self.height / zh if zh > 0 else 1.0

        # DPI factor: tkinter renders fonts at screen DPI, PIL at 72
        try:
            dpi = self._parent.winfo_fpixels('1i')
        except Exception:
            dpi = 96
        dpi_factor = dpi / 72.0

        draw = ImageDraw.Draw(result)
        for stroke in self.engine.get_strokes():
            if getattr(stroke, '_is_image', False):
                try:
                    coords = self._canvas.coords(stroke.canvas_ids[0])
                    ix = (coords[0] - px1) * sx
                    iy = (coords[1] - py1) * sy
                except (tk.TclError, IndexError):
                    ix, iy = stroke.points[0][0], stroke.points[0][1] - self.y_offset
                pil_img = stroke._pil_image
                try:
                    result.paste(pil_img, (int(ix), int(iy)), pil_img)
                except ValueError:
                    result.paste(pil_img, (int(ix), int(iy)))
                draw = ImageDraw.Draw(result)
                continue

            if stroke.is_text:
                if skip_text:
                    continue
                # Read actual canvas text position
                try:
                    coords = self._canvas.coords(stroke.canvas_ids[0])
                    cx, cy = coords[0], coords[1]
                except (tk.TclError, IndexError):
                    cx, cy = stroke.points[0]
                rx = (cx - px1) * sx
                ry = (cy - py1) * sy
                font_size = max(8, int(stroke.font_size * dpi_factor))
                text = stroke.text or ""

                # Try Windows GDI first (proper Bengali/complex script shaping)
                if sys.platform == "win32" and text.strip():
                    self._register_bundled_fonts_gdi()
                    gdi_img = self._gdi_render_text(
                        text, stroke.font_family, font_size, stroke.color)
                    if gdi_img:
                        try:
                            result.paste(gdi_img, (int(rx), int(ry)), gdi_img)
                        except ValueError:
                            result.paste(gdi_img, (int(rx), int(ry)))
                        draw = ImageDraw.Draw(result)
                        continue

                # Fallback: PIL rendering
                font = self._resolve_font(stroke.font_family, font_size)
                if "\n" in text:
                    lines = text.split("\n")
                    line_y = ry
                    for line in lines:
                        draw.text((rx, line_y), line, fill=stroke.color,
                                  font=font, anchor="lt")
                        try:
                            lh = font.getbbox("Ay")[3]
                        except Exception:
                            lh = font_size
                        line_y += lh + 2
                else:
                    pil_anchor = "lt" if stroke.anchor == "nw" else "lm"
                    draw.text((rx, ry), text, fill=stroke.color,
                              font=font, anchor=pil_anchor)
            else:
                # Read canvas item coords (handles zoom correctly)
                all_points = []
                for cid in stroke.canvas_ids:
                    try:
                        itype = self._canvas.type(cid)
                        coords = self._canvas.coords(cid)
                    except tk.TclError:
                        continue
                    if itype == "line" and len(coords) >= 4:
                        for j in range(0, len(coords), 2):
                            all_points.append((coords[j], coords[j + 1]))
                    elif itype == "oval" and len(coords) >= 4:
                        ocx = (coords[0] + coords[2]) / 2
                        ocy = (coords[1] + coords[3]) / 2
                        all_points.append((ocx, ocy))

                # Convert to page-relative coordinates
                adjusted = [((x - px1) * sx, (y - py1) * sy)
                            for x, y in all_points]
                w = max(1, int(stroke.width * sy))

                if len(adjusted) >= 2:
                    color = stroke.color
                    if stroke.is_highlighter:
                        overlay = Image.new("RGBA", result.size, (0, 0, 0, 0))
                        od = ImageDraw.Draw(overlay)
                        r, g, b = self._hex_to_rgb(color)
                        od.line(adjusted, fill=(r, g, b, 100), width=w)
                        result = Image.alpha_composite(result, overlay)
                        draw = ImageDraw.Draw(result)
                    else:
                        draw.line(adjusted, fill=color, width=w, joint="curve")
                elif len(adjusted) == 1:
                    r = max(1, w // 2)
                    x, y = adjusted[0]
                    draw.ellipse([x - r, y - r, x + r, y + r],
                                 fill=stroke.color)

        return result

    @staticmethod
    def _resolve_font(family, size):
        """Resolve font family name to a PIL ImageFont, searching bundled fonts."""
        import os
        fonts_dir = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "fonts")

        # Try direct family name + .ttf
        candidates = [
            os.path.join(fonts_dir, family + ".ttf"),
            os.path.join(fonts_dir, family.replace(" ", "") + "-Regular.ttf"),
        ]
        # Also search all files in fonts/ for a matching name
        if os.path.isdir(fonts_dir):
            for fname in os.listdir(fonts_dir):
                if fname.lower().endswith(".ttf"):
                    # Match by family name in filename (case-insensitive)
                    if family.lower().replace(" ", "") in fname.lower().replace(" ", ""):
                        candidates.insert(0, os.path.join(fonts_dir, fname))

        for path in candidates:
            if os.path.isfile(path):
                try:
                    return ImageFont.truetype(path, size)
                except OSError:
                    continue

        # System font fallback
        for sys_name in [family + ".ttf", family, "arial.ttf", "segoeui.ttf"]:
            try:
                return ImageFont.truetype(sys_name, size)
            except OSError:
                continue
        return ImageFont.load_default()

    @staticmethod
    def _hex_to_rgb(hex_color):
        h = hex_color.lstrip("#")
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

    # ── Windows GDI text renderer (proper Bengali/complex script shaping) ──

    _gdi_fonts_registered = False

    @classmethod
    def _register_bundled_fonts_gdi(cls):
        """Register bundled TTF fonts with Windows GDI (once per process)."""
        if cls._gdi_fonts_registered:
            return
        cls._gdi_fonts_registered = True
        try:
            import ctypes
            gdi32 = ctypes.windll.gdi32
            fonts_dir = os.path.join(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))), "fonts")
            if os.path.isdir(fonts_dir):
                for fname in os.listdir(fonts_dir):
                    if fname.lower().endswith((".ttf", ".otf")):
                        path = os.path.join(fonts_dir, fname)
                        gdi32.AddFontResourceExW(path, 0x10, 0)  # FR_PRIVATE
        except Exception:
            pass

    @staticmethod
    def _gdi_render_text(text, font_family, font_size_px, color_hex):
        """Render text using Windows GDI for proper complex script shaping.
        Returns RGBA PIL Image with transparent background, or None on failure."""
        if not text or sys.platform != "win32":
            return None
        try:
            import ctypes
            from ctypes import wintypes

            gdi32 = ctypes.windll.gdi32
            user32 = ctypes.windll.user32

            # Parse color
            c = color_hex.lstrip("#")
            if len(c) >= 6:
                cr, cg, cb = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
            else:
                cr, cg, cb = 0, 0, 0

            # Create memory DC and font
            mem_dc = gdi32.CreateCompatibleDC(0)
            hFont = gdi32.CreateFontW(
                -font_size_px, 0, 0, 0,
                400, 0, 0, 0,       # weight=NORMAL, no italic/underline/strikeout
                0, 0, 0,            # charset=DEFAULT, precision defaults
                4,                  # ANTIALIASED_QUALITY (grayscale, not ClearType)
                0, font_family
            )
            old_font = gdi32.SelectObject(mem_dc, hFont)

            # Measure each line
            lines = text.split("\n")
            max_w = 0
            line_heights = []
            for line in lines:
                sz = wintypes.SIZE()
                t = line if line else " "
                gdi32.GetTextExtentPoint32W(mem_dc, t, len(t), ctypes.byref(sz))
                max_w = max(max_w, sz.cx)
                line_heights.append(sz.cy)

            pad = 4
            w = max(max_w + pad, 1)
            h = max(sum(line_heights) + pad, 1)

            # BITMAPINFOHEADER: 40 bytes, top-down 32bpp
            bmi = (ctypes.c_byte * 40)()
            struct.pack_into("iiiHHiiiiii", bmi, 0,
                             40, w, -h, 1, 32, 0, 0, 0, 0, 0, 0)

            def _render_pass(bg_colorref):
                ppv = ctypes.c_void_p()
                hBmp = gdi32.CreateDIBSection(
                    mem_dc, bmi, 0, ctypes.byref(ppv), None, 0)
                if not hBmp:
                    return None
                old_bmp = gdi32.SelectObject(mem_dc, hBmp)
                # Fill background
                rect = wintypes.RECT(0, 0, w, h)
                hBr = gdi32.CreateSolidBrush(bg_colorref)
                user32.FillRect(mem_dc, ctypes.byref(rect), hBr)
                gdi32.DeleteObject(hBr)
                # Draw text
                gdi32.SetTextColor(mem_dc, cr | (cg << 8) | (cb << 16))
                gdi32.SetBkMode(mem_dc, 1)  # TRANSPARENT
                y = 0
                for i, line in enumerate(lines):
                    if line:
                        gdi32.TextOutW(mem_dc, 0, y, line, len(line))
                    y += line_heights[i]
                # Read pixels
                buf = (ctypes.c_ubyte * (w * h * 4))()
                ctypes.memmove(buf, ppv, w * h * 4)
                gdi32.SelectObject(mem_dc, old_bmp)
                gdi32.DeleteObject(hBmp)
                return bytes(buf)

            buf_w = _render_pass(0xFFFFFF)   # white background
            buf_b = _render_pass(0x000000)   # black background

            # Cleanup GDI
            gdi32.SelectObject(mem_dc, old_font)
            gdi32.DeleteObject(hFont)
            gdi32.DeleteDC(mem_dc)

            if not buf_w or not buf_b:
                return None

            # Compute alpha via dual-render: alpha = 255 - (W - B) per channel
            img_w = Image.frombuffer("RGBA", (w, h), buf_w, "raw", "BGRA", 0, 1)
            img_b = Image.frombuffer("RGBA", (w, h), buf_b, "raw", "BGRA", 0, 1)

            rw, gw, bw, _ = img_w.split()
            rb, gb, bb, _ = img_b.split()

            ones = Image.new("L", (w, h), 255)
            diff_r = ImageChops.subtract(rw, rb)
            diff_g = ImageChops.subtract(gw, gb)
            diff_b = ImageChops.subtract(bw, bb)
            max_diff = ImageChops.lighter(
                ImageChops.lighter(diff_r, diff_g), diff_b)
            alpha = ImageChops.subtract(ones, max_diff)

            result = Image.new("RGBA", (w, h), (cr, cg, cb, 255))
            result.putalpha(alpha)
            return result

        except Exception:
            return None

    @staticmethod
    def _resolve_font_path(family):
        """Resolve font family name to a file path for PyMuPDF."""
        fonts_dir = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "fonts")
        if os.path.isdir(fonts_dir):
            for fname in os.listdir(fonts_dir):
                if fname.lower().endswith(".ttf"):
                    if family.lower().replace(" ", "") in fname.lower().replace(" ", ""):
                        return os.path.join(fonts_dir, fname)
        # Direct name match
        path = os.path.join(fonts_dir, family + ".ttf")
        if os.path.isfile(path):
            return path
        return None

    @staticmethod
    def _hex_to_rgb_float(hex_color):
        """Convert hex color to (r, g, b) floats 0..1 for PyMuPDF."""
        h = hex_color.lstrip("#")
        try:
            return (int(h[0:2], 16) / 255.0,
                    int(h[2:4], 16) / 255.0,
                    int(h[4:6], 16) / 255.0)
        except (ValueError, IndexError):
            return (0, 0, 0)


class EditorWindow(tk.Toplevel):
    """Built-in multi-page editor.

    Uses the same PenToolbar as the pen overlay - implements the same
    API (set_tool, set_color, set_width, set_font, undo, redo, etc.)
    so PenToolbar can target this window without any changes.
    """

    _supports_view_mode = False  # No click-through toggle in editor

    # ── Unified toolbar theme (professional) ──
    TB_BG = "#1A1A2E"
    TB_BG_ACTIVE = "#3D5AFE"
    TB_BG_HOVER = "#2A2A45"
    TB_ACCENT = "#3D5AFE"
    TB_TEXT = "#C8C8DC"
    TB_TEXT_DIM = "#787890"
    TB_BORDER = "#2E2E4A"
    ICON_PEN = "\u270f\ufe0f"
    ICON_HIGHLIGHTER = "\U0001f58d\ufe0f"
    ICON_ERASER = "\U0001f9f9"
    ICON_MOUSE = "\U0001f5b1\ufe0f"
    ICON_TEXT = "T"
    ICON_HANDWRITE = "\u270d\ufe0f"
    ICON_SELECT = "\u2922"               # ⤢ select / move arrow
    ICON_MIC = "\U0001f399\ufe0f"       # 🎙️ Studio mic
    ICON_SOUND = "\U0001f50a"            # 🔊 Speaker
    ICON_AI = "\U0001f916"               # 🤖 Robot
    ICON_CAMERA = "\U0001f4f7"           # 📷 Camera
    ICON_SETTINGS = "\u2699\ufe0f"       # ⚙️ Gear
    ICON_UNDO = "\u21a9"                 # ↩
    ICON_REDO = "\u21aa"                 # ↪
    ICON_TRASH = "\U0001f5d1"            # 🗑
    ICON_FULLSCREEN = "\u26f6"           # ⛶
    ICON_CLOSE = "\u2716"                # ✖
    TB_COLORS = [
        ("#FF0000", "Red"), ("#0066FF", "Blue"), ("#00CC44", "Green"),
        ("#000000", "Black"), ("#FFFFFF", "White"), ("#FFaa00", "Orange"),
    ]

    def __init__(self, parent, app_ref):
        super().__init__(parent)
        self._app = app_ref
        self._pages: List[EditorPage] = []
        self._active_page_idx = 0
        self._active_tool = "pen"
        self._save_path: Optional[str] = None
        self._fullscreen = False
        self._plus_buttons = []
        self._page_number_labels = []
        self._pen_toolbar = None
        self._toolbar_frame = None

        self._zoom_level = 1.0
        self._base_scrollregion = (0, 0, 1920, 1120)
        self._selection_mgr = None

        self._setup_window()
        self._build_menu()
        self._build_status_bar()           # pack bottom → very bottom
        self._build_editor_toolbar()       # pack bottom → above status
        self._build_canvas_area()          # fill="both" → fills rest

        self._selection_mgr = SelectionManager(self._canvas)

        # Add initial page and update scroll
        self._add_page(1920, 1080)
        self._update_scroll()

        # Apply correct pen cursor + update toolbar icon for initial active tool
        self.set_tool("pen")
        self._tb_update_tool_icons()

        self.bind("<F11>", lambda e: self._toggle_fullscreen())
        self.bind("<Escape>", self._on_escape)
        self.bind("<Control-v>", lambda e: self._paste_from_clipboard())
        # Track foreground state - used by voice typing in main.py to decide
        # whether to inject into the editor's text item or send to the OS-
        # active window. Default False so voice goes to the OS app the user
        # is actually looking at, not the editor in the background.
        self._has_foreground = False
        # Ensure canvas gets focus when editor window is activated
        def _on_focus_in(e):
            if e.widget is self:
                self._has_foreground = True
                self._canvas.focus_set()
        def _on_focus_out(e):
            if e.widget is self:
                self._has_foreground = False
        self.bind("<FocusIn>", _on_focus_in, add="+")
        self.bind("<FocusOut>", _on_focus_out, add="+")
        self.protocol("WM_DELETE_WINDOW", self._on_close_window)
        # Start periodic auto-save (every 60s)
        self._autosave_job = None
        self._schedule_autosave()

    def _setup_window(self):
        self.title(tr("editor_title"))
        self.geometry("1200x800")
        self.configure(bg=BG_COLOR)
        self.minsize(600, 400)
        try:
            self.iconbitmap(os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                        "DualVoicerLogo.ico"))
        except (tk.TclError, FileNotFoundError):
            pass

    def _tb_make_btn(self, parent, text, command, bg=None, fg=None,
                     font=None, width=None, is_emoji=False, tooltip=None):
        """Create a professional toolbar button with hover effects."""
        _bg = bg or self.TB_BG
        _fg = fg or self.TB_TEXT
        _font = font or (("Segoe UI Emoji", 12) if is_emoji else ("Segoe UI", 9, "bold"))
        kw = {}
        if width is not None:
            kw["width"] = width
        btn = tk.Button(parent, text=text, bg=_bg, fg=_fg, font=_font,
                        relief="flat", bd=0, padx=6, pady=3, cursor="hand2",
                        activebackground=self.TB_BG_HOVER, activeforeground="#FFF",
                        command=command, **kw)
        # Hover effect
        normal_bg = _bg
        btn.bind("<Enter>", lambda e, b=btn, nb=normal_bg: b.configure(
            bg=self.TB_BG_HOVER if nb == self.TB_BG else nb))
        btn.bind("<Leave>", lambda e, b=btn, nb=normal_bg: b.configure(bg=nb))
        if tooltip:
            self._tb_add_tooltip(btn, tooltip)
        return btn

    def _tb_add_tooltip(self, widget, text):
        """Add a hover tooltip to a widget."""
        tip = None
        def show(e):
            nonlocal tip
            tip = tk.Toplevel(widget)
            tip.wm_overrideredirect(True)
            tip.wm_geometry(f"+{e.x_root+10}+{e.y_root-28}")
            lbl = tk.Label(tip, text=text, bg="#1E1E32", fg="#E0E0E0",
                           font=("Segoe UI", 8), relief="solid", bd=1, padx=4, pady=2)
            lbl.pack()
        def hide(e):
            nonlocal tip
            if tip:
                tip.destroy()
                tip = None
        widget.bind("<Enter>", lambda e: (show(e)), add="+")
        widget.bind("<Leave>", lambda e: hide(e), add="+")

    def _tb_separator(self, parent):
        """Create a subtle vertical separator."""
        sep = tk.Frame(parent, bg=self.TB_BORDER, width=1)
        sep.pack(side="left", fill="y", padx=6, pady=4)
        return sep

    def _build_editor_toolbar(self):
        """Unified single-row professional toolbar - voice, tools, drawing, colors, sliders."""
        bg = self.TB_BG

        # ── Main container with top accent border ──
        self._toolbar_frame = tk.Frame(self, bg=bg)
        self._toolbar_frame.pack(fill="x", side="bottom")
        tk.Frame(self._toolbar_frame, bg=self.TB_ACCENT, height=2).pack(fill="x")

        bar = tk.Frame(self._toolbar_frame, bg=bg, padx=6, pady=4)
        bar.pack(fill="x")

        # ═══════════════════════════════════════════════════
        # ── GROUP 1: Voice Buttons (🎙 + lang label) ──
        # ═══════════════════════════════════════════════════
        voice_grp = tk.Frame(bar, bg=bg)
        voice_grp.pack(side="left")

        lang1 = self._app.settings.get("btn1_lang", "bn-BD")
        lang2 = self._app.settings.get("btn2_lang", "en-US")
        l1_code = lang1.split("-")[0].upper()
        l2_code = lang2.split("-")[0].upper()

        # Mic button 1 (BN)
        self._tb_btn_bn = self._tb_make_btn(
            voice_grp, f"{self.ICON_MIC}{l1_code}",
            lambda: self._app.switch_language(
                self._app.settings.get("btn1_lang", "bn-BD")),
            is_emoji=True, font=("Segoe UI Emoji", 10),
            tooltip=tr("tip_voice", code=l1_code))
        self._tb_btn_bn.pack(side="left", padx=1)

        # Mic button 2 (EN)
        self._tb_btn_en = self._tb_make_btn(
            voice_grp, f"{self.ICON_MIC}{l2_code}",
            lambda: self._app.switch_language(
                self._app.settings.get("btn2_lang", "en-US")),
            is_emoji=True, font=("Segoe UI Emoji", 10),
            tooltip=tr("tip_voice", code=l2_code))
        self._tb_btn_en.pack(side="left", padx=1)

        # Sound button
        self._tb_btn_snd = self._tb_make_btn(
            voice_grp, self.ICON_SOUND,
            self._app.handle_reader_click,
            is_emoji=True, tooltip=tr("tip_sound"))
        self._tb_btn_snd.pack(side="left", padx=1)

        # AI button
        self._tb_btn_ai = self._tb_make_btn(
            voice_grp, self.ICON_AI,
            self._app.ai_trigger_flow if hasattr(self._app, 'ai_trigger_flow') else None,
            is_emoji=True, tooltip=tr("tip_ai"))
        self._tb_btn_ai.pack(side="left", padx=1)

        self._tb_separator(bar)

        # ═══════════════════════════════════════════════════
        # ── GROUP 2: Utility Tools (📷 ⚙) ──
        # ═══════════════════════════════════════════════════
        self._tb_make_btn(
            bar, self.ICON_CAMERA, self._app.take_screenshot,
            is_emoji=True, tooltip=tr("tip_screenshot")
        ).pack(side="left", padx=1)

        self._tb_make_btn(
            bar, self.ICON_SETTINGS, self._app.open_settings_panel,
            is_emoji=True, tooltip=tr("tip_settings")
        ).pack(side="left", padx=1)

        self._tb_separator(bar)

        # ═══════════════════════════════════════════════════
        # ── GROUP 3: Drawing Tools ──
        # ═══════════════════════════════════════════════════
        draw_grp = tk.Frame(bar, bg=bg)
        draw_grp.pack(side="left")

        draw_tools = [
            (self.ICON_SELECT,      "select",      tr("tip_select"),      False),
            (self.ICON_PEN,         "pen",         tr("tip_pen"),         True),
            (self.ICON_HIGHLIGHTER, "highlighter", tr("tip_highlighter"), False),
            (self.ICON_ERASER,      "eraser",      tr("tip_eraser"),      False),
            (self.ICON_TEXT,        "text",        tr("tip_text"),        False),
            (self.ICON_HANDWRITE,   "handwrite",   tr("tip_handwrite"),   False),
        ]
        self._tb_draw_btns = {}
        for icon, tool, tip, active in draw_tools:
            is_text = (tool == "text")
            cmd = (lambda: self._tb_activate_eraser()) if tool == "eraser" \
                else (lambda t=tool: self._toggle_draw_tool(t))
            btn_bg = self.TB_BG_ACTIVE if active else bg
            btn = self._tb_make_btn(
                draw_grp, icon, cmd, bg=btn_bg,
                font=("Segoe UI", 11, "bold") if is_text else ("Segoe UI Emoji", 12),
                tooltip=tip)
            btn.pack(side="left", padx=1)
            self._tb_draw_btns[tool] = btn

        self._tb_separator(bar)

        # ═══════════════════════════════════════════════════
        # ── GROUP 4: Font Dropdown ──
        # ═══════════════════════════════════════════════════
        try:
            import tkinter.font as tkfont
            all_fonts = sorted(set(tkfont.families(self)), key=lambda f: f.lower())
            all_fonts = [f for f in all_fonts if not f.startswith("@")]
        except Exception:
            all_fonts = ["Segoe UI", "Arial"]
        popular = ["Segoe UI", "Arial", "Nirmala UI", "Times New Roman",
                   "Courier New", "Impact", "Comic Sans MS", "Consolas"]
        font_list = [f for f in popular if f in all_fonts]
        remaining = [f for f in all_fonts if f not in font_list]
        if remaining:
            font_list = font_list + ["───────"] + remaining

        self._tb_font_var = tk.StringVar(value=font_list[0] if font_list else "Segoe UI")
        self._tb_font_menu = tk.OptionMenu(bar, self._tb_font_var,
            *font_list, command=self._tb_on_font_change)
        self._tb_font_menu.configure(
            bg="#16162A", fg=self.TB_TEXT, font=("Segoe UI", 8),
            highlightthickness=0, bd=1, relief="solid", width=9, anchor="w",
            activebackground=self.TB_BG_HOVER, activeforeground="#FFF",
            cursor="hand2")
        self._tb_font_menu["menu"].configure(
            bg="#16162A", fg=self.TB_TEXT, font=("Segoe UI", 9),
            activebackground=self.TB_BG_ACTIVE, activeforeground="#FFF")
        self._tb_font_menu.pack(side="left", padx=3)

        self._tb_separator(bar)

        # ═══════════════════════════════════════════════════
        # ── GROUP 5: Color Swatches ──
        # ═══════════════════════════════════════════════════
        color_grp = tk.Frame(bar, bg=bg)
        color_grp.pack(side="left")

        self._tb_color_btns = {}
        self._tb_active_color_btn = None
        for hex_color, name in self.TB_COLORS:
            btn = tk.Canvas(color_grp, width=16, height=16,
                            bg=hex_color, highlightthickness=1,
                            highlightbackground="#555", cursor="hand2")
            btn.pack(side="left", padx=2, pady=2)
            btn.bind("<Button-1>", lambda e, c=hex_color: self._tb_set_color(c))
            self._tb_color_btns[hex_color] = btn
            if hex_color == "#FF0000":
                btn.configure(highlightbackground=self.TB_ACCENT,
                              highlightthickness=2)
                self._tb_active_color_btn = btn

        self._tb_separator(bar)

        # ═══════════════════════════════════════════════════
        # ── GROUP 6: Sliders (Pen + Font size) ──
        # ═══════════════════════════════════════════════════
        slider_grp = tk.Frame(bar, bg=bg)
        slider_grp.pack(side="left")

        # Pen thickness
        tk.Label(slider_grp, text=self.ICON_PEN, bg=bg, fg=self.TB_TEXT_DIM,
                 font=("Segoe UI Emoji", 9)).pack(side="left")
        self._tb_thickness_var = tk.IntVar(value=4)
        self._tb_pen_slider = tk.Scale(
            slider_grp, from_=1, to=100, orient="horizontal",
            variable=self._tb_thickness_var, length=60, sliderlength=14,
            showvalue=False, bg=bg, fg=self.TB_TEXT, troughcolor="#16162A",
            highlightthickness=0, bd=0, activebackground=self.TB_ACCENT,
            command=self._tb_on_thickness_change)
        self._tb_pen_slider.pack(side="left", padx=(2, 0))
        self._tb_pen_val = tk.Label(slider_grp, text="4", bg=bg,
            fg=self.TB_ACCENT, font=("Segoe UI", 8, "bold"), width=3, anchor="w")
        self._tb_pen_val.pack(side="left")

        # Font size
        tk.Label(slider_grp, text="T", bg=bg, fg=self.TB_TEXT_DIM,
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(4, 0))
        self._tb_fontsize_var = tk.IntVar(value=16)
        self._tb_font_slider = tk.Scale(
            slider_grp, from_=8, to=72, orient="horizontal",
            variable=self._tb_fontsize_var, length=60, sliderlength=14,
            showvalue=False, bg=bg, fg=self.TB_TEXT, troughcolor="#16162A",
            highlightthickness=0, bd=0, activebackground=self.TB_ACCENT,
            command=self._tb_on_font_size_change)
        self._tb_font_slider.pack(side="left", padx=(2, 0))
        self._tb_font_val = tk.Label(slider_grp, text="16", bg=bg,
            fg=self.TB_ACCENT, font=("Segoe UI", 8, "bold"), width=3, anchor="w")
        self._tb_font_val.pack(side="left")

        self._tb_separator(bar)

        # ═══════════════════════════════════════════════════
        # ── GROUP 7: Actions (undo / redo / clear) ──
        # ═══════════════════════════════════════════════════
        for icon, cmd, tip in [
            (self.ICON_UNDO, self.undo, tr("tip_undo")),
            (self.ICON_REDO, self.redo, tr("tip_redo")),
            (self.ICON_TRASH, self.clear_all, tr("tip_clear")),
        ]:
            self._tb_make_btn(bar, icon, cmd, is_emoji=True,
                              tooltip=tip).pack(side="left", padx=1)

        # ═══════════════════════════════════════════════════
        # ── RIGHT SIDE: Close + Fullscreen ──
        # ═══════════════════════════════════════════════════
        # Close button (distinct red)
        close_btn = tk.Button(bar, text=self.ICON_CLOSE, bg="#6B1D30",
                              fg="#FFD0D0", font=("Segoe UI", 10, "bold"),
                              relief="flat", bd=0, padx=8, pady=3, cursor="hand2",
                              activebackground="#9B2D45", activeforeground="#FFF",
                              command=self._on_close_window)
        close_btn.pack(side="right", padx=(4, 0))
        close_btn.bind("<Enter>", lambda e: close_btn.configure(bg="#9B2D45"))
        close_btn.bind("<Leave>", lambda e: close_btn.configure(bg="#6B1D30"))
        self._tb_add_tooltip(close_btn, tr("tip_close"))

        # Fullscreen
        self._tb_make_btn(
            bar, self.ICON_FULLSCREEN, self._toggle_fullscreen,
            is_emoji=True, tooltip=tr("tip_fullscreen")
        ).pack(side="right", padx=2)

    # ── Toolbar tool methods ──────────────────────────

    def _toggle_draw_tool(self, tool):
        """Toggle drawing tool - set active, update icons."""
        if self._active_tool == tool:
            self._active_tool = "select"
            self.set_tool("select")
        else:
            self._active_tool = tool
            self.set_tool(tool)
            if tool == "text":
                engine = self._engine
                if engine and hasattr(engine, 'auto_place_text'):
                    engine.auto_place_text()
        self._tb_update_tool_icons()
        self._update_status()

    def _tb_activate_eraser(self):
        self._active_tool = "eraser"
        self.set_tool("eraser")
        self._tb_update_tool_icons()
        self._update_status()

    def _tb_update_tool_icons(self):
        """Highlight active tool button with accent color."""
        active = self._active_tool
        for tool, btn in self._tb_draw_btns.items():
            if tool == active:
                btn.configure(bg=self.TB_BG_ACTIVE)
                # Update hover to keep active bg
                btn.bind("<Enter>", lambda e, b=btn: b.configure(bg=self.TB_BG_ACTIVE))
                btn.bind("<Leave>", lambda e, b=btn: b.configure(bg=self.TB_BG_ACTIVE))
                if tool == "pen":
                    btn.configure(text=self.ICON_MOUSE)
            else:
                btn.configure(bg=self.TB_BG)
                # Restore normal hover
                btn.bind("<Enter>", lambda e, b=btn: b.configure(bg=self.TB_BG_HOVER))
                btn.bind("<Leave>", lambda e, b=btn: b.configure(bg=self.TB_BG))
                if tool == "pen":
                    btn.configure(text=self.ICON_PEN)

    def _tb_set_color(self, color):
        """Set pen color and highlight active swatch with accent ring."""
        self.set_color(color)
        # Reset previous
        if self._tb_active_color_btn:
            self._tb_active_color_btn.configure(
                highlightbackground="#555", highlightthickness=1)
        btn = self._tb_color_btns.get(color)
        if btn:
            btn.configure(highlightbackground=self.TB_ACCENT, highlightthickness=2)
            self._tb_active_color_btn = btn

    def _tb_on_font_change(self, font_name):
        """Handle font family change from dropdown."""
        if font_name.startswith("─"):
            return
        engine = self._engine
        if engine:
            if self._active_tool == "handwrite" and hasattr(engine, 'set_hw_font'):
                engine.set_hw_font(font_name, self._tb_fontsize_var.get())
            elif hasattr(engine, '_text_font'):
                engine._text_font = font_name
                if engine._text_active:
                    engine._update_text_display()

    def _tb_on_thickness_change(self, val):
        """Route pen thickness change."""
        v = int(val)
        self._tb_pen_val.configure(text=str(v))
        self.set_width(v)

    def _tb_on_font_size_change(self, val):
        """Route font size change."""
        v = int(val)
        self._tb_font_val.configure(text=str(v))
        engine = self._engine
        if engine:
            if self._active_tool == "handwrite" and hasattr(engine, 'set_hw_font'):
                font = getattr(engine, '_hw_font', "Segoe UI")
                engine.set_hw_font(font, v)
            elif self._active_tool == "text":
                if hasattr(self, 'set_text_font_size'):
                    self.set_text_font_size(v)
                elif engine:
                    engine._text_font_size = v
                    if engine._text_active:
                        engine._update_text_display()

    def _on_toolbar_retract(self):
        """Hide toolbar (user wants more canvas space)."""
        if self._toolbar_frame:
            self._toolbar_frame.pack_forget()

    def _show_toolbar(self):
        """Re-show toolbar if hidden."""
        if self._toolbar_frame and not self._toolbar_frame.winfo_ismapped():
            self._toolbar_frame.pack(fill="x", side="bottom")

    # ── PenOverlay-Compatible API (used by PenToolbar) ──

    @property
    def _engine(self):
        """Active page's DrawingEngine - used by PenToolbar."""
        if self._pages:
            return self._pages[self._active_page_idx].engine
        return None

    def set_tool(self, tool: str):
        # Deselect when switching away from select
        if self._active_tool == "select" and tool != "select":
            if self._selection_mgr:
                self._selection_mgr.deselect_all()
        self._active_tool = tool
        if tool != "select":
            for page in self._pages:
                page.engine.set_tool(tool)
        # Update cursor
        pen_cursor = _get_pen_cursor()
        cursors = {"pen": pen_cursor, "highlighter": pen_cursor,
                   "eraser": "circle", "text": "xterm", "pan": "fleur",
                   "select": "arrow", "handwrite": pen_cursor}
        cursor = cursors.get(tool, pen_cursor)
        try:
            self._canvas.configure(cursor=cursor)
        except tk.TclError:
            self._canvas.configure(cursor="pencil")
        self._update_status()

    def set_color(self, color: str):
        for page in self._pages:
            page.engine.set_color(color)

    def set_width(self, width: int):
        for page in self._pages:
            page.engine.set_width(width)

    def set_font(self, font_family: str):
        for page in self._pages:
            page.engine.set_font(font_family)

    def set_hw_font(self, font_family, font_size=None):
        for page in self._pages:
            page.engine.set_hw_font(font_family, font_size)

    def set_text_font_size(self, size: int):
        for page in self._pages:
            page.engine._text_font_size = size
            if page.engine._text_active:
                page.engine._update_text_display()

    def set_highlighter_color(self, color: str):
        for page in self._pages:
            page.engine.set_highlighter_color(color)

    def undo(self):
        if self._pages:
            self._pages[self._active_page_idx].engine.undo()

    def redo(self):
        if self._pages:
            self._pages[self._active_page_idx].engine.redo()

    def clear_all(self):
        if self._pages:
            self._pages[self._active_page_idx].engine.clear_all()

    def auto_place_text(self):
        if self._pages:
            self._pages[self._active_page_idx].engine.auto_place_text()
            self.focus_force()

    def set_click_through(self, enabled: bool):
        """No-op - editor is always in draw mode."""
        pass

    @property
    def is_click_through(self):
        return False

    def set_zoom(self, level: float):
        """Apply zoom level (1.0 = 100%)."""
        if not self._pages:
            return
        old = self._zoom_level
        if abs(level - old) < 0.001:
            return
        factor = level / old
        self._apply_zoom(factor)
        self._zoom_level = level
        self._update_status()

    def _apply_zoom(self, factor: float, cx: float = None, cy: float = None):
        """Scale all canvas items by factor, centered on (cx,cy)."""
        if cx is None:
            cx = self._canvas.canvasx(self._canvas.winfo_width() / 2)
        if cy is None:
            cy = self._canvas.canvasy(self._canvas.winfo_height() / 2)
        self._canvas.scale("all", cx, cy, factor, factor)
        # Scroll region from actual item bounds (allows scroll in all directions)
        bbox = self._canvas.bbox("all")
        if bbox:
            pad_x = max(self._canvas.winfo_width(), 200)
            pad_y = max(self._canvas.winfo_height(), 200)
            self._canvas.configure(scrollregion=(
                bbox[0] - pad_x, bbox[1] - pad_y,
                bbox[2] + pad_x, bbox[3] + pad_y))
        # Scale text font sizes to match zoom
        z = self._zoom_level * factor
        for page in self._pages:
            page.engine.set_display_scale(z)

    def close(self):
        """Called by PenToolbar close button - auto-save and hide editor."""
        self._on_close_window()

    # ── Menu ──────────────────────────────────────────

    def _build_menu(self):
        self._menubar = tk.Menu(self, bg="#1E1E28", fg="#AAA",
                                activebackground="#3A3A50",
                                activeforeground="#FFF")
        file_menu = tk.Menu(self._menubar, tearoff=0, bg="#1E1E28", fg="#AAA",
                            activebackground="#3A3A50", activeforeground="#FFF")
        file_menu.add_command(label=tr("menu_new"), command=self._new_file_dialog,
                              accelerator="Ctrl+N")
        file_menu.add_command(label=tr("menu_open"), command=self._open_file,
                              accelerator="Ctrl+O")
        file_menu.add_command(label=tr("menu_import"), command=self._import_file)
        file_menu.add_separator()
        file_menu.add_command(label=tr("menu_save"), command=self._save,
                              accelerator="Ctrl+S")
        file_menu.add_command(label=tr("menu_save_as"), command=self._save_as)
        file_menu.add_separator()

        export_menu = tk.Menu(file_menu, tearoff=0, bg="#1E1E28", fg="#AAA",
                              activebackground="#3A3A50", activeforeground="#FFF")
        export_menu.add_command(label="PDF", command=lambda: self._export("pdf"))
        export_menu.add_command(label="PNG", command=lambda: self._export("png"))
        export_menu.add_command(label="JPG", command=lambda: self._export("jpg"))
        file_menu.add_cascade(label=tr("menu_export") + " ▸", menu=export_menu)

        file_menu.add_separator()
        file_menu.add_command(label=tr("menu_show_toolbar"), command=self._on_toolbar_retract,
                              accelerator="Ctrl+T")
        file_menu.add_separator()
        file_menu.add_command(label=tr("menu_close"), command=self._on_close_window)

        self._menubar.add_cascade(label=tr("menu_file"), menu=file_menu)

        # ── Page menu ──
        page_menu = tk.Menu(self._menubar, tearoff=0, bg="#1E1E28", fg="#AAA",
                            activebackground="#3A3A50", activeforeground="#FFF")
        page_menu.add_command(label=tr("menu_add_page"), command=self._add_page_dialog)
        page_menu.add_command(label=tr("menu_delete_page"),
                              command=self._delete_current_page)
        page_menu.add_separator()
        page_menu.add_command(label=tr("menu_fit"),
                              command=self._zoom_to_fit)
        self._menubar.add_cascade(label=tr("menu_page"), menu=page_menu)

        self.config(menu=self._menubar)

        self.bind("<Control-n>", lambda e: self._new_file_dialog())
        self.bind("<Control-o>", lambda e: self._open_file())
        self.bind("<Control-s>", lambda e: self._save())
        self.bind("<Control-t>", lambda e: self._on_toolbar_retract())

    # ── Canvas Area ───────────────────────────────────

    def _build_canvas_area(self):
        self._canvas_frame = tk.Frame(self, bg=BG_COLOR)
        self._canvas_frame.pack(fill="both", expand=True)

        self._canvas = tk.Canvas(
            self._canvas_frame, bg=BG_COLOR, highlightthickness=0,
            cursor="pencil"
        )
        self._v_scroll = tk.Scrollbar(self._canvas_frame, orient="vertical",
                                       command=self._canvas.yview)
        self._h_scroll = tk.Scrollbar(self._canvas_frame, orient="horizontal",
                                       command=self._canvas.xview)
        self._canvas.configure(yscrollcommand=self._v_scroll.set,
                               xscrollcommand=self._h_scroll.set)

        self._canvas.grid(row=0, column=0, sticky="nsew")
        self._v_scroll.grid(row=0, column=1, sticky="ns")
        self._h_scroll.grid(row=1, column=0, sticky="ew")
        self._canvas_frame.grid_rowconfigure(0, weight=1)
        self._canvas_frame.grid_columnconfigure(0, weight=1)

        self._canvas.bind("<ButtonPress-1>", self._on_canvas_click)
        self._canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self._canvas.bind("<Key>", self._on_key)
        self._canvas.bind("<Control-z>", lambda e: self.undo())
        self._canvas.bind("<Control-y>", lambda e: self.redo())
        self._canvas.bind("<MouseWheel>", self._on_mousewheel)
        self._canvas.bind("<ButtonPress-3>", self._on_canvas_right_click)

    def _build_status_bar(self):
        self._status = tk.Frame(self, bg="#1E1E28", height=24)
        self._status.pack(fill="x", side="bottom")
        self._status_label = tk.Label(
            self._status, text="",
            bg="#1E1E28", fg="#666", font=("Segoe UI", 8)
        )
        self._status_label.pack(side="left", padx=8)

    def _update_status(self):
        tool_keys = {"pen": "tool_pen", "highlighter": "tool_highlighter",
                     "eraser": "tool_eraser", "text": "tool_text", "pan": "tool_pan",
                     "select": "tool_select", "handwrite": "tool_handwrite"}
        t = tr(tool_keys.get(self._active_tool, "tool_pen")) if self._active_tool in tool_keys else self._active_tool
        n = len(self._pages)
        p = self._active_page_idx + 1 if self._pages else 0
        z = int(self._zoom_level * 100)
        self._status_label.configure(text=tr("status_format", p=p, n=n, t=t, z=z))

    # ── Page Management ───────────────────────────────

    def _add_page(self, width: int, height: int,
                  bg_image: Optional[Image.Image] = None,
                  insert_at: Optional[int] = None,
                  batch: bool = False):
        if insert_at is not None:
            idx = insert_at
        else:
            idx = len(self._pages)

        page = EditorPage(self._canvas, self, width, height, 0, bg_image)
        self._pages.insert(idx, page)
        self._active_page_idx = idx
        if not batch:
            self._relayout_pages()
            self._update_status()

    def _relayout_pages(self):
        for bid in self._plus_buttons:
            self._canvas.delete(bid)
        self._plus_buttons.clear()
        for lid in self._page_number_labels:
            self._canvas.delete(lid)
        self._page_number_labels.clear()

        max_w = max((p.width for p in self._pages), default=0)
        # Use viewport width for centering if larger than max page width
        vw = max(self._canvas.winfo_width(), max_w)
        center_x = vw // 2

        y = GAP
        for i, page in enumerate(self._pages):
            page.y_offset = y
            x_off = center_x - page.width // 2
            # Shadow
            if page._shadow_id:
                self._canvas.coords(page._shadow_id,
                                    x_off + 4, y + 4,
                                    x_off + page.width + 4, y + page.height + 4)
            self._canvas.coords(page._rect_id,
                                x_off, y, x_off + page.width, y + page.height)
            if page._bg_canvas_id:
                self._canvas.coords(page._bg_canvas_id, x_off, y)

            y += page.height + GAP

            plus_y = y - GAP // 2
            bid = self._canvas.create_text(
                center_x, plus_y, text="＋", fill="#555",
                font=("Segoe UI", 16, "bold"), tags="plus_btn"
            )
            self._plus_buttons.append(bid)
            # Page number label
            num_id = self._canvas.create_text(
                center_x, plus_y + 20, text=f"── {i + 1} ──",
                fill="#555", font=("Segoe UI", 9), tags="page_label"
            )
            self._page_number_labels.append(num_id)
            self._canvas.tag_bind(bid, "<ButtonPress-1>",
                                  lambda e, idx=i: self._on_plus_click(idx + 1))

        content_w = max(vw, max_w)
        sr = (0, 0, content_w, y + GAP)
        self._base_scrollregion = sr
        self._canvas.configure(scrollregion=sr)
        self._canvas.tag_lower("page_bg")

    def _on_plus_click(self, insert_idx):
        if self._fullscreen:
            return
        if self._pages:
            ref = self._pages[min(insert_idx - 1, len(self._pages) - 1)]
            w, h = ref.width, ref.height
        else:
            w, h = 1920, 1080
        self._add_page(w, h, insert_at=insert_idx)

    def _add_page_dialog(self):
        """Add a new page after current page using same size."""
        idx = self._active_page_idx + 1 if self._pages else 0
        self._on_plus_click(idx)

    def _delete_current_page(self):
        """Delete the currently active page."""
        if not self._pages:
            return
        if len(self._pages) == 1:
            messagebox.showinfo(tr("dlg_delete_title"), tr("dlg_delete_last_page"),
                                parent=self)
            return
        idx = self._active_page_idx
        page = self._pages[idx]
        confirm = messagebox.askyesno(
            tr("dlg_delete_page_title"),
            tr("dlg_delete_page_q", n=idx + 1),
            parent=self
        )
        if not confirm:
            return
        # Remove canvas items
        page.cleanup()
        self._pages.pop(idx)
        # Adjust active page index
        if self._active_page_idx >= len(self._pages):
            self._active_page_idx = len(self._pages) - 1
        # Re-layout and reset zoom
        self._zoom_level = 1.0
        self._relayout_pages()
        self._sync_zoom_slider()
        self._update_status()

    def _get_page_at(self, canvas_y: float) -> Optional[int]:
        """Find page at canvas Y - uses actual canvas coords (works after zoom).
        Falls back to nearest page so pen tool never silently drops clicks."""
        if not self._pages:
            return None
        best_idx = 0
        best_dist = float("inf")
        for i, page in enumerate(self._pages):
            coords = self._canvas.coords(page._rect_id)
            if len(coords) < 4:
                continue
            if coords[1] <= canvas_y <= coords[3]:
                return i  # exact hit
            # Track nearest page
            dist = min(abs(canvas_y - coords[1]), abs(canvas_y - coords[3]))
            if dist < best_dist:
                best_dist = dist
                best_idx = i
        return best_idx

    def _update_scroll(self):
        if not self._pages:
            return
        bbox = self._canvas.bbox("all")
        if bbox:
            pad_x = max(self._canvas.winfo_width(), 200)
            pad_y = max(self._canvas.winfo_height(), 200)
            self._canvas.configure(scrollregion=(
                bbox[0] - pad_x, bbox[1] - pad_y,
                bbox[2] + pad_x, bbox[3] + pad_y))
        else:
            last = self._pages[-1]
            total_h = last.y_offset + last.height + GAP * 2
            max_w = max(p.width for p in self._pages)
            self._canvas.configure(scrollregion=(0, 0, max_w, total_h))

    # ── Canvas Event Routing ──────────────────────────

    def _canvas_coords(self, event):
        cx = self._canvas.canvasx(event.x)
        cy = self._canvas.canvasy(event.y)
        return cx, cy

    def _on_canvas_click(self, event):
        self._canvas.focus_set()
        if not self._pages:
            return
        cx, cy = self._canvas_coords(event)
        if self._active_tool == "pan":
            self._canvas.scan_mark(event.x, event.y)
            return
        page_idx = self._get_page_at(cy)
        if page_idx is None:
            return
        self._active_page_idx = page_idx
        if self._active_tool == "select":
            strokes = self._pages[page_idx].engine.get_strokes()
            self._selection_mgr.on_mouse_down(cx, cy, strokes)
            return
        self._update_status()
        fake = type('Event', (), {'x': cx, 'y': cy})()
        self._pages[page_idx].engine.on_mouse_down(fake)

    def _on_canvas_drag(self, event):
        if not self._pages:
            return
        cx, cy = self._canvas_coords(event)
        if self._active_tool == "pan":
            self._canvas.scan_dragto(event.x, event.y, gain=1)
            # Sync scrollbar positions after pan drag
            self._v_scroll.set(*self._canvas.yview())
            self._h_scroll.set(*self._canvas.xview())
            return
        if self._active_tool == "select":
            self._selection_mgr.on_mouse_move(cx, cy)
            return
        fake = type('Event', (), {'x': cx, 'y': cy})()
        self._pages[self._active_page_idx].engine.on_mouse_move(fake)

    def _on_canvas_release(self, event):
        if not self._pages:
            return
        if self._active_tool == "pan":
            return
        cx, cy = self._canvas_coords(event)
        if self._active_tool == "select":
            strokes = self._pages[self._active_page_idx].engine.get_strokes()
            self._selection_mgr.on_mouse_up(cx, cy, strokes)
            return
        cx, cy = self._canvas_coords(event)
        fake = type('Event', (), {'x': cx, 'y': cy})()
        self._pages[self._active_page_idx].engine.on_mouse_up(fake)

    def _on_key(self, event):
        if not self._pages:
            return
        engine = self._pages[self._active_page_idx].engine
        engine.on_key(event)
        if engine._text_active:
            return "break"

    def _on_mousewheel(self, event):
        if self._active_tool == "pan":
            # Natural zoom centered on cursor
            factor = 1.08 if event.delta > 0 else (1 / 1.08)
            new_zoom = max(0.10, min(4.0, self._zoom_level * factor))
            if abs(new_zoom - self._zoom_level) < 0.001:
                return
            scale_factor = new_zoom / self._zoom_level
            cx = self._canvas.canvasx(event.x)
            cy = self._canvas.canvasy(event.y)
            self._apply_zoom(scale_factor, cx, cy)
            self._zoom_level = new_zoom
            # Sync toolbar slider
            self._sync_zoom_slider()
            self._update_status()
        else:
            self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_canvas_right_click(self, event):
        """Right-click context menu on canvas."""
        if not self._pages:
            return
        cx, cy = self._canvas_coords(event)
        page_idx = self._get_page_at(cy)
        menu = tk.Menu(self._canvas, tearoff=0, bg="#2A2A40", fg="#CCC",
                       activebackground="#4A4A6A", activeforeground="#FFF")
        menu.add_command(
            label=f"{tr('menu_delete_page')} ({(page_idx or 0) + 1})",
            command=lambda: self._delete_page(page_idx)
        )
        menu.add_command(label=tr("menu_add_page"), command=self._add_page_dialog)
        menu.add_separator()
        menu.add_command(label=tr("menu_fit"), command=self._zoom_to_fit)
        menu.tk_popup(event.x_root, event.y_root)

    def _delete_page(self, idx):
        """Delete a specific page by index."""
        if idx is None or not self._pages:
            return
        if len(self._pages) == 1:
            messagebox.showinfo(tr("dlg_delete_title"), tr("dlg_delete_last_page"),
                                parent=self)
            return
        page = self._pages[idx]
        page.cleanup()
        self._pages.pop(idx)
        if self._active_page_idx >= len(self._pages):
            self._active_page_idx = len(self._pages) - 1
        self._zoom_level = 1.0
        self._relayout_pages()
        self._sync_zoom_slider()
        self._update_status()

    def _sync_zoom_slider(self):
        """Keep toolbar zoom slider in sync with current zoom level."""
        if self._pen_toolbar and hasattr(self._pen_toolbar, '_zoom_var'):
            z = int(self._zoom_level * 100)
            self._pen_toolbar._zoom_var.set(z)
            self._pen_toolbar._zoom_label.configure(text=tr("dlg_zoom_label", z=z))

    def _on_escape(self, event):
        if self._fullscreen:
            self._toggle_fullscreen()
        elif self._pages:
            self._pages[self._active_page_idx].engine.on_escape()

    def _toggle_fullscreen(self):
        self._fullscreen = not self._fullscreen
        self.attributes('-fullscreen', self._fullscreen)
        if self._fullscreen:
            self._status.pack_forget()
            self.config(menu="")
            for bid in self._plus_buttons:
                self._canvas.itemconfigure(bid, state="hidden")
            for lid in self._page_number_labels:
                self._canvas.itemconfigure(lid, state="hidden")
            self._v_scroll.grid_remove()
            self._h_scroll.grid_remove()
            self._fit_page_to_screen()
        else:
            self.config(menu=self._menubar)
            self._status.pack(fill="x", side="bottom")
            for bid in self._plus_buttons:
                self._canvas.itemconfigure(bid, state="normal")
            for lid in self._page_number_labels:
                self._canvas.itemconfigure(lid, state="normal")
            self._v_scroll.grid()
            self._h_scroll.grid()
            self._relayout_pages()
            self._update_scroll()

    def _fit_page_to_screen(self):
        """Center and fit the active page to the screen in fullscreen."""
        if not self._pages:
            return
        page = self._pages[self._active_page_idx]
        self.update_idletasks()
        screen_w = self.winfo_width()
        screen_h = self.winfo_height()

        # Calculate visible region to center the page
        # We scroll so the page is centered in the viewport
        total_w = max(p.width for p in self._pages)
        last = self._pages[-1]
        total_h = last.y_offset + last.height + GAP * 2

        # Scroll to center the active page
        page_center_y = page.y_offset + page.height / 2
        frac_y = max(0, (page_center_y - screen_h / 2) / total_h)
        self._canvas.yview_moveto(frac_y)

        page_center_x = page.width / 2
        frac_x = max(0, (page_center_x - screen_w / 2) / total_w) if total_w > screen_w else 0
        self._canvas.xview_moveto(frac_x)

    # ── New File Dialog ────────────────────────────────

    BG_TYPES = [
        (tr("color_white"), "white", "#FFFFFF"),
        (tr("color_black"), "black", "#000000"),
        (tr("color_gray"), "gray", "#808080"),
        (tr("color_graph"), "graph", "#F8F8F8"),
    ]

    def _new_file_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title(tr("dlg_new_file_title"))
        dialog.geometry("320x480")
        dialog.configure(bg="#2A2A40")
        dialog.transient(self)
        dialog.grab_set()

        tk.Label(dialog, text=tr("dlg_lbl_background"),
                 bg="#2A2A40", fg="#CCC", font=("Segoe UI", 11, "bold")
                 ).pack(pady=(10, 5))

        bg_var = tk.StringVar(value="white")
        bg_frame = tk.Frame(dialog, bg="#2A2A40")
        bg_frame.pack(pady=5)
        for label, bg_type, preview_color in self.BG_TYPES:
            f = tk.Frame(bg_frame, bg="#2A2A40")
            f.pack(side="left", padx=4)
            swatch = tk.Canvas(f, width=36, height=36, highlightthickness=2,
                               highlightbackground="#555", bg=preview_color)
            swatch.pack()
            rb = tk.Radiobutton(f, text=label, variable=bg_var, value=bg_type,
                                bg="#2A2A40", fg="#CCC", selectcolor="#2A2A40",
                                activebackground="#2A2A40", activeforeground="#FFF",
                                font=("Segoe UI", 8))
            rb.pack()

        tk.Label(dialog, text=tr("dlg_lbl_page_size"),
                 bg="#2A2A40", fg="#CCC", font=("Segoe UI", 11, "bold")
                 ).pack(pady=(12, 5))

        for name, (w, h) in PAGE_PRESETS.items():
            tk.Button(
                dialog, text=f"{name}  ({w}×{h})",
                bg="#3A3A55", fg="#CCC", font=("Segoe UI", 10),
                relief="flat", bd=0, activebackground="#4A4A6A",
                width=28,
                command=lambda w=w, h=h, d=dialog: (
                    self._create_new_file(w, h, bg_var.get(), d)
                )
            ).pack(pady=2)

        tk.Button(
            dialog, text=tr("dlg_btn_custom_size"),
            bg="#3A3A55", fg="#CCC", font=("Segoe UI", 10),
            relief="flat", bd=0, activebackground="#4A4A6A", width=28,
            command=lambda: self._custom_size_dialog(dialog, bg_var.get())
        ).pack(pady=(8, 2))

    def _create_new_file(self, w, h, bg_type, dialog):
        dialog.destroy()
        self._clear_all_pages()
        self._save_path = None
        bg_image = self._make_bg_image(w, h, bg_type)
        self._add_page(w, h, bg_image=bg_image)
        self.title(tr("editor_title"))
        # Delete session file on New File
        try:
            if os.path.exists(SESSION_FILE):
                os.remove(SESSION_FILE)
        except Exception:
            pass
        self.after(100, self._zoom_to_fit)

    def _zoom_to_fit(self):
        """Auto-fit: zoom so the widest page fits in the viewport with margin."""
        if not self._pages:
            return
        max_w = max(p.width for p in self._pages)
        vw = self._canvas.winfo_width() - 40  # 20px margin each side
        if vw <= 0 or max_w <= 0:
            return
        target = vw / max_w
        target = max(0.25, min(4.0, target))
        if abs(target - self._zoom_level) < 0.01:
            return
        self.set_zoom(target)
        self._sync_zoom_slider()

    def _make_bg_image(self, w, h, bg_type):
        if bg_type == "white":
            return None  # default white rect
        elif bg_type == "black":
            return Image.new("RGBA", (w, h), (0, 0, 0, 255))
        elif bg_type == "gray":
            return Image.new("RGBA", (w, h), (128, 128, 128, 255))
        elif bg_type == "graph":
            return self._create_graph_paper(w, h)
        return None

    def _create_graph_paper(self, w, h):
        img = Image.new("RGBA", (w, h), (248, 248, 248, 255))
        d = ImageDraw.Draw(img)
        grid = 40
        # Minor grid
        for x in range(0, w, grid):
            d.line([(x, 0), (x, h)], fill=(200, 220, 240, 255), width=1)
        for y in range(0, h, grid):
            d.line([(0, y), (w, y)], fill=(200, 220, 240, 255), width=1)
        # Major grid every 5 cells
        for x in range(0, w, grid * 5):
            d.line([(x, 0), (x, h)], fill=(160, 190, 220, 255), width=1)
        for y in range(0, h, grid * 5):
            d.line([(0, y), (w, y)], fill=(160, 190, 220, 255), width=1)
        return img

    def _custom_size_dialog(self, parent_dialog, bg_type):
        w_str = simpledialog.askstring(tr("dlg_width_title"), tr("dlg_width_prompt"), parent=parent_dialog)
        if not w_str:
            return
        h_str = simpledialog.askstring(tr("dlg_height_title"), tr("dlg_height_prompt"), parent=parent_dialog)
        if not h_str:
            return
        try:
            w = int(float(w_str) * 96)
            h = int(float(h_str) * 96)
            if w > 0 and h > 0:
                self._create_new_file(w, h, bg_type, parent_dialog)
        except ValueError:
            messagebox.showerror(tr("dlg_error_title"), tr("dlg_invalid_number"), parent=parent_dialog)

    # ── Open File ─────────────────────────────────────

    def _open_file(self):
        ftypes = [(tr("ftype_all_supported"), "*.png *.jpg *.jpeg *.bmp *.gif *.pdf"),
                  (tr("ftype_image"), "*.png *.jpg *.jpeg *.bmp *.gif"),
                  ("PDF", "*.pdf"),
                  (tr("ftype_dvai"), "*.dvai")]
        path = filedialog.askopenfilename(filetypes=ftypes, parent=self)
        if not path:
            return

        ext = os.path.splitext(path)[1].lower()
        if ext == ".dvai":
            self._load_dvai(path)
        elif ext == ".pdf":
            self._open_pdf(path)
        elif ext in (".png", ".jpg", ".jpeg", ".bmp", ".gif"):
            self._open_image(path)

    def _open_image(self, path):
        try:
            img = Image.open(path).convert("RGBA")
        except Exception as e:
            messagebox.showerror(tr("dlg_error_title"), tr("err_image_open", e=e), parent=self)
            return
        self._clear_all_pages()
        self._add_page(img.width, img.height, bg_image=img)
        self.title(f"{tr('editor_title')} - {os.path.basename(path)}")

    def _open_pdf(self, path):
        if not HAS_PYMUPDF:
            messagebox.showerror(tr("dlg_error_title"), tr("err_pymupdf_missing"),
                                 parent=self)
            return
        try:
            doc = fitz.open(path)
        except Exception as e:
            messagebox.showerror(tr("dlg_error_title"), tr("err_pdf_open", e=e), parent=self)
            return
        total = len(doc)
        self._clear_all_pages()
        self.title(f"{tr('editor_title')} - {os.path.basename(path)} ({tr('loading')})")
        # Progress label on canvas
        self._pdf_progress = tk.Label(
            self._canvas, text=tr("msg_loading_n", i=0, n=total),
            bg=BG_COLOR, fg="#AAA", font=("Segoe UI", 14))
        self.update_idletasks()
        cx = max(self._canvas.winfo_width() // 2, 200)
        self._pdf_progress_win = self._canvas.create_window(
            cx, 100, window=self._pdf_progress)
        self._pdf_loading = True
        # Background thread
        threading.Thread(
            target=self._load_pdf_worker,
            args=(doc, path, total), daemon=True).start()

    def _load_pdf_worker(self, doc, path, total):
        """Background thread: rasterize PDF pages and post to main thread."""
        for i in range(total):
            try:
                page = doc[i]
                mat = fitz.Matrix(150 / 72, 150 / 72)
                pix = page.get_pixmap(matrix=mat)
                img = Image.frombytes("RGB", [pix.width, pix.height],
                                      pix.samples).convert("RGBA")
                self.after(0, self._add_pdf_page_batch, img, i, total)
            except Exception as e:
                print(f"[PDF] Page {i} error: {e}")
        doc.close()
        self.after(0, self._pdf_load_done, path)

    def _add_pdf_page_batch(self, img, idx, total):
        """Main thread: add one PDF page and update progress."""
        if not self._pdf_loading:
            return
        self._add_page(img.width, img.height, bg_image=img, batch=True)
        self._pdf_progress.configure(text=tr("msg_loading_n", i=idx + 1, n=total))
        # Relayout every 5 pages or on last page
        if (idx + 1) % 5 == 0 or idx == total - 1:
            self._relayout_pages()
            self._update_status()

    def _pdf_load_done(self, path):
        """Main thread: cleanup after PDF load complete."""
        self._pdf_loading = False
        try:
            self._canvas.delete(self._pdf_progress_win)
            self._pdf_progress.destroy()
        except Exception:
            pass
        self._relayout_pages()
        self._update_status()
        self.title(f"{tr('editor_title')} - {os.path.basename(path)}")
        self.after(100, self._zoom_to_fit)

    # ── Import ────────────────────────────────────────

    def _import_file(self):
        ftypes = [(tr("ftype_all_supported"), "*.png *.jpg *.jpeg *.bmp *.gif *.pdf"),
                  (tr("ftype_image"), "*.png *.jpg *.jpeg *.bmp *.gif"),
                  ("PDF", "*.pdf")]
        path = filedialog.askopenfilename(filetypes=ftypes, parent=self)
        if not path:
            return
        ext = os.path.splitext(path)[1].lower()
        insert_at = self._active_page_idx + 1
        if ext == ".pdf":
            self._import_pdf(path, insert_at)
        elif ext in (".png", ".jpg", ".jpeg", ".bmp", ".gif"):
            self._import_image(path, insert_at)

    def _import_image(self, path, insert_at):
        try:
            img = Image.open(path).convert("RGBA")
            self._place_image_on_page(img)
        except Exception as e:
            messagebox.showerror(tr("dlg_error_title"), tr("err_image_import", e=e),
                                 parent=self)

    def _place_image_on_page(self, img: Image.Image):
        """Place an image at the center of the current page as a stroke."""
        if not self._pages:
            self._add_page(1920, 1080)
        page = self._pages[self._active_page_idx]

        # Scale to fit page if larger
        scale = min(page.width / img.width, page.height / img.height, 1.0)
        if scale < 1.0:
            new_w = int(img.width * scale)
            new_h = int(img.height * scale)
            img = img.resize((new_w, new_h), Image.LANCZOS)

        # Center on page
        cx = page.width // 2 - img.width // 2
        cy = page.y_offset + page.height // 2 - img.height // 2

        # Create canvas image
        tk_img = ImageTk.PhotoImage(img)
        cid = self._canvas.create_image(cx, cy, anchor="nw", image=tk_img, tags="stroke")

        # Store reference to prevent GC
        if not hasattr(page, '_image_refs'):
            page._image_refs = []
        page._image_refs.append(tk_img)

        # Create a stroke record for undo/redo and export
        stroke = Stroke(
            points=[(cx, cy)], color="#000000", width=0,
            is_text=False, is_highlighter=False,
        )
        stroke.canvas_ids = [cid]
        stroke._is_image = True
        stroke._pil_image = img
        page.engine._strokes.append(stroke)

    def _import_pdf(self, path, insert_at):
        if not HAS_PYMUPDF:
            messagebox.showerror(tr("dlg_error_title"), tr("err_pymupdf_short"), parent=self)
            return
        try:
            doc = fitz.open(path)
            for i in range(len(doc)):
                page = doc[i]
                mat = fitz.Matrix(150/72, 150/72)
                pix = page.get_pixmap(matrix=mat)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                self._add_page(img.width, img.height,
                               bg_image=img.convert("RGBA"),
                               insert_at=insert_at + i)
            doc.close()
        except Exception as e:
            messagebox.showerror(tr("dlg_error_title"), tr("err_pdf_import", e=e),
                                 parent=self)

    # ── Clipboard Paste ────────────────────────────────

    def _paste_from_clipboard(self):
        try:
            from PIL import ImageGrab
            img = ImageGrab.grabclipboard()
            if isinstance(img, Image.Image):
                self._place_image_on_page(img.convert("RGBA"))
            elif isinstance(img, list):
                # File list from clipboard
                for path in img:
                    ext = os.path.splitext(path)[1].lower()
                    if ext in (".png", ".jpg", ".jpeg", ".bmp", ".gif"):
                        try:
                            pasted = Image.open(path).convert("RGBA")
                            self._place_image_on_page(pasted)
                        except (OSError, Exception):
                            pass
                        break
        except Exception:
            pass

    # ── Save / Save As (.dvai) ────────────────────────

    def _save(self):
        if self._save_path:
            self._save_dvai(self._save_path)
        else:
            self._save_as()

    def _save_as(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".dvai",
            filetypes=[(tr("ftype_dvai"), "*.dvai")],
            parent=self
        )
        if path:
            self._save_path = path
            self._save_dvai(path)

    def _save_dvai(self, path):
        data = {"version": 1, "pages": []}
        for page in self._pages:
            page_data = {
                "width": page.width, "height": page.height,
                "strokes": [], "bg_image": None,
            }
            if page.bg_image:
                buf = io.BytesIO()
                page.bg_image.save(buf, format="PNG")
                page_data["bg_image"] = base64.b64encode(buf.getvalue()).decode()

            for stroke in page.engine.get_strokes():
                s = {
                    "points": stroke.points, "color": stroke.color,
                    "width": stroke.width,
                    "is_highlighter": stroke.is_highlighter,
                    "is_text": stroke.is_text, "text": stroke.text,
                    "font_family": stroke.font_family,
                    "font_size": stroke.font_size,
                    "wrap_width": getattr(stroke, "wrap_width", 0) or 0,
                    "anchor": getattr(stroke, "anchor", "nw"),
                }
                if stroke.smoothed_points:
                    s["smoothed_points"] = stroke.smoothed_points
                page_data["strokes"].append(s)
            data["pages"].append(page_data)

        # Safe write: temp file + rename (atomic)
        tmp = path + ".tmp"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, path)
        if path != SESSION_FILE:
            self.title(f"{tr('editor_title')} - {os.path.basename(path)}")

    def _load_dvai(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            messagebox.showerror(tr("dlg_error_title"), tr("err_file_load", e=e),
                                 parent=self)
            return

        self._clear_all_pages()
        self._save_path = path

        for page_data in data.get("pages", []):
            w = page_data["width"]
            h = page_data["height"]
            bg_image = None
            if page_data.get("bg_image"):
                img_bytes = base64.b64decode(page_data["bg_image"])
                bg_image = Image.open(io.BytesIO(img_bytes)).convert("RGBA")

            self._add_page(w, h, bg_image=bg_image)
            page = self._pages[-1]

            for s in page_data.get("strokes", []):
                pts = [tuple(p) for p in s["points"]]
                stroke = Stroke(
                    points=pts, color=s["color"], width=s["width"],
                    is_highlighter=s.get("is_highlighter", False),
                    is_text=s.get("is_text", False),
                    text=s.get("text", ""),
                    font_family=s.get("font_family", "Segoe UI"),
                    font_size=s.get("font_size", 16),
                    anchor=s.get("anchor", "nw"),
                    wrap_width=int(s.get("wrap_width", 0) or 0),
                )
                if s.get("smoothed_points"):
                    stroke.smoothed_points = [tuple(p) for p in s["smoothed_points"]]

                if stroke.is_text:
                    font = (stroke.font_family, stroke.font_size)
                    text_kwargs = dict(
                        text=stroke.text, anchor=stroke.anchor,
                        fill=stroke.color, font=font, tags="stroke",
                        justify="left",
                    )
                    if stroke.wrap_width > 0:
                        text_kwargs["width"] = stroke.wrap_width
                    tid = self._canvas.create_text(
                        pts[0][0], pts[0][1], **text_kwargs
                    )
                    stroke.canvas_ids = [tid]
                else:
                    draw_pts = stroke.smoothed_points or stroke.points
                    stipple = "gray50" if stroke.is_highlighter else ""
                    if len(draw_pts) >= 2:
                        flat = []
                        for p in draw_pts:
                            flat.extend(p)
                        lid = self._canvas.create_line(
                            *flat, fill=stroke.color, width=stroke.width,
                            smooth=True, splinesteps=32,
                            capstyle=tk.ROUND, joinstyle=tk.ROUND,
                            stipple=stipple, tags="stroke"
                        )
                        stroke.canvas_ids = [lid]
                    elif len(draw_pts) == 1:
                        r = max(1, stroke.width // 2)
                        x, y = draw_pts[0]
                        did = self._canvas.create_oval(
                            x-r, y-r, x+r, y+r,
                            fill=stroke.color, outline="",
                            stipple=stipple, tags="stroke"
                        )
                        stroke.canvas_ids = [did]
                page.engine._strokes.append(stroke)

        self.title(f"{tr('editor_title')} - {os.path.basename(path)}")

    # ── Export ────────────────────────────────────────

    def _export(self, fmt):
        if not self._pages:
            messagebox.showinfo(tr("dlg_info_title"), tr("msg_no_pages_export"), parent=self)
            return
        if fmt == "pdf":
            self._export_pdf()
        else:
            self._export_images(fmt)

    def _export_pdf(self):
        if not HAS_PYMUPDF:
            messagebox.showerror(tr("dlg_error_title"), tr("err_pymupdf_short"), parent=self)
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf", filetypes=[("PDF", "*.pdf")],
            title=tr("dlg_save_pdf_title"), parent=self
        )
        if not path:
            return
        total = len(self._pages)
        # Progress dialog
        prog_win = tk.Toplevel(self)
        prog_win.title(tr("dlg_pdf_export_title"))
        prog_win.geometry("300x80")
        prog_win.resizable(False, False)
        prog_win.transient(self)
        prog_label = tk.Label(prog_win, text=tr("msg_exporting_n", i=0, n=total),
                              font=("Segoe UI", 11))
        prog_label.pack(expand=True, padx=20, pady=20)
        prog_win.update()

        # Composite pages in background
        page_images = []
        def _worker():
            try:
                for i, page_obj in enumerate(self._pages):
                    img = page_obj.composite(skip_text=False).convert("RGB")
                    page_images.append((img, page_obj.width, page_obj.height))
                    self.after(0, lambda idx=i: prog_label.configure(
                        text=tr("msg_exporting_n", i=idx + 1, n=total)))
                self.after(0, _finish)
            except Exception as e:
                self.after(0, lambda: _error(e))

        def _finish():
            try:
                doc = fitz.open()
                for img, w, h in page_images:
                    img_bytes = io.BytesIO()
                    img.save(img_bytes, format="PNG", optimize=True)
                    img_bytes.seek(0)
                    pdf_page = doc.new_page(width=w, height=h)
                    rect = fitz.Rect(0, 0, w, h)
                    pdf_page.insert_image(rect, stream=img_bytes.getvalue())
                doc.save(path)
                doc.close()
                prog_win.destroy()
                messagebox.showinfo(tr("dlg_success_title"), tr("msg_pdf_exported", path=path),
                                    parent=self)
            except Exception as e:
                _error(e)

        def _error(e):
            try:
                prog_win.destroy()
            except Exception:
                pass
            messagebox.showerror(tr("dlg_error_title"), tr("err_pdf_export", e=e),
                                 parent=self)

        threading.Thread(target=_worker, daemon=True).start()

    def _export_images(self, fmt):
        ext = "png" if fmt == "png" else "jpg"
        pil_fmt = "PNG" if fmt == "png" else "JPEG"
        ft = [("PNG", "*.png")] if fmt == "png" else [("JPEG", "*.jpg *.jpeg")]

        if len(self._pages) == 1:
            # Single page: save as single file with filename
            path = filedialog.asksaveasfilename(
                defaultextension=f".{ext}",
                filetypes=ft,
                title=tr("dlg_save_image_title"),
                parent=self
            )
            if not path:
                return
            try:
                img = self._pages[0].composite()
                if pil_fmt == "JPEG":
                    img = img.convert("RGB")
                img.save(path, format=pil_fmt, quality=95)
                messagebox.showinfo(tr("dlg_success_title"), tr("msg_saved_to", path=path),
                                    parent=self)
            except Exception as e:
                messagebox.showerror(tr("dlg_error_title"), tr("err_save_failed", e=e), parent=self)
        else:
            # Multiple pages: ask for base filename, save as name_1, name_2...
            path = filedialog.asksaveasfilename(
                defaultextension=f".{ext}",
                filetypes=ft,
                title=tr("dlg_save_image_multi"),
                parent=self
            )
            if not path:
                return
            base, fext = os.path.splitext(path)
            try:
                for i, page_obj in enumerate(self._pages):
                    img = page_obj.composite()
                    if pil_fmt == "JPEG":
                        img = img.convert("RGB")
                    out_path = f"{base}_{i+1}{fext}"
                    img.save(out_path, format=pil_fmt, quality=95)
                messagebox.showinfo(tr("dlg_success_title"),
                                    tr("msg_saved_pages", n=len(self._pages), base=base, ext=ext),
                                    parent=self)
            except Exception as e:
                messagebox.showerror(tr("dlg_error_title"), tr("err_save_failed", e=e), parent=self)

    # ── Helpers ───────────────────────────────────────

    def _clear_all_pages(self):
        for page in self._pages:
            page.cleanup()
        self._pages.clear()
        self._canvas.delete("all")
        self._plus_buttons.clear()
        self._page_number_labels.clear()

    def _schedule_autosave(self):
        self._autosave_job = self.after(60000, self._do_autosave)

    def _do_autosave(self):
        try:
            self._save_session()
        except Exception:
            pass
        self._schedule_autosave()

    def _save_session(self):
        """Save current state to session file for persistence."""
        try:
            os.makedirs(os.path.dirname(SESSION_FILE), exist_ok=True)
            self._save_dvai(SESSION_FILE)
        except Exception as e:
            print(f"[EDITOR] Auto-save failed: {e}")

    def _on_close_window(self):
        """Auto-save and hide editor (don't destroy - preserve state).
        Restores main widget visibility."""
        # Cancel auto-save timer
        if self._autosave_job:
            self.after_cancel(self._autosave_job)
            self._autosave_job = None
        # Save session
        self._save_session()
        # Hide window (don't destroy)
        self.withdraw()
        # Restore main widget
        try:
            self._app.deiconify()
            self._app.attributes('-topmost', True)
            self._app.lift()
        except tk.TclError:
            pass
