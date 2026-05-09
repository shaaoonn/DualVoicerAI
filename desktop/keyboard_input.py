# keyboard_input.py
"""Avro-style Bengali Phonetic Input Method.

Wraps the official Avro Phonetic engine (avro-py, MIT-licensed Python
port maintained by hitblast at https://github.com/hitblast/avro.py)
so users get pixel-identical "amar nam Rahul" → "আমার নাম রাহুল"
conversion in any Windows text field — no separate Avro/Bijoy install
needed.

Architecture:
  - Single global keyboard hook via the `keyboard` library
  - Buffers ASCII characters as the user types
  - On a word boundary (space / Enter / punctuation), the buffer is
    flushed: backspace the original Latin → paste the Bengali via
    clipboard (clipboard is more reliable than synthesised key events
    for non-Latin scripts on Windows).

Toggle hotkey: F12 by default (configurable via the
`bengali_input_toggle` keyboard shortcut in Settings → ⌨️ Shortcuts).

Designed to coexist with `keyboard.unhook_all()` — call `reapply()`
after any global unhook to re-arm the input hook.
"""

from __future__ import annotations

import threading
import time
from typing import Optional

try:
    import keyboard
except ImportError:        # pragma: no cover
    keyboard = None        # type: ignore

try:
    import pyperclip
except ImportError:        # pragma: no cover
    pyperclip = None       # type: ignore

# Avro Phonetic engine.
#   1. Prefer the vendored OmicronLab rules (avro_engine package) for
#      100% Avro-Keyboard-identical output and zero third-party
#      maintenance risk.
#   2. Fall back to the third-party `avro-py` library if the vendored
#      data is missing for some reason (e.g. trimmed PyInstaller build).
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


# Keys that mark a word boundary — flush the buffer & convert.
# Backspace handled separately (pops one char from buffer).
_WORD_BOUNDARY_KEYS = {
    "space", "enter", "tab", "esc",
    ".", ",", "?", "!", ";", ":", "/", "\\",
    "(", ")", "[", "]", "{", "}",
    '"', "'", "<", ">", "=", "+", "-", "*",
    "|", "~", "`", "@", "#", "$", "%", "^", "&",
}


class BengaliInput:
    """Singleton-style Avro Phonetic input manager.

    Real-time mode: every keystroke triggers a re-render of the current
    word in Bengali — matches Avro's native typing experience where the
    output updates as you type, not only after Space.
    """

    def __init__(self) -> None:
        self.enabled: bool = False
        self._buffer: str = ""        # Latin chars typed for the current word
        self._displayed: str = ""     # Bengali currently in the focused field
                                       # (for the active word — reset on word
                                       # boundary so each word renders fresh)
        self._hook = None
        self._lock = threading.Lock()
        self._restore_clipboard_timer: Optional[threading.Timer] = None
        # ── Self-event consumption queue ──────────────────────────
        # When _render_locked() synthesises backspaces + ctrl+v those
        # echo back through our own hook. We track exactly what we sent
        # so genuine user keystrokes during the render aren't swallowed.
        # Format: list of (key_name, expiry_timestamp).
        self._expected_self_keys: list = []
        self._self_lock = threading.Lock()

    # ── Public API ────────────────────────────────────────────────

    def enable(self) -> None:
        if self.enabled or keyboard is None or not _HAS_AVRO:
            if not _HAS_AVRO:
                print("[BENGALI-INPUT] avro engine unavailable — vendored "
                      "avro_engine missing AND avro-py not installed")
            return
        try:
            self._hook = keyboard.hook(self._on_event)
            self.enabled = True
            print("[BENGALI-INPUT] ON (Avro Phonetic)")
        except Exception as e:
            print(f"[BENGALI-INPUT] enable failed: {e}")

    def disable(self) -> None:
        if not self.enabled:
            return
        self.enabled = False
        if self._hook is not None and keyboard is not None:
            try:
                keyboard.unhook(self._hook)
            except Exception:
                pass
        self._hook = None
        with self._lock:
            self._buffer = ""
            self._displayed = ""
        print("[BENGALI-INPUT] OFF")

    def toggle(self) -> None:
        if self.enabled:
            self.disable()
        else:
            self.enable()

    def reapply(self) -> None:
        """Re-register the global hook. Call after any code elsewhere
        that does `keyboard.unhook_all()` so our input keeps working."""
        if not self.enabled or keyboard is None:
            return
        try:
            self._hook = keyboard.hook(self._on_event)
        except Exception as e:
            print(f"[BENGALI-INPUT] reapply failed: {e}")

    # ── Internal: hook callback ───────────────────────────────────

    def _on_event(self, event) -> None:
        if not self.enabled:
            return
        # Only act on key-down — ignore key-up entirely.
        if getattr(event, "event_type", "") != "down":
            return

        key = (getattr(event, "name", "") or "").lower()
        if not key:
            return

        # If this exact key is one of OUR synthesised echoes, eat it
        # silently. Anything else is a real user keystroke.
        if self._consume_self_event(key):
            return

        # Hotkey-style modifier combos (Ctrl+anything, Alt+anything,
        # Win+anything) — don't interfere. Also clear the buffer so
        # post-shortcut typing doesn't merge with pre-shortcut typing.
        try:
            if (keyboard.is_pressed("ctrl") or keyboard.is_pressed("alt")
                    or keyboard.is_pressed("windows")):
                with self._lock:
                    self._buffer = ""
                return
        except Exception:
            pass

        # Ignore function keys, navigation keys, modifier keys, etc.
        if (key.startswith("f") and key[1:].isdigit()) or \
                key in {"shift", "ctrl", "alt", "windows", "menu",
                        "caps lock", "num lock", "scroll lock",
                        "left", "right", "up", "down",
                        "home", "end", "page up", "page down",
                        "insert", "delete", "print screen", "pause"}:
            return

        with self._lock:
            # Word boundary → reset state. The boundary key (space, dot,
            # etc.) types naturally into the field — we don't intercept it.
            # The previous word's Bengali is already on screen from the
            # last real-time render.
            if key in _WORD_BOUNDARY_KEYS:
                self._buffer = ""
                self._displayed = ""
                return
            # Backspace → pop one char from buffer + re-render. If the
            # buffer is already empty, let the backspace pass through to
            # delete previous content in the field naturally.
            if key == "backspace":
                if self._buffer:
                    self._buffer = self._buffer[:-1]
                    # User's backspace already removed 1 char from field
                    self._render_locked(field_chars=len(self._displayed) - 1)
                return
            # Letters / digits → buffer + re-render in real-time.
            if len(key) == 1:
                ch = key
                try:
                    if keyboard.is_pressed("shift") and ch.isalpha():
                        ch = ch.upper()
                except Exception:
                    pass
                self._buffer += ch
                # User's keystroke just added 1 char to the field
                self._render_locked(field_chars=len(self._displayed) + 1)
                return

    # ── Internal: self-event tracking ─────────────────────────────

    def _expect_self_event(self, key: str, count: int = 1,
                            timeout: float = 0.6) -> None:
        """Mark `count` future hook events for `key` as our own echoes.
        Each entry expires after `timeout` seconds so a missing echo
        doesn't permanently swallow the user's real keystrokes."""
        expiry = time.time() + timeout
        with self._self_lock:
            for _ in range(count):
                self._expected_self_keys.append((key, expiry))

    def _consume_self_event(self, key: str) -> bool:
        """Returns True if `key` matches a pending self-event (and pops
        it from the queue). Expired entries are reaped on every call."""
        now = time.time()
        with self._self_lock:
            # Reap expired
            self._expected_self_keys = [
                (k, e) for k, e in self._expected_self_keys if e > now]
            # Find first matching
            for i, (k, _e) in enumerate(self._expected_self_keys):
                if k == key:
                    self._expected_self_keys.pop(i)
                    return True
        return False

    # ── Internal: real-time render ────────────────────────────────

    def _render_locked(self, field_chars: int) -> None:
        """Replace the last `field_chars` characters in the focused field
        with the Bengali transliteration of the current buffer.

        `field_chars` = how many codepoints currently exist in the field
        for the active word (BEFORE we clean up). E.g. after the user
        types one more letter, that's `len(self._displayed) + 1`. After
        the user backspaces one, that's `len(self._displayed) - 1`.

        MUST be called with `self._lock` held.
        """
        if not _HAS_AVRO:
            return
        try:
            new_bengali = _avro_parse(self._buffer) if self._buffer else ""
        except Exception as e:
            print(f"[BENGALI-INPUT] avro parse failed: {e}")
            return

        # Quick log only when render actually does work
        if self._buffer or self._displayed:
            print(f"[BENGALI-INPUT] render buf='{self._buffer}' "
                  f"prev='{self._displayed}' new='{new_bengali}' wipe={field_chars}")

        wipe = max(0, field_chars)

        # Pre-register every key we're about to synthesise so the hook
        # doesn't re-process its own echoes. User keystrokes that arrive
        # mid-render still pass through (they don't match expected keys).
        self._expect_self_event("backspace", wipe)
        if new_bengali:
            self._expect_self_event("ctrl", 1)
            self._expect_self_event("v", 1)

        # Erase the current rendering (plus the just-typed user key, or
        # minus the just-removed backspace target). Slightly longer
        # inter-key gap (5ms) than the previous 2ms — fast typists were
        # outrunning the OS, leaving a stray char behind. 5ms is still
        # fast enough to feel real-time but reliably ordered.
        for _ in range(wipe):
            try:
                keyboard.send("backspace")
            except Exception:
                pass
            time.sleep(0.005)

        # Paste the new Bengali via clipboard (more reliable than key
        # synthesis for non-Latin scripts on Windows).
        if new_bengali and pyperclip is not None:
            saved_clipboard = ""
            try:
                saved_clipboard = pyperclip.paste()
            except Exception:
                pass
            try:
                pyperclip.copy(new_bengali)
                # Give clipboard ownership a moment to settle before paste
                time.sleep(0.012)
                keyboard.press_and_release("ctrl+v")
            except Exception as e:
                print(f"[BENGALI-INPUT] paste failed: {e}")
            else:
                # Restore previous clipboard after the paste settles
                if self._restore_clipboard_timer is not None:
                    try:
                        self._restore_clipboard_timer.cancel()
                    except Exception:
                        pass
                if saved_clipboard:
                    self._restore_clipboard_timer = threading.Timer(
                        0.4, lambda s=saved_clipboard: _safe_clipboard_set(s))
                    self._restore_clipboard_timer.daemon = True
                    self._restore_clipboard_timer.start()

        self._displayed = new_bengali


def _safe_clipboard_set(text: str) -> None:
    try:
        pyperclip.copy(text)
    except Exception:
        pass


# ── Module-level singleton ────────────────────────────────────────

_INSTANCE: Optional[BengaliInput] = None


def get_instance() -> BengaliInput:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = BengaliInput()
    return _INSTANCE


def is_available() -> bool:
    """True if the Avro engine + keyboard library are both importable."""
    return _HAS_AVRO and keyboard is not None
