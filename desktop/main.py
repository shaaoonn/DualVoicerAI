# ===============================================================================
# FIX FOR PYINSTALLER --WINDOWED MODE
# Developer Team Solution: NullWriter class to prevent speech_recognition crash
# Must be at the VERY TOP of the file, before any other imports
# ===============================================================================
import sys
import os

# FIX: Force UTF-8 encoding on Windows to prevent UnicodeEncodeError with Bengali text
if sys.platform == 'win32':
    os.environ.setdefault('PYTHONUTF8', '1')
    if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
        try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except Exception: pass
    if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
        try: sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        except Exception: pass

# DPI AWARENESS — UNAWARE_GDISCALED (Win10 1809+).
#
# History: we previously toggled between Per-Monitor V2 (sharp 4K but
# breaks mixed-DPI multi-monitor layout because CTk's
# set_widget_scaling locks at startup based on the primary monitor)
# and full DPI-Unaware bitmap-scaling (consistent layout but text
# looks washed-out / pixelated on 4K and 2K screens).
#
# Windows 10 v1809 added a third option that solves both: declaring
# the process **DPI_AWARENESS_CONTEXT_UNAWARE_GDISCALED** (-5). The
# app still believes it is 96-DPI Unaware (so every pixel-coordinate
# calculation we do — drag positions, drawer geometry, pen overlay
# bounds — stays unchanged), BUT Windows uses GDI scaling instead of
# bitmap zoom when painting the window to the screen. Concrete net:
# text and vector glyphs are rendered at the display's NATIVE pixel
# density, while images and our pen-canvas strokes still scale via
# bitmap zoom. Practically: settings panel + drawer + toolbar text
# all become crisp on 4K, with zero changes to our layout math.
#
# The manifest already declares `<gdiScaling>true</gdiScaling>`, but
# that flag only activates when the process awareness is one of the
# explicit GDI-scaled contexts. The PyInstaller --windowed bootloader
# launches the EXE as plain Unaware (lasterr=0 from
# SetProcessDpiAwarenessContext implies awareness was set elsewhere
# before our user code runs — see dpi_early_diag.log), which is why
# the manifest line on its own had no effect. We have to call the API
# again here, before any tkinter import.
#
# Fallback chain: UNAWARE_GDISCALED → PerMonitorV2 → System-Aware →
# legacy SetProcessDPIAware. The first one that doesn't NameError /
# OSError wins.
import ctypes as _ct

def _enable_gdi_scaled_dpi() -> str:
    """Try to put the process into UNAWARE_GDISCALED mode.

    Returns a short string identifying which API succeeded, for
    diagnostics. Silent failure is fine — we just fall through to
    whatever mode Windows defaulted to.

    Note on ctypes: ``SetProcessDpiAwarenessContext`` takes a
    ``DPI_AWARENESS_CONTEXT`` HANDLE (an opaque void* in Win32 ABI).
    Without explicit ``argtypes`` / ``restype`` the default ctypes
    convention coerces the Python int to ``c_int``, which silently
    truncates on 64-bit and the API rejects the call. We must
    declare the prototype as ``c_void_p`` so the negative sentinel
    values (-1 .. -5) round-trip as ``INVALID_HANDLE_VALUE``-style
    pseudo-handles instead of getting clipped.
    """
    try:
        fn = _ct.windll.user32.SetProcessDpiAwarenessContext
        fn.argtypes = [_ct.c_void_p]
        fn.restype = _ct.c_bool
        # DPI_AWARENESS_CONTEXT_UNAWARE_GDISCALED = -5 — Win10 1809+,
        # the ideal mode for our app.
        if fn(_ct.c_void_p(-5)):
            return "UNAWARE_GDISCALED"
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4 — Win10
        # 1703+. Sharp text but breaks our layout math on mixed-DPI
        # multi-monitor setups (CTk widget scaling is global, not
        # per-window).
        if fn(_ct.c_void_p(-4)):
            return "PER_MONITOR_AWARE_V2"
    except (AttributeError, OSError):
        pass
    try:
        # Win8.1+ fallback. 2 == PROCESS_PER_MONITOR_DPI_AWARE.
        _ct.windll.shcore.SetProcessDpiAwareness(2)
        return "PER_MONITOR_AWARE"
    except (AttributeError, OSError):
        pass
    try:
        # Vista+ last-ditch.
        _ct.windll.user32.SetProcessDPIAware()
        return "SYSTEM_AWARE"
    except (AttributeError, OSError):
        pass
    return "UNAWARE"

_dpi_mode = _enable_gdi_scaled_dpi()

# 1. ডামি ক্লাস যা সব আউটপুট 'গিলে' ফেলবে
class NullWriter:
    def write(self, data):
        pass
    def flush(self):
        pass

# 2. --windowed (Frozen) stdout fix (ROBUST)
# Frozen (EXE) মোডে থাকলে বা stdout না থাকলে, আমরা সব আউটপুট বন্ধ করে দেব
# এতে বাফার বাফার ফুল হয়ে অ্যাপ ফ্রিজ হওয়া আটকাবে
if getattr(sys, 'frozen', False) or sys.stderr is None:
    sys.stderr = NullWriter()

if getattr(sys, 'frozen', False) or sys.stdout is None:
    sys.stdout = NullWriter()

# 3. ইনপুট চ্যানেল ব্লক করা (গুরুত্বপূর্ণ)
if sys.stdin is None:
    try:
        sys.stdin = open(os.devnull, 'r')
    except Exception:
        pass

# --- এরপর বাকি লাইব্রেরি ইমপোর্ট করুন ---
import customtkinter as ctk
import speech_recognition as sr
import threading
import time
# Fix: Create lightweight cv2 mock instead of loading heavy OpenCV
# pyscreeze (pyautogui dependency) checks cv2.__version__ at import
import types
_cv2_mock = types.ModuleType('cv2')
_cv2_mock.__version__ = '0.0.0'
sys.modules['cv2'] = _cv2_mock
import pyautogui
import pyperclip
import pygame
import webbrowser
import asyncio          # Required for edge_tts async TTS engine
import uuid
import edge_tts
from PIL import Image, ImageDraw, ImageFont
import ctypes
import ctypes.wintypes
import socket
import pystray
from pystray import MenuItem as item
import queue
import keyboard
import winreg
import tempfile
import requests
import tkinter as tk
from tkinter import messagebox
import datetime
import json
import subprocess
import re
import winsound


# Auto-Update System
from updater import UpdateChecker, UpdateDownloader, UpdateInstaller
from i18n import tr

# Application Version
# App constants (version, default settings, UI palette) live in
# app/constants.py now. Re-imported here so existing references in main.py
# (APP_VERSION, DEFAULT_SETTINGS, etc.) keep working transparently.
from app.constants import (  # noqa: E402
    APP_VERSION,
    BTN_SIZES,
    DEFAULT_SETTINGS,
    DRAWER_ACTIVE,
    DRAWER_BG,
    DRAWER_BORDER,
    DRAWER_HEADER,
    DRAWER_MUTED,
    DRAWER_ROW_BG,
    DRAWER_ROW_HV,
    DRAWER_TEXT,
    TOOLBAR_BG,
    UPDATE_REPO_URL,
)

# Module-level helpers (format_size, resource_path, silent_restart) live in
# app/helpers.py now. Import them here so the rest of main.py's references
# resolve transparently — call sites stay unchanged.
from app.helpers import format_size, resource_path, silent_restart  # noqa: E402

# Network timeout for Google STT API (10s = handles large audio chunks without timeout)
from app.helpers import install_socket_default_timeout  # noqa: E402
install_socket_default_timeout(10)


# Firebase removed - Uses API now

ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

# CTk scaling locked to 1.0 to pair with the UNAWARE_GDISCALED DPI
# mode set above. The app advertises itself as 96-DPI Unaware, so all
# our geometry math (widget sizes, drawer widths, pen toolbar dims,
# Toplevel geometry strings) stays in plain logical pixels. Windows
# then uses GDI scaling — not bitmap zoom — to render the actual
# pixels on the display: text glyphs and vector primitives are drawn
# at the monitor's native resolution. End result on a 4K screen:
# layout is identical to a 1080p machine (drag positions, click
# regions, drawer alignment all match) but text and icons render
# crisply instead of looking pixelated/washed-out.
ctk.set_widget_scaling(1.0)
ctk.set_window_scaling(1.0)
print(f"[DPI] Awareness: {_dpi_mode}; CTk locked at 1.0x")


# The VoiceTypingApp class itself — assembled from a stack of mixins
# under app/ and auth/ — now lives in app/app_core.py. Importing it here
# keeps the entry-point shape (`app = VoiceTypingApp()` below) unchanged
# while collapsing what was once ~5,500 lines of inlined class body into
# a single line. See app/app_core.py for the mixin order and __init__
# orchestration.
from app.app_core import VoiceTypingApp  # noqa: E402



if __name__ == "__main__":
    app = VoiceTypingApp()
    
    # Cleanup handler - Remove lock file + unregister fonts on exit
    def cleanup():
        try:
            from auth.single_instance import release_lock
            if hasattr(app, 'lock_file'):
                release_lock(app.lock_file)
        except Exception as e:
            print(f"[WARNING] Lock file cleanup failed: {e}")
        try:
            from font_manager import unregister_all_fonts
            unregister_all_fonts()
        except Exception:
            pass
    
    import atexit
    atexit.register(cleanup)
    
    try:
        app.mainloop()
    finally:
        cleanup()
