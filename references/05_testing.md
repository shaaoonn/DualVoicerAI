# Reference 05: Testing + Build
**প্রতিটি module শেষে এই list থেকে test করুন**

---

## Phase 1 Test Checklist

### P1-1: Spectrum Button
```
□ App চালু হলে ৩টি গোল বাটন দেখা যাচ্ছে (BN, EN, AI)
□ Idle state: dark gray bars, faint ring
□ BN click → listening animation (gray wave)
□ EN click → listening animation
□ AI button hover → bars উঠে যায়
□ Window drag কাজ করছে (বাটনে ধরে টানা)
□ Settings ⚙ বাটন কাজ করছে
```

### P1-2: AI Engine
```
□ .env ফাইলে OPENROUTER_API_KEY আছে
□ python -c "from ai_engine.openrouter import complete; import asyncio; print(asyncio.run(complete([{'role':'user','content':'say hi'}])))"
□ কোনো import error নেই
```

### P1-3: AI Hotkey
```
□ কোনো text select করো → Ctrl+Shift+A → AI button নীল হয় → result paste হয়
□ "আমার নাম কি?" select → Mode A: answer নিচে যোগ হয়
□ "এই লেখা formal করো" select → Mode C: replace হয়
□ Plain mode → paste-এ ** বা # নেই
□ API timeout → error message দেখায়
□ AI button processing শেষে idle-এ ফিরে আসে
```

### P1-4: Multi-Language STT
```
□ Settings → ভাষা tab খোলে
□ BN button-এর ভাষা বদলানো যাচ্ছে (dropdown থেকে)
□ EN button-এর ভাষা বদলানো যাচ্ছে
□ Hindi select করে বললে Hindi type হচ্ছে
□ Settings save করলে পরের session-এও থাকছে
```

### P1-5: Auto TTS
```
□ বাংলা text select করে Reader চালু করো → বাংলা voice বাজছে
□ English text → English voice
□ Settings → টিটিএস → auto-detect off → manual voice কাজ করছে
```

### P1-6: Smart Paste
```
□ কিছু text copy করো → Ctrl+Shift+V → AI button নীল → reply paste হয়
□ Knowledge Base-এ কিছু লিখে save করো → Smart Paste → KB থেকে উত্তর আসছে
□ ক্লিপবোর্ড empty → "আগে কিছু কপি করুন" message
□ Smart Paste শেষে original clipboard restore হয়
```

### P1-7: Freemium Gate
```
□ DEV_MODE=True → সব কিছু কাজ করছে (gate bypass)
□ DEV_MODE=False করে test করো:
   □ AI trigger → lock popup দেখাচ্ছে
   □ TTS → lock popup
   □ Settings → lock overlay
   □ Voice typing (BN/EN) → এখনো কাজ করছে (free forever)
□ DEV_MODE=True ফিরিয়ে দাও Phase 1-এ
```

### P1-8: Settings Panel
```
□ Settings খুললে 860×700 window আসে
□ বাম sidebar-এ ৬টি tab আছে
□ সাধারণ tab: microphone dropdown, noise slider কাজ করছে
□ ভাষা tab: দুটো dropdown আছে
□ AI tab: system prompt, knowledge base textarea আছে
□ সংরক্ষণ করলে settings.json update হচ্ছে
□ পরের session-এও settings থাকছে
```

---

## §build - Phase 1 Final Build

```bash
# 1. সব dependencies install করো:
pip install -r requirements.txt

# 2. Test চালাও:
python main.py

# 3. Build করো:
pyinstaller --noconfirm --windowed --onefile \
  --name "VoiceAIPro" \
  --icon assets/app_icon.ico \
  --add-data "assets;assets" \
  --add-data "ai_engine;ai_engine" \
  --add-data "ui_components;ui_components" \
  --add-data "ui;ui" \
  --add-data "subscription;subscription" \
  --add-data ".env;." \
  --hidden-import customtkinter \
  --hidden-import aiohttp \
  --hidden-import speech_recognition \
  --hidden-import pygame \
  --hidden-import edge_tts \
  --hidden-import pystray \
  --hidden-import keyboard \
  --hidden-import fast_langdetect \
  main.py

# 4. dist/ ফোল্ডারে .exe পাবে
# 5. নতুন PC-তে চালিয়ে test করো
```

---

## §phase3 - Phase 3 Integration Test

```
□ config.py: DEV_MODE = False
□ Login window খুলছে
□ Google login button → browser খোলে → Google account select করা যাচ্ছে
□ Login হলে → "Pro" plan দেখাচ্ছে (trial)
□ Phone OTP → number দিলে SMS আসছে → OTP দিলে login হচ্ছে
□ Expired account → block হচ্ছে
□ AI features → subscription ছাড়া locked
□ Voice typing → subscription ছাড়াও কাজ করছে
□ Production .exe build + নতুন PC test
```
