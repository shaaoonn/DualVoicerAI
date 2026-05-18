"""TTS reader pipeline — Smart-Streaming edge_tts.

The SND button reads selected text aloud using Microsoft's edge_tts
voices. Architecture is a producer/consumer pair around a queue:

* ``stream_audio_chunks`` (PRODUCER, async): splits text into
  sentences, calls edge_tts per sentence, writes mp3 chunks to a temp
  file, enqueues file paths to ``playback_queue``.
* ``play_audio_chunks`` (CONSUMER, daemon thread): dequeues files
  and plays them through ``pygame.mixer.music`` sequentially with
  ~50ms gaps so playback never stutters mid-sentence.

Session lifecycle is tracked via ``_tts_session_id``: a new SND
click bumps the counter, old consumers detect the bump and exit
without leaving orphaned threads or playing stale audio.

Owned state:
  - is_reading, is_paused, current_text
  - _tts_session_id, _tts_lock, playback_queue
"""

from __future__ import annotations

import asyncio
import datetime
import os
import queue
import re
import tempfile
import threading
import time
import tkinter as tk
import uuid

import edge_tts
import pyautogui
import pygame
import pyperclip


class TTSMixin:
    """Mixed into VoiceTypingApp — TTS reader pipeline."""

    def _pause_reader(self):
        """Pause TTS playback immediately (synchronous)."""
        if self.is_reading and not self.is_paused:
            try:
                pygame.mixer.music.pause()
            except pygame.error: pass
            self.is_paused = True
            self.after(0, lambda: self.btn_read.set_state("idle"))
            self.after(0, lambda: self.btn_read.set_icon_mode("pause"))

    def _resume_reader(self):
        """Resume paused TTS."""
        if self.is_reading and self.is_paused:
            try:
                pygame.mixer.music.unpause()
            except pygame.error: pass
            self.is_paused = False
            self.after(0, lambda: self.btn_read.set_state("listening"))
            self.after(0, lambda: self.btn_read.set_icon_mode("play"))

    def handle_reader_click(self):
        from config import DEV_MODE
        if not DEV_MODE and not self.is_authenticated:
            self.open_auth_panel()
            return

        # Simple state machine - no _sound_busy guard
        if self.is_reading and not self.is_paused:
            # Playing → Pause (synchronous, instant)
            self._pause_reader()
        elif self.is_reading and self.is_paused:
            # Paused → check for new text, then resume or play new
            threading.Thread(target=self._reader_resume_or_new, daemon=True).start()
        else:
            # Not reading → start new
            threading.Thread(target=self._reader_start_new, daemon=True).start()

    def _reader_start_new(self):
        """Grab selected text and start TTS (background thread)."""
        try:
            saved = ""
            try: saved = pyperclip.paste()
            except Exception: pass
            pyperclip.copy("")
            pyautogui.hotkey('ctrl', 'c')
            time.sleep(0.2)
            new_text = pyperclip.paste().strip()
            if not new_text:
                pyautogui.hotkey('ctrl', 'insert')
                time.sleep(0.15)
                new_text = pyperclip.paste().strip()
            if not new_text:
                try: pyperclip.copy(saved)
                except Exception: pass
                return
            self.current_text = new_text
            self._run_tts_async()
        except Exception as e:
            print(f"[TTS ERROR] {e}")
            self.stop_reader_internal()

    def _reader_resume_or_new(self):
        """From paused state: check clipboard for new text, resume or play new."""
        try:
            saved = ""
            try: saved = pyperclip.paste()
            except Exception: pass
            pyperclip.copy("")
            pyautogui.hotkey('ctrl', 'c')
            time.sleep(0.2)
            new_text = pyperclip.paste().strip()
            if not new_text:
                # No new selection → just resume
                try: pyperclip.copy(saved)
                except Exception: pass
                self._resume_reader()
                return
            if new_text != self.current_text:
                # New text → stop old, play new
                self.stop_reader_internal()
                time.sleep(0.1)
                self.current_text = new_text
                self._run_tts_async()
            else:
                # Same text → resume
                self._resume_reader()
        except Exception as e:
            print(f"[TTS ERROR] {e}")
            self.stop_reader_internal()

    
    # ===== SMART STREAMING TTS START =====
    
    def _run_tts_async(self):
        """Entry point for Smart Streaming TTS with session management"""
        # 1. Create new session (prevents old consumers from killing this one)
        with self._tts_lock:
            self._tts_session_id += 1
            my_session = self._tts_session_id

        # 2. Initialize Queue for this session
        self.playback_queue = queue.Queue()
        self.is_reading = True; self.is_paused = False

        # 3. Update UI - playing state
        self.after(0, lambda: self.btn_read.set_state("listening"))
        self.after(0, lambda: self.btn_read.set_icon_mode("pause"))

        # 4. Start Consumer Thread (Player) with session ID
        threading.Thread(target=self.play_audio_chunks, args=(my_session,), daemon=True).start()

        # 5. Start Producer (Generator) - Runs in asyncio
        try:
            # Ensure pygame mixer is initialized
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            asyncio.run(self.stream_audio_chunks(my_session))
        except Exception as e:
            self._log_tts_error(f"TTS Producer failed: {e}")
            # Only stop if still the current session
            if self._tts_session_id == my_session:
                self.stop_reader_internal()

    def _log_tts_error(self, message):
        """Log TTS errors to file (NullWriter hides console output)"""
        try:
            import traceback
            log_path = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'DualVoicer', 'tts_error.log')
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(f"\n[{datetime.datetime.now()}] {message}\n")
                f.write(traceback.format_exc())
        except OSError:
            pass

    async def stream_audio_chunks(self, session_id):
        """PRODUCER: Splits text and generates individual audio chunks with retry"""
        try:
            full_text = self.current_text

            # ── Split into TTS sentences FIRST (used by both normal and
            # translate modes) ───────────────────────────────────────────
            def _split_sentences(text):
                chunks = re.split(r'([.?!;:\n|।])', text)
                raw = []
                cur = ""
                for part in chunks:
                    if part in ".?!;:\n|।":
                        cur += part
                        if cur.strip():
                            raw.append(cur.strip())
                        cur = ""
                    else:
                        cur += part
                if cur.strip():
                    raw.append(cur.strip())
                if not raw:
                    raw = [text]
                # Merge short pieces into ~300-char chunks
                merged = []
                buf = ""
                for s in raw:
                    if len(buf) + len(s) < 300:
                        buf = (buf + " " + s).strip() if buf else s
                    else:
                        if buf:
                            merged.append(buf)
                        buf = s
                if buf:
                    merged.append(buf)
                return merged

            # ── SND drawer "in btn1/btn2 lang" mode ──────────────────────
            # Translate sentence-by-sentence so:
            #   • No single API call carries an entire long text → no timeout
            #   • Streaming starts playing the FIRST sentence while later
            #     sentences are still being translated
            #
            # NOTE: stream_audio_chunks runs inside asyncio.run() (a FRESH
            # event loop in the TTS thread). Dispatch through asyncio.to_thread
            # → translate_to_target_sync → run_on_executor → persistent
            # executor loop. This avoids aiohttp session cross-loop crashes.
            tts_mode = self.settings.get("tts_source_mode", "auto")
            if tts_mode in ("btn1", "btn2") and full_text.strip():
                target_lang = self.settings.get(
                    f"{tts_mode}_lang",
                    "bn-BD" if tts_mode == "btn1" else "en-US")

                from ai_engine.tts_detector import get_tts_voice
                voice = self.settings.get("tts_voice", "bn-BD-NabanitaNeural")
                # Fallback: derive voice from target_lang if tts_voice unset
                if not voice or voice == "en-US-JennyNeural":
                    voice = get_tts_voice(target_lang, target_lang)

                from ai_engine.translator import translate_to_target_sync

                sentences_orig = _split_sentences(full_text)
                print(f"[TTS-AI] mode={tts_mode} lang={target_lang} "
                      f"chunks={len(sentences_orig)}")

                try:
                    speed = float(self.settings.get("reading_speed", "1.0"))
                except (ValueError, TypeError):
                    speed = 1.0
                speed = max(0.5, min(speed, 3.0))
                rate_pct = int(round((speed - 1.0) * 100))
                rate = f"{'+' if rate_pct >= 0 else ''}{rate_pct}%"

                for i, orig_sentence in enumerate(sentences_orig):
                    if not self.is_reading or self._tts_session_id != session_id:
                        print("[TTS-AI] Stopped (session changed)")
                        break
                    # Translate this sentence (~short text → fast, no timeout)
                    try:
                        translated_sentence = await asyncio.to_thread(
                            translate_to_target_sync, orig_sentence, target_lang)
                        tts_sentence = (translated_sentence.strip()
                                        if translated_sentence and translated_sentence.strip()
                                        else orig_sentence)
                        print(f"[TTS-AI] chunk {i+1}/{len(sentences_orig)}: "
                              f"{tts_sentence[:60].replace(chr(10), ' ')}…")
                    except Exception as e:
                        print(f"[TTS-AI] chunk {i+1} translate failed ({e}) "
                              f"— using original")
                        tts_sentence = orig_sentence

                    filename = os.path.join(
                        tempfile.gettempdir(), f"stream_{uuid.uuid4().hex}.mp3")
                    success = False
                    for attempt in range(3):
                        try:
                            comm = edge_tts.Communicate(tts_sentence, voice,
                                                        rate=rate)
                            await comm.save(filename)
                            success = True
                            break
                        except Exception as e:
                            if attempt < 2:
                                print(f"[TTS-AI] TTS attempt {attempt+1} "
                                      f"failed: {e}, retrying…")
                                await asyncio.sleep(1 * (attempt + 1))
                            else:
                                self._log_tts_error(
                                    f"TTS-AI chunk {i+1} failed: {e}")
                    if success and self.is_reading and self._tts_session_id == session_id:
                        self.playback_queue.put(filename)
                    elif not success:
                        try: os.remove(filename)
                        except OSError: pass

                if self.is_reading and self._tts_session_id == session_id:
                    self.playback_queue.put(None)
                return   # ← translation path done; skip normal TTS below

            # ── Normal (auto-detect) TTS path ────────────────────────────
            sentences = _split_sentences(full_text)
            print(f"[TTS] Smart Streaming: {len(sentences)} chunks to process")

            from ai_engine.tts_detector import get_tts_voice
            if self.settings.get("tts_auto_detect", True):
                voice = get_tts_voice(full_text, getattr(self, 'active_lang', None) or "en-US")
            else:
                voice = self.settings.get("tts_voice", "en-US-JennyNeural")

            # Reading speed → edge_tts rate string. Old code used brittle
            # string equality ("2" never matched the saved "2.0"), so 2x
            # silently fell back to normal speed. Parse as float instead so
            # any speed (1.0/1.5/2.0/2.5/etc.) maps correctly.
            try:
                speed = float(self.settings.get("reading_speed", "1.0"))
            except (ValueError, TypeError):
                speed = 1.0
            # Clamp to edge_tts safe range (it accepts roughly -50%..+200%)
            speed = max(0.5, min(speed, 3.0))
            rate_pct = int(round((speed - 1.0) * 100))
            rate = f"{'+' if rate_pct >= 0 else ''}{rate_pct}%"

            for i, sentence in enumerate(sentences):
                if not self.is_reading or self._tts_session_id != session_id:
                    print("[TTS] Producer Stopped (session changed)")
                    break

                filename = os.path.join(tempfile.gettempdir(), f"stream_{uuid.uuid4().hex}.mp3")
                chunk_voice = voice

                # Retry logic for edge_tts (up to 2 retries with backoff)
                success = False
                for attempt in range(3):
                    try:
                        comm = edge_tts.Communicate(sentence, chunk_voice, rate=rate)
                        await comm.save(filename)
                        success = True
                        break
                    except Exception as e:
                        if attempt < 2:
                            print(f"[TTS] Chunk {i+1} attempt {attempt+1} failed: {e}, retrying...")
                            await asyncio.sleep(1 * (attempt + 1))
                        else:
                            self._log_tts_error(f"TTS chunk {i+1} failed after 3 attempts: {e}")

                if not success:
                    # Show error to user
                    self.after(0, self.show_network_error)
                    continue  # Skip this chunk, try next

                if self.is_reading and self._tts_session_id == session_id:
                    self.playback_queue.put(filename)
                    print(f"[TTS] Produced Chunk {i+1}/{len(sentences)}")
                else:
                    try: os.remove(filename)
                    except OSError: pass

            # Signal End of Stream
            if self.is_reading and self._tts_session_id == session_id:
                self.playback_queue.put(None)

        except Exception as e:
             self._log_tts_error(f"TTS Stream Error: {e}")
             if self._tts_session_id == session_id:
                 self.playback_queue.put(None)

    def play_audio_chunks(self, session_id):
        """CONSUMER: Plays audio files from the queue sequentially (session-aware)"""
        current_file = None
        is_first_chunk = True
        try:
            while self.is_reading and self._tts_session_id == session_id:
                try:
                    # First chunk: longer timeout (edge_tts needs time to generate)
                    # Subsequent chunks: shorter timeout (already in pipeline)
                    timeout = 12 if is_first_chunk else 5
                    file_path = self.playback_queue.get(timeout=timeout)

                    if file_path is None:
                        break  # End of stream signal

                    is_first_chunk = False
                    current_file = file_path
                    if not os.path.exists(current_file):
                        continue

                    # Play via pygame.mixer.music (dedicated for TTS, SFX uses Channel)
                    if not pygame.mixer.get_init(): pygame.mixer.init()
                    pygame.mixer.music.load(current_file)
                    pygame.mixer.music.play()

                    # Wait while playing (check session validity)
                    while self.is_reading and self._tts_session_id == session_id and (pygame.mixer.music.get_busy() or self.is_paused):
                         time.sleep(0.1)

                    # Cleanup after play
                    pygame.mixer.music.unload()
                    try: os.remove(current_file); current_file = None
                    except OSError: pass

                    self.playback_queue.task_done()

                except queue.Empty:
                    continue
                except Exception as e:
                    print(f"[TTS] Playback error: {e}")
                    if current_file:
                        try: os.remove(current_file)
                        except OSError: pass

        except Exception as e:
            self._log_tts_error(f"TTS Consumer Error: {e}")
        finally:
            # Only stop if still the current session (prevents killing newer session)
            if self._tts_session_id == session_id:
                self.stop_reader_internal()

    # ===== SMART STREAMING TTS END =====

    def stop_reader_internal(self):
        """Stops reader and clears Smart Streaming queue"""
        self.is_reading = False
        self.is_paused = False
        
        try: 
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
        except pygame.error: pass
        
        # CLEAR QUEUE (Critical for instant switching)
        if hasattr(self, 'playback_queue'):
            try:
                while not self.playback_queue.empty():
                    try:
                        f = self.playback_queue.get_nowait()
                        if f and os.path.exists(f): os.remove(f)
                        self.playback_queue.task_done()
                    except (OSError, Exception): pass
            except Exception: pass

        # Restore sound button to idle + play icon
        try:
            self.after(0, lambda: self.btn_read.set_state("idle"))
            self.after(0, lambda: self.btn_read.set_icon_mode("play"))
        except tk.TclError: pass
