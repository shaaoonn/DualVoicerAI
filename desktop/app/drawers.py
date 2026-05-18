"""Embedded drawer system — BN/EN/SND/AI dropdown drawers.

The ▼ arrow under each of the four main spectrum buttons opens a
compact drawer that slides down from the toolbar showing per-button
options (voice mode, TTS source, AI settings). The drawers share a
common geometry resize protocol with the toolbar — opening grows the
window, closing shrinks it back.

Owned state:
  - _drawer_widget, _drawer_active_kind, _drawer_host
  - _active_dropdown (legacy floating-popup cleanup)
"""

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from app.constants import (
    DRAWER_ACTIVE,
    DRAWER_BG,
    DRAWER_BORDER,
    DRAWER_HEADER,
    DRAWER_MUTED,
    DRAWER_ROW_BG,
    DRAWER_ROW_HV,
    DRAWER_TEXT,
)


class DrawerMixin:
    """Mixed into VoiceTypingApp — BN/EN/SND/AI drawer system."""

    def _close_active_dropdown(self):
        # Close any embedded slide-out drawer (BN/EN/SND/AI)
        try:
            if getattr(self, "_drawer_widget", None) is not None:
                self._close_drawer()
        except Exception:
            pass
        # Legacy floating-popup cleanup (kept for safety)
        p = getattr(self, "_active_dropdown", None)
        if p is None:
            return
        try:
            if hasattr(p, "winfo_exists") and p.winfo_exists():
                p.destroy()
        except Exception:
            pass
        self._active_dropdown = None
        # Reset any active-arrow highlight
        for a in getattr(self, "_arrows", []) or []:
            try: a.set_active(False)
            except Exception: pass

    def _open_bn_dropdown(self):
        self._toggle_voice_drawer(btn_idx=1)

    def _open_en_dropdown(self):
        self._toggle_voice_drawer(btn_idx=2)

    def _open_read_dropdown(self):
        self._toggle_tts_drawer()

    def _open_ai_dropdown(self):
        self._toggle_ai_drawer()

    def _push_screenshot_to_drawer(self, b64_url: str):
        """Push a freshly-captured screenshot into the AI drawer's
        image slot if the drawer is currently open."""
        drawer = getattr(self, "_drawer_widget", None)
        if (self._drawer_active_kind == "ai"
                and drawer is not None
                and hasattr(drawer, "set_image_from_b64")):
            try:
                drawer.set_image_from_b64(b64_url, label="Screenshot")
            except Exception as e:
                print(f"[SCREENSHOT] push to drawer failed: {e}")


    def _apply_voice_mode(self, btn_idx: int, mode: str):
        """Sync derived state when user picks a voice-mode row."""
        own_lang = self.settings.get(
            f"btn{btn_idx}_lang", "bn-BD" if btn_idx == 1 else "en-US")
        other_lang = self.settings.get(
            f"btn{3 - btn_idx}_lang",
            "en-US" if btn_idx == 1 else "bn-BD")
        self.settings[f"btn{btn_idx}_voice_mode"] = mode
        if mode == "normal":
            self.settings[f"btn{btn_idx}_translate_enabled"] = False
        elif mode == "ai_polish":
            self.settings[f"btn{btn_idx}_translate_enabled"] = True
            self.settings[f"btn{btn_idx}_translate_from"]    = own_lang
        elif mode == "ai_translate":
            self.settings[f"btn{btn_idx}_translate_enabled"] = True
            self.settings[f"btn{btn_idx}_translate_from"]    = other_lang
        try: self.save_settings()
        except Exception as e: print(f"[VOICE-MODE] save failed: {e}")
        try: self._refresh_translation_state()
        except Exception as e: print(f"[VOICE-MODE] refresh failed: {e}")
        print(f"[VOICE-MODE] btn{btn_idx} = {mode}")

    def _apply_tts_mode(self, mode: str):
        """Sync derived state when user picks a TTS source row."""
        try:
            from ai_engine.tts_detector import LANG_TO_VOICE, DEFAULT_VOICE
        except Exception:
            LANG_TO_VOICE, DEFAULT_VOICE = {}, "en-US-JennyNeural"

        def _voice_for(lang: str) -> str:
            prefix = (lang or "").split("-")[0].lower()
            return LANG_TO_VOICE.get(prefix, DEFAULT_VOICE)

        self.settings["tts_source_mode"] = mode
        if mode == "auto":
            self.settings["tts_auto_detect"] = True
        elif mode == "btn1":
            self.settings["tts_auto_detect"] = False
            self.settings["tts_voice"] = _voice_for(
                self.settings.get("btn1_lang", "bn-BD"))
        elif mode == "btn2":
            self.settings["tts_auto_detect"] = False
            self.settings["tts_voice"] = _voice_for(
                self.settings.get("btn2_lang", "en-US"))
        try: self.save_settings()
        except Exception as e: print(f"[TTS-MODE] save failed: {e}")
        print(f"[TTS-MODE] {mode} -> voice={self.settings.get('tts_voice')}")

    # ─── Embedded drawer system ────────────────────────────────────

    # Drawer palette — class-attribute aliases of the module-level
    # constants in app.constants. Existing `self._DRAWER_BG` references
    # in mixins / call-sites resolve to these.
    _DRAWER_BG     = DRAWER_BG
    _DRAWER_HEADER = DRAWER_HEADER
    _DRAWER_ROW_BG = DRAWER_ROW_BG
    _DRAWER_ROW_HV = DRAWER_ROW_HV
    _DRAWER_ACTIVE = DRAWER_ACTIVE
    _DRAWER_TEXT   = DRAWER_TEXT
    _DRAWER_MUTED  = DRAWER_MUTED
    _DRAWER_BORDER = DRAWER_BORDER

    def _current_drawer_height(self) -> int:
        """Pixel height the drawer is currently consuming (0 if closed)."""
        if self._drawer_widget is None:
            return 0
        try:
            return self._drawer_widget.winfo_reqheight()
        except Exception:
            return 0

    def _close_drawer(self):
        """Tear down any open drawer + restore Toplevel size."""
        if self._drawer_widget is None:
            return
        was_ai = (self._drawer_active_kind == "ai")
        # Reset arrow active highlight
        for arrow in (getattr(self, "_arrows", []) or []):
            try: arrow.set_active(False)
            except Exception: pass
        try:
            self._drawer_widget.destroy()
        except Exception:
            pass
        self._drawer_widget = None
        self._drawer_active_kind = None
        # Re-pack drawer host with zero height
        try:
            self._drawer_host.configure(height=0)
        except Exception:
            pass
        # Restore Toplevel geometry to base size
        self._restore_geometry_no_drawer()

        # AI drawer borrowed keyboard focus by stripping
        # WS_EX_NOACTIVATE — put it back so subsequent toolbar
        # clicks no longer steal focus from the user's foreground app,
        # and hand foreground back to whatever window they were using
        # before opening the drawer. Use the AttachThreadInput helper
        # so SetForegroundWindow isn't blocked by Windows' anti-focus-
        # stealing guard.
        if was_ai:
            self._toggle_no_activate(True)
            prev = getattr(self, "_ai_prev_foreground", None)
            if prev and not self._force_foreground(prev):
                try:
                    import pyautogui
                    pyautogui.hotkey("alt", "tab")
                except Exception as e:
                    print(f"[AI-DRAWER] alt+tab fallback failed: {e}")
            self._ai_prev_foreground = None

    def _restore_geometry_no_drawer(self):
        try:
            wx, wy = self.winfo_x(), self.winfo_y()
        except Exception:
            return
        try:
            cur_w = self.winfo_width()
            base_h = getattr(self, "_toolbar_base_h", None)
            if base_h is None:
                return
            self.geometry(f"{cur_w}x{base_h}+{wx}+{wy}")
        except Exception:
            pass

    def _grow_geometry_for_drawer(self, drawer_h: int):
        try:
            wx, wy = self.winfo_x(), self.winfo_y()
            cur_w = self.winfo_width()
            base_h = getattr(self, "_toolbar_base_h", None)
            if base_h is None:
                return
            self.geometry(f"{cur_w}x{base_h + drawer_h}+{wx}+{wy}")
        except Exception:
            pass

    def _set_arrow_active(self, kind: str):
        """Highlight the arrow whose drawer is open; reset others."""
        mapping = {"bn": getattr(self, "arrow_bn", None),
                   "en": getattr(self, "arrow_en", None),
                   "snd": getattr(self, "arrow_read", None),
                   "ai": getattr(self, "arrow_ai", None)}
        for k, a in mapping.items():
            if a is None: continue
            try: a.set_active(k == kind)
            except Exception: pass

    def _reposition_drawer(self):
        """Re-place the active drawer at the right X after a layout change."""
        if self._drawer_widget is None:
            return
        kind = self._drawer_active_kind
        try:
            if kind in ("bn", "en", "snd"):
                idx = {"bn": 0, "en": 1, "snd": 2}[kind]
                xs = getattr(self, "_btn_x_centres", []) or []
                if idx < len(xs):
                    btn_s = getattr(self, "_btn_size", 72)
                    x = xs[idx] - btn_s // 2
                    # Preserve the width chosen at open-time so the
                    # row labels still fit after the layout change.
                    cur_w = self._drawer_widget.winfo_width()
                    if cur_w <= 1:    # not yet rendered → fallback
                        cur_w = btn_s
                    self._drawer_widget.place(x=x, y=0, width=cur_w)
            elif kind == "ai":
                w = getattr(self, "_toolbar_base_w", None)
                if w:
                    self._drawer_widget.place(x=0, y=0, width=w)
            self._grow_geometry_for_drawer(
                self._drawer_widget.winfo_reqheight())
        except Exception:
            pass

    # ── Voice-mode drawer (BN / EN) ────────────────────────────────

    def _toggle_voice_drawer(self, btn_idx: int):
        kind = "bn" if btn_idx == 1 else "en"
        if self._drawer_active_kind == kind:
            self._close_drawer()
            return
        self._close_drawer()

        own_lang   = self.settings.get(
            f"btn{btn_idx}_lang", "bn-BD" if btn_idx == 1 else "en-US")
        other_lang = self.settings.get(
            f"btn{3 - btn_idx}_lang",
            "en-US" if btn_idx == 1 else "bn-BD")
        own_label   = self._lang_display(own_lang).split()[0]
        other_label = self._lang_display(other_lang).split()[0]
        rows = [
            ("ai_translate", f"🌐 Translate → {own_label}"),
            ("ai_polish",    f"✨ Polish in {own_label}"),
            ("normal",       f"📝 Normal {own_label}"),
        ]
        cur = self.settings.get(f"btn{btn_idx}_voice_mode", "normal")

        btn_s = getattr(self, "_btn_size", 72)
        xs = getattr(self, "_btn_x_centres", []) or []
        if not xs:
            return
        x_left = xs[0 if btn_idx == 1 else 1] - btn_s // 2
        # Auto-size to fit the longest label — single button width
        # truncates labels like "🌐 Translate → বাংলা".
        drawer_w = self._calc_compact_drawer_width(rows, btn_s, x_left)

        self._build_compact_drawer(
            kind=kind, x=x_left, width=drawer_w, rows=rows, current=cur,
            on_select=lambda v, i=btn_idx: (self._apply_voice_mode(i, v),
                                            self._close_drawer()))

    # ── TTS drawer (SND) ───────────────────────────────────────────

    def _toggle_tts_drawer(self):
        if self._drawer_active_kind == "snd":
            self._close_drawer()
            return
        self._close_drawer()

        btn1_lang = self.settings.get("btn1_lang", "bn-BD")
        btn2_lang = self.settings.get("btn2_lang", "en-US")
        rows = [("btn1",
                  f"🔊 {self._lang_display(btn1_lang).split()[0]}")]
        if btn2_lang != btn1_lang:
            rows.append(("btn2",
                         f"🔊 {self._lang_display(btn2_lang).split()[0]}"))
        rows.append(("auto", "🎯 Auto-detect"))
        cur = self.settings.get("tts_source_mode", "auto")

        btn_s = getattr(self, "_btn_size", 72)
        xs = getattr(self, "_btn_x_centres", []) or []
        if len(xs) < 3:
            return
        x_left = xs[2] - btn_s // 2
        # Auto-size to fit the longest label.
        drawer_w = self._calc_compact_drawer_width(rows, btn_s, x_left)

        self._build_compact_drawer(
            kind="snd", x=x_left, width=drawer_w, rows=rows, current=cur,
            on_select=lambda v: (self._apply_tts_mode(v),
                                  self._close_drawer()))

    def _calc_compact_drawer_width(self, rows, btn_s: int,
                                     x_left: int) -> int:
        """Pick the smallest drawer width that fully shows every row's
        label. Anchored at x_left, may extend rightward up to (but not
        past) the widget's right edge. Always at least one button wide.

        rows: iterable of (value, label) tuples.
        Uses the same font (Segoe UI 7pt) the rows are rendered in."""
        try:
            import tkinter.font as tkfont
            f = tkfont.Font(family="Segoe UI", size=7)
            max_text = 0
            for _v, label in rows:
                w = f.measure(label)
                if w > max_text:
                    max_text = w
            # Padding: button text ipady=3 + button border + frame margin
            needed_w = max_text + 24
            # Cap at widget right edge so we don't overflow.
            toolbar_w = (getattr(self, "_toolbar_base_w", 0)
                          or self.winfo_width() or 480)
            max_avail = max(btn_s, toolbar_w - x_left - 4)
            return max(btn_s, min(needed_w, max_avail))
        except Exception as e:
            print(f"[DRAWER-WIDTH] calc failed: {e}")
            return btn_s

    def _build_compact_drawer(self, kind: str, x: int, width: int,
                                rows, current: str, on_select):
        """Stack of dark buttons, anchored under one toolbar button."""
        # Cleanup any previous content in drawer host
        for c in self._drawer_host.winfo_children():
            try: c.destroy()
            except Exception: pass

        drawer = tk.Frame(self._drawer_host, bg=self._DRAWER_BG,
                           highlightthickness=1,
                           highlightbackground=self._DRAWER_BORDER,
                           highlightcolor=self._DRAWER_BORDER)
        # Place at correct X within the drawer host (which spans full
        # widget width). y=0 because drawer_host sits below toolbar.
        drawer.place(x=x, y=0, width=width)

        for value, label in rows:
            is_cur = (value == current)
            btn = tk.Button(
                drawer, text=label,
                # Shrunk to 0.75× (was 9pt) per user request — voice
                # and TTS drawer rows feel less crowded at 7pt.
                font=("Segoe UI", 7, "bold" if is_cur else "normal"),
                bg=self._DRAWER_ROW_BG if not is_cur else self._DRAWER_HEADER,
                fg=self._DRAWER_ACTIVE if is_cur else self._DRAWER_TEXT,
                activebackground=self._DRAWER_ROW_HV,
                activeforeground=self._DRAWER_TEXT,
                relief="flat", bd=0, cursor="hand2",
                command=lambda v=value: on_select(v))
            btn.pack(fill="x", padx=2, pady=1, ipady=3)
            # Hover effect
            def _enter(_e, b=btn, c=is_cur):
                if not c: b.configure(bg=self._DRAWER_ROW_HV)
            def _leave(_e, b=btn, c=is_cur):
                if not c: b.configure(bg=self._DRAWER_ROW_BG)
            btn.bind("<Enter>", _enter)
            btn.bind("<Leave>", _leave)

        # Force geometry update so winfo_reqheight returns real value
        drawer.update_idletasks()
        self._drawer_host.configure(height=drawer.winfo_reqheight())

        self._drawer_widget = drawer
        self._drawer_active_kind = kind
        self._set_arrow_active(kind)
        self._grow_geometry_for_drawer(drawer.winfo_reqheight())

    # ── AI drawer (full-width compact bar) ─────────────────────────

    def _toggle_ai_drawer(self):
        if self._drawer_active_kind == "ai":
            self._close_drawer()
            return
        self._close_drawer()

        # Step 1 — capture user state BEFORE we steal focus.
        # The widget normally has WS_EX_NOACTIVATE so clicking the ▼
        # arrow did NOT switch foreground away from the user's app.
        # We therefore have one safe moment to:
        #   (a) note which window the user was working in, so we can
        #       SetForegroundWindow back to it before typing the result.
        #   (b) Ctrl+C any text they had selected, so the drawer can
        #       send it to the AI alongside the prompt + image.
        prev_hwnd = None
        try:
            import ctypes
            prev_hwnd = ctypes.windll.user32.GetForegroundWindow()
        except Exception:
            pass
        captured_selection = ""
        try:
            from ai_engine.clipboard_guard import ClipboardGuard
            captured_selection = (
                ClipboardGuard().get_selected_text() or "").strip()
        except Exception as e:
            print(f"[AI-DRAWER] selection capture failed: {e}")
        self._ai_prev_foreground = prev_hwnd

        for c in self._drawer_host.winfo_children():
            try: c.destroy()
            except Exception: pass

        from ui.ai_drawer import AIDrawer
        full_w = getattr(self, "_toolbar_base_w", self.winfo_width())
        # Hand the drawer any unconsumed screenshot so it appears as
        # an attached image right when the user opens it.
        pending_screenshot = getattr(self, "_last_screenshot_b64", None)
        drawer = AIDrawer(
            self._drawer_host, app=self, width=full_w,
            captured_selection=captured_selection,
            previous_foreground_hwnd=prev_hwnd,
            pending_image_b64=pending_screenshot)
        drawer.place(x=0, y=0, width=full_w)
        drawer.update_idletasks()
        self._drawer_host.configure(height=drawer.winfo_reqheight())

        self._drawer_widget = drawer
        self._drawer_active_kind = "ai"
        self._set_arrow_active("ai")
        self._grow_geometry_for_drawer(drawer.winfo_reqheight())

        # Step 2 — strip NOACTIVATE so the textbox can take keyboard
        # focus, then promote the widget Toplevel to foreground and
        # focus the entry.
        if self._toggle_no_activate(False):
            try:
                import ctypes
                hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
                ctypes.windll.user32.SetForegroundWindow(hwnd)
            except Exception as e:
                print(f"[AI-DRAWER] SetForegroundWindow failed: {e}")
            self.after(60, drawer.focus_entry)
