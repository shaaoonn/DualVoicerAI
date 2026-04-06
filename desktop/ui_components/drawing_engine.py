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
        self._font_family = "Segoe UI"
        self._dragging_stroke = None
        self._drag_offset = (0, 0)

        # Shape detection state
        self._shape_hold_job = None
        self._last_move_pos = (0, 0)

        # EMA smoothing state
        self._ema_x = 0.0
        self._ema_y = 0.0
        self._ema_alpha = 0.35

    # ── Public API (called by toolbar) ────────────────

    def set_color(self, color: str):
        self._pen_color = color

    def set_width(self, width: int):
        self._pen_width = width

    def set_tool(self, tool: str):
        if self._text_active and tool != "text":
            self._finalize_text()
        self._tool = tool

    def set_font(self, font_family: str):
        self._font_family = font_family
        if self._text_active:
            self._update_text_display()

    def set_highlighter_color(self, color: str):
        self._highlighter_color = color

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
            hit = self._find_text_at(x, y)
            if hit:
                self._dragging_stroke = hit
                px, py = hit.points[0]
                self._drag_offset = (x - px, y - py)
                return
            self._start_text_at(x, y)
            return

        if self._tool == "eraser":
            self._erase_at(x, y)
            return

        if self._text_active:
            self._finalize_text()

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

    def on_key(self, event):
        if not self._text_active:
            return

        if event.keysym == "Return":
            self._finalize_text()
            return
        if event.keysym == "BackSpace":
            if self._text_buffer:
                self._text_buffer = self._text_buffer[:-1]
                self._update_text_display()
            return
        if event.keysym == "Escape":
            if self._text_canvas_id:
                self._canvas.delete(self._text_canvas_id)
                self._text_canvas_id = None
            self._cleanup_text_cursor()
            self._text_active = False
            return

        if event.char and event.char.isprintable():
            self._text_buffer += event.char
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
        size = self._pen_width * 4
        return (self._font_family, size)

    def _start_text_at(self, x, y):
        if self._text_active:
            self._finalize_text()

        self._text_active = True
        self._text_buffer = ""
        self._text_pos = (x, y)

        font = self._get_text_font()
        self._text_canvas_id = self._canvas.create_text(
            x, y, text="", anchor="w",
            fill=self._pen_color, font=font, tags="stroke"
        )
        self._text_cursor_visible = True
        self._text_cursor_id = self._canvas.create_text(
            x, y, text="|", anchor="w",
            fill=self._pen_color, font=font, tags="text_cursor"
        )
        self._blink_cursor()

    def _blink_cursor(self):
        if not self._text_active:
            return
        self._text_cursor_visible = not self._text_cursor_visible
        if self._text_cursor_id:
            try:
                state = "normal" if self._text_cursor_visible else "hidden"
                self._canvas.itemconfigure(self._text_cursor_id, state=state)
            except tk.TclError:
                pass
        self._text_cursor_job = self._parent.after(500, self._blink_cursor)

    def _update_text_display(self):
        if not self._text_canvas_id:
            return
        font = self._get_text_font()
        self._canvas.itemconfigure(self._text_canvas_id,
                                   text=self._text_buffer, font=font,
                                   fill=self._pen_color)
        bbox = self._canvas.bbox(self._text_canvas_id)
        if bbox and self._text_cursor_id:
            cx = bbox[2]
            cy = self._text_pos[1]
            self._canvas.coords(self._text_cursor_id, cx, cy)
            self._canvas.itemconfigure(self._text_cursor_id, font=font,
                                       fill=self._pen_color)
        elif self._text_cursor_id:
            self._canvas.coords(self._text_cursor_id,
                                self._text_pos[0], self._text_pos[1])

    def _finalize_text(self):
        self._cleanup_text_cursor()

        if self._text_buffer.strip() and self._text_canvas_id:
            font = self._get_text_font()
            self._canvas.itemconfigure(self._text_canvas_id,
                                       text=self._text_buffer, font=font)
            stroke = Stroke(
                points=[self._text_pos],
                color=self._pen_color,
                width=self._pen_width,
                canvas_ids=[self._text_canvas_id],
                is_text=True,
                text=self._text_buffer,
                font_family=self._font_family,
                font_size=self._pen_width * 4,
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

    def redo(self):
        if not self._undo_stack:
            return
        stroke = self._undo_stack.pop()

        if stroke.is_text:
            stroke.canvas_ids.clear()
            font = (stroke.font_family, stroke.font_size)
            tid = self._canvas.create_text(
                stroke.points[0][0], stroke.points[0][1],
                text=stroke.text, anchor="w",
                fill=stroke.color, font=font, tags="stroke"
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

    def clear_all(self):
        self._canvas.delete("stroke")
        self._strokes.clear()
        self._undo_stack.clear()

    def cleanup(self):
        """Clean up scheduled jobs."""
        self._cleanup_text_cursor()
        self._cancel_shape_hold()
