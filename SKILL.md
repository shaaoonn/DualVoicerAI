---
name: ai-voice-product
description: Build the new AI-powered voice typing desktop app for EJOSB IT in 3 phases. Use this skill for: নতুন AI ভয়েস অ্যাপ, spectrum button, Smart Paste, Ctrl+Shift+V, multi-language voice, Google login, freemium gate, knowledge base, auto TTS, DEV_MODE, pen overlay, handwriting recognition, editor window, auto-update. Always read this master file first, then the relevant phase reference.
---

# AI Voice Product - Phased Build Plan
**EJOSB IT | Successor to Dual Voicer v4.0.8**
**github.com/shaaoonn/DualVoicerAI (base code)**

---

## 🛑 RULES FOR CLAUDE CODE (Read Every Session)

```
1. RESEARCH FIRST - Search PyPI/official docs before implementing. No assumptions.
2. UPDATE PROGRESS - After each task, mark ✅ in the table below.
3. ONE TASK AT A TIME - Complete + test before moving on.
4. SKILL.md = GROUND TRUTH - Discover better approach? Update SKILL.md first.
5. NO HALLUCINATION - Unsure about an API? Run: pip show <pkg> or search web.
6. DEV_MODE - Phase 1 runs with DEV_MODE=True. Never remove this flag from code.
```

---

## 🗺️ 3-PHASE OVERVIEW

```
PHASE 1: Desktop App (4-5 days) ✅ COMPLETE
  → Software সম্পূর্ণ করা, DEV_MODE=True দিয়ে auth bypass
  → সব features কাজ করবে, কোনো backend দরকার নেই
  → শেষে: working .exe তৈরি

PHASE 2: Backend + Website (3-4 days, Phase 1 শেষে)
  → নতুন Flask backend + Firebase project
  → নতুন website (ejobsit.com/ai-voice বা নতুন domain)
  → Payment integration (bKash)

PHASE 3: Auth Connect (1-2 days, Phase 2 শেষে)
  → DEV_MODE=False করা
  → App-এ Google login + Phone OTP চালু করা
  → Production build + deployment
```

---

## 📊 PHASE 1 PROGRESS (✅ COMPLETE)

| # | Task | Status | Reference | Notes |
|---|------|--------|-----------|-------|
| P1-0 | Fork + config.py (DEV_MODE=True) | ✅ | §Setup below | Done: cloned, config.py, .gitignore, folders |
| P1-1 | Spectrum Button (replace PNGs) | ✅ | ref/04_modules.md §1 | Canvas buttons, PIL rendered, glossy 3D, rainbow ring AI, metallic ring others |
| P1-2 | AI Engine (openrouter + 3-mode) | ✅ | ref/04_modules.md §2 | 4 files in ai_engine/ (openrouter, text_processor, screenshot_analyzer, tts_detector) |
| P1-3 | AI Hotkey Ctrl+Shift+A | ✅ | ref/04_modules.md §3 | ai_trigger_flow + text/screenshot dual mode |
| P1-4 | Multi-Language STT (55+ langs) | ✅ | ref/04_modules.md §4 | language_data.py + active_lang + configurable hotkeys |
| P1-5 | Auto-Detect TTS (fast-langdetect) | ✅ | ref/04_modules.md §5 | tts_detector.py + smart streaming TTS (40+ voices) |
| P1-6 | Smart Paste Ctrl+Shift+V | ✅ | ref/04_modules.md §6 | smart_paste_flow() + knowledge base + rich/plain output |
| P1-7 | Freemium Gate (DEV_MODE bypass) | ✅ | ref/04_modules.md §7 | freemium.py + _show_lock_popup (24h trial) |
| P1-8 | Settings Panel (860×700) | ✅ | ref/02_ui_panel.md | 6-tab sidebar panel with all settings |
| P1-9 | Smart Punctuation | ✅ | - | Voice-triggered punctuation (BN: দাড়ি, কমা, নতুন লাইন etc. / EN: period, comma, newline etc.) |
| P1-10 | Voice Commands | ✅ | - | backspace, ব্যাকস্পেস, back sentence, select all, copy, paste |
| P1-11 | Pen Overlay (Screen Annotation) | ✅ | - | Two-window technique, transparent canvas, custom pen cursor |
| P1-12 | Drawing Engine | ✅ | - | Freehand pen, highlighter, eraser, text tool, shape detection, Catmull-Rom smoothing, undo/redo |
| P1-13 | Handwriting Recognition | ✅ | - | Google Input Tools API, batch-based, 15+ language fonts |
| P1-14 | Font Manager (30+ fonts) | ✅ | - | Per-process Win32 font registration, language-to-font mapping |
| P1-15 | Pen Toolbar | ✅ | - | Tool buttons, color picker, thickness slider, font dropdown, zoom slider |
| P1-16 | Built-in Editor Window | ✅ | - | Multi-page, PDF/image open+import, export PDF/PNG/JPG, .dvai format, auto-save session |
| P1-17 | Selection Manager | ✅ | - | Click-select, rubber-band, drag-move, corner-handle resize, image resize |
| P1-18 | Screenshot + AI Vision | ✅ | - | Win+Shift+S capture, clipboard poll, 10s AI glow, save to folder |
| P1-19 | Auto-Update System | ✅ | - | Background checker (30s→6h), download to ~/Downloads, installer launch |
| P1-20 | Clipboard Guard | ✅ | - | Save/restore clipboard during AI operations |
| P1-21 | Format Handler (Rich Paste) | ✅ | - | Markdown→HTML clipboard (CF_HTML), professional CSS, strip_markdown fallback |
| P1-22 | Remote Config | ✅ | - | GitHub-hosted config with disk/memory cache (1h TTL), fallback defaults |
| P1-23 | Smart Streaming TTS | ✅ | - | Sentence chunking, session-aware producer/consumer, retry logic (3 attempts) |
| P1-24 | Noise Filter & Engine Refresh | ✅ | - | Manual threshold slider (50-500), auto-refresh every 15 recognitions |
| P1-25 | Fullscreen Detection | ✅ | - | Auto-hide widget during fullscreen apps, pen mode overrides auto-hide |
| P1-26 | Web-First Auth UI | ✅ | - | Login panel (email+phone), trial signup with HWID, subscription link |
| P1-27 | Auth Security System | ✅ | - | API-based login, HWID verification, periodic re-verification (24h), expiry check, auto-login |
| P1-28 | Full test + .exe build | ✅ | ref/05_testing.md | v4.0.8 working, all imports OK |

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

## 📦 FEATURE DETAIL: Phase 1 Implemented Features

### 🎙 Core Voice Typing
- **Dual-language support:** BN (বাংলা) + EN (English) toggle buttons
- **55+ STT languages** via Google Web Speech API (`language_data.py`)
- **Configurable hotkeys:** Alt+Z (BN), Alt+X (EN), customizable in settings
- **Auto-stop timer:** 5-90 seconds or ∞ (infinite)
- **Mic sensitivity:** Normal / High / Very High
- **Noise Filter slider:** Manual threshold 50-500 (no auto-calibration for speed)
- **Auto-refresh engine:** Recognizer refresh every 15 recognitions to prevent drift
- **Queue management:** Max 3 chunks to prevent buildup
- **Watchdog:** Automatic restart on mic failure

### ✨ AI Features
- **AI Trigger (Ctrl+Shift+A):** Select text → AI processes and replaces
- **Dual-mode AI:**
  - Text mode: Selected text → OpenRouter API → formatted response
  - Screenshot mode: Recent screenshot → AI vision analysis → paste result
- **Smart Paste (Ctrl+Shift+V):** Clipboard text + knowledge base → AI reply
- **Rich output:** Markdown→HTML clipboard (CF_HTML) with professional CSS, or plain text
- **AI Models:** Primary (gemini-2.5-flash-lite), Fallback (gpt-4o-mini), Economy (claude-haiku)
- **Error handling:** Rate limit, timeout, invalid API key messages

### 📸 Screenshot & Vision
- **Win+Shift+S** triggers Windows Snipping Tool
- **Clipboard polling** for up to 15 seconds
- **AI button glow** for 10 seconds when screenshot ready
- **Auto-save** to configured directory
- **Pen mode integration:** Temporarily pauses drawing for snip capture

### 🔊 Text-to-Speech (Smart Streaming TTS)
- **Edge-TTS** with 40+ language voices
- **Auto-detect language** via `fast-langdetect`
- **Smart chunking:** Sentences split at `.?!;:\n।`, merged into <300 char chunks
- **Session management:** Prevents old/new TTS conflicts
- **Retry logic:** 3 attempts per chunk with exponential backoff
- **Pause/Resume:** Click to toggle, long press to stop
- **Speed control:** 1.0x, 1.5x, 2.0x, 2.5x
- **SFX channel separation:** Start/end sounds don't interrupt TTS

### 🎤 Smart Punctuation
- **Voice-triggered punctuation** for both Bangla and English
- **Bangla:** দাড়ি (।), কমা (,), প্রশ্নবোধক (?), বিস্ময়বোধক (!), নতুন লাইন (\\n)
- **English:** period, comma, question mark, exclamation, newline
- **Smart spacing:** Auto-removes space before punctuation
- **In-text processing:** Multi-word triggers (longest-first matching)

### 🗣️ Voice Commands
- **Backspace / ব্যাকস্পেস** → pyautogui backspace
- **Back sentence / ব্যাক সেন্টেন্স** → Ctrl+Z
- **Select all / সিলেক্ট অল** → Ctrl+A
- **Copy / কপি** → Ctrl+C
- **Paste / পেস্ট** → Ctrl+V

### ✏️ Pen Overlay (Screen Annotation)
- **Two-window technique:**
  - `render_win`: Transparent background, click-through, shows strokes
  - `input_win`: Nearly invisible (alpha=1/255), captures mouse events
- **Z-order management:** `input < MAIN WIDGET < render < toolbar`
- **Custom pen cursor** (.cur file with hotspot at tip)
- **Draw/View mode toggle:** Active tool ↔ click-through
- **Pen mode stays above fullscreen apps**

### 🎨 Drawing Engine (`drawing_engine.py`)
- **Tools:** Freehand pen, highlighter (50% stipple), eraser, text tool, handwrite mode
- **Catmull-Rom smoothing** with RDP simplification
- **EMA mouse smoothing** (α=0.35)
- **Shape detection:** Hold 3s → auto-snap to circle, rectangle, or straight line
- **Text tool features:**
  - Click-to-place, multiline (Enter), cursor positioning
  - Click-to-edit existing text (OneNote-like)
  - Text selection (drag-select), Shift+selection
  - IME support (Bengali, CJK) with debounce deduplication
  - Auto-wrap to canvas edge
  - Inject text from voice typing
- **Undo/Redo:** Full stroke-level undo/redo stack

### ✍️ Handwriting Recognition
- **Google Input Tools API** (unofficial handwriting endpoint)
- **Batch-based:** Accumulates strokes, fires after debounce (700ms BN / 500ms EN)
- **Pre-context:** Last 20 chars for word boundary detection
- **Ink strokes replace with recognized text** at handwriting position
- **Appending mode:** Same-line writing appends to existing text
- **15+ languages** with dedicated handwriting fonts

### 🖋️ Font Manager (`font_manager.py`)
- **30+ bundled TTF fonts** in `desktop/fonts/`
- **Per-process registration** via Win32 `AddFontResourceExW`
- **Language-to-font mapping:** Bengali, Hindi, Arabic, Urdu, Chinese, Japanese, Korean, Thai, etc.
- **Handwriting-style fonts:** Playpen Sans (Latin), Dekko (Devanagari), Ma Shan Zheng (Chinese), Klee One (Japanese), etc.

### 🔧 Pen Toolbar (`pen_toolbar.py`)
- **Tool buttons:** Pen, Highlighter, Eraser, Text (T), Handwrite (✍️)
- **6 color picker** with active indicator
- **Thickness/Font-size slider** (1-100px, auto-switches between pen/font mode)
- **Font dropdown:** 8 popular + all system fonts
- **Action buttons:** Undo, Redo, Clear
- **Editor button** (opens editor window from overlay)
- **Draw/View mode toggle** (tool icon ↔ mouse icon)
- **Draggable** toolbar

### 📄 Built-in Editor Window (`editor_window.py`)
- **Multi-page editor** with scrollable canvas
- **Page presets:** A4, Legal, HD 16:9, 4K, Book 6×9, Square
- **File operations:**
  - Open images (PNG/JPG/BMP/GIF/TIFF/WebP) and PDF (via PyMuPDF)
  - Import pages from images/PDF
  - Save as `.dvai` (internal JSON+base64 format)
  - Export as PDF, PNG, JPG
- **Auto-save session** (every 60s to AppData)
- **Session restore** on re-open
- **Zoom** (10%-400%) with scroll wheel + slider
- **Selection tool:** Click-select, rubber-band, drag-move, corner-handle resize
- **Page management:** Add, delete, insert between pages
- **Composite rendering:** PIL-based export with GDI text rendering for complex scripts
- **Shares PenToolbar** with pen overlay (no duplicated controls)
- **Paste from clipboard** (Ctrl+V images)

### 🔄 Auto-Update System (`updater.py`)
- **Background update manager:** Check after 30s, then every 6 hours
- **Version comparison:** Semantic versioning (major.minor.patch)
- **GitHub-hosted:** `version.json` on GitHub raw
- **Download to** `~/Downloads/Dual Voicer Updates/`
- **Progress bar** in settings panel
- **One-click install:** Launch installer, auto-close app

### 🌐 Remote Config (`remote_config.py`)
- **GitHub-hosted JSON** with fallback chain: memory cache → disk cache (1h TTL) → remote fetch → hardcoded defaults
- **Currently controls:** Handwriting API URL, handwriting enabled flag
- **Extensible:** Any config can be changed server-side without app update

### 🔐 Authentication System (Web-First Model)
- **Login:** Email (Gmail-only) + Phone number verification
- **API endpoint:** `https://dualvoicer.ejobsit.com/api/desktop-login`
- **HWID binding:** Stable hardware ID stored in AppData
- **Device management:** devices_used / max_devices tracking
- **Plan types:** Trial (7 days), Premium, Unlimited
- **Expiry check:** Both at login and periodically (every 24 hours)
- **Auto-login:** Saved credentials in AppData config file
- **Trial signup:** Opens website with HWID parameter
- **Subscription:** Opens website payment page
- **Logout:** Clears saved config, resets auth state
- **DEV_MODE bypass:** All auth checks skipped when DEV_MODE=True

### 🖥️ UI & UX Features
- **CustomTkinter** dark theme with gradient toolbar
- **SpectrumButton:** PIL-rendered, glossy 3D circle, emoji icons, animated spectrum bars
- **WS_EX_NOACTIVATE:** Widget doesn't steal focus from active window
- **overrideredirect(True):** Borderless floating widget
- **Draggable widget** with position save/restore
- **Dynamic opacity:** Idle opacity ↔ Max opacity on hover
- **Widget scale:** 0.8x - 1.5x
- **Fullscreen detection:** Auto-hide widget during fullscreen apps (games, YouTube)
- **System tray** icon with show/exit menu
- **Network error toast:** Floating notification near widget
- **Button hover micro-animation:** 5% scale up/down
- **Label visibility toggle**
- **Start/End sound effects** via SFX channel

### 📋 Clipboard Guard (`clipboard_guard.py`)
- **Save/Restore pattern:** Preserves user's clipboard during AI/TTS operations
- **Rich paste support:** CF_HTML for formatted output (Word/Google Docs compatible)

---

## ⚙️ SETUP: config.py (Actual Current State)

> **⚠️ NOTE:** `config.py` still has placeholder values (`APP_NAME="VoiceAI Pro"`, `APP_VERSION="1.0.0"`)
> from initial setup. `main.py` overrides with actual values: `APP_VERSION = "4.0.8"`, and uses
> `"Dual Voicer"` as the display name. The `BACKEND_BASE` in config.py is a placeholder URL - 
> `main.py` directly hardcodes `https://dualvoicer.ejobsit.com/api/desktop-login` for auth.
> These should be synced in Phase 2/3.

```python
# config.py (ACTUAL FILE - with placeholder values noted)
import os
from dotenv import load_dotenv
load_dotenv()

# ════════════════════════════════════════════════════════
# DEV_MODE: Phase 1 = True (no auth needed)
#           Phase 3 = False (auth enabled)
# ════════════════════════════════════════════════════════
DEV_MODE = True   # ← ONLY change this in Phase 3

# Identity (⚠️ Placeholders - main.py uses "4.0.8" and "Dual Voicer")
APP_NAME        = "VoiceAI Pro"        # TODO: Change to "Dual Voicer" in Phase 2
APP_VERSION     = "1.0.0"              # TODO: Sync with main.py APP_VERSION = "4.0.8"
HWID_PREFIX     = "VAIPRO"
APPDATA_FOLDER  = "VoiceAIPro"         # TODO: Change to "DualVoicer" (main.py uses DualVoicer)
LOCK_FILE_NAME  = "voice_ai_pro.lock"  # TODO: Change to "dual_voicer.lock"

# AI (Phase 1 - needs real key in .env)
OPENROUTER_API_KEY  = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
AI_MODELS = {
    "primary":  "google/gemini-2.5-flash-lite",
    "fallback": "openai/gpt-4o-mini",
    "economy":  "anthropic/claude-haiku-4-5",
}
AI_TIMEOUT, AI_MAX_TOKENS = 20, 2048

# Backend (⚠️ Placeholder URL - main.py hardcodes "https://dualvoicer.ejobsit.com")
BACKEND_BASE        = os.getenv("BACKEND_URL", "https://placeholder.ejobsit.com")
API_GOOGLE_AUTH_URL = f"{BACKEND_BASE}/api/v2/google-auth"
API_SEND_OTP_URL    = f"{BACKEND_BASE}/api/v2/send-otp"
API_VERIFY_OTP_URL  = f"{BACKEND_BASE}/api/v2/verify-otp"
UPDATE_REPO_URL     = "https://raw.githubusercontent.com/shaaoonn/[DIST-REPO]/main"
GOOGLE_CLIENT_ID    = os.getenv("GOOGLE_CLIENT_ID", "")
# main.py actually uses: "https://dualvoicer.ejobsit.com/api/desktop-login" (hardcoded)
# main.py UPDATE_REPO_URL: "https://raw.githubusercontent.com/shaaoonn/DualVoicer-Dist/main"

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
    "size_preset": "medium",           # Widget size: tiny/small/medium/large/xlarge
    "screenshot_save_dir": "",         # Auto-save screenshot directory
}
```

---

## 🔑 DEV_MODE - How It Works

```python
# In main.py __init__ - add these lines:
from config import DEV_MODE

if DEV_MODE:
    # Simulate logged-in premium user - no backend needed
    self.is_authenticated = True
    self.user_email       = "dev@ejobsit.com"
    self.device_count     = 1
    self.max_devices      = 10
    self.user_cache       = {
        "plan_type": "Pro (Dev Mode)",
        "expiry_date": "2099-12-31",
    }
    print("[DEV_MODE] Auth bypassed - all features unlocked")
```

```python
# In freemium.py - bypass check:
def can_use(self, feature, app_instance):
    from config import DEV_MODE
    if DEV_MODE:
        return True   # ← everything allowed in dev mode
    # ... rest of freemium logic
```

```python
# In setup_hotkeys() - skip auth check:
def ai_trigger_flow(self):
    from config import DEV_MODE
    if not DEV_MODE and not self.is_authenticated:
        self.after(0, self.open_auth_panel)
        return
    # ... rest of AI flow
```

**Phase 3 করতে:** শুধু `config.py`-এ `DEV_MODE = False` করুন। Auth gate সব জায়গায় automatically চালু হবে।

---

## 📁 GitHub Repository Structure

**Repo:** `github.com/shaaoonn/DualVoicerAI`
**Branch:** `main`

```
DualVoicerAI/                  ← GitHub repo root
├── .gitignore
├── SKILL.md                   ← Master plan (you are here)
├── references/                ← Project planning docs (all phases)
│   ├── 02_ui_panel.md
│   ├── 03_auth_system.md
│   ├── 04_modules.md
│   ├── 05_testing.md
│   └── 06_backend.md
│
├── desktop/                   ← ★ Desktop App (Phase 1 - COMPLETE)
│   ├── main.py                ← 3766 lines: core app (VoiceTypingApp class)
│   ├── config.py              ← DEV_MODE, API keys, UI config
│   ├── updater.py             ← Auto-update system (check, download, install)
│   ├── remote_config.py       ← Server-side config with cache + fallback
│   ├── font_manager.py        ← Win32 font registration + language mapping
│   ├── build.bat              ← PyInstaller build script
│   ├── requirements.txt       ← Python dependencies
│   ├── version.json           ← Current version (3.6.9 for dist, 4.0.8 in code)
│   ├── .env.example           ← Environment variables template
│   ├── DualVoicerLogo.ico     ← App icon
│   ├── *.wav                  ← Start/end sound effects
│   ├── *.png                  ← Legacy button images (unused, kept for reference)
│   ├── fonts/                 ← 30+ bundled TTF fonts for handwriting
│   ├── ai_engine/             ← AI, TTS, clipboard, screenshot modules
│   │   ├── openrouter.py      ← OpenRouter API (text + vision)
│   │   ├── text_processor.py  ← Text processing with system prompt
│   │   ├── screenshot_analyzer.py  ← Vision analysis (multimodal)
│   │   ├── tts_detector.py    ← Language auto-detect + voice mapping
│   │   ├── handwriting.py     ← Google Handwriting Recognition API
│   │   ├── clipboard_guard.py ← Clipboard save/restore
│   │   └── format_handler.py  ← Markdown→HTML (CF_HTML), strip_markdown
│   ├── ui/                    ← Windows/panels
│   │   ├── settings_panel.py  ← Settings panel (6-tab sidebar, 29KB)
│   │   └── editor_window.py   ← Built-in editor (multi-page, 67KB)
│   ├── ui_components/         ← Reusable UI components
│   │   ├── spectrum_button.py ← PIL-rendered animated button
│   │   ├── language_data.py   ← 55+ STT language definitions
│   │   ├── pen_overlay.py     ← Transparent screen annotation (two-window)
│   │   ├── pen_toolbar.py     ← Floating pen toolbar
│   │   ├── drawing_engine.py  ← Canvas-agnostic drawing engine (47KB)
│   │   └── selection_manager.py ← Select, move, resize items
│   └── subscription/          ← Freemium gate
│       └── freemium.py        ← Trial timer + feature gating
│
├── website/                   ← (Phase 2 - future)
│   └── ...
│
└── backend/                   ← (Phase 2 - future)
    └── ...
```

### 🔒 CRITICAL: Folder Structure Rules for Claude Code

```
1. NEVER move files between top-level folders (desktop/, website/, backend/).
   - desktop/ এর ফাইল website/ এ নিয়ে যাবে না, উল্টোটাও না।
   - প্রতিটা ফোল্ডার আলাদা প্রোজেক্ট, আলাদা dependency.

2. NEVER flatten the structure - desktop app files MUST stay inside desktop/.
   - main.py → desktop/main.py (NOT repo root)
   - config.py → desktop/config.py (NOT repo root)

3. Root-level files: Only .gitignore, SKILL.md, references/ belong at repo root.
   - কখনো repo root-এ .py ফাইল রাখবে না।

4. NEW folders: Phase 2 তে website/ ও backend/ তৈরি হবে।
   - এগুলো desktop/ এর ভেতরে না, পাশে (sibling) থাকবে।

5. Git push: Always push to `main` branch on `origin`.
   - git push -u origin main

6. NEVER commit .env (secrets) - only .env.example.
   - .gitignore এ .env আছে, সরাবে না।

7. LOCAL dev path: F:\WEB and APPS\Dual Voicer AI\desktop\
   - App চালাতে: cd desktop && python main.py
```

---

## 🚀 Claude Code - Session Start

```
"SKILL.md পড়ো।
 বর্তমান Phase কোনটা? (Phase 1 COMPLETE, Phase 2 পরবর্তী)
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
markdown2>=2.5.0

# Optional (for editor PDF support)
# PyMuPDF>=1.23.0

# Phase 3 (add when needed)
# google-auth-oauthlib>=1.2.0
```
