"""UI builder + window-size geometry.

Builds the toolbar (4 spectrum buttons + dropdown arrows + 3 tool
icons), renders the gradient background, and computes the geometry
math for the various size presets (mini/tiny/small/medium/large/xlarge).

The static ``_calc_*`` helpers live here too because they're the
geometry source of truth — used both for initial layout and for
``apply_size_preset`` re-layout after the user changes Settings →
Size.
"""

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from app.constants import BTN_SIZES


class UIBuilderMixin:
    """Mixed into VoiceTypingApp — toolbar build + geometry + size scaling."""

    @staticmethod
    def _calc_dims(btn_s):
        """Calculate window (w, h) from button size - single source of truth."""
        sc = btn_s / 72.0
        padx = max(6, int(8 * sc))
        gap = max(3, int(4 * sc))
        # XXS (mini=36) uses a smaller width budget for the tool column so the
        # widget stays narrower AND the tools visibly shrink vs XS (was 16 →
        # too close to XS's 20). 14 gives a clear 30% width reduction.
        tool_floor = 14 if btn_s < 48 else 20
        tool_w = max(tool_floor, int(28 * sc)) + 4
        w = 2 * padx + 4 * btn_s + 4 * gap + tool_w
        # Reserve extra height below the buttons for the dropdown ▼ arrows
        # (BN / EN / SND / AI). Skipped at the smallest preset where the
        # arrow would render too tiny to read.
        arrow_h, arrow_gap = VoiceTypingApp._calc_arrow_dims(btn_s)
        base_h = btn_s + max(12, int(14 * sc))
        h = base_h + arrow_h + arrow_gap if arrow_h else base_h
        return w, h

    @staticmethod
    def _calc_arrow_dims(btn_s):
        """Return (arrow_height, arrow_gap) reserved below the buttons.
        Returns (0, 0) when the preset is too small for a legible arrow.
        Tightened further per user request — these are just toggles for
        the drawer, they shouldn't visually compete with the buttons."""
        sc = btn_s / 72.0
        arrow_h = max(5, int(6 * sc))
        arrow_gap = max(2, int(2 * sc))
        if arrow_h < 5:
            return 0, 0
        return arrow_h, arrow_gap

    @staticmethod
    def _calc_tools_panel_w(btn_s):
        """Pen tools panel width — initial estimate, refined by actual
        measurement after the toolbar renders (see _refit_panel_to_toolbar).

        The estimate floor (320) is chosen so XS/S widgets don't get a hard
        440px container around a 290–340px toolbar, which produced visible
        right-side empty space. Once the toolbar mounts we measure
        winfo_reqwidth() and tighten the container to actual content."""
        scale = btn_s / 72.0
        # Linear estimate matching observed embedded-toolbar content widths:
        # scale 0.667 → ~310,  0.778 → ~360,  1.0 → ~445,  1.167 → ~520,
        # 1.333 → ~590. Floor 320 keeps the smallest preset just barely
        # roomier than its measured content (~290px) so the measurement
        # step never has to expand, only shrink.
        return max(320, int(445 * scale))

    def _refit_panel_to_toolbar(self):
        """Tighten the panel container to the toolbar's actual rendered width.

        The toolbar is ``pack(fill="both", expand=True)`` inside
        ``_panel_container`` which has ``pack_propagate(False)`` so the
        container's set width wins. After mount, the toolbar's natural
        ``winfo_reqwidth()`` reflects exactly how wide the buttons + paddings
        are. Setting the container to that + tiny margin removes any
        right-side gap at small widget sizes (XS/S) where the linear
        estimate slightly overshoots."""
        try:
            tb = getattr(self, '_pen_toolbar', None)
            if not tb or not getattr(self, '_pen_tools_expanded', False):
                return
            root = tb.get_root_widget()
            root.update_idletasks()
            req = root.winfo_reqwidth()
            if req <= 1:
                return
            # +4px margin so border/highlightthickness doesn't clip
            target = req + 4
            preset = self.settings.get("size_preset", "medium")
            btn_s = self.BTN_SIZES.get(preset, 72)
            base_w, h = self._calc_dims(btn_s)
            self._panel_container.configure(width=target, height=h)
            try:
                wx, wy = self.winfo_x(), self.winfo_y()
            except Exception:
                wx, wy = 0, 0
            self.geometry(f"{base_w + target}x{h}+{wx}+{wy}")
        except Exception:
            pass

    def init_ui(self):
        import tkinter as tk
        from ui_components.spectrum_button import SpectrumButton
        from config import SPECTRUM_BTN_SIZE, SPECTRUM_COLORS

        # Main container - holds canvas (left) + pen panel (right)
        # Vertical wrapper so we can place a slide-out drawer BELOW the
        # main toolbar row (used by the BN/EN/SND/AI ▼ arrows).
        self._root_vbox = tk.Frame(self, bg="#22214B")
        self._root_vbox.pack(fill="both", expand=True)

        self._main_container = tk.Frame(self._root_vbox, bg="#22214B")
        self._main_container.pack(side="top", fill="x")

        # Drawer host — sibling of _main_container, packed BELOW it.
        # Always present; content is added/removed when a drawer opens.
        # bg = the Toplevel's transparent magic color (set in __init__
        # via wm_attributes("-transparentcolor", "#010101")) so the
        # area around a narrow BN/EN/SND drawer is click-through and
        # the wallpaper shows through. Without this the host renders
        # as a dark strip beside the drawer that doesn't belong.
        self._drawer_host = tk.Frame(self._root_vbox,
                                       bg=self.transparent_color,
                                       highlightthickness=0)
        self._drawer_host.pack(side="top", fill="x")
        # Children are placed via .place() (zero natural size). Lock the
        # frame so pack does NOT collapse it — height is driven manually
        # via configure(height=N) when a drawer opens / closes.
        self._drawer_host.pack_propagate(False)
        self._drawer_host.configure(height=0)
        self._drawer_active_kind = None     # "bn"/"en"/"snd"/"ai" or None
        self._drawer_widget = None          # current drawer Frame

        # Panel container for embedded pen tools (LEFT side, initially hidden)
        self._panel_container = tk.Frame(
            self._main_container, bg="#302D5E",
            highlightthickness=0)
        # NOT packed yet - packed only when pen panel opens

        # Canvas for gradient background (RIGHT side, always visible)
        self.frame = tk.Canvas(self._main_container, bg="#22214B",
                               highlightthickness=0)
        self.frame.pack(side="left", fill="y")

        self.frame.bind("<ButtonPress-1>", self.on_press)
        self.frame.bind("<B1-Motion>", self.on_drag)
        self.frame.bind("<ButtonRelease-1>", self._on_bg_release)

        btn_size = SPECTRUM_BTN_SIZE

        # Spectrum buttons (placed on canvas later by _apply_window_size)
        lang1 = self.settings.get("btn1_lang", "bn-BD")
        self.btn_bn = SpectrumButton(self.frame, size=btn_size, label="BN",
            colors=SPECTRUM_COLORS, toolbar_bg=self.TOOLBAR_BG,
            command=lambda: self.switch_language(self.settings.get("btn1_lang", "bn-BD")))
        self.btn_bn.set_display_label(lang1.split("-")[0].upper())

        lang2 = self.settings.get("btn2_lang", "en-US")
        self.btn_en = SpectrumButton(self.frame, size=btn_size, label="EN",
            colors=SPECTRUM_COLORS, toolbar_bg=self.TOOLBAR_BG,
            command=lambda: self.switch_language(self.settings.get("btn2_lang", "en-US")))
        self.btn_en.set_display_label(lang2.split("-")[0].upper())

        self.btn_read = SpectrumButton(self.frame, size=btn_size, label="SND",
            colors=SPECTRUM_COLORS, toolbar_bg=self.TOOLBAR_BG,
            command=self.handle_reader_click)

        self.btn_ai = SpectrumButton(self.frame, size=btn_size, label="AI",
            colors=SPECTRUM_COLORS, toolbar_bg=self.TOOLBAR_BG,
            command=self._ai_button_send)

        # Dropdown ▼ arrows under each main button. Live as Canvas-
        # embedded widgets that get placed by _apply_window_size.
        # Hidden during drag, auto-resize per size_preset.
        from ui_components.dropdown_arrow import DropdownArrow
        self.arrow_bn = DropdownArrow(
            self.frame, command=self._open_bn_dropdown,
            toolbar_bg=self.TOOLBAR_BG)
        self.arrow_en = DropdownArrow(
            self.frame, command=self._open_en_dropdown,
            toolbar_bg=self.TOOLBAR_BG)
        self.arrow_read = DropdownArrow(
            self.frame, command=self._open_read_dropdown,
            toolbar_bg=self.TOOLBAR_BG)
        self.arrow_ai = DropdownArrow(
            self.frame, command=self._open_ai_dropdown,
            toolbar_bg=self.TOOLBAR_BG)
        self._arrows = [self.arrow_bn, self.arrow_en,
                        self.arrow_read, self.arrow_ai]
        self._active_dropdown = None

        # Apply label visibility from settings
        if not self.settings.get("show_labels", True):
            for btn in [self.btn_bn, self.btn_en, self.btn_read, self.btn_ai]:
                btn.set_labels_visible(False)

        # Tool buttons frame
        self.tool_frame = tk.Frame(self.frame, bg=self.TOOLBAR_BG)

        # 1x1 transparent pixel — paired with compound="center" forces
        # tk.Button width/height to be interpreted as PIXELS (not text units).
        # This is what lets the 3 tool buttons actually shrink at XXS (CTk's
        # internal minimum of ~20px would otherwise overflow the canvas).
        self._tool_pixel = tk.PhotoImage(width=1, height=1)

        def _mk_tool(glyph, cmd):
            b = tk.Button(
                self.tool_frame, text=glyph, image=self._tool_pixel,
                compound="center", width=30, height=26,
                font=("Segoe UI Emoji", 13),
                bg=self.TOOLBAR_BG, fg="white", relief="flat", bd=0,
                # padx/pady default to 1 in tk.Button — internal padding
                # would add 2px to actual rendered size, breaking the
                # pixel-precise place() math at XXS. Force to 0.
                padx=0, pady=0,
                highlightthickness=0, activebackground="#4A4A6A",
                activeforeground="white", cursor="hand2", command=cmd)
            b.pack(pady=0)
            return b

        self.btn_pen = _mk_tool("\U0001f58a\ufe0f", self.toggle_pen_mode)
        self.btn_screenshot = _mk_tool("\U0001f4f7", self.take_screenshot)
        self.btn_settings = _mk_tool("\u2699\ufe0f", self.open_settings_panel)

        self._apply_window_size()

    def _render_toolbar_bg(self, w, h):
        """Render rectangular gradient 3D toolbar background - no rounding."""
        from PIL import ImageTk

        img = Image.new("RGB", (w, h))
        d = ImageDraw.Draw(img)

        for y in range(h):
            t = y / max(1, h - 1)
            # Blue-purple gradient (3D: top light, bottom dark)
            r = int(62 - 28 * t)
            g = int(58 - 25 * t)
            b = int(115 - 42 * t)

            # Glass highlight at top 18%
            if t < 0.18:
                glow = (1 - t / 0.18) ** 1.8
                r = min(255, r + int(50 * glow))
                g = min(255, g + int(48 * glow))
                b = min(255, b + int(55 * glow))

            # Bottom shadow (last 10%)
            if t > 0.90:
                shadow = (t - 0.90) / 0.10
                r = max(0, int(r - 12 * shadow))
                g = max(0, int(g - 10 * shadow))
                b = max(0, int(b - 15 * shadow))

            d.line([(0, y), (w - 1, y)], fill=(r, g, b))

        # Top highlight border
        d.line([(0, 0), (w - 1, 0)], fill=(90, 85, 150))
        # Bottom shadow border
        d.line([(0, h - 1), (w - 1, h - 1)], fill=(25, 23, 55))

        self._toolbar_bg_photo = ImageTk.PhotoImage(img)
        self.frame.delete("bg")
        self.frame.create_image(0, 0, anchor="nw", image=self._toolbar_bg_photo,
                                tags="bg")
        self.frame.tag_lower("bg")

    def load_png_with_label(self, png_filename, label="", width=60, height=35):
        """Simple PNG loader with optional label overlay"""
        try:
            png_path = resource_path(png_filename)
            
            if not os.path.exists(png_path):
                # Try finding in current directory as fallback
                cwd_path = os.path.join(os.getcwd(), png_filename)
                if os.path.exists(cwd_path):
                    png_path = cwd_path
                else:
                    return None
            
            # Load and resize PNG
            img = Image.open(png_path).convert('RGBA')
            img = img.resize((width*2, height*2), Image.Resampling.LANCZOS)
            
            # Add label if provided
            if label:
                draw = ImageDraw.Draw(img)
                try:
                    font = ImageFont.truetype("arial.ttf", int(height * 0.36))
                except OSError:
                    font = ImageFont.load_default()
                
                bbox = draw.textbbox((0, 0), label, font=font)
                text_w = bbox[2] - bbox[0]
                text_h = bbox[3] - bbox[1]
                
                label_x = width * 2 - text_w - int(width * 0.15)
                label_y = height * 2 - text_h - int(height * 0.15)
                
                # Shadow
                for offset in [(-2,-2), (-2,2), (2,-2), (2,2)]:
                    draw.text((label_x + offset[0], label_y + offset[1]), label, 
                             font=font, fill=(0, 0, 0, 180))
                draw.text((label_x, label_y), label, font=font, fill=(255, 255, 255, 255))
            
            return img
        except Exception as e:
            return None

    # Class-attribute alias of the module-level constant.
    BTN_SIZES = BTN_SIZES

    def _apply_window_size(self):
        """Apply size from preset - dynamic width, tight layout."""
        preset = self.settings.get("size_preset", "medium")
        btn_s = self.BTN_SIZES.get(preset, 72)
        base_w, h = self._calc_dims(btn_s)

        # Canvas always fixed to base width
        self.frame.configure(width=base_w, height=h)

        # Total window width = base + panel (if expanded)
        total_w = base_w
        if getattr(self, '_pen_tools_expanded', False):
            panel_w = self._calc_tools_panel_w(btn_s)
            total_w += panel_w
            self._panel_container.configure(width=panel_w, height=h)

        # Preserve position
        try:
            wx, wy = self.winfo_x(), self.winfo_y()
        except Exception:
            wx, wy = 0, 0
        # Add drawer height if a slide-out is currently open
        drawer_h = self._current_drawer_height()
        self.geometry(f"{total_w}x{h + drawer_h}+{wx}+{wy}")

        scale = btn_s / 72.0
        padx = max(6, int(8 * scale))
        gap = max(3, int(4 * scale))
        # Match _calc_dims: XXS gets a tighter floor (14) for visible size
        # difference vs XS (20). tiny+ unchanged.
        tool_floor = 14 if btn_s < 48 else 20
        tool_sz = max(tool_floor, int(28 * scale))
        tool_w = tool_sz + 4

        # Scale spectrum buttons
        for btn in [self.btn_bn, self.btn_en, self.btn_read, self.btn_ai]:
            if hasattr(btn, 'resize'):
                btn.resize(btn_s)

        # Scale the embedded pen toolbar in lock-step with the widget
        # (only matters when the panel is currently open)
        if getattr(self, '_pen_toolbar', None):
            try:
                self._pen_toolbar.set_scale(scale)
            except Exception:
                pass
            # After the toolbar reflows at the new scale, tighten the panel
            # container to its actual measured width — eliminates any gap at
            # XS/S sizes where the linear estimate slightly overshoots.
            self.after(60, self._refit_panel_to_toolbar)

        # Scale tool buttons. tk.Button + 1x1 image trick makes width/height
        # exact pixels, so the 3-button stack can be precisely distributed.
        # 0.80 ratio (was 0.85) makes them slightly more compact per request.
        tool_font = max(9, int(13 * scale))
        tool_h = int(tool_sz * 0.80)
        # XXS: explicit overrides — tool_h=12 gives perfect 3-3-3-3 gap
        # distribution in 48px canvas, and 8pt font fits inside the 12px
        # button height (9pt overflows ~14px line-height → causes the
        # adjacent-button visual overlap the user reported).
        if btn_s < 48:
            tool_h = 12
            tool_font = 8
        tool_buttons = [self.btn_pen, self.btn_screenshot, self.btn_settings]
        for btn in tool_buttons:
            try:
                btn.configure(width=tool_sz, height=tool_h,
                              font=("Segoe UI Emoji", tool_font))
            except tk.TclError:
                pass

        # Distribute the 3 tool buttons with EQUAL 4-way gaps inside the
        # canvas-height tool_frame. With place() we get pixel-precise
        # alignment (all 3 share one x), and gaps are computed so top,
        # between-1, between-2, and bottom are as equal as integer pixels
        # allow. Any 1-3 leftover pixels go symmetrically to outer gaps.
        try:
            self.tool_frame.config(width=tool_w, height=h)
            self.tool_frame.pack_propagate(False)
            free = h - 3 * tool_h
            if free < 0:
                free = 0
            base = free // 4
            extra = free - 4 * base
            gaps = [base, base, base, base]
            if extra >= 1: gaps[0] += 1   # top
            if extra >= 2: gaps[3] += 1   # bottom (symmetric)
            if extra >= 3: gaps[1] += 1   # one inner gap
            btn_x = max(0, (tool_w - tool_sz) // 2)
            # Per-glyph optical correction: 📷 has its visual mass concentrated
            # at the bottom (the lens), so it appears slightly low even when
            # the bounding box is mathematically centered. Nudge up 1-2 px to
            # match the user's perception of a centered icon.
            cam_nudge = -1 if tool_h <= 16 else -2
            y = gaps[0]
            for i, btn in enumerate(tool_buttons):
                try:
                    btn.pack_forget()
                except tk.TclError:
                    pass
                # i==1 is the screenshot (camera) button
                y_off = cam_nudge if i == 1 else 0
                btn.place(x=btn_x, y=y + y_off, width=tool_sz, height=tool_h)
                y += tool_h + gaps[i + 1]
        except tk.TclError:
            pass

        # Remove old widget placements
        self.frame.delete("widgets")

        # Render gradient background (only canvas area, not panel)
        self._render_toolbar_bg(base_w, h)

        # Place buttons on canvas - tight layout. When dropdown arrows
        # are enabled we shift the button row UP so the arrows fit
        # below; the tool frame stays centred to `cy_tools`.
        arrow_h, arrow_gap = self._calc_arrow_dims(btn_s)
        if arrow_h:
            # Buttons up by half the arrow zone — arrows occupy the
            # bottom band, tool frame stays centred to mid-height.
            cy_buttons = (h - arrow_h - arrow_gap) // 2
        else:
            cy_buttons = h // 2
        cy_tools = h // 2
        x = padx + btn_s // 2

        btns = [self.btn_bn, self.btn_en, self.btn_read, self.btn_ai]
        button_xs = []
        for btn in btns:
            self.frame.create_window(x, cy_buttons, window=btn, tags="widgets")
            button_xs.append(x)
            x += btn_s + gap

        # Stash button x-centres + widget metrics so drawer code can
        # align its slide-out panel under the right button.
        self._btn_x_centres = list(button_xs)
        self._btn_size = btn_s
        self._toolbar_base_w = base_w
        self._toolbar_base_h = h
        # Re-position the active drawer (if one is open) so it stays
        # under the same button after a layout change.
        try:
            if getattr(self, "_drawer_active_kind", None):
                self._reposition_drawer()
        except Exception:
            pass

        # Place dropdown ▼ arrows directly below each button (if enabled
        # at this preset). Both `widgets` and `dropdown_arrows` tags so
        # the existing delete("widgets") cleans them up on relayout
        # AND a separate `dropdown_arrows` tag exists for drag hide/show.
        arrows = list(getattr(self, "_arrows", []))
        if arrow_h and arrows and len(arrows) == len(button_xs):
            arrow_y = cy_buttons + btn_s // 2 + arrow_gap + arrow_h // 2
            for arrow, x_center in zip(arrows, button_xs):
                try:
                    arrow.resize(width=btn_s, height=arrow_h)
                except Exception:
                    pass
                self.frame.create_window(
                    x_center, arrow_y, window=arrow,
                    tags=("widgets", "dropdown_arrows"))

        # Tool frame - tight: right after last button's edge
        tool_cx = x - btn_s // 2 + tool_w // 2
        self.frame.create_window(tool_cx, cy_tools,
                                 window=self.tool_frame, tags="widgets")

    def update_button_labels(self):
        """Update BN/EN button labels from current settings."""
        if hasattr(self, 'btn_bn'):
            lang1 = self.settings.get("btn1_lang", "bn-BD")
            self.btn_bn.set_display_label(lang1.split("-")[0].upper())
        if hasattr(self, 'btn_en'):
            lang2 = self.settings.get("btn2_lang", "en-US")
            self.btn_en.set_display_label(lang2.split("-")[0].upper())

    def apply_size_scaling(self):
        """Load icon path only."""
        self.icon_path = None
        new_logo = os.path.join(self.base_path, "DualVoicerLogo.ico")
        if os.path.exists(new_logo):
            self.icon_path = new_logo
        self.logo_img = None
        if self.icon_path:
            try:
                from PIL import Image
                img = Image.open(self.icon_path)
                self.logo_img = ctk.CTkImage(light_image=img, dark_image=img, size=(45, 45))
            except (OSError, tk.TclError): pass

    def apply_size_preset(self, preset=None):
        """Called from settings panel when size changes."""
        if preset:
            self.settings["size_preset"] = preset
        # Any open dropdown was anchored to the OLD button layout — close
        # it so it doesn't float in stale coordinates after relayout.
        self._close_active_dropdown()
        self._apply_window_size()
        self.save_settings()

    def update_size(self, value):
        pass
