<div align="center">
  <img src="DualVoicerLogo.ico" alt="Dual Voicer AI Logo" width="120" />
  <h1>Dual Voicer AI Pro</h1>
  <p><strong>The Ultimate AI-Powered Voice Typing & Productivity Desktop Assistant</strong></p>
  <p>
    <a href="#features">Features</a> •
    <a href="#tech-stack">Tech Stack</a> •
    <a href="#installation--build">Installation</a> •
    <a href="#shortcuts--hotkeys">Shortcuts</a>
  </p>
</div>

---

## 🚀 Overview

**Dual Voicer AI Pro** is a cutting-edge desktop application designed to supercharge your productivity. It seamlessly blends **multi-lingual voice typing** (with 55+ languages including Bengali and English), **AI-driven text assistance**, **screen annotation (Pen Overlay)**, **intelligent clipboard management**, and a **pro-level built-in editor**. 

Whether you need to dictate an article, rewrite an email using AI, annotate your screen during a presentation, or quickly snap a screenshot for AI vision analysis—Dual Voicer AI Pro has you covered.

---

## ✨ Key Features

### 🎙️ Core Voice Typing
- **Dual-Language Toggle:** Instantly switch between Bengali and English typing with a single click or hotkey.
- **Global 55+ Language Support:** Powered by Google Web Speech API.
- **Smart Punctuation:** Automatically adds punctuation based on voice commands (e.g., saying "দাড়ি" adds `।`, "কমা" adds `,`, "নতুন লাইন" adds `\n`).
- **Voice Commands:** Supports commands like "ব্যাকস্পেস", "কপি", "পেস্ট", and "সিলেক্ট অল".
- **Auto-Stop & Noise Filtering:** Configurable microphone sensitivity and intelligent auto-stop timers.

### 🤖 AI Assistant & Vision
- **AI Trigger:** Select text anywhere on your PC and hit `Ctrl+Shift+A` to have AI rewrite, translate, or format it.
- **Smart Paste (`Ctrl+Shift+V`):** Paste clipboard content enriched by AI using your custom knowledge base.
- **Screenshot Vision:** Capture your screen (`Win+Shift+S`) and let AI analyze the image to extract text or answer visual questions.
- **Multi-Model Support:** Integrates with OpenRouter, supporting Gemini 2.5 Flash, GPT-4o-Mini, and Claude Haiku.

### ⌨️ Built-in Bengali Keyboards
- **Avro Phonetic Support:** Type "ami banglay gan gai" and get "আমি বাংলায় গান গাই" instantly—**no external software needed!**
- **Bijoy 52 Support:** Built-in mapping for traditional Bijoy layout users.

### ✏️ Screen Annotation (Pen Overlay)
- **Draw Anywhere:** Floating pen toolbar allows you to draw, highlight, or erase directly on your screen.
- **Handwriting Recognition:** Draw letters on the screen and have them automatically converted to digital text using Google Input Tools API.
- **Smart Shapes:** Hold your pen for 3 seconds to auto-snap to perfect circles, rectangles, or straight lines.

### 📄 Pro-Level Built-in Editor
- **Multi-page Canvas:** Import PDFs or Images and edit them on an infinite scrollable canvas.
- **Export Options:** Save your projects as `.dvai`, or export to PDF, PNG, and JPG.
- **Auto-Save:** Automatic session saving every 60 seconds ensures you never lose your work.

### 🔊 Smart Text-to-Speech (TTS)
- **Auto-Language Detection:** Reads text back to you in its native language (Bengali or English) using Edge-TTS.
- **40+ Premium Voices:** Natural sounding voices with adjustable playback speed.

---

## 🛠️ Tech Stack

- **GUI Framework:** CustomTkinter (Modern Python UI) & Pygame (Audio)
- **Voice / Speech:** SpeechRecognition, Google Web Speech, Edge-TTS
- **AI Integration:** OpenRouter API (Multimodal)
- **Image & PDF:** Pillow (PIL), PyMuPDF
- **System Level:** keyboard, pyautogui, pystray (System Tray), ctypes (Win32 API)

---

## 📂 Project Structure

```text
DualVoicerAI/
├── desktop/                  # Main application source code
│   ├── main.py               # Application entry point (VoiceTypingApp)
│   ├── config.py             # Global configurations & Hotkeys
│   ├── build.bat             # PyInstaller build script for creating the .exe
│   ├── ai_engine/            # AI, OpenRouter, Vision & STT logic
│   ├── ui/                   # Main Windows (Settings Panel, Editor)
│   ├── ui_components/        # Reusable UI widgets (Spectrum Button, Toolbar)
│   ├── avro_engine/          # Built-in Bengali Phonetic engine
│   └── fonts/                # Bundled handwriting & UI fonts
├── SKILL.md                  # Comprehensive development & feature plan
└── README.md                 # You are here
```

---

## ⚙️ Installation & Build

### Prerequisites
- Windows 10 / 11
- Python 3.10+ (if running from source)

### Running from Source
1. Clone the repository:
   ```bash
   git clone https://github.com/shaaoonn/DualVoicerAI.git
   cd DualVoicerAI/desktop
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application:
   ```bash
   python main.py
   ```

### Building the Executable (`.exe`)
To create a standalone portable executable that runs on any Windows machine without requiring Python:
1. Navigate to the `desktop` directory.
2. Run the build script:
   ```bash
   build.bat
   ```
3. The compiled executable will be located at `desktop/dist/VoiceAIPro.exe`.

---

## ⌨️ Shortcuts & Hotkeys

*Note: Most hotkeys can be customized within the app's Settings Panel.*

| Action | Default Hotkey |
|--------|----------------|
| **Trigger AI on selection** | `Ctrl + Shift + A` |
| **Smart Paste** | `Ctrl + Shift + V` |
| **Take Screenshot** | `Win + Shift + S` (Custom `Ctrl+Shift+S`) |
| **Start/Stop Voice 1 (BN)** | `Alt + Z` |
| **Start/Stop Voice 2 (EN)** | `Alt + X` |
| **Toggle Pen Overlay** | `Ctrl + Shift + D` |

**Editor Tool Shortcuts:**
- `Alt + P` : Pen
- `Alt + H` : Highlighter
- `Alt + E` : Eraser
- `Alt + T` : Text Tool
- `Alt + W` : Handwrite Mode

---

<div align="center">
  <p>Built with ❤️ by EJOSB IT</p>
</div>
