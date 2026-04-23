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

# Dark 3D theme matching main widget's purple-navy gradient (TOOLBAR_BG=#302D5E).
# Pen toolbar sits beside the widget and needs visual continuity with it.
_SLIDER_TRACK   = "#1F1D45"   # unfilled track (dark, blends with bg)
_SLIDER_FILL    = "#7090FF"   # filled portion (cool blue accent)
_SLIDER_THUMB   = "#E5B453"   # gold thumb — premium touch on dark bg
_SLIDER_HOVER   = "#FFD27D"

user32 = ctypes.windll.user32
GWL_EXSTYLE     = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080


# Fixed font-size choices for the embedded font-size dropdown.
# Replaces the slider — user picks from common sizes which keeps the
# control compact and predictable.
FONT_SIZE_CHOICES = ["8", "12", "24", "32", "48", "60", "72",
                     "100", "150", "200", "300", "500"]


class _ScrollableFontPicker:
    """Custom font dropdown built from a Listbox + ttk.Scrollbar.

    Looks like a CTkComboBox but its popup shows exactly N rows at a time
    with a scrollbar on the right — works reliably even with 200+ system
    fonts (CTkComboBox/OptionMenu can't scroll long lists)."""

    SEPARATOR = tr("tb_separator")

    def __init__(self, parent, fonts, current, on_select, scale=1.0,
                 visible_rows=20, base_w=140, min_w=96):
        self.parent = parent
        self.fonts = list(fonts)
        self.on_select = on_select
        self.visible_rows = visible_rows
        self.popup = None
        self._var = tk.StringVar(value=current or (
            self.fonts[0] if self.fonts else "Segoe UI"))
        self._scale = max(0.65, min(1.6, float(scale)))
        # Width tuning — caller can override for narrow pickers (e.g. font
        # size, which only needs ~3 digits) vs wide ones (font names).
        self._base_w = max(40, int(base_w))
        self._min_w = max(28, int(min_w))

        # Light-theme picker palette
        bg = "#1E1E35"
        self._bg = bg
        self._border = "#4A4680"
        self._text = "#E8E8F5"
        self._hover = "#3F3C7A"
        self._sel = "#4D6AFF"

        self.frame = tk.Frame(parent, bg=bg, highlightbackground=self._border,
                              highlightthickness=1)
        self.label = tk.Label(self.frame, textvariable=self._var, bg=bg,
                              fg=self._text, anchor="w", padx=4)
        self.label.pack(side="left", fill="both", expand=True)
        self.arrow = tk.Label(self.frame, text="\u25be", bg=bg,
                              fg=self._text, padx=4)
        self.arrow.pack(side="right")
        for w in (self.frame, self.label, self.arrow):
            w.bind("<Button-1>", lambda _e: self.toggle())
        self.set_scale(self._scale)

    def _metrics(self):
        s = self._scale
        return dict(
            w=max(self._min_w, int(self._base_w * s)),
            h=max(18, int(22 * s)),
            fz=max(8, int(9 * s)),
            list_fz=max(9, int(10 * s)),
            row_h=max(16, int(20 * s)),
        )

    def set_scale(self, scale):
        self._scale = max(0.65, min(1.6, float(scale)))
        m = self._metrics()
        self.frame.configure(width=m["w"], height=m["h"])
        self.frame.pack_propagate(False)
        self.label.configure(font=("Segoe UI", m["fz"]))
        self.arrow.configure(font=("Segoe UI", m["fz"]))

    # — packing API to mimic a normal widget —
    def pack(self, **kwargs):
        self.frame.pack(**kwargs)

    def pack_configure(self, **kwargs):
        self.frame.pack_configure(**kwargs)

    def pack_forget(self):
        self.frame.pack_forget()

    def winfo_exists(self):
        try:
            return bool(self.frame.winfo_exists())
        except Exception:
            return False

    def get(self):
        return self._var.get()

    def set(self, value):
        self._var.set(value)

    # — popup —
    def toggle(self):
        if self.popup and self.popup.winfo_exists():
            self._close()
        else:
            self._open()

    def _open(self):
        self.frame.update_idletasks()
        # Remember whoever had focus before we steal it — so when the popup
        # closes we can hand keyboard focus back. This is what makes typing
        # in an active text-edit continue seamlessly after picking a size.
        try:
            self._prev_focus = self.parent.focus_get()
        except Exception:
            self._prev_focus = None
        x = self.frame.winfo_rootx()
        trig_top = self.frame.winfo_rooty()
        trig_bot = trig_top + self.frame.winfo_height()
        m = self._metrics()
        # Popup is at least its own metric width or the trigger width,
        # whichever is bigger — but never less than 60 so even the tiny
        # font-size picker popup is wide enough to read.
        w = max(60, m["w"], self.frame.winfo_width())
        rows = min(self.visible_rows, max(1, len(self.fonts)))
        h = m["row_h"] * rows + 4

        # Smart placement: pick the side (below / above) with more room.
        # If neither has full room, clamp to fit on whichever side is bigger.
        try:
            screen_h = self.frame.winfo_screenheight()
        except Exception:
            screen_h = 1080
        space_below = max(0, screen_h - trig_bot - 8)
        space_above = max(0, trig_top - 8)
        if space_below >= h:
            y = trig_bot
        elif space_above >= h:
            y = trig_top - h
        elif space_above > space_below:
            # Open above but shrink height to fit
            h = space_above
            y = trig_top - h
        else:
            h = space_below
            y = trig_bot
        # Clamp x onscreen too
        try:
            screen_w = self.frame.winfo_screenwidth()
            if x + w > screen_w - 4:
                x = max(0, screen_w - w - 4)
        except Exception:
            pass

        popup = tk.Toplevel(self.parent)
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        popup.geometry(f"{w}x{h}+{x}+{y}")
        popup.configure(bg=self._border)
        self.popup = popup

        inner = tk.Frame(popup, bg=self._bg)
        inner.pack(fill="both", expand=True, padx=1, pady=1)

        from tkinter import ttk
        sb = ttk.Scrollbar(inner, orient="vertical")
        sb.pack(side="right", fill="y")

        lb = tk.Listbox(inner, font=("Segoe UI", m["list_fz"]),
                        bg=self._bg, fg=self._text,
                        selectbackground=self._sel, selectforeground="#FFFFFF",
                        highlightthickness=0, bd=0, activestyle="none",
                        yscrollcommand=sb.set, exportselection=False)
        for f in self.fonts:
            lb.insert("end", f)
        lb.pack(side="left", fill="both", expand=True)
        sb.config(command=lb.yview)

        # Pre-select current font
        try:
            idx = self.fonts.index(self._var.get())
            lb.selection_set(idx)
            lb.activate(idx)
            lb.see(idx)
        except (ValueError, tk.TclError):
            pass

        def _commit(_event=None):
            sel = lb.curselection()
            if sel:
                font = self.fonts[sel[0]]
                if font and font != self.SEPARATOR:
                    self._var.set(font)
                    if self.on_select:
                        try:
                            self.on_select(font)
                        except Exception:
                            pass
            self._close()

        lb.bind("<<ListboxSelect>>", _commit)
        lb.bind("<Return>", _commit)
        lb.bind("<Escape>", lambda _e: self._close())
        popup.bind("<FocusOut>", lambda _e: self._close())
        popup.focus_force()
        lb.focus_set()

    def _close(self):
        if self.popup:
            try:
                self.popup.destroy()
            except Exception:
                pass
            self.popup = None
        # Restore keyboard focus to whoever had it before opening, so an
        # active text-edit keeps receiving keystrokes immediately. Deferred
        # via after_idle because the destroyed popup needs a tick before Tk
        # accepts focus elsewhere.
        prev = getattr(self, "_prev_focus", None)
        self._prev_focus = None

        def _restore():
            if prev is None:
                return
            try:
                if prev.winfo_exists():
                    prev.focus_set()
            except Exception:
                pass

        try:
            self.parent.after_idle(_restore)
        except Exception:
            _restore()


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

    # Dark 3D theme — standalone toolbar (matches main widget TOOLBAR_BG=#302D5E).
    # Keeping a consistent purple-navy aesthetic across widget + tool panel.
    BG = "#302D5E"
    BG_ACTIVE = "#4D6AFF"   # bright blue accent — high contrast on dark bg
    BG_HOVER = "#3F3C7A"    # slightly lighter than BG for hover lift

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
            tools_frame, text=self.ICON_MOUSE, bg=self.BG_ACTIVE, fg="#E8E8F5",
            font=("Segoe UI Emoji", 11), relief="flat", bd=0,
            activebackground=self.BG_HOVER,
            command=lambda: self._toggle_tool("pen")
        )
        self._btn_pen.pack(side="left", padx=1)

        self._btn_highlight = tk.Button(
            tools_frame, text=self.ICON_HIGHLIGHTER, bg=self.BG, fg="#E8E8F5",
            font=("Segoe UI Emoji", 11), relief="flat", bd=0,
            activebackground=self.BG_HOVER,
            command=lambda: self._toggle_tool("highlighter")
        )
        self._btn_highlight.pack(side="left", padx=1)

        self._btn_eraser = tk.Button(
            tools_frame, text=self.ICON_ERASER, bg=self.BG, fg="#E8E8F5",
            font=("Segoe UI Emoji", 11), relief="flat", bd=0,
            activebackground=self.BG_HOVER,
            command=lambda: self._activate_eraser()
        )
        self._btn_eraser.pack(side="left", padx=1)

        self._btn_text = tk.Button(
            tools_frame, text=self.ICON_TEXT, bg=self.BG, fg="#E8E8F5",
            font=("Segoe UI", 12, "bold"), relief="flat", bd=0,
            activebackground=self.BG_HOVER, width=2,
            command=lambda: self._toggle_tool("text")
        )
        self._btn_text.pack(side="left", padx=1)

        self._btn_handwrite = tk.Button(
            tools_frame, text=self.ICON_HANDWRITE, bg=self.BG, fg="#E8E8F5",
            font=("Segoe UI Emoji", 11), relief="flat", bd=0,
            activebackground=self.BG_HOVER,
            command=lambda: self._toggle_tool("handwrite")
        )
        self._btn_handwrite.pack(side="left", padx=1)

        # ── Hand + Zoom (editor mode only) ──
        self._btn_hand = None
        if not getattr(self._overlay, '_supports_view_mode', True):
            self._btn_hand = tk.Button(
                tools_frame, text=self.ICON_HAND, bg=self.BG, fg="#E8E8F5",
                font=("Segoe UI Emoji", 11), relief="flat", bd=0,
                activebackground=self.BG_HOVER,
                command=lambda: self._toggle_tool("pan")
            )
            self._btn_hand.pack(side="left", padx=1)

        # ── Zoom slider (editor mode only) ──
        if not getattr(self._overlay, '_supports_view_mode', True):
            tk.Frame(row, bg="#4A4680", width=1, height=22).pack(side="left", padx=3)
            zoom_frame = tk.Frame(row, bg=self.BG)
            zoom_frame.pack(side="left", padx=(0, 4))
            self._zoom_label = tk.Label(
                zoom_frame, text=tr("tb_zoom", z=100), bg=self.BG, fg="#E8E8F5",
                font=("Segoe UI", 8), width=8
            )
            self._zoom_label.pack(side="left")
            self._zoom_var = tk.IntVar(value=100)
            self._zoom_slider = tk.Scale(
                zoom_frame, from_=10, to=400, orient="horizontal",
                variable=self._zoom_var, length=80, sliderlength=12,
                showvalue=False, bg=self.BG, fg="#E8E8F5", troughcolor="#1F1D45",
                highlightthickness=0, bd=0, activebackground=self.BG_ACTIVE,
                font=("Segoe UI", 7), command=self._on_zoom_change
            )
            self._zoom_slider.pack(side="left", padx=2)

        # ── Separator ──
        tk.Frame(row, bg="#4A4680", width=1, height=22).pack(side="left", padx=3)

        # ── Font dropdown (for text tool) ──
        self._font_var = tk.StringVar(value=self._font_list[0] if self._font_list else "Segoe UI")
        self._font_menu = tk.OptionMenu(
            row, self._font_var, *self._font_list,
            command=self._on_font_change
        )
        self._font_menu.configure(
            bg=self.BG, fg="#E8E8F5", font=("Segoe UI", 9),
            highlightthickness=0, bd=0, relief="flat",
            activebackground=self.BG_HOVER, activeforeground="#FFFFFF",
            width=10
        )
        self._font_menu["menu"].configure(
            bg="#272550", fg="#E8E8F5", font=("Segoe UI", 9),
            activebackground=self.BG_ACTIVE, activeforeground="#FFFFFF"
        )
        self._font_menu.pack(side="left", padx=(0, 4))

        # ── Separator ──
        tk.Frame(row, bg="#4A4680", width=1, height=22).pack(side="left", padx=3)

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
        tk.Frame(row, bg="#4A4680", width=1, height=22).pack(side="left", padx=3)

        # ── Thickness / Font-size slider ──
        thick_frame = tk.Frame(row, bg=self.BG)
        thick_frame.pack(side="left", padx=(0, 6))

        self._slider_label = tk.Label(
            thick_frame, text=tr("tb_thickness_pen"), bg=self.BG, fg="#E8E8F5",
            font=("Segoe UI", 7), width=4
        )
        self._slider_label.pack(side="left")

        self._thickness_var = tk.IntVar(value=4)
        self._slider = tk.Scale(
            thick_frame, from_=1, to=100, orient="horizontal",
            variable=self._thickness_var,
            length=110, sliderlength=14,
            showvalue=True,
            bg=self.BG, fg="#E8E8F5", troughcolor="#1F1D45",
            highlightthickness=0, bd=0,
            activebackground=self.BG_ACTIVE,
            font=("Segoe UI", 7),
            command=self._on_thickness_change
        )
        self._slider.pack(side="left", padx=2)

        # ── Separator ──
        tk.Frame(row, bg="#4A4680", width=1, height=22).pack(side="left", padx=3)

        # ── Action buttons ──
        actions_frame = tk.Frame(row, bg=self.BG)
        actions_frame.pack(side="left", padx=(0, 4))

        self._action_btn(actions_frame, "\u21a9", self._undo)
        self._action_btn(actions_frame, "\u21aa", self._redo)
        self._action_btn(actions_frame, "\U0001f5d1", self._clear)

        # ── Separator ──
        tk.Frame(row, bg="#4A4680", width=1, height=22).pack(side="left", padx=3)

        # ── Fullscreen (editor mode only) ──
        if not getattr(self._overlay, '_supports_view_mode', True):
            tk.Button(
                row, text="\u26f6", bg=self.BG, fg="#E8E8F5",
                font=("Segoe UI", 12), relief="flat", bd=0,
                activebackground=self.BG_HOVER,
                command=self._toggle_fullscreen
            ).pack(side="left", padx=1)

        # ── Editor (overlay mode only) ──
        if getattr(self._overlay, '_supports_view_mode', True):
            tk.Button(
                row, text="\U0001f4c4", bg=self.BG, fg="#E8E8F5",
                font=("Segoe UI Emoji", 11), relief="flat", bd=0,
                activebackground=self.BG_HOVER,
                command=self._open_editor
            ).pack(side="left", padx=1)

        # ── Close ──
        tk.Button(
            row, text="\u2716", bg="#E53935", fg="#FFF",
            font=("Segoe UI", 10, "bold"), relief="flat", bd=0,
            width=2, activebackground="#FF5252",
            command=self._close_pen
        ).pack(side="left")

    # ── Embedded UI (3 rows - compact panel) ─────────

    # Background colors for embedded panel — light theme
    BG_EMB = "#302D5E"          # matches main widget gradient middle tone
    BG_EMB_ACTIVE = "#4D6AFF"   # bright blue active highlight
    BG_EMB_HOVER = "#3F3C7A"    # subtle lift for hover

    @staticmethod
    def _emb_metrics(scale):
        """Single source of truth for all scale-derived sizes in embedded mode.
        At scale=1.0 (medium widget, btn_s=72) this matches the new compact
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
            # Font-size dropdown — shrunk to <half its previous width
            # (round 4: caller asked for narrower picker boxes so the
            # whole toolbar packs tighter).
            fs_w=max(26, int(30 * s)),
            fs_h=max(18, int(22 * s)),
            fs_fz=max(8, int(9 * s)),
            fs_drop_fz=max(9, int(10 * s)),
            # Font picker — shrunk to <half its previous width
            fp_w=max(46, int(64 * s)),
            fp_h=max(18, int(22 * s)),
            # Pen slider (CTkSlider) — bigger now that it lives on row 1
            # alongside the icon buttons; fills the previous right-side gap.
            sl_w=max(85, int(115 * s)),
            sl_h=max(12, int(14 * s)),
            sl_pack_lpad=max(2, int(3 * s)),
            sl_pack_rpad=max(1, int(1 * s)),
            sl_pack_pady=max(1, int(2 * s)),
            # Slider unit labels (✏)
            sl_lbl_fz=max(8, int(10 * s)),
            sl_val_fz=max(7, int(8 * s)),
            sl_val_w=max(2, int(3 * s)),
            # Color swatches
            color_w=max(1, int(2 * s)),
            color_h=1,
            color_padx=0,
            # Action buttons (undo / redo / clear) — now thicker/bigger
            act_fz=max(10, int(12 * s)),
            act_padx=max(2, int(4 * s)),
            act_pady=max(1, int(2 * s)),
            act_pack_padx=max(1, int(2 * s)),
            # Fixed-shape tool buttons (round 6: arrow / circle / triangles /
            # rect / hex). Six glyphs share row 2's middle gap, so the font is
            # slightly smaller than the main tool icons to keep them packed
            # tight without overflowing the panel.
            shape_fz=max(8, int(11 * s)),
            shape_padx=max(0, int(1 * s)),
            # Editor + close buttons (right-aligned)
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
        """Compact 2-row layout for main voice widget panel.

        All sizes derive from self._emb_scale via _emb_metrics() so the toolbar
        rescales in lock-step with the main widget's size preset.

        Row 1 (everything left-flowing — no right gap):
          Pen Highlight Eraser | Text Handwrite | FontSize▼ | Undo Redo Clear
          Editor Close (still right-aligned but row width matches content)
        Row 2:
          Colors | ✏ slider value | Font picker (custom Listbox dropdown)
        """
        bg = self.BG_EMB
        sep_clr = "#4A4680"  # subtle purple separator on dark bg
        m = self._emb_metrics(self._emb_scale)

        # The main frame is the *visual background* — it acts as the
        # "anchor at left-middle" parent. All toolbar widgets live inside,
        # so when set_scale() resizes them the background scales with them.
        main = tk.Frame(self._root, bg=bg, padx=m["main_padx"],
                        pady=m["main_pady"])
        main.pack(fill="both", expand=True)
        self._emb_main = main
        self._bind_drag(main)

        def _bcfg():
            return dict(fg="#E8E8F5", relief="flat", bd=0,
                        padx=m["btn_padx"], pady=m["btn_pady"])

        # ══════════════════════════════════════════════════
        # ROW 1: tools | text-tools | font-size | actions | editor close
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
        self._track(self._btn_pen, "icon_first", side="left")

        self._btn_highlight = tk.Button(
            row1, text=self.ICON_HIGHLIGHTER, bg=bg,
            font=("Segoe UI Emoji", m["icon_fz"]),
            activebackground=self.BG_EMB_HOVER,
            command=lambda: self._toggle_tool("highlighter"), **_bcfg())
        self._btn_highlight.pack(side="left", padx=m["pack_padx"])
        self._track(self._btn_highlight, "icon", side="left")

        self._btn_eraser = tk.Button(
            row1, text=self.ICON_ERASER, bg=bg,
            font=("Segoe UI Emoji", m["icon_fz"]),
            activebackground=self.BG_EMB_HOVER,
            command=lambda: self._activate_eraser(), **_bcfg())
        self._btn_eraser.pack(side="left", padx=m["pack_padx"])
        self._track(self._btn_eraser, "icon", side="left")

        # Separator
        sep1 = tk.Frame(row1, bg=sep_clr, width=1)
        sep1.pack(side="left", fill="y", padx=m["sep_padx"],
                  pady=m["sep_pady"])
        self._track(sep1, "sep", side="left")

        # - Text tools group -
        self._btn_text = tk.Button(
            row1, text=self.ICON_TEXT, bg=bg,
            font=("Segoe UI", m["text_fz"], "bold"),
            activebackground=self.BG_EMB_HOVER,
            command=lambda: self._toggle_tool("text"), **_bcfg())
        self._btn_text.pack(side="left", padx=m["pack_padx"])
        self._track(self._btn_text, "text", side="left")

        self._btn_handwrite = tk.Button(
            row1, text=self.ICON_HANDWRITE, bg=bg,
            font=("Segoe UI Emoji", m["icon_fz"]),
            activebackground=self.BG_EMB_HOVER,
            command=lambda: self._toggle_tool("handwrite"), **_bcfg())
        self._btn_handwrite.pack(side="left", padx=m["pack_padx"])
        self._track(self._btn_handwrite, "icon", side="left")

        self._btn_hand = None  # No pan in embedded mode

        # Separator
        sep2 = tk.Frame(row1, bg=sep_clr, width=1)
        sep2.pack(side="left", fill="y", padx=m["sep_padx"],
                  pady=m["sep_pady"])
        self._track(sep2, "sep", side="left")

        # - Pen-thickness slider (moved from row 2 to row 1, slightly bigger
        #   to fill the gap on the right side of row 1). Independent of font
        #   size — see _on_thickness_change docstring. -
        self._lbl_pen_unit = tk.Label(
            row1, text="\u270f", bg=bg, fg="#A0A0C0",
            font=("Segoe UI Emoji", m["sl_lbl_fz"]))
        self._lbl_pen_unit.pack(side="left")
        self._track(self._lbl_pen_unit, "sl_lbl", side="left")

        self._thickness_var = tk.IntVar(value=4)
        self._slider = ctk.CTkSlider(
            row1, from_=1, to=100, number_of_steps=99,
            variable=self._thickness_var,
            width=m["sl_w"], height=m["sl_h"],
            fg_color=_SLIDER_TRACK, progress_color=_SLIDER_FILL,
            button_color=_SLIDER_THUMB, button_hover_color=_SLIDER_HOVER,
            command=self._on_thickness_change)
        self._slider.pack(side="left",
                          padx=(m["sl_pack_lpad"], m["sl_pack_rpad"]),
                          pady=m["sl_pack_pady"])
        self._track(self._slider, "slider", side="left")

        # - Pen-width value with click-to-toggle ◀ / ▶ steppers (round 7) -
        # The value label sits in a small frame using grid so the stepper
        # buttons can appear/disappear on either side without disturbing
        # the surrounding pack layout. grid_remove() preserves geometry.
        self._pen_stepper_frame = tk.Frame(row1, bg=bg)
        self._pen_stepper_frame.pack(side="left")
        self._track(self._pen_stepper_frame, "stepper_frame", side="left")

        step_fz = max(7, m["sl_val_fz"] - 1)
        self._pen_dec_btn = tk.Button(
            self._pen_stepper_frame, text="\u25c0", bg=bg, fg="#E8E8F5",
            relief="flat", bd=0, padx=1, pady=0,
            activebackground=self.BG_EMB_HOVER, cursor="hand2",
            font=("Segoe UI Symbol", step_fz),
            command=lambda: self._step_pen_thickness(-1))
        self._pen_dec_btn.grid(row=0, column=0)
        self._pen_dec_btn.grid_remove()  # hidden until value is clicked
        self._track(self._pen_dec_btn, "step_btn", side="left")

        self._pen_val_lbl = tk.Label(
            self._pen_stepper_frame, text="4", bg=bg, fg="#A0A0C0",
            font=("Segoe UI", m["sl_val_fz"]),
            width=m["sl_val_w"], anchor="center", cursor="hand2")
        self._pen_val_lbl.grid(row=0, column=1)
        self._pen_val_lbl.bind("<Button-1>", self._toggle_pen_stepper)
        self._track(self._pen_val_lbl, "sl_val", side="left")

        self._pen_inc_btn = tk.Button(
            self._pen_stepper_frame, text="\u25b6", bg=bg, fg="#E8E8F5",
            relief="flat", bd=0, padx=1, pady=0,
            activebackground=self.BG_EMB_HOVER, cursor="hand2",
            font=("Segoe UI Symbol", step_fz),
            command=lambda: self._step_pen_thickness(1))
        self._pen_inc_btn.grid(row=0, column=2)
        self._pen_inc_btn.grid_remove()  # hidden until value is clicked
        self._track(self._pen_inc_btn, "step_btn", side="left")

        self._pen_stepper_visible = False

        # Separator
        sep3 = tk.Frame(row1, bg=sep_clr, width=1)
        sep3.pack(side="left", fill="y", padx=m["sep_padx"],
                  pady=m["sep_pady"])
        self._track(sep3, "sep", side="left")

        # - Action buttons on row 1: only undo + redo now.
        #   Clear (\U0001f5d1) moved to row 2 far-right per user request,
        #   to soak up the empty space that used to sit below the close
        #   button when row 2 was narrower than row 1.
        self._action_btns = []
        for icon, cmd in [("\u21a9", self._undo), ("\u21aa", self._redo)]:
            b = tk.Button(
                row1, text=icon, bg=bg, fg="#E8E8F5",
                font=("Segoe UI", m["act_fz"]), relief="flat", bd=0,
                padx=m["act_padx"], pady=m["act_pady"], width=2,
                activebackground=self.BG_EMB_HOVER, command=cmd)
            b.pack(side="left", padx=m["act_pack_padx"])
            self._action_btns.append(b)
            self._track(b, "act", side="left")

        # - Close button (row 1 far-right, accent) -
        self._btn_close = tk.Button(
            row1, text="\u2716", bg="#E53935", fg="#FFF",
            font=("Segoe UI", m["close_fz"], "bold"), relief="flat", bd=0,
            padx=m["close_padx"], pady=m["close_pady"],
            activebackground="#FF5252",
            command=self._on_retract)
        self._btn_close.pack(side="right", padx=(m["close_pack_padx"], 0))
        self._track(self._btn_close, "close", side="right")

        # NOTE: Editor button moved to row 2 (was row 1 before this round).
        # Initialised to None here; created in row-2 block below.
        self._btn_editor = None

        # ══════════════════════════════════════════════════
        # ROW 2 (round 7 layout):
        #   shapes (LEFT) | <gap> | colors | font-size | font-picker |
        #                                              editor | clear (RIGHT)
        # Shapes occupy the slot the colour swatches used to hold; styling
        # controls (colour / font / font-size) cluster on the right next to
        # the editor button. side="right" packs in reverse visual order, so
        # we pack clear → editor → font-picker → font-size → colors so that
        # they appear left-to-right as: colors, font-size, font-picker,
        # editor, clear.
        # ══════════════════════════════════════════════════
        row2 = tk.Frame(main, bg=bg)
        row2.pack(fill="x")
        self._row2 = row2
        self._bind_drag(row2)

        # ── LEFT side: shape tools ────────────────────────
        # - Fixed shape-tool group (round 6) -
        #   Six click-and-drag shape tools that share the global pen color
        #   and pen width — drag to define bounding box, release to commit.
        #   Engine-side rendering lives in DrawingEngine._render_shape.
        self._shape_btns = {}
        SHAPE_DEFS = [
            ("arrow", "\u27a4"),    # ➤
            ("circle", "\u25cb"),   # ○
            ("rtri", "\u25e3"),     # ◣
            ("etri", "\u25b3"),     # △
            ("rect", "\u25ad"),     # ▭
            ("hex", "\u2b21"),      # ⬡
        ]
        for kind, glyph in SHAPE_DEFS:
            sb = tk.Button(
                row2, text=glyph, bg=bg,
                font=("Segoe UI Symbol", m["shape_fz"]),
                activebackground=self.BG_EMB_HOVER,
                command=lambda k=kind: self._toggle_tool(f"shape_{k}"),
                **_bcfg())  # _bcfg() already supplies fg, relief, bd, pad
            sb.pack(side="left", padx=m["shape_padx"])
            self._shape_btns[kind] = sb
            self._track(sb, "shape", side="left")

        # ── RIGHT side: clear → editor → font-picker → font-size → colors
        # Pack in reverse so they appear left-to-right in the natural order.

        # - Clear button (row 2 far-right) -
        self._btn_clear = tk.Button(
            row2, text="\U0001f5d1", bg=bg, fg="#E8E8F5",
            font=("Segoe UI", m["act_fz"]), relief="flat", bd=0,
            padx=m["act_padx"], pady=m["act_pady"], width=2,
            activebackground=self.BG_EMB_HOVER, command=self._clear)
        self._btn_clear.pack(side="right", padx=(m["act_pack_padx"], 0))
        self._action_btns.append(self._btn_clear)
        self._track(self._btn_clear, "act_right", side="right")

        # - Editor button (right of font picker, before clear) -
        if getattr(self._overlay, '_supports_view_mode', True):
            self._btn_editor = tk.Button(
                row2, text="\U0001f4c4", bg=bg, fg="#E8E8F5",
                font=("Segoe UI Emoji", m["edit_fz"]), relief="flat", bd=0,
                padx=m["edit_padx"], pady=m["edit_pady"],
                activebackground=self.BG_EMB_HOVER,
                command=self._open_editor)
            self._btn_editor.pack(side="right", padx=m["edit_pack_padx"])
            self._track(self._btn_editor, "edit", side="right")

        # - Font picker (right of font-size, before editor) -
        self._font_var = tk.StringVar(
            value=self._font_list[0] if self._font_list else "Segoe UI")
        self._font_picker = _ScrollableFontPicker(
            row2, fonts=self._font_list,
            current=self._font_var.get(),
            on_select=self._on_font_pick,
            scale=self._emb_scale, visible_rows=20,
            base_w=64, min_w=46)
        self._font_picker.pack(side="right", padx=m["pack_padx"], pady=1)
        self._track(self._font_picker, "font_picker", side="right")
        # Compatibility: _font_menu is referenced in some sync paths.
        self._font_menu = self._font_picker

        # - Font-size dropdown (right of colors, before font picker) -
        self._font_size_var = tk.StringVar(value="24")
        self._font_size_menu = _ScrollableFontPicker(
            row2, fonts=FONT_SIZE_CHOICES, current="24",
            on_select=self._on_font_size_pick,
            scale=self._emb_scale, visible_rows=12,
            base_w=30, min_w=26)
        self._font_size_menu.pack(side="right", padx=m["pack_padx"], pady=1)
        self._track(self._font_size_menu, "fs_picker", side="right")

        # - Color swatches (right group, leftmost — packed last with side=right
        #   so they sit just left of font-size). They appear visually in the
        #   declared order PEN_COLORS because each swatch is packed side=right
        #   in turn, which would reverse them — so iterate reversed() here. -
        self._color_btns = {}
        for hex_color, name in reversed(self.PEN_COLORS):
            btn = tk.Button(
                row2, bg=hex_color, width=m["color_w"], height=m["color_h"],
                relief="groove", bd=1, activebackground=hex_color,
                command=lambda c=hex_color: self._set_color(c))
            btn.pack(side="right", padx=m["color_padx"], pady=1)
            self._color_btns[hex_color] = btn
            self._track(btn, "color_right", side="right")
            if hex_color == "#FF0000":
                btn.configure(relief="solid", bd=2)
                self._active_color_btn = btn

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
            parent, text=text, bg=bg, fg="#E8E8F5",
            font=("Segoe UI", 10), relief="flat", bd=0,
            activebackground=self.BG_EMB_HOVER, command=command
        ).pack(side="left", padx=1)

    # ── Common helpers ────────────────────────────────

    def _action_btn(self, parent, text, command, font_size=11):
        tk.Button(
            parent, text=text, bg=self.BG, fg="#E8E8F5",
            font=("Segoe UI", font_size), relief="flat", bd=0,
            activebackground=self.BG_HOVER, command=command
        ).pack(side="left", padx=1)

    def get_root_widget(self):
        """Return actual widget - Toplevel (standalone) or Frame (embedded)."""
        return self._root

    @staticmethod
    def calc_panel_width(btn_s):
        """Embedded panel width — sized to fit the new 2-row content exactly
        so there's no empty space on the right. With actions moved to row 1
        and font-size now a compact dropdown, the panel can be tighter."""
        scale = btn_s / 72.0
        return max(310, int(395 * scale))

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

        # Per-widget reconfiguration (sizes / fonts / widths)
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
                elif kind == "fs_picker":
                    # Font-size picker — same scrollable-picker class as fonts.
                    widget.set_scale(m["scale"])
                elif kind == "font_picker":
                    # Custom picker has its own scale-aware update
                    widget.set_scale(m["scale"])
                elif kind == "slider":
                    widget.configure(width=m["sl_w"], height=m["sl_h"])
                elif kind == "sl_lbl":
                    widget.configure(
                        font=("Segoe UI Emoji", m["sl_lbl_fz"]))
                elif kind == "sl_val":
                    widget.configure(font=("Segoe UI", m["sl_val_fz"]),
                                     width=m["sl_val_w"])
                elif kind in ("color", "color_right"):
                    widget.configure(width=m["color_w"], height=m["color_h"])
                elif kind in ("act", "act_right"):
                    widget.configure(font=("Segoe UI", m["act_fz"]),
                                     padx=m["act_padx"],
                                     pady=m["act_pady"])
                elif kind == "shape":
                    widget.configure(
                        font=("Segoe UI Symbol", m["shape_fz"]),
                        padx=m["btn_padx"], pady=m["btn_pady"])
                elif kind == "step_btn":
                    widget.configure(
                        font=("Segoe UI Symbol",
                              max(7, m["sl_val_fz"] - 1)))
                elif kind == "stepper_frame":
                    pass  # frame has no scaling-relevant attrs
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

        # Re-apply pack paddings (configure above only changes widget options)
        for widget, kind, _kwargs in self._scaled_widgets:
            try:
                if kind == "icon_first":
                    widget.pack_configure(padx=(0, m["pack_padx"]))
                elif kind in ("icon", "text"):
                    widget.pack_configure(padx=m["pack_padx"])
                elif kind == "fs_picker":
                    widget.pack_configure(padx=m["pack_padx"], pady=1)
                elif kind == "font_picker":
                    widget.pack_configure(padx=m["pack_padx"], pady=1)
                elif kind == "slider":
                    widget.pack_configure(
                        padx=(m["sl_pack_lpad"], m["sl_pack_rpad"]),
                        pady=m["sl_pack_pady"])
                elif kind in ("color", "color_right"):
                    widget.pack_configure(padx=m["color_padx"], pady=1)
                elif kind == "act":
                    widget.pack_configure(padx=m["act_pack_padx"])
                elif kind == "act_right":
                    # Clear button on row 2 — anchored to right edge
                    widget.pack_configure(padx=(m["act_pack_padx"], 0))
                elif kind == "shape":
                    widget.pack_configure(padx=m["shape_padx"])
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

        # Shape tools (round 6): no view-mode toggle — clicking the same
        # shape again reverts to the pen tool so the user can quickly leave
        # shape-drawing mode without hunting for the pen icon.
        if tool.startswith("shape_"):
            if self._active_tool == tool and self._draw_mode:
                self._active_tool = "pen"
                self._overlay.set_tool("pen")
            else:
                self._active_tool = tool
                self._overlay.set_tool(tool)
            self._enter_draw_mode()
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

        # Shape buttons (round 6): highlight whichever shape is active.
        # In view mode all shape buttons revert to inactive bg.
        if hasattr(self, '_shape_btns') and self._shape_btns:
            for kind, btn in self._shape_btns.items():
                want_tool = "shape_" + kind
                if (self._draw_mode and self._active_tool == want_tool):
                    btn.configure(bg=bg_on)
                else:
                    btn.configure(bg=bg_off)

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
        # Keep current tool if it's text or one of the shape_* tools — colour
        # changes shouldn't kick the user out of those modes. Otherwise fall
        # back to pen (the historical behaviour).
        keep_tool = (
            self._active_tool == "text"
            or (isinstance(self._active_tool, str)
                and self._active_tool.startswith("shape_"))
        )
        if not keep_tool:
            self._active_tool = "pen"
            self._overlay.set_tool("pen")
        self._enter_draw_mode()

    def _on_thickness_change(self, value):
        """Pen-thickness slider handler.

        IMPORTANT: This slider is dedicated to pen/highlighter/eraser stroke
        width ONLY. It must NEVER drive font size — text/handwrite font
        size is controlled exclusively by the dedicated font-size dropdown.
        Earlier versions branched on _active_tool and routed the slider
        value into set_text_font_size/set_hw_font when text or handwrite
        was active, which made dragging the thickness slider visually
        resize live text — confusing and unwanted."""
        val = int(value)
        if hasattr(self, '_pen_val_lbl'):
            self._pen_val_lbl.configure(text=str(val))
        # Always — and only — set pen stroke width. No font side-effects.
        self._overlay.set_width(val)

    def _toggle_pen_stepper(self, _evt=None):
        """Show / hide the ◀ ▶ steppers around the pen-width number.

        Round 7: clicking the value reveals tiny inc/dec buttons so the
        user can fine-tune width by ±1 without dragging the slider.
        """
        if not hasattr(self, '_pen_stepper_visible'):
            return
        self._pen_stepper_visible = not self._pen_stepper_visible
        try:
            if self._pen_stepper_visible:
                self._pen_dec_btn.grid()
                self._pen_inc_btn.grid()
            else:
                self._pen_dec_btn.grid_remove()
                self._pen_inc_btn.grid_remove()
        except (AttributeError, tk.TclError):
            pass

    def _step_pen_thickness(self, delta):
        """Increment / decrement the pen-thickness slider by `delta`."""
        try:
            cur = int(self._thickness_var.get())
        except (AttributeError, tk.TclError):
            return
        new = max(1, min(100, cur + int(delta)))
        if new == cur:
            return
        try:
            self._thickness_var.set(new)
        except tk.TclError:
            pass
        self._on_thickness_change(new)

    def _on_font_size_change(self, value):
        """Handle font size slider change (standalone mode only)."""
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

    def _on_font_size_pick(self, choice):
        """Font-size picker selection.

        UX rule (round 6): font/size pickers NEVER mutate already-typed
        text and they work the same regardless of which tool is active.

        - If a text edit is currently in progress, finalize it first so
          the existing text keeps its existing size.
        - Store the new size as the engine default; the next text edit
          (started by clicking the canvas in text-tool mode) uses it.
        - Also update handwrite default size for symmetry.

        This eliminates the previous broken behaviour where dragging the
        thickness slider or picking a font-size would visually resize
        the live text mid-edit, and where pickers only "worked" after
        toggling out of text mode."""
        try:
            val = int(choice)
        except (TypeError, ValueError):
            return
        engine = getattr(self._overlay, '_engine', None)
        if not engine:
            return
        if getattr(engine, '_text_active', False):
            try:
                engine._finalize_text()
            except Exception:
                pass
        engine._text_font_size = val
        engine._hw_font_size = val
        # Force next handwrite stroke to start a fresh text run with new size
        engine._hw_active_text = None

    def _on_font_pick(self, font_name):
        """Font-name picker — same UX rule as font size (see above)."""
        if not font_name or font_name == self.SEPARATOR:
            return
        try:
            self._font_var.set(font_name)
        except Exception:
            pass
        engine = getattr(self._overlay, '_engine', None)
        if not engine:
            return
        if getattr(engine, '_text_active', False):
            try:
                engine._finalize_text()
            except Exception:
                pass
        engine._font_family = font_name
        engine._hw_font = font_name
        engine._hw_active_text = None

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
