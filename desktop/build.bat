@echo off
echo === VoiceAI Pro Build Script ===
echo.

REM 1. Install dependencies
echo [1/3] Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (echo FAILED: pip install && exit /b 1)

REM 2. Verify imports
echo [2/3] Verifying imports...
python -c "from config import DEV_MODE; from ai_engine.openrouter import complete; from ui_components.spectrum_button import SpectrumButton; from subscription.freemium import FreemiumGate; from ui.settings_panel import SettingsPanel; print('[OK] All imports passed')"
if errorlevel 1 (echo FAILED: import test && exit /b 1)

REM 3. Build .exe
echo [3/3] Building .exe...
pyinstaller --noconfirm --windowed --onefile ^
  --name "VoiceAIPro" ^
  --icon "DualVoicerLogo.ico" ^
  --add-data "ai_engine;ai_engine" ^
  --add-data "ui_components;ui_components" ^
  --add-data "ui;ui" ^
  --add-data "subscription;subscription" ^
  --add-data ".env;." ^
  --add-data "*.wav;." ^
  --add-data "*.ico;." ^
  --add-data "version.json;." ^
  --hidden-import customtkinter ^
  --hidden-import aiohttp ^
  --hidden-import speech_recognition ^
  --hidden-import pygame ^
  --hidden-import edge_tts ^
  --hidden-import pystray ^
  --hidden-import keyboard ^
  --hidden-import fast_langdetect ^
  --hidden-import fast_langdetect.ft_detect ^
  main.py

if errorlevel 1 (echo FAILED: pyinstaller build && exit /b 1)

echo.
echo === BUILD SUCCESS ===
echo Output: dist\VoiceAIPro.exe
pause
