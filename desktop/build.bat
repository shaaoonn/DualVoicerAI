@echo off
setlocal
echo === VoiceAI Pro Build Script ===
echo.

REM 1. Verify imports (skip pip install - rely on already-installed packages
REM    because some packages like pygame have no wheels for newest Python).
echo [1/3] Verifying imports...
python -c "from config import DEV_MODE; from ai_engine.openrouter import complete; from ui_components.spectrum_button import SpectrumButton; from subscription.freemium import FreemiumGate; from ui.settings_panel import SettingsPanel; from i18n import tr; from keyboard_overlay import KeyboardOverlay; print('[OK] All imports passed')"
if errorlevel 1 (
    echo FAILED: import test
    exit /b 1
)

REM 2. Stage .env beside main.py so PyInstaller can bundle it
echo [2/3] Staging .env...
if exist "..\.env" (
    copy /Y "..\.env" ".env" >nul
    echo   .env copied from parent
) else (
    if not exist ".env" (
        echo. > .env
        echo   no .env found - created empty placeholder
    )
)

REM 3. Build .exe via `python -m PyInstaller` (more reliable than `pyinstaller`
REM    when the Scripts directory isn't on PATH).
echo [3/3] Building .exe (this takes 1-3 minutes)...
python -m PyInstaller --noconfirm --windowed --onefile ^
  --clean ^
  --name "VoiceAIPro" ^
  --icon "DualVoicerLogo.ico" ^
  --add-data "ai_engine;ai_engine" ^
  --add-data "ui_components;ui_components" ^
  --add-data "ui;ui" ^
  --add-data "subscription;subscription" ^
  --add-data "avro_engine;avro_engine" ^
  --add-data "fonts;fonts" ^
  --add-data ".env;." ^
  --add-data "*.wav;." ^
  --add-data "*.png;." ^
  --add-data "*.ico;." ^
  --add-data "version.json;." ^
  --add-data "i18n.py;." ^
  --add-data "keyboard_overlay.py;." ^
  --add-data "keyboard_input.py;." ^
  --add-data "ll_hook.py;." ^
  --add-data "font_manager.py;." ^
  --add-data "remote_config.py;." ^
  --add-data "updater.py;." ^
  --add-data "config.py;." ^
  --collect-all customtkinter ^
  --collect-all avro_engine ^
  --collect-all avro ^
  --collect-data PIL ^
  --collect-submodules pystray ^
  --collect-submodules keyboard ^
  --hidden-import customtkinter ^
  --hidden-import aiohttp ^
  --hidden-import speech_recognition ^
  --hidden-import pygame ^
  --hidden-import edge_tts ^
  --hidden-import pystray ^
  --hidden-import pystray._win32 ^
  --hidden-import keyboard ^
  --hidden-import keyboard._winkeyboard ^
  --hidden-import fast_langdetect ^
  --hidden-import fast_langdetect.ft_detect ^
  --hidden-import markdown2 ^
  --hidden-import dotenv ^
  --hidden-import psutil ^
  --hidden-import pyautogui ^
  --hidden-import pyperclip ^
  --hidden-import requests ^
  --hidden-import PIL._tkinter_finder ^
  --hidden-import PIL.ImageGrab ^
  --hidden-import PIL.ImageTk ^
  --hidden-import avro ^
  --hidden-import asyncio ^
  --hidden-import json ^
  --hidden-import uuid ^
  main.py

if errorlevel 1 (
    echo FAILED: pyinstaller build
    exit /b 1
)

REM Clean up staged .env (don't leave secrets in repo dir)
if exist ".env" (
    fc /b ".env" "..\.env" >nul 2>&1
    if not errorlevel 1 del ".env" 2>nul
)

echo.
echo === BUILD SUCCESS ===
echo Output: dist\VoiceAIPro.exe
echo.
endlocal
