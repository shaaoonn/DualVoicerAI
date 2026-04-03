# Reference 04: Phase 1 Modules — Implementation Code
**P1-1 থেকে P1-8 পর্যন্ত সব কোড এখানে**
**পড়ার আগে SKILL.md-এর progress table চেক করুন**

---

# §1 — Spectrum Button (Task P1-1)
**File:** `ui_components/spectrum_button.py`
**কাজ:** PNG button সরিয়ে circular animated Canvas button

```python
# ui_components/spectrum_button.py
import tkinter as tk
import math

class SpectrumButton(tk.Canvas):
    """
    Circular audio spectrum button.
    States: idle | listening | ai_thinking
    No images needed — pure Canvas drawing.
    """
    BAR_COUNT = 5
    ANIM_MS   = 50

    def __init__(self, parent, size=76, label="", command=None, colors=None, **kwargs):
        super().__init__(parent, width=size, height=size,
                         bg="#111111", highlightthickness=0, **kwargs)
        self.size    = size
        self.label   = label
        self.command = command
        self.colors  = colors or {
            "idle_bar": "#3A3A3A", "idle_ring": "#4A4A4A",
            "listening_ring": "#A0A0A0", "listening_bar": "#C0C0C0",
            "ai_ring": "#4A6A8A", "ai_bar": "#6C9EBF", "bg": "#111111",
        }
        self._state   = "idle"
        self._bars    = [0.08] * self.BAR_COUNT
        self._phase   = 0.0
        self._job     = None
        self._pressed = False

        self._draw()
        self.bind("<Button-1>",        self._on_down)
        self.bind("<ButtonRelease-1>", self._on_up)
        self.bind("<Enter>",  lambda e: self._on_hover(True))
        self.bind("<Leave>",  lambda e: self._on_hover(False))

    def set_state(self, state: str):
        """'idle' | 'listening' | 'ai_thinking'"""
        self._state = state
        if state == "idle":
            self._bars = [0.08] * self.BAR_COUNT
            self._stop()
            self._draw()
        else:
            self._start()

    def _draw(self):
        self.delete("all")
        cx = cy = self.size // 2
        r  = cx - 5

        # Ring color
        if self._state == "listening":
            pulse      = 0.65 + 0.35 * math.sin(self._phase * 0.18)
            v          = int(140 + 80 * pulse)
            ring_color = f"#{v:02x}{v:02x}{v:02x}"
            ring_w     = 2
        elif self._state == "ai_thinking":
            pulse      = 0.6 + 0.4 * math.sin(self._phase * 0.12)
            rv = int(74  + 20 * pulse)
            gv = int(106 + 20 * pulse)
            bv = int(143 + 20 * pulse)
            ring_color = f"#{rv:02x}{gv:02x}{bv:02x}"
            ring_w     = 2
        else:
            ring_color = self.colors["idle_ring"]
            ring_w     = 1

        self.create_oval(4, 4, self.size-4, self.size-4,
                         outline=ring_color, width=ring_w, fill="#1A1A1A")

        # 5 bars
        bar_w, gap  = 4, 7
        total_w     = self.BAR_COUNT * bar_w + (self.BAR_COUNT - 1) * gap
        sx          = cx - total_w // 2

        for i, h in enumerate(self._bars):
            bh = max(3, int(r * h))
            x1 = sx + i * (bar_w + gap)
            x2 = x1 + bar_w
            y1, y2 = cy - bh // 2, cy + bh // 2

            if self._state == "idle":
                bar_c = self.colors["idle_bar"]
            elif self._state == "listening":
                g     = int(80 + 140 * h)
                bar_c = f"#{g:02x}{g:02x}{g:02x}"
            else:
                t     = (math.sin(self._phase * 0.1 + i * 0.9) + 1) / 2
                bar_c = f"#{int(60+60*t):02x}{int(90+60*t):02x}{int(130+80*t):02x}"

            self.create_rectangle(x1, y1, x2, y2, fill=bar_c, outline="")

        if self.label:
            self.create_text(cx, self.size - 6, text=self.label,
                             fill="#666666", font=("Segoe UI", 7, "bold"))

    def _start(self):
        if not self._job: self._animate()

    def _stop(self):
        if self._job:
            self.after_cancel(self._job)
            self._job = None

    def _animate(self):
        self._phase += 1.0
        mid = self.BAR_COUNT // 2
        if self._state == "listening":
            for i in range(self.BAR_COUNT):
                dist = abs(i - mid) / mid if mid else 0
                wave = math.sin(self._phase * 0.25 + i * 0.75) * 0.5 + 0.5
                self._bars[i] = max(0.04, wave * (1.0 - dist * 0.25))
        elif self._state == "ai_thinking":
            for i in range(self.BAR_COUNT):
                self._bars[i] = 0.35 + 0.55 * (
                    math.sin(self._phase * 0.12 + i * 1.1) * 0.5 + 0.5)
        self._draw()
        self._job = self.after(self.ANIM_MS, self._animate)

    def _on_down(self, e): self._pressed = True
    def _on_up(self, e):
        if self._pressed and self.command: self.command()
        self._pressed = False
    def _on_hover(self, entering):
        if self._state == "idle":
            self._bars = [0.22]*self.BAR_COUNT if entering else [0.08]*self.BAR_COUNT
            self._draw()
```

### main.py-তে replace করবে (init_ui-এর ভেতরে)

```python
# REMOVE: সব PIL/PNG loading code (btn_width থেকে btn_settings পর্যন্ত)
# ADD:
from ui_components.spectrum_button import SpectrumButton
from config import SPECTRUM_BTN_SIZE, SPECTRUM_COLORS

btn_size = SPECTRUM_BTN_SIZE
self.frame.configure(fg_color="#111111")

self.btn_bn = SpectrumButton(self.frame, size=btn_size, label="BN",
    colors=SPECTRUM_COLORS,
    command=lambda: self.switch_language(self.settings.get("btn1_lang","bn-BD")),
    bg="#111111")
self.btn_bn.bind("<ButtonPress-1>", self.on_press)
self.btn_bn.bind("<B1-Motion>", self.on_drag)
self.btn_bn.grid(row=0, column=0, padx=(10,4), pady=8)

self.btn_en = SpectrumButton(self.frame, size=btn_size, label="EN",
    colors=SPECTRUM_COLORS,
    command=lambda: self.switch_language(self.settings.get("btn2_lang","en-US")),
    bg="#111111")
self.btn_en.bind("<ButtonPress-1>", self.on_press)
self.btn_en.bind("<B1-Motion>", self.on_drag)
self.btn_en.grid(row=0, column=1, padx=4, pady=8)

self.btn_ai = SpectrumButton(self.frame, size=btn_size, label="AI",
    colors=SPECTRUM_COLORS,
    command=self.ai_trigger_flow,
    bg="#111111")
self.btn_ai.bind("<ButtonPress-1>", self.on_press)
self.btn_ai.bind("<B1-Motion>", self.on_drag)
self.btn_ai.grid(row=0, column=2, padx=4, pady=8)

self.btn_settings = ctk.CTkButton(
    self.frame, text="⚙", width=24, height=24,
    font=("Segoe UI", 14), fg_color="transparent",
    hover_color="#2A2A2A", command=self.open_settings_panel)
self.btn_settings.bind("<ButtonPress-1>", self.on_press)
self.btn_settings.bind("<B1-Motion>", self.on_drag)
self.btn_settings.grid(row=0, column=3, padx=(2,8), pady=8)

self.geometry("295x92")
```

### update_ui_state() replacement

```python
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
```

---

# §2 — AI Engine (Task P1-2)
**Files:** `ai_engine/` folder — ৪টি ফাইল

## ai_engine/openrouter.py

```python
# ai_engine/openrouter.py
import aiohttp, asyncio, os
from config import (OPENROUTER_API_KEY, OPENROUTER_BASE_URL,
                    AI_MODELS, AI_TIMEOUT, AI_MAX_TOKENS, APP_NAME)

HEADERS = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://ejobsit.com",
    "X-Title": APP_NAME,
}

async def complete(messages: list, model_key: str = "primary") -> str:
    """Call OpenRouter API. Falls back to 'fallback' model on rate limit/timeout."""
    model   = AI_MODELS[model_key]
    payload = {"model": model, "messages": messages, "max_tokens": AI_MAX_TOKENS}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(OPENROUTER_BASE_URL, headers=HEADERS, json=payload,
                              timeout=aiohttp.ClientTimeout(total=AI_TIMEOUT)) as resp:
                if resp.status == 429:
                    if model_key == "primary":
                        return await complete(messages, "fallback")
                    raise RuntimeError("RATE_LIMIT")
                if resp.status == 401:
                    raise RuntimeError("INVALID_API_KEY")
                data = await resp.json()
                return data["choices"][0]["message"]["content"]
    except asyncio.TimeoutError:
        if model_key == "primary":
            return await complete(messages, "fallback")
        raise RuntimeError("TIMEOUT")
```

## ai_engine/format_handler.py

```python
# ai_engine/format_handler.py
import re

def strip_markdown(text: str) -> str:
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*',     r'\1', text)
    text = re.sub(r'_(.*?)_',       r'\1', text)
    text = re.sub(r'`(.*?)`',       r'\1', text)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[-*+]\s+', '• ', text, flags=re.MULTILINE)
    return text.strip()

def format_for_paste(text: str, mode: str = "plain") -> str:
    return strip_markdown(text) if mode == "plain" else text
```

## ai_engine/clipboard_guard.py

```python
# ai_engine/clipboard_guard.py
import pyperclip, pyautogui, time

class ClipboardGuard:
    def __init__(self): self._saved = ""

    def get_selected_text(self) -> str:
        try:    self._saved = pyperclip.paste()
        except: self._saved = ""
        pyautogui.hotkey("ctrl", "c")
        time.sleep(0.18)
        return pyperclip.paste()

    def paste_result(self, text: str):
        pyperclip.copy(text)
        time.sleep(0.05)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.12)
        try: pyperclip.copy(self._saved)
        except: pass
```

## ai_engine/text_processor.py

```python
# ai_engine/text_processor.py
"""
3-mode AI flow:
  MODE A (Question)  → text ends with '?' → answer appended below
  MODE B (Continue)  → text ends with trigger word → continue the text
  MODE C (Command)   → everything else → replace with AI output
"""
import re, asyncio
from ai_engine.openrouter import complete
from ai_engine.format_handler import format_for_paste

CONTINUE_TRIGGERS = [
    "চালিয়ে যাও", "continue", "লিখতে থাকো",
    "go on", "keep going", "এগিয়ে যাও", "...",
]

class TextProcessor:
    def __init__(self, system_instruction="", output_format="plain"):
        self.system = system_instruction or (
            "তুমি একজন দক্ষ বাংলা ও ইংরেজি লেখক সহকারী। সংক্ষিপ্ত উত্তর দাও।")
        self.format = output_format

    def _detect_mode(self, text):
        t = text.strip()
        if t.endswith("?"): return "question"
        for trig in CONTINUE_TRIGGERS:
            if t.lower().endswith(trig.lower()): return "continue"
        return "command"

    def _build_messages(self, text, mode):
        fmt = ("\n\nআউটপুট: plain text, কোনো markdown নয়।" if self.format == "plain"
               else "\n\nআউটপুট: **bold**, _italic_ ব্যবহার করতে পারো।")
        sys_msg = self.system + fmt

        if mode == "question":
            user = f"এই প্রশ্নের উত্তর দাও:\n\n{text}"
        elif mode == "continue":
            clean = text
            for t in CONTINUE_TRIGGERS:
                clean = re.sub(re.escape(t), "", clean, flags=re.IGNORECASE).strip()
            user = f"নিচের লেখাটা একই tone-এ চালিয়ে লেখো:\n\n{clean}"
        else:
            user = f"নিচের নির্দেশ অনুযায়ী কাজ করো:\n\n{text}"

        return [{"role":"system","content":sys_msg}, {"role":"user","content":user}]

    def _merge(self, original, ai_out, mode):
        out = format_for_paste(ai_out, self.format)
        if mode == "question": return f"{original}\n\n{out}"
        if mode == "continue":
            clean = original
            for t in CONTINUE_TRIGGERS:
                clean = re.sub(re.escape(t),"",clean,flags=re.IGNORECASE).strip()
            return f"{clean} {out}"
        return out

    async def process(self, selected_text: str) -> str:
        mode = self._detect_mode(selected_text)
        ai_out = await complete(self._build_messages(selected_text, mode))
        return self._merge(selected_text, ai_out, mode)
```

---

# §3 — AI Hotkey (Task P1-3)
**main.py-তে যোগ করবে**

```python
# setup_hotkeys()-এ যোগ করো:
from config import AI_HOTKEY, SMART_PASTE_HOTKEY, DEV_MODE

keyboard.add_hotkey(AI_HOTKEY,          self.ai_trigger_flow,   suppress=False)
keyboard.add_hotkey(SMART_PASTE_HOTKEY, self.smart_paste_flow,  suppress=True)
keyboard.add_hotkey(
    self.settings.get("btn1_hotkey", "ctrl+shift+b"),
    lambda: self.switch_language(self.settings.get("btn1_lang", "bn-BD"))
)
keyboard.add_hotkey(
    self.settings.get("btn2_hotkey", "ctrl+shift+e"),
    lambda: self.switch_language(self.settings.get("btn2_lang", "en-US"))
)

# ── New method: ai_trigger_flow() ────────────────────────
def ai_trigger_flow(self):
    from config import DEV_MODE
    if not DEV_MODE and not self.is_authenticated:
        self.after(0, self.open_auth_panel)
        return
    if not self.freemium.can_use("ai", self):
        self.after(0, lambda: self._show_lock_popup(
            self.freemium.get_lock_message("ai")))
        return
    if self.is_listening:
        self.is_listening = False
        self._silent_reset()

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
            guard.paste_result(result)
        except RuntimeError as e:
            msgs = {
                "RATE_LIMIT":      "⏳ AI লিমিট পৌঁছে গেছে, পরে চেষ্টা করুন",
                "TIMEOUT":         "⌛ AI সাড়া দিচ্ছে না",
                "INVALID_API_KEY": "🔑 API কী সমস্যা — Settings চেক করুন",
            }
            msg = msgs.get(str(e), f"❌ {e}")
            self.after(0, lambda m=msg: self._show_ai_error(m))
        finally:
            self.after(0, lambda: self.btn_ai.set_state("idle"))

    import threading
    threading.Thread(target=_run, daemon=True).start()

def _show_ai_error(self, message: str):
    from tkinter import messagebox
    messagebox.showwarning(APP_NAME, message)
```

---

# §4 — Multi-Language STT (Task P1-4)
**File:** `ui_components/language_data.py`

```python
# ui_components/language_data.py
# Google Web Speech API verified BCP-47 codes
GOOGLE_STT_LANGUAGES = [
    ("বাংলা (Bangladesh)",   "bn-BD"),
    ("বাংলা (India)",        "bn-IN"),
    ("English (US)",          "en-US"),
    ("English (UK)",          "en-GB"),
    ("English (India)",       "en-IN"),
    ("English (Australia)",   "en-AU"),
    ("हिन्दी",               "hi-IN"),
    ("اردو",                 "ur-PK"),
    ("தமிழ்",                "ta-IN"),
    ("తెలుగు",               "te-IN"),
    ("ಕನ್ನಡ",                "kn-IN"),
    ("മലയാളം",               "ml-IN"),
    ("ગુજરાતી",              "gu-IN"),
    ("ਪੰਜਾਬੀ",               "pa-IN"),
    ("मराठी",                "mr-IN"),
    ("नेपाली",                "ne-NP"),
    ("සිංහල",                "si-LK"),
    ("中文 (简体)",           "zh-CN"),
    ("中文 (繁體)",           "zh-TW"),
    ("日本語",                "ja-JP"),
    ("한국어",                "ko-KR"),
    ("Bahasa Indonesia",      "id-ID"),
    ("Bahasa Melayu",         "ms-MY"),
    ("ภาษาไทย",               "th-TH"),
    ("Tiếng Việt",            "vi-VN"),
    ("Filipino",              "fil-PH"),
    ("မြန်မာဘာသာ",           "my-MM"),
    ("العربية",               "ar-SA"),
    ("العربية (مصر)",         "ar-EG"),
    ("فارسی",                "fa-IR"),
    ("עברית",                "he-IL"),
    ("Türkçe",               "tr-TR"),
    ("Español (España)",      "es-ES"),
    ("Español (México)",      "es-MX"),
    ("Français",              "fr-FR"),
    ("Français (Canada)",     "fr-CA"),
    ("Deutsch",               "de-DE"),
    ("Italiano",              "it-IT"),
    ("Português (Brasil)",    "pt-BR"),
    ("Português (Portugal)",  "pt-PT"),
    ("Русский",               "ru-RU"),
    ("Polski",                "pl-PL"),
    ("Nederlands",            "nl-NL"),
    ("Svenska",               "sv-SE"),
    ("Norsk",                 "no-NO"),
    ("Dansk",                 "da-DK"),
    ("Suomi",                 "fi-FI"),
    ("Čeština",               "cs-CZ"),
    ("Magyar",                "hu-HU"),
    ("Română",                "ro-RO"),
    ("Українська",            "uk-UA"),
    ("Ελληνικά",              "el-GR"),
    ("Afrikaans",             "af-ZA"),
    ("Kiswahili",             "sw-KE"),
]

DEFAULT_BTN1_LANG = "bn-BD"
DEFAULT_BTN2_LANG = "en-US"
```

### main.py-তে mic_listener_loop()-এ পরিবর্তন

```python
# খুঁজুন: recognize_google(audio, language="bn-BD") বা "en-US"
# বদলান:  recognize_google(audio, language=self.active_lang)
# self.active_lang switch_language()-এ set হয় — কোনো অন্য পরিবর্তন লাগবে না
```

---

# §5 — Auto-Detect TTS (Task P1-5)
**File:** `ai_engine/tts_detector.py`
**Install:** `pip install fast-langdetect`

```python
# ai_engine/tts_detector.py
"""
Auto-detect language of text → pick matching edge_tts voice.
Uses fast-langdetect lite model (offline, ~900KB, 80x faster than langdetect).
Source: https://pypi.org/project/fast-langdetect/ (verified April 2026)
Source: https://pypi.org/project/edge-tts/ v7.2.8
"""
from fast_langdetect import detect as fl_detect

# ISO 639-1 → preferred edge_tts voice (verified in edge_tts v7.2.8)
LANG_TO_VOICE = {
    "bn":    "bn-BD-NabanitaNeural",
    "en":    "en-US-JennyNeural",
    "hi":    "hi-IN-SwaraNeural",
    "ur":    "ur-PK-UzmaNeural",
    "ar":    "ar-SA-ZariyahNeural",
    "zh":    "zh-CN-XiaoxiaoNeural",
    "zh-cn": "zh-CN-XiaoxiaoNeural",
    "zh-tw": "zh-TW-HsiaoChenNeural",
    "ja":    "ja-JP-NanamiNeural",
    "ko":    "ko-KR-SunHiNeural",
    "fr":    "fr-FR-DeniseNeural",
    "de":    "de-DE-KatjaNeural",
    "es":    "es-ES-ElviraNeural",
    "it":    "it-IT-ElsaNeural",
    "pt":    "pt-BR-FranciscaNeural",
    "ru":    "ru-RU-SvetlanaNeural",
    "tr":    "tr-TR-EmelNeural",
    "id":    "id-ID-GadisNeural",
    "ms":    "ms-MY-YasminNeural",
    "th":    "th-TH-PremwadeeNeural",
    "vi":    "vi-VN-HoaiMyNeural",
    "pl":    "pl-PL-ZofiaNeural",
    "nl":    "nl-NL-ColetteNeural",
    "sv":    "sv-SE-SofieNeural",
    "da":    "da-DK-ChristelNeural",
    "fi":    "fi-FI-NooraNeural",
    "cs":    "cs-CZ-VlastaNeural",
    "hu":    "hu-HU-NoemiNeural",
    "ro":    "ro-RO-AlinaNeural",
    "uk":    "uk-UA-PolinaNeural",
    "el":    "el-GR-AthinaNeural",
    "ta":    "ta-IN-PallaviNeural",
    "af":    "af-ZA-AdriNeural",
    "sw":    "sw-KE-ZuriNeural",
}
DEFAULT_VOICE = "en-US-JennyNeural"

def detect_language(text: str) -> str:
    if not text or len(text.strip()) < 3:
        return "en"
    try:
        results = fl_detect(text.strip(), model='lite', k=1)
        if results:
            return results[0].get('lang', 'en').lower()
    except Exception:
        pass
    return "en"

def get_tts_voice(text: str, fallback_lang: str = "en-US") -> str:
    detected = detect_language(text)
    if detected in LANG_TO_VOICE:
        return LANG_TO_VOICE[detected]
    prefix = detected.split("-")[0]
    if prefix in LANG_TO_VOICE:
        return LANG_TO_VOICE[prefix]
    stt_prefix = fallback_lang.split("-")[0].lower()
    if stt_prefix in LANG_TO_VOICE:
        return LANG_TO_VOICE[stt_prefix]
    return DEFAULT_VOICE
```

### stream_audio_chunks()-এ পরিবর্তন

```python
# main.py stream_audio_chunks() method-এ:
# খুঁজুন: communicate = edge_tts.Communicate(text, ...)
# বদলান:

from ai_engine.tts_detector import get_tts_voice
if self.settings.get("tts_auto_detect", True):
    tts_voice = get_tts_voice(text, self.active_lang or "en-US")
else:
    tts_voice = self.settings.get("tts_voice", "en-US-JennyNeural")

communicate = edge_tts.Communicate(text, tts_voice, rate=reading_speed)
```

---

# §6 — Smart Paste (Task P1-6)
**main.py-তে নতুন method**

```python
def smart_paste_flow(self):
    """Ctrl+Shift+V — clipboard content → KB + AI → paste reply."""
    from config import DEV_MODE
    if not DEV_MODE and not self.is_authenticated:
        self.after(0, self.open_auth_panel)
        return
    if not self.freemium.can_use("ai", self):
        self.after(0, lambda: self._show_lock_popup(
            self.freemium.get_lock_message("ai")))
        return

    try:    clipboard_text = pyperclip.paste()
    except: clipboard_text = ""

    if not clipboard_text or not clipboard_text.strip():
        self._show_ai_error("📋 ক্লিপবোর্ড খালি। আগে কিছু কপি করুন।")
        return

    # Truncate if too long
    clipboard_text = clipboard_text[:4000]

    self.after(0, lambda: self.btn_ai.set_state("ai_thinking"))

    def _run():
        import asyncio
        from ai_engine.openrouter import complete
        from ai_engine.format_handler import format_for_paste

        sys_prompt = self.settings.get("ai_system_prompt", "তুমি একজন দক্ষ সহকারী।")
        kb         = self.settings.get("knowledge_base", "").strip()
        out_format = self.settings.get("ai_output_format", "plain")

        kb_section = f"\n\n--- নলেজ বেজ ---\n{kb}\n--- নলেজ বেজ শেষ ---\n" if kb else ""
        system_msg = (
            f"{sys_prompt}{kb_section}\n\n"
            "নির্দেশ: সরাসরি reply লেখো। কোনো ভূমিকা নয়। "
            "যে ভাষায় প্রশ্ন সে ভাষায় উত্তর।"
        )
        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user",   "content": f"উত্তর দাও:\n\n{clipboard_text.strip()}"},
        ]
        try:
            result = asyncio.run(complete(messages))
            final  = format_for_paste(result, out_format)
            saved  = pyperclip.paste()
            pyperclip.copy(final)
            import time; time.sleep(0.05)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.12)
            try: pyperclip.copy(saved)
            except: pass
        except Exception as e:
            self.after(0, lambda: self._show_ai_error(f"Smart Paste সমস্যা: {e}"))
        finally:
            self.after(0, lambda: self.btn_ai.set_state("idle"))

    import threading
    threading.Thread(target=_run, daemon=True).start()
```

---

# §7 — Freemium Gate (Task P1-7)
**File:** `subscription/freemium.py`

```python
# subscription/freemium.py
import os, json, datetime

class FreemiumGate:
    TRIAL_HOURS     = 24
    GATED_FEATURES  = {"ai", "tts", "punctuation", "settings"}

    def __init__(self, app_data_dir: str):
        self._file = os.path.join(app_data_dir, ".freemium.json")
        self._data = self._load()

    def _load(self) -> dict:
        if os.path.exists(self._file):
            try:
                with open(self._file) as f: return json.load(f)
            except: pass
        data = {"first_install": datetime.datetime.now().isoformat()}
        self._save(data)
        return data

    def _save(self, data):
        try:
            os.makedirs(os.path.dirname(self._file), exist_ok=True)
            with open(self._file, "w") as f: json.dump(data, f)
        except: pass

    def is_trial_active(self) -> bool:
        try:
            installed = datetime.datetime.fromisoformat(self._data["first_install"])
            return (datetime.datetime.now()-installed).total_seconds() < self.TRIAL_HOURS*3600
        except: return False

    def is_subscribed(self, app) -> bool:
        return getattr(app, "is_authenticated", False)

    def can_use(self, feature: str, app) -> bool:
        from config import DEV_MODE
        if DEV_MODE:           return True   # Phase 1: always allowed
        if feature == "voice_typing": return True
        if feature not in self.GATED_FEATURES: return True
        if self.is_trial_active():   return True
        if self.is_subscribed(app):  return True
        return False

    def get_remaining_hours(self) -> float:
        try:
            installed = datetime.datetime.fromisoformat(self._data["first_install"])
            remaining = self.TRIAL_HOURS*3600 - (datetime.datetime.now()-installed).total_seconds()
            return max(0.0, remaining/3600)
        except: return 0.0

    def get_lock_message(self, feature: str) -> str:
        msgs = {
            "ai":          "🤖 AI ফিচার ব্যবহার করতে সাবস্ক্রাইব করুন",
            "tts":         "🔊 Text-to-Speech ব্যবহার করতে সাবস্ক্রাইব করুন",
            "punctuation": "✏️ দাড়ি কমা স্বয়ংক্রিয় করতে সাবস্ক্রাইব করুন",
            "settings":    "⚙️ সেটিংস পরিবর্তন করতে সাবস্ক্রাইব করুন",
        }
        return msgs.get(feature, "সাবস্ক্রিপশন প্রয়োজন")
```

### main.py __init__()-এ যোগ করো

```python
from subscription.freemium import FreemiumGate
self.freemium = FreemiumGate(self.app_data_dir)

# Freemium gate এখানে যোগ করো (existing gates modify করো):
# handle_reader_click(): if not self.freemium.can_use("tts", self): ...
# process_punctuation(): if not self.freemium.can_use("punctuation", self): return text

def _show_lock_popup(self, message: str):
    import webbrowser
    popup = ctk.CTkToplevel(self)
    popup.geometry("380x160")
    popup.title("সাবস্ক্রিপশন প্রয়োজন")
    popup.attributes("-topmost", True)
    ctk.CTkLabel(popup, text=message, font=("Segoe UI",12),
                 wraplength=340, justify="center").pack(pady=20)
    ctk.CTkButton(popup, text="সাবস্ক্রাইব করুন",
                  command=lambda: [webbrowser.open("https://ejobsit.com/ai-voice"),
                                   popup.destroy()]).pack(pady=4)
    ctk.CTkButton(popup, text="বাতিল", fg_color="#333333",
                  command=popup.destroy).pack()
    popup.after(8000, popup.destroy)
```

---

# §8 — Settings Panel (Task P1-8)
**→ বিস্তারিত কোড:** `references/02_ui_panel.md` পড়ুন
**File:** `ui/settings_panel.py`
**Integration:**
```python
# main.py-এ open_settings_panel() replace করো:
def open_settings_panel(self):
    from ui.settings_panel import SettingsPanel
    if not hasattr(self,'_settings_win') or not self._settings_win.winfo_exists():
        self._settings_win = SettingsPanel(parent=self, app_ref=self)
    self._settings_win.focus()
    self._settings_win.lift()
```

---

# §9 — DEV_MODE Setup (Task P1-0)

```python
# main.py VoiceTypingApp.__init__() শুরুতে যোগ করো:
from config import DEV_MODE, APP_NAME, NEW_SETTINGS_KEYS

# New settings keys merge
for k, v in NEW_SETTINGS_KEYS.items():
    if k not in self.settings:
        self.settings[k] = v

# DEV_MODE bypass
if DEV_MODE:
    self.is_authenticated = True
    self.user_email       = "dev@ejobsit.com"
    self.device_count     = 1
    self.max_devices      = 10
    self.user_cache       = {"plan_type": "Pro (Dev)", "expiry_date": "2099-12-31"}
```
