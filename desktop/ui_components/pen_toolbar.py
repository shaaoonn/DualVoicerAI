# ui_components/pen_toolbar.py
"""PenToolbar - Dual-mode toolbar for pen/annotation tool controls.
  - mode="standalone": Floating Toplevel window (used by EditorWindow)
  - mode="embedded":   tk.Frame embedded in main widget canvas (slide-out panel)
Pen/highlighter buttons toggle between draw mode (shows cursor) and view mode.
Thickness controlled by slider (1-100px)."""

import tkinter as tk
import tkinter.font as tkfont
import ctypes
from i18n import tr

user32 = ctypes.windll.user32
GWL_EXSTYLE     = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080


class PenToolbar:
    """Compact toolbar for pen tool controls - standalone or embedded."""

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
    SEPARATOR = tr("tb_separator")

    def __init__(self, parent, overlay, app_ref, mode="standalone",
                 on_retract=None):
        self._mode = mode
        self._overlay = overlay
        self._app = app_ref
        self._active_tool = "pen"
        self._draw_mode = True
        self._active_color_btn = None
        self._on_retract_cb = on_retract
        self._hwnd = None

        if mode == "standalone":
            self._root = tk.Toplevel(parent)
            self._font_list = self._build_font_list(self._root)
            self._setup_window()
            self._build_ui_standalone()
            self._root.after(100, self._setup_win32)
        else:
            # Embedded frame - placed in panel container by caller
            self._root = tk.Frame(parent, bg=self.BG_EMB)
            self._font_list = self._build_font_list(self._root)
            self._build_ui_embedded()

    # ── Font list ─────────────────────────────────────

    def _build_font_list(self, widget):
        """Build font list: popular 8 + separator + all system fonts."""
        try:
            all_fonts = sorted(set(tkfont.families(widget)),
                               key=lambda f: f.lower())
            all_fonts = [f for f in all_fonts if not f.startswith("@")]
        except Exception:
            all_fonts = []

        popular = [f for f in self.POPULAR_FONTS if f in all_fonts]
        remaining = [f for f in all_fonts if f not in popular]

        if remaining:
            return popular + [self.SEPARATOR] + remaining
        return popular

    # ── Standalone window setup ───────────────────────

    def _setup_window(self):
        self._root.overrideredirect(True)
        self._root.attributes('-topmost', True)
        self._root.configure(bg=self.BG)
        try:
            wx = self._app.winfo_x()
            wy = self._app.winfo_y() + self._app.winfo_height() + 5
        except tk.TclError:
            wx, wy = 100, 100
        self._root.geometry(f"+{wx}+{wy}")
        self._drag_data = {"x": 0, "y": 0}

    def _setup_win32(self):
        try:
            self._root.update_idletasks()
            hwnd = user32.GetParent(self._root.winfo_id())
            self._hwnd = hwnd
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style |= WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        except (OSError, ctypes.ArgumentError):
            pass

    # ── Standalone UI (single row - original layout) ──

    def _build_ui_standalone(self):
        main = tk.Frame(self._root, bg=self.BG, padx=4, pady=3)
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
                zoom_frame, text=tr("tb_zoom", z=100), bg=self.BG, fg="#CCC",
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
            thick_frame, text=tr("tb_thickness_pen"), bg=self.BG, fg="#CCC",
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

    # ── Embedded UI (3 rows - compact panel) ─────────

    # Background colors for embedded panel - match main widget gradient
    BG_EMB = "#302D5E"        # Matches toolbar gradient middle
    BG_EMB_ACTIVE = "#4A4680"
    BG_EMB_HOVER = "#3D3970"

    def _build_ui_embedded(self):
        """Professional 2-row compact layout for main voice widget panel.
        Row 1: Drawing tools | Text tools | Font | Close
        Row 2: Colors | Pen slider | Font slider | Actions"""
        bg = self.BG_EMB
        sep_clr = "#4A4680"

        main = tk.Frame(self._root, bg=bg, padx=6, pady=4)
        main.pack(fill="both", expand=True)
        self._emb_main = main
        self._bind_drag(main)

        # Shared button config
        _bcfg = dict(fg="#E0E0E0", relief="flat", bd=0, padx=4, pady=2)

        # ══════════════════════════════════════════════════
        # ROW 1: [Pen Highlight Eraser] | [Text Handwrite] | [Font ▼] | [✖]
        # ══════════════════════════════════════════════════
        row1 = tk.Frame(main, bg=bg)
        row1.pack(fill="x", pady=(0, 3))
        self._bind_drag(row1)

        # - Drawing tools group -
        self._btn_pen = tk.Button(
            row1, text=self.ICON_MOUSE, bg=self.BG_EMB_ACTIVE,
            font=("Segoe UI Emoji", 12), activebackground=self.BG_EMB_HOVER,
            command=lambda: self._toggle_tool("pen"), **_bcfg)
        self._btn_pen.pack(side="left", padx=(0, 2))

        self._btn_highlight = tk.Button(
            row1, text=self.ICON_HIGHLIGHTER, bg=bg,
            font=("Segoe UI Emoji", 12), activebackground=self.BG_EMB_HOVER,
            command=lambda: self._toggle_tool("highlighter"), **_bcfg)
        self._btn_highlight.pack(side="left", padx=2)

        self._btn_eraser = tk.Button(
            row1, text=self.ICON_ERASER, bg=bg,
            font=("Segoe UI Emoji", 12), activebackground=self.BG_EMB_HOVER,
            command=lambda: self._activate_eraser(), **_bcfg)
        self._btn_eraser.pack(side="left", padx=2)

        # Separator
        tk.Frame(row1, bg=sep_clr, width=1).pack(
            side="left", fill="y", padx=5, pady=3)

        # - Text tools group -
        self._btn_text = tk.Button(
            row1, text=self.ICON_TEXT, bg=bg,
            font=("Segoe UI", 12, "bold"), activebackground=self.BG_EMB_HOVER,
            command=lambda: self._toggle_tool("text"), **_bcfg)
        self._btn_text.pack(side="left", padx=2)

        self._btn_handwrite = tk.Button(
            row1, text=self.ICON_HANDWRITE, bg=bg,
            font=("Segoe UI Emoji", 12), activebackground=self.BG_EMB_HOVER,
            command=lambda: self._toggle_tool("handwrite"), **_bcfg)
        self._btn_handwrite.pack(side="left", padx=2)

        self._btn_hand = None  # No pan in embedded mode

        # Separator
        tk.Frame(row1, bg=sep_clr, width=1).pack(
            side="left", fill="y", padx=5, pady=3)

        # - Font dropdown -
        self._font_var = tk.StringVar(
            value=self._font_list[0] if self._font_list else "Segoe UI")
        self._font_menu = tk.OptionMenu(
            row1, self._font_var, *self._font_list,
            command=self._on_font_change)
        self._font_menu.configure(
            bg="#1E1C3A", fg="#DDD", font=("Segoe UI", 9),
            highlightthickness=0, bd=1, relief="solid",
            activebackground=self.BG_EMB_HOVER, activeforeground="#FFF",
            width=9, anchor="w")
        self._font_menu["menu"].configure(
            bg="#1E1C3A", fg="#DDD", font=("Segoe UI", 9),
            activebackground=self.BG_EMB_ACTIVE, activeforeground="#FFF")
        self._font_menu.pack(side="left", padx=4)

        # - Close button (right-aligned, accent) -
        tk.Button(
            row1, text="\u2716", bg="#5A2030", fg="#FFF",
            font=("Segoe UI", 11, "bold"), relief="flat", bd=0,
            padx=6, pady=2, activebackground="#8A3050",
            command=self._on_retract
        ).pack(side="right", padx=(2, 0))

        # - Editor button (right-aligned, before close) -
        if getattr(self._overlay, '_supports_view_mode', True):
            tk.Button(
                row1, text="\U0001f4c4", bg=bg, fg="#E0E0E0",
                font=("Segoe UI Emoji", 11), relief="flat", bd=0,
                padx=4, pady=2, activebackground=self.BG_EMB_HOVER,
                command=self._open_editor
            ).pack(side="right", padx=2)

        # ══════════════════════════════════════════════════
        # ROW 2: [■■■■■■] | [✏ ═══] | [T ═══] | [↩ ↪ 🗑]
        # ══════════════════════════════════════════════════
        row2 = tk.Frame(main, bg=bg)
        row2.pack(fill="x")
        self._bind_drag(row2)

        # - Color swatches -
        self._color_btns = {}
        for hex_color, name in self.PEN_COLORS:
            btn = tk.Button(
                row2, bg=hex_color, width=2, relief="groove", bd=1,
                activebackground=hex_color,
                command=lambda c=hex_color: self._set_color(c))
            btn.pack(side="left", padx=1, pady=1)
            self._color_btns[hex_color] = btn
            if hex_color == "#FF0000":
                btn.configure(relief="solid", bd=2)
                self._active_color_btn = btn

        # Separator
        tk.Frame(row2, bg=sep_clr, width=1).pack(
            side="left", fill="y", padx=5, pady=3)

        # - Pen thickness slider -
        tk.Label(row2, text="\u270f", bg=bg, fg="#AAA",
                 font=("Segoe UI Emoji", 9)).pack(side="left")
        self._thickness_var = tk.IntVar(value=4)
        self._slider = tk.Scale(
            row2, from_=1, to=100, orient="horizontal",
            variable=self._thickness_var, length=55, sliderlength=12,
            showvalue=False, bg=bg, fg="#DDD", troughcolor="#1E1C3A",
            highlightthickness=0, bd=0,
            activebackground=self.BG_EMB_ACTIVE,
            command=self._on_thickness_change)
        self._slider.pack(side="left", padx=(2, 0))
        self._pen_val_lbl = tk.Label(
            row2, text="4", bg=bg, fg="#AAA",
            font=("Segoe UI", 8), width=3, anchor="w")
        self._pen_val_lbl.pack(side="left")

        # Separator
        tk.Frame(row2, bg=sep_clr, width=1).pack(
            side="left", fill="y", padx=5, pady=3)

        # - Font size slider -
        tk.Label(row2, text="T", bg=bg, fg="#AAA",
                 font=("Segoe UI", 9, "bold")).pack(side="left")
        self._font_size_var = tk.IntVar(value=16)
        self._font_slider = tk.Scale(
            row2, from_=8, to=72, orient="horizontal",
            variable=self._font_size_var, length=55, sliderlength=12,
            showvalue=False, bg=bg, fg="#DDD", troughcolor="#1E1C3A",
            highlightthickness=0, bd=0,
            activebackground=self.BG_EMB_ACTIVE,
            command=self._on_font_size_change)
        self._font_slider.pack(side="left", padx=(2, 0))
        self._font_val_lbl = tk.Label(
            row2, text="16", bg=bg, fg="#AAA",
            font=("Segoe UI", 8), width=3, anchor="w")
        self._font_val_lbl.pack(side="left")

        # - Actions (right-aligned) -
        act_f = tk.Frame(row2, bg=bg)
        act_f.pack(side="right", padx=(4, 0))
        for icon, cmd in [("\u21a9", self._undo), ("\u21aa", self._redo),
                          ("\U0001f5d1", self._clear)]:
            tk.Button(
                act_f, text=icon, bg=bg, fg="#CCC",
                font=("Segoe UI", 11), relief="flat", bd=0,
                padx=3, activebackground=self.BG_EMB_HOVER,
                command=cmd).pack(side="left", padx=1)

    def _bind_drag(self, widget):
        """Bind drag events on a widget to forward to main app.
        Only applies for main widget embedded mode (not editor)."""
        if not hasattr(self._app, 'on_press'):
            return  # Skip drag binding in editor context
        widget.bind("<ButtonPress-1>", self._app_drag_start)
        widget.bind("<B1-Motion>", self._app_drag_move)
        widget.bind("<ButtonRelease-1>", self._app_drag_release)

    def _action_btn_emb(self, parent, text, command):
        """Action button for embedded panel."""
        bg = self.BG_EMB
        tk.Button(
            parent, text=text, bg=bg, fg="#DDD",
            font=("Segoe UI", 10), relief="flat", bd=0,
            activebackground=self.BG_EMB_HOVER, command=command
        ).pack(side="left", padx=1)

    # ── Common helpers ────────────────────────────────

    def _action_btn(self, parent, text, command, font_size=11):
        tk.Button(
            parent, text=text, bg=self.BG, fg="#CCC",
            font=("Segoe UI", font_size), relief="flat", bd=0,
            activebackground=self.BG_HOVER, command=command
        ).pack(side="left", padx=1)

    def get_root_widget(self):
        """Return actual widget - Toplevel (standalone) or Frame (embedded)."""
        return self._root

    @staticmethod
    def calc_panel_width(btn_s):
        """Calculate embedded panel width for a given button size."""
        scale = btn_s / 72.0
        return max(360, int(450 * scale))

    # ── Delegation (winfo_exists, destroy, etc.) ──────

    def winfo_exists(self):
        try:
            return self._root.winfo_exists()
        except Exception:
            return False

    def destroy(self):
        try:
            self._root.destroy()
        except Exception:
            pass

    def lift(self):
        if self._mode == "standalone":
            try:
                self._root.lift()
            except Exception:
                pass

    def attributes(self, *args, **kwargs):
        if self._mode == "standalone":
            return self._root.attributes(*args, **kwargs)

    # ── Tool Toggle ───────────────────────────────────

    def _toggle_tool(self, tool):
        if tool == "pan":
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

        # Swap slider between pen thickness ↔ font size (standalone only)
        # Embedded mode has both sliders always visible - no swapping needed
        if self._mode != "embedded":
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
                self._slider_label.configure(text=tr("tb_thickness_font"))
            elif leaving_font:
                saved = getattr(self, '_saved_pen_thickness', 4)
                self._thickness_var.set(saved)
                self._overlay.set_width(saved)
                self._slider_label.configure(text=tr("tb_thickness_pen"))

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
        # Use appropriate colors for embedded vs standalone
        if self._mode == "embedded":
            bg_on, bg_off = self.BG_EMB_ACTIVE, self.BG_EMB
            fsz = 10
        else:
            bg_on, bg_off = self.BG_ACTIVE, self.BG
            fsz = 11

        if self._draw_mode or is_select:
            active = self._active_tool
            pen_icon = self.ICON_MOUSE if active in ("pen", "select") else self.ICON_PEN
            hl_icon = self.ICON_MOUSE if active == "highlighter" else self.ICON_HIGHLIGHTER
            er_icon = self.ICON_MOUSE if active == "eraser" else self.ICON_ERASER
            self._btn_pen.configure(text=pen_icon,
                bg=bg_on if active in ("pen", "select") else bg_off)
            self._btn_highlight.configure(text=hl_icon,
                bg=bg_on if active == "highlighter" else bg_off)
            self._btn_eraser.configure(text=er_icon,
                bg=bg_on if active == "eraser" else bg_off)
            txt_icon = self.ICON_MOUSE if active == "text" else self.ICON_TEXT
            txt_font = ("Segoe UI Emoji", fsz) if active == "text" else ("Segoe UI", fsz, "bold")
            self._btn_text.configure(text=txt_icon, font=txt_font,
                bg=bg_on if active == "text" else bg_off)
            hw_icon = self.ICON_MOUSE if active == "handwrite" else self.ICON_HANDWRITE
            self._btn_handwrite.configure(text=hw_icon,
                font=("Segoe UI Emoji", fsz),
                bg=bg_on if active == "handwrite" else bg_off)
            if self._btn_hand:
                self._btn_hand.configure(
                    bg=bg_on if active == "pan" else bg_off)
        else:
            self._btn_pen.configure(text=self.ICON_PEN, bg=bg_off)
            self._btn_highlight.configure(text=self.ICON_HIGHLIGHTER, bg=bg_off)
            self._btn_eraser.configure(text=self.ICON_ERASER, bg=bg_off)
            self._btn_text.configure(text=self.ICON_TEXT,
                font=("Segoe UI", fsz, "bold"), bg=bg_off)
            self._btn_handwrite.configure(text=self.ICON_HANDWRITE, bg=bg_off)
            if self._btn_hand:
                self._btn_hand.configure(bg=bg_off)

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
        if font_name == self.SEPARATOR:
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
        if self._active_tool != "text":
            self._active_tool = "pen"
            self._overlay.set_tool("pen")
        self._enter_draw_mode()

    def _on_thickness_change(self, value):
        val = int(value)
        if hasattr(self, '_pen_val_lbl'):
            self._pen_val_lbl.configure(text=str(val))
        if self._active_tool == "handwrite":
            engine = getattr(self._overlay, '_engine', None)
            hw_font = getattr(engine, '_hw_font', "Segoe UI") if engine else "Segoe UI"
            if hasattr(self._overlay, 'set_hw_font'):
                self._overlay.set_hw_font(hw_font, val)
            elif engine:
                engine.set_hw_font(hw_font, val)
        elif self._active_tool == "text":
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

    def _on_font_size_change(self, value):
        """Handle font size slider change (embedded mode - always visible)."""
        val = int(value)
        if hasattr(self, '_font_val_lbl'):
            self._font_val_lbl.configure(text=str(val))
        if self._active_tool == "handwrite":
            engine = getattr(self._overlay, '_engine', None)
            hw_font = getattr(engine, '_hw_font', "Segoe UI") if engine else "Segoe UI"
            if hasattr(self._overlay, 'set_hw_font'):
                self._overlay.set_hw_font(hw_font, val)
            elif engine:
                engine.set_hw_font(hw_font, val)
        elif self._active_tool == "text":
            if hasattr(self._overlay, 'set_text_font_size'):
                self._overlay.set_text_font_size(val)
            else:
                engine = getattr(self._overlay, '_engine', None)
                if engine:
                    engine._text_font_size = val
                    if engine._text_active:
                        engine._update_text_display()

    def _undo(self):
        self._overlay.undo()

    def _redo(self):
        self._overlay.redo()

    def _clear(self):
        self._overlay.clear_all()

    def _close_pen(self):
        self._overlay.close()

    def _on_retract(self):
        """Embedded mode: trigger retract animation via callback."""
        if self._on_retract_cb:
            self._on_retract_cb()
        else:
            self._close_pen()

    def _on_zoom_change(self, value):
        level = int(value)
        if hasattr(self, '_zoom_label'):
            self._zoom_label.configure(text=tr("tb_zoom", z=level))
        if hasattr(self._overlay, 'set_zoom'):
            self._overlay.set_zoom(level / 100.0)

    def _toggle_fullscreen(self):
        if hasattr(self._overlay, '_toggle_fullscreen'):
            self._overlay._toggle_fullscreen()

    def _open_editor(self):
        if hasattr(self._app, 'open_editor_window'):
            # Delay to let button callback finish before toolbar is destroyed
            self._app.after(50, self._app.open_editor_window)

    # ── Drag (standalone mode) ────────────────────────

    def _drag_start(self, event):
        self._drag_data["x"] = event.x_root - self._root.winfo_x()
        self._drag_data["y"] = event.y_root - self._root.winfo_y()

    def _drag_move(self, event):
        x = event.x_root - self._drag_data["x"]
        y = event.y_root - self._drag_data["y"]
        self._root.geometry(f"+{x}+{y}")

    # ── Drag forwarding (embedded mode) ───────────────

    def _app_drag_start(self, event):
        """Forward drag to main app widget."""
        if self._app and hasattr(self._app, 'on_press'):
            self._app.on_press(event)

    def _app_drag_move(self, event):
        if self._app and hasattr(self._app, 'on_drag'):
            self._app.on_drag(event)

    def _app_drag_release(self, event):
        if self._app and hasattr(self._app, '_on_bg_release'):
            self._app._on_bg_release(event)

    # ── HWND ──────────────────────────────────────────

    def get_hwnd(self):
        return self._hwnd
