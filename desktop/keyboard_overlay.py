"""
keyboard_overlay.py — On-screen "Show Keyboard Shortcut" overlay.

When enabled, every key press is rendered as a styled rounded box near the
bottom-right of the screen. Multiple simultaneous keys are joined with "+"
labels (e.g.  Ctrl + Shift + V).  Each burst auto-hides after HIDE_AFTER_MS.

Designed to coexist with `keyboard.unhook_all()` calls elsewhere in the app:
the host should call `reapply()` after re-registering its own hotkeys so this
module's hook is restored too.

The keyboard library invokes callbacks on its own listener thread. We never
touch Tk directly from there — every UI mutation is bounced to the Tk main
thread via `root.after(0, ...)`.
"""

from __future__ import annotations

import threading
import tkinter as tk

try:
    import keyboard  # global key hook
except Exception:  # pragma: no cover
    keyboard = None  # type: ignore


# ─────────────────────── Config ───────────────────────

HIDE_AFTER_MS = 500  # half a second, per the user spec

BG_COLOR     = "#1A1A22"   # window background
KEY_BG       = "#2A2A38"   # individual key cap background
KEY_BORDER   = "#5070FF"   # subtle blue border around each cap
PLUS_COLOR   = "#A0A0B0"   # color of the "+" between keys
PAD_X        = 14          # outer padding inside the overlay window
PAD_Y        = 10
KEY_PAD_X    = 12          # padding inside each key box
KEY_PAD_Y    = 6
KEY_GAP      = 8           # gap between key boxes / plus signs
MARGIN_R     = 28          # distance from right edge of screen
MARGIN_B     = 80          # distance from bottom edge of screen

# Modifier key normalisation — both left/right map to the same display name
_MODS = {
    "ctrl", "left ctrl", "right ctrl",
    "shift", "left shift", "right shift",
    "alt", "left alt", "right alt", "alt gr",
    "windows", "left windows", "right windows", "cmd",
}

_DISPLAY = {
    "ctrl": "Ctrl", "left ctrl": "Ctrl", "right ctrl": "Ctrl",
    "shift": "Shift", "left shift": "Shift", "right shift": "Shift",
    "alt": "Alt", "left alt": "Alt", "right alt": "Alt", "alt gr": "AltGr",
    "windows": "Win", "left windows": "Win", "right windows": "Win", "cmd": "Cmd",
    "space": "Space",
    "enter": "Enter", "return": "Enter",
    "esc": "Esc", "escape": "Esc",
    "tab": "Tab", "caps lock": "Caps", "backspace": "⌫", "delete": "Del",
    "up": "↑", "down": "↓", "left": "←", "right": "→",
    "page up": "PgUp", "page down": "PgDn",
    "home": "Home", "end": "End",
    "insert": "Ins",
    "print screen": "PrtSc",
    "scroll lock": "ScrLk",
    "pause": "Pause",
    "num lock": "NumLk",
}


def _format_key(name: str) -> str:
    if not name:
        return ""
    n = name.lower()
    if n in _DISPLAY:
        return _DISPLAY[n]
    if n.startswith("f") and n[1:].isdigit():   # F1..F24
        return n.upper()
    if len(n) == 1:
        return n.upper()
    return n.title()


# ─────────────────────── Overlay ───────────────────────

class KeyboardOverlay:
    """Live keyboard-shortcut overlay.

    Lifecycle:
        ovl = KeyboardOverlay(root)
        ovl.set_font_size(18); ovl.set_font_color("#FFFFFF")
        ovl.enable()           # arms the global key hook + creates window
        ovl.disable()          # tears it down

        # If anything in the app calls keyboard.unhook_all(), the host MUST
        # call ovl.reapply() afterwards to re-arm the listener.
    """

    def __init__(self, root: tk.Misc):
        self._root = root
        self._enabled = False
        self._hook = None
        self._lock = threading.Lock()

        self._font_size  = 18
        self._font_color = "#FFFFFF"

        self._win: tk.Toplevel | None = None
        self._inner: tk.Frame | None = None
        self._hide_after_id = None

        # Currently held physical keys, in press order
        self._held: list[str] = []
        # Latest "burst" to render — set on every keydown
        self._last_burst: list[str] = []

    # ── Public API ────────────────────────────────────────

    def set_font_size(self, size: int):
        try:
            self._font_size = max(8, min(64, int(size)))
        except (TypeError, ValueError):
            self._font_size = 18

    def set_font_color(self, color: str):
        if isinstance(color, str) and color.startswith("#") and len(color) == 7:
            self._font_color = color

    def enable(self):
        if self._enabled:
            return
        if keyboard is None:
            return
        try:
            self._hook = keyboard.hook(self._on_event)
        except Exception as e:
            print(f"[KB-OVERLAY] hook failed: {e}")
            return
        self._enabled = True

    def disable(self):
        if not self._enabled:
            return
        self._enabled = False
        try:
            if self._hook is not None and keyboard is not None:
                keyboard.unhook(self._hook)
        except Exception:
            pass
        self._hook = None
        self._held.clear()
        self._destroy_window()

    def reapply(self):
        """Re-register the hook (call after `keyboard.unhook_all()`)."""
        if not self._enabled:
            return
        if keyboard is None:
            return
        try:
            self._hook = keyboard.hook(self._on_event)
        except Exception as e:
            print(f"[KB-OVERLAY] reapply failed: {e}")

    # ── Hook callback (runs on keyboard listener thread) ──

    def _on_event(self, event):
        if not self._enabled:
            return
        try:
            name = (event.name or "").lower()
            etype = event.event_type  # 'down' | 'up'
        except AttributeError:
            return
        if not name:
            return

        with self._lock:
            if etype == "down":
                # debounce auto-repeat: don't append duplicates
                if name not in self._held:
                    self._held.append(name)
                # snapshot current burst (held mods + this new key)
                self._last_burst = list(self._held)
                burst = list(self._last_burst)
                # Marshal to Tk thread
                try:
                    self._root.after(0, lambda b=burst: self._show_burst(b))
                except Exception:
                    pass
            elif etype == "up":
                if name in self._held:
                    try:
                        self._held.remove(name)
                    except ValueError:
                        pass

    # ── Tk-thread UI ──────────────────────────────────────

    def _ensure_window(self):
        if self._win is not None and self._win.winfo_exists():
            return
        try:
            w = tk.Toplevel(self._root)
        except Exception as e:
            print(f"[KB-OVERLAY] toplevel failed: {e}")
            return
        w.overrideredirect(True)
        try:
            w.attributes("-topmost", True)
        except tk.TclError:
            pass
        try:
            w.attributes("-toolwindow", True)
        except tk.TclError:
            pass
        try:
            w.attributes("-alpha", 0.95)
        except tk.TclError:
            pass
        w.configure(bg=BG_COLOR)
        # Don't steal focus on Windows
        try:
            w.attributes("-disabled", False)
        except tk.TclError:
            pass

        self._inner = tk.Frame(w, bg=BG_COLOR)
        self._inner.pack(padx=PAD_X, pady=PAD_Y)
        self._win = w

    def _destroy_window(self):
        if self._hide_after_id:
            try:
                self._root.after_cancel(self._hide_after_id)
            except Exception:
                pass
            self._hide_after_id = None
        if self._win is not None:
            try:
                self._win.destroy()
            except Exception:
                pass
        self._win = None
        self._inner = None

    def _show_burst(self, keys: list[str]):
        if not self._enabled or not keys:
            return
        # Re-create inner frame so we don't worry about leftover children
        self._ensure_window()
        if self._win is None or self._inner is None:
            return

        for child in self._inner.winfo_children():
            try:
                child.destroy()
            except Exception:
                pass

        # Sort: modifiers first (in canonical order), then the rest in press order
        order = ["ctrl", "left ctrl", "right ctrl",
                 "shift", "left shift", "right shift",
                 "alt", "left alt", "right alt", "alt gr",
                 "windows", "left windows", "right windows", "cmd"]
        mods_seen = []
        rest = []
        for k in keys:
            if k in _MODS:
                # collapse left/right duplicates by display name
                if _DISPLAY.get(k, k) not in [_DISPLAY.get(m, m) for m in mods_seen]:
                    mods_seen.append(k)
            else:
                rest.append(k)
        mods_seen.sort(key=lambda k: order.index(k) if k in order else 999)
        ordered = mods_seen + rest

        font_main = ("Segoe UI", self._font_size, "bold")
        font_plus = ("Segoe UI", max(10, self._font_size - 2), "bold")

        for i, k in enumerate(ordered):
            if i > 0:
                plus = tk.Label(
                    self._inner, text="+",
                    font=font_plus, fg=PLUS_COLOR, bg=BG_COLOR,
                    padx=2, pady=0,
                )
                plus.pack(side="left", padx=(KEY_GAP // 2, KEY_GAP // 2))

            cap_outer = tk.Frame(
                self._inner, bg=KEY_BORDER,
                highlightthickness=0, bd=0,
            )
            cap_outer.pack(side="left")
            cap_inner = tk.Label(
                cap_outer,
                text=_format_key(k),
                font=font_main,
                fg=self._font_color,
                bg=KEY_BG,
                padx=KEY_PAD_X, pady=KEY_PAD_Y,
            )
            # 1px border via outer frame's bg showing through
            cap_inner.pack(padx=1, pady=1)

        # Position bottom-right
        try:
            self._win.update_idletasks()
            ww = self._win.winfo_reqwidth()
            wh = self._win.winfo_reqheight()
            sw = self._win.winfo_screenwidth()
            sh = self._win.winfo_screenheight()
            x = max(0, sw - ww - MARGIN_R)
            y = max(0, sh - wh - MARGIN_B)
            self._win.geometry(f"{ww}x{wh}+{x}+{y}")
            self._win.deiconify()
            self._win.lift()
        except tk.TclError:
            return

        # Schedule auto-hide
        if self._hide_after_id:
            try:
                self._root.after_cancel(self._hide_after_id)
            except Exception:
                pass
        self._hide_after_id = self._root.after(HIDE_AFTER_MS, self._hide)

    def _hide(self):
        self._hide_after_id = None
        if self._win is not None:
            try:
                self._win.withdraw()
            except tk.TclError:
                pass
