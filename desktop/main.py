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
