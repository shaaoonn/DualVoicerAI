# keyboard_input.py
"""Avro-style Bengali Phonetic Input Method (v3 — Win32 LL hook).

Architecture:
  - A real Windows WH_KEYBOARD_LL hook installed via ctypes
    (`ll_hook.py`). The hook runs on its own thread with a message
    loop and reliably suppresses individual key events at OS level —
    the third-party `keyboard` package's add_hotkey(suppress=True)
    is unreliable for plain letters and was the root cause of the
    earlier "Latin leaks into the field" bugs.
  - When Bengali Input is ON:
      * Letter & digit keys → blocked + buffered
      * Boundary keys (space / punctuation / Enter / Tab) → blocked,
        we render the buffered word as Bengali and inject it +
        the boundary character ourselves via SendInput Unicode.
      * Backspace → if buffer non-empty, pop char + re-render;
        if buffer empty, pass through (delete previous text).
      * Modified keys (Ctrl/Alt+letter) → never blocked → user's
        normal shortcuts (Ctrl+C, Ctrl+V, etc.) all work.
  - SendInput uses KEYEVENTF_UNICODE so Bengali codepoints (incl.
    conjuncts and vowel signs) are typed directly without needing
    the focused app to have a Bengali keyboard layout selected.
    Also uses dwExtraInfo = SELF_MARKER so our own events get
    recognised + skipped by our hook.

Toggle hotkey: F12 (configurable via Settings → ⌨️ Shortcuts).
Avro engine: vendored OmicronLab rules in `avro_engine/`.
"""

from __future__ import annotations

import threading
import time
from typing import Optional

# Avro Phonetic engine — prefer vendored OmicronLab rules
_avro_parse = None
try:
    from avro_engine import parse as _vendored_parse
    _avro_parse = _vendored_parse
except Exception:           # pragma: no cover
    try:
        import avro
        _avro_parse = avro.parse
    except ImportError:
        _avro_parse = None
_HAS_AVRO = _avro_parse is not None

# LL hook + SendInput helpers
try:
    from ll_hook import (LLKeyboardHook, send_backspaces,
                         send_unicode_string, vk_to_char,
                         VK_BACK, VK_RETURN, VK_TAB, VK_SPACE,
                         VK_ESCAPE, VK_SHIFT, VK_CONTROL, VK_MENU,
                         VK_LWIN, VK_RWIN, VK_CAPITAL,
                         _OEM_VK_TO_CHAR)
    _HAS_LL_HOOK = True
except Exception as e:      # pragma: no cover
    print(f"[BENGALI-INPUT] ll_hook import failed: {e}")
    _HAS_LL_HOOK = False


class BengaliInput:
    """Singleton Avro Phonetic input manager (LL-hook based)."""

    def __init__(self) -> None:
        self.enabled: bool = False
        # Latin chars buffered for the current word. NOT in the field —
        # letter keys are blocked at the LL hook level.
        self._buffer: str = ""
        # Codepoints of the CURRENT word's rendered Bengali currently
        # in the focused field. Reset to 0 on word boundary.
        self._displayed_count: int = 0
        self._lock = threading.Lock()
        self._ll_hook: Optional[LLKeyboardHook] = None
        # ── Debounce ──────────────────────────────────────────────
        self._render_timer: Optional[threading.Timer] = None
        self._render_delay_s: float = 0.030
        self._render_token: int = 0

    # ── Public API ────────────────────────────────────────────────

    def enable(self) -> None:
        if self.enabled:
            return
        if not _HAS_AVRO:
            print("[BENGALI-INPUT] avro engine missing")
            return
        if not _HAS_LL_HOOK:
            print("[BENGALI-INPUT] ll_hook module unavailable")
            return
        self._ll_hook = LLKeyboardHook(self._on_ll_key)
        if not self._ll_hook.start():
            print("[BENGALI-INPUT] LL hook failed to install")
            self._ll_hook = None
            return
        self.enabled = True
        print("[BENGALI-INPUT] ON (LL hook)")

    def disable(self) -> None:
        if not self.enabled:
            return
        self.enabled = False
        if self._ll_hook is not None:
            try:
                self._ll_hook.stop()
            except Exception:
                pass
            self._ll_hook = None
        if self._render_timer is not None:
            try:
                self._render_timer.cancel()
            except Exception:
                pass
            self._render_timer = None
        with self._lock:
            self._buffer = ""
            self._displayed_count = 0
        print("[BENGALI-INPUT] OFF")

    def toggle(self) -> None:
        if self.enabled:
            self.disable()
        else:
            self.enable()

    def reapply(self) -> None:
        """No-op for LL hook (it's independent of the keyboard library's
        unhook_all). Kept for backwards compatibility with main.py."""
        return

    # ── LL hook callback (runs on hook thread — keep it FAST) ─────

    def _on_ll_key(self, vk: int, is_down: bool,
                    has_shift: bool, has_ctrl: bool,
                    has_alt: bool) -> bool:
        """Returns True to suppress the event, False to let it through."""
        if not self.enabled:
            return False
        if not is_down:
            return False
        # Modifier-held shortcuts (Ctrl+anything, Alt+anything) → user's
        # normal app shortcuts → never intercept.
        if has_ctrl or has_alt:
            return False
        # Pure modifier keys → pass through
        if vk in (VK_SHIFT, VK_CONTROL, VK_MENU, VK_LWIN,
                   VK_RWIN, VK_CAPITAL):
            return False

        # ── Letters (a-z / A-Z) ───────────────────────────────────
        if 0x41 <= vk <= 0x5A:
            ch = chr(vk) if has_shift else chr(vk).lower()
            with self._lock:
                self._buffer += ch
                self._schedule_render_locked()
            return True  # block

        # ── Digits (0-9) ──────────────────────────────────────────
        if 0x30 <= vk <= 0x39:
            if has_shift:
                # Shift+digit = punctuation → boundary
                ch = ')!@#$%^&*('[vk - 0x30]
                with self._lock:
                    self._flush_for_boundary_locked(ch)
                return True
            ch = chr(vk)
            with self._lock:
                self._buffer += ch
                self._schedule_render_locked()
            return True

        # ── Backspace ─────────────────────────────────────────────
        if vk == VK_BACK:
            with self._lock:
                if self._buffer:
                    self._buffer = self._buffer[:-1]
                    self._schedule_render_locked()
                    return True   # block — re-render handles the visual
                # else: buffer empty, let backspace pass through to
                # delete previous text in the field naturally
            return False

        # ── Boundary: space / Enter / Tab ─────────────────────────
        if vk == VK_SPACE:
            with self._lock:
                self._flush_for_boundary_locked(' ')
            return True
        if vk == VK_RETURN:
            with self._lock:
                self._flush_for_boundary_locked('\n')
            return True
        if vk == VK_TAB:
            with self._lock:
                self._flush_for_boundary_locked('\t')
            return True
        if vk == VK_ESCAPE:
            # Esc: just reset state, don't inject anything
            with self._lock:
                self._cancel_timer_locked()
                self._render_token += 1
                if self._displayed_count > 0:
                    send_backspaces(self._displayed_count)
                self._buffer = ""
                self._displayed_count = 0
            return False  # let Esc through (closes dialogs etc.)

        # ── OEM punctuation (.,;:?![]\\` etc.) ────────────────────
        if vk in _OEM_VK_TO_CHAR:
            ch = vk_to_char(vk, has_shift)
            if ch:
                with self._lock:
                    self._flush_for_boundary_locked(ch)
                return True
            return False

        # Anything else (arrow keys, F-keys, etc.) → pass through
        return False

    # ── Boundary flush (immediate) ────────────────────────────────

    def _flush_for_boundary_locked(self, boundary_char: str) -> None:
        """Render the buffered word as Bengali and inject it + the
        boundary character. Called from the LL hook callback — already
        in fast path, no event-queue race because we BLOCK the original
        boundary and inject our own text via SendInput."""
        self._cancel_timer_locked()
        self._render_token += 1

        # Erase any mid-word render that was already on screen
        if self._displayed_count > 0:
            send_backspaces(self._displayed_count)

        try:
            bengali = _avro_parse(self._buffer) if self._buffer else ""
        except Exception as e:
            print(f"[BENGALI-INPUT] avro parse failed: {e}")
            bengali = self._buffer  # fall back

        text = bengali + boundary_char
        print(f"[BENGALI-INPUT] flush buf='{self._buffer}' "
              f"boundary={boundary_char!r} -> sending '{text}'")
        if text:
            send_unicode_string(text)

        self._buffer = ""
        self._displayed_count = 0

    # ── Debounced mid-word render ─────────────────────────────────

    def _cancel_timer_locked(self) -> None:
        if self._render_timer is not None:
            try:
                self._render_timer.cancel()
            except Exception:
                pass
            self._render_timer = None

    def _schedule_render_locked(self) -> None:
        self._cancel_timer_locked()
        self._render_token += 1
        token = self._render_token
        self._render_timer = threading.Timer(
            self._render_delay_s,
            lambda t=token: self._do_render(t))
        self._render_timer.daemon = True
        self._render_timer.start()

    def _do_render(self, token: int) -> None:
        with self._lock:
            if token != self._render_token:
                return  # superseded
            self._do_render_locked()

    def _do_render_locked(self) -> None:
        try:
            bengali = _avro_parse(self._buffer) if self._buffer else ""
        except Exception as e:
            print(f"[BENGALI-INPUT] avro parse failed: {e}")
            return
        print(f"[BENGALI-INPUT] render buf='{self._buffer}' "
              f"prev_count={self._displayed_count} -> '{bengali}' "
              f"({len(bengali)} cp)")
        # Erase the previously-rendered Bengali (if any) for this word
        if self._displayed_count > 0:
            send_backspaces(self._displayed_count)
        # Inject the freshly-converted Bengali
        if bengali:
            send_unicode_string(bengali)
        self._displayed_count = len(bengali)


# ── Module-level singleton ────────────────────────────────────────

_INSTANCE: Optional[BengaliInput] = None


def get_instance() -> BengaliInput:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = BengaliInput()
    return _INSTANCE


def is_available() -> bool:
    return _HAS_AVRO and _HAS_LL_HOOK
