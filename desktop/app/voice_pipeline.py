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

import threading
import time
import tkinter as tk

import pyautogui
import pyperclip


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
