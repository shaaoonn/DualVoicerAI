# ui/editor_window.py
"""EditorWindow — Built-in image/PDF editor with permanent annotations.

Multi-page editor using DrawingEngine. No built-in toolbar — uses
the same PenToolbar as the pen overlay, so tools aren't duplicated.
Supports opening images/PDFs, importing pages, exporting to PDF/PNG/JPG,
and saving in internal .dvai format."""

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import json
import base64
import os
import io
from typing import List, Optional

from PIL import Image, ImageTk, ImageDraw, ImageFont
from ui_components.drawing_engine import Stroke, DrawingEngine
from ui_components.pen_overlay import _get_pen_cursor
from ui_components.selection_manager import SelectionManager

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

GAP = 20          # pixels between pages
BG_COLOR = "#3A3A4A"
PAGE_OUTLINE = "#666"


class EditorPage:
    """One page in the editor — has its own DrawingEngine."""

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

        # Draw page rectangle
        self._rect_id = canvas.create_rectangle(
            0, y_offset, width, y_offset + height,
            fill="white", outline=PAGE_OUTLINE, width=1, tags="page_bg"
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

    def composite(self) -> Image.Image:
        """Render page to PIL Image (bg + strokes)."""
        result = Image.new("RGBA", (self.width, self.height), (255, 255, 255, 255))

        if self.bg_image:
            bg = self.bg_image.convert("RGBA")
            result.paste(bg, (0, 0))

        draw = ImageDraw.Draw(result)
        for stroke in self.engine.get_strokes():
            if getattr(stroke, '_is_image', False):
                pil_img = stroke._pil_image
                x, y = stroke.points[0]
                rel_y = int(y - self.y_offset)
                try:
                    result.paste(pil_img, (int(x), rel_y), pil_img)
                except:
                    result.paste(pil_img, (int(x), rel_y))
                draw = ImageDraw.Draw(result)
                continue
            if stroke.is_text:
                x, y = stroke.points[0]
                rel_y = y - self.y_offset
                try:
                    font = ImageFont.truetype(stroke.font_family + ".ttf",
                                              stroke.font_size)
                except:
                    try:
                        font = ImageFont.truetype("arial.ttf", stroke.font_size)
                    except:
                        font = ImageFont.load_default()
                draw.text((x, rel_y), stroke.text, fill=stroke.color, font=font,
                          anchor="lm")
            else:
                pts = stroke.smoothed_points or stroke.points
                adjusted = [(p[0], p[1] - self.y_offset) for p in pts]
                if len(adjusted) >= 2:
                    w = max(1, stroke.width)
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
                    r = max(1, stroke.width // 2)
                    x, y = adjusted[0]
                    draw.ellipse([x-r, y-r, x+r, y+r], fill=stroke.color)

        return result

    @staticmethod
    def _hex_to_rgb(hex_color):
        h = hex_color.lstrip("#")
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


class EditorWindow(tk.Toplevel):
    """Built-in multi-page editor.

    Uses the same PenToolbar as the pen overlay — implements the same
    API (set_tool, set_color, set_width, set_font, undo, redo, etc.)
    so PenToolbar can target this window without any changes.
    """

    _supports_view_mode = False  # PenToolbar checks this — no click-through toggle

    def __init__(self, parent, app_ref):
        super().__init__(parent)
        self._app = app_ref
        self._pages: List[EditorPage] = []
        self._active_page_idx = 0
        self._active_tool = "pen"
        self._save_path: Optional[str] = None
        self._fullscreen = False
        self._plus_buttons = []
        self._pen_toolbar = None
        self._pan_start_x = 0
        self._pan_start_y = 0

        self._zoom_level = 1.0
        self._selection_mgr = None

        self._setup_window()
        self._build_menu()
        self._build_canvas_area()
        self._build_status_bar()

        self._selection_mgr = SelectionManager(self._canvas)

        # Start with one blank HD page
        self._add_page(1920, 1080)
        self._update_scroll()

        # Open PenToolbar targeting this editor
        self._open_toolbar()

        self.bind("<F11>", lambda e: self._toggle_fullscreen())
        self.bind("<Escape>", self._on_escape)
        self.bind("<Control-v>", lambda e: self._paste_from_clipboard())
        self.protocol("WM_DELETE_WINDOW", self._on_close_window)

    def _setup_window(self):
        self.title("এডিটর — Dual Voicer AI")
        self.geometry("1200x800")
        self.configure(bg=BG_COLOR)
        self.minsize(600, 400)
        try:
            self.iconbitmap(os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                        "DualVoicerLogo.ico"))
        except:
            pass

    def _open_toolbar(self):
        """Open a PenToolbar targeting this editor window."""
        from ui_components.pen_toolbar import PenToolbar
        self._pen_toolbar = PenToolbar(self._app, self, self._app)
        # Start in draw mode
        self._pen_toolbar.sync_draw_mode()

    # ── PenOverlay-Compatible API (used by PenToolbar) ──

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
                   "select": "arrow"}
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
        """No-op — editor is always in draw mode."""
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
        self._zoom_level = level
        factor = level / old
        cx = self._canvas.canvasx(self._canvas.winfo_width() / 2)
        cy = self._canvas.canvasy(self._canvas.winfo_height() / 2)
        self._canvas.scale("all", cx, cy, factor, factor)
        # Update scroll region
        sr = self._canvas.cget("scrollregion")
        if sr:
            parts = sr.split()
            if len(parts) == 4:
                x1, y1, x2, y2 = [float(v) for v in parts]
                self._canvas.configure(scrollregion=(
                    x1 * factor, y1 * factor, x2 * factor, y2 * factor))
        self._update_status()

    def close(self):
        """Called by PenToolbar close button — hide toolbar only."""
        if self._pen_toolbar:
            try:
                self._pen_toolbar.destroy()
            except:
                pass
            self._pen_toolbar = None

    # ── Menu ──────────────────────────────────────────

    def _build_menu(self):
        self._menubar = tk.Menu(self, bg="#1A1A2A", fg="#CCC",
                                activebackground="#4A4A6A",
                                activeforeground="#FFF")
        file_menu = tk.Menu(self._menubar, tearoff=0, bg="#1A1A2A", fg="#CCC",
                            activebackground="#4A4A6A", activeforeground="#FFF")
        file_menu.add_command(label="নতুন", command=self._new_file_dialog,
                              accelerator="Ctrl+N")
        file_menu.add_command(label="খুলুন...", command=self._open_file,
                              accelerator="Ctrl+O")
        file_menu.add_command(label="ইম্পোর্ট...", command=self._import_file)
        file_menu.add_separator()
        file_menu.add_command(label="সেভ", command=self._save,
                              accelerator="Ctrl+S")
        file_menu.add_command(label="সেভ অ্যাজ...", command=self._save_as)
        file_menu.add_separator()

        export_menu = tk.Menu(file_menu, tearoff=0, bg="#1A1A2A", fg="#CCC",
                              activebackground="#4A4A6A", activeforeground="#FFF")
        export_menu.add_command(label="PDF", command=lambda: self._export("pdf"))
        export_menu.add_command(label="PNG", command=lambda: self._export("png"))
        export_menu.add_command(label="JPG", command=lambda: self._export("jpg"))
        file_menu.add_cascade(label="এক্সপোর্ট ▸", menu=export_menu)

        file_menu.add_separator()
        file_menu.add_command(label="টুলবার দেখান", command=self._open_toolbar,
                              accelerator="Ctrl+T")
        file_menu.add_separator()
        file_menu.add_command(label="বন্ধ", command=self._on_close_window)

        self._menubar.add_cascade(label="ফাইল", menu=file_menu)
        self.config(menu=self._menubar)

        self.bind("<Control-n>", lambda e: self._new_file_dialog())
        self.bind("<Control-o>", lambda e: self._open_file())
        self.bind("<Control-s>", lambda e: self._save())
        self.bind("<Control-t>", lambda e: self._open_toolbar())

    # ── Canvas Area ───────────────────────────────────

    def _build_canvas_area(self):
        self._canvas_frame = tk.Frame(self, bg=BG_COLOR)
        self._canvas_frame.pack(fill="both", expand=True)

        self._vscroll = tk.Scrollbar(self._canvas_frame, orient="vertical")
        self._vscroll.pack(side="right", fill="y")

        self._hscroll = tk.Scrollbar(self._canvas_frame, orient="horizontal")
        self._hscroll.pack(side="bottom", fill="x")

        self._canvas = tk.Canvas(
            self._canvas_frame, bg=BG_COLOR, highlightthickness=0,
            xscrollcommand=self._hscroll.set,
            yscrollcommand=self._vscroll.set,
            cursor="pencil"
        )
        self._canvas.pack(fill="both", expand=True)
        self._vscroll.config(command=self._canvas.yview)
        self._hscroll.config(command=self._canvas.xview)

        self._canvas.bind("<ButtonPress-1>", self._on_canvas_click)
        self._canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self.bind("<Key>", self._on_key)
        self.bind("<Control-z>", lambda e: self.undo())
        self.bind("<Control-y>", lambda e: self.redo())
        self._canvas.bind("<MouseWheel>", self._on_mousewheel)

    def _build_status_bar(self):
        self._status = tk.Frame(self, bg="#1A1A2A", height=22)
        self._status.pack(fill="x", side="bottom")
        self._status_label = tk.Label(
            self._status, text="পেজ: 0 | টুল: পেন",
            bg="#1A1A2A", fg="#888", font=("Segoe UI", 8)
        )
        self._status_label.pack(side="left", padx=6)

    def _update_status(self):
        tool_names = {"pen": "পেন", "highlighter": "হাইলাইটার",
                      "eraser": "ইরেজার", "text": "টেক্সট", "pan": "প্যান",
                      "select": "সিলেক্ট"}
        t = tool_names.get(self._active_tool, self._active_tool)
        n = len(self._pages)
        p = self._active_page_idx + 1 if self._pages else 0
        z = int(self._zoom_level * 100)
        self._status_label.configure(text=f"পেজ: {p}/{n} | টুল: {t} | {z}%")

    # ── Page Management ───────────────────────────────

    def _add_page(self, width: int, height: int,
                  bg_image: Optional[Image.Image] = None,
                  insert_at: Optional[int] = None):
        if insert_at is not None:
            idx = insert_at
        else:
            idx = len(self._pages)

        page = EditorPage(self._canvas, self, width, height, 0, bg_image)
        self._pages.insert(idx, page)
        self._active_page_idx = idx
        self._relayout_pages()
        self._update_status()

    def _relayout_pages(self):
        for bid in self._plus_buttons:
            self._canvas.delete(bid)
        self._plus_buttons.clear()

        y = GAP
        max_w = 0
        for i, page in enumerate(self._pages):
            page.y_offset = y
            self._canvas.coords(page._rect_id, 0, y, page.width, y + page.height)
            if page._bg_canvas_id:
                self._canvas.coords(page._bg_canvas_id, 0, y)

            max_w = max(max_w, page.width)
            y += page.height + GAP

            plus_y = y - GAP // 2
            bid = self._canvas.create_text(
                max_w // 2, plus_y, text="＋", fill="#666",
                font=("Segoe UI", 14, "bold"), tags="plus_btn"
            )
            self._plus_buttons.append(bid)
            self._canvas.tag_bind(bid, "<ButtonPress-1>",
                                  lambda e, idx=i: self._on_plus_click(idx + 1))

        self._canvas.configure(scrollregion=(0, 0, max_w, y + GAP))
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

    def _get_page_at(self, canvas_y: float) -> Optional[int]:
        for i, page in enumerate(self._pages):
            if page.y_offset <= canvas_y <= page.y_offset + page.height:
                return i
        return None

    def _update_scroll(self):
        if not self._pages:
            return
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
        cx, cy = self._canvas_coords(event)
        if self._active_tool == "pan":
            self._pan_start_x = event.x
            self._pan_start_y = event.y
            return
        if self._active_tool == "select":
            page_idx = self._get_page_at(cy)
            if page_idx is not None:
                self._active_page_idx = page_idx
            strokes = self._pages[self._active_page_idx].engine.get_strokes()
            self._selection_mgr.on_mouse_down(cx, cy, strokes)
            return
        page_idx = self._get_page_at(cy)
        if page_idx is None:
            return
        self._active_page_idx = page_idx
        self._update_status()
        fake = type('Event', (), {'x': cx, 'y': cy})()
        self._pages[page_idx].engine.on_mouse_down(fake)

    def _on_canvas_drag(self, event):
        if not self._pages:
            return
        cx, cy = self._canvas_coords(event)
        if self._active_tool == "pan":
            dx = event.x - self._pan_start_x
            dy = event.y - self._pan_start_y
            self._canvas.xview_scroll(int(-dx), "units")
            self._canvas.yview_scroll(int(-dy), "units")
            self._pan_start_x = event.x
            self._pan_start_y = event.y
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
        self._pages[self._active_page_idx].engine.on_key(event)

    def _on_mousewheel(self, event):
        if self._active_tool == "pan":
            # Zoom centered on cursor
            factor = 1.1 if event.delta > 0 else (1 / 1.1)
            new_zoom = max(0.25, min(4.0, self._zoom_level * factor))
            if abs(new_zoom - self._zoom_level) < 0.001:
                return
            scale_factor = new_zoom / self._zoom_level
            cx = self._canvas.canvasx(event.x)
            cy = self._canvas.canvasy(event.y)
            self._canvas.scale("all", cx, cy, scale_factor, scale_factor)
            self._zoom_level = new_zoom
            sr = self._canvas.cget("scrollregion")
            if sr:
                parts = sr.split()
                if len(parts) == 4:
                    x1, y1, x2, y2 = [float(v) for v in parts]
                    self._canvas.configure(scrollregion=(
                        x1 * scale_factor, y1 * scale_factor,
                        x2 * scale_factor, y2 * scale_factor))
            # Sync toolbar slider
            if self._pen_toolbar and hasattr(self._pen_toolbar, '_zoom_var'):
                self._pen_toolbar._zoom_var.set(int(new_zoom * 100))
                self._pen_toolbar._zoom_label.configure(
                    text=f"{int(new_zoom * 100)}%")
            self._update_status()
        else:
            self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_escape(self, event):
        if self._fullscreen:
            self._toggle_fullscreen()
        elif self._pages:
            self._pages[self._active_page_idx].engine.on_escape()

    def _toggle_fullscreen(self):
        self._fullscreen = not self._fullscreen
        self.attributes('-fullscreen', self._fullscreen)
        if self._fullscreen:
            # Hide chrome
            self._status.pack_forget()
            self.config(menu="")
            self._vscroll.pack_forget()
            self._hscroll.pack_forget()
            # Hide plus buttons
            for bid in self._plus_buttons:
                self._canvas.itemconfigure(bid, state="hidden")
            # Fit active page to screen
            self._fit_page_to_screen()
        else:
            # Restore chrome
            self.config(menu=self._menubar)
            self._canvas.pack_forget()
            self._vscroll.pack(side="right", fill="y")
            self._hscroll.pack(side="bottom", fill="x")
            self._canvas.pack(fill="both", expand=True)
            self._status.pack(fill="x", side="bottom")
            # Show plus buttons
            for bid in self._plus_buttons:
                self._canvas.itemconfigure(bid, state="normal")
            # Restore scroll region
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
        ("সাদা", "white", "#FFFFFF"),
        ("কালো", "black", "#000000"),
        ("ধূসর", "gray", "#808080"),
        ("গ্রাফ পেপার", "graph", "#F8F8F8"),
    ]

    def _new_file_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title("নতুন ফাইল")
        dialog.geometry("320x480")
        dialog.configure(bg="#2A2A40")
        dialog.transient(self)
        dialog.grab_set()

        tk.Label(dialog, text="ব্যাকগ্রাউন্ড",
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

        tk.Label(dialog, text="পেজ সাইজ",
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
            dialog, text="কাস্টম সাইজ (ইঞ্চি)...",
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
        self.title("এডিটর — Dual Voicer AI")

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
        w_str = simpledialog.askstring("প্রস্থ", "প্রস্থ (ইঞ্চি):", parent=parent_dialog)
        if not w_str:
            return
        h_str = simpledialog.askstring("উচ্চতা", "উচ্চতা (ইঞ্চি):", parent=parent_dialog)
        if not h_str:
            return
        try:
            w = int(float(w_str) * 96)
            h = int(float(h_str) * 96)
            if w > 0 and h > 0:
                self._create_new_file(w, h, bg_type, parent_dialog)
        except ValueError:
            messagebox.showerror("ত্রুটি", "সঠিক সংখ্যা দিন।", parent=parent_dialog)

    # ── Open File ─────────────────────────────────────

    def _open_file(self):
        ftypes = [("সকল সমর্থিত", "*.png *.jpg *.jpeg *.bmp *.gif *.pdf"),
                  ("ছবি", "*.png *.jpg *.jpeg *.bmp *.gif"),
                  ("PDF", "*.pdf"),
                  ("DVAI প্রজেক্ট", "*.dvai")]
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
            messagebox.showerror("ত্রুটি", f"ছবি খুলতে পারেনি:\n{e}", parent=self)
            return
        self._clear_all_pages()
        self._add_page(img.width, img.height, bg_image=img)
        self.title(f"এডিটর — {os.path.basename(path)}")

    def _open_pdf(self, path):
        if not HAS_PYMUPDF:
            messagebox.showerror("ত্রুটি", "PyMuPDF ইন্সটল নেই।\npip install PyMuPDF",
                                 parent=self)
            return
        try:
            doc = fitz.open(path)
        except Exception as e:
            messagebox.showerror("ত্রুটি", f"PDF খুলতে পারেনি:\n{e}", parent=self)
            return
        self._clear_all_pages()
        for page_num in range(len(doc)):
            page = doc[page_num]
            mat = fitz.Matrix(150/72, 150/72)
            pix = page.get_pixmap(matrix=mat)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            self._add_page(img.width, img.height, bg_image=img.convert("RGBA"))
        doc.close()
        self.title(f"এডিটর — {os.path.basename(path)}")

    # ── Import ────────────────────────────────────────

    def _import_file(self):
        ftypes = [("সকল সমর্থিত", "*.png *.jpg *.jpeg *.bmp *.gif *.pdf"),
                  ("ছবি", "*.png *.jpg *.jpeg *.bmp *.gif"),
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
            messagebox.showerror("ত্রুটি", f"ছবি ইম্পোর্ট করতে পারেনি:\n{e}",
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
            messagebox.showerror("ত্রুটি", "PyMuPDF ইন্সটল নেই।", parent=self)
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
            messagebox.showerror("ত্রুটি", f"PDF ইম্পোর্ট করতে পারেনি:\n{e}",
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
                        except:
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
            filetypes=[("DVAI প্রজেক্ট", "*.dvai")],
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
                }
                if stroke.smoothed_points:
                    s["smoothed_points"] = stroke.smoothed_points
                page_data["strokes"].append(s)
            data["pages"].append(page_data)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        self.title(f"এডিটর — {os.path.basename(path)}")

    def _load_dvai(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            messagebox.showerror("ত্রুটি", f"ফাইল লোড করতে পারেনি:\n{e}",
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
                )
                if s.get("smoothed_points"):
                    stroke.smoothed_points = [tuple(p) for p in s["smoothed_points"]]

                if stroke.is_text:
                    font = (stroke.font_family, stroke.font_size)
                    tid = self._canvas.create_text(
                        pts[0][0], pts[0][1], text=stroke.text,
                        anchor="w", fill=stroke.color, font=font, tags="stroke"
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

        self.title(f"এডিটর — {os.path.basename(path)}")

    # ── Export ────────────────────────────────────────

    def _export(self, fmt):
        if not self._pages:
            messagebox.showinfo("তথ্য", "এক্সপোর্ট করার মতো পেজ নেই।", parent=self)
            return
        if fmt == "pdf":
            self._export_pdf()
        else:
            self._export_images(fmt)

    def _export_pdf(self):
        if not HAS_PYMUPDF:
            messagebox.showerror("ত্রুটি", "PyMuPDF ইন্সটল নেই।", parent=self)
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf", filetypes=[("PDF", "*.pdf")], parent=self
        )
        if not path:
            return
        try:
            doc = fitz.open()
            for page_obj in self._pages:
                img = page_obj.composite().convert("RGB")
                img_bytes = io.BytesIO()
                img.save(img_bytes, format="PNG")
                img_bytes.seek(0)
                pdf_page = doc.new_page(width=page_obj.width, height=page_obj.height)
                rect = fitz.Rect(0, 0, page_obj.width, page_obj.height)
                pdf_page.insert_image(rect, stream=img_bytes.getvalue())
            doc.save(path)
            doc.close()
            messagebox.showinfo("সফল", f"PDF এক্সপোর্ট হয়েছে:\n{path}", parent=self)
        except Exception as e:
            messagebox.showerror("ত্রুটি", f"PDF এক্সপোর্ট ব্যর্থ:\n{e}", parent=self)

    def _export_images(self, fmt):
        folder = filedialog.askdirectory(title="এক্সপোর্ট ফোল্ডার নির্বাচন", parent=self)
        if not folder:
            return
        ext = "png" if fmt == "png" else "jpg"
        pil_fmt = "PNG" if fmt == "png" else "JPEG"
        try:
            for i, page_obj in enumerate(self._pages):
                img = page_obj.composite()
                if pil_fmt == "JPEG":
                    img = img.convert("RGB")
                out_path = os.path.join(folder, f"page_{i+1}.{ext}")
                img.save(out_path, format=pil_fmt, quality=95)
            messagebox.showinfo("সফল",
                                f"{len(self._pages)} পেজ এক্সপোর্ট হয়েছে:\n{folder}",
                                parent=self)
        except Exception as e:
            messagebox.showerror("ত্রুটি", f"এক্সপোর্ট ব্যর্থ:\n{e}", parent=self)

    # ── Helpers ───────────────────────────────────────

    def _clear_all_pages(self):
        for page in self._pages:
            page.cleanup()
        self._pages.clear()
        self._canvas.delete("all")
        self._plus_buttons.clear()

    def _on_close_window(self):
        """Close editor + its toolbar."""
        if self._pen_toolbar:
            try:
                self._pen_toolbar.destroy()
            except:
                pass
            self._pen_toolbar = None
        for page in self._pages:
            page.cleanup()
        self.destroy()
