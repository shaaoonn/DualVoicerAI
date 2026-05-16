# config.py
import os, sys
from dotenv import load_dotenv

# When frozen by PyInstaller (--onefile), the bundled .env lives inside
# sys._MEIPASS (the temp extraction folder), NOT the current working
# directory. Without this, load_dotenv() silently finds nothing and
# OPENROUTER_API_KEY ends up empty → every AI call fails with 401.
if getattr(sys, 'frozen', False):
    _bundle_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    load_dotenv(os.path.join(_bundle_dir, '.env'))
else:
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
AI_TIMEOUT, AI_MAX_TOKENS = 45, 2048

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

# ════════════════════════════════════════════════════════
# Editable keyboard shortcuts (user can override in Settings → Shortcuts)
# Action IDs are stable; the values are pre-set defaults the user can edit.
# ════════════════════════════════════════════════════════
DEFAULT_KEYBOARD_SHORTCUTS = {
    # Main app (global hotkeys via `keyboard` library)
    "ai_assistant":      "ctrl+shift+a",
    "smart_paste":       "ctrl+shift+v",
    "voice_btn1":        "ctrl+shift+b",
    "voice_btn2":        "ctrl+shift+e",
    "take_screenshot":   "ctrl+shift+s",
    # Tool switching — Ctrl+Alt+letter combos.
    #
    # WHY NOT plain Alt+letter? The Windows low-level keyboard hook used by
    # the `keyboard` library cannot reliably suppress Alt+letter combos
    # without admin privileges — the trigger letter often leaks through to
    # whatever app is focused (e.g. Alt+P leaks "p" into Notepad). Adding
    # Ctrl as a second modifier avoids menu-bar activation entirely and
    # makes suppression reliable.
    "tool_select":       "ctrl+alt+v",   # ⤢ cursor / move objects
    "tool_pen":          "ctrl+alt+p",
    "tool_highlighter":  "ctrl+alt+h",
    "tool_eraser":       "ctrl+alt+e",
    "tool_text":         "ctrl+alt+t",
    "tool_handwrite":    "ctrl+alt+w",
    "tool_arrow":        "ctrl+alt+a",   # ➤ draw arrow SHAPE (≠ select)
    "clear_all":         "ctrl+shift+delete",   # 🗑 wipe canvas / overlay
    # Editor — actions
    "editor_undo":       "ctrl+z",
    "editor_redo":       "ctrl+y",
    "editor_save":       "ctrl+s",
    "editor_screenshot": "ctrl+shift+c",
    "editor_close":      "escape",
    # Bengali Phonetic Input toggle (Avro-style)
    "bengali_input_toggle": "f12",
}

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
    # Editable keyboard shortcuts (action_id -> hotkey string).
    # Defaults pulled from DEFAULT_KEYBOARD_SHORTCUTS above.
    "keyboard_shortcuts": dict(DEFAULT_KEYBOARD_SHORTCUTS),
    # Per-shortcut enable/disable toggles (action_id -> bool).
    # When False, the shortcut is NOT bound (editor) or NOT registered
    # (main app). All default to True.
    "keyboard_shortcuts_enabled": {k: True for k in DEFAULT_KEYBOARD_SHORTCUTS},
    # ── Voice AI Mode (per button) ───────────────────────────────────
    # When enabled per button, voice typing transcribes in the
    # "translate_from" language then runs the result through Gemini
    # before typing. If translate_from == button_lang → AI just cleans
    # up the text (removes duplicates, fixes errors, adds punctuation).
    # If translate_from != button_lang → AI translates AND cleans up.
    #
    # Old `translation_mode` master toggle is auto-migrated to per-button
    # enables in main.py at startup.
    "btn1_translate_enabled": False,
    "btn2_translate_enabled": False,
    "btn1_translate_from": "en-US",
    "btn2_translate_from": "bn-BD",
    # ── User-facing voice mode picker (drives the dropdown arrows
    # below the BN/EN buttons). Values: "normal" | "ai_translate" |
    # "ai_polish". The boolean keys above are kept in sync as derived
    # state so existing _refresh_translation_state() keeps working.
    "btn1_voice_mode": "normal",
    "btn2_voice_mode": "normal",
    # ── TTS source mode (drives the dropdown under the SND button).
    # Values: "auto" | "btn1" | "btn2". When non-auto, tts_auto_detect
    # is set False and tts_voice is set from the chosen button's lang.
    "tts_source_mode": "auto",
    # ── AI chat popup (under the AI button arrow) — restores last
    # prompt the user typed so they can iterate on a request.
    "ai_popup_last_prompt": "",
    # ── Bengali Phonetic Input (Avro-style, built-in) ────────────────
    # When True: typing Latin characters in any Windows app produces
    # Bengali (e.g. "ami" → "আমি"). Toggle via F12 (configurable).
    "bengali_input_enabled": False,
}
