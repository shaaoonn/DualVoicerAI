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

# DPI AWARENESS: Must be set BEFORE any tkinter import for crisp rendering on high-DPI displays
if sys.platform == 'win32':
    try:
        import ctypes
        # Per-monitor DPI awareness V2 (Windows 10+)
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()  # Fallback Win 7/8
        except (AttributeError, OSError):
            pass

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
APP_VERSION = "4.0.8"
UPDATE_REPO_URL = "https://raw.githubusercontent.com/shaaoonn/DualVoicer-Dist/main"

# Default settings (single source of truth)
DEFAULT_SETTINGS = {
    "max_opacity": 0.95,
    "idle_opacity": 0.4,
    "scale": 1.0,
    "reading_speed": "1.0",
    "auto_timeout": "15",
    "show_desktop_icon": True,
    "sound_enabled": True,
    "show_labels": True,
    "mic_sensitivity": "normal",
    "noise_threshold": 100,
    "mic_index": None,
    "window_x": None,
    "window_y": 0
}

def format_size(bytes_val):
    """Format bytes to human-readable size string"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_val < 1024:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f} TB"

# Network timeout for Google STT API (10s = handles large audio chunks without timeout)
socket.setdefaulttimeout(10)

# CRITICAL: Define resource_path BEFORE Firebase initialization
def resource_path(relative_path):
    """Resolve a bundled resource path.

    PyInstaller frozen builds: use sys._MEIPASS (the temp extraction dir).
    Dev runs (not frozen):     use the directory where this main.py lives,
                               so the lookup works no matter what CWD the
                               user launched from. Previously we used
                               os.path.abspath(".") which broke when the
                               app was launched from outside desktop/ (e.g.
                               from the project root) - the start/end SFX
                               WAVs then silently failed to load.
    """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def silent_restart(app_instance=None):
    """
    SILENT RESTART: Restarts the app invisibly.
    Developer Team Solution: Simple Popen for --windowed mode (no console flags needed).
    """
    try:
        # Get current position
        pos_x, pos_y = 100, 100
        
        if app_instance:
            try:
                pos_x = app_instance.winfo_x()
                pos_y = app_instance.winfo_y()
                
                # Save to settings file as backup
                app_instance.settings["window_x"] = pos_x
                app_instance.settings["window_y"] = pos_y
                if hasattr(app_instance, 'settings_file'):
                    with open(app_instance.settings_file, 'w') as f:
                        json.dump(app_instance.settings, f, indent=2)
            except Exception:
                pass
        
        # Remove lock file before restart
        lock_file = os.path.join(tempfile.gettempdir(), "dual_voicer.lock")
        try:
            if os.path.exists(lock_file):
                os.remove(lock_file)
        except OSError:
            pass

        if getattr(sys, 'frozen', False):
            # FROZEN (PyInstaller EXE)
            executable = sys.executable
            cmd_args = [executable, f"--pos={pos_x},{pos_y}"]
            
            # Windowed mode এর জন্য simple process start
            # কনসোল ফ্ল্যাগগুলোর আর দরকার নেই কারণ আমরা কনসোল চাই না
            subprocess.Popen(cmd_args, shell=False)
        else:
            # DEV MODE
            python = sys.executable
            os.execl(python, python, *sys.argv)
        
        # বর্তমান অ্যাপ বন্ধ করা
        if app_instance:
            try:
                app_instance.quit()
            except Exception:
                pass
        
        # Force kill current process
        os._exit(0)
        
    except Exception:
        # Windowed মোডে error দেখা যাবে না, শুধু continue করি
        pass


# Firebase removed - Uses API now

ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

# CustomTkinter widget scaling for crisp text on high-DPI displays.
# After enabling per-monitor DPI awareness above, the OS reports the *real*
# DPI to tk - but ctk renders widgets at logical (1.0x) size by default,
# so on a 1.5x or 2.0x display text looks tiny and aliased. Match ctk's
# scaling factor to the OS scale so the panel renders crisply.
if sys.platform == 'win32':
    try:
        import ctypes
        # GetScaleFactorForDevice returns the scale percent (e.g. 150 for 1.5x).
        # Falls back gracefully on older Windows.
        try:
            scale_pct = ctypes.windll.shcore.GetScaleFactorForDevice(0)
            dpi_scale = max(1.0, scale_pct / 100.0)
        except (AttributeError, OSError):
            # Fallback: GetDeviceCaps LOGPIXELSX (88) → DPI; baseline = 96
            hdc = ctypes.windll.user32.GetDC(0)
            dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)
            ctypes.windll.user32.ReleaseDC(0, hdc)
            dpi_scale = max(1.0, dpi / 96.0)
        ctk.set_widget_scaling(dpi_scale)
        ctk.set_window_scaling(dpi_scale)
        print(f"[DPI] Scale factor: {dpi_scale:.2f}x")
    except Exception as e:
        print(f"[DPI] Scaling setup failed: {e}")


class BackgroundUpdateManager:
    def __init__(self, app_version, repo_url, on_update_ready_callback):
        self.app_version = app_version
        self.repo_url = repo_url
        self.on_update_ready = on_update_ready_callback
        self.checker = UpdateChecker(app_version, repo_url)
        self.stop_event = threading.Event()
        
    def start(self):
        threading.Thread(target=self._run_loop, daemon=True).start()
        
    def _run_loop(self):
        print("[UPDATE] Background update manager started")
        # Initial check after 30 seconds (let app load first)
        time.sleep(30)
        
        while not self.stop_event.is_set():
            try:
                self._check_and_process()
            except Exception as e:
                print(f"[UPDATE] Background check failed: {e}")
            
            # Wait 1 hour before next check
            # Check stop_event periodically to allow clean exit
            for _ in range(3600): 
                if self.stop_event.is_set(): return
                time.sleep(1)
                
    def _check_and_process(self):
        print("[UPDATE] Checking for updates silently...")
        result = self.checker.check_for_updates()
        
        if result.get("available"):
            print(f"[UPDATE] New version found: {result.get('version')}")
            download_url = result.get("download_url")
            
            # Download silently
            downloader = UpdateDownloader(download_url)
            # Use temp folder for silent background download to avoid clutter
            # We'll override the default 'Downloads' behavior for this specific instance if possible
            # But UpdateDownloader hardcodes Downloads. Let's use it as is, it's fine.
            
            print("[UPDATE] Starting background download...")
            path = downloader.download_update()
            
            if path and os.path.exists(path):
                print(f"[UPDATE] Download complete: {path}")
                # Notify main thread to show popup
                if self.on_update_ready:
                    self.on_update_ready(result.get("version"), path, result.get("release_notes"))
        else:
            print("[UPDATE] No update found")

class VoiceTypingApp(ctk.CTk):
    def __init__(self):
        # SINGLE INSTANCE ENFORCEMENT - Prevent multiple copies (SMART VERSION)
        self.lock_file = os.path.join(tempfile.gettempdir(), "dual_voicer.lock")
        
        # Define base path for assets
        try:
            self.base_path = sys._MEIPASS
        except Exception:
            self.base_path = os.path.abspath(".")
            
        def is_process_running(pid):
            """Check if a process with given PID is actually running"""
            try:
                import psutil
                return psutil.pid_exists(pid)
            except ImportError:
                # Fallback: Try to check using os methods
                try:
                    os.kill(pid, 0)  # Signal 0 just checks if process exists
                    return True
                except OSError:
                    return False
            except (ValueError, OSError): return False

        # Cleanup stale lock file if process is dead
        if os.path.exists(self.lock_file):
            try:
                with open(self.lock_file, 'r') as f:
                    old_pid = int(f.read().strip())
                
                if not is_process_running(old_pid):
                    print(f"[INFO] Removing stale lock file (PID {old_pid} not running)")
                    try: os.remove(self.lock_file)
                    except OSError: pass
                else:
                    # App is running, bring to front instead of launching new
                    print(f"[INFO] App already running (PID {old_pid})")
                    try:
                        messagebox.showinfo("Dual Voicer", "App is already running! Check the tray icon or press Alt+Z.")
                    except tk.TclError: pass
                    sys.exit(0)
            except Exception as e:
                print(f"[WARNING] Lock file check failed: {e}")
                # Try to remove if corrupted
                try: os.remove(self.lock_file)
                except OSError: pass

        # Create new lock file
        try:
            with open(self.lock_file, 'w') as f:
                f.write(str(os.getpid()))
            print(f"[INFO] Lock file created with PID {os.getpid()}")
        except Exception as e:
            print(f"[ERROR] Could not create lock file: {e}")

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
        base_w, base_h = VoiceTypingApp._calc_dims({"mini":36,"tiny":48,"small":56,"medium":72,"large":84,"xlarge":96}.get(_p, 72))
        
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
        _pw, _ph = VoiceTypingApp._calc_dims({"mini":36,"tiny":48,"small":56,"medium":72,"large":84,"xlarge":96}.get(_preset, 72))
        self.geometry(f"{_pw}x{_ph}+{self.start_x}+{self.start_y}")

        self.drag_start = {"x": 0, "y": 0, "root_x": 0, "root_y": 0}
        self.is_dragging = False

        self.recognizer = sr.Recognizer()
        # Apply mic sensitivity setting
        self.apply_mic_sensitivity()
        # ---------------------------------------
        
        self.active_lang = None
        self.is_listening = False
        self.is_processing = False
        self.last_speech_time = 0
        self.shutdown_flag = threading.Event()
        self.mic_start_event = threading.Event()  # Instant wakeup for mic thread
        self.mic_ready_event = threading.Event()   # Signal: mic is ready to receive speech
        self.audio_queue = queue.Queue()
        
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

    def handle_update_ready(self, version, file_path, notes):
        """Called from background thread when update is ready"""
        def show_popup():
            try:
                # Play notification sound if possible
                try: winsound.MessageBeep(winsound.MB_ICONASTERISK)
                except Exception: pass
                
                msg = f"🎉 New Update Ready! (v{version})\n\nIt has been downloaded in the background.\nWould you like to install it now?"
                if messagebox.askyesno("Update Ready", msg):
                    UpdateInstaller.install_update(file_path)
            except Exception as e:
                print(f"[ERROR] Update popup failed: {e}")
                
        # Schedule on main thread
        self.after(0, show_popup)

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

    def get_stable_hwid(self):
        """
        PERSISTENT HWID: Once generated, the ID is saved and reused forever.
        This ensures the same device always has the same ID, even after reinstall.
        The HWID file is stored in AppData which survives uninstall.
        """
        import hashlib
        
        # STEP 1: Check for existing HWID file FIRST (most important)
        hwid_file = os.path.join(self.app_data_dir, ".hwid")
        try:
            if os.path.exists(hwid_file):
                with open(hwid_file, 'r') as f:
                    saved_hwid = f.read().strip()
                    if saved_hwid and len(saved_hwid) > 10:
                        print(f"[HWID] Using saved HWID: {saved_hwid[:8]}...")
                        return saved_hwid
        except Exception as e:
            print(f"[HWID] Error reading saved HWID: {e}")
        
        # STEP 2: Generate new HWID from hardware components
        hwid_parts = []
        
        # Component 1: Motherboard UUID
        try:
            cmd = 'powershell -Command "(Get-CimInstance -ClassName Win32_ComputerSystemProduct).UUID"'
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL, timeout=5).decode().strip()
            if output and output.lower() not in ["", "none", "to be filled by o.e.m."]:
                hwid_parts.append(f"MB:{output}")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            pass

        # Component 2: CPU ID
        try:
            cmd = 'powershell -Command "(Get-CimInstance -ClassName Win32_Processor).ProcessorId"'
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL, timeout=5).decode().strip()
            if output and output != "":
                hwid_parts.append(f"CPU:{output}")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            pass

        # Component 3: Disk Serial
        try:
            cmd = 'powershell -Command "(Get-CimInstance -ClassName Win32_DiskDrive | Select-Object -First 1).SerialNumber"'
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL, timeout=5).decode().strip()
            if output and output != "":
                hwid_parts.append(f"DISK:{output}")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            pass

        # Component 4: MAC Address
        try:
            mac = format(uuid.getnode(), '012x')
            hwid_parts.append(f"MAC:{mac}")
        except Exception:
            pass
        
        # Create HWID from components or generate random
        if len(hwid_parts) >= 2:
            combined = "|".join(sorted(hwid_parts))
            hwid_hash = hashlib.sha256(combined.encode()).hexdigest()[:32]
            new_hwid = f"DV-{hwid_hash.upper()}"
            print(f"[HWID] Generated from {len(hwid_parts)} hardware components")
        else:
            # Fallback: Random UUID
            new_hwid = f"DV-{str(uuid.uuid4()).replace('-', '').upper()[:32]}"
            print(f"[HWID] Generated random HWID (no hardware info available)")
        
        # STEP 3: SAVE the HWID for future use (critical!)
        try:
            os.makedirs(self.app_data_dir, exist_ok=True)
            with open(hwid_file, 'w') as f:
                f.write(new_hwid)
            print(f"[HWID] Saved new HWID: {new_hwid[:8]}...")
        except Exception as e:
            print(f"[HWID] Warning: Could not save HWID: {e}")
        
        return new_hwid
    
    def save_login_config(self, email, phone):
        """Save login credentials for auto-login"""
        try:
            config = {"email": email, "phone": phone, "last_login": datetime.datetime.now().isoformat()}
            with open(self.config_file, 'w') as f:
                json.dump(config, f)
            print(f"[INFO] Login config saved for {email}")
        except Exception as e:
            print(f"[WARNING] Failed to save config: {e}")
    
    def load_login_config(self):
        """Load saved login credentials"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                return config.get("email"), config.get("phone")
        except Exception as e:
            print(f"[WARNING] Failed to load config: {e}")
        return None, None
    
    def clear_login_config(self):
        """Clear saved login credentials (for logout)"""
        try:
            if os.path.exists(self.config_file):
                os.remove(self.config_file)
                print("[INFO] Login config cleared")
        except Exception as e:
            print(f"[WARNING] Failed to clear config: {e}")
    
    def auto_login_if_saved(self):
        """Attempt auto-login using saved credentials"""
        saved_email, saved_phone = self.load_login_config()
        if saved_email and saved_phone:
            print(f"[INFO] Attempting auto-login for {saved_email}")
            # Mark that auto-login is being attempted
            self._auto_login_attempted = True
            
            # Store phone for validate_device_access to use
            self._auto_login_phone = saved_phone 
            
            threading.Thread(
                target=self.validate_device_access,
                args=(saved_email, None, None, True),
                daemon=True
            ).start()
        else:
            # No saved credentials, clear flag
            self._auto_login_attempted = False
    
    def check_and_add_to_startup(self):
        try:
            exe_path = sys.executable
            # Only enact if running as compiled EXE
            if getattr(sys, 'frozen', False):
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_ALL_ACCESS)
                try:
                    winreg.SetValueEx(key, "DualVoicer", 0, winreg.REG_SZ, exe_path)
                except OSError:
                    pass
                finally:
                    winreg.CloseKey(key)
        except OSError: pass

    def _cache_microphones(self):
        """Cache microphone list in background for fast settings panel loading"""
        try:
            import pyaudio
            p = pyaudio.PyAudio()
            mic_list = ["Default Microphone"]
            mic_map = {"Default Microphone": None}
            
            counter = 1
            for i in range(p.get_device_count()):
                dev = p.get_device_info_by_index(i)
                if dev.get('maxInputChannels') <= 0: continue
                
                name = dev.get('name')
                try:
                    if isinstance(name, bytes): name = name.decode('utf-8', 'ignore')
                except UnicodeDecodeError: pass
                
                lower_name = name.lower()
                if any(x in lower_name for x in ["mapper", "primary sound", "stereo mix", "speaker", "output", "hands-free"]):
                    continue
                if dev.get('hostApi') != 0: continue
                
                label = f"{counter}. {name}"
                mic_list.append(label)
                mic_map[label] = i
                counter += 1
            
            p.terminate()
            self._cached_mic_list = mic_list
            self._cached_mic_map = mic_map
            print(f"[INFO] Cached {len(mic_list)} microphones")
        except Exception as e:
            print(f"[ERROR] Mic cache: {e}")

    def setup_hotkeys(self):
        from config import AI_HOTKEY, SMART_PASTE_HOTKEY, DEV_MODE
        try:
            # Clean slate - remove ALL previous hooks
            try: keyboard.unhook_all()
            except Exception: pass

            # ONLY register hotkeys - no suppress, no trigger_on_release
            keyboard.add_hotkey('alt+z', lambda: self.after(0, lambda: self.switch_language('bn-BD')))
            keyboard.add_hotkey('alt+x', lambda: self.after(0, lambda: self.switch_language('en-US')))
            keyboard.add_hotkey('alt+c', lambda: self.after(0, self.handle_reader_click))
            keyboard.add_hotkey(AI_HOTKEY, lambda: self.after(0, self.ai_trigger_flow))
            keyboard.add_hotkey(SMART_PASTE_HOTKEY, lambda: self.after(0, self.smart_paste_flow))
            keyboard.add_hotkey('ctrl+shift+d', lambda: self.after(0, self.toggle_pen_mode))
            print("[HOTKEYS] Registered: alt+z/x/c, " + AI_HOTKEY + ", " + SMART_PASTE_HOTKEY + ", ctrl+shift+d (pen)")
        except Exception as e:
            print(f"[HOTKEY ERROR] {e}")

    def _set_no_activate(self):
        """Prevent this window from stealing focus when clicked.
        Uses Windows WS_EX_NOACTIVATE extended style."""
        try:
            import ctypes
            from ctypes import wintypes
            GWL_EXSTYLE = -20
            WS_EX_NOACTIVATE = 0x08000000
            WS_EX_APPWINDOW  = 0x00040000
            WS_EX_TOOLWINDOW = 0x00000080

            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style = style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
            style = style & ~WS_EX_APPWINDOW
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
            print("[FOCUS] WS_EX_NOACTIVATE set - widget won't steal focus")
        except Exception as e:
            print(f"[FOCUS] Failed to set NOACTIVATE: {e}")

    # Toolbar gradient color (approx middle of gradient - used for button corners)
    TOOLBAR_BG = "#302D5E"

    @staticmethod
    def _calc_dims(btn_s):
        """Calculate window (w, h) from button size - single source of truth."""
        sc = btn_s / 72.0
        padx = max(6, int(8 * sc))
        gap = max(3, int(4 * sc))
        # XXS (mini=36) uses a smaller width budget for the tool column so the
        # widget stays narrower AND the tools visibly shrink vs XS (was 16 →
        # too close to XS's 20). 14 gives a clear 30% width reduction.
        tool_floor = 14 if btn_s < 48 else 20
        tool_w = max(tool_floor, int(28 * sc)) + 4
        w = 2 * padx + 4 * btn_s + 4 * gap + tool_w
        h = btn_s + max(12, int(14 * sc))
        return w, h

    @staticmethod
    def _calc_tools_panel_w(btn_s):
        """Pen tools panel width — initial estimate, refined by actual
        measurement after the toolbar renders (see _refit_panel_to_toolbar).

        The estimate floor (320) is chosen so XS/S widgets don't get a hard
        440px container around a 290–340px toolbar, which produced visible
        right-side empty space. Once the toolbar mounts we measure
        winfo_reqwidth() and tighten the container to actual content."""
        scale = btn_s / 72.0
        # Linear estimate matching observed embedded-toolbar content widths:
        # scale 0.667 → ~310,  0.778 → ~360,  1.0 → ~445,  1.167 → ~520,
        # 1.333 → ~590. Floor 320 keeps the smallest preset just barely
        # roomier than its measured content (~290px) so the measurement
        # step never has to expand, only shrink.
        return max(320, int(445 * scale))

    def _refit_panel_to_toolbar(self):
        """Tighten the panel container to the toolbar's actual rendered width.

        The toolbar is ``pack(fill="both", expand=True)`` inside
        ``_panel_container`` which has ``pack_propagate(False)`` so the
        container's set width wins. After mount, the toolbar's natural
        ``winfo_reqwidth()`` reflects exactly how wide the buttons + paddings
        are. Setting the container to that + tiny margin removes any
        right-side gap at small widget sizes (XS/S) where the linear
        estimate slightly overshoots."""
        try:
            tb = getattr(self, '_pen_toolbar', None)
            if not tb or not getattr(self, '_pen_tools_expanded', False):
                return
            root = tb.get_root_widget()
            root.update_idletasks()
            req = root.winfo_reqwidth()
            if req <= 1:
                return
            # +4px margin so border/highlightthickness doesn't clip
            target = req + 4
            preset = self.settings.get("size_preset", "medium")
            btn_s = self.BTN_SIZES.get(preset, 72)
            base_w, h = self._calc_dims(btn_s)
            self._panel_container.configure(width=target, height=h)
            try:
                wx, wy = self.winfo_x(), self.winfo_y()
            except Exception:
                wx, wy = 0, 0
            self.geometry(f"{base_w + target}x{h}+{wx}+{wy}")
        except Exception:
            pass

    def init_ui(self):
        import tkinter as tk
        from ui_components.spectrum_button import SpectrumButton
        from config import SPECTRUM_BTN_SIZE, SPECTRUM_COLORS

        # Main container - holds canvas (left) + pen panel (right)
        self._main_container = tk.Frame(self, bg="#22214B")
        self._main_container.pack(fill="both", expand=True)

        # Panel container for embedded pen tools (LEFT side, initially hidden)
        self._panel_container = tk.Frame(
            self._main_container, bg="#302D5E",
            highlightthickness=0)
        # NOT packed yet - packed only when pen panel opens

        # Canvas for gradient background (RIGHT side, always visible)
        self.frame = tk.Canvas(self._main_container, bg="#22214B",
                               highlightthickness=0)
        self.frame.pack(side="left", fill="y")

        self.frame.bind("<ButtonPress-1>", self.on_press)
        self.frame.bind("<B1-Motion>", self.on_drag)
        self.frame.bind("<ButtonRelease-1>", self._on_bg_release)

        btn_size = SPECTRUM_BTN_SIZE

        # Spectrum buttons (placed on canvas later by _apply_window_size)
        lang1 = self.settings.get("btn1_lang", "bn-BD")
        self.btn_bn = SpectrumButton(self.frame, size=btn_size, label="BN",
            colors=SPECTRUM_COLORS, toolbar_bg=self.TOOLBAR_BG,
            command=lambda: self.switch_language(self.settings.get("btn1_lang", "bn-BD")))
        self.btn_bn.set_display_label(lang1.split("-")[0].upper())

        lang2 = self.settings.get("btn2_lang", "en-US")
        self.btn_en = SpectrumButton(self.frame, size=btn_size, label="EN",
            colors=SPECTRUM_COLORS, toolbar_bg=self.TOOLBAR_BG,
            command=lambda: self.switch_language(self.settings.get("btn2_lang", "en-US")))
        self.btn_en.set_display_label(lang2.split("-")[0].upper())

        self.btn_read = SpectrumButton(self.frame, size=btn_size, label="SND",
            colors=SPECTRUM_COLORS, toolbar_bg=self.TOOLBAR_BG,
            command=self.handle_reader_click)

        self.btn_ai = SpectrumButton(self.frame, size=btn_size, label="AI",
            colors=SPECTRUM_COLORS, toolbar_bg=self.TOOLBAR_BG,
            command=self.ai_trigger_flow if hasattr(self, 'ai_trigger_flow') else None)

        # Apply label visibility from settings
        if not self.settings.get("show_labels", True):
            for btn in [self.btn_bn, self.btn_en, self.btn_read, self.btn_ai]:
                btn.set_labels_visible(False)

        # Tool buttons frame
        self.tool_frame = tk.Frame(self.frame, bg=self.TOOLBAR_BG)

        # 1x1 transparent pixel — paired with compound="center" forces
        # tk.Button width/height to be interpreted as PIXELS (not text units).
        # This is what lets the 3 tool buttons actually shrink at XXS (CTk's
        # internal minimum of ~20px would otherwise overflow the canvas).
        self._tool_pixel = tk.PhotoImage(width=1, height=1)

        def _mk_tool(glyph, cmd):
            b = tk.Button(
                self.tool_frame, text=glyph, image=self._tool_pixel,
                compound="center", width=30, height=26,
                font=("Segoe UI Emoji", 13),
                bg=self.TOOLBAR_BG, fg="white", relief="flat", bd=0,
                # padx/pady default to 1 in tk.Button — internal padding
                # would add 2px to actual rendered size, breaking the
                # pixel-precise place() math at XXS. Force to 0.
                padx=0, pady=0,
                highlightthickness=0, activebackground="#4A4A6A",
                activeforeground="white", cursor="hand2", command=cmd)
            b.pack(pady=0)
            return b

        self.btn_pen = _mk_tool("\U0001f58a\ufe0f", self.toggle_pen_mode)
        self.btn_screenshot = _mk_tool("\U0001f4f7", self.take_screenshot)
        self.btn_settings = _mk_tool("\u2699\ufe0f", self.open_settings_panel)

        self._apply_window_size()

    def _render_toolbar_bg(self, w, h):
        """Render rectangular gradient 3D toolbar background - no rounding."""
        from PIL import ImageTk

        img = Image.new("RGB", (w, h))
        d = ImageDraw.Draw(img)

        for y in range(h):
            t = y / max(1, h - 1)
            # Blue-purple gradient (3D: top light, bottom dark)
            r = int(62 - 28 * t)
            g = int(58 - 25 * t)
            b = int(115 - 42 * t)

            # Glass highlight at top 18%
            if t < 0.18:
                glow = (1 - t / 0.18) ** 1.8
                r = min(255, r + int(50 * glow))
                g = min(255, g + int(48 * glow))
                b = min(255, b + int(55 * glow))

            # Bottom shadow (last 10%)
            if t > 0.90:
                shadow = (t - 0.90) / 0.10
                r = max(0, int(r - 12 * shadow))
                g = max(0, int(g - 10 * shadow))
                b = max(0, int(b - 15 * shadow))

            d.line([(0, y), (w - 1, y)], fill=(r, g, b))

        # Top highlight border
        d.line([(0, 0), (w - 1, 0)], fill=(90, 85, 150))
        # Bottom shadow border
        d.line([(0, h - 1), (w - 1, h - 1)], fill=(25, 23, 55))

        self._toolbar_bg_photo = ImageTk.PhotoImage(img)
        self.frame.delete("bg")
        self.frame.create_image(0, 0, anchor="nw", image=self._toolbar_bg_photo,
                                tags="bg")
        self.frame.tag_lower("bg")

    def load_png_with_label(self, png_filename, label="", width=60, height=35):
        """Simple PNG loader with optional label overlay"""
        try:
            png_path = resource_path(png_filename)
            
            if not os.path.exists(png_path):
                # Try finding in current directory as fallback
                cwd_path = os.path.join(os.getcwd(), png_filename)
                if os.path.exists(cwd_path):
                    png_path = cwd_path
                else:
                    return None
            
            # Load and resize PNG
            img = Image.open(png_path).convert('RGBA')
            img = img.resize((width*2, height*2), Image.Resampling.LANCZOS)
            
            # Add label if provided
            if label:
                draw = ImageDraw.Draw(img)
                try:
                    font = ImageFont.truetype("arial.ttf", int(height * 0.36))
                except OSError:
                    font = ImageFont.load_default()
                
                bbox = draw.textbbox((0, 0), label, font=font)
                text_w = bbox[2] - bbox[0]
                text_h = bbox[3] - bbox[1]
                
                label_x = width * 2 - text_w - int(width * 0.15)
                label_y = height * 2 - text_h - int(height * 0.15)
                
                # Shadow
                for offset in [(-2,-2), (-2,2), (2,-2), (2,2)]:
                    draw.text((label_x + offset[0], label_y + offset[1]), label, 
                             font=font, fill=(0, 0, 0, 180))
                draw.text((label_x, label_y), label, font=font, fill=(255, 255, 255, 255))
            
            return img
        except Exception as e:
            return None

    BTN_SIZES = {"mini": 36, "tiny": 48, "small": 56, "medium": 72, "large": 84, "xlarge": 96}

    def _apply_window_size(self):
        """Apply size from preset - dynamic width, tight layout."""
        preset = self.settings.get("size_preset", "medium")
        btn_s = self.BTN_SIZES.get(preset, 72)
        base_w, h = self._calc_dims(btn_s)

        # Canvas always fixed to base width
        self.frame.configure(width=base_w, height=h)

        # Total window width = base + panel (if expanded)
        total_w = base_w
        if getattr(self, '_pen_tools_expanded', False):
            panel_w = self._calc_tools_panel_w(btn_s)
            total_w += panel_w
            self._panel_container.configure(width=panel_w, height=h)

        # Preserve position
        try:
            wx, wy = self.winfo_x(), self.winfo_y()
        except Exception:
            wx, wy = 0, 0
        self.geometry(f"{total_w}x{h}+{wx}+{wy}")

        scale = btn_s / 72.0
        padx = max(6, int(8 * scale))
        gap = max(3, int(4 * scale))
        # Match _calc_dims: XXS gets a tighter floor (14) for visible size
        # difference vs XS (20). tiny+ unchanged.
        tool_floor = 14 if btn_s < 48 else 20
        tool_sz = max(tool_floor, int(28 * scale))
        tool_w = tool_sz + 4

        # Scale spectrum buttons
        for btn in [self.btn_bn, self.btn_en, self.btn_read, self.btn_ai]:
            if hasattr(btn, 'resize'):
                btn.resize(btn_s)

        # Scale the embedded pen toolbar in lock-step with the widget
        # (only matters when the panel is currently open)
        if getattr(self, '_pen_toolbar', None):
            try:
                self._pen_toolbar.set_scale(scale)
            except Exception:
                pass
            # After the toolbar reflows at the new scale, tighten the panel
            # container to its actual measured width — eliminates any gap at
            # XS/S sizes where the linear estimate slightly overshoots.
            self.after(60, self._refit_panel_to_toolbar)

        # Scale tool buttons. tk.Button + 1x1 image trick makes width/height
        # exact pixels, so the 3-button stack can be precisely distributed.
        # 0.80 ratio (was 0.85) makes them slightly more compact per request.
        tool_font = max(9, int(13 * scale))
        tool_h = int(tool_sz * 0.80)
        # XXS: explicit overrides — tool_h=12 gives perfect 3-3-3-3 gap
        # distribution in 48px canvas, and 8pt font fits inside the 12px
        # button height (9pt overflows ~14px line-height → causes the
        # adjacent-button visual overlap the user reported).
        if btn_s < 48:
            tool_h = 12
            tool_font = 8
        tool_buttons = [self.btn_pen, self.btn_screenshot, self.btn_settings]
        for btn in tool_buttons:
            try:
                btn.configure(width=tool_sz, height=tool_h,
                              font=("Segoe UI Emoji", tool_font))
            except tk.TclError:
                pass

        # Distribute the 3 tool buttons with EQUAL 4-way gaps inside the
        # canvas-height tool_frame. With place() we get pixel-precise
        # alignment (all 3 share one x), and gaps are computed so top,
        # between-1, between-2, and bottom are as equal as integer pixels
        # allow. Any 1-3 leftover pixels go symmetrically to outer gaps.
        try:
            self.tool_frame.config(width=tool_w, height=h)
            self.tool_frame.pack_propagate(False)
            free = h - 3 * tool_h
            if free < 0:
                free = 0
            base = free // 4
            extra = free - 4 * base
            gaps = [base, base, base, base]
            if extra >= 1: gaps[0] += 1   # top
            if extra >= 2: gaps[3] += 1   # bottom (symmetric)
            if extra >= 3: gaps[1] += 1   # one inner gap
            btn_x = max(0, (tool_w - tool_sz) // 2)
            # Per-glyph optical correction: 📷 has its visual mass concentrated
            # at the bottom (the lens), so it appears slightly low even when
            # the bounding box is mathematically centered. Nudge up 1-2 px to
            # match the user's perception of a centered icon.
            cam_nudge = -1 if tool_h <= 16 else -2
            y = gaps[0]
            for i, btn in enumerate(tool_buttons):
                try:
                    btn.pack_forget()
                except tk.TclError:
                    pass
                # i==1 is the screenshot (camera) button
                y_off = cam_nudge if i == 1 else 0
                btn.place(x=btn_x, y=y + y_off, width=tool_sz, height=tool_h)
                y += tool_h + gaps[i + 1]
        except tk.TclError:
            pass

        # Remove old widget placements
        self.frame.delete("widgets")

        # Render gradient background (only canvas area, not panel)
        self._render_toolbar_bg(base_w, h)

        # Place buttons on canvas - tight layout
        cy = h // 2
        x = padx + btn_s // 2

        btns = [self.btn_bn, self.btn_en, self.btn_read, self.btn_ai]
        for btn in btns:
            self.frame.create_window(x, cy, window=btn, tags="widgets")
            x += btn_s + gap

        # Tool frame - tight: right after last button's edge
        tool_cx = x - btn_s // 2 + tool_w // 2
        self.frame.create_window(tool_cx, cy,
                                 window=self.tool_frame, tags="widgets")

    def update_button_labels(self):
        """Update BN/EN button labels from current settings."""
        if hasattr(self, 'btn_bn'):
            lang1 = self.settings.get("btn1_lang", "bn-BD")
            self.btn_bn.set_display_label(lang1.split("-")[0].upper())
        if hasattr(self, 'btn_en'):
            lang2 = self.settings.get("btn2_lang", "en-US")
            self.btn_en.set_display_label(lang2.split("-")[0].upper())

    def apply_size_scaling(self):
        """Load icon path only."""
        self.icon_path = None
        new_logo = os.path.join(self.base_path, "DualVoicerLogo.ico")
        if os.path.exists(new_logo):
            self.icon_path = new_logo
        self.logo_img = None
        if self.icon_path:
            try:
                from PIL import Image
                img = Image.open(self.icon_path)
                self.logo_img = ctk.CTkImage(light_image=img, dark_image=img, size=(45, 45))
            except (OSError, tk.TclError): pass

    def apply_size_preset(self, preset=None):
        """Called from settings panel when size changes."""
        if preset:
            self.settings["size_preset"] = preset
        self._apply_window_size()
        self.save_settings()

    def update_size(self, value):
        pass

    def open_editor_window(self):
        """Open the built-in editor window.
        Closes pen overlay first (its fullscreen input_win blocks editor).
        Restores previous session if available."""
        # Always close embedded pen panel first (even if editor already exists)
        self._close_pen_mode_immediate()

        if hasattr(self, '_editor_win') and self._editor_win is not None:
            try:
                if self._editor_win.winfo_exists():
                    self._editor_win.deiconify()
                    self._editor_win.lift()
                    # Show toolbar if hidden
                    if hasattr(self._editor_win, '_show_toolbar'):
                        self._editor_win._show_toolbar()
                    # Restart auto-save if stopped
                    if not self._editor_win._autosave_job:
                        self._editor_win._schedule_autosave()
                    # Hide main widget - editor has all controls
                    self.withdraw()
                    return
            except tk.TclError:
                pass

        from ui.editor_window import EditorWindow, SESSION_FILE
        # Pass None as parent so editor is independent Toplevel
        # (otherwise withdraw() on main widget hides editor too)
        self._editor_win = EditorWindow(None, self)
        # Restore previous session if exists
        if os.path.exists(SESSION_FILE):
            try:
                self._editor_win._load_dvai(SESSION_FILE)
            except Exception as e:
                print(f"[EDITOR] Session restore failed: {e}")
        # Hide main widget - editor toolbar has all controls
        self.withdraw()

    def toggle_pen_mode(self):
        """Toggle pen mode: off → draw → view (click-through) → draw → ..."""
        # If editor is open AND visible, bring it to focus instead of pen overlay
        if hasattr(self, '_editor_win') and self._editor_win is not None:
            try:
                if (self._editor_win.winfo_exists()
                        and self._editor_win.winfo_viewable()):
                    self._editor_win.lift()
                    if hasattr(self._editor_win, '_show_toolbar'):
                        self._editor_win._show_toolbar()
                    return
            except tk.TclError:
                pass

        if not hasattr(self, '_pen_overlay') or self._pen_overlay is None:
            # No overlay → create and enter draw mode
            self._open_pen_mode()
        elif self._pen_overlay.is_click_through:
            # View mode → switch to draw mode
            self._pen_set_draw_mode()
        else:
            # Draw mode → switch to view mode (strokes stay)
            self._pen_set_view_mode()

    def _open_pen_mode(self):
        """Open pen overlay + embedded toolbar (slide-out), enter draw mode."""
        try:
            from ui_components.pen_overlay import PenOverlay
            from ui_components.pen_toolbar import PenToolbar

            self._pen_overlay = PenOverlay(self, on_close_callback=self._close_pen_mode)
            preset = self.settings.get("size_preset", "medium")
            btn_s_now = self.BTN_SIZES.get(preset, 72)
            self._pen_toolbar = PenToolbar(
                self._panel_container,  # parent = panel container frame
                self._pen_overlay,
                self,
                mode="embedded",
                on_retract=self._retract_pen_tools,
                scale=btn_s_now / 72.0,
            )

            # Main toolbar: pen icon → mouse icon
            self.btn_pen.configure(text="\U0001f5b1\ufe0f")
            self._animate_tools_open()
            self.after(200, self._pen_ensure_topmost)
            print("[PEN] Pen mode opened (draw)")
        except Exception as e:
            print(f"[PEN] Failed to open: {e}")
            import traceback; traceback.print_exc()
            self._pen_overlay = None
            self._pen_toolbar = None

    def _pen_set_draw_mode(self):
        """Switch to draw mode (pen captures events)."""
        if self._pen_overlay:
            self._pen_overlay.set_click_through(False)
            self.btn_pen.configure(text="\U0001f5b1\ufe0f")
            if self._pen_toolbar:
                self._pen_toolbar.sync_draw_mode()

    def _pen_set_view_mode(self):
        """Switch to view mode (click-through, strokes stay)."""
        if self._pen_overlay:
            self._pen_overlay.set_click_through(True)
            self.btn_pen.configure(text="\U0001f58a\ufe0f")
            if self._pen_toolbar:
                self._pen_toolbar.sync_view_mode()

    # ── Pen tools slide-out animation ───────────────────

    def _animate_tools_open(self):
        """Slide tools panel out from RIGHT edge - left edge stays fixed."""
        preset = self.settings.get("size_preset", "medium")
        btn_s = self.BTN_SIZES.get(preset, 72)
        base_w, h = self._calc_dims(btn_s)
        panel_w = self._calc_tools_panel_w(btn_s)
        target_w = base_w + panel_w

        # Position stays fixed - panel grows rightward
        wx, wy = self.winfo_x(), self.winfo_y()

        # Off-screen: shift left only if needed
        screen_w = self.winfo_screenwidth()
        if wx + target_w > screen_w:
            wx = max(0, screen_w - target_w)

        # Place pen toolbar frame (already child of _panel_container)
        tools_frame = self._pen_toolbar.get_root_widget()
        tools_frame.pack(fill="both", expand=True)
        self._panel_container.configure(width=1, height=h)
        self._panel_container.pack_propagate(False)
        self._panel_container.pack(side="right", fill="y")

        self._pen_tools_expanded = True
        steps = 8
        step_pw = panel_w / steps

        def _step(i, pw_so_far):
            if i >= steps:
                self._panel_container.configure(width=panel_w)
                self.geometry(f"{target_w}x{h}+{wx}+{wy}")
                # Open animation done — now measure actual toolbar width and
                # tighten the container so there's no gap on the right.
                self.after(40, self._refit_panel_to_toolbar)
                return
            pw_so_far += step_pw
            pw_int = int(pw_so_far)
            self._panel_container.configure(width=pw_int)
            self.geometry(f"{base_w + pw_int}x{h}+{wx}+{wy}")
            self._pen_anim_job = self.after(16, lambda: _step(i + 1, pw_so_far))

        _step(0, 0.0)

    def _animate_tools_close(self, on_done=None):
        """Retract tools panel from RIGHT - left edge stays fixed."""
        preset = self.settings.get("size_preset", "medium")
        btn_s = self.BTN_SIZES.get(preset, 72)
        base_w, h = self._calc_dims(btn_s)
        panel_w = self._calc_tools_panel_w(btn_s)

        wx, wy = self.winfo_x(), self.winfo_y()  # Position stays fixed
        steps = 8
        step_pw = panel_w / steps

        def _step(i, pw_remaining):
            if i >= steps:
                self._panel_container.pack_forget()
                self._pen_tools_expanded = False
                self.geometry(f"{base_w}x{h}+{wx}+{wy}")
                if on_done:
                    on_done()
                return
            pw_remaining -= step_pw
            pw_int = max(1, int(pw_remaining))
            self._panel_container.configure(width=pw_int)
            self.geometry(f"{base_w + pw_int}x{h}+{wx}+{wy}")
            self._pen_anim_job = self.after(16, lambda: _step(i + 1, pw_remaining))

        _step(0, float(panel_w))

    def _retract_pen_tools(self):
        """Called when embedded toolbar Close is clicked - retract + cleanup."""
        def _after_retract():
            if hasattr(self, '_pen_toolbar') and self._pen_toolbar:
                try:
                    self._pen_toolbar.destroy()
                except Exception:
                    pass
                self._pen_toolbar = None
            if hasattr(self, '_pen_overlay') and self._pen_overlay:
                try:
                    self._pen_overlay.destroy()
                except Exception:
                    pass
                self._pen_overlay = None
            self.btn_pen.configure(text="\U0001f58a\ufe0f")
            print("[PEN] Pen mode closed (retracted)")

        self._animate_tools_close(on_done=_after_retract)

    def _close_pen_mode(self):
        """Close pen overlay + toolbar with retract animation."""
        try:
            if getattr(self, '_pen_tools_expanded', False):
                self._retract_pen_tools()
            else:
                # Fallback (standalone mode or already retracted)
                if hasattr(self, '_pen_toolbar') and self._pen_toolbar:
                    try:
                        self._pen_toolbar.destroy()
                    except Exception:
                        pass
                    self._pen_toolbar = None
                if hasattr(self, '_pen_overlay') and self._pen_overlay:
                    try:
                        self._pen_overlay.destroy()
                    except Exception:
                        pass
                    self._pen_overlay = None
                self.btn_pen.configure(text="\U0001f58a\ufe0f")
                print("[PEN] Pen mode closed")
        except Exception as e:
            print(f"[PEN] Error closing: {e}")

    def _close_pen_mode_immediate(self):
        """Close pen overlay + toolbar immediately (no animation).
        Used when editor needs to open right away."""
        try:
            # Cancel any running animation
            if self._pen_anim_job:
                try:
                    self.after_cancel(self._pen_anim_job)
                except Exception:
                    pass
                self._pen_anim_job = None

            # Destroy toolbar
            if hasattr(self, '_pen_toolbar') and self._pen_toolbar:
                try:
                    self._pen_toolbar.destroy()
                except Exception:
                    pass
                self._pen_toolbar = None

            # Destroy overlay
            if hasattr(self, '_pen_overlay') and self._pen_overlay:
                try:
                    self._pen_overlay.destroy()
                except Exception:
                    pass
                self._pen_overlay = None

            # Restore panel + window size immediately
            if getattr(self, '_pen_tools_expanded', False):
                self._panel_container.pack_forget()
                self._pen_tools_expanded = False
                preset = self.settings.get("size_preset", "medium")
                btn_s = self.BTN_SIZES.get(preset, 72)
                base_w, h = self._calc_dims(btn_s)
                wx, wy = self.winfo_x(), self.winfo_y()  # Position stays fixed
                self.geometry(f"{base_w}x{h}+{wx}+{wy}")

            self.btn_pen.configure(text="\U0001f58a\ufe0f")
            self.update_idletasks()  # Force tkinter to process all pending destroys
            print("[PEN] Pen mode closed (immediate)")
        except Exception as e:
            print(f"[PEN] Error closing immediate: {e}")

    def _pen_ensure_topmost(self):
        """Ensure correct z-order: input < main widget < render.
        Toolbar is always embedded (no separate Toplevel)."""
        try:
            if hasattr(self, '_pen_overlay') and self._pen_overlay and self._pen_overlay.winfo_exists():
                self._pen_overlay.lift_input()
                self.lift()
                self._pen_overlay.lift_render()
        except tk.TclError:
            pass

    def take_screenshot(self):
        """Trigger Windows Snipping Tool, save clipboard image for AI analysis.
        In pen mode: temporarily make overlay click-through so snip tool works,
        and keep render window visible so drawings appear in screenshot."""
        if self.is_reading:
            self._pause_reader()

        # In pen mode, make input window click-through so snipping tool works
        pen_was_drawing = False
        if (hasattr(self, '_pen_overlay') and self._pen_overlay and
                self._pen_overlay.winfo_exists()):
            if not self._pen_overlay.is_click_through:
                pen_was_drawing = True
                self._pen_overlay.set_click_through(True)

        pyautogui.hotkey('win', 'shift', 's')

        self._screenshot_pending = True

        def _capture_after_snip():
            """Poll clipboard for image (up to 15s), then save for AI."""
            from PIL import ImageGrab
            import io, base64

            captured = False
            # Poll clipboard every 0.5s for up to 15 seconds
            for _ in range(30):
                time.sleep(0.5)
                try:
                    img = ImageGrab.grabclipboard()
                    if img:
                        buf = io.BytesIO()
                        img.save(buf, format='PNG')
                        buf.seek(0)
                        b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
                        self._last_screenshot_b64 = f"data:image/png;base64,{b64}"
                        self._last_screenshot_time = time.time()
                        print("[SCREENSHOT] Captured for AI analysis")
                        captured = True

                        # Show AI button glow (10s countdown)
                        self.after(0, self._start_screenshot_glow)

                        # Save to folder if configured
                        save_dir = self.settings.get("screenshot_save_dir", "").strip()
                        if save_dir and os.path.isdir(save_dir):
                            fname = datetime.datetime.now().strftime("screenshot_%Y%m%d_%H%M%S.png")
                            path = os.path.join(save_dir, fname)
                            img.save(path)
                            print(f"[SCREENSHOT] Saved: {path}")
                        break
                except (OSError, Exception):
                    pass
            if not captured:
                print("[SCREENSHOT] No image captured after 15s")

            # Restore pen draw mode if it was active
            if pen_was_drawing:
                self.after(0, lambda: self._pen_restore_after_screenshot())

            self._screenshot_pending = False

        threading.Thread(target=_capture_after_snip, daemon=True).start()

    def _pen_restore_after_screenshot(self):
        """Restore pen draw mode after screenshot capture."""
        if (hasattr(self, '_pen_overlay') and self._pen_overlay and
                self._pen_overlay.winfo_exists()):
            self._pen_overlay.set_click_through(False)
            if hasattr(self, '_pen_toolbar') and self._pen_toolbar:
                self._pen_toolbar.sync_draw_mode()

    def _start_screenshot_glow(self):
        """Bright glow on AI button for 10 seconds to indicate screenshot ready."""
        self._screenshot_glow_active = True
        self.btn_ai.set_glow(True)
        # Auto-expire after 10 seconds
        self.after(10000, self._stop_screenshot_glow)

    def _stop_screenshot_glow(self):
        """Stop AI button glow and expire screenshot."""
        self._screenshot_glow_active = False
        self.btn_ai.set_glow(False)
        # Expire screenshot after 10s
        if (hasattr(self, '_last_screenshot_time') and
                time.time() - self._last_screenshot_time >= 10):
            self._last_screenshot_b64 = None

    def _pause_reader(self):
        """Pause TTS playback immediately (synchronous)."""
        if self.is_reading and not self.is_paused:
            try:
                pygame.mixer.music.pause()
            except pygame.error: pass
            self.is_paused = True
            self.after(0, lambda: self.btn_read.set_state("idle"))
            self.after(0, lambda: self.btn_read.set_icon_mode("pause"))

    def _resume_reader(self):
        """Resume paused TTS."""
        if self.is_reading and self.is_paused:
            try:
                pygame.mixer.music.unpause()
            except pygame.error: pass
            self.is_paused = False
            self.after(0, lambda: self.btn_read.set_state("listening"))
            self.after(0, lambda: self.btn_read.set_icon_mode("play"))

    def on_hover_enter(self, event):
        self.attributes('-alpha', self.settings["max_opacity"])

    def on_hover_leave(self, event):
        sw = self.settings_window or getattr(self, '_settings_win', None)
        if sw and sw.winfo_exists():
            self.attributes('-alpha', self.settings["max_opacity"])
        else:
            self.attributes('-alpha', self.settings["idle_opacity"])

    def on_button_hover_enter(self, event, button, original_size):
        """Animate button scale up on hover for micro-interaction UX"""
        try:
            # Scale up by 5% (reduced from 10% to prevent clipping)
            new_w = int(original_size[0] * 1.05)
            new_h = int(original_size[1] * 1.05)
            button.configure(width=new_w, height=new_h)
            
            # Update image size if exists
            if hasattr(button, 'cget') and button.cget('image'):
                img = button.cget('image')
                if hasattr(img, 'configure'):
                    img.configure(size=(new_w, new_h))
            
            # Special handling for sound button - also scale settings icon
            if button == getattr(self, 'btn_read', None):
                if hasattr(self, 'btn_settings'):
                    settings_w = int(20 * 1.05)
                    self.btn_settings.configure(width=settings_w, height=settings_w)
        except tk.TclError: pass

    def on_button_hover_leave(self, event, button, original_size):
        """Restore button to original size on hover leave"""
        try:
            button.configure(width=original_size[0], height=original_size[1])
            
            # Restore image size
            if hasattr(button, 'cget') and button.cget('image'):
                img = button.cget('image')
                if hasattr(img, 'configure'):
                    img.configure(size=original_size)
            
            # Special handling for sound button - restore settings icon
            if button == getattr(self, 'btn_read', None):
                if hasattr(self, 'btn_settings'):
                    self.btn_settings.configure(width=20, height=20)
        except tk.TclError: pass

    def animate_button_press(self, button, original_size):
        """Quick press animation - shrink then restore"""
        try:
            # Shrink to 95%
            shrink_w = int(original_size[0] * 0.95)
            shrink_h = int(original_size[1] * 0.95)
            button.configure(width=shrink_w, height=shrink_h)
            
            # Restore after 100ms
            self.after(100, lambda: button.configure(width=original_size[0], height=original_size[1]))
        except tk.TclError: pass

    def on_settings_hover_enter(self, event):
        """Settings icon gets extra big when hovered (on top of sound hover effect)"""
        try:
            # Settings goes to 110% (extra 5% on top of sound's 5%)
            self.btn_settings.configure(width=24, height=24)
        except tk.TclError: pass

    def on_settings_hover_leave(self, event):
        """Restore settings to sound hover size (not original - sound might still be hovered)"""
        try:
            # Back to 105% (sound hover size)
            self.btn_settings.configure(width=21, height=21)
        except tk.TclError: pass


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
                self.settings.get("ai_output_format", "plain")
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
                result = asyncio.run(analyze_screenshot(screenshot_b64, system_prompt=img_sys))
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

    def _show_ai_error(self, message: str):
        from config import APP_NAME
        messagebox.showwarning(APP_NAME, message)

    def _show_lock_popup(self, message: str):
        import webbrowser
        popup = ctk.CTkToplevel(self)
        popup.geometry("380x160")
        popup.title("\u09b8\u09be\u09ac\u09b8\u09cd\u0995\u09cd\u09b0\u09bf\u09aa\u09b6\u09a8 \u09aa\u09cd\u09b0\u09df\u09cb\u099c\u09a8")
        popup.attributes("-topmost", True)
        ctk.CTkLabel(popup, text=message, font=("Segoe UI", 12),
                     wraplength=340, justify="center").pack(pady=20)
        ctk.CTkButton(popup, text="\u09b8\u09be\u09ac\u09b8\u09cd\u0995\u09cd\u09b0\u09be\u0987\u09ac \u0995\u09b0\u09c1\u09a8",
                      command=lambda: [webbrowser.open("https://ejobsit.com/ai-voice"),
                                       popup.destroy()]).pack(pady=4)
        ctk.CTkButton(popup, text="\u09ac\u09be\u09a4\u09bf\u09b2", fg_color="#333333",
                      command=popup.destroy).pack()
        popup.after(8000, popup.destroy)

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

    def open_settings_panel(self):
        from ui.settings_panel import SettingsPanel
        if self._settings_win is None or not self._settings_win.winfo_exists():
            self._settings_win = SettingsPanel(parent=self, app_ref=self)
            self._settings_win.attributes("-topmost", True)
        self._settings_win.focus()
        self._settings_win.lift()

    def show_instructions(self):
        txt = tr("instructions_text")
        # Legacy hardcoded text replaced by tr("instructions_text") - see desktop/i18n.py
        info_win = ctk.CTkToplevel(self)
        info_win.title(tr("instructions_window_title"))
        info_win.attributes('-topmost', True)  # Set topmost first
        
        # Position to the RIGHT of settings window
        if self.settings_window and self.settings_window.winfo_exists():
            try:
                # Position to the right side of settings window
                x = self.settings_window.winfo_x() + self.settings_window.winfo_width() + 10
                y = self.settings_window.winfo_y()
                info_win.geometry(f"500x750+{x}+{y}")
            except tk.TclError:
                info_win.geometry("500x750")
        else:
            info_win.geometry("500x750")

        info_win.resizable(False, False)
        info_win.lift()  # Bring to front
        info_win.focus_force()  # Take focus
        
        # Schedule another lift to ensure it stays on top
        info_win.after(100, lambda: info_win.lift())

        try: info_win.iconbitmap(self.icon_path)
        except tk.TclError: pass
        
        # Header with Logo
        head_frame = ctk.CTkFrame(info_win, fg_color="transparent")
        head_frame.pack(pady=(15, 10))
        
        try:
            if self.icon_path:
                from PIL import Image
                img = Image.open(self.icon_path)
                logo_img = ctk.CTkImage(light_image=img, dark_image=img, size=(50, 50))
                ctk.CTkLabel(head_frame, text="", image=logo_img).pack(side="left", padx=10)
        except (OSError, tk.TclError): pass

        l = ctk.CTkLabel(head_frame, text="ডুয়েল ভয়েসার গাইডলাইন", font=("Segoe UI", 18, "bold"), text_color="#f39c12")
        l.pack(side="left")
        
        textbox = ctk.CTkTextbox(info_win, font=("Segoe UI", 13), text_color="#ecf0f1", fg_color="#2c3e50")
        textbox.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        textbox.insert("0.0", txt)
        textbox.configure(state="disabled")

    def open_auth_panel(self):
        """Open authentication panel - Web-First model (no registration here)"""
        # Web-First model (no registration here)

        
        # Check if already open
        if hasattr(self, 'auth_window') and self.auth_window is not None and self.auth_window.winfo_exists():
            self.auth_window.lift()
            self.auth_window.focus_force()
            return

        # Create auth dialog
        self.auth_window = ctk.CTkToplevel(self)
        dialog = self.auth_window # Use local var for convenience
        dialog.title("Dual Voicer - Login")
        dialog.geometry("450x540") # Increased height for logo
        dialog.resizable(False, False)
        dialog.attributes('-topmost', True)
        
        # Position to the RIGHT of settings window
        try:
            if self.settings_window and self.settings_window.winfo_exists():
                x = self.settings_window.winfo_x() + self.settings_window.winfo_width() + 10
                y = self.settings_window.winfo_y()
                dialog.geometry(f"450x540+{x}+{y}")
            else:
                dialog.geometry("450x540+100+100")
        except tk.TclError:
            dialog.geometry("450x540+100+100")
        
        dialog.lift()  # Bring to front
        dialog.focus_force()  # Take focus
        # Schedule another lift to ensure it stays on top
        dialog.after(100, lambda: dialog.lift())
            
        try: dialog.after(200, lambda: dialog.iconbitmap(self.icon_path))
        except tk.TclError: pass
        
        # Logo and Title
        header_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        header_frame.pack(pady=(20, 10))
        
        # Load larger logo for dialog
        try:
            if self.icon_path:
                from PIL import Image
                img = Image.open(self.icon_path)
                logo_img = ctk.CTkImage(light_image=img, dark_image=img, size=(64, 64))
                ctk.CTkLabel(header_frame, text="", image=logo_img).pack(pady=(0, 5))
        except (OSError, tk.TclError): pass

        ctk.CTkLabel(
            header_frame, text="Dual Voicer Premium", 
            font=("Segoe UI", 20, "bold"), text_color="#667eea"  # Logo Blue
        ).pack()
        
        ctk.CTkLabel(
            header_frame, text="Login to activate premium features", 
            font=("Arial", 11), text_color="#95a5a6"
        ).pack()
        
        # Input Fields
        input_frame = ctk.CTkFrame(dialog)
        input_frame.pack(fill="x", padx=30, pady=10)
        
        email_entry = ctk.CTkEntry(
            input_frame, placeholder_text="Enter your Email (Gmail Only)",
            height=40, font=("Segoe UI", 12)
        )
        email_entry.pack(fill="x", pady=(10, 5), padx=10)
        
        # Pre-fill email/phone if saved
        saved_email, saved_phone = self.load_login_config()
        if saved_email:
            email_entry.insert(0, saved_email)
            
        phone_entry = ctk.CTkEntry(
            input_frame, placeholder_text="Phone Number (e.g. 017...)",
            height=40, font=("Segoe UI", 12)
        )
        phone_entry.pack(fill="x", pady=(5, 10), padx=10)
        
        if saved_phone:
            phone_entry.insert(0, saved_phone)
        
        # Reference for API usage
        self.phone_entry_ref = phone_entry
        
        # Status Label
        status_label = ctk.CTkLabel(dialog, text="", font=("Arial", 11))
        status_label.pack(pady=5)
        
        # Login Handler
        def handle_login():
            """Validate existing user login with email + phone verification"""
            email = email_entry.get().strip().lower()
            phone = phone_entry.get().strip()
            
            if not email or "@" not in email:
                status_label.configure(text="Please enter a valid email address", text_color="#e74c3c")
                return
            
            # Gmail-only validation
            if not email.endswith('@gmail.com'):
                status_label.configure(text="⚠️ Only Gmail addresses are allowed", text_color="#e74c3c")
                return
                
            if len(phone) < 11:
                status_label.configure(text="⚠️ Please enter a valid phone number", text_color="#e74c3c")
                return
            
            status_label.configure(text="Authenticating...", text_color="#f39c12")
            dialog.update()
            
            # Run login validation in background (Using Secure API)
            threading.Thread(
                target=self.validate_device_access,
                args=(email, dialog, status_label),
                daemon=True
            ).start()
        
        # Action Buttons Frame
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=5)
        
        # Login Button
        ctk.CTkButton(
            btn_frame, text="🔓 Login", width=180, height=40,
            fg_color="#764ba2", hover_color="#6b46a3",  # Logo Purple
            font=("Segoe UI", 12, "bold"),
            command=handle_login
        ).pack(side="left", padx=5)
        
        # Cancel Button
        ctk.CTkButton(
            btn_frame, text="Cancel", width=180, height=40,
            fg_color="#4a5568", hover_color="#2d3748",  # Dark Gray
            command=dialog.destroy
        ).pack(side="left", padx=5)
        
        # Separator
        separator = ctk.CTkFrame(dialog, height=1, fg_color="#34495e")
        separator.pack(fill="x", padx=30, pady=10)
        
        # Registration Links
        links_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        links_frame.pack(pady=5)
        
        ctk.CTkLabel(
            links_frame, text="Don't have an account?",
            font=("Arial", 10), text_color="#95a5a6"
        ).pack()
        
        # Website Registration Buttons
        web_btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        web_btn_frame.pack(pady=5)
        
        # Trial signup handler with HWID
        def open_trial_signup():
            """Open trial signup with HWID parameter and warning"""
            hwid = self.get_stable_hwid()
            
            # Show warning about trial limit
            messagebox.showinfo(
                "Trial Signup",
                "🎁 Free Trial Information:\n\n"
                "• Each computer can only create ONE free trial\n"
                "• Trial period: 7 days\n"
                "• If you've already used a trial on this computer,\n"
                "  please purchase a subscription instead\n\n"
                "Opening browser for trial signup..."
            )
            
            # Open website with HWID parameter
            signup_url = f"https://dualvoicer.ejobsit.com/?trial=yes&hwid={hwid}"
            webbrowser.open(signup_url)
        
        # Free Trial Button - Opens Website with HWID
        ctk.CTkButton(
            web_btn_frame, text="🎁 Start Free Trial", width=180, height=35,
            fg_color="#667eea", hover_color="#5a67d8",  # Logo Blue
            font=("Segoe UI", 11, "bold"),
            command=open_trial_signup
        ).pack(side="left", padx=5)
        
        # Buy Subscription Button - Opens Website
        ctk.CTkButton(
            web_btn_frame, text="💳 Buy Subscription", width=180, height=35,
            fg_color="#9f7aea", hover_color="#805ad5",  # Logo Light Purple
            font=("Segoe UI", 11, "bold"),
            command=lambda: webbrowser.open("https://dualvoicer.ejobsit.com")
        ).pack(side="left", padx=5)
        
        # Bind Enter key to login
        email_entry.bind("<Return>", lambda e: phone_entry.focus())
        phone_entry.bind("<Return>", lambda e: handle_login())
    
    def validate_device_access(self, email, dialog, status_label, is_auto_login=False):
        """SECURE API LOGIN: Validates user via Website API"""
        def _api_login_thread():
            try:
                # API Endpoint
                API_URL = "https://dualvoicer.ejobsit.com/api/desktop-login"
                
                # Retrieve phone number - New Logic
                phone_number = ""
                if is_auto_login:
                    phone_number = getattr(self, '_auto_login_phone', "")
                elif hasattr(self, 'phone_entry_ref'):
                    try:
                        phone_number = self.phone_entry_ref.get().strip()
                    except (tk.TclError, AttributeError): pass
                
                payload = {
                    "email": email,
                    "phone": phone_number,
                    "hwid": self.hardware_id
                }
                
                print(f"[API] Checking login for {email} with phone...")
                
                try:
                    response = requests.post(API_URL, json=payload, timeout=10)
                    data = response.json()
                    
                    if response.status_code == 200 and data.get("success"):
                        # SUCCESS from API - but check expiry first!
                        user = data.get("user", {})
                        
                        # CRITICAL: Check expiry BEFORE allowing login
                        expiry_str = user.get("expiry_date") or user.get("expires_at")
                        plan_type = user.get("plan_type", "Premium")
                        
                        if expiry_str:
                            try:
                                # Parse expiry date (ISO format from API)
                                if isinstance(expiry_str, str):
                                    expiry_datetime = datetime.datetime.fromisoformat(expiry_str.replace('Z', '+00:00').replace('+00:00', ''))
                                else:
                                    expiry_datetime = expiry_str
                                
                                if datetime.datetime.now() > expiry_datetime:
                                    # EXPIRED! Block login
                                    if plan_type.lower() == "trial":
                                        error_msg = tr("err_trial_expired")
                                    else:
                                        error_msg = tr("err_subscription_expired")
                                    
                                    # Clear saved config for expired users
                                    try:
                                        if hasattr(self, 'config_file') and os.path.exists(self.config_file):
                                            os.remove(self.config_file)
                                    except OSError: pass
                                    
                                    if is_auto_login:
                                        print(f"[SECURITY] Auto-login blocked: Trial/Subscription expired")
                                        # Show login panel for expired users
                                        self.after(0, self.force_logout_expired)
                                        return
                                    
                                    self.after(0, lambda: self.login_failed(error_msg, status_label))
                                    return
                            except Exception as e:
                                print(f"[WARNING] Expiry check failed: {e}")

                        # --- REMOVED LEGACY FIRESTORE CHECK ---
                        # Security is now fully handled by the API response (plan_type & expiry)
                        # and Server-side One-Device-One-Trial logic.
                        # --------------------------------------

                        # Cache user data for UI (Plan Info)
                        self.user_cache = user
                        self.user_email = email # Ensure this is set
                        
                        devices_used = user.get("devices_used", 1)
                        max_devices = user.get("max_devices", 1)
                        
                        self.after(0, lambda: self.login_success(email, phone_number, devices_used, max_devices, dialog, is_auto_login))
                        return
                        
                    else:
                        # FAIL returned by API
                        error_msg = data.get("message", "Login Failed")
                        
                        if is_auto_login:
                             print(f"[API] Auto-login blocked: {error_msg}")
                             try: os.remove(self.config_file)
                             except OSError: pass
                             return
                        
                        self.after(0, lambda: self.login_failed(error_msg, status_label))
                        return
                        
                except requests.exceptions.RequestException as e:
                    # Network Error
                    print(f"[API] Network Error: {e}")
                    if is_auto_login:
                        return
                    
                    self.after(0, lambda: self.login_failed(tr("err_server_connection"), status_label))
                    
            except Exception as e:
                print(f"[API] System Error: {e}")
                if not is_auto_login:
                    self.after(0, lambda: self.login_failed(f"System Error: {e}", status_label))

        # Run network request in thread
        threading.Thread(target=_api_login_thread, daemon=True).start()
    
    def login_success(self, email, phone, device_count, max_devices=2, dialog=None, is_auto_login=False):
        """Handle successful login"""
        # Close login dialog immediately to prevent "stuck" UI
        if dialog:
            try: dialog.destroy()
            except tk.TclError: pass
            
        self.user_email = email
        self.user_phone = phone # Store phone for background verification
        self.is_authenticated = True
        self.device_count = device_count
        self.max_devices = max_devices  # Store for display
        
        # Save login for auto-login next time
        self.save_login_config(email, phone)
        
        # Fetch user plan info from Firestore to show in button
        self.fetch_and_update_plan_info()
        
        # Show success message
        if not is_auto_login:
            messagebox.showinfo(
                "Login Successful", 
                f"✅ Login Successful!\n\nWelcome Back!\n\nEmail: {email}\nDevices: {device_count}/{max_devices}"
            )
        else:
            print(f"[INFO] Auto-login successful for {email}")
        
        # Update window title to show premium status
        self.update_window_title()
        
        # SECURITY: Save last verification timestamp
        self._last_verified = time.time()
        
        # SECURITY: Start periodic re-verification (every 24 hours)
        self.schedule_periodic_verification()

    def schedule_periodic_verification(self):
        """SECURITY: Schedule periodic online verification to prevent offline abuse"""
        # Re-verify every 24 hours (86400000 ms)
        def verify_periodically():
            if self.is_authenticated and self.user_email:
                print("[SECURITY] Periodic verification triggered (24h)")
                threading.Thread(
                    target=self.verify_subscription_status,
                    daemon=True
                ).start()
            # Schedule next check
            self.after(86400000, verify_periodically)  # 24 hours

        # First check after 24 hours
        self.after(86400000, verify_periodically)
    
    def verify_subscription_status(self):
        """SECURITY: Verify subscription via API (Replaces Legacy Firestore Check)"""
        try:
            # Check for internet first (simple DNS check or similar, but requests will handle it)
            API_URL = "https://dualvoicer.ejobsit.com/api/desktop-login"
            
            # Use stored phone or try to get from config
            phone = getattr(self, 'user_phone', '')
            if not phone:
                 _, phone = self.load_login_config()
            
            payload = {
                "email": self.user_email,
                "phone": phone,
                "hwid": self.hardware_id
            }
            
            print("[SECURITY] Verifying subscription via API...")
            response = requests.post(API_URL, json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                     user = data.get("user", {})
                     # Check expiry from API response
                     expiry_str = user.get("expiry_date") or user.get("expires_at")
                     
                     if expiry_str:
                        try:
                            if isinstance(expiry_str, str):
                                expiry_dt = datetime.datetime.fromisoformat(expiry_str.replace('Z', '+00:00').replace('+00:00', ''))
                            else:
                                expiry_dt = expiry_str
                                
                            if datetime.datetime.now() > expiry_dt:
                                print("[SECURITY] API says: Expired")
                                self.after(0, self.force_logout_expired)
                                return
                        except (KeyError, ValueError, TypeError): pass

                     # Check if device is still in allowed list (API handles this logic too, but good to check user obj)
                     # Actually, if API returns success=True, it means device is allowed.
                     
                     # Update local cache
                     self.user_cache = user
                     self.device_count = user.get("devices_used", 1)
                     self.max_devices = user.get("max_devices", 1)
                     self.after(0, self.fetch_and_update_plan_info)
                     
                     print("[SECURITY] Verification Successful")
                     self._last_verified = time.time()
                     return
                else:
                    print(f"[SECURITY] API Verification Failed: {data.get('message')}")
                    # If API explicitly says failed (e.g. device removed), logout
                    if "device" in data.get("message", "").lower() or "expire" in data.get("message", "").lower():
                         self.after(0, self.force_logout_expired)
            else:
                print(f"[SECURITY] API Error {response.status_code}")
                # Don't logout on 500/404 errors, maybe temp server issue
                
        except Exception as e:
            print(f"[SECURITY] Verification connection error: {e}")
            # Offline is okay, we let them continue until next check
    
    def force_logout_expired(self):
        """SECURITY: Force logout when subscription/verification fails"""
        self.is_authenticated = False
        self.user_email = None
        self.clear_login_config()
        self.update_window_title()
        messagebox.showwarning(
            tr("title_subscription_ended"),
            tr("msg_subscription_ended"),
        )
        self.open_auth_panel()
    
    def login_failed(self, message, status_label):
        """Handle failed login"""
        if status_label:
            status_label.configure(text=message, text_color="#e74c3c")
        else:
            print(f"[ERROR] Login failed: {message}")
    
    def handle_logout(self):
        """Handle user logout"""
        # Confirm logout
        response = messagebox.askyesno(
            "Logout",
            "Are you sure you want to logout?\n\n"
            "You will need to login again next time."
        )
        
        if response:
            # Clear saved login config
            self.clear_login_config()
            
            # Reset authentication state
            self.is_authenticated = False
            self.user_email = None
            self.device_count = 0
            
            # Update window title
            self.update_window_title()
            
            # Update UI to Logged Out state
            self.fetch_and_update_plan_info()
            
            print("[INFO] User logged out successfully")
            
            # Show login panel
            self.open_auth_panel()
    
    
    def fetch_and_update_plan_info(self):
        """Fetch plan info from Local Cache and update UI (Handles Login & Logout states)"""
        try:
            # Check if login button frame exists
            if not hasattr(self, 'login_btn_frame') or not self.login_btn_frame.winfo_exists():
                return
            
            # Case 1: Logged Out
            if not self.user_email:
                # Clear frame
                for widget in self.login_btn_frame.winfo_children():
                    widget.destroy()
                
                # Recreate login button
                self.btn_login = ctk.CTkButton(
                    self.login_btn_frame, text="  🔐 Login / Activate",
                    fg_color="#764ba2", hover_color="#6b46a3",
                    font=("Segoe UI", 12, "bold"), height=35,
                    command=self.open_auth_panel
                )
                self.btn_login.pack(fill="x")
                
                if self.expiry_info_label:
                    self.expiry_info_label.configure(text="")
                return
            
            # Use cached data if available
            user_data = getattr(self, 'user_cache', {})
            if not user_data:
                # If no cache but email exists, maybe show basic info
                plan_type = "..."
                days_remaining = 0
            else:
                plan_type = user_data.get('plan_display', 'Premium')
                expiry_str = user_data.get('expiry_date')
                
                # Calculate days remaining
                days_remaining = 0
                if expiry_str and expiry_str != 'N/A':
                    try:
                        # Parse YYYY-MM-DD
                        exp_date = datetime.datetime.strptime(expiry_str, '%Y-%m-%d')
                        days_remaining = (exp_date - datetime.datetime.now()).days
                    except (ValueError, TypeError):
                        pass

            # Update button with plan info - SIDE BY SIDE LAYOUT using GRID
            if hasattr(self, 'login_btn_frame') and self.login_btn_frame is not None and self.login_btn_frame.winfo_exists():
                emoji = "🎁" if "trial" in plan_type.lower() else "✓"
                
                # Clear any existing pack/grid slaves
                for widget in self.login_btn_frame.winfo_children():
                    widget.destroy()
                    
                # Configure grid for 55-45 split
                self.login_btn_frame.grid_columnconfigure(0, weight=6)
                self.login_btn_frame.grid_columnconfigure(1, weight=4)
                self.login_btn_frame.configure(fg_color="transparent")
                
                # LEFT: Plan Info Box
                # Softer colors
                plan_color = "#219150" if plan_type.lower() in ["premium", "unlimited"] else "#d35400" 
                if "trial" in plan_type.lower(): plan_color = "#d35400" # Softer Orange
                
                # Plan Label as Button
                display_text = f"{emoji} {plan_type}"
                
                plan_btn = ctk.CTkButton(
                    self.login_btn_frame,
                    text=display_text,
                    fg_color=plan_color,
                    hover_color=plan_color,
                    font=("Segoe UI", 12, "bold"),
                    height=32,
                    state="normal"
                )
                plan_btn.grid(row=0, column=0, sticky="ew", padx=(0, 5))
                
                # Store reference
                self.btn_login = plan_btn
                
                # RIGHT: Logout Button
                self.btn_logout = ctk.CTkButton(
                    self.login_btn_frame,
                    text="Logout",
                    fg_color="#7f8c8d", # Gray instead of Red
                    hover_color="#95a5a6",
                    font=("Segoe UI", 11, "bold"),
                    height=32,
                    width=80,
                    command=self.handle_logout
                )
                self.btn_logout.grid(row=0, column=1, sticky="ew", padx=(5, 0))
            
            # Update expiry info label WITH DEVICE COUNT
            if self.expiry_info_label:
                # Add Device Count
                device_info = f" • Device: {getattr(self, 'device_count', 1)}/{getattr(self, 'max_devices', 2)}"
                
                if days_remaining > 0:
                    self.expiry_info_label.configure(
                        text=f"{days_remaining} days remaining{device_info}",
                        text_color="#27ae60"
                    )
                elif days_remaining == 0:
                    self.expiry_info_label.configure(
                        text=f"Expires today!{device_info}",
                        text_color="#f39c12"
                    )
                else:
                    self.expiry_info_label.configure(
                        text=f"Expired{device_info}",
                        text_color="#e74c3c"
                    )
                    # Note: Expired users should already be blocked at login time
                    # This is just a fallback UI indicator
                    
        except Exception as e:
            print(f"[ERROR] Failed to update plan info: {e}")
            # Fallback
            pass
    

    def check_authenticate_on_startup(self):
        """SECURITY: Force authentication on startup if not logged in"""
        from config import DEV_MODE
        if DEV_MODE:
            return  # Skip auth in dev mode
        # Check if auto-login is in progress
        if hasattr(self, '_auto_login_attempted'):
            return
        
        if not self.is_authenticated:
            # Try auto-login first
            saved_email, _ = self.load_login_config()
            
            if saved_email:
                print(f"[SECURITY] Found saved login for: {saved_email}. Attempting auto-login...")
                self._auto_login_attempted = True
                
                # Run validation in background to avoid freezing UI
                threading.Thread(
                    target=self.validate_device_access,
                    args=(saved_email, None, None, True), # is_auto_login=True
                    daemon=True
                ).start()
            else:
                print("[SECURITY] No saved login found - opening login panel")
                self.update_window_title()  # Show "Unregistered"
                self.open_auth_panel()
    
    def update_window_title(self):
        """Update window title based on authentication status"""
        if self.is_authenticated:
            plan_type = "Premium"  # You can check Firestore for plan_type if needed
            self.title(f"Dual Voicer ({plan_type})")
        else:
            self.title("Dual Voicer (Unregistered)")
    
    def toggle_desktop_visibility(self):
        val = bool(self.desk_switch.get())
        self.settings["show_desktop_icon"] = val
        if val: self.deiconify()
        else: self.withdraw()
        self.save_settings()  # Auto-save on toggle

    def save_settings(self):
        """Save all settings to AppData file"""
        try:
            if hasattr(self, 'settings_file'):
                with open(self.settings_file, 'w', encoding='utf-8') as f:
                    json.dump(self.settings, f, indent=2, ensure_ascii=False)
            # Update button labels after save
            self.after(0, self.update_button_labels)
        except Exception as e:
            print(f"[WARNING] Failed to save settings: {e}")



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

    def reset_engine_with_feedback(self):
        """User-facing reset (called from Settings → Reset Engine button).
        Runs the silent reset and pops a small toast so the user knows it
        actually happened - otherwise the click feels like nothing changed."""
        ok = self._silent_reset()
        # Show a tiny toast next to the widget so the user sees feedback
        try:
            self._show_toast(
                "✓ Engine reset" if ok else "⚠ Reset busy - try again",
                color=("#1A5A1A" if ok else "#8B5A20"))
        except Exception as e:
            print(f"[reset toast] {e}")

    def _show_toast(self, text: str, color: str = "#1A5A1A", duration_ms: int = 1400):
        """Floating non-blocking toast near the widget. Self-dismissing."""
        try:
            toast = ctk.CTkToplevel(self)
            toast.overrideredirect(True)
            toast.attributes('-topmost', True)
            toast.configure(fg_color=color)
            wx, wy, wh = self.winfo_x(), self.winfo_y(), self.winfo_height()
            toast.geometry(f"220x32+{wx}+{wy + wh + 6}")
            ctk.CTkLabel(toast, text=text, text_color="white",
                         fg_color=color, font=("Segoe UI", 12, "bold"),
                         height=32, corner_radius=8).pack(fill="both", expand=True)
            def _dismiss():
                try: toast.destroy()
                except tk.TclError: pass
            toast.after(duration_ms, _dismiss)
        except tk.TclError:
            pass

    def close_settings(self):
        self.save_settings()
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.destroy()
        if hasattr(self, '_settings_win') and self._settings_win and self._settings_win.winfo_exists():
            self._settings_win.destroy()
        try: self.on_hover_leave(None)
        except Exception: pass

    def update_max_opacity(self, v):
        self.settings["max_opacity"] = v
        self.attributes('-alpha', v)
        self.save_settings()

    def update_idle_opacity(self, v):
        self.settings["idle_opacity"] = v
        self.save_settings()
    
    def toggle_sound(self):
        """Apply sound-effect toggle. Settings dict is already updated by the
        settings panel from the switch's var.get() - we only persist + log."""
        self.save_settings()
        print(f"[SETTINGS] Sound {'enabled' if self.settings.get('sound_enabled', True) else 'disabled'}")

    def toggle_labels(self):
        """Toggle button label visibility"""
        show = self.settings.get("show_labels", True)
        for btn in [self.btn_bn, self.btn_en, self.btn_read, self.btn_ai]:
            btn.set_labels_visible(show)
        self.save_settings()
    
    def update_timeout(self, v):
        self.settings["auto_timeout"] = "99999" if v == "∞" else v
        self.save_settings()

    def update_speed(self, v):
        self.settings["reading_speed"] = v
        self.save_settings()

    def update_noise_threshold(self, v):
        """Update noise filter threshold (slider callback)"""
        threshold = int(v)
        self.settings["noise_threshold"] = threshold
        
        # Update label in real-time
        if hasattr(self, 'noise_label'):
            self.noise_label.configure(text=str(threshold))
        
        # Apply new settings immediately
        self.apply_mic_sensitivity()
        self.save_settings()
        print(f"[SETTINGS] Noise threshold changed to: {threshold}")

    def on_press(self, event): 
        self.drag_start["x"] = event.x_root
        self.drag_start["y"] = event.y_root
        self.drag_start["root_x"] = self.winfo_x()
        self.drag_start["root_y"] = self.winfo_y()
        self.is_dragging = False  # Reset flag
        self.drag_started = False  # Track if drag motion started
        
        # Save the currently focused window to restore focus after button click
        try:
            self._previous_foreground = ctypes.windll.user32.GetForegroundWindow()
        except (OSError, AttributeError):
            self._previous_foreground = None

    def on_drag(self, event):
        dx = event.x_root - self.drag_start["x"]
        dy = event.y_root - self.drag_start["y"]
        threshold = 5
        
        if not self.drag_started and (abs(dx) > threshold or abs(dy) > threshold):
            self.drag_started = True
            self.is_dragging = True
        
        if self.is_dragging:
            x = self.drag_start["root_x"] + dx
            y = self.drag_start["root_y"] + dy
            self.geometry(f"+{x}+{y}")
    
    def _on_bg_release(self, event):
        """Save position after dragging the toolbar background."""
        if self.is_dragging:
            try:
                self.settings["window_x"] = self.winfo_x()
                self.settings["window_y"] = self.winfo_y()
                self.save_settings()
            except Exception:
                pass
        self.is_dragging = False

    def on_release(self, event, cmd):
        # SAVE POSITION after dragging
        if self.is_dragging:
            try:
                new_x = self.winfo_x()
                new_y = self.winfo_y()
                self.settings["window_x"] = new_x
                self.settings["window_y"] = new_y
                self.save_settings()
                print(f"[POSITION] Saved new position: ({new_x}, {new_y})")
            except Exception as e:
                print(f"[WARNING] Failed to save position: {e}")
        
        # Only trigger command if not dragging
        if not self.is_dragging:
            cmd()
            # Restore focus to previous window using alt+tab (works better than SetForegroundWindow)
            threading.Thread(target=lambda: (time.sleep(0.02), pyautogui.hotkey('alt', 'tab')), daemon=True).start()


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
            self.is_listening = False; self.active_lang = None
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
            # STARTING voice typing
            # If switching from other lang while listening, do reset first
            if self.is_listening:
                self.is_listening = False
                self._silent_reset()
                time.sleep(0.1)

            # Start mic FIRST, then play sound when mic is ready
            self.mic_ready_event.clear()
            self.active_lang = lang; self.is_listening = True
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

    def show_network_error(self):
        # Prevent stacking multiple notifications
        if getattr(self, '_network_toast_showing', False):
            return
        self._network_toast_showing = True

        try:
            # Create floating toast notification near widget
            toast = ctk.CTkToplevel(self)
            toast.overrideredirect(True)
            toast.attributes('-topmost', True)
            toast.configure(fg_color="#e74c3c")

            # Position near widget
            wx = self.winfo_x()
            wy = self.winfo_y()
            wh = self.winfo_height()
            toast.geometry(f"200x30+{wx}+{wy + wh + 5}")

            label = ctk.CTkLabel(toast, text="⚠ No Internet", text_color="white",
                                 fg_color="#e74c3c", font=("Segoe UI", 12, "bold"),
                                 height=30, corner_radius=8)
            label.pack(fill="both", expand=True)

            # Auto-dismiss after 1.5 seconds
            def dismiss():
                try:
                    toast.destroy()
                except tk.TclError: pass
                self._network_toast_showing = False

            toast.after(1500, dismiss)
        except tk.TclError:
            self._network_toast_showing = False



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
                            # Listen for small chunks (OPTIMIZED v3.6.9)
                            # Shorter phrase_time_limit = faster API response, less queue buildup
                            audio = self.recognizer.listen(source, timeout=1.0, phrase_time_limit=8)
                            # Race guard: listen() can block up to phrase_time_limit
                            # seconds. If the user stopped typing in the meantime,
                            # active_lang has been cleared to None - queueing it
                            # would later cause recognize_google() to error with
                            # "`language` must be a string". Drop stale chunks.
                            captured_lang = self.active_lang
                            if not self.is_listening or not isinstance(captured_lang, str) or not captured_lang:
                                continue
                            self.audio_queue.put((audio, captured_lang))
                            
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



    def process_punctuation(self, text, lang):
        """Smart punctuation processing with multiple variations"""
        
        # Define punctuation triggers with multiple variations
        triggers = {}
        if lang == "bn-BD":
            # Bangla punctuation - multiple variations
            triggers = {
                # Full stop variations
                "দাড়ি": "।",
                "দাঁড়ি": "।",
                "ফুলস্টপ": "।",
                "ফুল স্টপ": "।",  # With space
                
                # Comma variations - only as standalone word
                "কমা": ",",
                
                # Question mark variations
                "প্রশ্নবোধক": "?",
                "প্রশ্নবোধক চিহ্ন": "?",
                "জিজ্ঞাসা": "?",
                "জিজ্ঞাসা চিহ্ন": "?",
                "কোশ্চেন মার্ক": "?",
                "কোশ্চেন": "?",
                
                # Exclamation mark variations
                "বিস্ময়সূচক": "!",
                "বিস্ময় সূচক": "!",
                "বিস্ময়বোধক": "!",
                "বিস্ময় চিহ্ন": "!",
                "বিস্ময়": "!",
                "আশ্চর্যবোধক": "!",
                
                # New line variations
                "নতুন লাইন": "\n",
                "নিউ লাইন": "\n",
                "নিউলাইন": "\n"
            }
        else:
            # English punctuation
            triggers = {
                "full stop": ".",
                "period": ".",
                "comma": ",",
                "question mark": "?",
                "question": "?",
                "exclamation": "!",
                "exclamation mark": "!",
                "new line": "\n",
                "newline": "\n"
            }
        
        lower_txt = text.lower().strip()
        
        # Check if entire text is a punctuation trigger (highest priority)
        if lower_txt in triggers:
            return triggers[lower_txt], True
        
        # For Bangla: Special handling for "কমা" to allow it even if attached to words
        if lang == "bn-BD" and "কমা" in lower_txt:
            processed = text
            # Regex to match "কমা" when it ends a word or sentence
            # It matches: space? + কমা + (space or end of string)
            # This handles "শব্দ কমা" -> "শব্দ,"
            processed = re.sub(r'\s*কমা(\s|$)', r',\1', processed)
            
            # Also handle if it's strictly attached like "শব্দকমা" (though rare in STT)
            if "কমা" in processed:
                 processed = re.sub(r'কমা(\s|$)', r',\1', processed)
            
            return processed, False
        
        # Process in-text punctuation triggers
        processed = text
        punctuation_found = False
        
        # IMPORTANT: Sort triggers by length (longest first) to avoid partial matches
        # e.g., "জিজ্ঞাসা চিহ্ন" should be matched before "জিজ্ঞাসা"
        sorted_triggers = sorted(triggers.items(), key=lambda x: len(x[0]), reverse=True)
        
        for trigger, symbol in sorted_triggers:
            # Skip "কমা" for Bangla as it's handled above
            if lang == "bn-BD" and trigger == "কমা":
                continue
            
            trigger_lower = trigger.lower()
            
            # Check if trigger exists in text
            if trigger_lower in lower_txt:
                # Replace with word boundaries to avoid false matches
                # For multi-word triggers, use exact phrase matching
                if ' ' in trigger:
                    # Multi-word trigger (e.g., "question mark", "প্রশ্নবোধক চিহ্ন")
                    pattern = re.escape(trigger)
                    processed = re.sub(pattern, symbol, processed, flags=re.IGNORECASE)
                else:
                    # Single word trigger
                    # For Bangla: Use custom boundary detection (space or start/end)
                    if lang == "bn-BD":
                        # Bangla: Match at word boundaries (space, start, or end)
                        # Pattern: (start|space) + trigger + (space|end)
                        pattern = r'(^|\s)' + re.escape(trigger) + r'(\s|$)'
                        # Replace but keep the surrounding spaces
                        processed = re.sub(pattern, r'\1' + symbol + r'\2', processed, flags=re.IGNORECASE)
                    else:
                        # English: Use word boundaries
                        pattern = r'\b' + re.escape(trigger) + r'\b'
                        processed = re.sub(pattern, symbol, processed, flags=re.IGNORECASE)
                
                punctuation_found = True
        
        # Clean up spacing around punctuation
        if punctuation_found:
            # Remove space before punctuation marks (Added . to list) - but NOT before \n
            processed = re.sub(r'[ \t]+([.।,?!;:--])', r'\1', processed)
            # Remove multiple spaces (but preserve newlines)
            processed = re.sub(r'[ \t]+', ' ', processed)
            # Trim spaces (but keep newlines at the end)
            processed = processed.strip(' \t')
        
        return processed, punctuation_found

    def type_text(self, text, leading_space=True):
        """Type text with smart spacing for punctuation"""
        try:
            # Route to drawing engine if text/handwrite tool is active
            # AND that surface is the foreground window - otherwise voice text
            # goes to whatever OS app the user is actually typing into.
            target_engine = None
            # Check editor window first - only if it's the foreground window
            if hasattr(self, '_editor_win') and self._editor_win:
                try:
                    if (self._editor_win.winfo_exists()
                            and getattr(self._editor_win, '_has_foreground', False)):
                        engine = getattr(self._editor_win, '_engine', None)
                        if engine and engine._text_active:
                            target_engine = engine
                except Exception:
                    pass
            # Check pen overlay (overlay is always topmost when shown,
            # so foreground check is implicit via _text_active)
            if not target_engine and hasattr(self, '_pen_overlay') and self._pen_overlay:
                engine = getattr(self._pen_overlay, '_engine', None)
                if engine and engine._text_active:
                    target_engine = engine
            if target_engine:
                cleaned = text.strip()
                if cleaned:
                    inject = (" " + cleaned) if leading_space else cleaned
                    # CRITICAL: voice typing fires from a background audio
                    # thread. Tkinter is NOT thread-safe - calling canvas
                    # methods from here causes silent failures, lost chars,
                    # and caret/text desync. Marshal to the main UI thread.
                    captured_engine = target_engine
                    captured_inject = inject
                    self.after(0, lambda: captured_engine.inject_text(captured_inject))
                # Gentle focus restore - also marshal (same thread-safety reason)
                def _restore_focus():
                    try:
                        if hasattr(self, '_pen_overlay') and self._pen_overlay:
                            eng = getattr(self._pen_overlay, '_engine', None)
                            if eng is target_engine and hasattr(self._pen_overlay, '_grab_focus'):
                                self._pen_overlay._grab_focus()
                        elif hasattr(self, '_editor_win') and self._editor_win:
                            eng = getattr(self._editor_win, '_engine', None)
                            if eng is target_engine and self._editor_win.winfo_exists():
                                self._editor_win._canvas.focus_set()
                    except Exception:
                        pass
                self.after(0, _restore_focus)
                return
            # Handle embedded newlines FIRST (before strip removes them)
            if "\n" in text:
                parts = text.split("\n")
                for i, part in enumerate(parts):
                    part_stripped = part.strip()
                    if part_stripped:
                        # Determine leading space for this part
                        add_space = leading_space if i == 0 else True
                        to_type = (" " + part_stripped) if add_space else part_stripped
                        try:
                            keyboard.write(to_type, delay=0)
                        except Exception:
                            pyperclip.copy(to_type)
                            pyautogui.hotkey('ctrl', 'v')
                    if i < len(parts) - 1:  # Press shift+enter between parts
                        keyboard.press_and_release('shift+enter')
                return
            
            # Special handling for pure newline
            if text == "\n" or text.strip() == "":
                if "\n" in text or text == "\n":
                    keyboard.press_and_release('shift+enter')
                    return
            
            # Clean the text
            cleaned_text = text.strip()
            # Check if text is purely punctuation (single character)
            is_pure_punctuation = len(cleaned_text) == 1 and cleaned_text in '.।,?!;:--'
            
            # Build the text to type
            if is_pure_punctuation:
                # Pure punctuation: NO space before, NO space after
                to_type = cleaned_text
            elif leading_space:
                # Normal text: Add leading space
                to_type = " " + cleaned_text
            else:
                # Punctuation embedded: No leading space
                # But check if text starts with punctuation
                if cleaned_text and cleaned_text[0] in '.।,?!;:--':
                    # Starts with punctuation: no leading space
                    to_type = cleaned_text
                else:
                    # Normal case
                    to_type = cleaned_text
            
            # Method 1: Direct keyboard typing (delay=0 for max speed)
            try:
                keyboard.write(to_type, delay=0)
                return
            except Exception:
                pass

            # Method 2: Fallback to clipboard paste
            pyperclip.copy(to_type)
            pyautogui.hotkey('ctrl', 'v')
        except Exception: pass

    def handle_reader_click(self):
        from config import DEV_MODE
        if not DEV_MODE and not self.is_authenticated:
            self.open_auth_panel()
            return

        # Simple state machine - no _sound_busy guard
        if self.is_reading and not self.is_paused:
            # Playing → Pause (synchronous, instant)
            self._pause_reader()
        elif self.is_reading and self.is_paused:
            # Paused → check for new text, then resume or play new
            threading.Thread(target=self._reader_resume_or_new, daemon=True).start()
        else:
            # Not reading → start new
            threading.Thread(target=self._reader_start_new, daemon=True).start()

    def _reader_start_new(self):
        """Grab selected text and start TTS (background thread)."""
        try:
            saved = ""
            try: saved = pyperclip.paste()
            except Exception: pass
            pyperclip.copy("")
            pyautogui.hotkey('ctrl', 'c')
            time.sleep(0.2)
            new_text = pyperclip.paste().strip()
            if not new_text:
                pyautogui.hotkey('ctrl', 'insert')
                time.sleep(0.15)
                new_text = pyperclip.paste().strip()
            if not new_text:
                try: pyperclip.copy(saved)
                except Exception: pass
                return
            self.current_text = new_text
            self._run_tts_async()
        except Exception as e:
            print(f"[TTS ERROR] {e}")
            self.stop_reader_internal()

    def _reader_resume_or_new(self):
        """From paused state: check clipboard for new text, resume or play new."""
        try:
            saved = ""
            try: saved = pyperclip.paste()
            except Exception: pass
            pyperclip.copy("")
            pyautogui.hotkey('ctrl', 'c')
            time.sleep(0.2)
            new_text = pyperclip.paste().strip()
            if not new_text:
                # No new selection → just resume
                try: pyperclip.copy(saved)
                except Exception: pass
                self._resume_reader()
                return
            if new_text != self.current_text:
                # New text → stop old, play new
                self.stop_reader_internal()
                time.sleep(0.1)
                self.current_text = new_text
                self._run_tts_async()
            else:
                # Same text → resume
                self._resume_reader()
        except Exception as e:
            print(f"[TTS ERROR] {e}")
            self.stop_reader_internal()

    
    # ===== SMART STREAMING TTS START =====
    
    def _run_tts_async(self):
        """Entry point for Smart Streaming TTS with session management"""
        # 1. Create new session (prevents old consumers from killing this one)
        with self._tts_lock:
            self._tts_session_id += 1
            my_session = self._tts_session_id

        # 2. Initialize Queue for this session
        self.playback_queue = queue.Queue()
        self.is_reading = True; self.is_paused = False

        # 3. Update UI - playing state
        self.after(0, lambda: self.btn_read.set_state("listening"))
        self.after(0, lambda: self.btn_read.set_icon_mode("pause"))

        # 4. Start Consumer Thread (Player) with session ID
        threading.Thread(target=self.play_audio_chunks, args=(my_session,), daemon=True).start()

        # 5. Start Producer (Generator) - Runs in asyncio
        try:
            # Ensure pygame mixer is initialized
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            asyncio.run(self.stream_audio_chunks(my_session))
        except Exception as e:
            self._log_tts_error(f"TTS Producer failed: {e}")
            # Only stop if still the current session
            if self._tts_session_id == my_session:
                self.stop_reader_internal()

    def _log_tts_error(self, message):
        """Log TTS errors to file (NullWriter hides console output)"""
        try:
            import traceback
            log_path = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'DualVoicer', 'tts_error.log')
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(f"\n[{datetime.datetime.now()}] {message}\n")
                f.write(traceback.format_exc())
        except OSError:
            pass

    async def stream_audio_chunks(self, session_id):
        """PRODUCER: Splits text and generates individual audio chunks with retry"""
        try:
            full_text = self.current_text
            chunks = re.split(r'([.?!;:\n|।])', full_text)

            # Reconstruct sentences (attach delimiter to previous text)
            raw_sentences = []
            current = ""
            for part in chunks:
                if part in ".?!;:\n|।":
                    current += part
                    if current.strip():
                        raw_sentences.append(current.strip())
                    current = ""
                else:
                    current += part
            if current.strip():
                raw_sentences.append(current.strip())

            if not raw_sentences:
                raw_sentences = [full_text]

            # Merge short sentences into bigger chunks (reduces edge_tts calls
            # and eliminates gaps between sentences)
            sentences = []
            buf = ""
            for s in raw_sentences:
                if len(buf) + len(s) < 300:
                    buf = (buf + " " + s).strip() if buf else s
                else:
                    if buf:
                        sentences.append(buf)
                    buf = s
            if buf:
                sentences.append(buf)

            print(f"[TTS] Smart Streaming: {len(sentences)} chunks to process")

            from ai_engine.tts_detector import get_tts_voice
            if self.settings.get("tts_auto_detect", True):
                voice = get_tts_voice(full_text, getattr(self, 'active_lang', None) or "en-US")
            else:
                voice = self.settings.get("tts_voice", "en-US-JennyNeural")

            # Reading speed → edge_tts rate string. Old code used brittle
            # string equality ("2" never matched the saved "2.0"), so 2x
            # silently fell back to normal speed. Parse as float instead so
            # any speed (1.0/1.5/2.0/2.5/etc.) maps correctly.
            try:
                speed = float(self.settings.get("reading_speed", "1.0"))
            except (ValueError, TypeError):
                speed = 1.0
            # Clamp to edge_tts safe range (it accepts roughly -50%..+200%)
            speed = max(0.5, min(speed, 3.0))
            rate_pct = int(round((speed - 1.0) * 100))
            rate = f"{'+' if rate_pct >= 0 else ''}{rate_pct}%"

            for i, sentence in enumerate(sentences):
                if not self.is_reading or self._tts_session_id != session_id:
                    print("[TTS] Producer Stopped (session changed)")
                    break

                filename = os.path.join(tempfile.gettempdir(), f"stream_{uuid.uuid4().hex}.mp3")
                chunk_voice = voice

                # Retry logic for edge_tts (up to 2 retries with backoff)
                success = False
                for attempt in range(3):
                    try:
                        comm = edge_tts.Communicate(sentence, chunk_voice, rate=rate)
                        await comm.save(filename)
                        success = True
                        break
                    except Exception as e:
                        if attempt < 2:
                            print(f"[TTS] Chunk {i+1} attempt {attempt+1} failed: {e}, retrying...")
                            await asyncio.sleep(1 * (attempt + 1))
                        else:
                            self._log_tts_error(f"TTS chunk {i+1} failed after 3 attempts: {e}")

                if not success:
                    # Show error to user
                    self.after(0, self.show_network_error)
                    continue  # Skip this chunk, try next

                if self.is_reading and self._tts_session_id == session_id:
                    self.playback_queue.put(filename)
                    print(f"[TTS] Produced Chunk {i+1}/{len(sentences)}")
                else:
                    try: os.remove(filename)
                    except OSError: pass

            # Signal End of Stream
            if self.is_reading and self._tts_session_id == session_id:
                self.playback_queue.put(None)

        except Exception as e:
             self._log_tts_error(f"TTS Stream Error: {e}")
             if self._tts_session_id == session_id:
                 self.playback_queue.put(None)

    def play_audio_chunks(self, session_id):
        """CONSUMER: Plays audio files from the queue sequentially (session-aware)"""
        current_file = None
        is_first_chunk = True
        try:
            while self.is_reading and self._tts_session_id == session_id:
                try:
                    # First chunk: longer timeout (edge_tts needs time to generate)
                    # Subsequent chunks: shorter timeout (already in pipeline)
                    timeout = 12 if is_first_chunk else 5
                    file_path = self.playback_queue.get(timeout=timeout)

                    if file_path is None:
                        break  # End of stream signal

                    is_first_chunk = False
                    current_file = file_path
                    if not os.path.exists(current_file):
                        continue

                    # Play via pygame.mixer.music (dedicated for TTS, SFX uses Channel)
                    if not pygame.mixer.get_init(): pygame.mixer.init()
                    pygame.mixer.music.load(current_file)
                    pygame.mixer.music.play()

                    # Wait while playing (check session validity)
                    while self.is_reading and self._tts_session_id == session_id and (pygame.mixer.music.get_busy() or self.is_paused):
                         time.sleep(0.1)

                    # Cleanup after play
                    pygame.mixer.music.unload()
                    try: os.remove(current_file); current_file = None
                    except OSError: pass

                    self.playback_queue.task_done()

                except queue.Empty:
                    continue
                except Exception as e:
                    print(f"[TTS] Playback error: {e}")
                    if current_file:
                        try: os.remove(current_file)
                        except OSError: pass

        except Exception as e:
            self._log_tts_error(f"TTS Consumer Error: {e}")
        finally:
            # Only stop if still the current session (prevents killing newer session)
            if self._tts_session_id == session_id:
                self.stop_reader_internal()

    # ===== SMART STREAMING TTS END =====

    def stop_reader_internal(self):
        """Stops reader and clears Smart Streaming queue"""
        self.is_reading = False
        self.is_paused = False
        
        try: 
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
        except pygame.error: pass
        
        # CLEAR QUEUE (Critical for instant switching)
        if hasattr(self, 'playback_queue'):
            try:
                while not self.playback_queue.empty():
                    try:
                        f = self.playback_queue.get_nowait()
                        if f and os.path.exists(f): os.remove(f)
                        self.playback_queue.task_done()
                    except (OSError, Exception): pass
            except Exception: pass

        # Restore sound button to idle + play icon
        try:
            self.after(0, lambda: self.btn_read.set_state("idle"))
            self.after(0, lambda: self.btn_read.set_icon_mode("play"))
        except tk.TclError: pass

    def init_tray_icon(self):
        try:
            image = Image.open(self.icon_path)
            menu = (item('Show', self.show_from_tray), item('Exit', self.quit_app_tray))
            self.tray_icon = pystray.Icon("DV", image, "Dual Voicer", menu)
            self.tray_icon.run()
        except Exception: pass

    def withdraw_to_tray(self): 
        self.withdraw()

    def show_from_tray(self,i,m): 
        self.settings["show_desktop_icon"] = True
        self.after(0,self.deiconify)
        self.after(0,self.lift)

    def quit_app_tray(self,i,m): self.tray_icon.stop(); self.shutdown_flag.set(); self.quit()

    def is_fullscreen_app_running(self):
        """
        SMART Fullscreen Detection:
        - Returns True when a window covers the ENTIRE screen AND overlaps the taskbar
        - Works for YouTube fullscreen, games, VLC fullscreen, etc.
        """
        try:
            user32 = ctypes.windll.user32
            
            # Get the foreground window
            foreground_hwnd = user32.GetForegroundWindow()
            if not foreground_hwnd:
                return False
            
            # Exclude our own window + pen overlay/toolbar
            try:
                my_hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
                if foreground_hwnd == my_hwnd:
                    return False
                # Exclude ALL pen overlay HWNDs (render + input windows)
                if hasattr(self, '_pen_overlay') and self._pen_overlay:
                    for ph in self._pen_overlay.get_all_hwnds():
                        if foreground_hwnd == ph:
                            return False
                # Exclude pen toolbar HWND (standalone mode only)
                if (hasattr(self, '_pen_toolbar') and self._pen_toolbar
                        and getattr(self._pen_toolbar, '_mode', '') == 'standalone'):
                    tb_hwnd = self._pen_toolbar.get_hwnd()
                    if tb_hwnd and foreground_hwnd == tb_hwnd:
                        return False
            except (tk.TclError, OSError): pass
            
            # Get window class name - exclude desktop/shell
            class_name = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(foreground_hwnd, class_name, 256)
            
            # Always exclude these (desktop, shell, our window)
            always_exclude = ["Progman", "WorkerW", "Shell_TrayWnd", "TkTopLevel", "CTk"]
            if class_name.value in always_exclude:
                return False
            
            # Get screen dimensions (primary monitor)
            screen_width = user32.GetSystemMetrics(0)
            screen_height = user32.GetSystemMetrics(1)
            
            # Get foreground window rect
            rect = ctypes.wintypes.RECT()
            user32.GetWindowRect(foreground_hwnd, ctypes.byref(rect))
            
            window_width = rect.right - rect.left
            window_height = rect.bottom - rect.top
            
            # Check if window covers entire screen
            covers_full_screen = (
                window_width >= screen_width and 
                window_height >= screen_height and
                rect.left <= 0 and 
                rect.top <= 0
            )
            
            if not covers_full_screen:
                return False
            
            # KEY CHECK: Does this window cover the taskbar area?
            taskbar_hwnd = user32.FindWindowW("Shell_TrayWnd", None)
            if taskbar_hwnd:
                taskbar_rect = ctypes.wintypes.RECT()
                user32.GetWindowRect(taskbar_hwnd, ctypes.byref(taskbar_rect))
                
                # If foreground window's bottom extends to or past taskbar top, it's fullscreen
                if rect.bottom >= taskbar_rect.top:
                    print(f"[FULLSCREEN] Detected: {class_name.value}")
                    return True
            
            return False
            
        except Exception as e:
            return False
    
    def monitor_topmost(self):
        """
        Monitor window position and ensure it stays on top.
        AUTO-HIDE when fullscreen apps are running.
        RE-ENFORCE topmost every cycle to prevent going behind other windows.
        """
        try:
            if not self.winfo_exists():
                return

            # Initialize state
            if not hasattr(self, '_hidden_for_fullscreen'):
                self._hidden_for_fullscreen = False

            # If editor is open and visible, skip topmost enforcement
            # (main widget is hidden; editor manages its own window)
            editor_open = (hasattr(self, '_editor_win') and self._editor_win
                           and self._editor_win.winfo_exists()
                           and self._editor_win.winfo_viewable())
            if editor_open:
                self.after(1500, self.monitor_topmost)
                return

            # Always check fullscreen (widget should hide during games/videos)
            try:
                is_fs = self.is_fullscreen_app_running()
                self._handle_fullscreen_result(is_fs)
            except Exception:
                pass

            # RE-ENFORCE topmost: prevent widget from going behind other windows
            if not self._hidden_for_fullscreen:
                pen_active = (hasattr(self, '_pen_overlay') and self._pen_overlay
                              and self._pen_overlay.winfo_exists())

                if pen_active:
                    # Z-order: input < MAIN WIDGET < render
                    # Toolbar is embedded in main widget (no separate Toplevel)
                    try:
                        self._pen_overlay.lift_input()      # Input at bottom
                        self.attributes('-topmost', True)
                        self.lift()                          # Main widget above input
                        self._pen_overlay.lift_render()      # Render above main
                    except tk.TclError:
                        pass
                else:
                    self.attributes('-topmost', True)
                    self.lift()

            self.after(1500, self.monitor_topmost)
        except Exception:
            try:
                self.after(1500, self.monitor_topmost)
            except tk.TclError:
                pass
    
    def _handle_fullscreen_result(self, is_fullscreen):
        """Handle fullscreen detection result on main thread.
        When pen mode is active, NEVER hide - pen should work over fullscreen apps.
        When editor is open, don't restore main widget (it's deliberately hidden)."""
        try:
            # Pen mode overrides fullscreen auto-hide
            pen_active = hasattr(self, '_pen_overlay') and self._pen_overlay is not None

            # If editor is open, don't deiconify main widget
            editor_open = (hasattr(self, '_editor_win') and self._editor_win
                           and self._editor_win.winfo_exists()
                           and self._editor_win.winfo_viewable())

            if is_fullscreen and not pen_active:
                if not self._hidden_for_fullscreen:
                    self._hidden_for_fullscreen = True
                    if not editor_open:
                        self.withdraw()
                    print("[FULLSCREEN] Widget hidden")
            else:
                if self._hidden_for_fullscreen:
                    self._hidden_for_fullscreen = False
                    if not editor_open:
                        self.deiconify()
                        self.attributes('-topmost', True)
                        self.lift()
                    print("[FULLSCREEN] Widget shown")
        except tk.TclError:
            pass

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
                    audio_data, lang = self.audio_queue.get(timeout=0.2)
                except queue.Empty:
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
                        try:
                            recognition_result[0] = self.recognizer.recognize_google(audio_data, language=lang)
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
                        
                        # Clean text
                        lower_txt = txt.lower().strip()
                        
                        # --- VOICE COMMANDS ---
                        if lower_txt in ["backspace", "ব্যাকস্পেস", "ব্যাক স্পেস"]:
                            pyautogui.press('backspace')
                        elif lower_txt in ["back sentence", "ব্যাক সেন্টেন্স", "ব্যাক সেন টেন্স"]:
                            pyautogui.hotkey('ctrl', 'z')
                        elif lower_txt in ["select all", "সিলেক্ট অল", "সিলেক্ট করি", "সব সিলেক্ট"]:
                            pyautogui.hotkey('ctrl', 'a')
                        elif lower_txt in ["copy", "কপি", "কপি করি"]:
                            pyautogui.hotkey('ctrl', 'c')
                        elif lower_txt in ["paste", "পেস্ট", "পেস্ট করি"]:
                            try:
                                content = pyperclip.paste()
                                pyperclip.copy(content)
                                time.sleep(0.01) 
                                pyautogui.hotkey('ctrl', 'v')
                            except Exception: pass
                        else:
                            # Normal Typing
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
    
    def check_for_update(self):
        """Check for software updates from GitHub"""
        try:
            # Disable button during check
            self.btn_check_update.configure(state="disabled", text="⏳ Checking...")
            self.update_status_label.configure(text="Connecting to update server...", text_color="#f39c12")
            
            # Create update checker
            checker = UpdateChecker(APP_VERSION, UPDATE_REPO_URL)
            
            # Check for updates in background
            def check_thread():
                result = checker.check_for_updates()
                self.after(0, lambda: self.handle_update_check_result(result))
            
            threading.Thread(target=check_thread, daemon=True).start()
            
        except Exception as e:
            print(f"[ERROR] Update check failed: {e}")
            self.btn_check_update.configure(state="normal", text="🔄 Check for Update")
            self.update_status_label.configure(
                text=f"Update check failed: {str(e)}", 
                text_color="#e74c3c"
            )
    
    def handle_update_check_result(self, result):
        """Handle the result of update check"""
        try:
            if result.get("available"):
                # New version available
                new_version = result.get("version")
                release_notes = result.get("release_notes", "New update available")
                download_url = result.get("download_url")
                
                self.update_status_label.configure(
                    text=f"🎉 New version {new_version} available!", 
                    text_color="#27ae60"
                )
                
                # Change button to download
                self.btn_check_update.configure(
                    state="normal",
                    text=f"⬇ Download Version {new_version}",
                    fg_color="#27ae60",
                    hover_color="#229954",
                    command=lambda: self.download_update(download_url, new_version)
                )
                
                # Show release notes
                messagebox.showinfo(
                    "Update Available",
                    f"New version {new_version} is available!\n\n"
                    f"Release Notes:\n{release_notes}\n\n"
                    f"Click 'Download Version {new_version}' button to update."
                )
                
            elif result.get("error"):
                # Error occurred
                self.update_status_label.configure(
                    text=result.get("message", "Update check failed"), 
                    text_color="#e74c3c"
                )
                self.btn_check_update.configure(state="normal", text="🔄 Check for Update")
                
            else:
                # Already latest version
                self.update_status_label.configure(
                    text="✅ You are using the latest version", 
                    text_color="#27ae60"
                )
                self.btn_check_update.configure(state="normal", text="🔄 Check for Update")
                
        except Exception as e:
            print(f"[ERROR] Update result handling failed: {e}")
            self.btn_check_update.configure(state="normal", text="🔄 Check for Update")
    
    def download_update(self, download_url, version):
        """Download the update installer"""
        try:
            # Disable button and show progress
            self.btn_check_update.configure(state="disabled", text="⬇ Downloading...")
            self.update_status_label.configure(text="Downloading update...", text_color="#3498db")
            self.update_progress.pack(fill="x", pady=(0, 5))  # Show progress bar
            self.update_progress.set(0)
            
            # Create downloader with progress callback
            downloader = UpdateDownloader(
                download_url,
                progress_callback=self.on_download_progress
            )
            
            # Download in background
            downloader.download_async(
                completion_callback=lambda path: self.on_download_complete(path, version)
            )
            
        except Exception as e:
            print(f"[ERROR] Download initiation failed: {e}")
            self.update_status_label.configure(
                text=f"Download failed: {str(e)}", 
                text_color="#e74c3c"
            )
            self.btn_check_update.configure(state="normal", text="🔄 Check for Update")
            self.update_progress.pack_forget()
    
    def on_download_progress(self, progress, downloaded, total):
        """Update progress bar during download"""
        try:
            self.update_progress.set(progress / 100.0)
            status_text = f"Downloading: {format_size(downloaded)} / {format_size(total)} ({progress:.1f}%)"
            self.update_status_label.configure(text=status_text, text_color="#3498db")
        except Exception as e:
            print(f"[ERROR] Progress update failed: {e}")
    
    def on_download_complete(self, installer_path, version):
        """Handle download completion"""
        try:
            if installer_path and os.path.exists(installer_path):
                # Download successful
                self.update_status_label.configure(
                    text=f"✅ Download complete! Ready to install v{version}", 
                    text_color="#27ae60"
                )
                self.update_progress.set(1.0)
                
                # Change button to install
                self.btn_check_update.configure(
                    state="normal",
                    text=f"🚀 Install Version {version}",
                    fg_color="#9b59b6",
                    hover_color="#8e44ad",
                    command=lambda: self.install_update(installer_path)
                )
                
                # Ask user if they want to install now
                response = messagebox.askyesno(
                    "Download Complete",
                    f"Version {version} has been downloaded successfully!\n\n"
                    f"Do you want to install it now?\n\n"
                    f"The application will close and the installer will run."
                )
                
                if response:
                    self.install_update(installer_path)
                    
            else:
                # Download failed
                self.update_status_label.configure(
                    text="❌ Download failed. Please try again.", 
                    text_color="#e74c3c"
                )
                self.btn_check_update.configure(state="normal", text="🔄 Check for Update")
                self.update_progress.pack_forget()
                
        except Exception as e:
            print(f"[ERROR] Download completion handling failed: {e}")
            self.update_status_label.configure(
                text=f"Error: {str(e)}", 
                text_color="#e74c3c"
            )
            self.btn_check_update.configure(state="normal", text="🔄 Check for Update")
    
    def install_update(self, installer_path):
        """Install the downloaded update"""
        try:
            # Confirm installation
            response = messagebox.askyesno(
                "Install Update",
                "The application will close and the installer will run.\n\n"
                "Do you want to continue?"
            )
            
            if response:
                self.update_status_label.configure(
                    text="🚀 Launching installer...", 
                    text_color="#9b59b6"
                )
                
                # Run installer and close app
                UpdateInstaller.install_update(installer_path, close_current_app=True)
                
        except Exception as e:
            print(f"[ERROR] Installation failed: {e}")
            messagebox.showerror(
                "Installation Error",
                f"Failed to launch installer:\n{str(e)}\n\n"
                f"Please run the installer manually from:\n{installer_path}"
            )


if __name__ == "__main__":
    app = VoiceTypingApp()
    
    # Cleanup handler - Remove lock file + unregister fonts on exit
    def cleanup():
        try:
            if hasattr(app, 'lock_file') and os.path.exists(app.lock_file):
                os.remove(app.lock_file)
                print("[INFO] Lock file removed")
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
