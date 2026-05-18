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

# DPI AWARENESS — intentionally DISABLED.
#
# We previously set Per-Monitor DPI Awareness V2 here so high-DPI
# displays (4K/2K/Retina) would render text crisply. The trouble:
# CTk's set_widget_scaling() is applied ONCE at startup based on the
# primary monitor's scale factor. On a multi-DPI system (e.g. a 4K
# laptop screen + a 1080p secondary monitor) the widget appears at
# the WRONG size on whichever monitor doesn't match the primary,
# AND the settings panel / pen toolbar / drawer geometry — all
# computed in raw pixels — gets mismatched against CTk's pre-scaled
# widgets. Result: completely broken UI on the 4K laptop while the
# 1080p dev machine looks fine.
#
# The clean cross-DPI fix is to LET WINDOWS BITMAP-SCALE the entire
# app. Without a SetProcessDpiAwareness call (and without a manifest
# declaring awareness), the OS treats us as "DPI Unaware" and scales
# the rendered window uniformly to match each monitor's DPI. Text is
# slightly softer on 4K than native rendering, but the LAYOUT is
# pixel-identical across every machine — which matters far more for
# a deployable widget app.
#
# If we ever want crisp 4K text back, the proper path is to make
# every geometry calculation (btn_size, drawer width, panel size,
# Toplevel geometry strings) multiply by GetDpiForWindow(hwnd) at
# draw time — a bigger refactor than just toggling awareness.

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

# CTk scaling locked to 1.0 to pair with the disabled DPI awareness
# above. Windows handles all per-display scaling via bitmap zoom; CTk
# renders widgets at their logical (1.0x) size so the layout matches
# our hardcoded geometry calculations. Without this lock, CTk's
# auto-scaling would still query the primary monitor's DPI and bloat
# the settings panel on high-DPI machines while the rest of the
# widget stayed at 1.0x — exactly the breakage we're working around.
ctk.set_widget_scaling(1.0)
ctk.set_window_scaling(1.0)
print("[DPI] App is DPI-Unaware — Windows bitmap-scales; CTk locked at 1.0x")


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
