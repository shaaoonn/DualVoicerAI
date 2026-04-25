# config.py
import os
from dotenv import load_dotenv
load_dotenv()

# ════════════════════════════════════════════════════════
# DEV_MODE: Phase 1 = True (no auth needed)
#           Phase 3 = False (auth enabled)
# ════════════════════════════════════════════════════════
DEV_MODE = True   # <- ONLY change this in Phase 3

# Identity
APP_NAME        = "VoiceAI Pro"        # CHANGE TO FINAL NAME
APP_VERSION     = "1.0.0"
HWID_PREFIX     = "VAIPRO"
APPDATA_FOLDER  = "VoiceAIPro"
LOCK_FILE_NAME  = "voice_ai_pro.lock"

# AI (Phase 1 -- needs real key in .env)
OPENROUTER_API_KEY  = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
AI_MODELS = {
    "primary":  "google/gemini-2.5-flash-lite",
    "fallback": "openai/gpt-4o-mini",
    "economy":  "anthropic/claude-haiku-4-5",
}
AI_TIMEOUT, AI_MAX_TOKENS = 20, 2048

# Backend (Phase 2+ only -- leave blank in Phase 1)
BACKEND_BASE        = os.getenv("BACKEND_URL", "https://placeholder.ejobsit.com")
API_GOOGLE_AUTH_URL = f"{BACKEND_BASE}/api/v2/google-auth"
API_SEND_OTP_URL    = f"{BACKEND_BASE}/api/v2/send-otp"
API_VERIFY_OTP_URL  = f"{BACKEND_BASE}/api/v2/verify-otp"
UPDATE_REPO_URL     = "https://raw.githubusercontent.com/shaaoonn/[DIST-REPO]/main"
GOOGLE_CLIENT_ID    = os.getenv("GOOGLE_CLIENT_ID", "")

# Hotkeys
AI_HOTKEY           = "ctrl+shift+a"
SMART_PASTE_HOTKEY  = "ctrl+shift+v"
DEFAULT_BTN1_HOTKEY = "ctrl+shift+b"
DEFAULT_BTN2_HOTKEY = "ctrl+shift+e"

# UI
SPECTRUM_BTN_SIZE    = 76
SPECTRUM_COLORS = {
    "idle_bar": "#3A3A3A",   "idle_ring": "#4A4A4A",
    "listening_ring": "#A0A0A0", "listening_bar": "#C0C0C0",
    "ai_ring": "#4A6A8A",    "ai_bar": "#6C9EBF",
    "bg": "#111111",
}
SETTINGS_WINDOW_SIZE = "860x700"
SETTINGS_MIN_SIZE    = (720, 580)

# Freemium
TRIAL_HOURS = 24

# New settings keys to add to DEFAULT_SETTINGS in main.py
NEW_SETTINGS_KEYS = {
    "btn1_lang": "bn-BD",   "btn2_lang": "en-US",
    "btn1_hotkey": "ctrl+shift+b",
    "btn2_hotkey": "ctrl+shift+e",
    "ai_enabled": True,
    "ai_output_format": "plain",
    "ai_system_prompt": "\u09a4\u09c1\u09ae\u09bf \u098f\u0995\u099c\u09a8 \u09a6\u0995\u09cd\u09b7 \u09ac\u09be\u0982\u09b2\u09be \u0993 \u0987\u0982\u09b0\u09c7\u099c\u09bf \u09b2\u09c7\u0996\u0995 \u09b8\u09b9\u0995\u09be\u09b0\u09c0\u0964",
    "image_system_prompt": "",
    "ai_model": "google/gemini-2.5-flash-lite",
    "knowledge_base": "",
    "tts_auto_detect": True,
    "tts_voice": "",
    "show_trial_banner": True,
    "size_preset": "medium",
    "screenshot_save_dir": "",
    "ui_language": "en",   # 'en' (default) or 'bn'
    # Keyboard-shortcut overlay (Show Keyboard Shortcut)
    "show_keyboard_shortcuts": False,
    "kb_overlay_font_size":    18,
    "kb_overlay_font_color":   "#FFFFFF",
}
