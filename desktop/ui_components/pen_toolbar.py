# ui_components/pen_toolbar.py
"""PenToolbar — Floating toolbar for pen/annotation tool controls.
Pen/highlighter buttons toggle between draw mode (shows cursor) and view mode.
Thickness controlled by slider (1-100px)."""

import tkinter as tk
import tkinter.font as tkfont
import ctypes

user32 = ctypes.windll.user32
GWL_EXSTYLE     = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080


class PenToolbar(tk.Toplevel):
    """Compact floating toolbar for pen tool controls."""

    PEN_COLORS = [
        ("#FF0000", "Red"),
        ("#0066FF", "Blue"),
        ("#00CC44", "Green"),
        ("#000000", "Black"),
        ("#FFFFFF", "White"),
        ("#FFaa00", "Orange"),
    ]

    BG = "#2A2A40"
    BG_ACTIVE = "#4A4A6A"
    BG_HOVER = "#3A3A55"

    ICON_PEN = "\u270f\ufe0f"
    ICON_HIGHLIGHTER = "\U0001f58d\ufe0f"
    ICON_ERASER = "\U0001f9f9"
    ICON_MOUSE = "\U0001f5b1\ufe0f"
    ICON_TEXT = "T"
    ICON_HANDWRITE = "\u270d\ufe0f"
    ICON_HAND = "\u270b"

    POPULAR_FONTS = [
        "Segoe UI",
        "Arial",
        "Nirmala UI",
        "Times New Roman",
        "Courier New",
        "Impact",
        "Comic Sans MS",
        "Consolas",
    ]
    SEPARATOR = "── আরো ──"

    def __init__(self, parent, overlay, app_ref):
        super().__init__(parent)
        self._overlay = overlay
        self._app = app_ref
        self._active_tool = "pen"
        self._draw_mode = True
        self._active_color_btn = None
        self._font_list = self._build_font_list()

        self._setup_window()
        self._build_ui()
        self.after(100, self._setup_win32)

    def _build_font_list(self):
        """Build font list: popular 8 + separator + all system fonts."""
        try:
            all_fonts = sorted(set(tkfont.families(self)),
                               key=lambda f: f.lower())
            # Filter out @-prefixed vertical fonts
            all_fonts = [f for f in all_fonts if not f.startswith("@")]
        except Exception:
            all_fonts = []

        popular = [f for f in self.POPULAR_FONTS if f in all_fonts]
        remaining = [f for f in all_fonts if f not in popular]

        if remaining:
            return popular + [self.SEPARATOR] + remaining
        return popular

    def _setup_window(self):
        self.overrideredirect(True)
        self.attributes('-topmost', True)
        self.configure(bg=self.BG)
        try:
            wx = self._app.winfo_x()
            wy = self._app.winfo_y() + self._app.winfo_height() + 5
        except tk.TclError:
            wx, wy = 100, 100
        self.geometry(f"+{wx}+{wy}")
        self._drag_data = {"x": 0, "y": 0}

    def _setup_win32(self):
        try:
            self.update_idletasks()
            hwnd = user32.GetParent(self.winfo_id())
            self._hwnd = hwnd
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style |= WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        except (OSError, ctypes.ArgumentError):
            pass

    def _build_ui(self):
        main = tk.Frame(self, bg=self.BG, padx=4, pady=3)
        main.pack(fill="both", expand=True)
        main.bind("<ButtonPress-1>", self._drag_start)
        main.bind("<B1-Motion>", self._drag_move)

        row = tk.Frame(main, bg=self.BG)
        row.pack(fill="x")

        # ── Tool buttons ──
        tools_frame = tk.Frame(row, bg=self.BG)
        tools_frame.pack(side="left", padx=(0, 6))

        self._btn_pen = tk.Button(
            tools_frame, text=self.ICON_MOUSE, bg=self.BG_ACTIVE, fg="#CCC",
            font=("Segoe UI Emoji", 11), relief="flat", bd=0,
            activebackground=self.BG_HOVER,
            command=lambda: self._toggle_tool("pen")
        )
        self._btn_pen.pack(side="left", padx=1)

        self._btn_highlight = tk.Button(
            tools_frame, text=self.ICON_HIGHLIGHTER, bg=self.BG, fg="#CCC",
            font=("Segoe UI Emoji", 11), relief="flat", bd=0,
            activebackground=self.BG_HOVER,
            command=lambda: self._toggle_tool("highlighter")
        )
        self._btn_highlight.pack(side="left", padx=1)

        self._btn_eraser = tk.Button(
            tools_frame, text=self.ICON_ERASER, bg=self.BG, fg="#CCC",
            font=("Segoe UI Emoji", 11), relief="flat", bd=0,
            activebackground=self.BG_HOVER,
            command=lambda: self._activate_eraser()
        )
        self._btn_eraser.pack(side="left", padx=1)

        self._btn_text = tk.Button(
            tools_frame, text=self.ICON_TEXT, bg=self.BG, fg="#CCC",
            font=("Segoe UI", 12, "bold"), relief="flat", bd=0,
            activebackground=self.BG_HOVER, width=2,
            command=lambda: self._toggle_tool("text")
        )
        self._btn_text.pack(side="left", padx=1)

        self._btn_handwrite = tk.Button(
            tools_frame, text=self.ICON_HANDWRITE, bg=self.BG, fg="#CCC",
            font=("Segoe UI Emoji", 11), relief="flat", bd=0,
            activebackground=self.BG_HOVER,
            command=lambda: self._toggle_tool("handwrite")
        )
        self._btn_handwrite.pack(side="left", padx=1)

        # ── Hand + Zoom (editor mode only) ──
        self._btn_hand = None
        if not getattr(self._overlay, '_supports_view_mode', True):
            self._btn_hand = tk.Button(
                tools_frame, text=self.ICON_HAND, bg=self.BG, fg="#CCC",
                font=("Segoe UI Emoji", 11), relief="flat", bd=0,
                activebackground=self.BG_HOVER,
                command=lambda: self._toggle_tool("pan")
            )
            self._btn_hand.pack(side="left", padx=1)

        # ── Zoom slider (editor mode only) ──
        if not getattr(self._overlay, '_supports_view_mode', True):
            tk.Frame(row, bg="#555", width=1, height=22).pack(side="left", padx=3)
            zoom_frame = tk.Frame(row, bg=self.BG)
            zoom_frame.pack(side="left", padx=(0, 4))
            self._zoom_label = tk.Label(
                zoom_frame, text="জুম 100%", bg=self.BG, fg="#CCC",
                font=("Segoe UI", 8), width=8
            )
            self._zoom_label.pack(side="left")
            self._zoom_var = tk.IntVar(value=100)
            self._zoom_slider = tk.Scale(
                zoom_frame, from_=10, to=400, orient="horizontal",
                variable=self._zoom_var, length=80, sliderlength=12,
                showvalue=False, bg=self.BG, fg="#CCC", troughcolor="#1A1A2A",
                highlightthickness=0, bd=0, activebackground=self.BG_ACTIVE,
                font=("Segoe UI", 7), command=self._on_zoom_change
            )
            self._zoom_slider.pack(side="left", padx=2)

        # ── Separator ──
        tk.Frame(row, bg="#555", width=1, height=22).pack(side="left", padx=3)

        # ── Font dropdown (for text tool) ──
        self._font_var = tk.StringVar(value=self._font_list[0] if self._font_list else "Segoe UI")
        self._font_menu = tk.OptionMenu(
            row, self._font_var, *self._font_list,
            command=self._on_font_change
        )
        self._font_menu.configure(
            bg=self.BG, fg="#CCC", font=("Segoe UI", 9),
            highlightthickness=0, bd=0, relief="flat",
            activebackground=self.BG_HOVER, activeforeground="#FFF",
            width=10
        )
        self._font_menu["menu"].configure(
            bg="#1A1A2A", fg="#CCC", font=("Segoe UI", 9),
            activebackground=self.BG_ACTIVE, activeforeground="#FFF"
        )
        self._font_menu.pack(side="left", padx=(0, 4))

        # ── Separator ──
        tk.Frame(row, bg="#555", width=1, height=22).pack(side="left", padx=3)

        # ── Color buttons ──
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

        # ── Separator ──
        tk.Frame(row, bg="#555", width=1, height=22).pack(side="left", padx=3)

        # ── Thickness / Font-size slider ──
        thick_frame = tk.Frame(row, bg=self.BG)
        thick_frame.pack(side="left", padx=(0, 6))

        self._slider_label = tk.Label(
            thick_frame, text="পেন", bg=self.BG, fg="#CCC",
            font=("Segoe UI", 7), width=4
        )
        self._slider_label.pack(side="left")

        self._thickness_var = tk.IntVar(value=4)
        self._slider = tk.Scale(
            thick_frame, from_=1, to=100, orient="horizontal",
            variable=self._thickness_var,
            length=110, sliderlength=14,
            showvalue=True,
            bg=self.BG, fg="#CCC", troughcolor="#1A1A2A",
            highlightthickness=0, bd=0,
            activebackground=self.BG_ACTIVE,
            font=("Segoe UI", 7),
            command=self._on_thickness_change
        )
        self._slider.pack(side="left", padx=2)

        # ── Separator ──
        tk.Frame(row, bg="#555", width=1, height=22).pack(side="left", padx=3)

        # ── Action buttons ──
        actions_frame = tk.Frame(row, bg=self.BG)
        actions_frame.pack(side="left", padx=(0, 4))

        self._action_btn(actions_frame, "\u21a9", self._undo)
        self._action_btn(actions_frame, "\u21aa", self._redo)
        self._action_btn(actions_frame, "\U0001f5d1", self._clear)

        # ── Separator ──
        tk.Frame(row, bg="#555", width=1, height=22).pack(side="left", padx=3)

        # ── Fullscreen (editor mode only) ──
        if not getattr(self._overlay, '_supports_view_mode', True):
            tk.Button(
                row, text="\u26f6", bg=self.BG, fg="#CCC",
                font=("Segoe UI", 12), relief="flat", bd=0,
                activebackground=self.BG_HOVER,
                command=self._toggle_fullscreen
            ).pack(side="left", padx=1)

        # ── Editor (overlay mode only) ──
        if getattr(self._overlay, '_supports_view_mode', True):
            tk.Button(
                row, text="\U0001f4c4", bg=self.BG, fg="#CCC",
                font=("Segoe UI Emoji", 11), relief="flat", bd=0,
                activebackground=self.BG_HOVER,
                command=self._open_editor
            ).pack(side="left", padx=1)

        # ── Close ──
        tk.Button(
            row, text="\u2716", bg="#663333", fg="#FFF",
            font=("Segoe UI", 10, "bold"), relief="flat", bd=0,
            width=2, activebackground="#993333",
            command=self._close_pen
        ).pack(side="left")

    def _action_btn(self, parent, text, command):
        tk.Button(
            parent, text=text, bg=self.BG, fg="#CCC",
            font=("Segoe UI", 11), relief="flat", bd=0,
            activebackground=self.BG_HOVER, command=command
        ).pack(side="left", padx=1)

    # ── Tool Toggle ───────────────────────────────────

    def _toggle_tool(self, tool):
        if tool == "pan":
            # Pan is editor-only
            self._active_tool = "pan"
            self._overlay.set_tool("pan")
            self._draw_mode = True
            self._update_tool_icons()
            return

        prev_tool = self._active_tool

        if self._active_tool == tool and self._draw_mode:
            if getattr(self._overlay, '_supports_view_mode', True):
                self._enter_view_mode()
            else:
                # Editor mode: enter select mode
                self._active_tool = "select"
                self._overlay.set_tool("select")
                self._update_tool_icons()
                return
        else:
            self._active_tool = tool
            self._overlay.set_tool(tool)
            self._enter_draw_mode()
            if tool == "text":
                self._overlay.auto_place_text()

        # Swap slider between pen thickness ↔ font size
        font_tools = ("handwrite", "text")
        entering_font = prev_tool not in font_tools and tool in font_tools
        leaving_font = prev_tool in font_tools and tool not in font_tools
        switching_font = prev_tool in font_tools and tool in font_tools

        if entering_font or switching_font:
            if entering_font:
                self._saved_pen_thickness = self._thickness_var.get()
            engine = getattr(self._overlay, '_engine', None)
            if tool == "handwrite":
                hw_size = getattr(engine, '_hw_font_size', 24) if engine else 24
                self._thickness_var.set(hw_size)
            else:
                txt_size = getattr(engine, '_text_font_size', 0) if engine else 0
                if not txt_size:
                    pen_w = getattr(engine, '_pen_width', 4) if engine else 4
                    txt_size = pen_w * 4
                self._thickness_var.set(txt_size)
            self._slider_label.configure(text="ফন্ট")
        elif leaving_font:
            saved = getattr(self, '_saved_pen_thickness', 4)
            self._thickness_var.set(saved)
            self._overlay.set_width(saved)
            self._slider_label.configure(text="পেন")

    def _activate_eraser(self):
        self._active_tool = "eraser"
        self._overlay.set_tool("eraser")
        self._enter_draw_mode()

    def _enter_draw_mode(self):
        self._draw_mode = True
        self._overlay.set_click_through(False)
        self._update_tool_icons()

    def _enter_view_mode(self):
        self._draw_mode = False
        self._overlay.set_click_through(True)
        self._update_tool_icons()

    def _update_tool_icons(self):
        is_select = self._active_tool == "select"
        if self._draw_mode or is_select:
            active = self._active_tool
            pen_icon = self.ICON_MOUSE if active in ("pen", "select") else self.ICON_PEN
            hl_icon = self.ICON_MOUSE if active == "highlighter" else self.ICON_HIGHLIGHTER
            er_icon = self.ICON_MOUSE if active == "eraser" else self.ICON_ERASER
            self._btn_pen.configure(text=pen_icon,
                bg=self.BG_ACTIVE if active in ("pen", "select") else self.BG)
            self._btn_highlight.configure(text=hl_icon,
                bg=self.BG_ACTIVE if active == "highlighter" else self.BG)
            self._btn_eraser.configure(text=er_icon,
                bg=self.BG_ACTIVE if active == "eraser" else self.BG)
            txt_icon = self.ICON_MOUSE if active == "text" else self.ICON_TEXT
            txt_font = ("Segoe UI Emoji", 11) if active == "text" else ("Segoe UI", 12, "bold")
            self._btn_text.configure(text=txt_icon, font=txt_font,
                bg=self.BG_ACTIVE if active == "text" else self.BG)
            hw_icon = self.ICON_MOUSE if active == "handwrite" else self.ICON_HANDWRITE
            hw_font = ("Segoe UI Emoji", 11)
            self._btn_handwrite.configure(text=hw_icon, font=hw_font,
                bg=self.BG_ACTIVE if active == "handwrite" else self.BG)
            if self._btn_hand:
                self._btn_hand.configure(
                    bg=self.BG_ACTIVE if active == "pan" else self.BG)
        else:
            self._btn_pen.configure(text=self.ICON_PEN, bg=self.BG)
            self._btn_highlight.configure(text=self.ICON_HIGHLIGHTER, bg=self.BG)
            self._btn_eraser.configure(text=self.ICON_ERASER, bg=self.BG)
            self._btn_text.configure(text=self.ICON_TEXT,
                font=("Segoe UI", 12, "bold"), bg=self.BG)
            self._btn_handwrite.configure(text=self.ICON_HANDWRITE, bg=self.BG)
            if self._btn_hand:
                self._btn_hand.configure(bg=self.BG)

    def sync_draw_mode(self):
        self._draw_mode = True
        if self._active_tool not in ("pen", "highlighter", "eraser", "text", "handwrite"):
            self._active_tool = "pen"
        self._overlay.set_tool(self._active_tool)
        self._overlay.set_click_through(False)
        self._update_tool_icons()

    def sync_view_mode(self):
        self._draw_mode = False
        self._overlay.set_click_through(True)
        self._update_tool_icons()

    # ── Actions ───────────────────────────────────────

    def _on_font_change(self, font_name):
        """Change font for text tool."""
        if font_name == self.SEPARATOR:
            # Revert to previous font — separator is not selectable
            self._font_var.set(self._font_list[0])
            return
        self._overlay.set_font(font_name)

    def _set_color(self, color):
        self._overlay.set_color(color)
        if self._active_color_btn:
            self._active_color_btn.configure(relief="flat", bd=0)
        btn = self._color_btns.get(color)
        if btn:
            btn.configure(relief="solid", bd=2)
            self._active_color_btn = btn
        # Keep current tool if it's text
        if self._active_tool != "text":
            self._active_tool = "pen"
            self._overlay.set_tool("pen")
        self._enter_draw_mode()

    def _on_thickness_change(self, value):
        val = int(value)
        if self._active_tool == "handwrite":
            # Slider controls font size in handwrite mode
            engine = getattr(self._overlay, '_engine', None)
            hw_font = getattr(engine, '_hw_font', "Segoe UI") if engine else "Segoe UI"
            if hasattr(self._overlay, 'set_hw_font'):
                self._overlay.set_hw_font(hw_font, val)
            elif engine:
                engine.set_hw_font(hw_font, val)
        elif self._active_tool == "text":
            # Slider directly controls text font size
            if hasattr(self._overlay, 'set_text_font_size'):
                self._overlay.set_text_font_size(val)
            else:
                engine = getattr(self._overlay, '_engine', None)
                if engine:
                    engine._text_font_size = val
                    if engine._text_active:
                        engine._update_text_display()
        else:
            self._overlay.set_width(val)

    def _undo(self):
        self._overlay.undo()

    def _redo(self):
        self._overlay.redo()

    def _clear(self):
        self._overlay.clear_all()

    def _close_pen(self):
        self._overlay.close()

    def _on_zoom_change(self, value):
        level = int(value)
        if hasattr(self, '_zoom_label'):
            self._zoom_label.configure(text=f"জুম {level}%")
        if hasattr(self._overlay, 'set_zoom'):
            self._overlay.set_zoom(level / 100.0)

    def _toggle_fullscreen(self):
        if hasattr(self._overlay, '_toggle_fullscreen'):
            self._overlay._toggle_fullscreen()

    def _open_editor(self):
        if hasattr(self._app, 'open_editor_window'):
            self._app.open_editor_window()

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
