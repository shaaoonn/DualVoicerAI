# ui/settings_panel.py
"""
Large settings window - 860x700.
All settings auto-save to self.settings dict (passed by reference from main.py).
Call: SettingsPanel(parent=app, app_ref=self)
"""
import customtkinter as ctk
import webbrowser
from config import (APP_NAME, APP_VERSION, SETTINGS_WINDOW_SIZE,
                    SETTINGS_MIN_SIZE, AI_MODELS, BACKEND_BASE)
from ui_components.language_data import GOOGLE_STT_LANGUAGES

class SettingsPanel(ctk.CTkToplevel):
    def __init__(self, parent, app_ref):
        super().__init__(parent)
        self.app = app_ref          # reference to VoiceTypingApp instance
        self.s  = app_ref.settings  # settings dict (live reference)

        self.title(f"{APP_NAME} \u2014 \u09b8\u09c7\u099f\u09bf\u0982\u09b8")
        self.geometry(SETTINGS_WINDOW_SIZE)
        self.minsize(*SETTINGS_MIN_SIZE)
        self.attributes("-topmost", False)

        self._active_tab = None
        self._tab_frames = {}
        self._nav_btns   = {}

        self._build_layout()
        self._show_tab("general")

    # -- Layout ---------------------------------------------------
    def _build_layout(self):
        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=190, corner_radius=0,
                                     fg_color="#161616")
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # App logo area
        ctk.CTkLabel(self.sidebar, text=APP_NAME,
                     font=("Segoe UI", 13, "bold"),
                     text_color="#FFFFFF").pack(pady=(20, 2))
        ctk.CTkLabel(self.sidebar, text=f"v{APP_VERSION}",
                     font=("Segoe UI", 9),
                     text_color="#555555").pack(pady=(0, 16))
        ctk.CTkFrame(self.sidebar, height=1, fg_color="#2A2A2A").pack(fill="x", padx=12, pady=4)

        # Nav buttons
        TABS = [
            ("\u2699\ufe0f  \u09b8\u09be\u09a7\u09be\u09b0\u09a3",       "general"),
            ("\U0001f310  \u09ad\u09be\u09b7\u09be",          "language"),
            ("\U0001f916  AI \u09b8\u09c7\u099f\u09bf\u0982\u09b8",     "ai"),
            ("\U0001f50a  \u099f\u09bf\u099f\u09bf\u098f\u09b8",        "tts"),
            ("\U0001f511  \u09b8\u09be\u09ac\u09b8\u09cd\u0995\u09cd\u09b0\u09bf\u09aa\u09b6\u09a8",  "subscription"),
            ("\u2139\ufe0f  \u09b8\u09ae\u09cd\u09aa\u09b0\u09cd\u0995\u09c7",      "about"),
        ]
        for label, key in TABS:
            btn = ctk.CTkButton(
                self.sidebar, text=label, anchor="w",
                fg_color="transparent", hover_color="#252525",
                font=("Segoe UI", 12), height=36,
                command=lambda k=key: self._show_tab(k)
            )
            btn.pack(fill="x", padx=8, pady=2)
            self._nav_btns[key] = btn

        # Footer buttons
        footer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=8, pady=12)
        ctk.CTkButton(footer, text="\u09b8\u0982\u09b0\u0995\u09cd\u09b7\u09a3", height=32,
                      command=self._save_and_close).pack(fill="x", pady=(0, 4))
        ctk.CTkButton(footer, text="\u09ac\u09a8\u09cd\u09a7 \u0995\u09b0\u09c1\u09a8", height=32,
                      fg_color="#2A2A2A", hover_color="#3A3A3A",
                      command=self.destroy).pack(fill="x")

        # Content area
        self.content_area = ctk.CTkFrame(self, corner_radius=0,
                                          fg_color="#141414")
        self.content_area.pack(side="right", fill="both", expand=True)

        # Build all tab frames (but only show one)
        self._build_general_tab()
        self._build_language_tab()
        self._build_ai_tab()
        self._build_tts_tab()
        self._build_subscription_tab()
        self._build_about_tab()

    def _show_tab(self, key: str):
        for k, frame in self._tab_frames.items():
            frame.pack_forget()
        if key in self._tab_frames:
            self._tab_frames[key].pack(fill="both", expand=True, padx=0, pady=0)
        for k, btn in self._nav_btns.items():
            btn.configure(fg_color="#1E3A5F" if k == key else "transparent")
        self._active_tab = key

    def _save_and_close(self):
        self._sync_textboxes()
        self.app.save_settings()
        self.destroy()

    def _sync_textboxes(self):
        """Read all textbox values into settings before save."""
        if hasattr(self, '_sys_box') and self._sys_box.winfo_exists():
            self.s["ai_system_prompt"] = self._sys_box.get("1.0", "end-1c").strip()
        if hasattr(self, '_img_sys_box') and self._img_sys_box.winfo_exists():
            self.s["image_system_prompt"] = self._img_sys_box.get("1.0", "end-1c").strip()
        if hasattr(self, '_kb_box') and self._kb_box.winfo_exists():
            self.s["knowledge_base"] = self._kb_box.get("1.0", "end-1c").strip()

    # -- Helper widgets --------------------------------------------
    def _scroll_frame(self, parent) -> ctk.CTkScrollableFrame:
        f = ctk.CTkScrollableFrame(parent, fg_color="transparent",
                                    scrollbar_fg_color="#1A1A1A")
        return f

    def _section(self, parent, title: str):
        ctk.CTkLabel(parent, text=title,
                     font=("Segoe UI", 12, "bold"),
                     text_color="#CCCCCC").pack(anchor="w", padx=28, pady=(18, 5))

    def _divider(self, parent):
        ctk.CTkFrame(parent, height=1, fg_color="#242424").pack(
            fill="x", padx=28, pady=6)

    def _card(self, parent) -> ctk.CTkFrame:
        c = ctk.CTkFrame(parent, fg_color="#1C1C1C", corner_radius=10)
        c.pack(fill="x", padx=28, pady=4)
        return c

    def _toggle_row(self, parent, label: str, key: str, on_change=None):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=7)
        ctk.CTkLabel(row, text=label,
                     font=("Segoe UI", 12)).pack(side="left")
        var = ctk.BooleanVar(value=self.s.get(key, True))
        def _cb():
            self.s[key] = var.get()
            if on_change: on_change()
        ctk.CTkSwitch(row, variable=var, text="", command=_cb).pack(side="right")
        return var

    def _slider_row(self, parent, label: str, key: str,
                    min_v: float, max_v: float, steps: int, on_change=None):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(6, 0))
        ctk.CTkLabel(row, text=label,
                     font=("Segoe UI", 11), text_color="#999999").pack(side="left")
        val_lbl = ctk.CTkLabel(row, text=f"{self.s.get(key, min_v):.2f}",
                                font=("Segoe UI", 10), text_color="#4FC3F7", width=40)
        val_lbl.pack(side="right")
        def _cb(v):
            self.s[key] = v
            val_lbl.configure(text=f"{v:.2f}")
            if on_change: on_change(v)
        sl = ctk.CTkSlider(parent, from_=min_v, to=max_v, number_of_steps=steps,
                            command=_cb, height=16)
        sl.set(self.s.get(key, min_v))
        sl.pack(fill="x", padx=16, pady=(2, 6))

    def _segmented_row(self, parent, label: str, key: str,
                        options: list, labels: list = None, on_change=None):
        """Radio-style segmented button row."""
        if labels is None: labels = options
        ctk.CTkLabel(parent, text=label,
                     font=("Segoe UI", 11), text_color="#999999").pack(
            anchor="w", padx=16, pady=(8, 4))
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 10))
        btns = {}
        current = str(self.s.get(key, options[0]))

        def _select(val):
            self.s[key] = val
            for v, b in btns.items():
                b.configure(fg_color="#1E3A5F" if v == val else "#2A2A2A",
                             hover_color="#2A5080" if v == val else "#383838")
            if on_change: on_change(val)

        for val, lbl in zip(options, labels):
            b = ctk.CTkButton(row, text=lbl, width=70, height=30,
                               fg_color="#1E3A5F" if val == current else "#2A2A2A",
                               hover_color="#2A5080" if val == current else "#383838",
                               font=("Segoe UI", 11),
                               command=lambda v=val: _select(v))
            b.pack(side="left", padx=3)
            btns[val] = b

    # -- TAB: General ----------------------------------------------
    def _build_general_tab(self):
        frame = self._scroll_frame(self.content_area)
        self._tab_frames["general"] = frame

        # Account card
        self._section(frame, "\U0001f464 \u0985\u09cd\u09af\u09be\u0995\u09be\u0989\u09a8\u09cd\u099f")
        acct = self._card(frame)
        plan = getattr(self.app, 'user_cache', {}).get('plan_type', 'Trial')
        is_premium = plan.lower() not in ('trial', 'expired')
        badge_color = "#1A4A1A" if is_premium else "#3A2A00"
        badge_text  = f"\u2713 {plan}" if is_premium else f"\u23f3 {plan}"
        ctk.CTkLabel(acct, text=badge_text, font=("Segoe UI", 13, "bold"),
                     fg_color=badge_color, corner_radius=6,
                     text_color="#AAFFAA" if is_premium else "#FFCC44"
                     ).pack(side="left", padx=16, pady=14)
        if hasattr(self.app, 'handle_logout'):
            ctk.CTkButton(acct, text="Logout", width=90, height=30,
                          fg_color="#3A3A3A", hover_color="#4A4A4A",
                          command=self.app.handle_logout).pack(side="right", padx=16)

        # Expiry info
        expiry = getattr(self.app, 'user_cache', {}).get('expiry_date', None)
        dev_ct  = getattr(self.app, 'device_count', 1)
        max_dev = getattr(self.app, 'max_devices', 1)
        if expiry:
            ctk.CTkLabel(frame, text=f"\u09ae\u09c7\u09df\u09be\u09a6: {expiry}  \u2022  \u09a1\u09bf\u09ad\u09be\u0987\u09b8: {dev_ct}/{max_dev}",
                         font=("Segoe UI", 10), text_color="#4CAF50"
                         ).pack(anchor="w", padx=28, pady=(2, 8))

        # Toggles
        self._section(frame, "\U0001f527 \u09b8\u09be\u09a7\u09be\u09b0\u09a3")
        toggle_card = self._card(frame)
        self._toggle_row(toggle_card, "Desktop \u0986\u0987\u0995\u09a8", "show_desktop_icon")
        self._divider(toggle_card)
        self._toggle_row(toggle_card, "Sound Effects", "sound_enabled",
                         on_change=getattr(self.app, 'toggle_sound', None))
        self._divider(toggle_card)
        self._toggle_row(toggle_card, "Button Labels", "show_labels",
                         on_change=getattr(self.app, 'toggle_labels', None))

        # Editor
        self._section(frame, "\U0001f4dd এডিটর")
        editor_card = self._card(frame)
        ctk.CTkButton(editor_card, text="\U0001f4dd এডিটর খুলুন",
                       width=180, height=34,
                       fg_color="#2A4A6A", hover_color="#3A5A7A",
                       font=("Segoe UI", 12),
                       command=lambda: self.app.open_editor_window()
                       ).pack(padx=16, pady=10)

        # UI Language switcher
        try:
            from i18n import get_available_languages
            ui_langs = get_available_languages()  # [("en","English"),("bn","Bengali (বাংলা)")]
        except Exception:
            ui_langs = [("en", "English"), ("bn", "Bengali (বাংলা)")]

        self._section(frame, "\U0001f5e3\ufe0f Interface Language")
        ui_card = self._card(frame)
        ui_lang_codes   = [c for c, _ in ui_langs]
        ui_lang_display = [n for _, n in ui_langs]
        cur_ui_lang = self.s.get("ui_language", "en")
        cur_ui_disp = ui_lang_display[ui_lang_codes.index(cur_ui_lang)] \
            if cur_ui_lang in ui_lang_codes else ui_lang_display[0]
        ui_var = ctk.StringVar(value=cur_ui_disp)

        def _on_ui_lang_change(v):
            if v in ui_lang_display:
                code = ui_lang_codes[ui_lang_display.index(v)]
                self.s["ui_language"] = code
                try:
                    from i18n import set_ui_language
                    set_ui_language(code)
                except Exception:
                    pass

        ctk.CTkComboBox(ui_card, variable=ui_var, values=ui_lang_display,
                        width=300, font=("Segoe UI", 11),
                        command=_on_ui_lang_change
                        ).pack(padx=16, pady=(12, 4))
        ctk.CTkLabel(ui_card,
                     text="Restart the app to fully apply the language change.",
                     font=("Segoe UI", 10), text_color="#888888"
                     ).pack(anchor="w", padx=16, pady=(0, 12))

        # Microphone
        self._section(frame, "\U0001f399\ufe0f \u09ae\u09be\u0987\u0995\u09cd\u09b0\u09cb\u09ab\u09cb\u09a8")
        mic_card = self._card(frame)
        mic_list = getattr(self.app, '_cached_mic_list', []) or ["Default Microphone"]
        mic_var = ctk.StringVar(value=mic_list[self.s.get("mic_index") or 0] if (self.s.get("mic_index") or 0) < len(mic_list) else mic_list[0])
        ctk.CTkComboBox(mic_card, variable=mic_var, values=mic_list,
                        width=500, font=("Segoe UI", 11),
                        command=lambda v: self.s.update(
                            {"mic_index": mic_list.index(v) if v in mic_list else 0})
                        ).pack(padx=16, pady=(14, 4))

        # Noise filter
        self._slider_row(mic_card, "Noise Filter", "noise_threshold",
                         50, 500, 90,
                         on_change=getattr(self.app, 'update_noise_threshold', None))
        # Pause labels
        pl = ctk.CTkFrame(mic_card, fg_color="transparent")
        pl.pack(fill="x", padx=16, pady=(0, 12))
        ctk.CTkLabel(pl, text="\u2190 \u09ae\u09be\u099d\u09c7 \u09ac\u09bf\u09b0\u09a4\u09bf", font=("Segoe UI", 9),
                     text_color="#555555").pack(side="left")
        ctk.CTkLabel(pl, text="\u0986\u09ac\u09be\u09b0 \u09b2\u09bf\u0996\u09bf \u2192", font=("Segoe UI", 9),
                     text_color="#555555").pack(side="right")

        # Appearance
        self._section(frame, "\U0001f3a8 Appearance & Behavior")
        appear = self._card(frame)
        self._slider_row(appear, "Idle Opacity",   "idle_opacity",  0.05, 1.0, 19,
                         on_change=getattr(self.app, 'update_idle_opacity', None))
        self._slider_row(appear, "Active Opacity", "max_opacity",   0.3,  1.0, 14,
                         on_change=getattr(self.app, 'update_max_opacity', None))
        self._segmented_row(appear, "Widget Size", "size_preset",
                             ["tiny", "small", "medium", "large", "xlarge"],
                             ["XS", "S", "M", "L", "XL"],
                             on_change=getattr(self.app, 'apply_size_preset', None))
        self._divider(appear)
        self._segmented_row(appear, "Auto Stop Timeout", "auto_timeout",
                             ["5", "10", "15", "30", "0"], ["5s", "10s", "15s", "30s", "\u221e"])
        self._segmented_row(appear, "Reading Speed", "reading_speed",
                             ["1.0", "1.5", "2.0", "2.5"], ["1x", "1.5x", "2x", "2.5x"])

        # Action buttons
        self._section(frame, "\U0001f6e0\ufe0f Actions")
        act = ctk.CTkFrame(frame, fg_color="transparent")
        act.pack(fill="x", padx=28, pady=(4, 20))
        if hasattr(self.app, '_silent_reset'):
            ctk.CTkButton(act, text="\u27f3  Reset Engine", width=160, height=36,
                          fg_color="#8B2020", hover_color="#AA2828",
                          command=self.app._silent_reset).pack(side="left", padx=(0, 8))
        if hasattr(self.app, 'check_for_update'):
            ctk.CTkButton(act, text=f"\u2191  \u0986\u09aa\u09a1\u09c7\u099f (v{APP_VERSION})", width=180, height=36,
                          fg_color="#4A1A7A", hover_color="#6A2A9A",
                          command=self.app.check_for_update).pack(side="left")

        # Screenshot save folder
        self._section(frame, "\U0001f4f7 Screenshot")
        ss_card = self._card(frame)
        ss_row = ctk.CTkFrame(ss_card, fg_color="transparent")
        ss_row.pack(fill="x", padx=16, pady=10)
        cur_dir = self.s.get("screenshot_save_dir", "")
        self._ss_label = ctk.CTkLabel(ss_row, text=cur_dir or "Not set",
                                       font=("Segoe UI", 10), text_color="#888888",
                                       width=350, anchor="w")
        self._ss_label.pack(side="left")

        def _pick_ss_dir():
            from tkinter import filedialog
            d = filedialog.askdirectory(title="Screenshot Save Folder")
            if d:
                self.s["screenshot_save_dir"] = d
                self._ss_label.configure(text=d)
        ctk.CTkButton(ss_row, text="Browse", width=80, height=28,
                      command=_pick_ss_dir).pack(side="right")

    # -- TAB: Language ---------------------------------------------
    def _build_language_tab(self):
        frame = self._scroll_frame(self.content_area)
        self._tab_frames["language"] = frame

        self._section(frame, "\U0001f310 \u09ad\u09df\u09c7\u09b8 \u099f\u09be\u0987\u09aa\u09bf\u0982 \u09ad\u09be\u09b7\u09be")
        ctk.CTkLabel(frame,
                     text="\u09aa\u09cd\u09b0\u09a4\u09bf\u099f\u09bf \u09ac\u09be\u099f\u09a8\u09c7\u09b0 \u099c\u09a8\u09cd\u09af \u0986\u09b2\u09be\u09a6\u09be \u09ad\u09be\u09b7\u09be \u09b8\u09bf\u09b2\u09c7\u0995\u09cd\u099f \u0995\u09b0\u09c1\u09a8\u0964 Google Speech API \u09ac\u09cd\u09af\u09ac\u09b9\u09be\u09b0 \u09b9\u09df\u0964",
                     font=("Segoe UI", 10), text_color="#666666").pack(anchor="w", padx=28)

        lang_display = [f"{name}  ({code})" for name, code in GOOGLE_STT_LANGUAGES]
        lang_codes   = [code for _, code in GOOGLE_STT_LANGUAGES]

        for btn_key, btn_label, default in [
            ("btn1_lang", "\U0001f399\ufe0f \u09ac\u09be\u099f\u09a8 \u09e7 (\u09ac\u09be\u09ae)", "bn-BD"),
            ("btn2_lang", "\U0001f399\ufe0f \u09ac\u09be\u099f\u09a8 \u09e8 (\u09ae\u09be\u099d)", "en-US"),
        ]:
            c = self._card(frame)
            ctk.CTkLabel(c, text=btn_label,
                         font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=16, pady=(12, 4))
            cur = self.s.get(btn_key, default)
            cur_disp = lang_display[lang_codes.index(cur)] if cur in lang_codes else lang_display[0]
            var = ctk.StringVar(value=cur_disp)
            ctk.CTkComboBox(c, variable=var, values=lang_display, width=540,
                            font=("Segoe UI", 11),
                            command=lambda v, k=btn_key: self.s.update(
                                {k: lang_codes[lang_display.index(v)] if v in lang_display else lang_codes[0]}
                            )).pack(padx=16, pady=(0, 14))

        ctk.CTkLabel(frame,
                     text="\U0001f4a1 \u09ad\u09be\u09b7\u09be \u09aa\u09b0\u09bf\u09ac\u09b0\u09cd\u09a4\u09a8 \u09a4\u09be\u09ce\u0995\u09cd\u09b7\u09a3\u09bf\u0995\u09ad\u09be\u09ac\u09c7 \u0995\u09be\u09b0\u09cd\u09af\u0995\u09b0 \u09b9\u09df\u0964",
                     font=("Segoe UI", 10), text_color="#555555").pack(
            anchor="w", padx=28, pady=(8, 20))

    # -- TAB: AI ---------------------------------------------------
    def _build_ai_tab(self):
        frame = self._scroll_frame(self.content_area)
        self._tab_frames["ai"] = frame

        self._section(frame, "\U0001f916 AI \u09b8\u09b9\u0995\u09be\u09b0\u09c0")
        ctk.CTkLabel(frame,
                     text="Ctrl+Shift+A: \u09b8\u09bf\u09b2\u09c7\u0995\u09cd\u099f\u09c7\u09a1 \u099f\u09c7\u0995\u09cd\u09b8\u099f\u09c7 AI  |  Ctrl+Shift+V: Smart Paste",
                     font=("Segoe UI", 10), text_color="#666666").pack(anchor="w", padx=28)
        self._divider(frame)

        # Enable toggle
        c = self._card(frame)
        self._toggle_row(c, "AI \u09b8\u0995\u09cd\u09b0\u09bf\u09df \u0995\u09b0\u09c1\u09a8", "ai_enabled")

        # Output format
        self._section(frame, "\u0986\u0989\u099f\u09aa\u09c1\u099f \u09ab\u09b0\u09ae\u09cd\u09af\u09be\u099f")
        fmt_c = self._card(frame)
        fmt_var = ctk.StringVar(value=self.s.get("ai_output_format", "plain"))
        for val, lbl, desc in [
            ("plain", "Plain Text", "\u0995\u09cb\u09a8\u09cb formatting \u09a8\u09c7\u0987 \u2014 \u09b8\u09b0\u09be\u09b8\u09b0\u09bf \u099f\u09c7\u0995\u09cd\u09b8\u099f"),
            ("rich",  "Rich (Markdown)", "**bold**, _italic_, \u2022 bullet \u09b8\u09b9"),
        ]:
            r = ctk.CTkFrame(fmt_c, fg_color="transparent")
            r.pack(fill="x", padx=16, pady=(10 if val == "plain" else 2, 10 if val == "rich" else 2))
            ctk.CTkRadioButton(r, text=lbl, variable=fmt_var, value=val,
                               font=("Segoe UI", 12),
                               command=lambda v=val: self.s.update({"ai_output_format": v})
                               ).pack(side="left")
            ctk.CTkLabel(r, text=desc, font=("Segoe UI", 10),
                         text_color="#555555").pack(side="left", padx=14)

        # Model
        self._section(frame, "AI \u09ae\u09a1\u09c7\u09b2")
        c2 = self._card(frame)
        model_vals = list(AI_MODELS.values())
        model_var  = ctk.StringVar(value=self.s.get("ai_model", model_vals[0]))
        ctk.CTkOptionMenu(c2, variable=model_var, values=model_vals, width=500,
                          command=lambda v: self.s.update({"ai_model": v})
                          ).pack(padx=16, pady=(14, 4))
        ctk.CTkLabel(c2, text="Gemini Flash = \u09a6\u09cd\u09b0\u09c1\u09a4 | GPT-4o Mini = \u09b8\u09cd\u09ae\u09be\u09b0\u09cd\u099f | Claude Haiku = \u09b8\u09c1\u09a8\u09bf\u09b0\u09cd\u09a6\u09bf\u09b7\u09cd\u099f",
                     font=("Segoe UI", 9), text_color="#555555").pack(anchor="w", padx=16, pady=(0, 12))

        # System instruction
        self._section(frame, "\u09b8\u09bf\u09b8\u09cd\u099f\u09c7\u09ae \u0987\u09a8\u09b8\u09cd\u099f\u09cd\u09b0\u09be\u0995\u09b6\u09a8")
        ctk.CTkLabel(frame,
                     text="AI-\u0995\u09c7 \u0995\u09c0\u09ad\u09be\u09ac\u09c7 \u0986\u099a\u09b0\u09a3 \u0995\u09b0\u09a4\u09c7 \u09b9\u09ac\u09c7 \u09ac\u09b2\u09c1\u09a8\u0964  '\u09b8\u09ac\u09b8\u09ae\u09df \u09ab\u09b0\u09cd\u09ae\u09be\u09b2 \u09ac\u09be\u0982\u09b2\u09be\u09df \u09b2\u09bf\u0996\u09ac\u09c7'",
                     font=("Segoe UI", 10), text_color="#555555").pack(anchor="w", padx=28, pady=(0, 6))
        self._sys_box = ctk.CTkTextbox(frame, height=130, font=("Segoe UI", 11),
                                  fg_color="#1A1A1A", border_color="#2A2A2A",
                                  border_width=1, wrap="word")
        self._sys_box.pack(fill="x", padx=28)
        self._sys_box.insert("1.0", self.s.get("ai_system_prompt",
                       "\u09a4\u09c1\u09ae\u09bf \u098f\u0995\u099c\u09a8 \u09a6\u0995\u09cd\u09b7 \u09ac\u09be\u0982\u09b2\u09be \u0993 \u0987\u0982\u09b0\u09c7\u099c\u09bf \u09b2\u09c7\u0996\u0995 \u09b8\u09b9\u0995\u09be\u09b0\u09c0\u0964 \u09b8\u0982\u0995\u09cd\u09b7\u09bf\u09aa\u09cd\u09a4 \u0989\u09a4\u09cd\u09a4\u09b0 \u09a6\u09be\u0993\u0964"))
        self._sys_box.bind("<KeyRelease>", lambda e: self.s.update(
            {"ai_system_prompt": self._sys_box.get("1.0", "end-1c").strip()}))

        # Image System Instruction
        self._section(frame, "\U0001f5bc\ufe0f ইমেজ সিস্টেম ইন্সট্রাকশন (স্ক্রিনশট AI)")
        ctk.CTkLabel(frame,
                     text="স্ক্রিনশট নিয়ে AI বাটন চাপলে এই ইন্সট্রাকশন ব্যবহার হবে।  খালি রাখলে ডিফল্ট ব্যবহার হবে।",
                     font=("Segoe UI", 10), text_color="#555555").pack(anchor="w", padx=28, pady=(0, 6))
        self._img_sys_box = ctk.CTkTextbox(frame, height=130, font=("Segoe UI", 11),
                                  fg_color="#1A1A20", border_color="#2A2A3A",
                                  border_width=1, wrap="word")
        self._img_sys_box.pack(fill="x", padx=28)
        self._img_sys_box.insert("1.0", self.s.get("image_system_prompt", ""))
        self._img_sys_box.bind("<KeyRelease>", lambda e: self.s.update(
            {"image_system_prompt": self._img_sys_box.get("1.0", "end-1c").strip()}))

        # Knowledge Base
        self._section(frame, "\U0001f4da \u09a8\u09b2\u09c7\u099c \u09ac\u09c7\u099c (Smart Paste-\u098f\u09b0 \u099c\u09a8\u09cd\u09af)")
        ctk.CTkLabel(frame,
                     text="Ctrl+Shift+V \u099a\u09be\u09aa\u09b2\u09c7 AI \u098f\u0987 \u09a4\u09a5\u09cd\u09af \u09ac\u09cd\u09af\u09ac\u09b9\u09be\u09b0 \u0995\u09b0\u09c7 \u0995\u09aa\u09bf \u0995\u09b0\u09be \u09ae\u09c7\u09b8\u09c7\u099c\u09c7\u09b0 \u0989\u09a4\u09cd\u09a4\u09b0 \u09a4\u09c8\u09b0\u09bf \u0995\u09b0\u09ac\u09c7\u0964\n"
                          "\u0989\u09a6\u09be\u09b9\u09b0\u09a3: \u0995\u09cb\u09b0\u09cd\u09b8\u09c7\u09b0 \u09a6\u09be\u09ae, \u0985\u09ab\u09bf\u09b8 \u09b8\u09ae\u09df, FAQ, \u09b0\u09bf\u099f\u09be\u09b0\u09cd\u09a8 \u09aa\u09b2\u09bf\u09b8\u09bf \u0987\u09a4\u09cd\u09af\u09be\u09a6\u09bf\u0964",
                     font=("Segoe UI", 10), text_color="#555555",
                     justify="left").pack(anchor="w", padx=28, pady=(0, 6))
        self._kb_box = ctk.CTkTextbox(frame, height=180, font=("Segoe UI", 11),
                                 fg_color="#141A14", border_color="#2A3A2A",
                                 border_width=1, wrap="word")
        self._kb_box.pack(fill="x", padx=28)
        self._kb_box.insert("1.0", self.s.get("knowledge_base", ""))
        self._kb_box.bind("<KeyRelease>", lambda e: self.s.update(
            {"knowledge_base": self._kb_box.get("1.0", "end-1c").strip()}))

        ctk.CTkLabel(frame,
                     text="\u2328\ufe0f  Ctrl+Shift+V  \u2192  \u0995\u09aa\u09bf \u0995\u09b0\u09be \u09ae\u09c7\u09b8\u09c7\u099c + \u09a8\u09b2\u09c7\u099c \u09ac\u09c7\u099c \u2192 AI reply paste \u09b9\u09ac\u09c7",
                     font=("Segoe UI", 10), text_color="#6C9EBF").pack(
            anchor="w", padx=28, pady=(8, 20))

    # -- TAB: TTS --------------------------------------------------
    def _build_tts_tab(self):
        frame = self._scroll_frame(self.content_area)
        self._tab_frames["tts"] = frame

        self._section(frame, "\U0001f50a Text-to-Speech \u09b8\u09c7\u099f\u09bf\u0982\u09b8")
        c = self._card(frame)
        self._toggle_row(c, "\u09ad\u09be\u09b7\u09be \u09b8\u09cd\u09ac\u09df\u0982\u0995\u09cd\u09b0\u09bf\u09df\u09ad\u09be\u09ac\u09c7 \u09b6\u09a8\u09be\u0995\u09cd\u09a4 \u0995\u09b0\u09c1\u09a8", "tts_auto_detect")
        ctk.CTkLabel(frame,
                     text="\u099a\u09be\u09b2\u09c1: typed text-\u098f\u09b0 \u09ad\u09be\u09b7\u09be detect \u0995\u09b0\u09c7 \u09b8\u09a0\u09bf\u0995 voice \u09ac\u09be\u099c\u09be\u09ac\u09c7\n"
                          "\u09ac\u09a8\u09cd\u09a7: \u09a8\u09bf\u099a \u09a5\u09c7\u0995\u09c7 manually voice \u099a\u09c1\u09a8 (\u09b8\u09ac \u09ad\u09be\u09b7\u09be\u09df \u0995\u09be\u099c \u09a8\u09be\u0993 \u0995\u09b0\u09a4\u09c7 \u09aa\u09be\u09b0\u09c7)",
                     font=("Segoe UI", 10), text_color="#555555",
                     justify="left").pack(anchor="w", padx=28, pady=(4, 16))
        # Reading speed
        c2 = self._card(frame)
        self._segmented_row(c2, "Reading Speed", "reading_speed",
                             ["1.0", "1.5", "2.0", "2.5"], ["1x", "1.5x", "2x", "2.5x"])

    # -- TAB: Subscription -----------------------------------------
    def _build_subscription_tab(self):
        frame = self._scroll_frame(self.content_area)
        self._tab_frames["subscription"] = frame

        self._section(frame, "\U0001f511 \u09aa\u09cd\u09b2\u09cd\u09af\u09be\u09a8 \u0993 \u09b8\u09be\u09ac\u09b8\u09cd\u0995\u09cd\u09b0\u09bf\u09aa\u09b6\u09a8")
        c = self._card(frame)
        plan = getattr(self.app, 'user_cache', {}).get('plan_type', 'Trial')
        ctk.CTkLabel(c, text=f"\u09ac\u09b0\u09cd\u09a4\u09ae\u09be\u09a8 \u09aa\u09cd\u09b2\u09cd\u09af\u09be\u09a8: {plan}",
                     font=("Segoe UI", 14, "bold")).pack(padx=16, pady=(16, 4))

        # Plans table
        plans = [
            ("\u09ab\u09cd\u09b0\u09bf", "\u09f3\u09e6", "Voice typing \u0986\u099c\u09c0\u09ac\u09a8", "\u2705"),
            ("\u09ac\u09c7\u09b8\u09bf\u0995", "\u09f3\u09e7\u09ef\u09ef/\u09ae\u09be\u09b8", "AI 200 calls/day, 2 PC", ""),
            ("\u09aa\u09cd\u09b0\u09cb", "\u09f3\u09e9\u09ef\u09ef/\u09ae\u09be\u09b8", "AI \u0986\u09a8\u09b2\u09bf\u09ae\u09bf\u099f\u09c7\u09a1, 3 PC", "\u2b50"),
            ("\u099f\u09bf\u09ae", "\u09f3\u09ee\u09ef\u09ef/\u09ae\u09be\u09b8", "AI \u0986\u09a8\u09b2\u09bf\u09ae\u09bf\u099f\u09c7\u09a1, 10 PC", ""),
        ]
        for pname, price, features, badge in plans:
            pr = ctk.CTkFrame(c, fg_color="#1E1E1E", corner_radius=6)
            pr.pack(fill="x", padx=16, pady=3)
            ctk.CTkLabel(pr, text=f"{badge} {pname}",
                         font=("Segoe UI", 11, "bold"), width=80).pack(side="left", padx=12, pady=8)
            ctk.CTkLabel(pr, text=price,
                         font=("Segoe UI", 11), text_color="#4FC3F7", width=100).pack(side="left")
            ctk.CTkLabel(pr, text=features,
                         font=("Segoe UI", 10), text_color="#888888").pack(side="left", padx=8)

        ctk.CTkButton(c, text="\u09b8\u09be\u09ac\u09b8\u09cd\u0995\u09cd\u09b0\u09be\u0987\u09ac \u0995\u09b0\u09c1\u09a8 \u2192", height=36,
                      fg_color="#1A5A1A", hover_color="#2A7A2A",
                      command=lambda: webbrowser.open(f"{BACKEND_BASE}/pricing")
                      ).pack(fill="x", padx=16, pady=(12, 16))

    # -- TAB: About ------------------------------------------------
    def _build_about_tab(self):
        frame = self._scroll_frame(self.content_area)
        self._tab_frames["about"] = frame

        ctk.CTkLabel(frame, text=APP_NAME, font=("Segoe UI", 22, "bold")).pack(pady=(40, 4))
        ctk.CTkLabel(frame, text=f"Version {APP_VERSION}", font=("Segoe UI", 12),
                     text_color="#777777").pack()
        ctk.CTkLabel(frame, text="Powered by EJOSB IT\nejobsit.com",
                     font=("Segoe UI", 11), text_color="#888888",
                     justify="center").pack(pady=(12, 4))
        ctk.CTkButton(frame, text="\u0993\u09df\u09c7\u09ac\u09b8\u09be\u0987\u099f \u09ad\u09bf\u099c\u09bf\u099f \u0995\u09b0\u09c1\u09a8",
                      command=lambda: webbrowser.open("https://ejobsit.com")
                      ).pack(pady=8)
        ctk.CTkLabel(frame, text="\u00a9 2025-2026 EJOSB IT \u2022 Developed by Ahsanullah Shaon",
                     font=("Segoe UI", 9), text_color="#444444").pack(pady=(20, 4))
