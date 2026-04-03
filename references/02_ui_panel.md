# Reference 02: Settings Panel — Full Spec (860×700)
**Large desktop-app style window — NOT small like old Dual Voicer**

---

## Window Spec

```
Size:     860×700 (resizable, minsize 720×580)
Style:    Dark theme (customtkinter dark)
Layout:   Left sidebar (190px) + Right scrollable content
Title:    [APP_NAME] — সেটিংস
Position: Centered on screen
Modal:    No (can work while open)
```

## Sidebar Tabs

```python
TABS = [
    ("⚙️  সাধারণ",       "general"),       # Microphone, sound, opacity etc.
    ("🌐  ভাষা",          "language"),      # BTN1 + BTN2 language selection
    ("🤖  AI সেটিংস",     "ai"),            # AI features + knowledge base
    ("🔊  টিটিএস",        "tts"),           # TTS auto-detect + voice picker
    ("🔑  সাবস্ক্রিপশন",  "subscription"),  # Plan info + login/logout
    ("ℹ️  সম্পর্কে",      "about"),         # Version, credits
]
DEFAULT_TAB = "general"
```

## File: `ui/settings_panel.py`

```python
# ui/settings_panel.py
"""
Large settings window — 860×700.
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

        self.title(f"{APP_NAME} — সেটিংস")
        self.geometry(SETTINGS_WINDOW_SIZE)
        self.minsize(*SETTINGS_MIN_SIZE)
        self.attributes("-topmost", False)

        self._active_tab = None
        self._tab_frames = {}
        self._nav_btns   = {}

        self._build_layout()
        self._show_tab("general")

    # ── Layout ───────────────────────────────────────────
    def _build_layout(self):
        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=190, corner_radius=0,
                                     fg_color="#161616")
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # App logo area
        ctk.CTkLabel(self.sidebar, text=APP_NAME,
                     font=("Segoe UI", 13, "bold"),
                     text_color="#FFFFFF").pack(pady=(20,2))
        ctk.CTkLabel(self.sidebar, text=f"v{APP_VERSION}",
                     font=("Segoe UI", 9),
                     text_color="#555555").pack(pady=(0,16))
        ctk.CTkFrame(self.sidebar, height=1, fg_color="#2A2A2A").pack(fill="x", padx=12, pady=4)

        # Nav buttons
        TABS = [
            ("⚙️  সাধারণ",       "general"),
            ("🌐  ভাষা",          "language"),
            ("🤖  AI সেটিংস",     "ai"),
            ("🔊  টিটিএস",        "tts"),
            ("🔑  সাবস্ক্রিপশন",  "subscription"),
            ("ℹ️  সম্পর্কে",      "about"),
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
        ctk.CTkButton(footer, text="সংরক্ষণ", height=32,
                      command=self._save_and_close).pack(fill="x", pady=(0,4))
        ctk.CTkButton(footer, text="বন্ধ করুন", height=32,
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
        self.app.save_settings()
        self.destroy()

    # ── Helper widgets ────────────────────────────────────
    def _scroll_frame(self, parent) -> ctk.CTkScrollableFrame:
        f = ctk.CTkScrollableFrame(parent, fg_color="transparent",
                                    scrollbar_fg_color="#1A1A1A")
        return f

    def _section(self, parent, title: str):
        ctk.CTkLabel(parent, text=title,
                     font=("Segoe UI", 12, "bold"),
                     text_color="#CCCCCC").pack(anchor="w", padx=28, pady=(18,5))

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
        row.pack(fill="x", padx=16, pady=(6,0))
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
        sl.pack(fill="x", padx=16, pady=(2,6))

    def _segmented_row(self, parent, label: str, key: str,
                        options: list, labels: list = None):
        """Radio-style segmented button row."""
        if labels is None: labels = options
        ctk.CTkLabel(parent, text=label,
                     font=("Segoe UI", 11), text_color="#999999").pack(
            anchor="w", padx=16, pady=(8,4))
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0,10))
        btns = {}
        current = str(self.s.get(key, options[0]))

        def _select(val):
            self.s[key] = val
            for v, b in btns.items():
                b.configure(fg_color="#1E3A5F" if v == val else "#2A2A2A",
                             hover_color="#2A5080" if v == val else "#383838")

        for val, lbl in zip(options, labels):
            b = ctk.CTkButton(row, text=lbl, width=70, height=30,
                               fg_color="#1E3A5F" if val == current else "#2A2A2A",
                               hover_color="#2A5080" if val == current else "#383838",
                               font=("Segoe UI", 11),
                               command=lambda v=val: _select(v))
            b.pack(side="left", padx=3)
            btns[val] = b

    # ── TAB: সাধারণ ──────────────────────────────────────
    def _build_general_tab(self):
        frame = self._scroll_frame(self.content_area)
        self._tab_frames["general"] = frame

        # Account card
        self._section(frame, "👤 অ্যাকাউন্ট")
        acct = self._card(frame)
        plan = getattr(self.app, 'user_cache', {}).get('plan_type', 'Trial')
        is_premium = plan.lower() not in ('trial', 'expired')
        badge_color = "#1A4A1A" if is_premium else "#3A2A00"
        badge_text  = f"✓ {plan}" if is_premium else f"⏳ {plan}"
        ctk.CTkLabel(acct, text=badge_text, font=("Segoe UI", 13, "bold"),
                     fg_color=badge_color, corner_radius=6,
                     text_color="#AAFFAA" if is_premium else "#FFCC44"
                     ).pack(side="left", padx=16, pady=14)
        ctk.CTkButton(acct, text="Logout", width=90, height=30,
                      fg_color="#3A3A3A", hover_color="#4A4A4A",
                      command=self.app.handle_logout).pack(side="right", padx=16)

        # Expiry info
        expiry = getattr(self.app, 'user_cache', {}).get('expiry_date', None)
        dev_ct  = getattr(self.app, 'device_count', 1)
        max_dev = getattr(self.app, 'max_devices', 1)
        if expiry:
            ctk.CTkLabel(frame, text=f"মেয়াদ: {expiry}  •  ডিভাইস: {dev_ct}/{max_dev}",
                         font=("Segoe UI", 10), text_color="#4CAF50"
                         ).pack(anchor="w", padx=28, pady=(2,8))

        # Toggles
        self._section(frame, "🔧 সাধারণ")
        toggle_card = self._card(frame)
        self._toggle_row(toggle_card, "Desktop আইকন", "show_desktop_icon")
        self._divider(toggle_card)
        self._toggle_row(toggle_card, "Sound Effects", "sound_enabled",
                         on_change=self.app.toggle_sound)

        # Microphone
        self._section(frame, "🎙️ মাইক্রোফোন")
        mic_card = self._card(frame)
        mic_list = [m["name"] for m in getattr(self.app, '_mic_cache', [])] or ["Default Microphone"]
        mic_var = ctk.StringVar(value=mic_list[self.s.get("mic_index") or 0])
        ctk.CTkComboBox(mic_card, variable=mic_var, values=mic_list,
                        width=500, font=("Segoe UI", 11),
                        command=lambda v: self.s.update(
                            {"mic_index": mic_list.index(v) if v in mic_list else 0})
                        ).pack(padx=16, pady=(14,4))

        # Noise filter
        self._slider_row(mic_card, "Noise Filter", "noise_threshold",
                         50, 500, 90, on_change=self.app.update_noise_threshold)
        # Pause labels
        pl = ctk.CTkFrame(mic_card, fg_color="transparent")
        pl.pack(fill="x", padx=16, pady=(0,12))
        ctk.CTkLabel(pl, text="← মাঝে বিরতি", font=("Segoe UI", 9),
                     text_color="#555555").pack(side="left")
        ctk.CTkLabel(pl, text="আবার লিখি →", font=("Segoe UI", 9),
                     text_color="#555555").pack(side="right")

        # Appearance
        self._section(frame, "🎨 Appearance & Behavior")
        appear = self._card(frame)
        self._slider_row(appear, "Idle Opacity",   "idle_opacity",  0.05, 1.0, 19,
                         on_change=self.app.update_idle_opacity)
        self._slider_row(appear, "Active Opacity", "max_opacity",   0.3,  1.0, 14,
                         on_change=self.app.update_max_opacity)
        self._slider_row(appear, "Widget Size",    "scale",         0.5,  2.0, 15,
                         on_change=self.app.update_size)
        self._divider(appear)
        self._segmented_row(appear, "Auto Stop Timeout", "auto_timeout",
                             ["5","10","15","30","0"], ["5s","10s","15s","30s","∞"])
        self._segmented_row(appear, "Reading Speed", "reading_speed",
                             ["1.0","1.5","2.0","2.5"], ["1x","1.5x","2x","2.5x"])

        # Action buttons
        self._section(frame, "🛠️ Actions")
        act = ctk.CTkFrame(frame, fg_color="transparent")
        act.pack(fill="x", padx=28, pady=(4,20))
        ctk.CTkButton(act, text="⟳  Reset Engine", width=160, height=36,
                      fg_color="#8B2020", hover_color="#AA2828",
                      command=self.app._silent_reset).pack(side="left", padx=(0,8))
        ctk.CTkButton(act, text=f"↑  আপডেট (v{APP_VERSION})", width=180, height=36,
                      fg_color="#4A1A7A", hover_color="#6A2A9A",
                      command=self.app.check_for_update).pack(side="left")

    # ── TAB: ভাষা ─────────────────────────────────────────
    def _build_language_tab(self):
        frame = self._scroll_frame(self.content_area)
        self._tab_frames["language"] = frame

        self._section(frame, "🌐 ভয়েস টাইপিং ভাষা")
        ctk.CTkLabel(frame,
                     text="প্রতিটি বাটনের জন্য আলাদা ভাষা সিলেক্ট করুন। Google Speech API ব্যবহার হয়।",
                     font=("Segoe UI", 10), text_color="#666666").pack(anchor="w", padx=28)

        lang_display = [f"{name}  ({code})" for name, code in GOOGLE_STT_LANGUAGES]
        lang_codes   = [code for _, code in GOOGLE_STT_LANGUAGES]

        for btn_key, btn_label, default in [
            ("btn1_lang", "🎙️ বাটন ১ (বাম)", "bn-BD"),
            ("btn2_lang", "🎙️ বাটন ২ (মাঝ)", "en-US"),
        ]:
            c = self._card(frame)
            ctk.CTkLabel(c, text=btn_label,
                         font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=16, pady=(12,4))
            cur = self.s.get(btn_key, default)
            cur_disp = lang_display[lang_codes.index(cur)] if cur in lang_codes else lang_display[0]
            var = ctk.StringVar(value=cur_disp)
            ctk.CTkComboBox(c, variable=var, values=lang_display, width=540,
                            font=("Segoe UI", 11),
                            command=lambda v, k=btn_key: self.s.update(
                                {k: lang_codes[lang_display.index(v)] if v in lang_display else lang_codes[0]}
                            )).pack(padx=16, pady=(0,14))

        ctk.CTkLabel(frame,
                     text="💡 ভাষা পরিবর্তন তাৎক্ষণিকভাবে কার্যকর হয়।",
                     font=("Segoe UI", 10), text_color="#555555").pack(
            anchor="w", padx=28, pady=(8, 20))

    # ── TAB: AI সেটিংস ────────────────────────────────────
    def _build_ai_tab(self):
        frame = self._scroll_frame(self.content_area)
        self._tab_frames["ai"] = frame

        self._section(frame, "🤖 AI সহকারী")
        ctk.CTkLabel(frame,
                     text="Ctrl+Shift+A: সিলেক্টেড টেক্সটে AI  |  Ctrl+Shift+V: Smart Paste",
                     font=("Segoe UI", 10), text_color="#666666").pack(anchor="w", padx=28)
        self._divider(frame)

        # Enable toggle
        c = self._card(frame)
        self._toggle_row(c, "AI সক্রিয় করুন", "ai_enabled")

        # Output format
        self._section(frame, "আউটপুট ফরম্যাট")
        fmt_c = self._card(frame)
        fmt_var = ctk.StringVar(value=self.s.get("ai_output_format", "plain"))
        for val, lbl, desc in [
            ("plain", "Plain Text", "কোনো formatting নেই — সরাসরি টেক্সট"),
            ("rich",  "Rich (Markdown)", "**bold**, _italic_, • bullet সহ"),
        ]:
            r = ctk.CTkFrame(fmt_c, fg_color="transparent")
            r.pack(fill="x", padx=16, pady=(10 if val=="plain" else 2, 10 if val=="rich" else 2))
            ctk.CTkRadioButton(r, text=lbl, variable=fmt_var, value=val,
                               font=("Segoe UI", 12),
                               command=lambda v=val: self.s.update({"ai_output_format": v})
                               ).pack(side="left")
            ctk.CTkLabel(r, text=desc, font=("Segoe UI", 10),
                         text_color="#555555").pack(side="left", padx=14)

        # Model
        self._section(frame, "AI মডেল")
        c2 = self._card(frame)
        model_vals = list(AI_MODELS.values())
        model_var  = ctk.StringVar(value=self.s.get("ai_model", model_vals[0]))
        ctk.CTkOptionMenu(c2, variable=model_var, values=model_vals, width=500,
                          command=lambda v: self.s.update({"ai_model": v})
                          ).pack(padx=16, pady=(14,4))
        ctk.CTkLabel(c2, text="Gemini Flash = দ্রুত | GPT-4o Mini = স্মার্ট | Claude Haiku = সুনির্দিষ্ট",
                     font=("Segoe UI", 9), text_color="#555555").pack(anchor="w", padx=16, pady=(0,12))

        # System instruction
        self._section(frame, "সিস্টেম ইনস্ট্রাকশন")
        ctk.CTkLabel(frame,
                     text="AI-কে কীভাবে আচরণ করতে হবে বলুন।  'সবসময় ফর্মাল বাংলায় লিখবে'",
                     font=("Segoe UI", 10), text_color="#555555").pack(anchor="w", padx=28, pady=(0,6))
        sys_box = ctk.CTkTextbox(frame, height=130, font=("Segoe UI", 11),
                                  fg_color="#1A1A1A", border_color="#2A2A2A",
                                  border_width=1, wrap="word")
        sys_box.pack(fill="x", padx=28)
        sys_box.insert("1.0", self.s.get("ai_system_prompt",
                       "তুমি একজন দক্ষ বাংলা ও ইংরেজি লেখক সহকারী। সংক্ষিপ্ত উত্তর দাও।"))
        sys_box.bind("<FocusOut>", lambda e: self.s.update(
            {"ai_system_prompt": sys_box.get("1.0","end-1c").strip()}))

        # Knowledge Base
        self._section(frame, "📚 নলেজ বেজ (Smart Paste-এর জন্য)")
        ctk.CTkLabel(frame,
                     text="Ctrl+Shift+V চাপলে AI এই তথ্য ব্যবহার করে কপি করা মেসেজের উত্তর তৈরি করবে।\n"
                          "উদাহরণ: কোর্সের দাম, অফিস সময়, FAQ, রিটার্ন পলিসি ইত্যাদি।",
                     font=("Segoe UI", 10), text_color="#555555",
                     justify="left").pack(anchor="w", padx=28, pady=(0,6))
        kb_box = ctk.CTkTextbox(frame, height=180, font=("Segoe UI", 11),
                                 fg_color="#141A14", border_color="#2A3A2A",
                                 border_width=1, wrap="word")
        kb_box.pack(fill="x", padx=28)
        kb_box.insert("1.0", self.s.get("knowledge_base", ""))
        kb_box.bind("<FocusOut>", lambda e: self.s.update(
            {"knowledge_base": kb_box.get("1.0","end-1c").strip()}))

        ctk.CTkLabel(frame,
                     text="⌨️  Ctrl+Shift+V  →  কপি করা মেসেজ + নলেজ বেজ → AI reply paste হবে",
                     font=("Segoe UI", 10), text_color="#6C9EBF").pack(
            anchor="w", padx=28, pady=(8,20))

    # ── TAB: টিটিএস ──────────────────────────────────────
    def _build_tts_tab(self):
        frame = self._scroll_frame(self.content_area)
        self._tab_frames["tts"] = frame

        self._section(frame, "🔊 Text-to-Speech সেটিংস")
        c = self._card(frame)
        self._toggle_row(c, "ভাষা স্বয়ংক্রিয়ভাবে শনাক্ত করুন", "tts_auto_detect")
        ctk.CTkLabel(frame,
                     text="চালু: typed text-এর ভাষা detect করে সঠিক voice বাজাবে\n"
                          "বন্ধ: নিচ থেকে manually voice চুন (সব ভাষায় কাজ নাও করতে পারে)",
                     font=("Segoe UI", 10), text_color="#555555",
                     justify="left").pack(anchor="w", padx=28, pady=(4,16))
        # Reading speed (same as general tab, duplicated for convenience)
        c2 = self._card(frame)
        self._segmented_row(c2, "Reading Speed", "reading_speed",
                             ["1.0","1.5","2.0","2.5"], ["1x","1.5x","2x","2.5x"])

    # ── TAB: সাবস্ক্রিপশন ────────────────────────────────
    def _build_subscription_tab(self):
        frame = self._scroll_frame(self.content_area)
        self._tab_frames["subscription"] = frame

        self._section(frame, "🔑 প্ল্যান ও সাবস্ক্রিপশন")
        c = self._card(frame)
        plan = getattr(self.app, 'user_cache', {}).get('plan_type', 'Trial')
        ctk.CTkLabel(c, text=f"বর্তমান প্ল্যান: {plan}",
                     font=("Segoe UI", 14, "bold")).pack(padx=16, pady=(16,4))

        # Plans table
        plans = [
            ("ফ্রি", "₹0", "Voice typing আজীবন", "✅"),
            ("বেসিক", "৳199/মাস", "AI 200 calls/day, 2 PC", ""),
            ("প্রো", "৳399/মাস", "AI আনলিমিটেড, 3 PC", "⭐"),
            ("টিম", "৳899/মাস", "AI আনলিমিটেড, 10 PC", ""),
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

        ctk.CTkButton(c, text="সাবস্ক্রাইব করুন →", height=36,
                      fg_color="#1A5A1A", hover_color="#2A7A2A",
                      command=lambda: webbrowser.open(f"{BACKEND_BASE}/pricing")
                      ).pack(fill="x", padx=16, pady=(12,16))

    # ── TAB: সম্পর্কে ─────────────────────────────────────
    def _build_about_tab(self):
        frame = self._scroll_frame(self.content_area)
        self._tab_frames["about"] = frame

        ctk.CTkLabel(frame, text=APP_NAME, font=("Segoe UI", 22, "bold")).pack(pady=(40,4))
        ctk.CTkLabel(frame, text=f"Version {APP_VERSION}", font=("Segoe UI", 12),
                     text_color="#777777").pack()
        ctk.CTkLabel(frame, text="Powered by EJOSB IT\nejobsit.com",
                     font=("Segoe UI", 11), text_color="#888888",
                     justify="center").pack(pady=(12,4))
        ctk.CTkButton(frame, text="ওয়েবসাইট ভিজিট করুন",
                      command=lambda: webbrowser.open("https://ejobsit.com")
                      ).pack(pady=8)
        ctk.CTkLabel(frame, text="© 2025-2026 EJOSB IT • Developed by Ahsanullah Shaon",
                     font=("Segoe UI", 9), text_color="#444444").pack(pady=(20,4))
```

## Integration in main.py

```python
# Replace open_settings_panel() entirely:
def open_settings_panel(self):
    # Freemium gate — settings locked if trial expired
    if not self.freemium.can_use("settings", self):
        # Still open but with lock overlay
        # (Handled inside SettingsPanel if needed)
        pass
    from ui.settings_panel import SettingsPanel
    if not hasattr(self, '_settings_win') or not self._settings_win.winfo_exists():
        self._settings_win = SettingsPanel(parent=self, app_ref=self)
    self._settings_win.focus()
    self._settings_win.lift()
```
