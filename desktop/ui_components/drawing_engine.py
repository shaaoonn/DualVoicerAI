# ui_components/drawing_engine.py
"""DrawingEngine — Canvas-agnostic drawing engine.

Extracted from pen_overlay.py to be reused by both the transparent
screen overlay and the built-in editor. Operates on any tk.Canvas.

Features: freehand pen, highlighter, eraser, text tool, shape detection
(circle/rectangle/line), Catmull-Rom smoothing, undo/redo."""

import tkinter as tk
import time
import math
from dataclasses import dataclass, field
from typing import List, Tuple, Optional


@dataclass
class Stroke:
    """Single drawn stroke or text item."""
    points: List[Tuple[float, float]] = field(default_factory=list)
    color: str = "#FF0000"
    width: int = 4
    is_highlighter: bool = False
    canvas_ids: List[int] = field(default_factory=list)
    smoothed_points: List[Tuple[float, float]] = field(default_factory=list)
    # Text-specific fields
    is_text: bool = False
    text: str = ""
    font_family: str = "Segoe UI"
    font_size: int = 16
    anchor: str = "nw"  # canvas text anchor: "nw" for top-left growth
    wrap_width: int = 0  # 0 = auto-wrap to canvas edge; >0 = drag-defined box width


class DrawingEngine:
    """Canvas-agnostic drawing engine. Operates on any tk.Canvas.

    Usage:
        engine = DrawingEngine(canvas, parent_widget)
        canvas.bind("<ButtonPress-1>", engine.on_mouse_down)
        canvas.bind("<B1-Motion>", engine.on_mouse_move)
        canvas.bind("<ButtonRelease-1>", engine.on_mouse_up)
        parent.bind("<Key>", engine.on_key)
    """

    DEFAULT_COLOR = "#FF0000"
    DEFAULT_WIDTH = 4

    def __init__(self, canvas: tk.Canvas, parent_widget):
        self._canvas = canvas
        self._parent = parent_widget

        # Drawing state
        self._strokes: List[Stroke] = []
        self._undo_stack: List[Stroke] = []
        self._current_stroke: Optional[Stroke] = None

        # Pen settings
        self._pen_color = self.DEFAULT_COLOR
        self._pen_width = self.DEFAULT_WIDTH
        self._tool = "pen"
        self._highlighter_color = "#FFFF44"

        # Text tool state
        self._text_active = False
        self._text_buffer = ""
        self._text_pos = (0, 0)
        self._text_canvas_id = None
        self._text_cursor_id = None
        self._text_cursor_visible = True
        self._text_cursor_job = None
        self._text_cursor_idx = 0       # cursor position within text_buffer
        self._text_font_size = 0        # 0 = use _pen_width*4 fallback
        self._text_sel_start = -1       # selection start index (-1 = no selection)
        self._text_sel_end = -1         # selection end index
        self._text_sel_id = None        # legacy: first canvas rect of selection highlight
        self._text_sel_ids = []         # all canvas rects (one per visual line)
        self._text_dragging = False     # True during text drag-select
        self._font_family = "Segoe UI"
        self._dragging_stroke = None
        self._drag_offset = (0, 0)
        self._editing_stroke = None     # existing stroke being edited
        self._last_key_serial = -1      # dedup IME composition events
        self._ime_debounce_job = None   # after() job for IME dedup
        self._ime_pending_char = None   # pending char from IME
        self._overlay_mode = False      # True for pen overlay (transparent bg)
        self._tk_text_images = []       # keep PhotoImage refs alive (GC prevention)

        # Shape detection state
        self._shape_hold_job = None
        self._last_move_pos = (0, 0)

        # EMA smoothing state
        self._ema_x = 0.0
        self._ema_y = 0.0
        self._ema_alpha = 0.35

        # Display scale (zoom) — original font sizes are stored in Stroke,
        # canvas items use font_size * _display_scale
        self._display_scale = 1.0

        # Handwriting recognition — batch-based (one recognition per batch)
        self._hw_points = []            # current batch stroke points
        self._hw_batch_strokes = []     # current batch Stroke objects on canvas
        self._hw_inflight_strokes = []  # strokes sent for recognition (in-flight)
        self._hw_debounce_job = None    # recognition timer
        self._hw_font = "Li Alinur Nobin Unicode"  # Bengali default
        self._hw_font_size = 24
        self._hw_lang = "bn"
        self._hw_recognizer = None
        self._hw_active_text = None     # most recent recognized text Stroke (for appending)
        self._hw_pre_context = ""       # previously recognized text for API context
        self._hw_last_pen_width = 4     # pen thickness preserved from pen tool

        # Text drag-to-create-box (Photoshop-style)
        self._text_drag_start = None
        self._text_drag_rect_id = None
        self._text_wrap_w = 0  # last-used text wrap width (0 = auto)

    # ── Public API (called by toolbar) ────────────────

    def set_color(self, color: str):
        self._pen_color = color
        self._hw_active_text = None  # new sentence on color change

    def set_width(self, width: int):
        self._pen_width = width

    def set_tool(self, tool: str):
        if self._text_active and tool != "text":
            self._finalize_text()
        # Switching away from handwrite → reset state, restore pen width
        if self._tool == "handwrite" and tool != "handwrite":
            self._reset_hw()
            self._pen_width = self._hw_last_pen_width
        # Switching to handwrite → save current pen width
        if tool == "handwrite" and self._tool != "handwrite":
            self._hw_last_pen_width = self._pen_width
        self._tool = tool

    def set_font(self, font_family: str):
        self._font_family = font_family
        if self._text_active:
            self._update_text_display()
        # Also update handwrite font
        self._hw_font = font_family
        self._hw_active_text = None

    def set_highlighter_color(self, color: str):
        self._highlighter_color = color

    def set_hw_language(self, lang: str):
        """Set handwriting recognition language ('bn' or 'en')."""
        self._hw_lang = lang

    def set_hw_font(self, font_family: str, font_size: int = None):
        """Set font for handwriting recognition output."""
        self._hw_font = font_family
        if font_size is not None:
            self._hw_font_size = font_size
        self._hw_active_text = None  # new sentence on font/size change

    def set_display_scale(self, scale: float):
        """Set display zoom scale. Updates all text items' canvas font sizes."""
        self._display_scale = scale
        for stroke in self._strokes:
            if stroke.is_text:
                ds = max(12, int(stroke.font_size * scale))
                for cid in stroke.canvas_ids:
                    try:
                        self._canvas.itemconfigure(
                            cid, font=(stroke.font_family, ds))
                    except tk.TclError:
                        pass

    def _display_font(self, family, size):
        """Get display-scaled font tuple for canvas rendering.
        Min 12px so complex scripts (Bengali etc.) remain readable."""
        ds = max(12, int(size * self._display_scale))
        return (family, ds)

    def get_strokes(self) -> List[Stroke]:
        return self._strokes

    @property
    def tool(self):
        return self._tool

    # ── Event Handlers ────────────────────────────────

    def on_escape(self):
        """Escape: finalize text if active."""
        if self._text_active:
            self._finalize_text()

    def on_mouse_down(self, event):
        x, y = event.x, event.y

        if self._tool == "text":
            # If clicking on currently active text, start drag-select
            if self._text_active and self._text_canvas_id:
                bbox = self._canvas.bbox(self._text_canvas_id)
                if bbox and bbox[0] <= x <= bbox[2] and bbox[1] <= y <= bbox[3]:
                    idx = self._char_index_at(x, y)
                    self._text_cursor_idx = idx
                    self._text_sel_start = idx
                    self._text_sel_end = idx
                    self._text_dragging = True
                    self._clear_sel_rect()  # only remove old rect, keep indices
                    self._update_text_display()
                    return
            hit = self._find_text_at(x, y)
            if hit:
                self._edit_existing_text(hit, click_x=x)
                return
            # Empty space: start drag tracking (click vs drag decided on mouse up)
            if self._text_active:
                self._finalize_text()
            self._text_drag_start = (x, y)
            return

        if self._tool == "eraser":
            self._erase_at(x, y)
            return

        if self._text_active:
            self._finalize_text()

        # Cancel handwriting debounce — user is still drawing
        if self._tool == "handwrite" and self._hw_debounce_job:
            self._parent.after_cancel(self._hw_debounce_job)
            self._hw_debounce_job = None

        color = self._highlighter_color if self._tool == "highlighter" else self._pen_color
        width = self._pen_width * 3 if self._tool == "highlighter" else self._pen_width
        is_hl = (self._tool == "highlighter")

        self._current_stroke = Stroke(
            points=[(x, y)], color=color, width=width,
            is_highlighter=is_hl,
        )
        self._cancel_shape_hold()
        self._ema_x = float(x)
        self._ema_y = float(y)

        r = max(1, width // 2)
        stipple = "gray50" if is_hl else ""
        dot_id = self._canvas.create_oval(
            x - r, y - r, x + r, y + r,
            fill=color, outline="", stipple=stipple, tags="stroke"
        )
        self._current_stroke.canvas_ids.append(dot_id)

    def on_mouse_move(self, event):
        # Text drag-to-create-box preview (Photoshop style)
        if self._tool == "text" and self._text_drag_start is not None:
            sx, sy = self._text_drag_start
            if self._text_drag_rect_id:
                self._canvas.delete(self._text_drag_rect_id)
            self._text_drag_rect_id = self._canvas.create_rectangle(
                sx, sy, event.x, event.y,
                outline=self._pen_color, dash=(4, 3), width=1,
                tags="text_drag_preview")
            return

        # Text drag-select
        if self._text_dragging and self._text_active and self._text_canvas_id:
            idx = self._char_index_at(event.x, event.y)
            self._text_sel_end = idx
            self._text_cursor_idx = idx
            self._draw_text_selection()
            self._update_text_display()
            return

        if self._dragging_stroke:
            nx = event.x - self._drag_offset[0]
            ny = event.y - self._drag_offset[1]
            self._dragging_stroke.points[0] = (nx, ny)
            for cid in self._dragging_stroke.canvas_ids:
                self._canvas.coords(cid, nx, ny)
            return

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
            if dx * dx + dy * dy < 16:
                return

        pts.append((x, y))

        if len(pts) >= 2:
            stipple = "gray50" if self._current_stroke.is_highlighter else ""
            line_id = self._canvas.create_line(
                pts[-2][0], pts[-2][1], x, y,
                fill=self._current_stroke.color,
                width=self._current_stroke.width,
                capstyle=tk.ROUND, stipple=stipple, tags="stroke"
            )
            self._current_stroke.canvas_ids.append(line_id)

        # Shape hold detection — 3s timer resets on movement
        self._last_move_pos = (x, y)
        self._cancel_shape_hold()
        if len(pts) > 5:
            self._shape_hold_job = self._parent.after(3000, self._try_snap_shape)

    def on_mouse_up(self, event):
        self._cancel_shape_hold()

        # Text drag-to-create-box (Photoshop/OneNote style):
        #   click without drag → start text at click position (auto-wrap to canvas edge)
        #   drag a rectangle  → start text inside that rectangle, wrap to its width
        if self._tool == "text" and self._text_drag_start is not None:
            sx, sy = self._text_drag_start
            ex, ey = event.x, event.y
            # Clean up the dashed preview rectangle
            if self._text_drag_rect_id:
                try: self._canvas.delete(self._text_drag_rect_id)
                except Exception: pass
                self._text_drag_rect_id = None
            self._text_drag_start = None

            dx, dy = abs(ex - sx), abs(ey - sy)
            if dx < 5 and dy < 5:
                # Treat as a simple click → IME-style insertion point
                self._start_text_at(sx, sy)
            else:
                # User dragged a box → constrain text to that width, left-aligned wrap
                x1, y1 = min(sx, ex), min(sy, ey)
                wrap_w = max(50, abs(ex - sx))
                self._start_text_at(x1, y1, wrap_w=wrap_w)
            return

        if self._text_dragging:
            self._text_dragging = False
            return

        if self._dragging_stroke:
            self._dragging_stroke = None
            return

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

        # Handwriting recognition: accumulate strokes, recognize after pause
        if self._tool == "handwrite" and len(stroke.points) >= 2:
            self._hw_points.append(list(stroke.points))
            self._hw_batch_strokes.append(stroke)

            # Debounce: fires only after user truly stops drawing
            # (cancelled in on_mouse_down when new stroke starts)
            if self._hw_debounce_job:
                self._parent.after_cancel(self._hw_debounce_job)
            debounce_ms = 700 if self._hw_lang == "bn" else 500
            self._hw_debounce_job = self._parent.after(
                debounce_ms, self._recognize_handwriting
            )

    def inject_text(self, text: str):
        """Insert text at cursor (used by voice typing to bypass OS focus)."""
        if not self._text_active:
            return
        if self._has_text_selection():
            self._delete_text_selection()
        self._text_buffer = (self._text_buffer[:self._text_cursor_idx] +
                             text +
                             self._text_buffer[self._text_cursor_idx:])
        self._text_cursor_idx += len(text)
        self._update_text_display()

    def _commit_ime_char(self):
        """Insert debounced IME character (called after 40ms delay)."""
        self._ime_debounce_job = None
        ch = self._ime_pending_char
        if not ch or not self._text_active:
            return
        self._ime_pending_char = None
        if self._has_text_selection():
            self._delete_text_selection()
        self._text_buffer = (self._text_buffer[:self._text_cursor_idx] +
                             ch +
                             self._text_buffer[self._text_cursor_idx:])
        self._text_cursor_idx += 1
        self._update_text_display()

    def on_key(self, event):
        if not self._text_active:
            return

        # IME deduplication: skip duplicate events from IME composition
        serial = getattr(event, 'serial', 0)
        if serial and serial == self._last_key_serial:
            return
        self._last_key_serial = serial

        # Filter IME composition keysyms (Windows Bengali IME)
        if event.keysym in ('VoidSymbol', '??'):
            return

        if event.keysym == "Return":
            if self._has_text_selection():
                self._delete_text_selection()
            self._text_buffer = (self._text_buffer[:self._text_cursor_idx] +
                                 "\n" +
                                 self._text_buffer[self._text_cursor_idx:])
            self._text_cursor_idx += 1
            self._update_text_display()
            return
        if event.keysym == "BackSpace":
            if self._has_text_selection():
                self._delete_text_selection()
                self._update_text_display()
            elif self._text_cursor_idx > 0:
                self._text_buffer = (self._text_buffer[:self._text_cursor_idx - 1] +
                                     self._text_buffer[self._text_cursor_idx:])
                self._text_cursor_idx -= 1
                self._update_text_display()
            return
        if event.keysym == "Delete":
            if self._has_text_selection():
                self._delete_text_selection()
                self._update_text_display()
            elif self._text_cursor_idx < len(self._text_buffer):
                self._text_buffer = (self._text_buffer[:self._text_cursor_idx] +
                                     self._text_buffer[self._text_cursor_idx + 1:])
                self._update_text_display()
            return
        if event.keysym == "Left":
            self._clear_text_selection()
            if self._text_cursor_idx > 0:
                self._text_cursor_idx -= 1
                self._update_text_display()
            return
        if event.keysym == "Right":
            self._clear_text_selection()
            if self._text_cursor_idx < len(self._text_buffer):
                self._text_cursor_idx += 1
                self._update_text_display()
            return
        if event.keysym == "Home":
            self._text_cursor_idx = 0
            self._update_text_display()
            return
        if event.keysym == "End":
            self._text_cursor_idx = len(self._text_buffer)
            self._update_text_display()
            return
        if event.keysym == "Escape":
            if self._editing_stroke:
                # Cancel edit — restore original text
                dfont = self._display_font(self._editing_stroke.font_family,
                                           self._editing_stroke.font_size)
                try:
                    self._canvas.itemconfigure(
                        self._text_canvas_id, text=self._editing_stroke.text,
                        font=dfont)
                except tk.TclError:
                    pass
                self._editing_stroke = None
            elif self._text_canvas_id:
                self._canvas.delete(self._text_canvas_id)
            self._text_canvas_id = None
            self._cleanup_text_cursor()
            self._text_active = False
            return

        if event.char and event.char.isprintable():
            ch = event.char
            # IME dedup: non-ASCII chars (Bengali etc.) use debounce to absorb
            # duplicate events from Windows IME composition
            is_multibyte = ord(ch) > 127
            if is_multibyte:
                # Cancel pending insert and schedule new one (only last event wins)
                if self._ime_debounce_job:
                    self._parent.after_cancel(self._ime_debounce_job)
                self._ime_pending_char = ch
                self._ime_debounce_job = self._parent.after(
                    40, self._commit_ime_char)
                return

            if self._has_text_selection():
                self._delete_text_selection()
            self._text_buffer = (self._text_buffer[:self._text_cursor_idx] +
                                 ch +
                                 self._text_buffer[self._text_cursor_idx:])
            self._text_cursor_idx += 1
            self._update_text_display()

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
            left = DrawingEngine._rdp_simplify(points[:max_idx+1], epsilon)
            right = DrawingEngine._rdp_simplify(points[max_idx:], epsilon)
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
        return result

    # ── Text Tool ─────────────────────────────────────

    def _find_text_at(self, x, y):
        for stroke in reversed(self._strokes):
            if not stroke.is_text:
                continue
            for cid in stroke.canvas_ids:
                bbox = self._canvas.bbox(cid)
                if bbox and bbox[0] <= x <= bbox[2] and bbox[1] <= y <= bbox[3]:
                    return stroke
        return None

    def auto_place_text(self):
        if self._text_active:
            self._finalize_text()

        last_stroke = None
        for s in reversed(self._strokes):
            if not s.is_text:
                last_stroke = s
                break

        if last_stroke:
            pts = last_stroke.smoothed_points or last_stroke.points
            if pts:
                ex, ey = pts[-1]
                self._start_text_at(ex, ey)
                return

    def _get_text_font(self):
        size = self._text_font_size if self._text_font_size else max(24, self._pen_width * 4)
        return (self._font_family, size)

    def _start_text_at(self, x, y, wrap_w=None):
        """Start text input at (x, y).

        wrap_w:
          - None  → simple click: auto-wrap from x to canvas right edge
          - int   → drag-created box: wrap to this exact width (left-aligned)
        """
        if self._text_active:
            self._finalize_text()

        self._text_active = True
        self._editing_stroke = None
        self._text_buffer = ""
        self._text_cursor_idx = 0
        self._text_pos = (x, y)

        font = self._get_text_font()
        dfont = self._display_font(font[0], font[1])
        # Wrap width: drag → user-defined; click → remaining canvas width
        if wrap_w is None:
            wrap_w = max(200, int(self._canvas.winfo_width() - x - 20))
        else:
            wrap_w = max(50, int(wrap_w))
        # Remember the box width so the text stroke retains it on commit + edit
        self._text_wrap_w = wrap_w
        self._text_canvas_id = self._canvas.create_text(
            x, y, text="", anchor="nw",
            fill=self._pen_color, font=dfont, tags="stroke",
            width=wrap_w, justify="left",
        )
        self._text_cursor_visible = True
        cursor_h = self._cursor_height(dfont)
        self._text_cursor_id = self._canvas.create_line(
            x, y, x, y + cursor_h,
            fill=self._pen_color, width=2, tags="text_cursor"
        )
        self._blink_cursor()

    def _edit_existing_text(self, stroke, click_x=None):
        """Enter edit mode for an existing text stroke (OneNote-like).
        If click_x is provided, places cursor at the clicked character position."""
        if self._text_active:
            self._finalize_text()

        self._text_active = True
        self._editing_stroke = stroke
        self._text_buffer = stroke.text
        self._text_pos = stroke.points[0]
        # Restore the box width so further typing keeps the original wrap geometry
        self._text_wrap_w = getattr(stroke, "wrap_width", 0) or 0

        dfont = self._display_font(stroke.font_family, stroke.font_size)
        self._text_canvas_id = stroke.canvas_ids[0]

        # Determine cursor index from click position
        bbox = self._canvas.bbox(self._text_canvas_id)
        if click_x is not None and bbox and stroke.text:
            import tkinter.font as tkFont
            try:
                f = tkFont.Font(family=dfont[0], size=dfont[1])
                rel_x = click_x - bbox[0]
                best_idx = len(stroke.text)
                for i in range(1, len(stroke.text) + 1):
                    w = f.measure(stroke.text[:i])
                    if w >= rel_x:
                        w_prev = f.measure(stroke.text[:i - 1])
                        best_idx = i - 1 if (rel_x - w_prev) < (w - rel_x) else i
                        break
                self._text_cursor_idx = best_idx
            except Exception:
                self._text_cursor_idx = len(stroke.text)
        else:
            self._text_cursor_idx = len(stroke.text)

        # Position cursor at calculated index
        self._text_cursor_visible = True
        cursor_x, cursor_y = self._calc_cursor_pos(dfont)

        cursor_h = self._cursor_height(dfont)
        self._text_cursor_id = self._canvas.create_line(
            cursor_x, cursor_y, cursor_x, cursor_y + cursor_h,
            fill=stroke.color, width=2, tags="text_cursor"
        )
        self._blink_cursor()

    def _char_index_at(self, x, y):
        """Find character index in text buffer at canvas position (x, y).

        Wrap-aware: maps visual lines (after word-wrap) to buffer offsets so
        clicking on the second visual line of a wrapped paragraph lands on the
        right buffer index.
        """
        if not self._text_canvas_id or not self._text_buffer:
            return 0
        bbox = self._canvas.bbox(self._text_canvas_id)
        if not bbox:
            return 0
        try:
            import tkinter.font as tkFont
            dfont = self._get_text_dfont()
            f = tkFont.Font(family=dfont[0], size=dfont[1])
            line_h = f.metrics('linespace')
            visual_lines = self._wrap_lines(
                self._text_buffer, f, self._get_wrap_width())
            # Which visual line?
            rel_y = y - bbox[1]
            line_num = max(0, int(rel_y / line_h)) if line_h > 0 else 0
            line_num = min(line_num, len(visual_lines) - 1)
            vline_text, n_chars, start_offset = visual_lines[line_num]
            # Character offset within the visual line
            rel_x = max(0, x - bbox[0])
            line = vline_text
            best_idx = len(line)
            for i in range(1, len(line) + 1):
                w = f.measure(line[:i])
                if w >= rel_x:
                    w_prev = f.measure(line[:i - 1])
                    best_idx = i - 1 if (rel_x - w_prev) < (w - rel_x) else i
                    break
            buf_idx = start_offset + best_idx
            return min(buf_idx, len(self._text_buffer))
        except Exception:
            return len(self._text_buffer)

    def _has_text_selection(self):
        return (self._text_sel_start >= 0 and self._text_sel_end >= 0
                and self._text_sel_start != self._text_sel_end)

    def _get_selection_range(self):
        """Return (start, end) of selection, ordered."""
        s = min(self._text_sel_start, self._text_sel_end)
        e = max(self._text_sel_start, self._text_sel_end)
        return s, e

    def _delete_text_selection(self):
        """Delete selected text and update cursor."""
        if not self._has_text_selection():
            return False
        s, e = self._get_selection_range()
        self._text_buffer = self._text_buffer[:s] + self._text_buffer[e:]
        self._text_cursor_idx = s
        self._clear_text_selection()
        return True

    def _draw_text_selection(self):
        """Draw highlight rectangles over selected text.

        Wrap-aware: emits one rectangle per visual line spanned by the
        selection — first line from sel-start to end-of-line, full middle
        lines from line-start to line-end-of-text, last line from line-start
        to sel-end. Identical to how OneNote / browser textareas highlight.
        """
        self._clear_sel_rect()  # remove old rects, keep indices
        if not self._has_text_selection() or not self._text_canvas_id:
            return
        bbox = self._canvas.bbox(self._text_canvas_id)
        if not bbox:
            return
        try:
            import tkinter.font as tkFont
            dfont = self._get_text_dfont()
            f = tkFont.Font(family=dfont[0], size=dfont[1])
            line_h = f.metrics('linespace')

            visual_lines = self._wrap_lines(self._text_buffer, f, self._get_wrap_width())
            s, e = self._get_selection_range()
            line_s, x_s_off, _   = self._buffer_idx_to_visual(s, f, visual_lines)
            line_e, x_e_off, _   = self._buffer_idx_to_visual(e, f, visual_lines)

            self._text_sel_ids = []
            for li in range(line_s, line_e + 1):
                vline_text = visual_lines[li][0]
                line_full_w = f.measure(vline_text)
                # Determine left/right x for this visual line
                if li == line_s:
                    x1 = bbox[0] + x_s_off
                else:
                    x1 = bbox[0]
                if li == line_e:
                    x2 = bbox[0] + x_e_off
                else:
                    x2 = bbox[0] + line_full_w
                # Skip degenerate rects
                if x2 <= x1:
                    continue
                y1 = bbox[1] + li * line_h
                y2 = y1 + line_h
                rid = self._canvas.create_rectangle(
                    x1, y1, x2, y2,
                    fill="#3399FF", outline="", stipple="gray50",
                    tags="text_sel"
                )
                self._text_sel_ids.append(rid)
                self._canvas.tag_lower(rid, self._text_canvas_id)
            # Keep _text_sel_id in sync with the legacy single-rect API
            self._text_sel_id = self._text_sel_ids[0] if self._text_sel_ids else None
        except Exception:
            pass

    def _clear_sel_rect(self):
        """Remove all visual selection rectangles (keep indices)."""
        for rid in getattr(self, "_text_sel_ids", []) or []:
            try:
                self._canvas.delete(rid)
            except tk.TclError:
                pass
        self._text_sel_ids = []
        if self._text_sel_id:
            try:
                self._canvas.delete(self._text_sel_id)
            except tk.TclError:
                pass
            self._text_sel_id = None

    def _clear_text_selection(self):
        """Remove selection highlight AND reset selection state."""
        self._clear_sel_rect()
        self._text_sel_start = -1
        self._text_sel_end = -1

    def _wrap_lines(self, text, f, max_width):
        """Simulate tk.Canvas word-wrap.

        Returns a list of (visual_line_text, consumed_chars, start_offset)
        where start_offset is the buffer index where this visual line begins.
        consumed_chars INCLUDES the trailing space that wraps to the next
        visual line, OR the trailing '\\n' that ends a paragraph — so summing
        them tells you the buffer position of the next visual line, and
        sum(consumed_chars) == len(text) exactly.

        max_width <= 0 → no wrapping (one visual line per paragraph).
        """
        out = []
        if not text:
            return [("", 0, 0)]
        paragraphs = text.split('\n')
        cursor = 0  # buffer offset for the next visual line to start
        for p_idx, para in enumerate(paragraphs):
            trailing_nl = 1 if p_idx < len(paragraphs) - 1 else 0
            if max_width <= 0 or not para:
                n = len(para) + trailing_nl
                out.append((para, n, cursor))
                cursor += n
                continue
            words = para.split(' ')
            current = ''         # accumulated visible text for the current line
            line_start = cursor  # buffer offset where current line begins
            for w in words:
                sep = '' if not current else ' '
                candidate = current + sep + w
                if f.measure(candidate) <= max_width or not current:
                    current = candidate
                else:
                    # Wrap: the space that would have been `sep` is consumed
                    # by THIS line (so buffer offsets stay aligned).
                    n = len(current) + 1
                    out.append((current, n, line_start))
                    line_start += n
                    current = w
            # Last visual line of this paragraph
            n = len(current) + trailing_nl
            out.append((current, n, line_start))
            cursor = line_start + n
        return out

    def _get_text_dfont(self):
        """Return display font tuple for the currently active text item."""
        stroke = self._editing_stroke
        if stroke:
            return self._display_font(stroke.font_family, stroke.font_size)
        font = self._get_text_font()
        return self._display_font(font[0], font[1])

    def _get_wrap_width(self):
        """Read wrap width from the active text item itself."""
        if not self._text_canvas_id:
            return 0
        try:
            return int(self._canvas.itemcget(self._text_canvas_id, "width"))
        except (tk.TclError, ValueError):
            return 0

    def _buffer_idx_to_visual(self, idx, f, visual_lines):
        """Map buffer index → (visual_line_num, x_offset_within_line, line_text_before_cursor)."""
        consumed = 0
        for i, (vline, n_chars, start) in enumerate(visual_lines):
            # Cursor sits on this line when target ≤ start + len(visible_text)
            in_line_end = start + len(vline)
            if idx <= in_line_end:
                in_line_idx = max(0, idx - start)
                return i, f.measure(vline[:in_line_idx]), vline[:in_line_idx]
            consumed = start + n_chars
        # Past end → end of last line
        last_i = len(visual_lines) - 1
        last_v, _, _ = visual_lines[last_i]
        return last_i, f.measure(last_v), last_v

    def _calc_cursor_pos(self, font):
        """Calculate caret (x, y) — y is the TOP of the caret line.

        Honours BOTH explicit '\\n' breaks AND tk.Canvas auto word-wrap when
        the text item has a `width=` constraint (drag-created text boxes).
        """
        bbox = self._canvas.bbox(self._text_canvas_id) if self._text_canvas_id else None
        if not bbox:
            return self._text_pos
        try:
            import tkinter.font as tkFont
            f = tkFont.Font(family=font[0], size=font[1])
            line_h = f.metrics('linespace')
            visual_lines = self._wrap_lines(self._text_buffer, f, self._get_wrap_width())
            line_num, x_off, _ = self._buffer_idx_to_visual(
                self._text_cursor_idx, f, visual_lines)
            return bbox[0] + x_off, bbox[1] + line_h * line_num
        except Exception:
            return bbox[2], bbox[1]

    def _cursor_height(self, dfont):
        """Pixel-accurate cursor line height using font metrics (NOT pt size)."""
        try:
            import tkinter.font as tkFont
            f = tkFont.Font(family=dfont[0], size=dfont[1])
            return f.metrics('linespace')
        except Exception:
            sz = dfont[1] if isinstance(dfont[1], int) else 16
            return int(sz * 1.3)

    def _blink_cursor(self):
        if not self._text_active:
            return
        self._text_cursor_visible = not self._text_cursor_visible
        if self._text_cursor_id:
            try:
                state = "normal" if self._text_cursor_visible else "hidden"
                self._canvas.itemconfigure(self._text_cursor_id, state=state)
                # When making visible, raise above text so it never hides
                if self._text_cursor_visible:
                    self._canvas.tag_raise(self._text_cursor_id)
            except tk.TclError:
                pass
        self._text_cursor_job = self._parent.after(500, self._blink_cursor)

    def _update_text_display(self):
        if not self._text_canvas_id:
            return
        if self._editing_stroke:
            family = self._editing_stroke.font_family
            size = self._editing_stroke.font_size
            color = self._editing_stroke.color
        else:
            font = self._get_text_font()
            family, size = font
            color = self._pen_color
        dfont = self._display_font(family, size)
        self._canvas.itemconfigure(self._text_canvas_id,
                                   text=self._text_buffer, font=dfont,
                                   fill=color)
        # Clamp cursor index
        self._text_cursor_idx = max(0, min(self._text_cursor_idx,
                                           len(self._text_buffer)))
        if self._text_cursor_id:
            cx, cy = self._calc_cursor_pos(dfont)
            cursor_h = self._cursor_height(dfont)
            self._canvas.coords(self._text_cursor_id, cx, cy, cx, cy + cursor_h)
            self._canvas.itemconfigure(self._text_cursor_id, fill=color)
            # ALWAYS raise caret above the text item — otherwise tag-raise
            # operations elsewhere (selection rect lower, layer reordering on
            # itemconfigure, etc.) can leave the caret hidden behind text.
            try:
                self._canvas.tag_raise(self._text_cursor_id)
            except tk.TclError:
                pass

    def _finalize_text(self):
        # Commit any pending IME character before finalizing
        if self._ime_debounce_job:
            self._parent.after_cancel(self._ime_debounce_job)
            self._ime_debounce_job = None
            if self._ime_pending_char:
                self._text_buffer = (self._text_buffer[:self._text_cursor_idx] +
                                     self._ime_pending_char +
                                     self._text_buffer[self._text_cursor_idx:])
                self._text_cursor_idx += 1
                self._ime_pending_char = None
        self._cleanup_text_cursor()
        self._clear_text_selection()

        if self._editing_stroke:
            # Editing existing text stroke
            if self._text_buffer.strip():
                self._editing_stroke.text = self._text_buffer
                # Canvas item already updated via _update_text_display
            else:
                # Empty → delete the stroke
                for cid in self._editing_stroke.canvas_ids:
                    try:
                        self._canvas.delete(cid)
                    except tk.TclError:
                        pass
                if self._editing_stroke in self._strokes:
                    self._strokes.remove(self._editing_stroke)
            self._editing_stroke = None
        elif self._text_buffer.strip() and self._text_canvas_id:
            font = self._get_text_font()
            dfont = self._display_font(font[0], font[1])
            self._canvas.itemconfigure(self._text_canvas_id,
                                       text=self._text_buffer, font=dfont)
            stroke = Stroke(
                points=[self._text_pos],
                color=self._pen_color,
                width=self._pen_width,
                canvas_ids=[self._text_canvas_id],
                is_text=True,
                text=self._text_buffer,
                font_family=self._font_family,
                font_size=font[1],  # original (un-zoomed) size
                anchor="nw",  # text tool uses nw for multiline
                wrap_width=getattr(self, "_text_wrap_w", 0) or 0,
            )
            self._strokes.append(stroke)
            self._undo_stack.clear()
        elif self._text_canvas_id:
            self._canvas.delete(self._text_canvas_id)

        self._text_canvas_id = None
        self._text_active = False
        self._text_buffer = ""

    def _cleanup_text_cursor(self):
        if self._text_cursor_job:
            self._parent.after_cancel(self._text_cursor_job)
            self._text_cursor_job = None
        if self._text_cursor_id:
            try:
                self._canvas.delete(self._text_cursor_id)
            except tk.TclError:
                pass
            self._text_cursor_id = None

    # ── Shape Detection ───────────────────────────────

    def _cancel_shape_hold(self):
        if self._shape_hold_job:
            self._parent.after_cancel(self._shape_hold_job)
            self._shape_hold_job = None

    def _try_snap_shape(self):
        self._shape_hold_job = None
        if not self._current_stroke:
            return

        stroke = self._current_stroke
        pts = stroke.points
        if len(pts) < 5:
            return

        self._current_stroke = None

        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        w = max_x - min_x
        h = max_y - min_y

        for cid in stroke.canvas_ids:
            self._canvas.delete(cid)
        stroke.canvas_ids.clear()

        stipple = "gray50" if stroke.is_highlighter else ""

        start_pt = pts[0]
        end_pt = pts[-1]
        close_dist = math.hypot(end_pt[0] - start_pt[0], end_pt[1] - start_pt[1])
        is_closed = close_dist < max(50, (w + h) * 0.15)

        if not is_closed or w < 15 or h < 15:
            shape_id = self._canvas.create_line(
                start_pt[0], start_pt[1], end_pt[0], end_pt[1],
                fill=stroke.color, width=stroke.width,
                capstyle=tk.ROUND, stipple=stipple, tags="stroke"
            )
        else:
            cx = (min_x + max_x) / 2
            cy = (min_y + max_y) / 2

            dists = [math.hypot(p[0] - cx, p[1] - cy) for p in pts]
            mean_dist = sum(dists) / len(dists)
            variance = sum((d - mean_dist)**2 for d in dists) / len(dists)
            cv = (variance ** 0.5) / mean_dist if mean_dist > 0 else 1

            if cv < 0.18:
                if 0.75 < (w / h if h > 0 else 1) < 1.33:
                    r = max(w, h) / 2
                    shape_id = self._canvas.create_oval(
                        cx - r, cy - r, cx + r, cy + r,
                        outline=stroke.color, width=stroke.width,
                        stipple=stipple, tags="stroke"
                    )
                else:
                    shape_id = self._canvas.create_oval(
                        min_x, min_y, max_x, max_y,
                        outline=stroke.color, width=stroke.width,
                        stipple=stipple, tags="stroke"
                    )
            else:
                aspect = w / h if h > 0 else 1
                if 0.8 < aspect < 1.25:
                    side = max(w, h)
                    min_x = cx - side / 2
                    min_y = cy - side / 2
                    max_x = cx + side / 2
                    max_y = cy + side / 2
                shape_id = self._canvas.create_rectangle(
                    min_x, min_y, max_x, max_y,
                    outline=stroke.color, width=stroke.width,
                    stipple=stipple, tags="stroke"
                )

        stroke.canvas_ids = [shape_id]
        stroke.smoothed_points = pts
        self._strokes.append(stroke)
        self._undo_stack.clear()

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
        if stroke is self._hw_active_text:
            self._hw_active_text = None

    def redo(self):
        if not self._undo_stack:
            return
        stroke = self._undo_stack.pop()

        if stroke.is_text:
            stroke.canvas_ids.clear()
            dfont = self._display_font(stroke.font_family, stroke.font_size)
            wrap_w = getattr(stroke, "wrap_width", 0) or 0
            kwargs = dict(text=stroke.text, anchor=stroke.anchor,
                          fill=stroke.color, font=dfont, tags="stroke",
                          justify="left")
            if wrap_w > 0:
                kwargs["width"] = wrap_w
            tid = self._canvas.create_text(
                stroke.points[0][0], stroke.points[0][1], **kwargs
            )
            stroke.canvas_ids = [tid]
            self._strokes.append(stroke)
            return

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

    # ── Handwriting Recognition ─────────────────────────

    def _recognize_handwriting(self):
        """Debounced: send batch strokes to Google API."""
        self._hw_debounce_job = None
        if not self._hw_points:
            return

        # Move batch to inflight (isolate from new incoming strokes)
        strokes_to_send = list(self._hw_points[:150])  # API limit ~150
        self._hw_inflight_strokes = list(self._hw_batch_strokes)
        self._hw_points.clear()
        self._hw_batch_strokes.clear()

        lang = self._hw_lang
        w = self._canvas.winfo_width()
        h = self._canvas.winfo_height()

        if not self._hw_recognizer:
            from ai_engine.handwriting import HandwritingRecognizer
            self._hw_recognizer = HandwritingRecognizer(
                on_result=lambda text: self._parent.after(
                    0, self._on_hw_result, text
                ),
                on_error=lambda e: print(f"[HW] {e}"),
            )

        self._hw_recognizer.recognize(
            strokes_to_send, lang, w, h,
            pre_context=self._hw_pre_context,
        )

    def _on_hw_result(self, text):
        """API result — delete drawn strokes, place/append text, show cursor."""
        if not text:
            return

        inflight = self._hw_inflight_strokes
        self._hw_inflight_strokes = []

        # Delete only the inflight drawn strokes from canvas
        all_pts = []
        for s in inflight:
            all_pts.extend(s.points)
            for cid in s.canvas_ids:
                try:
                    self._canvas.delete(cid)
                except tk.TclError:
                    pass
            if s in self._strokes:
                self._strokes.remove(s)

        if not all_pts:
            return

        hw_min_x = min(p[0] for p in all_pts)
        hw_min_y = min(p[1] for p in all_pts)
        hw_max_y = max(p[1] for p in all_pts)
        hw_center_y = (hw_min_y + hw_max_y) / 2

        # If currently editing the active text, update buffer directly
        if (self._text_active and self._editing_stroke and
                self._editing_stroke == self._hw_active_text and
                self._hw_active_text in self._strokes):
            try:
                bbox = self._canvas.bbox(self._hw_active_text.canvas_ids[0])
            except tk.TclError:
                bbox = None
            if bbox:
                active_cy = (bbox[1] + bbox[3]) / 2
                if abs(hw_center_y - active_cy) < 120:
                    sep = "" if text.startswith(" ") else " "
                    self._text_buffer += sep + text
                    self._text_cursor_idx = len(self._text_buffer)
                    self._editing_stroke.text = self._text_buffer
                    self._update_text_display()
                    self._hw_pre_context = self._text_buffer
                    return

        # Finalize any active text editing before creating/updating
        if self._text_active:
            self._finalize_text()

        # Check if should append to active text (same line, nearby)
        if self._hw_active_text and self._hw_active_text in self._strokes:
            try:
                bbox = self._canvas.bbox(self._hw_active_text.canvas_ids[0])
            except tk.TclError:
                bbox = None
            if bbox:
                active_cy = (bbox[1] + bbox[3]) / 2
                if abs(hw_center_y - active_cy) < 120:
                    sep = "" if text.startswith(" ") else " "
                    new_text = self._hw_active_text.text + sep + text
                    try:
                        self._canvas.itemconfig(
                            self._hw_active_text.canvas_ids[0], text=new_text
                        )
                    except tk.TclError:
                        pass
                    self._hw_active_text.text = new_text
                    self._hw_pre_context = new_text
                    # Enter edit mode with cursor at end
                    self._edit_existing_text(self._hw_active_text)
                    return

        # New text block at the handwriting position
        dfont = self._display_font(self._hw_font, self._hw_font_size)
        text_id = self._canvas.create_text(
            hw_min_x, hw_min_y, text=text, anchor="nw",
            fill=self._pen_color, font=dfont, tags="stroke",
        )

        stroke = Stroke(
            points=[(hw_min_x, hw_min_y)],
            color=self._pen_color,
            width=self._hw_last_pen_width,
            canvas_ids=[text_id],
            is_text=True,
            text=text,
            font_family=self._hw_font,
            font_size=self._hw_font_size,
            anchor="nw",
        )
        self._strokes.append(stroke)
        self._hw_active_text = stroke
        self._hw_pre_context = text
        # Enter edit mode with cursor at end
        self._edit_existing_text(stroke)

    def _reset_hw(self):
        """Reset handwriting state. Called on tool switch, clear, cleanup."""
        if self._hw_debounce_job:
            self._parent.after_cancel(self._hw_debounce_job)
            self._hw_debounce_job = None
        self._hw_points.clear()
        self._hw_batch_strokes.clear()
        self._hw_inflight_strokes.clear()
        self._hw_active_text = None
        self._hw_pre_context = ""

    def clear_all(self):
        self._canvas.delete("stroke")
        self._strokes.clear()
        self._undo_stack.clear()
        self._reset_hw()

    def cleanup(self):
        """Clean up scheduled jobs."""
        self._cleanup_text_cursor()
        self._cancel_shape_hold()
        self._reset_hw()
