# ui_components/pen_toolbar.py
"""PenToolbar - Dual-mode toolbar for pen/annotation tool controls.
  - mode="standalone": Floating Toplevel window (used by EditorWindow)
  - mode="embedded":   tk.Frame embedded in main widget canvas (slide-out panel)
Pen/highlighter buttons toggle between draw mode (shows cursor) and view mode.
Thickness controlled by slider (1-100px)."""

import tkinter as tk
import tkinter.font as tkfont
import ctypes
import customtkinter as ctk
from i18n import tr

# Modern slider/dropdown look (gold thumb on subtle dark track)
_SLIDER_TRACK   = "#1E1C3A"   # unfilled portion of track
_SLIDER_FILL    = "#4A4680"   # filled portion (left of thumb)
_SLIDER_THUMB   = "#E5B453"   # gold thumb
_SLIDER_HOVER   = "#FFD27D"

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
                 on_retract=None, scale=1.0):
        self._mode = mode
        self._overlay = overlay
        self._app = app_ref
        self._active_tool = "pen"
        self._draw_mode = True
        self._active_color_btn = None
        self._on_retract_cb = on_retract
        self._hwnd = None
        self._emb_scale = max(0.6, min(1.6, float(scale)))
        # Tracks widgets whose font/width/height/pack-padding must rescale
        # when set_scale() is called. Format: list of (widget, kind, **kwargs)
        # where kind ∈ {"btn_icon","btn_text","btn_label","slider","combo",
        #               "color","label_small","sep"}.
        self._scaled_widgets = []

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

    @staticmethod
    def _emb_metrics(scale):
        """Single source of truth for all scale-derived sizes in embedded mode.
        At scale=1.0 (medium widget, btn_s=72) this matches the previous compact
        layout. At smaller scale every dimension shrinks proportionally with
        sane minimums so nothing collapses; at larger scale it grows."""
        s = max(0.65, min(1.6, scale))
        return dict(
            scale=s,
            # Outer padding inside the toolbar background
            main_padx=max(3, int(6 * s)),
            main_pady=max(2, int(4 * s)),
            # Inter-row gap
            row_gap=max(2, int(3 * s)),
            # Tool icon buttons (pen / highlighter / eraser / text / handwrite)
            icon_fz=max(9, int(12 * s)),
            text_fz=max(9, int(12 * s)),
            btn_padx=max(1, int(2 * s)),
            btn_pady=max(0, int(1 * s)),
            pack_padx=max(1, int(2 * s)),
            # Separators
            sep_padx=max(2, int(3 * s)),
            sep_pady=max(1, int(3 * s)),
            # Font dropdown (CTkComboBox)
            cb_w=max(72, int(96 * s)),
            cb_h=max(18, int(22 * s)),
            cb_fz=max(8, int(9 * s)),
            cb_drop_fz=max(9, int(10 * s)),
            # Sliders (CTkSlider)
            sl_w=max(40, int(54 * s)),
            sl_h=max(10, int(12 * s)),
            sl_pack_lpad=max(2, int(3 * s)),
            sl_pack_rpad=max(1, int(1 * s)),
            sl_pack_pady=max(1, int(2 * s)),
            # Slider unit labels (✏ / T)
            sl_lbl_fz=max(8, int(9 * s)),
            sl_val_fz=max(7, int(8 * s)),
            sl_val_w=max(2, int(3 * s)),
            # Color swatches
            color_w=max(1, int(2 * s)),
            color_h=1,
            color_padx=0,
            # Action buttons (undo / redo / clear)
            act_fz=max(9, int(10 * s)),
            act_padx=max(1, int(1 * s)),
            # Right-aligned editor + close buttons
            close_fz=max(9, int(10 * s)),
            close_padx=max(2, int(4 * s)),
            close_pady=max(0, int(1 * s)),
            edit_fz=max(9, int(10 * s)),
            edit_padx=max(1, int(2 * s)),
            edit_pady=max(0, int(1 * s)),
            edit_pack_padx=max(1, int(1 * s)),
            close_pack_padx=max(1, int(2 * s)),
        )

    def _track(self, widget, kind, **kwargs):
        """Register a widget for live rescaling via set_scale().
        kwargs may carry 'side' so pack_configure preserves alignment."""
        self._scaled_widgets.append((widget, kind, kwargs))

    def _build_ui_embedded(self):
        """Professional 2-row compact layout for main voice widget panel.
        All sizes derive from self._emb_scale via _emb_metrics() so the toolbar
        rescales in lock-step with the main widget's size preset.
        Row 1: Drawing tools | Text tools | Font | (Editor + Close right)
        Row 2: Colors | Pen slider | Font slider | Actions"""
        bg = self.BG_EMB
        sep_clr = "#4A4680"
        m = self._emb_metrics(self._emb_scale)

        # The main frame is the *visual background* — it acts as the "anchor at
        # left-middle" parent the user described. All toolbar widgets live
        # inside it, so when set_scale() resizes them the perceived effect is
        # the background scaling its children together.
        main = tk.Frame(self._root, bg=bg, padx=m["main_padx"],
                        pady=m["main_pady"])
        main.pack(fill="both", expand=True)
        self._emb_main = main
        self._bind_drag(main)

        # Shared button config (no padx/pady here — those come from metrics)
        def _bcfg():
            return dict(fg="#E0E0E0", relief="flat", bd=0,
                        padx=m["btn_padx"], pady=m["btn_pady"])

        # ══════════════════════════════════════════════════
        # ROW 1: [Pen Highlight Eraser] | [Text Handwrite] | [Font ▼] | [✖]
        # ══════════════════════════════════════════════════
        row1 = tk.Frame(main, bg=bg)
        row1.pack(fill="x", pady=(0, m["row_gap"]))
        self._row1 = row1
        self._bind_drag(row1)

        # - Drawing tools group -
        self._btn_pen = tk.Button(
            row1, text=self.ICON_MOUSE, bg=self.BG_EMB_ACTIVE,
            font=("Segoe UI Emoji", m["icon_fz"]),
            activebackground=self.BG_EMB_HOVER,
            command=lambda: self._toggle_tool("pen"), **_bcfg())
        self._btn_pen.pack(side="left", padx=(0, m["pack_padx"]))
        self._track(self._btn_pen, "icon_first", side="left",
                    padx=(0, m["pack_padx"]))

        self._btn_highlight = tk.Button(
            row1, text=self.ICON_HIGHLIGHTER, bg=bg,
            font=("Segoe UI Emoji", m["icon_fz"]),
            activebackground=self.BG_EMB_HOVER,
            command=lambda: self._toggle_tool("highlighter"), **_bcfg())
        self._btn_highlight.pack(side="left", padx=m["pack_padx"])
        self._track(self._btn_highlight, "icon", side="left",
                    padx=m["pack_padx"])

        self._btn_eraser = tk.Button(
            row1, text=self.ICON_ERASER, bg=bg,
            font=("Segoe UI Emoji", m["icon_fz"]),
            activebackground=self.BG_EMB_HOVER,
            command=lambda: self._activate_eraser(), **_bcfg())
        self._btn_eraser.pack(side="left", padx=m["pack_padx"])
        self._track(self._btn_eraser, "icon", side="left",
                    padx=m["pack_padx"])

        # Separator
        sep1 = tk.Frame(row1, bg=sep_clr, width=1)
        sep1.pack(side="left", fill="y", padx=m["sep_padx"],
                  pady=m["sep_pady"])
        self._track(sep1, "sep", side="left", fill="y",
                    padx=m["sep_padx"], pady=m["sep_pady"])

        # - Text tools group -
        self._btn_text = tk.Button(
            row1, text=self.ICON_TEXT, bg=bg,
            font=("Segoe UI", m["text_fz"], "bold"),
            activebackground=self.BG_EMB_HOVER,
            command=lambda: self._toggle_tool("text"), **_bcfg())
        self._btn_text.pack(side="left", padx=m["pack_padx"])
        self._track(self._btn_text, "text", side="left",
                    padx=m["pack_padx"])

        self._btn_handwrite = tk.Button(
            row1, text=self.ICON_HANDWRITE, bg=bg,
            font=("Segoe UI Emoji", m["icon_fz"]),
            activebackground=self.BG_EMB_HOVER,
            command=lambda: self._toggle_tool("handwrite"), **_bcfg())
        self._btn_handwrite.pack(side="left", padx=m["pack_padx"])
        self._track(self._btn_handwrite, "icon", side="left",
                    padx=m["pack_padx"])

        self._btn_hand = None  # No pan in embedded mode

        # Separator
        sep2 = tk.Frame(row1, bg=sep_clr, width=1)
        sep2.pack(side="left", fill="y", padx=m["sep_padx"],
                  pady=m["sep_pady"])
        self._track(sep2, "sep", side="left", fill="y",
                    padx=m["sep_padx"], pady=m["sep_pady"])

        # - Font dropdown (modern: anchored popup with built-in scrollbar) -
        self._font_var = tk.StringVar(
            value=self._font_list[0] if self._font_list else "Segoe UI")
        self._font_menu = ctk.CTkComboBox(
            row1, values=self._font_list, variable=self._font_var,
            command=self._on_font_change,
            width=m["cb_w"], height=m["cb_h"],
            font=("Segoe UI", m["cb_fz"]),
            dropdown_font=("Segoe UI", m["cb_drop_fz"]),
            fg_color="#1E1C3A", border_color=self.BG_EMB_ACTIVE,
            border_width=1,
            button_color=self.BG_EMB_ACTIVE,
            button_hover_color=self.BG_EMB_HOVER,
            text_color="#DDD",
            dropdown_fg_color="#1E1C3A",
            dropdown_text_color="#DDD",
            dropdown_hover_color=self.BG_EMB_ACTIVE,
            state="readonly")
        self._font_menu.pack(side="left", padx=m["pack_padx"], pady=1)
        self._track(self._font_menu, "combo", side="left",
                    padx=m["pack_padx"], pady=1)

        # - Close button (right-aligned, accent) -
        self._btn_close = tk.Button(
            row1, text="\u2716", bg="#5A2030", fg="#FFF",
            font=("Segoe UI", m["close_fz"], "bold"), relief="flat", bd=0,
            padx=m["close_padx"], pady=m["close_pady"],
            activebackground="#8A3050",
            command=self._on_retract)
        self._btn_close.pack(side="right", padx=(m["close_pack_padx"], 0))
        self._track(self._btn_close, "close", side="right",
                    padx=(m["close_pack_padx"], 0))

        # - Editor button (right-aligned, before close) -
        self._btn_editor = None
        if getattr(self._overlay, '_supports_view_mode', True):
            self._btn_editor = tk.Button(
                row1, text="\U0001f4c4", bg=bg, fg="#E0E0E0",
                font=("Segoe UI Emoji", m["edit_fz"]), relief="flat", bd=0,
                padx=m["edit_padx"], pady=m["edit_pady"],
                activebackground=self.BG_EMB_HOVER,
                command=self._open_editor)
            self._btn_editor.pack(side="right", padx=m["edit_pack_padx"])
            self._track(self._btn_editor, "edit", side="right",
                        padx=m["edit_pack_padx"])

        # ══════════════════════════════════════════════════
        # ROW 2: [■■■■■■] | [✏ ═══] | [T ═══] | [↩ ↪ 🗑]
        # ══════════════════════════════════════════════════
        row2 = tk.Frame(main, bg=bg)
        row2.pack(fill="x")
        self._row2 = row2
        self._bind_drag(row2)

        # - Color swatches -
        self._color_btns = {}
        for hex_color, name in self.PEN_COLORS:
            btn = tk.Button(
                row2, bg=hex_color, width=m["color_w"], height=m["color_h"],
                relief="groove", bd=1,
                activebackground=hex_color,
                command=lambda c=hex_color: self._set_color(c))
            btn.pack(side="left", padx=m["color_padx"], pady=1)
            self._color_btns[hex_color] = btn
            self._track(btn, "color", side="left",
                        padx=m["color_padx"], pady=1)
            if hex_color == "#FF0000":
                btn.configure(relief="solid", bd=2)
                self._active_color_btn = btn

        # Separator
        sep3 = tk.Frame(row2, bg=sep_clr, width=1)
        sep3.pack(side="left", fill="y", padx=m["sep_padx"],
                  pady=m["sep_pady"])
        self._track(sep3, "sep", side="left", fill="y",
                    padx=m["sep_padx"], pady=m["sep_pady"])

        # - Pen thickness slider (modern: thin track + gold thumb) -
        self._lbl_pen_unit = tk.Label(
            row2, text="\u270f", bg=bg, fg="#AAA",
            font=("Segoe UI Emoji", m["sl_lbl_fz"]))
        self._lbl_pen_unit.pack(side="left")
        self._track(self._lbl_pen_unit, "sl_lbl", side="left")

        self._thickness_var = tk.IntVar(value=4)
        self._slider = ctk.CTkSlider(
            row2, from_=1, to=100, number_of_steps=99,
            variable=self._thickness_var,
            width=m["sl_w"], height=m["sl_h"],
            fg_color=_SLIDER_TRACK, progress_color=_SLIDER_FILL,
            button_color=_SLIDER_THUMB, button_hover_color=_SLIDER_HOVER,
            command=self._on_thickness_change)
        self._slider.pack(side="left",
                          padx=(m["sl_pack_lpad"], m["sl_pack_rpad"]),
                          pady=m["sl_pack_pady"])
        self._track(self._slider, "slider", side="left",
                    padx=(m["sl_pack_lpad"], m["sl_pack_rpad"]),
                    pady=m["sl_pack_pady"])
        self._pen_val_lbl = tk.Label(
            row2, text="4", bg=bg, fg="#AAA",
            font=("Segoe UI", m["sl_val_fz"]),
            width=m["sl_val_w"], anchor="w")
        self._pen_val_lbl.pack(side="left")
        self._track(self._pen_val_lbl, "sl_val", side="left")

        # Separator
        sep4 = tk.Frame(row2, bg=sep_clr, width=1)
        sep4.pack(side="left", fill="y", padx=m["sep_padx"],
                  pady=m["sep_pady"])
        self._track(sep4, "sep", side="left", fill="y",
                    padx=m["sep_padx"], pady=m["sep_pady"])

        # - Font size slider (modern: thin track + gold thumb) -
        self._lbl_font_unit = tk.Label(
            row2, text="T", bg=bg, fg="#AAA",
            font=("Segoe UI", m["sl_lbl_fz"], "bold"))
        self._lbl_font_unit.pack(side="left")
        self._track(self._lbl_font_unit, "sl_lbl_b", side="left")

        self._font_size_var = tk.IntVar(value=16)
        self._font_slider = ctk.CTkSlider(
            row2, from_=8, to=72, number_of_steps=64,
            variable=self._font_size_var,
            width=m["sl_w"], height=m["sl_h"],
            fg_color=_SLIDER_TRACK, progress_color=_SLIDER_FILL,
            button_color=_SLIDER_THUMB, button_hover_color=_SLIDER_HOVER,
            command=self._on_font_size_change)
        self._font_slider.pack(side="left",
                               padx=(m["sl_pack_lpad"], m["sl_pack_rpad"]),
                               pady=m["sl_pack_pady"])
        self._track(self._font_slider, "slider", side="left",
                    padx=(m["sl_pack_lpad"], m["sl_pack_rpad"]),
                    pady=m["sl_pack_pady"])
        self._font_val_lbl = tk.Label(
            row2, text="16", bg=bg, fg="#AAA",
            font=("Segoe UI", m["sl_val_fz"]),
            width=m["sl_val_w"], anchor="w")
        self._font_val_lbl.pack(side="left")
        self._track(self._font_val_lbl, "sl_val", side="left")

        # - Actions (right-aligned) -
        act_f = tk.Frame(row2, bg=bg)
        act_f.pack(side="right", padx=(m["act_padx"] + 1, 0))
        self._act_frame = act_f
        self._action_btns = []
        for icon, cmd in [("\u21a9", self._undo), ("\u21aa", self._redo),
                          ("\U0001f5d1", self._clear)]:
            b = tk.Button(
                act_f, text=icon, bg=bg, fg="#CCC",
                font=("Segoe UI", m["act_fz"]), relief="flat", bd=0,
                padx=m["act_padx"], pady=0,
                activebackground=self.BG_EMB_HOVER, command=cmd)
            b.pack(side="left", padx=0)
            self._action_btns.append(b)
            self._track(b, "act", side="left", padx=0)

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
        """Embedded panel width. Now that the embedded toolbar shrinks its
        contents proportionally with btn_s (via set_scale), the panel itself
        can shrink with it too. Floor at 360px so even at 'tiny' (btn_s=48)
        every tool still fits; medium scales to ~450, xlarge to ~600."""
        scale = btn_s / 72.0
        return max(360, int(450 * scale))

    def set_scale(self, scale):
        """Rescale the embedded toolbar in lock-step with the main widget's
        size preset. Caller passes scale = btn_s / 72.0 (1.0 at medium).

        Updates fonts, slider/dropdown dimensions, button widths and pack
        paddings on every tracked widget. The visual effect is the toolbar
        background and its child tools growing/shrinking together — the
        'parent-anchor at left-middle' behaviour the user asked for."""
        if self._mode != "embedded":
            return
        new_scale = max(0.65, min(1.6, float(scale)))
        if abs(new_scale - self._emb_scale) < 0.02:
            return  # No meaningful change
        self._emb_scale = new_scale
        m = self._emb_metrics(new_scale)

        # Outer padding inside the toolbar background frame
        try:
            self._emb_main.configure(padx=m["main_padx"], pady=m["main_pady"])
        except Exception:
            pass
        # Inter-row gap
        try:
            self._row1.pack_configure(pady=(0, m["row_gap"]))
        except Exception:
            pass

        # Per-widget reconfiguration
        for widget, kind, _kwargs in self._scaled_widgets:
            try:
                if not widget.winfo_exists():
                    continue
            except Exception:
                continue
            try:
                if kind in ("icon", "icon_first"):
                    widget.configure(font=("Segoe UI Emoji", m["icon_fz"]),
                                     padx=m["btn_padx"], pady=m["btn_pady"])
                elif kind == "text":
                    widget.configure(
                        font=("Segoe UI", m["text_fz"], "bold"),
                        padx=m["btn_padx"], pady=m["btn_pady"])
                elif kind == "sep":
                    widget.pack_configure(padx=m["sep_padx"],
                                          pady=m["sep_pady"])
                elif kind == "combo":
                    widget.configure(
                        width=m["cb_w"], height=m["cb_h"],
                        font=("Segoe UI", m["cb_fz"]),
                        dropdown_font=("Segoe UI", m["cb_drop_fz"]))
                elif kind == "slider":
                    widget.configure(width=m["sl_w"], height=m["sl_h"])
                elif kind == "sl_lbl":
                    widget.configure(
                        font=("Segoe UI Emoji", m["sl_lbl_fz"]))
                elif kind == "sl_lbl_b":
                    widget.configure(
                        font=("Segoe UI", m["sl_lbl_fz"], "bold"))
                elif kind == "sl_val":
                    widget.configure(font=("Segoe UI", m["sl_val_fz"]),
                                     width=m["sl_val_w"])
                elif kind == "color":
                    widget.configure(width=m["color_w"], height=m["color_h"])
                elif kind == "act":
                    widget.configure(font=("Segoe UI", m["act_fz"]),
                                     padx=m["act_padx"], pady=0)
                elif kind == "close":
                    widget.configure(
                        font=("Segoe UI", m["close_fz"], "bold"),
                        padx=m["close_padx"], pady=m["close_pady"])
                    widget.pack_configure(
                        padx=(m["close_pack_padx"], 0))
                elif kind == "edit":
                    widget.configure(
                        font=("Segoe UI Emoji", m["edit_fz"]),
                        padx=m["edit_padx"], pady=m["edit_pady"])
                    widget.pack_configure(padx=m["edit_pack_padx"])
            except Exception:
                pass

        # Re-apply pack paddings on the icon/text/combo widgets too
        # (configure above only changes widget options, not pack opts)
        for widget, kind, kwargs in self._scaled_widgets:
            if kind == "icon_first":
                # First pen icon butts against left edge: padx=(0, gap)
                try:
                    widget.pack_configure(padx=(0, m["pack_padx"]))
                except Exception:
                    pass
            elif kind in ("icon", "text"):
                try:
                    widget.pack_configure(padx=m["pack_padx"])
                except Exception:
                    pass
            elif kind == "combo":
                try:
                    widget.pack_configure(padx=m["pack_padx"], pady=1)
                except Exception:
                    pass
            elif kind == "slider":
                try:
                    widget.pack_configure(
                        padx=(m["sl_pack_lpad"], m["sl_pack_rpad"]),
                        pady=m["sl_pack_pady"])
                except Exception:
                    pass
            elif kind == "color":
                try:
                    widget.pack_configure(padx=m["color_padx"], pady=1)
                except Exception:
                    pass

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
