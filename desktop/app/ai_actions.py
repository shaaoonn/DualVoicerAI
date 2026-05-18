"""AI trigger flows — Ctrl+Shift+A, smart paste, screenshot vision.

Thin orchestration wrappers around ``ai_engine/*``. Heavy lifting
(OpenRouter API, prompt construction, vision encoding) already lives
in the ai_engine package; this mixin handles:

* Auth + freemium gating
* Selection capture via ClipboardGuard
* UI state transitions (btn_ai → "ai_thinking" → "idle")
* Error mapping (RATE_LIMIT / TIMEOUT / INVALID_API_KEY → toast text)
* Result paste through ClipboardGuard
"""

from __future__ import annotations

import threading
import time
import tkinter as tk

import customtkinter as ctk
import pyautogui
import pyperclip


class AIActionsMixin:
    """Mixed into VoiceTypingApp — AI trigger flows."""


    # ── AI Trigger Flow (Ctrl+Shift+A) ────────────────────────
    def ai_trigger_flow(self):
        from config import DEV_MODE
        # Honour the AI on/off toggle from settings
        if not self.settings.get("ai_enabled", True):
            print("[AI] Disabled in settings - ignoring trigger")
            return
        if not DEV_MODE and not self.is_authenticated:
            self.after(0, self.open_auth_panel)
            return
        if hasattr(self, 'freemium') and not self.freemium.can_use("ai", self):
            self.after(0, lambda: self._show_lock_popup(
                self.freemium.get_lock_message("ai")))
            return
        # Stop TTS if playing
        if self.is_reading:
            self.stop_reader_internal()
        if self.is_listening:
            self.is_listening = False
            self._silent_reset()

        # Check if there's a recent screenshot (within last 10 seconds)
        has_screenshot = (
            hasattr(self, '_last_screenshot_b64') and
            self._last_screenshot_b64 and
            hasattr(self, '_last_screenshot_time') and
            (time.time() - self._last_screenshot_time) < 10
        )

        if has_screenshot:
            self._ai_screenshot_flow()
        else:
            self._ai_text_flow()

    def _ai_text_flow(self):
        """Standard AI text processing (Ctrl+Shift+A with selected text)."""
        self.after(0, lambda: self.btn_ai.set_state("ai_thinking"))

        def _run():
            import asyncio
            from ai_engine.clipboard_guard import ClipboardGuard
            from ai_engine.text_processor import TextProcessor

            guard    = ClipboardGuard()
            selected = guard.get_selected_text()
            if not selected or not selected.strip():
                self.after(0, lambda: self.btn_ai.set_state("idle"))
                return

            processor = TextProcessor(
                self.settings.get("ai_system_prompt", ""),
                self.settings.get("ai_output_format", "plain"),
                knowledge_base=self.settings.get("knowledge_base", ""),
            )
            try:
                result = asyncio.run(processor.process(selected))
                out_fmt = self.settings.get("ai_output_format", "plain")
                guard.paste_result(result, output_format=out_fmt)
            except RuntimeError as e:
                msgs = {
                    "RATE_LIMIT":      "\u23f3 AI \u09b2\u09bf\u09ae\u09bf\u099f \u09aa\u09cc\u0981\u099b\u09c7 \u0997\u09c7\u099b\u09c7, \u09aa\u09b0\u09c7 \u099a\u09c7\u09b7\u09cd\u099f\u09be \u0995\u09b0\u09c1\u09a8",
                    "TIMEOUT":         "\u231b AI \u09b8\u09be\u09dc\u09be \u09a6\u09bf\u099a\u09cd\u099b\u09c7 \u09a8\u09be",
                    "INVALID_API_KEY": "\U0001f511 API \u0995\u09c0 \u09b8\u09ae\u09b8\u09cd\u09af\u09be \u2014 Settings \u099a\u09c7\u0995 \u0995\u09b0\u09c1\u09a8",
                }
                msg = msgs.get(str(e), f"\u274c {e}")
                self.after(0, lambda m=msg: self._show_ai_error(m))
            finally:
                self.after(0, lambda: self.btn_ai.set_state("idle"))

        import threading
        threading.Thread(target=_run, daemon=True).start()

    def _ai_screenshot_flow(self):
        """AI vision analysis of the last screenshot."""
        self.after(0, lambda: self.btn_ai.set_state("ai_thinking"))
        screenshot_b64 = self._last_screenshot_b64

        # Clear screenshot so next AI press does text mode
        self._last_screenshot_b64 = None
        self._last_screenshot_time = 0

        def _run():
            import asyncio
            from ai_engine.screenshot_analyzer import analyze_screenshot
            from ai_engine.clipboard_guard import ClipboardGuard

            try:
                img_sys = self.settings.get("image_system_prompt", "")
                kb      = self.settings.get("knowledge_base", "")
                result = asyncio.run(analyze_screenshot(
                    screenshot_b64,
                    system_prompt=img_sys,
                    knowledge_base=kb,
                ))
                if result and result.strip():
                    # Copy result to clipboard and paste
                    guard = ClipboardGuard()
                    out_fmt = self.settings.get("ai_output_format", "plain")
                    guard.paste_result(result, output_format=out_fmt)
                    print(f"[AI SCREENSHOT] Analysis complete ({len(result)} chars)")
            except RuntimeError as e:
                msgs = {
                    "RATE_LIMIT":      "\u23f3 AI \u09b2\u09bf\u09ae\u09bf\u099f \u09aa\u09cc\u0981\u099b\u09c7 \u0997\u09c7\u099b\u09c7",
                    "TIMEOUT":         "\u231b AI \u09b8\u09be\u09dc\u09be \u09a6\u09bf\u099a\u09cd\u099b\u09c7 \u09a8\u09be",
                    "INVALID_API_KEY": "\U0001f511 API \u0995\u09c0 \u09b8\u09ae\u09b8\u09cd\u09af\u09be",
                }
                msg = msgs.get(str(e), f"\u274c {e}")
                self.after(0, lambda m=msg: self._show_ai_error(m))
            except Exception as e:
                self.after(0, lambda: self._show_ai_error(f"\u274c Screenshot AI: {e}"))
            finally:
                self.after(0, lambda: self.btn_ai.set_state("idle"))

        import threading
        threading.Thread(target=_run, daemon=True).start()


    # ── Smart Paste Flow (Ctrl+Shift+V) ────────────────────────
    def smart_paste_flow(self):
        """Ctrl+Shift+V - clipboard content + KB + AI -> paste reply."""
        from config import DEV_MODE
        if not DEV_MODE and not self.is_authenticated:
            self.after(0, self.open_auth_panel)
            return
        if hasattr(self, 'freemium') and not self.freemium.can_use("ai", self):
            self.after(0, lambda: self._show_lock_popup(
                self.freemium.get_lock_message("ai")))
            return

        try:    clipboard_text = pyperclip.paste()
        except Exception: clipboard_text = ""

        if not clipboard_text or not clipboard_text.strip():
            self._show_ai_error("\U0001f4cb \u0995\u09cd\u09b2\u09bf\u09aa\u09ac\u09cb\u09b0\u09cd\u09a1 \u0996\u09be\u09b2\u09bf\u0964 \u0986\u0997\u09c7 \u0995\u09bf\u099b\u09c1 \u0995\u09aa\u09bf \u0995\u09b0\u09c1\u09a8\u0964")
            return

        clipboard_text = clipboard_text[:4000]
        self.after(0, lambda: self.btn_ai.set_state("ai_thinking"))

        def _run():
            import asyncio
            from ai_engine.openrouter import complete
            from ai_engine.format_handler import format_for_paste

            sys_prompt = self.settings.get("ai_system_prompt", "\u09a4\u09c1\u09ae\u09bf \u098f\u0995\u099c\u09a8 \u09a6\u0995\u09cd\u09b7 \u09b8\u09b9\u0995\u09be\u09b0\u09c0\u0964")
            kb         = self.settings.get("knowledge_base", "").strip()
            out_format = self.settings.get("ai_output_format", "plain")

            kb_section = f"\n\n--- \u09a8\u09b2\u09c7\u099c \u09ac\u09c7\u099c ---\n{kb}\n--- \u09a8\u09b2\u09c7\u099c \u09ac\u09c7\u099c \u09b6\u09c7\u09b7 ---\n" if kb else ""
            system_msg = (
                f"{sys_prompt}{kb_section}\n\n"
                "\u09a8\u09bf\u09b0\u09cd\u09a6\u09c7\u09b6: \u09b8\u09b0\u09be\u09b8\u09b0\u09bf reply \u09b2\u09c7\u0996\u09cb\u0964 \u0995\u09cb\u09a8\u09cb \u09ad\u09c2\u09ae\u09bf\u0995\u09be \u09a8\u09df\u0964 "
                "\u09af\u09c7 \u09ad\u09be\u09b7\u09be\u09df \u09aa\u09cd\u09b0\u09b6\u09cd\u09a8 \u09b8\u09c7 \u09ad\u09be\u09b7\u09be\u09df \u0989\u09a4\u09cd\u09a4\u09b0\u0964"
            )
            messages = [
                {"role": "system", "content": system_msg},
                {"role": "user",   "content": f"\u0989\u09a4\u09cd\u09a4\u09b0 \u09a6\u09be\u0993:\n\n{clipboard_text.strip()}"},
            ]
            try:
                result = asyncio.run(complete(messages))
                final  = format_for_paste(result, out_format)
                saved  = pyperclip.paste()
                if out_format == "rich":
                    from ai_engine.format_handler import markdown_to_html_clipboard
                    if markdown_to_html_clipboard(result):
                        import time; time.sleep(0.05)
                        pyautogui.hotkey("ctrl", "v")
                        time.sleep(0.12)
                        try: pyperclip.copy(saved)
                        except Exception: pass
                    else:
                        # fallback plain
                        pyperclip.copy(final)
                        import time; time.sleep(0.05)
                        pyautogui.hotkey("ctrl", "v")
                        time.sleep(0.12)
                        try: pyperclip.copy(saved)
                        except Exception: pass
                else:
                    pyperclip.copy(final)
                    import time; time.sleep(0.05)
                    pyautogui.hotkey("ctrl", "v")
                    time.sleep(0.12)
                    try: pyperclip.copy(saved)
                    except Exception: pass
            except Exception as e:
                self.after(0, lambda: self._show_ai_error(f"Smart Paste \u09b8\u09ae\u09b8\u09cd\u09af\u09be: {e}"))
            finally:
                self.after(0, lambda: self.btn_ai.set_state("idle"))

        import threading
        threading.Thread(target=_run, daemon=True).start()

    def _ai_button_send(self):
        """Main AI button click — equivalent to the Send (➤) button
        inside the drawer, NOT a "open drawer" trigger.

        Behavior:
          • drawer open  → trigger the drawer's send (uses its
            already-captured selection + prompt textbox + image).
          • drawer closed → fall back to the standalone selection-AI
            flow that existed before the drawer was added (Ctrl+C
            grab → AI process → paste).
        """
        drawer = getattr(self, "_drawer_widget", None)
        if (self._drawer_active_kind == "ai"
                and drawer is not None
                and not getattr(drawer, "_busy", False)):
            try:
                drawer._on_send()
            except Exception as e:
                print(f"[AI BTN] drawer send failed: {e}")
            return
        # Drawer not open (or busy) — original flow.
        try:
            self.ai_trigger_flow()
        except Exception as e:
            print(f"[AI BTN] ai_trigger_flow failed: {e}")
