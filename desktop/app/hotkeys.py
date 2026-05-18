"""Global hotkey registration + keyboard overlay setup.

``setup_hotkeys`` is one big registration loop that wires every
global ``keyboard.add_hotkey(...)`` callback the app supports:

* Voice-toggle hotkeys (Alt+Z BN, Alt+X EN, Alt+C SND)
* AI hotkeys (Ctrl+Shift+A, Ctrl+Shift+V smart paste)
* Pen-mode tool shortcuts (Ctrl+Alt+P pen, +H highlighter, +E eraser, …)
* Screenshot (Ctrl+Shift+S)
* Editor undo/redo/save shortcuts
* Clear-all routing (Ctrl+Shift+Delete)

``apply_kb_overlay_setting`` lazily instantiates the keyboard
shortcut overlay (the "press a key" cheat-sheet that floats over apps
when the user enables it from Settings → Shortcuts → Show overlay).
"""

from __future__ import annotations

import keyboard
import threading


class HotkeyMixin:
    """Mixed into VoiceTypingApp — global hotkey registration + KB overlay."""

    def setup_hotkeys(self):
        from config import (AI_HOTKEY, SMART_PASTE_HOTKEY, DEV_MODE,
                            DEFAULT_KEYBOARD_SHORTCUTS)
        try:
            # Clean slate - remove ALL previous hooks
            try: keyboard.unhook_all()
            except Exception: pass

            # Pull user-edited shortcuts (with per-action enable toggles)
            sc = self.settings.get("keyboard_shortcuts")
            if not isinstance(sc, dict):
                sc = {}
                self.settings["keyboard_shortcuts"] = sc
            en = self.settings.get("keyboard_shortcuts_enabled")
            if not isinstance(en, dict):
                en = {}
                self.settings["keyboard_shortcuts_enabled"] = en

            # ── Migration: replace plain "alt+letter" tool shortcuts with
            # the new "ctrl+alt+letter" defaults. The bare-Alt versions
            # cannot be reliably suppressed on Windows so the trigger letter
            # leaks into focused apps (e.g. typing "p" in Notepad). Users
            # can still pick any combo they want via Settings.
            migrated = False
            for tool_id in ("tool_select", "tool_pen", "tool_highlighter",
                            "tool_eraser", "tool_text", "tool_handwrite",
                            "tool_arrow"):
                cur = (sc.get(tool_id) or "").lower().strip()
                # Only migrate the EXACT old single-modifier defaults
                if cur in ("alt+v", "alt+p", "alt+h", "alt+e",
                           "alt+t", "alt+w", "alt+a"):
                    new_val = DEFAULT_KEYBOARD_SHORTCUTS.get(tool_id, "")
                    if new_val and new_val != cur:
                        print(f"[MIGRATE] {tool_id}: {cur} → {new_val}")
                        sc[tool_id] = new_val
                        migrated = True
            # Also default the new clear_all + tool_arrow if missing
            for new_id in ("tool_arrow", "clear_all"):
                if new_id not in sc:
                    sc[new_id] = DEFAULT_KEYBOARD_SHORTCUTS.get(new_id, "")
                    migrated = True
                if new_id not in en:
                    en[new_id] = True
                    migrated = True
            if migrated:
                try:
                    self.save_settings()
                except Exception:
                    pass

            def _hk(action_id, hardcoded_fallback=None):
                """Return the hotkey to register, or None if the user disabled
                it. Falls back to DEFAULT_KEYBOARD_SHORTCUTS, then to a
                hardcoded value if the action isn't in the new system."""
                if action_id and not en.get(action_id, True):
                    return None
                if action_id:
                    val = sc.get(action_id) or DEFAULT_KEYBOARD_SHORTCUTS.get(action_id, "")
                    if val:
                        return val
                return hardcoded_fallback

            registered = []

            def _reg(action_id, callback, fallback=None, suppress=False):
                hk = _hk(action_id, fallback)
                if not hk:
                    return  # disabled or unconfigured
                try:
                    keyboard.add_hotkey(hk, callback, suppress=suppress)
                    registered.append(f"{action_id or '(legacy)'}={hk}")
                except Exception as ex:
                    print(f"[HOTKEY] failed to register {action_id} ({hk}): {ex}")

            # Legacy fixed hotkeys (no per-action toggle yet — keep them on)
            _reg(None, lambda: self.after(0, lambda: self.switch_language('bn-BD')),
                 fallback='alt+z')
            _reg(None, lambda: self.after(0, lambda: self.switch_language('en-US')),
                 fallback='alt+x')
            _reg(None, lambda: self.after(0, self.handle_reader_click),
                 fallback='alt+c')
            _reg(None, lambda: self.after(0, self.toggle_pen_mode),
                 fallback='ctrl+shift+d')

            # User-configurable main app shortcuts (no suppress — they're
            # standard global shortcuts users may want to coexist with apps)
            _reg("ai_assistant",
                 lambda: self.after(0, self.ai_trigger_flow),
                 fallback=AI_HOTKEY)
            _reg("smart_paste",
                 lambda: self.after(0, self.smart_paste_flow),
                 fallback=SMART_PASTE_HOTKEY)
            _reg("take_screenshot",
                 lambda: self.after(0, self.take_screenshot))
            _reg("voice_btn1",
                 lambda: self.after(
                     0, lambda: self.switch_language(
                         self.settings.get("btn1_lang", "bn-BD"))))
            _reg("voice_btn2",
                 lambda: self.after(
                     0, lambda: self.switch_language(
                         self.settings.get("btn2_lang", "en-US"))))

            # Tool-switch shortcuts — GLOBAL, suppress=True so other apps
            # don't also receive (e.g. Alt+P would otherwise open Notepad's
            # menu before our hook can run). Route through the central
            # dispatcher so they switch tools in the active surface (pen
            # overlay OR editor).
            tool_actions = [
                ("tool_select",      "select"),
                ("tool_pen",         "pen"),
                ("tool_highlighter", "highlighter"),
                ("tool_eraser",      "eraser"),
                ("tool_text",        "text"),
                ("tool_handwrite",   "handwrite"),
                ("tool_arrow",       "shape_arrow"),
            ]
            # NOTE: suppress=True was REMOVED here because it caused the
            # `keyboard` library's modifier-tracking bug — Shift would get
            # "stuck" in the library's internal state, making subsequent
            # text typing produce wrong characters. Ctrl+Alt+letter combos
            # naturally don't leak the trigger letter into focused apps
            # (the Ctrl+Alt prefix prevents normal text-input handling),
            # so suppress=True isn't needed for cleanliness either.
            for action_id, tool_name in tool_actions:
                _reg(action_id,
                     lambda t=tool_name: self.after(
                         0, lambda: self._route_tool_shortcut(t)))

            _reg("clear_all",
                 lambda: self.after(0, self._route_clear_all))

            # Bengali Phonetic Input toggle — DISABLED in this version.
            # Re-enable by uncommenting once the LL hook integration is
            # rebuilt against a more reliable substrate (e.g. Windows
            # TSF instead of pure-Python hook).
            # _reg("bengali_input_toggle",
            #      lambda: self.after(0, self._toggle_bengali_input))

            print(f"[HOTKEYS] Registered: {', '.join(registered)}")

            # CRITICAL: re-arm the keyboard-overlay hook after unhook_all() above
            try:
                if getattr(self, "_kb_overlay", None) is not None:
                    self._kb_overlay.reapply()
            except Exception as e:
                print(f"[KB-OVERLAY] reapply skipped: {e}")
            # Same for the Bengali Phonetic Input hook — its hook gets
            # wiped by unhook_all() too, must be re-armed if enabled.
            try:
                from keyboard_input import get_instance, is_available
                if is_available():
                    get_instance().reapply()
            except Exception as e:
                print(f"[BENGALI-INPUT] reapply skipped: {e}")
        except Exception as e:
            print(f"[HOTKEY ERROR] {e}")

    def apply_kb_overlay_setting(self):
        """Enable / disable / reconfigure the keyboard-shortcut overlay
        based on the current self.settings values. Safe to call repeatedly."""
        try:
            from keyboard_overlay import KeyboardOverlay
        except Exception as e:
            print(f"[KB-OVERLAY] import failed: {e}")
            return
        if self._kb_overlay is None:
            try:
                self._kb_overlay = KeyboardOverlay(self)
            except Exception as e:
                print(f"[KB-OVERLAY] init failed: {e}")
                return
        try:
            self._kb_overlay.set_font_size(self.settings.get("kb_overlay_font_size", 18))
            self._kb_overlay.set_font_color(self.settings.get("kb_overlay_font_color", "#FFFFFF"))
            if self.settings.get("show_keyboard_shortcuts", False):
                self._kb_overlay.enable()
            else:
                self._kb_overlay.disable()
        except Exception as e:
            print(f"[KB-OVERLAY] apply failed: {e}")
