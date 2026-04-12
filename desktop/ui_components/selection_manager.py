# ui_components/selection_manager.py
"""SelectionManager — Canvas item selection, move, and resize for the editor.

Handles click-to-select, rubber-band (marquee) selection, drag-to-move,
and corner-handle resize. Works with DrawingEngine Stroke objects."""

import tkinter as tk
from typing import List, Optional, Tuple

from PIL import Image, ImageTk
from ui_components.drawing_engine import Stroke


class SelectionManager:
    """Manages selection, move, and resize of canvas items."""

    HANDLE_SIZE = 8
    SEL_COLOR = "#4A90D9"
    SEL_DASH = (4, 4)
    HANDLE_FILL = "#FFFFFF"
    HANDLE_OUTLINE = "#4A90D9"

    def __init__(self, canvas: tk.Canvas):
        self._canvas = canvas
        self._selected: List[Stroke] = []
        self._sel_rect_id: Optional[int] = None
        self._handle_ids: List[int] = []
        self._mode = "idle"  # idle | moving | resizing | rubber_band
        self._drag_start = (0.0, 0.0)
        self._resize_idx: Optional[int] = None
        self._rubber_band_id: Optional[int] = None
        self._anchor = (0.0, 0.0)  # opposite corner for resize
        self._image_refs: list = []  # prevent GC of resized images

    # ── Public API ───────────────────────────────────

    def on_mouse_down(self, x: float, y: float, all_strokes: List[Stroke]):
        # 1) Check handles first (resize)
        hidx = self._hit_handle(x, y)
        if hidx is not None and self._selected:
            self._mode = "resizing"
            self._resize_idx = hidx
            self._drag_start = (x, y)
            bbox = self._selection_bbox()
            if bbox:
                # Anchor is opposite corner
                cx = (bbox[0] + bbox[2]) / 2
                cy = (bbox[1] + bbox[3]) / 2
                # Map handle index to anchor point
                anchors = [
                    (bbox[2], bbox[3]),  # 0=TL → anchor BR
                    (bbox[0], bbox[3]),  # 1=TR → anchor BL
                    (bbox[2], bbox[1]),  # 2=BL → anchor TR
                    (bbox[0], bbox[1]),  # 3=BR → anchor TL
                    (cx, bbox[3]),       # 4=TC → anchor BC
                    (cx, bbox[1]),       # 5=BC → anchor TC
                    (bbox[2], cy),       # 6=ML → anchor MR
                    (bbox[0], cy),       # 7=MR → anchor ML
                ]
                self._anchor = anchors[hidx]
            return

        # 2) Check if clicking on an already-selected item (move)
        stroke = self._find_stroke_at(x, y, all_strokes)
        if stroke and stroke in self._selected:
            self._mode = "moving"
            self._drag_start = (x, y)
            return

        # 3) Click on an unselected item (select it)
        if stroke:
            self.deselect_all()
            self._select_stroke(stroke)
            self._mode = "moving"
            self._drag_start = (x, y)
            return

        # 4) Empty area — start rubber-band
        self.deselect_all()
        self._mode = "rubber_band"
        self._drag_start = (x, y)
        self._rubber_band_id = self._canvas.create_rectangle(
            x, y, x, y, outline=self.SEL_COLOR, dash=self.SEL_DASH,
            width=1, tags="sel_rubber"
        )

    def on_mouse_move(self, x: float, y: float):
        if self._mode == "moving":
            dx = x - self._drag_start[0]
            dy = y - self._drag_start[1]
            self._move_selection(dx, dy)
            self._drag_start = (x, y)
        elif self._mode == "resizing":
            self._resize_selection(x, y)
            self._drag_start = (x, y)
        elif self._mode == "rubber_band":
            if self._rubber_band_id:
                sx, sy = self._drag_start
                self._canvas.coords(self._rubber_band_id, sx, sy, x, y)

    def on_mouse_up(self, x: float, y: float, all_strokes: List[Stroke]):
        if self._mode == "rubber_band":
            if self._rubber_band_id:
                self._canvas.delete(self._rubber_band_id)
                self._rubber_band_id = None
            sx, sy = self._drag_start
            found = self._find_strokes_in_rect(
                min(sx, x), min(sy, y), max(sx, x), max(sy, y), all_strokes
            )
            if found:
                for s in found:
                    self._select_stroke(s, add=True)
                self._draw_selection_visuals()
        self._mode = "idle"

    def deselect_all(self):
        self._clear_visuals()
        self._selected.clear()
        self._mode = "idle"

    @property
    def has_selection(self) -> bool:
        return len(self._selected) > 0

    # ── Selection visuals ────────────────────────────

    def _select_stroke(self, stroke: Stroke, add: bool = False):
        if not add:
            self._selected.clear()
        if stroke not in self._selected:
            self._selected.append(stroke)
        self._draw_selection_visuals()

    def _draw_selection_visuals(self):
        self._clear_visuals()
        bbox = self._selection_bbox()
        if not bbox:
            return
        x1, y1, x2, y2 = bbox
        pad = 4
        x1 -= pad; y1 -= pad; x2 += pad; y2 += pad

        # Selection rectangle
        self._sel_rect_id = self._canvas.create_rectangle(
            x1, y1, x2, y2, outline=self.SEL_COLOR,
            dash=self.SEL_DASH, width=2, tags="sel_visual"
        )

        # 8 handles: 4 corners + 4 midpoints
        hs = self.HANDLE_SIZE // 2
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        handle_positions = [
            (x1, y1), (x2, y1),  # TL, TR
            (x1, y2), (x2, y2),  # BL, BR
            (cx, y1), (cx, y2),  # TC, BC
            (x1, cy), (x2, cy),  # ML, MR
        ]
        for hx, hy in handle_positions:
            hid = self._canvas.create_rectangle(
                hx - hs, hy - hs, hx + hs, hy + hs,
                fill=self.HANDLE_FILL, outline=self.HANDLE_OUTLINE,
                width=1, tags="sel_visual"
            )
            self._handle_ids.append(hid)

    def _clear_visuals(self):
        if self._sel_rect_id:
            self._canvas.delete(self._sel_rect_id)
            self._sel_rect_id = None
        for hid in self._handle_ids:
            self._canvas.delete(hid)
        self._handle_ids.clear()

    def _selection_bbox(self) -> Optional[Tuple[float, float, float, float]]:
        """Union bounding box of all selected strokes."""
        bx1 = by1 = float('inf')
        bx2 = by2 = float('-inf')
        found = False
        for stroke in self._selected:
            for cid in stroke.canvas_ids:
                bb = self._canvas.bbox(cid)
                if bb:
                    found = True
                    bx1 = min(bx1, bb[0])
                    by1 = min(by1, bb[1])
                    bx2 = max(bx2, bb[2])
                    by2 = max(by2, bb[3])
        return (bx1, by1, bx2, by2) if found else None

    # ── Hit testing ──────────────────────────────────

    def _hit_handle(self, x: float, y: float) -> Optional[int]:
        """Return handle index if (x,y) is on a handle, else None."""
        hs = self.HANDLE_SIZE
        for i, hid in enumerate(self._handle_ids):
            bb = self._canvas.bbox(hid)
            if bb and (bb[0] - hs <= x <= bb[2] + hs and
                       bb[1] - hs <= y <= bb[3] + hs):
                return i
        return None

    def _find_stroke_at(self, x: float, y: float,
                        all_strokes: List[Stroke]) -> Optional[Stroke]:
        """Find topmost stroke at (x,y)."""
        r = 5  # tolerance
        overlapping = self._canvas.find_overlapping(x - r, y - r, x + r, y + r)
        if not overlapping:
            return None
        # Filter out selection visuals and page backgrounds
        overlapping = [
            oid for oid in overlapping
            if "sel_visual" not in self._canvas.gettags(oid)
            and "sel_rubber" not in self._canvas.gettags(oid)
            and "page_bg" not in self._canvas.gettags(oid)
            and "plus_btn" not in self._canvas.gettags(oid)
        ]
        if not overlapping:
            return None
        # Match to strokes (reverse = topmost first)
        for stroke in reversed(all_strokes):
            for cid in stroke.canvas_ids:
                if cid in overlapping:
                    return stroke
        return None

    def _find_strokes_in_rect(self, x1: float, y1: float, x2: float, y2: float,
                              all_strokes: List[Stroke]) -> List[Stroke]:
        """Find all strokes with canvas items inside the rectangle."""
        # Use find_overlapping (more forgiving than find_enclosed)
        overlapping = set(self._canvas.find_overlapping(x1, y1, x2, y2))
        result = []
        for stroke in all_strokes:
            for cid in stroke.canvas_ids:
                if cid in overlapping:
                    result.append(stroke)
                    break
        return result

    # ── Move ─────────────────────────────────────────

    def _move_selection(self, dx: float, dy: float):
        """Move all selected strokes by (dx, dy)."""
        for stroke in self._selected:
            for cid in stroke.canvas_ids:
                self._canvas.move(cid, dx, dy)
            # Update stroke points
            stroke.points = [(px + dx, py + dy) for px, py in stroke.points]
            if stroke.smoothed_points:
                stroke.smoothed_points = [
                    (px + dx, py + dy) for px, py in stroke.smoothed_points
                ]
        # Move visuals
        if self._sel_rect_id:
            self._canvas.move(self._sel_rect_id, dx, dy)
        for hid in self._handle_ids:
            self._canvas.move(hid, dx, dy)

    # ── Resize ───────────────────────────────────────

    def _resize_selection(self, x: float, y: float):
        """Scale selected strokes based on drag from handle."""
        bbox = self._selection_bbox()
        if not bbox:
            return
        ax, ay = self._anchor
        old_w = abs(self._drag_start[0] - ax)
        old_h = abs(self._drag_start[1] - ay)
        new_w = abs(x - ax)
        new_h = abs(y - ay)

        if old_w < 5 or old_h < 5:
            return

        sx = new_w / old_w if old_w > 0 else 1.0
        sy = new_h / old_h if old_h > 0 else 1.0
        # Clamp to prevent items from disappearing
        sx = max(0.2, min(5.0, sx))
        sy = max(0.2, min(5.0, sy))

        for stroke in self._selected:
            if getattr(stroke, '_is_image', False):
                # Image stroke: recreate at new size
                self._resize_image_stroke(stroke, ax, ay, sx, sy)
            else:
                for cid in stroke.canvas_ids:
                    self._canvas.scale(cid, ax, ay, sx, sy)
                # Update stroke points
                stroke.points = [
                    (ax + (px - ax) * sx, ay + (py - ay) * sy)
                    for px, py in stroke.points
                ]
                if stroke.smoothed_points:
                    stroke.smoothed_points = [
                        (ax + (px - ax) * sx, ay + (py - ay) * sy)
                        for px, py in stroke.smoothed_points
                    ]
                if stroke.is_text:
                    # Scale font size for text strokes
                    scale_factor = max(sx, sy)
                    new_fs = max(8, int(stroke.font_size * scale_factor))
                    stroke.font_size = new_fs
                    for cid in stroke.canvas_ids:
                        try:
                            self._canvas.itemconfigure(
                                cid, font=(stroke.font_family, new_fs))
                        except tk.TclError:
                            pass
                else:
                    # Scale width for drawing strokes
                    new_w_val = max(1, int(stroke.width * max(sx, sy)))
                    stroke.width = new_w_val
                    for cid in stroke.canvas_ids:
                        try:
                            self._canvas.itemconfigure(cid, width=new_w_val)
                        except tk.TclError:
                            pass

        # Refresh visuals
        self._draw_selection_visuals()

    def _resize_image_stroke(self, stroke: Stroke, ax, ay, sx, sy):
        """Resize an image stroke by recreating the image at new size."""
        pil_img = getattr(stroke, '_pil_image', None)
        if not pil_img:
            return
        # Calculate new position
        old_x, old_y = stroke.points[0]
        new_x = ax + (old_x - ax) * sx
        new_y = ay + (old_y - ay) * sy
        # Calculate new image size
        new_img_w = max(10, int(pil_img.width * sx))
        new_img_h = max(10, int(pil_img.height * sy))
        resized = pil_img.resize((new_img_w, new_img_h), Image.LANCZOS)
        # Update PIL reference
        stroke._pil_image = resized
        stroke.points = [(new_x, new_y)]
        # Delete old canvas item, create new
        for cid in stroke.canvas_ids:
            self._canvas.delete(cid)
        tk_img = ImageTk.PhotoImage(resized)
        self._image_refs.append(tk_img)
        new_cid = self._canvas.create_image(
            int(new_x), int(new_y), anchor="nw", image=tk_img, tags="stroke"
        )
        stroke.canvas_ids = [new_cid]
