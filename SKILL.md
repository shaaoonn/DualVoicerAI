---
name: ai-voice-product
description: Build the new AI-powered voice typing desktop app for EJOSB IT in 3 phases. Use this skill for: নতুন AI ভয়েস অ্যাপ, spectrum button, Smart Paste, Ctrl+Shift+V, multi-language voice, Google login, freemium gate, knowledge base, auto TTS, DEV_MODE. Always read this master file first, then the relevant phase reference.
---

# AI Voice Product — Phased Build Plan
**EJOSB IT | Successor to Dual Voicer v4.0.8**
**github.com/shaaoonn/dualvoicer-web (base code)**

---

## 🛑 RULES FOR CLAUDE CODE (Read Every Session)

```
1. RESEARCH FIRST — Search PyPI/official docs before implementing. No assumptions.
2. UPDATE PROGRESS — After each task, mark ✅ in the table below.
3. ONE TASK AT A TIME — Complete + test before moving on.
4. SKILL.md = GROUND TRUTH — Discover better approach? Update SKILL.md first.
5. NO HALLUCINATION — Unsure about an API? Run: pip show <pkg> or search web.
6. DEV_MODE — Phase 1 runs with DEV_MODE=True. Never remove this flag from code.
```

---

## 🗺️ 3-PHASE OVERVIEW

```
PHASE 1: Desktop App (4–5 days)
  → Software সম্পূর্ণ করা, DEV_MODE=True দিয়ে auth bypass
  → সব features কাজ করবে, কোনো backend দরকার নেই
  → শেষে: working .exe তৈরি

PHASE 2: Backend + Website (3–4 days, Phase 1 শেষে)
  → নতুন Flask backend + Firebase project
  → নতুন website (ejobsit.com/ai-voice বা নতুন domain)
  → Payment integration (bKash)

PHASE 3: Auth Connect (1–2 days, Phase 2 শেষে)
  → DEV_MODE=False করা
  → App-এ Google login + Phone OTP চালু করা
  → Production build + deployment
```

---

## 📊 PHASE 1 PROGRESS (Current Phase)

| # | Task | Status | Reference | Notes |
|---|------|--------|-----------|-------|
| P1-0 | Fork + config.py (DEV_MODE=True) | ✅ | §Setup below | Done: cloned, config.py, .gitignore, folders |
| P1-1 | Spectrum Button (replace PNGs) | ✅ | ref/04_modules.md §1 | Canvas buttons, no PNGs needed |
| P1-2 | AI Engine (openrouter + 3-mode) | ✅ | ref/04_modules.md §2 | 4 files in ai_engine/ |
| P1-3 | AI Hotkey Ctrl+Shift+A | ✅ | ref/04_modules.md §3 | ai_trigger_flow + hotkeys |
| P1-4 | Multi-Language STT (55+ langs) | ✅ | ref/04_modules.md §4 | language_data.py + active_lang |
| P1-5 | Auto-Detect TTS (fast-langdetect) | ✅ | ref/04_modules.md §5 | tts_detector.py + stream_audio |
| P1-6 | Smart Paste Ctrl+Shift+V | ✅ | ref/04_modules.md §6 | smart_paste_flow() added |
| P1-7 | Freemium Gate (DEV_MODE bypass) | ✅ | ref/04_modules.md §7 | freemium.py + _show_lock_popup |
| P1-8 | Settings Panel (860×700) | ✅ | ref/02_ui_panel.md | 6-tab sidebar panel |
| P1-9 | Full test + .exe build | ✅ | ref/05_testing.md | 19 imports OK, VoiceAIPro.exe (63MB) built |

## 📊 PHASE 2 PROGRESS (After Phase 1)

| # | Task | Status | Reference | Notes |
|---|------|--------|-----------|-------|
| P2-0 | New Firebase project setup | ⬜ | ref/06_backend.md §setup | |
| P2-1 | Flask backend (new domain) | ⬜ | ref/06_backend.md §flask | |
| P2-2 | Google OAuth backend endpoint | ⬜ | ref/03_auth_system.md | |
| P2-3 | Phone OTP backend endpoint | ⬜ | ref/03_auth_system.md | |
| P2-4 | bKash payment integration | ⬜ | ref/06_backend.md §payment | Copy from old app.py |
| P2-5 | New website (landing page) | ⬜ | ref/06_backend.md §website | |
| P2-6 | Coolify VPS deployment | ⬜ | ref/06_backend.md §deploy | |

## 📊 PHASE 3 PROGRESS (After Phase 2)

| # | Task | Status | Reference | Notes |
|---|------|--------|-----------|-------|
| P3-0 | Set DEV_MODE=False in config.py | ⬜ | §DEV_MODE below | 1 line change |
| P3-1 | Login window (Google + OTP UI) | ⬜ | ref/03_auth_system.md §ui | |
| P3-2 | Connect app → backend endpoints | ⬜ | ref/03_auth_system.md | |
| P3-3 | Freemium backend sync | ⬜ | ref/04_modules.md §7 | |
| P3-4 | Full integration test | ⬜ | ref/05_testing.md §phase3 | |
| P3-5 | Production .exe build + release | ⬜ | ref/05_testing.md §build | |

---

## ⚙️ SETUP: config.py (Complete — Start Here)

```python
# config.py
import os
from dotenv import load_dotenv
load_dotenv()

# ════════════════════════════════════════════════════════
# DEV_MODE: Phase 1 = True (no auth needed)
#           Phase 3 = False (auth enabled)
# ════════════════════════════════════════════════════════
DEV_MODE = True   # ← ONLY change this in Phase 3

# Identity
APP_NAME        = "VoiceAI Pro"        # CHANGE TO FINAL NAME
APP_VERSION     = "1.0.0"
HWID_PREFIX     = "VAIPRO"
APPDATA_FOLDER  = "VoiceAIPro"
LOCK_FILE_NAME  = "voice_ai_pro.lock"

# AI (Phase 1 — needs real key in .env)
OPENROUTER_API_KEY  = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
AI_MODELS = {
    "primary":  "google/gemini-2.5-flash-lite",
    "fallback": "openai/gpt-4o-mini",
    "economy":  "anthropic/claude-haiku-4-5",
}
AI_TIMEOUT, AI_MAX_TOKENS = 20, 2048

# Backend (Phase 2+ only — leave blank in Phase 1)
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
    "ai_system_prompt": "তুমি একজন দক্ষ বাংলা ও ইংরেজি লেখক সহকারী।",
    "ai_model": "google/gemini-2.5-flash-lite",
    "knowledge_base": "",
    "tts_auto_detect": True,
    "tts_voice": "",
    "show_trial_banner": True,
}
```

---

## 🔑 DEV_MODE — How It Works

```python
# In main.py __init__ — add these lines:
from config import DEV_MODE

if DEV_MODE:
    # Simulate logged-in premium user — no backend needed
    self.is_authenticated = True
    self.user_email       = "dev@ejobsit.com"
    self.device_count     = 1
    self.max_devices      = 10
    self.user_cache       = {
        "plan_type": "Pro (Dev Mode)",
        "expiry_date": "2099-12-31",
    }
    print("[DEV_MODE] Auth bypassed — all features unlocked")
```

```python
# In freemium.py — bypass check:
def can_use(self, feature, app_instance):
    from config import DEV_MODE
    if DEV_MODE:
        return True   # ← everything allowed in dev mode
    # ... rest of freemium logic
```

```python
# In setup_hotkeys() — skip auth check:
def ai_trigger_flow(self):
    from config import DEV_MODE
    if not DEV_MODE and not self.is_authenticated:
        self.after(0, self.open_auth_panel)
        return
    # ... rest of AI flow
```

**Phase 3 করতে:** শুধু `config.py`-এ `DEV_MODE = False` করুন। Auth gate সব জায়গায় automatically চালু হবে।

---

## 📁 File Structure

```
ai-voice-product/
├── SKILL.md               ← Master (you are here)
├── references/
│   ├── 02_ui_panel.md     ← Settings panel spec (860×700)
│   ├── 03_auth_system.md  ← Google OAuth + Phone OTP (Phase 3)
│   ├── 04_modules.md      ← P1-1 to P1-8 implementation
│   ├── 05_testing.md      ← Test checklists + build
│   └── 06_backend.md      ← Phase 2: Flask + Firebase + Website
│
├── main.py                ← Fork of desktop/main.py
├── config.py              ← ← ← START HERE
├── updater.py             ← Unchanged
├── version.json
├── .env                   ← OPENROUTER_API_KEY=sk-...
├── .env.example
│
├── ai_engine/             ← Phase 1 (P1-2,3)
│   ├── openrouter.py
│   ├── text_processor.py
│   ├── format_handler.py
│   ├── clipboard_guard.py
│   └── tts_detector.py    ← Phase 1 (P1-5)
│
├── ui_components/         ← Phase 1
│   ├── spectrum_button.py ← P1-1
│   └── language_data.py   ← P1-4
│
├── ui/
│   └── settings_panel.py  ← P1-8 (large window)
│
└── subscription/
    ├── freemium.py        ← P1-7 (DEV_MODE aware)
    └── auth_new.py        ← Phase 3 only
```

---

## 🚀 Claude Code — Session Start

```
"SKILL.md পড়ো।
 বর্তমান Phase কোনটা? (Phase 1)
 পরবর্তী ⬜ Pending task কোনটা?
 সেটার reference file পড়ো।
 Implement করো। Test করো। Progress update করো।"
```

---

## 📦 requirements.txt

```
# Phase 1 (required now)
customtkinter>=5.2.2
pygame>=2.5.0
edge-tts>=7.2.8
pyautogui>=0.9.54
pyperclip>=1.8.2
keyboard>=0.13.5
SpeechRecognition>=3.10.0
pystray>=0.19.5
Pillow>=10.0.0
requests>=2.31.0
psutil>=5.9.0
pyinstaller>=6.0.0
aiohttp>=3.9.0
python-dotenv>=1.0.0
fast-langdetect>=1.0.0

# Phase 3 (add when needed)
# google-auth-oauthlib>=1.2.0
```
