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


# BackgroundUpdateManager lives in app/background_updates.py now.
from app.background_updates import BackgroundUpdateManager  # noqa: E402

# Auth subsystem (login dialog, API client, auto-login, subscription polling)
# lives in auth/ now. AuthPanelMixin contributes all the methods that used
# to be inlined in VoiceTypingApp; ctk.CTk MUST stay first in the bases
# tuple so super().__init__() resolves to it.
from auth.auth_panel import AuthPanelMixin  # noqa: E402

# Update UI (Settings → Check for Update flow) lives in app/update_ui.py.
from app.update_ui import UpdateUIMixin  # noqa: E402

# Tray icon + button hover/press animations live in app/tray.py.
from app.tray import TrayMixin  # noqa: E402

# Window chrome (focus, drag, hover opacity, fullscreen) lives in
# app/window_chrome.py.
from app.window_chrome import WindowChromeMixin  # noqa: E402

# Settings I/O (save/load, toggles, sliders, toasts, popups) lives in
# app/settings_io.py.
from app.settings_io import SettingsIOMixin  # noqa: E402

# AI trigger flows (Ctrl+Shift+A, smart paste, screenshot vision) live in
# app/ai_actions.py.
from app.ai_actions import AIActionsMixin  # noqa: E402

# Screenshot capture + AI-button glow lives in app/screenshot.py.
from app.screenshot import ScreenshotMixin  # noqa: E402

# Pen-mode lifecycle (open/close, draw/view, slide animation) lives in
# app/pen_mode.py.
from app.pen_mode import PenModeMixin  # noqa: E402

# Global hotkey registration + keyboard overlay lives in app/hotkeys.py.
from app.hotkeys import HotkeyMixin  # noqa: E402

# UI builder (init_ui, _apply_window_size, geometry helpers) lives in
# app/ui_builder.py.
from app.ui_builder import UIBuilderMixin  # noqa: E402

# Embedded drawer system (BN/EN/SND/AI dropdowns) lives in app/drawers.py.
from app.drawers import DrawerMixin  # noqa: E402

# TTS reader pipeline (handle_reader_click, stream/play audio chunks) lives
# in app/tts.py.
from app.tts import TTSMixin  # noqa: E402

# Voice pipeline (text injection, AI translate buffer, mic + STT loops in B.18)
# lives in app/voice_pipeline.py.
from app.voice_pipeline import VoicePipelineMixin  # noqa: E402


class VoiceTypingApp(
    ctk.CTk,
    AuthPanelMixin,
    UpdateUIMixin,
    TrayMixin,
    WindowChromeMixin,
    SettingsIOMixin,
    AIActionsMixin,
    ScreenshotMixin,
    PenModeMixin,
    HotkeyMixin,
    UIBuilderMixin,
    DrawerMixin,
    TTSMixin,
    VoicePipelineMixin,
):
    def __init__(self):
        # ── Single-instance enforcement ────────────────────────────
        # Lock-file dance now lives in auth.single_instance. If
        # acquire_lock returns False there's already an alive
        # instance — we bail out immediately before any Tk init.
        from auth.single_instance import acquire_lock

        self.lock_file = os.path.join(tempfile.gettempdir(), "dual_voicer.lock")
        if not acquire_lock(self.lock_file):
            sys.exit(0)

        # Define base path for assets
        try:
            self.base_path = sys._MEIPASS
        except Exception:
            self.base_path = os.path.abspath(".")

        super().__init__()

        # Register bundled fonts (handwriting fonts for 20+ languages)
        try:
            from font_manager import register_all_fonts
            register_all_fonts()
        except Exception as e:
            print(f"[FONTS] Registration failed: {e}")

        # Hide window initially to prevent black square artifact
        self.withdraw()

        # Default settings (will be overwritten if file exists)
        self.settings = DEFAULT_SETTINGS.copy()
        
        # Device & Authentication tracking
        self.hardware_id = None  # Will be set after get_stable_hwid() call
        self.user_email = None
        self.is_authenticated = False
        self.device_count = 0
        self.account_status_label = None
        self.btn_login = None
        self.expiry_info_label = None
        self.auth_window = None # Singleton reference for login window
    
        # Initialize Audio Mixer (industry-standard: separate channels for SFX vs TTS)
        try:
            pygame.mixer.init()
            pygame.mixer.set_num_channels(8)
            pygame.mixer.set_reserved(1)  # Channel 0 reserved for SFX (start/end sounds)
            self._sfx_channel = pygame.mixer.Channel(0)
            # Pre-load SFX into memory for instant playback (won't conflict with TTS)
            try:
                self._sfx_start = pygame.mixer.Sound(resource_path("start-sound.wav"))
                self._sfx_end = pygame.mixer.Sound(resource_path("end-sound.wav"))
            except (pygame.error, FileNotFoundError):
                self._sfx_start = None
                self._sfx_end = None
        except Exception as e:
            print(f"[ERROR] Failed to init mixer: {e}")
            self._sfx_channel = None
            self._sfx_start = None
            self._sfx_end = None

        # TTS session management (prevents race conditions)
        self._tts_session_id = 0
        self._tts_lock = threading.Lock()


        # Load Settings (Persist in AppData)
        try:
            # Use %APPDATA%/DualVoicer for settings (Accessible & Persistent)
            self.app_data_dir = os.path.join(os.environ['APPDATA'], "DualVoicer")
            if not os.path.exists(self.app_data_dir):
                os.makedirs(self.app_data_dir)
            
            self.settings_file = os.path.join(self.app_data_dir, "settings.json")
            self.config_file = os.path.join(self.app_data_dir, ".dual_voicer_config.json")
            
            if os.path.exists(self.settings_file):
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    self.settings = json.load(f)
            else:
                self.settings = DEFAULT_SETTINGS.copy()
        except (OSError, json.JSONDecodeError, KeyError):
            # Fallback to defaults if AppData fails
            self.settings = DEFAULT_SETTINGS.copy()
            self.config_file = os.path.join(os.path.expanduser("~"), ".dual_voicer_config.json")
        
        # Merge new settings keys from config
        from config import DEV_MODE, NEW_SETTINGS_KEYS
        for k, v in NEW_SETTINGS_KEYS.items():
            if k not in self.settings:
                self.settings[k] = v

        # Initialize UI language from settings (default English)
        try:
            from i18n import set_ui_language
            set_ui_language(self.settings.get("ui_language", "en"))
        except Exception:
            pass

        # Keyboard-shortcut overlay (instantiated lazily; activated below)
        self._kb_overlay = None

        # DEV_MODE bypass - simulate authenticated premium user
        if DEV_MODE:
            self.is_authenticated = True
            self.user_email       = "dev@ejobsit.com"
            self.device_count     = 1
            self.max_devices      = 10
            self.user_cache       = {"plan_type": "Pro (Dev)", "expiry_date": "2099-12-31"}
            print("[DEV_MODE] Auth bypassed - all features unlocked")

        # Initialize Freemium Gate
        from subscription.freemium import FreemiumGate
        self.freemium = FreemiumGate(getattr(self, 'app_data_dir', os.path.join(os.environ.get('APPDATA', '.'), 'DualVoicer')))

        # Now set hardware ID (needs to be after class is initialized)
        self.hardware_id = self.get_stable_hwid()
        
        self.logo_img = None
        self.icon_path = resource_path("DualVoicerLogo.ico")
        self.tray_icon = None
        
        try:
            if os.path.exists(self.icon_path):
                self.iconbitmap(self.icon_path)
                pil_img = Image.open(self.icon_path)
                self.logo_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(60, 60))
        except Exception as e:
            print(f"Asset Error: {e}")

        self.title("Voice Typing Tool")
        self.overrideredirect(True)
        self.attributes('-topmost', True)
        self.attributes('-alpha', self.settings["idle_opacity"])
        self.transparent_color = "#010101"
        self.configure(fg_color=self.transparent_color)
        self.attributes('-transparentcolor', self.transparent_color)
        
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        _p = self.settings.get("size_preset", "medium")
        base_w, base_h = VoiceTypingApp._calc_dims(BTN_SIZES.get(_p, 72))
        
        # Check saved position from settings
        saved_x = self.settings.get("window_x")
        saved_y = self.settings.get("window_y")
        
        # Validate saved position is within visible screen area
        # Invalid if: None, negative, or beyond screen bounds
        is_valid_position = (
            saved_x is not None and 
            saved_y is not None and
            isinstance(saved_x, (int, float)) and 
            isinstance(saved_y, (int, float)) and
            saved_x >= 0 and  # Not on left monitor (negative)
            saved_x < screen_width and  # Not beyond right edge
            saved_y >= 0 and  # Not above screen
            saved_y < screen_height  # Not below screen
        )
        
        if is_valid_position:
            self.start_x = int(saved_x)
            self.start_y = int(saved_y)
            print(f"[POSITION] Restored: ({self.start_x}, {self.start_y})")
        else:
            # Default: Top center of PRIMARY screen
            self.start_x = (screen_width // 2) - (base_w // 2)
            self.start_y = 0  # Top of screen
            print(f"[POSITION] Default top center: ({self.start_x}, {self.start_y})")
            # Clear invalid saved position
            if saved_x is not None:
                self.settings["window_x"] = None
                self.settings["window_y"] = None
        
        _preset = self.settings.get("size_preset", "medium")
        _pw, _ph = VoiceTypingApp._calc_dims(BTN_SIZES.get(_preset, 72))
        self.geometry(f"{_pw}x{_ph}+{self.start_x}+{self.start_y}")

        self.drag_start = {"x": 0, "y": 0, "root_x": 0, "root_y": 0}
        self.is_dragging = False

        self.recognizer = sr.Recognizer()
        # Apply mic sensitivity setting
        self.apply_mic_sensitivity()
        # ---------------------------------------
        
        self.active_lang = None
        self.active_stt_lang = None
        self.active_target_lang = None
        self.is_listening = False
        self.is_processing = False
        self.last_speech_time = 0
        self.shutdown_flag = threading.Event()
        self.mic_start_event = threading.Event()  # Instant wakeup for mic thread
        self.mic_ready_event = threading.Event()   # Signal: mic is ready to receive speech
        self.audio_queue = queue.Queue()
        # ── Translation buffer (Voice AI Mode) ───────────────────────
        # In AI mode we DON'T translate each STT chunk in isolation —
        # instead we buffer chunks and flush after a brief silence so the
        # AI sees the complete sentence (lets it de-duplicate words and
        # apply punctuation correctly). Normal voice typing is unaffected.
        self._trans_buffer = []          # list[(text, src, tgt, token)]
        self._trans_buffer_lock = threading.Lock()
        self._trans_flush_after_id = None
        # Silence gap (ms) that triggers a flush. Tuned a bit longer than
        # a natural mid-sentence pause so a long thought split into
        # several utterances gets combined into ONE AI call. Keep this
        # >= 2500 — anything shorter and the user's "thinking pauses"
        # cause premature flushes that look like duplicated sentences.
        self._trans_silence_ms = 3000
        
        # Auto-Reset Counter: After N successful recognitions, reset the engine
        self.recognition_count = 0
        self.MAX_RECOGNITIONS_BEFORE_RESET = 30  # Higher = fewer disruptions
        
        self.current_text = ""
        self.is_reading = False
        self.is_paused = False
        self.error_state = False
        self.settings_window = None
        self._settings_win = None
        
        # Update UI components
        self.update_status_label = None
        self.update_progress = None
        self.btn_check_update = None
        
        self.cur_btn_w = 60
        self.cur_btn_h = 35
        self.cur_set_s = 20
        
        # Cache microphone list at startup (avoids slow loading in settings)
        self._cached_mic_list = ["Default Microphone"]
        self._cached_mic_map = {"Default Microphone": None}
        threading.Thread(target=self._cache_microphones, daemon=True).start()

        self.init_ui()
        self.apply_size_scaling()
        self.setup_hotkeys()
        self.apply_kb_overlay_setting()
        # Bengali Phonetic Input feature DISABLED in this version — the
        # pure-Python LL-hook approach proved too brittle across Windows
        # text fields. The supporting modules (keyboard_input.py,
        # ll_hook.py, avro_engine/) remain in the tree for a future
        # revival but no longer auto-activate.
        # self.apply_bengali_input_setting()

        # Pre-warm the OpenRouter HTTP connection in the background so the
        # FIRST translation call doesn't pay the TLS-handshake tax (~1s).
        # This is fire-and-forget — failures are silently ignored because
        # users without an API key shouldn't see errors at startup.
        def _prewarm_openrouter():
            try:
                from ai_engine.openrouter import _ensure_executor, run_on_executor, _get_session
                _ensure_executor()
                # Just open the TCP/TLS connection; don't actually send data.
                async def _warmup():
                    try:
                        await _get_session()
                    except Exception:
                        pass
                run_on_executor(_warmup(), timeout=5)
                print("[PREWARM] OpenRouter executor ready")
            except Exception as e:
                print(f"[PREWARM] skipped: {e}")
        threading.Thread(target=_prewarm_openrouter, daemon=True).start()

        # Pre-warm the audio subsystem (open mic for ~50ms then release).
        # WASAPI init takes 500ms-1s on first open — doing it now saves
        # that latency from the user's FIRST voice-button click.
        def _prewarm_mic():
            try:
                # Wait briefly so settings + recognizer are fully ready
                time.sleep(0.8)
                with sr.Microphone() as _src:
                    # Just opening + closing warms WASAPI / audio drivers.
                    pass
                print("[PREWARM] Audio subsystem ready")
            except Exception as e:
                print(f"[PREWARM] mic warmup skipped: {e}")
        threading.Thread(target=_prewarm_mic, daemon=True).start()

        # Pen tools slide-out panel state
        self._pen_tools_expanded = False
        self._pen_anim_job = None 

        self.bind("<Enter>", self.on_hover_enter)
        self.bind("<Leave>", self.on_hover_leave)

        threading.Thread(target=self.mic_listener_loop, daemon=True).start()
        threading.Thread(target=self.processing_loop, daemon=True).start()
        threading.Thread(target=self.init_tray_icon, daemon=True).start()
        
        self.monitor_topmost()
        self.check_and_add_to_startup()
        
        # Auto-login for same device (enables after first login)
        self.after(500, self.auto_login_if_saved)
        
        # SECURITY: Force login if not authenticated (fallback)
        # Increased delay to 3000ms to allow auto-login to complete (was 1500ms)
        self.after(3000, self.check_authenticate_on_startup)

        # CRITICAL: Show window after initialization (prevent it staying hidden)
        self.after(200, lambda: self.deiconify())

        # FOCUS FIX: Set WS_EX_NOACTIVATE so clicking widget doesn't steal focus
        self.after(400, self._set_no_activate)
        
        # Start Silent Background Update Manager
        self.update_manager = BackgroundUpdateManager(
            app_version=APP_VERSION,
            repo_url=UPDATE_REPO_URL,
            on_update_ready_callback=self.handle_update_ready
        )
        self.update_manager.start()


    def apply_mic_sensitivity(self):
        """
        Apply microphone settings (SIMPLIFIED v3.6.9).
        
        Uses manual noise_threshold from settings slider.
        Lower value = more sensitive (quiet environment)
        Higher value = filters more noise (noisy environment)
        """
        # CRITICAL: Fixed threshold prevents drift over time
        self.recognizer.dynamic_energy_threshold = False
        
        # Use manual threshold from settings slider (50-500)
        noise_level = self.settings.get("noise_threshold", 100)
        self.recognizer.energy_threshold = noise_level
        
        # BALANCED: Fast detection without cutting off last syllable
        self.recognizer.pause_threshold = 0.35     # শেষ অক্ষর মিস হওয়া রোধ + দ্রুত
        self.recognizer.non_speaking_duration = 0.25  # accuracy + speed balance
        self.recognizer.phrase_threshold = 0.2      # ছোট noise ফিল্টার, accuracy উন্নত
        
        print(f"[MIC] Noise threshold: {noise_level}")

    # ── HWID + login config — implementation in app.hwid ──────────
    # These are thin wrappers that forward to the pure functions in
    # app.hwid, passing in our instance paths (app_data_dir, config_file).
    # Existing call sites use `self.get_stable_hwid()`, `self.save_login_config(...)`,
    # etc., so we keep the same method signatures.

    def get_stable_hwid(self):
        """Return the persistent device fingerprint. See ``app.hwid.get_stable_hwid``."""
        from app.hwid import get_stable_hwid
        return get_stable_hwid(self.app_data_dir)

    def save_login_config(self, email, phone):
        """Persist the user's email + phone for auto-login."""
        from app.hwid import save_login_config
        save_login_config(self.config_file, email, phone)

    def load_login_config(self):
        """Return ``(email, phone)`` from saved config or ``(None, None)``."""
        from app.hwid import load_login_config
        return load_login_config(self.config_file)

    def clear_login_config(self):
        """Drop the saved login config (used on explicit logout)."""
        from app.hwid import clear_login_config
        clear_login_config(self.config_file)
    


    def _toggle_bengali_input(self):
        """Flip Bengali Phonetic Input ON/OFF and persist the new state."""
        try:
            from keyboard_input import get_instance
            mgr = get_instance()
            mgr.toggle()
            self.settings["bengali_input_enabled"] = mgr.enabled
            try:
                self.save_settings()
            except Exception:
                pass
        except Exception as e:
            print(f"[BENGALI-INPUT] toggle failed: {e}")

    def apply_bengali_input_setting(self):
        """Sync the input manager's state with the saved setting. Called
        on startup and after settings panel changes."""
        try:
            from keyboard_input import get_instance, is_available
            if not is_available():
                return
            mgr = get_instance()
            want = bool(self.settings.get("bengali_input_enabled", False))
            if want and not mgr.enabled:
                mgr.enable()
            elif not want and mgr.enabled:
                mgr.disable()
        except Exception as e:
            print(f"[BENGALI-INPUT] apply setting failed: {e}")

    def _route_clear_all(self):
        """Wipe whichever drawing surface is currently active — Pen Mode
        overlay OR Editor window. Triggered by the user's clear_all hotkey."""
        pt = getattr(self, '_pen_toolbar', None)
        po = getattr(self, '_pen_overlay', None)
        # Pen overlay first
        try:
            if po is not None and hasattr(po, 'clear_all'):
                root_w = getattr(pt, '_toolbar', None) or \
                         getattr(pt, '_root', None) if pt else None
                if root_w is not None and root_w.winfo_exists():
                    print("[ROUTE] -> pen overlay: clear_all")
                    po.clear_all()
                    return
        except Exception as ex:
            print(f"[ROUTE] pen clear_all failed: {ex}")
        # Editor window fallback
        ew = getattr(self, '_editor_win', None)
        try:
            if ew is not None and ew.winfo_exists() and \
                    ew.state() != 'withdrawn' and \
                    hasattr(ew, 'clear_all'):
                print("[ROUTE] -> editor: clear_all")
                ew.clear_all()
                return
        except Exception as ex:
            print(f"[ROUTE] editor clear_all failed: {ex}")
        print("[ROUTE] no surface active for clear_all")

    def _route_tool_shortcut(self, tool_name: str):
        """Dispatch a tool-switch shortcut to whichever drawing surface is
        currently active — Pen Mode overlay OR Editor window. Called from
        the global keyboard hook so it works even when another app has
        focus."""
        # Pen Mode overlay first — most users live here when annotating.
        pt = getattr(self, '_pen_toolbar', None)
        try:
            if pt is not None:
                # PenToolbar exposes _toggle_tool / _activate_eraser internally.
                # If the toolbar widget still exists, route there.
                root_w = getattr(pt, '_toolbar', None) or \
                         getattr(pt, '_root', None)
                if root_w is not None and root_w.winfo_exists():
                    print(f"[ROUTE] -> pen toolbar: {tool_name}")
                    if tool_name == "eraser":
                        pt._activate_eraser()
                    else:
                        pt._toggle_tool(tool_name)
                    return
        except Exception as ex:
            print(f"[ROUTE] pen toolbar dispatch failed: {ex}")
        # Editor window fallback.
        ew = getattr(self, '_editor_win', None)
        try:
            if ew is not None and ew.winfo_exists() and \
                    ew.state() != 'withdrawn':
                print(f"[ROUTE] -> editor: {tool_name}")
                ew._tool_shortcut(tool_name)
                return
        except Exception as ex:
            print(f"[ROUTE] editor dispatch failed: {ex}")
        # Neither active — open Pen Mode and apply the tool there.
        print(f"[ROUTE] no surface active — opening pen mode for {tool_name}")
        try:
            self.toggle_pen_mode()
            # Give pen mode a moment to set up, then apply the tool
            def _apply_after_open():
                pt2 = getattr(self, '_pen_toolbar', None)
                try:
                    if pt2 is not None:
                        if tool_name == "eraser":
                            pt2._activate_eraser()
                        else:
                            pt2._toggle_tool(tool_name)
                except Exception:
                    pass
            self.after(150, _apply_after_open)
        except Exception:
            pass



    # Class-attribute alias of the module-level constant so existing
    # `self.TOOLBAR_BG` references in mixins / call-sites keep working.
    TOOLBAR_BG = TOOLBAR_BG








    


    def _silent_reset(self):
        """Silent reset - no message shown to user. Called when manually stopping voice typing."""
        # Prevent cascading resets
        if getattr(self, '_resetting', False):
            return self._resetting
        self._resetting = True

        ok = False
        try:
            # Signal mic thread to restart
            self.restart_mic_flag = True

            # Clear audio queue
            if hasattr(self, 'audio_queue'):
                with self.audio_queue.mutex:
                    self.audio_queue.queue.clear()

            # Create fresh recognizer
            self.recognizer = sr.Recognizer()
            self.apply_mic_sensitivity()

            # Reset processing state
            self.is_processing = False

            # Reset error state and UI
            self.error_state = False
            self.after(0, self.update_ui_state)

            # Reset network socket timeout (keep consistent with global setting)
            socket.setdefaulttimeout(10)

            print("[SILENT RESET] Voice engine reset (user won't notice)")
            ok = True
        except Exception as e:
            print(f"[SILENT RESET ERROR] {e}")
        finally:
            self._resetting = False
        return ok






    def switch_language(self, lang):
        # DEV_MODE bypass + Authentication check
        from config import DEV_MODE
        if not DEV_MODE and not self.is_authenticated:
            print("[SECURITY BLOCK] Voice typing blocked - user not authenticated")
            self.after(0, self.open_auth_panel)
            return
        
        # Auto-pause TTS if playing
        if self.is_reading:
            self._pause_reader()

        self.error_state = False
        if self.active_lang == lang and self.is_listening:
            # STOPPING voice typing manually - do full reset
            # Force-flush any buffered AI text BEFORE we bump the token —
            # otherwise the user loses what they just said. The flush uses
            # the OLD token so the result still gets typed.
            try:
                if hasattr(self, "_trans_buffer_lock"):
                    has_buffered = False
                    with self._trans_buffer_lock:
                        has_buffered = bool(self._trans_buffer)
                    if has_buffered:
                        # Cancel pending silence timer and flush right now
                        if self._trans_flush_after_id is not None:
                            try:
                                self.after_cancel(self._trans_flush_after_id)
                            except Exception:
                                pass
                            self._trans_flush_after_id = None
                        self._flush_translation_buffer()
            except Exception as e:
                print(f"[TRANS-BUFFER] flush-on-stop failed: {e}")

            self.is_listening = False; self.active_lang = None
            # Clear translation state + bump token so any future stale
            # translation result (e.g. a chunk still mid-recognition) is
            # dropped before it reaches type_text.
            self.active_stt_lang = None
            self.active_target_lang = None
            self.translation_token = (getattr(self, "translation_token", 0) + 1) & 0xFFFFFFFF
            self.update_ui_state()
            # Play end sound via SFX channel (won't interrupt TTS)
            if self.settings.get("sound_enabled", True):
                try:
                    if self._sfx_channel and self._sfx_end:
                        self._sfx_channel.play(self._sfx_end)
                except pygame.error: pass
            # FULL RESET: Clear all stuck states
            self.after(200, self._silent_reset)
        else:
            # STARTING voice typing — bump translation token to drop any
            # in-flight translation result from a previous click. Implements
            # the user's "cancel old, start new" UX requirement.
            self.translation_token = (getattr(self, "translation_token", 0) + 1) & 0xFFFFFFFF
            # If switching from other lang while listening, do reset first
            if self.is_listening:
                self.is_listening = False
                self._silent_reset()
                time.sleep(0.1)

            # Start mic FIRST, then play sound when mic is ready
            self.mic_ready_event.clear()
            self.active_lang = lang; self.is_listening = True
            # Compute STT source language + translation target based on
            # the Translation Mode setting. Without translation, both are
            # the same (target = None means "no translation").
            self._refresh_translation_state()
            self.mic_start_event.set()  # Instant wakeup for mic thread
            # Propagate language to handwriting recognizer
            if hasattr(self, '_pen_overlay') and self._pen_overlay:
                hw_lang = "bn" if lang == "bn-BD" else "en"
                self._pen_overlay._engine.set_hw_language(hw_lang)
                # Auto-set font for language
                try:
                    from font_manager import get_font_for_language
                    hw_font = get_font_for_language(hw_lang)
                    self._pen_overlay._engine.set_hw_font(hw_font)
                except Exception:
                    pass
            self.update_ui_state(); self.last_speech_time = time.time()

            # Wait for mic to be ready (max 800ms), THEN play start sound via SFX channel
            def _play_start_sound_when_ready():
                self.mic_ready_event.wait(timeout=0.8)
                if self.settings.get("sound_enabled", True):
                    try:
                        if self._sfx_channel and self._sfx_start:
                            self._sfx_channel.play(self._sfx_start)
                    except pygame.error: pass
            threading.Thread(target=_play_start_sound_when_ready, daemon=True).start()

    def update_ui_state(self):
        if self.is_listening:
            if self.active_lang == self.settings.get("btn1_lang", "bn-BD"):
                self.btn_bn.set_state("listening")
                self.btn_en.set_state("idle")
            else:
                self.btn_en.set_state("listening")
                self.btn_bn.set_state("idle")
        else:
            self.btn_bn.set_state("idle")
            self.btn_en.set_state("idle")
        # btn_ai managed by ai_trigger_flow()




    def _refresh_translation_state(self):
        """Recompute STT source language + AI target based on per-button
        Voice AI Mode settings. Safe to call any time — from
        switch_language, from settings change handlers, etc.

        Result:
          self.active_stt_lang    — what to recognize as
          self.active_target_lang — what to send to AI (None = raw, no AI)
                                    Same as stt → cleanup mode
                                    Different from stt → translation
        """
        # ── One-time migration of the legacy master `translation_mode` key
        # to the new per-button enables. Runs at most once per session.
        if not getattr(self, "_voice_ai_migrated", False):
            legacy = self.settings.pop("translation_mode", None)
            if legacy is True:
                self.settings.setdefault("btn1_translate_enabled", True)
                self.settings.setdefault("btn2_translate_enabled", True)
                self.settings["btn1_translate_enabled"] = True
                self.settings["btn2_translate_enabled"] = True
                try:
                    self.save_settings()
                except Exception:
                    pass
                print("[MIGRATE] translation_mode → per-button enables")
            # Also infer the new picker-mode keys from existing booleans
            # so the dropdown UI shows the correct current selection.
            for idx in (1, 2):
                key = f"btn{idx}_voice_mode"
                if key not in self.settings:
                    enabled = self.settings.get(f"btn{idx}_translate_enabled", False)
                    own_lang = self.settings.get(
                        f"btn{idx}_lang", "bn-BD" if idx == 1 else "en-US")
                    src_lang = self.settings.get(
                        f"btn{idx}_translate_from",
                        "en-US" if idx == 1 else "bn-BD")
                    if not enabled:
                        self.settings[key] = "normal"
                    elif src_lang == own_lang:
                        self.settings[key] = "ai_polish"
                    else:
                        self.settings[key] = "ai_translate"
            # TTS source mode inference
            if "tts_source_mode" not in self.settings:
                if self.settings.get("tts_auto_detect", True):
                    self.settings["tts_source_mode"] = "auto"
                else:
                    voice = (self.settings.get("tts_voice") or "").lower()
                    btn1 = self.settings.get("btn1_lang", "bn-BD").split("-")[0].lower()
                    btn2 = self.settings.get("btn2_lang", "en-US").split("-")[0].lower()
                    if voice.startswith(btn1):
                        self.settings["tts_source_mode"] = "btn1"
                    elif voice.startswith(btn2):
                        self.settings["tts_source_mode"] = "btn2"
                    else:
                        self.settings["tts_source_mode"] = "auto"
            try:
                self.save_settings()
            except Exception:
                pass
            self._voice_ai_migrated = True

        if not getattr(self, "active_lang", None):
            self.active_stt_lang = None
            self.active_target_lang = None
            return

        btn1_lang = self.settings.get("btn1_lang", "bn-BD")
        btn2_lang = self.settings.get("btn2_lang", "en-US")

        # Figure out which of the two buttons this active_lang belongs to.
        if self.active_lang == btn1_lang:
            ai_on = bool(self.settings.get("btn1_translate_enabled", False))
            stt_from = self.settings.get("btn1_translate_from", "en-US")
        elif self.active_lang == btn2_lang:
            ai_on = bool(self.settings.get("btn2_translate_enabled", False))
            stt_from = self.settings.get("btn2_translate_from", "bn-BD")
        else:
            ai_on = False
            stt_from = self.active_lang

        if not ai_on:
            self.active_stt_lang = self.active_lang
            self.active_target_lang = None
            print(f"[VOICE-AI] off — stt={self.active_lang}")
            return

        # AI on — STT in source lang, AI cleans/translates to button lang.
        self.active_stt_lang = stt_from
        self.active_target_lang = self.active_lang
        mode = "cleanup" if stt_from == self.active_lang else "translate"
        print(f"[VOICE-AI] {mode}: stt={stt_from} → ai={self.active_lang}")

    def mic_listener_loop(self):
        # STABILITY UPDATE v3.5.4: Robust Loop with Watchdog Support
        # - Instant start (shortened calibration)
        # - Continuous listening without aggressive cutoffs
        # - Self-healing connection
        
        self.restart_mic_flag = False
        retry_count = 0

        while not self.shutdown_flag.is_set():
            # 1. Wait until listening is enabled (Event-based = instant wakeup)
            self.mic_start_event.clear()
            while not self.is_listening and not self.shutdown_flag.is_set():
                self.mic_start_event.wait(timeout=0.5)
                self.mic_start_event.clear()
                retry_count = 0

            if self.shutdown_flag.is_set(): break
            
            try:
                # Get current settings
                mic_index = self.settings.get("mic_index")
                
                # Fallback logic
                if retry_count > 3:
                     print("[WARNING] Multiple failures, falling back to default microphone")
                     mic_index = None 
                     
                print(f"[DEBUG] Opening Mic Stream (Index: {mic_index if mic_index is not None else 'Default'})")
                
                # 2. Acquire Microphone Resource
                with sr.Microphone(device_index=mic_index) as source:
                    # v3.6.9: NO AUTO CALIBRATION - using manual Noise Filter slider
                    # This is much faster and more predictable
                    self.apply_mic_sensitivity()
                    print(f"[DEBUG] Using threshold: {self.recognizer.energy_threshold}")

                    retry_count = 0

                    # Signal that mic is ready (for start sound timing)
                    self.mic_ready_event.set()

                    # 3. Active Listening Loop
                    print("[INFO] Mic listening...")
                    self.restart_mic_flag = False
                    self.last_process_time = time.time() # Initialize timestamp
                    
                    while self.is_listening and not self.shutdown_flag.is_set():
                        # Watchdog check
                        if self.restart_mic_flag:
                             print("[INFO] Watchdog requested restart")
                             break
                        
                        # Settings check
                        if self.settings.get("mic_index") != mic_index:
                            print("[INFO] Mic changed, reopening stream...")
                            break 
                        
                        # Auto-stop timeout check
                        try:
                            timeout_val = str(self.settings.get("auto_timeout", "15"))
                            if timeout_val in ("0", "99999", ""):
                                allowed = 999999  # infinite
                            else:
                                allowed = float(timeout_val)
                        except (ValueError, TypeError): allowed = 15.0

                        if allowed < 999999 and time.time() - self.last_speech_time > allowed:
                            print("[INFO] Auto-stop timeout reached")
                            self.is_listening = False; self.active_lang = None
                            self.after(0, self.update_ui_state)
                            # Play end sound on auto-timeout via SFX channel
                            if self.settings.get("sound_enabled", True):
                                try:
                                    if self._sfx_channel and self._sfx_end:
                                        self._sfx_channel.play(self._sfx_end)
                                except pygame.error: pass
                            # Silent reset: clear cache & refresh engine
                            self.after(200, self._silent_reset)
                            break
                            
                        # Queue cleanup: keep latest 2 chunks, discard oldest
                        while self.audio_queue.qsize() > 3:
                            try:
                                self.audio_queue.get_nowait()
                                self.audio_queue.task_done()
                            except queue.Empty:
                                break
                                
                        try:
                            # ── Adaptive listen() configuration ─────────
                            # Translation/cleanup (AI) mode: wait for the
                            # user to PAUSE for ~1s before returning, and
                            # allow up to 60s of continuous speech in one
                            # chunk. This way the entire long sentence is
                            # captured as ONE audio chunk → ONE recognition
                            # call → ONE translation. No fake "duplicate
                            # sentences" from chunk splits.
                            #
                            # Normal voice typing: keep the original
                            # snappy 8s phrase limit + tight 0.35s pause
                            # threshold so chunks land in the typed text
                            # quickly. THIS BEHAVIOUR IS UNCHANGED.
                            if getattr(self, "active_target_lang", None):
                                self.recognizer.pause_threshold = 1.0
                                phrase_limit = 60
                            else:
                                self.recognizer.pause_threshold = 0.35
                                phrase_limit = 8
                            audio = self.recognizer.listen(
                                source, timeout=1.0,
                                phrase_time_limit=phrase_limit)
                            # Race guard: listen() can block up to phrase_time_limit
                            # seconds. If the user stopped typing in the meantime,
                            # active_lang has been cleared to None - queueing it
                            # would later cause recognize_google() to error with
                            # "`language` must be a string". Drop stale chunks.
                            # In translation mode, STT runs in the SOURCE
                            # language (e.g. en-US for the Bengali button)
                            # and we translate to the TARGET (active_lang).
                            captured_lang = (
                                getattr(self, "active_stt_lang", None)
                                or self.active_lang
                            )
                            captured_target = getattr(
                                self, "active_target_lang", None)
                            captured_token = getattr(
                                self, "translation_token", 0)
                            if not self.is_listening or not isinstance(captured_lang, str) or not captured_lang:
                                continue
                            self.audio_queue.put(
                                (audio, captured_lang, captured_target, captured_token))
                            
                            # CRITICAL: Update watchdog timestamp
                            self.last_process_time = time.time()
                            self.last_speech_time = time.time() 
                            
                        except sr.WaitTimeoutError:
                            # Still alive, just silent. Update watchdog so we don't restart unnecessarily
                            # (Unless we want to restart on pure silence? No, silence is valid)
                            self.last_process_time = time.time() 
                            continue 
                        except Exception as e:
                            print(f"[WARNING] Listen loop error: {e}")
                            break 
                            
                print("[DEBUG] Mic Stream Closed")
                
            except OSError as e:
                print(f"[ERROR] OS Mic Error: {e}")
                retry_count += 1
                time.sleep(1)
                
            except Exception as e:
                print(f"[ERROR] Mic Init Failed: {e}")
                retry_count += 1
                time.sleep(1)






    # ─────── Dropdown arrow handlers (BN / EN / SND / AI) ──────────

    @staticmethod
    def _lang_display(code: str) -> str:
        """Return a human-readable name for a BCP-47 language code,
        falling back to the code itself if unknown."""
        try:
            from ui_components.language_data import GOOGLE_STT_LANGUAGES
            for name, c in GOOGLE_STT_LANGUAGES:
                if c == code:
                    return name
        except Exception:
            pass
        return code

    # ── Drawer click handlers (called by DropdownArrow widgets) ────


    # ───────────────────────────────────────────────────────────────




    def processing_loop(self):
        """
        Robust processing loop that never dies.
        Handles network timeouts and efficiently processes audio.
        Uses threaded recognition with hard timeout to prevent stuck states.
        """
        consecutive_errors = 0

        while not self.shutdown_flag.is_set():
            try:
                # 1. Get audio from queue (non-blocking wait)
                try:
                    item = self.audio_queue.get(timeout=0.2)
                except queue.Empty:
                    continue

                # Backwards-compat: old 2-tuple (audio, lang) still works.
                # New 4-tuple is (audio, stt_lang, target_lang, token) for
                # translation-mode dispatch.
                if isinstance(item, tuple) and len(item) >= 4:
                    audio_data, lang, target_lang, captured_token = item[:4]
                elif isinstance(item, tuple) and len(item) == 2:
                    audio_data, lang = item
                    target_lang = None
                    captured_token = 0
                else:
                    print(f"[SKIP] Dropping audio chunk with bad shape: {type(item)}")
                    self.audio_queue.task_done()
                    continue

                # Defensive: a stale chunk could still slip in between the
                # listener's race guard and the queue. recognize_google() needs
                # a non-empty string for `language`, otherwise it throws.
                if not isinstance(lang, str) or not lang:
                    print(f"[SKIP] Dropping audio chunk with invalid lang={lang!r}")
                    self.audio_queue.task_done()
                    continue

                self.is_processing = True

                # 2. Process Audio with HARD TIMEOUT (prevents stuck state)
                try:
                    txt = None
                    recognition_result = [None]
                    recognition_error = [None]

                    def do_recognize():
                        _t0 = time.time()
                        try:
                            recognition_result[0] = self.recognizer.recognize_google(audio_data, language=lang)
                            _dt = (time.time() - _t0) * 1000
                            if recognition_result[0]:
                                print(f"[STT] {lang} in {_dt:.0f}ms: '{recognition_result[0]}'")
                        except sr.UnknownValueError:
                            pass  # Speech not detected - normal
                        except sr.RequestError as e:
                            recognition_error[0] = e
                        except Exception as e:
                            recognition_error[0] = e

                    # Run recognition in thread with 8-second hard timeout
                    rec_thread = threading.Thread(target=do_recognize, daemon=True)
                    rec_thread.start()
                    rec_thread.join(timeout=8)

                    if rec_thread.is_alive():
                        # Recognition timed out - skip this chunk
                        print("[WARNING] Recognition timed out (8s), skipping chunk")
                        consecutive_errors += 1
                        if consecutive_errors >= 3:
                            print("[AUTO-RECOVERY] Too many timeouts, refreshing recognizer")
                            self.recognizer = sr.Recognizer()
                            self.apply_mic_sensitivity()
                            consecutive_errors = 0
                        continue

                    if recognition_error[0]:
                        if isinstance(recognition_error[0], sr.RequestError):
                            print(f"[ERROR] Network/API Error: {recognition_error[0]}")
                            self.after(0, self.show_network_error)
                            consecutive_errors += 1
                        else:
                            print(f"[ERROR] Recognition Error: {recognition_error[0]}")
                            consecutive_errors += 1

                        if consecutive_errors >= 3:
                            print("[AUTO-RECOVERY] Too many errors, refreshing recognizer")
                            self.recognizer = sr.Recognizer()
                            self.apply_mic_sensitivity()
                            consecutive_errors = 0
                        txt = None
                    else:
                        txt = recognition_result[0]
                        if txt:
                            consecutive_errors = 0  # Reset on success
    
                    if txt:
                        self.last_speech_time = time.time()

                        # AUTO-REFRESH: Lightweight engine refresh (v3.6.9)
                        # Only refresh recognizer, don't restart mic loop
                        self.recognition_count += 1
                        if self.recognition_count >= self.MAX_RECOGNITIONS_BEFORE_RESET:
                            print(f"[AUTO-REFRESH] Refreshing recognizer after {self.recognition_count} recognitions")
                            # Lightweight refresh: reset recognizer only, DON'T clear queue
                            self.recognizer = sr.Recognizer()
                            self.apply_mic_sensitivity()
                            self.recognition_count = 0

                    if txt:
                        # Voice commands run on the RAW transcribed text
                        # (regardless of AI mode) so commands like
                        # "backspace" / "select all" never get translated.
                        raw_lower = txt.lower().strip()

                        # --- VOICE COMMANDS ---
                        if raw_lower in ["backspace", "ব্যাকস্পেস", "ব্যাক স্পেস"]:
                            pyautogui.press('backspace')
                        elif raw_lower in ["back sentence", "ব্যাক সেন্টেন্স", "ব্যাক সেন টেন্স"]:
                            pyautogui.hotkey('ctrl', 'z')
                        elif raw_lower in ["select all", "সিলেক্ট অল", "সিলেক্ট করি", "সব সিলেক্ট"]:
                            pyautogui.hotkey('ctrl', 'a')
                        elif raw_lower in ["copy", "কপি", "কপি করি"]:
                            pyautogui.hotkey('ctrl', 'c')
                        elif raw_lower in ["paste", "পেস্ট", "পেস্ট করি"]:
                            try:
                                content = pyperclip.paste()
                                pyperclip.copy(content)
                                time.sleep(0.01)
                                pyautogui.hotkey('ctrl', 'v')
                            except Exception: pass
                        elif target_lang:
                            # ── Voice AI Mode ────────────────────────
                            # The mic's silence detection (pause_threshold)
                            # has ALREADY captured the full sentence as one
                            # chunk — see mic_listener_loop. So we can
                            # translate + type immediately, no buffering.
                            try:
                                from ai_engine.translator import translate_sync
                                t0 = time.time()
                                translated = translate_sync(
                                    txt, lang, target_lang)
                                dt_ms = (time.time() - t0) * 1000
                                cur_token = getattr(self, "translation_token", 0)
                                if captured_token != cur_token:
                                    print(f"[TRANS] dropped stale "
                                          f"({captured_token} != {cur_token})")
                                else:
                                    print(f"[TRANS] {lang}->{target_lang} "
                                          f"in {dt_ms:.0f}ms: '{translated}'")
                                    self._type_ai_result(translated)
                            except Exception as e:
                                print(f"[TRANS] failed ({e}) — typing raw")
                                self._type_ai_result(txt)
                        else:
                            # Normal Typing — unchanged behaviour
                            processed_txt, punc_found = self.process_punctuation(txt, lang)
                        
                            # DIRECT handling for newline
                            if processed_txt == "\n":
                                keyboard.press_and_release('shift+enter')
                            else:
                                # Determine leading space
                                is_only_punc = (punc_found and len(processed_txt.strip()) <= 2 and all(c in '.।,?!;:--\n ' for c in processed_txt))
                                self.type_text(processed_txt, leading_space=not is_only_punc)
                
                except Exception as e:
                    print(f"[ERROR] Processing iteration failed: {e}")
                 
                finally:
                    # CRITICAL: Always release processing lock and task
                    self.is_processing = False
                    self.audio_queue.task_done()
                    
            except Exception as e:
                print(f"[CRITICAL] Outer processing loop error: {e}")
                time.sleep(1) # Prevent CPU spin if loop breaks

    # ===== AUTO-UPDATE SYSTEM METHODS =====
    


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
