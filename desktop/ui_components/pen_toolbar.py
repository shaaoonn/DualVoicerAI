# ui_components/pen_toolbar.py
"""PenToolbar — Floating toolbar for pen/annotation tool controls."""

import tkinter as tk
import ctypes

user32 = ctypes.windll.user32
GWL_EXSTYLE     = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080


class PenToolbar(tk.Toplevel):
    """Compact floating toolbar for pen tool controls."""

    # Colors palette
    PEN_COLORS = [
        ("#FF0000", "Red"),
        ("#0066FF", "Blue"),
        ("#00CC44", "Green"),
        ("#000000", "Black"),
        ("#FFFFFF", "White"),
        ("#FFaa00", "Orange"),
    ]

    HIGHLIGHTER_COLORS = [
        ("#FFFF44", "Yellow"),
        ("#44FF88", "Green"),
        ("#44AAFF", "Blue"),
        ("#FF88CC", "Pink"),
    ]

    THICKNESS = [
        ("S", 2),
        ("M", 4),
        ("L", 8),
    ]

    BG = "#2A2A40"
    BG_ACTIVE = "#4A4A6A"
    BG_HOVER = "#3A3A55"

    def __init__(self, parent, overlay, app_ref):
        super().__init__(parent)
        self._overlay = overlay
        self._app = app_ref
        self._active_tool = "pen"
        self._active_color_btn = None
        self._active_thick_btn = None
        self._click_through = False

        self._setup_window()
        self._build_ui()
        self.after(100, self._setup_win32)

    def _setup_window(self):
        """Small floating toolbar near the main widget."""
        self.overrideredirect(True)
        self.attributes('-topmost', True)
        self.configure(bg=self.BG)

        # Position below the main toolbar
        try:
            wx = self._app.winfo_x()
            wy = self._app.winfo_y() + self._app.winfo_height() + 5
        except:
            wx, wy = 100, 100
        self.geometry(f"+{wx}+{wy}")

        # Drag support
        self._drag_data = {"x": 0, "y": 0}

    def _setup_win32(self):
        """Prevent focus stealing."""
        try:
            self.update_idletasks()
            hwnd = user32.GetParent(self.winfo_id())
            self._hwnd = hwnd
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style |= WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        except:
            pass

    def _build_ui(self):
        """Build toolbar UI: tools | colors | thickness | actions."""
        main = tk.Frame(self, bg=self.BG, padx=4, pady=3)
        main.pack(fill="both", expand=True)

        # Drag binding on the frame
        main.bind("<ButtonPress-1>", self._drag_start)
        main.bind("<B1-Motion>", self._drag_move)

        # ── Row: Tools + Colors + Thickness + Actions ──
        row = tk.Frame(main, bg=self.BG)
        row.pack(fill="x")

        # Tool buttons
        tools_frame = tk.Frame(row, bg=self.BG)
        tools_frame.pack(side="left", padx=(0, 6))

        self._btn_pen = self._tool_btn(tools_frame, "\u270f\ufe0f", "pen", "Pen")
        self._btn_highlight = self._tool_btn(tools_frame, "\U0001f58d\ufe0f", "highlighter", "Highlight")
        self._btn_eraser = self._tool_btn(tools_frame, "\U0001f9f9", "eraser", "Eraser")

        # Separator
        tk.Frame(row, bg="#555", width=1, height=22).pack(side="left", padx=3)

        # Color buttons
        colors_frame = tk.Frame(row, bg=self.BG)
        colors_frame.pack(side="left", padx=(0, 6))

        self._color_btns = {}
        for hex_color, name in self.PEN_COLORS:
            btn = tk.Button(
                colors_frame, bg=hex_color, width=2, height=1,
                relief="flat", bd=0, activebackground=hex_color,
                command=lambda c=hex_color: self._set_color(c)
            )
            btn.pack(side="left", padx=1)
            self._color_btns[hex_color] = btn
            if hex_color == "#FF0000":
                btn.configure(relief="solid", bd=2)
                self._active_color_btn = btn

        # Separator
        tk.Frame(row, bg="#555", width=1, height=22).pack(side="left", padx=3)

        # Thickness buttons
        thick_frame = tk.Frame(row, bg=self.BG)
        thick_frame.pack(side="left", padx=(0, 6))

        self._thick_btns = {}
        for label, width in self.THICKNESS:
            btn = tk.Button(
                thick_frame, text=label, bg=self.BG, fg="#CCC",
                font=("Segoe UI", 9, "bold"),
                width=2, height=1, relief="flat", bd=0,
                activebackground=self.BG_HOVER, activeforeground="#FFF",
                command=lambda w=width, l=label: self._set_thickness(w, l)
            )
            btn.pack(side="left", padx=1)
            self._thick_btns[label] = btn
            if label == "S":
                btn.configure(bg=self.BG_ACTIVE)
                self._active_thick_btn = btn

        # Separator
        tk.Frame(row, bg="#555", width=1, height=22).pack(side="left", padx=3)

        # Action buttons
        actions_frame = tk.Frame(row, bg=self.BG)
        actions_frame.pack(side="left", padx=(0, 4))

        self._action_btn(actions_frame, "\u21a9", self._undo, "Undo")
        self._action_btn(actions_frame, "\u21aa", self._redo, "Redo")
        self._action_btn(actions_frame, "\U0001f5d1", self._clear, "Clear")

        # Separator
        tk.Frame(row, bg="#555", width=1, height=22).pack(side="left", padx=3)

        # Click-through toggle + Close
        mode_frame = tk.Frame(row, bg=self.BG)
        mode_frame.pack(side="left")

        self._btn_passthrough = tk.Button(
            mode_frame, text="\U0001f5b1\ufe0f", bg=self.BG, fg="#CCC",
            font=("Segoe UI Emoji", 11), relief="flat", bd=0,
            activebackground=self.BG_HOVER,
            command=self._toggle_click_through
        )
        self._btn_passthrough.pack(side="left", padx=1)

        self._btn_close = tk.Button(
            mode_frame, text="\u2716", bg="#663333", fg="#FFF",
            font=("Segoe UI", 10, "bold"), relief="flat", bd=0,
            width=2, activebackground="#993333",
            command=self._close_pen
        )
        self._btn_close.pack(side="left", padx=(4, 0))

    def _tool_btn(self, parent, emoji, tool_name, tooltip=""):
        """Create a tool toggle button."""
        bg = self.BG_ACTIVE if tool_name == "pen" else self.BG
        btn = tk.Button(
            parent, text=emoji, bg=bg, fg="#CCC",
            font=("Segoe UI Emoji", 11), relief="flat", bd=0,
            activebackground=self.BG_HOVER,
            command=lambda: self._set_tool(tool_name)
        )
        btn.pack(side="left", padx=1)
        return btn

    def _action_btn(self, parent, text, command, tooltip=""):
        """Create an action button (undo, redo, clear)."""
        btn = tk.Button(
            parent, text=text, bg=self.BG, fg="#CCC",
            font=("Segoe UI", 11), relief="flat", bd=0,
            activebackground=self.BG_HOVER,
            command=command
        )
        btn.pack(side="left", padx=1)
        return btn

    # ── Actions ───────────────────────────────────────

    def _set_tool(self, tool):
        self._active_tool = tool
        self._overlay.set_tool(tool)

        # Update visual state
        for name, btn in [("pen", self._btn_pen),
                          ("highlighter", self._btn_highlight),
                          ("eraser", self._btn_eraser)]:
            btn.configure(bg=self.BG_ACTIVE if name == tool else self.BG)

    def _set_color(self, color):
        self._overlay.set_color(color)
        # Deselect previous
        if self._active_color_btn:
            self._active_color_btn.configure(relief="flat", bd=0)
        # Select new
        btn = self._color_btns.get(color)
        if btn:
            btn.configure(relief="solid", bd=2)
            self._active_color_btn = btn
        # Switch to pen tool
        if self._active_tool != "pen":
            self._set_tool("pen")

    def _set_thickness(self, width, label):
        self._overlay.set_width(width)
        # Update visual
        if self._active_thick_btn:
            self._active_thick_btn.configure(bg=self.BG)
        btn = self._thick_btns.get(label)
        if btn:
            btn.configure(bg=self.BG_ACTIVE)
            self._active_thick_btn = btn

    def _undo(self):
        self._overlay.undo()

    def _redo(self):
        self._overlay.redo()

    def _clear(self):
        self._overlay.clear_all()

    def _toggle_click_through(self):
        self._click_through = not self._click_through
        self._overlay.set_click_through(self._click_through)
        # Visual feedback
        if self._click_through:
            self._btn_passthrough.configure(bg="#336633", fg="#AFA")
        else:
            self._btn_passthrough.configure(bg=self.BG, fg="#CCC")

    def _close_pen(self):
        """Close pen mode entirely."""
        self._overlay.close()

    # ── Drag ──────────────────────────────────────────

    def _drag_start(self, event):
        self._drag_data["x"] = event.x_root - self.winfo_x()
        self._drag_data["y"] = event.y_root - self.winfo_y()

    def _drag_move(self, event):
        x = event.x_root - self._drag_data["x"]
        y = event.y_root - self._drag_data["y"]
        self.geometry(f"+{x}+{y}")

    def get_hwnd(self):
        return getattr(self, '_hwnd', None)
