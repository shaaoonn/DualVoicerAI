# ll_hook.py
"""Low-level Windows keyboard hook + SendInput wrappers via ctypes.

Used by `keyboard_input.py` to install a WH_KEYBOARD_LL hook with
RELIABLE per-event suppression — something the third-party `keyboard`
package's `add_hotkey(suppress=True)` does not provide consistently
on Windows.

Architecture:
  - Hook runs on a dedicated thread with its own Win32 message loop
    (LL hooks REQUIRE a message loop on the installing thread).
  - Hook callback decides per-event whether to block. Heavy work is
    NOT done in the hook — Windows imposes a 5-second timeout.
  - `send_*` helpers tag every synthesised event with `SELF_MARKER`
    in `dwExtraInfo` so the hook can recognise its own echoes and
    pass them through without re-processing.

The two SendInput modes used:
  - `KEYEVENTF_UNICODE` — types arbitrary Unicode chars (incl. all
    of Bengali) reliably without needing the focused app to have a
    Bengali keyboard layout selected. Much cleaner than clipboard.
  - VK-based — for controlling backspace.
"""

from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes


user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


# ── Constants ────────────────────────────────────────────────────
WH_KEYBOARD_LL = 13
HC_ACTION = 0
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_QUIT = 0x0012

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

# Magic value placed in dwExtraInfo on every event we synthesise so the
# hook callback can recognise its own echoes and skip them.
SELF_MARKER = 0xDEADBEEF

# VK codes
VK_SHIFT, VK_CONTROL, VK_MENU = 0x10, 0x11, 0x12
VK_LWIN, VK_RWIN = 0x5B, 0x5C
VK_BACK, VK_RETURN, VK_TAB, VK_SPACE, VK_ESCAPE = 0x08, 0x0D, 0x09, 0x20, 0x1B
VK_CAPITAL = 0x14

# OEM keys → US-layout char (base, no shift). Used to recognise
# punctuation as word boundaries.
_OEM_VK_TO_CHAR = {
    0xBA: ';',  0xBB: '=',  0xBC: ',',  0xBD: '-',
    0xBE: '.',  0xBF: '/',  0xC0: '`',  0xDB: '[',
    0xDC: '\\', 0xDD: ']',  0xDE: "'",
}
_OEM_SHIFT_CHAR = {
    ';': ':', '=': '+', ',': '<', '-': '_', '.': '>',
    '/': '?', '`': '~', '[': '{', '\\': '|', ']': '}', "'": '"',
}
_DIGIT_SHIFT_CHARS = ')!@#$%^&*('


# ── Structures ───────────────────────────────────────────────────
class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]

class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]

class _INPUT_I(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT)]

class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("ii", _INPUT_I)]


# ── Function prototypes ──────────────────────────────────────────
LRESULT = ctypes.c_long
HOOKPROC = ctypes.WINFUNCTYPE(
    LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

user32.SetWindowsHookExW.argtypes = [
    ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
user32.UnhookWindowsHookEx.restype = wintypes.BOOL
user32.CallNextHookEx.argtypes = [
    wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
user32.CallNextHookEx.restype = LRESULT
user32.SendInput.argtypes = [
    wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.GetMessageW.argtypes = [
    ctypes.c_void_p, wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = wintypes.BOOL
user32.PostThreadMessageW.argtypes = [
    wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostThreadMessageW.restype = wintypes.BOOL
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.GetCurrentThreadId.argtypes = []
kernel32.GetCurrentThreadId.restype = wintypes.DWORD


# ── SendInput helpers (all events get SELF_MARKER) ───────────────

def _make_kbd_input(vk: int = 0, scan: int = 0, flags: int = 0) -> INPUT:
    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    inp.ii.ki.wVk = vk
    inp.ii.ki.wScan = scan
    inp.ii.ki.dwFlags = flags
    inp.ii.ki.time = 0
    inp.ii.ki.dwExtraInfo = SELF_MARKER
    return inp


def send_backspaces(count: int) -> None:
    """Send `count` backspace events (down + up each) atomically."""
    if count <= 0:
        return
    inputs = (INPUT * (count * 2))()
    for i in range(count):
        d = _make_kbd_input(vk=VK_BACK)
        u = _make_kbd_input(vk=VK_BACK, flags=KEYEVENTF_KEYUP)
        inputs[i*2] = d
        inputs[i*2 + 1] = u
    user32.SendInput(count * 2, inputs, ctypes.sizeof(INPUT))


def send_unicode_string(text: str) -> None:
    """Type a Unicode string via KEYEVENTF_UNICODE — works for any
    codepoint including Bengali conjuncts. No clipboard needed."""
    if not text:
        return
    # Compute total INPUT count (surrogate pairs for codepoints > BMP)
    n = 0
    for ch in text:
        n += 2 if ord(ch) <= 0xFFFF else 4
    inputs = (INPUT * n)()
    idx = 0
    for ch in text:
        cp = ord(ch)
        if cp <= 0xFFFF:
            inputs[idx]   = _make_kbd_input(scan=cp, flags=KEYEVENTF_UNICODE)
            inputs[idx+1] = _make_kbd_input(scan=cp,
                                            flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)
            idx += 2
        else:
            cp -= 0x10000
            high = 0xD800 + (cp >> 10)
            low  = 0xDC00 + (cp & 0x3FF)
            for code in (high, low):
                inputs[idx]   = _make_kbd_input(scan=code, flags=KEYEVENTF_UNICODE)
                inputs[idx+1] = _make_kbd_input(scan=code,
                                                flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)
                idx += 2
    user32.SendInput(n, inputs, ctypes.sizeof(INPUT))


def vk_to_char(vk: int, has_shift: bool) -> str:
    """Map a VK code to its US-layout character. Returns '' if not a
    text-producing key."""
    if 0x41 <= vk <= 0x5A:        # A-Z
        ch = chr(vk)
        return ch if has_shift else ch.lower()
    if 0x30 <= vk <= 0x39:        # 0-9
        return _DIGIT_SHIFT_CHARS[vk - 0x30] if has_shift else chr(vk)
    if vk == VK_SPACE:  return ' '
    if vk == VK_RETURN: return '\n'
    if vk == VK_TAB:    return '\t'
    if vk in _OEM_VK_TO_CHAR:
        ch = _OEM_VK_TO_CHAR[vk]
        return _OEM_SHIFT_CHAR.get(ch, ch) if has_shift else ch
    return ''


# ── Hook class ───────────────────────────────────────────────────

class LLKeyboardHook:
    """Background thread that installs WH_KEYBOARD_LL and runs a
    Win32 message loop (required for LL hooks). Forward each event
    to `on_key` which returns True to suppress."""

    def __init__(self, on_key):
        """on_key(vk, is_down, has_shift, has_ctrl, has_alt) -> bool"""
        self.on_key = on_key
        self._hook = None
        self._thread = None
        self._proc = None        # keep ref so ctypes doesn't GC it
        self._thread_id = None
        self._installed = threading.Event()

    def start(self) -> bool:
        if self._thread and self._thread.is_alive():
            return True
        self._installed.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="LL-Hook")
        self._thread.start()
        self._installed.wait(timeout=2)
        return self._hook is not None

    def stop(self) -> None:
        if self._thread_id:
            try:
                user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
            except Exception:
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)
        self._thread = None
        self._thread_id = None
        self._hook = None

    def _run(self) -> None:
        h_module = kernel32.GetModuleHandleW(None)
        self._proc = HOOKPROC(self._hook_callback)
        self._hook = user32.SetWindowsHookExW(
            WH_KEYBOARD_LL, self._proc, h_module, 0)
        self._thread_id = kernel32.GetCurrentThreadId()

        if not self._hook:
            err = ctypes.get_last_error()
            print(f"[LL-HOOK] SetWindowsHookExW failed: {err}")
            self._installed.set()
            return

        print(f"[LL-HOOK] Installed (thread {self._thread_id})")
        self._installed.set()

        # Message loop — REQUIRED for the LL hook to receive events.
        msg_buf = ctypes.create_string_buffer(64)  # MSG struct (~28 B)
        try:
            while True:
                ret = user32.GetMessageW(msg_buf, None, 0, 0)
                if ret == 0 or ret == -1:    # WM_QUIT or error
                    break
        finally:
            if self._hook:
                try:
                    user32.UnhookWindowsHookEx(self._hook)
                except Exception:
                    pass
                self._hook = None
            print("[LL-HOOK] Uninstalled")

    def _hook_callback(self, nCode, wParam, lParam):
        if nCode != HC_ACTION:
            return user32.CallNextHookEx(0, nCode, wParam, lParam)
        try:
            kbd = ctypes.cast(
                lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            extra = kbd.dwExtraInfo or 0
            if extra == SELF_MARKER:
                # Our own synthetic event — never re-process
                return user32.CallNextHookEx(0, nCode, wParam, lParam)

            vk = kbd.vkCode
            is_down = wParam in (WM_KEYDOWN, WM_SYSKEYDOWN)
            has_shift = bool(user32.GetAsyncKeyState(VK_SHIFT) & 0x8000)
            has_ctrl  = bool(user32.GetAsyncKeyState(VK_CONTROL) & 0x8000)
            has_alt   = bool(user32.GetAsyncKeyState(VK_MENU) & 0x8000)

            if self.on_key:
                if self.on_key(vk, is_down, has_shift, has_ctrl, has_alt):
                    return 1   # suppress
        except Exception as e:
            print(f"[LL-HOOK] callback error: {e}")
        return user32.CallNextHookEx(0, nCode, wParam, lParam)
