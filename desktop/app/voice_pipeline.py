"""Voice pipeline — text-injection side.

This file currently holds the LEAF helpers — text mangling and OS
keyboard injection. The heavy mic loop + STT processing loop come in
step B.18 (also extracted into this file).

Owned helpers:
  - process_punctuation: maps voice triggers (দাঁড়ি, comma, …) to
    actual punctuation characters.
  - type_text: routes typed text either to the pen editor (if open),
    the drawer's text box (if open), or the OS-focused window (via
    pyautogui / clipboard paste).
  - _focused_window_class / _inject_text_universally: foreground
    window detection + paste-vs-typewrite routing.
  - _buffer_for_translation / _reschedule_translation_flush /
    _flush_translation_buffer / _type_ai_result: AI-mode buffering
    so a long sentence becomes one translate call instead of N.
"""

from __future__ import annotations

import ctypes
import queue
import re
import socket
import threading
import time
import tkinter as tk

import keyboard
import pyautogui
import pygame
import pyperclip
import speech_recognition as sr


class VoicePipelineMixin:
    """Mixed into VoiceTypingApp — voice text injection + translation buffer."""

    def _buffer_for_translation(self, txt, src_lang, tgt_lang, token):
        """Append a transcribed chunk to the AI translation buffer and
        (re)arm the silence-flush timer. Called from the processing
        worker thread; the timer fires on the Tk main thread.

        How others solve the 'broken sentence' problem:
          - VAD / silence detection: wait for a natural pause to flag
            the end of a phrase before sending it to the LLM.
          - Streaming STT with revision: keep updating the same line
            as new tokens arrive. Less applicable here since Google STT
            returns finalised chunks.
          - Buffer-then-flush: accumulate finalised chunks until
            silence, send the whole buffer as one prompt. Simple and
            matches how dictation apps like Google Docs voice typing
            and Whisper-based tools handle long sentences.
        We use buffer-then-flush.
        """
        with self._trans_buffer_lock:
            # Token mismatch → user changed language / restarted, drop old
            if self._trans_buffer and self._trans_buffer[-1][3] != token:
                print("[TRANS-BUFFER] token changed — clearing stale buffer")
                self._trans_buffer.clear()
            self._trans_buffer.append((txt, src_lang, tgt_lang, token))
        # Schedule the flush on the Tk main thread (after-callback safety)
        try:
            self.after(0, self._reschedule_translation_flush)
        except Exception:
            pass

    def _reschedule_translation_flush(self):
        """(Re)arm the silence timer that flushes the translation
        buffer. Each new chunk pushes the deadline back so we only
        translate when the user actually pauses."""
        if self._trans_flush_after_id is not None:
            try:
                self.after_cancel(self._trans_flush_after_id)
            except Exception:
                pass
            self._trans_flush_after_id = None
        self._trans_flush_after_id = self.after(
            self._trans_silence_ms, self._flush_translation_buffer)

    def _flush_translation_buffer(self):
        """Send the full buffered text to the AI as ONE call, then type
        the result. Runs on Tk main thread; offloads the actual API
        call to a worker thread so the UI doesn't freeze.

        Pipeline-busy guard: if more audio chunks are still queued OR
        currently being recognised, we postpone the flush. This is what
        makes a long sentence split across several recognition chunks
        get COMBINED into one AI call instead of flushed prematurely."""
        self._trans_flush_after_id = None

        # If more chunks are coming through the recognition pipeline,
        # wait for them. Otherwise we'd translate sentence-by-sentence
        # even when the user is still in the middle of a thought.
        try:
            queue_busy = (not self.audio_queue.empty()) or self.is_processing
        except Exception:
            queue_busy = False
        if queue_busy:
            # Reschedule for ~1s later — gives the recognizer time to
            # finish, then we re-evaluate. Loops until pipeline is idle.
            self._trans_flush_after_id = self.after(
                1000, self._flush_translation_buffer)
            return

        with self._trans_buffer_lock:
            if not self._trans_buffer:
                return
            items = list(self._trans_buffer)
            self._trans_buffer.clear()

        # Concatenate every chunk with a single space separator so the AI
        # treats it as one continuous sentence.
        full_text = " ".join((it[0] or "").strip() for it in items if it[0])
        if not full_text:
            return
        src_lang  = items[0][1]
        tgt_lang  = items[0][2]
        captured_token = items[-1][3]
        chunk_count = len(items)

        def _worker():
            try:
                from ai_engine.translator import translate_sync
                t0 = time.time()
                translated = translate_sync(full_text, src_lang, tgt_lang)
                dt_ms = (time.time() - t0) * 1000
                cur_token = getattr(self, "translation_token", 0)
                if captured_token != cur_token:
                    print(f"[TRANS-FLUSH] dropped stale "
                          f"({captured_token} != {cur_token})")
                    return
                print(f"[TRANS-FLUSH] {src_lang}->{tgt_lang} "
                      f"({chunk_count} chunks, {dt_ms:.0f}ms): '{translated}'")
                # Type on Tk main thread
                self.after(0, lambda t=translated: self._type_ai_result(t))
            except Exception as e:
                print(f"[TRANS-FLUSH] failed: {e} — typing raw transcribed text")
                self.after(0, lambda t=full_text: self._type_ai_result(t))

        threading.Thread(target=_worker, daemon=True).start()

    def _type_ai_result(self, text):
        """Type AI-translated/cleaned text. The AI output already includes
        proper punctuation, so we skip process_punctuation() here."""
        if not text:
            return
        is_only_punc = (len(text.strip()) <= 2
                        and all(c in '.।,?!;:--\n ' for c in text))
        try:
            self.type_text(text, leading_space=not is_only_punc)
        except Exception as e:
            print(f"[TYPE] AI result failed: {e}")


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
                        self._inject_text_universally(to_type)
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
            
            # Universal injection — keyboard.write for ASCII (fast),
            # clipboard paste for non-ASCII (works everywhere incl.
            # Notepad, Photoshop, Illustrator, AE, Blender, 3ds Max).
            self._inject_text_universally(to_type)
        except Exception: pass

    # Window class names of apps that DO NOT correctly handle
    # `keyboard.write` Unicode SendInput for non-Latin scripts. We
    # fall back to clipboard paste (Ctrl+V) for these apps. Other
    # apps (Photoshop, After Effects, Illustrator, Blender, 3ds Max,
    # browsers, MS Office, etc.) handle Unicode SendInput correctly
    # AND in some cases (After Effects timeline) Ctrl+V triggers an
    # unwanted "duplicate" action — so we MUST NOT use clipboard
    # there.
    _PASTE_REQUIRED_CLASSES = {
        "Notepad",                 # Windows Notepad (legacy edit ctrl)
        "Edit",                    # generic Win32 edit control
    }

    def _focused_window_class(self) -> str:
        """Return the Win32 class name of the foreground window, or ''."""
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return ""
            buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, buf, 256)
            return buf.value or ""
        except Exception:
            return ""

    def _inject_text_universally(self, text):
        """Inject `text` into the focused app reliably across Windows
        apps including Notepad, Adobe Photoshop / Illustrator / After
        Effects, Blender, 3ds Max, browsers, Office, etc.

        Hybrid strategy keyed on the FOCUSED APP'S window class:
          - Notepad / classic Edit ctrls → clipboard paste for ALL
            text (English + Bengali both). Notepad's legacy Edit
            control drops chars when keybd_event sequences arrive
            faster than it can process — clipboard is the only
            consistently reliable injection method there.
          - Everything else (Photoshop, AE, Illustrator, Blender,
            3ds Max, browsers, Office, …) → `keyboard.write`. Pro
            apps handle Unicode SendInput fine, AND clipboard paste
            (Ctrl+V) would cause unwanted side effects in some of
            them (e.g. AE timeline duplicates layers on Ctrl+V).
        """
        if not text:
            return

        cls = self._focused_window_class()
        needs_clipboard = cls in self._PASTE_REQUIRED_CLASSES

        if not needs_clipboard:
            # Default fast path — works for the vast majority of apps
            try:
                keyboard.write(text, delay=0)
                return
            except Exception:
                # Fall through to clipboard if keyboard.write fails
                pass

        # Clipboard paste (Notepad-class apps OR keyboard.write fallback)
        try:
            saved = ""
            try:
                saved = pyperclip.paste()
            except Exception:
                pass
            pyperclip.copy(text)
            time.sleep(0.005)
            pyautogui.hotkey('ctrl', 'v')
            if saved:
                def _restore_clip():
                    try:
                        pyperclip.copy(saved)
                    except Exception:
                        pass
                threading.Timer(0.4, _restore_clip).start()
        except Exception as e:
            print(f"[TYPE] inject fallback failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Voice pipeline part 2 — mic listener + processing loop + language switching
# ─────────────────────────────────────────────────────────────────────────────
# These are appended onto VoicePipelineMixin (defined above in the same
# file). Kept in one mixin so all the shared state (audio_queue,
# recognizer, mic events, active_lang, translation buffer state) lives
# in one place.


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

    # ── HWID + login config — implementation in app.hwid ──────────
    # These are thin wrappers that forward to the pure functions in
    # app.hwid, passing in our instance paths (app_data_dir, config_file).
    # Existing call sites use `self.get_stable_hwid()`, `self.save_login_config(...)`,
    # etc., so we keep the same method signatures.


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
            # Force-flush any buffered AI text BEFORE we bump the token —
            # otherwise the user loses what they just said. The flush uses
            # the OLD token so the result still gets typed.
            try:
                if hasattr(self, "_trans_buffer_lock"):
                    has_buffered = False
                    with self._trans_buffer_lock:
                        has_buffered = bool(self._trans_buffer)
                    if has_buffered:
                        # Cancel pending silence timer and flush right now
                        if self._trans_flush_after_id is not None:
                            try:
                                self.after_cancel(self._trans_flush_after_id)
                            except Exception:
                                pass
                            self._trans_flush_after_id = None
                        self._flush_translation_buffer()
            except Exception as e:
                print(f"[TRANS-BUFFER] flush-on-stop failed: {e}")

            self.is_listening = False; self.active_lang = None
            # Clear translation state + bump token so any future stale
            # translation result (e.g. a chunk still mid-recognition) is
            # dropped before it reaches type_text.
            self.active_stt_lang = None
            self.active_target_lang = None
            self.translation_token = (getattr(self, "translation_token", 0) + 1) & 0xFFFFFFFF
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
            # STARTING voice typing — bump translation token to drop any
            # in-flight translation result from a previous click. Implements
            # the user's "cancel old, start new" UX requirement.
            self.translation_token = (getattr(self, "translation_token", 0) + 1) & 0xFFFFFFFF
            # If switching from other lang while listening, do reset first
            if self.is_listening:
                self.is_listening = False
                self._silent_reset()
                time.sleep(0.1)

            # Start mic FIRST, then play sound when mic is ready
            self.mic_ready_event.clear()
            self.active_lang = lang; self.is_listening = True
            # Compute STT source language + translation target based on
            # the Translation Mode setting. Without translation, both are
            # the same (target = None means "no translation").
            self._refresh_translation_state()
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




    def _refresh_translation_state(self):
        """Recompute STT source language + AI target based on per-button
        Voice AI Mode settings. Safe to call any time — from
        switch_language, from settings change handlers, etc.

        Result:
          self.active_stt_lang    — what to recognize as
          self.active_target_lang — what to send to AI (None = raw, no AI)
                                    Same as stt → cleanup mode
                                    Different from stt → translation
        """
        # ── One-time migration of the legacy master `translation_mode` key
        # to the new per-button enables. Runs at most once per session.
        if not getattr(self, "_voice_ai_migrated", False):
            legacy = self.settings.pop("translation_mode", None)
            if legacy is True:
                self.settings.setdefault("btn1_translate_enabled", True)
                self.settings.setdefault("btn2_translate_enabled", True)
                self.settings["btn1_translate_enabled"] = True
                self.settings["btn2_translate_enabled"] = True
                try:
                    self.save_settings()
                except Exception:
                    pass
                print("[MIGRATE] translation_mode → per-button enables")
            # Also infer the new picker-mode keys from existing booleans
            # so the dropdown UI shows the correct current selection.
            for idx in (1, 2):
                key = f"btn{idx}_voice_mode"
                if key not in self.settings:
                    enabled = self.settings.get(f"btn{idx}_translate_enabled", False)
                    own_lang = self.settings.get(
                        f"btn{idx}_lang", "bn-BD" if idx == 1 else "en-US")
                    src_lang = self.settings.get(
                        f"btn{idx}_translate_from",
                        "en-US" if idx == 1 else "bn-BD")
                    if not enabled:
                        self.settings[key] = "normal"
                    elif src_lang == own_lang:
                        self.settings[key] = "ai_polish"
                    else:
                        self.settings[key] = "ai_translate"
            # TTS source mode inference
            if "tts_source_mode" not in self.settings:
                if self.settings.get("tts_auto_detect", True):
                    self.settings["tts_source_mode"] = "auto"
                else:
                    voice = (self.settings.get("tts_voice") or "").lower()
                    btn1 = self.settings.get("btn1_lang", "bn-BD").split("-")[0].lower()
                    btn2 = self.settings.get("btn2_lang", "en-US").split("-")[0].lower()
                    if voice.startswith(btn1):
                        self.settings["tts_source_mode"] = "btn1"
                    elif voice.startswith(btn2):
                        self.settings["tts_source_mode"] = "btn2"
                    else:
                        self.settings["tts_source_mode"] = "auto"
            try:
                self.save_settings()
            except Exception:
                pass
            self._voice_ai_migrated = True

        if not getattr(self, "active_lang", None):
            self.active_stt_lang = None
            self.active_target_lang = None
            return

        btn1_lang = self.settings.get("btn1_lang", "bn-BD")
        btn2_lang = self.settings.get("btn2_lang", "en-US")

        # Figure out which of the two buttons this active_lang belongs to.
        if self.active_lang == btn1_lang:
            ai_on = bool(self.settings.get("btn1_translate_enabled", False))
            stt_from = self.settings.get("btn1_translate_from", "en-US")
        elif self.active_lang == btn2_lang:
            ai_on = bool(self.settings.get("btn2_translate_enabled", False))
            stt_from = self.settings.get("btn2_translate_from", "bn-BD")
        else:
            ai_on = False
            stt_from = self.active_lang

        if not ai_on:
            self.active_stt_lang = self.active_lang
            self.active_target_lang = None
            print(f"[VOICE-AI] off — stt={self.active_lang}")
            return

        # AI on — STT in source lang, AI cleans/translates to button lang.
        self.active_stt_lang = stt_from
        self.active_target_lang = self.active_lang
        mode = "cleanup" if stt_from == self.active_lang else "translate"
        print(f"[VOICE-AI] {mode}: stt={stt_from} → ai={self.active_lang}")

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
                            # ── Adaptive listen() configuration ─────────
                            # Translation/cleanup (AI) mode: wait for the
                            # user to PAUSE for ~1s before returning, and
                            # allow up to 60s of continuous speech in one
                            # chunk. This way the entire long sentence is
                            # captured as ONE audio chunk → ONE recognition
                            # call → ONE translation. No fake "duplicate
                            # sentences" from chunk splits.
                            #
                            # Normal voice typing: keep the original
                            # snappy 8s phrase limit + tight 0.35s pause
                            # threshold so chunks land in the typed text
                            # quickly. THIS BEHAVIOUR IS UNCHANGED.
                            if getattr(self, "active_target_lang", None):
                                self.recognizer.pause_threshold = 1.0
                                phrase_limit = 60
                            else:
                                self.recognizer.pause_threshold = 0.35
                                phrase_limit = 8
                            audio = self.recognizer.listen(
                                source, timeout=1.0,
                                phrase_time_limit=phrase_limit)
                            # Race guard: listen() can block up to phrase_time_limit
                            # seconds. If the user stopped typing in the meantime,
                            # active_lang has been cleared to None - queueing it
                            # would later cause recognize_google() to error with
                            # "`language` must be a string". Drop stale chunks.
                            # In translation mode, STT runs in the SOURCE
                            # language (e.g. en-US for the Bengali button)
                            # and we translate to the TARGET (active_lang).
                            captured_lang = (
                                getattr(self, "active_stt_lang", None)
                                or self.active_lang
                            )
                            captured_target = getattr(
                                self, "active_target_lang", None)
                            captured_token = getattr(
                                self, "translation_token", 0)
                            if not self.is_listening or not isinstance(captured_lang, str) or not captured_lang:
                                continue
                            self.audio_queue.put(
                                (audio, captured_lang, captured_target, captured_token))
                            
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






    # ─────── Dropdown arrow handlers (BN / EN / SND / AI) ──────────

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
                    item = self.audio_queue.get(timeout=0.2)
                except queue.Empty:
                    continue

                # Backwards-compat: old 2-tuple (audio, lang) still works.
                # New 4-tuple is (audio, stt_lang, target_lang, token) for
                # translation-mode dispatch.
                if isinstance(item, tuple) and len(item) >= 4:
                    audio_data, lang, target_lang, captured_token = item[:4]
                elif isinstance(item, tuple) and len(item) == 2:
                    audio_data, lang = item
                    target_lang = None
                    captured_token = 0
                else:
                    print(f"[SKIP] Dropping audio chunk with bad shape: {type(item)}")
                    self.audio_queue.task_done()
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
                        _t0 = time.time()
                        try:
                            recognition_result[0] = self.recognizer.recognize_google(audio_data, language=lang)
                            _dt = (time.time() - _t0) * 1000
                            if recognition_result[0]:
                                print(f"[STT] {lang} in {_dt:.0f}ms: '{recognition_result[0]}'")
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

                    if txt:
                        # Voice commands run on the RAW transcribed text
                        # (regardless of AI mode) so commands like
                        # "backspace" / "select all" never get translated.
                        raw_lower = txt.lower().strip()

                        # --- VOICE COMMANDS ---
                        if raw_lower in ["backspace", "ব্যাকস্পেস", "ব্যাক স্পেস"]:
                            pyautogui.press('backspace')
                        elif raw_lower in ["back sentence", "ব্যাক সেন্টেন্স", "ব্যাক সেন টেন্স"]:
                            pyautogui.hotkey('ctrl', 'z')
                        elif raw_lower in ["select all", "সিলেক্ট অল", "সিলেক্ট করি", "সব সিলেক্ট"]:
                            pyautogui.hotkey('ctrl', 'a')
                        elif raw_lower in ["copy", "কপি", "কপি করি"]:
                            pyautogui.hotkey('ctrl', 'c')
                        elif raw_lower in ["paste", "পেস্ট", "পেস্ট করি"]:
                            try:
                                content = pyperclip.paste()
                                pyperclip.copy(content)
                                time.sleep(0.01)
                                pyautogui.hotkey('ctrl', 'v')
                            except Exception: pass
                        elif target_lang:
                            # ── Voice AI Mode ────────────────────────
                            # The mic's silence detection (pause_threshold)
                            # has ALREADY captured the full sentence as one
                            # chunk — see mic_listener_loop. So we can
                            # translate + type immediately, no buffering.
                            try:
                                from ai_engine.translator import translate_sync
                                t0 = time.time()
                                translated = translate_sync(
                                    txt, lang, target_lang)
                                dt_ms = (time.time() - t0) * 1000
                                cur_token = getattr(self, "translation_token", 0)
                                if captured_token != cur_token:
                                    print(f"[TRANS] dropped stale "
                                          f"({captured_token} != {cur_token})")
                                else:
                                    print(f"[TRANS] {lang}->{target_lang} "
                                          f"in {dt_ms:.0f}ms: '{translated}'")
                                    self._type_ai_result(translated)
                            except Exception as e:
                                print(f"[TRANS] failed ({e}) — typing raw")
                                self._type_ai_result(txt)
                        else:
                            # Normal Typing — unchanged behaviour
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
