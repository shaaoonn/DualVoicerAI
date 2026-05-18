"""Screenshot capture + AI-button glow effect.

The pen toolbar / hotkey triggers Windows' snip tool, then we poll
the clipboard for the resulting image. When one shows up we encode it
as base64 and stash it so the next AI button click routes through the
vision flow instead of the text flow.

The glow effect is a short visual cue on the AI button that confirms
"hey, your screenshot is captured and ready to send to AI".
"""

from __future__ import annotations

import datetime
import os
import threading
import time
import tkinter as tk

import pyautogui


class ScreenshotMixin:
    """Mixed into VoiceTypingApp — screenshot capture + glow effect."""

    def take_screenshot(self, on_complete=None):
        """Trigger Windows Snipping Tool, save clipboard image for AI analysis.
        In pen mode: temporarily make overlay click-through so snip tool works,
        and keep render window visible so drawings appear in screenshot.

        Args:
            on_complete: Optional callable. Invoked on the Tk main thread when
                         the snip session ends — whether the user captured an
                         image OR cancelled and the 15s poll timed out. Used
                         by the editor to restore its previous tool.
        """
        if self.is_reading:
            self._pause_reader()

        # In pen mode, make input window click-through so snipping tool works
        pen_was_drawing = False
        if (hasattr(self, '_pen_overlay') and self._pen_overlay and
                self._pen_overlay.winfo_exists()):
            if not self._pen_overlay.is_click_through:
                pen_was_drawing = True
                self._pen_overlay.set_click_through(True)

        # Snapshot the previous screenshot so the polling loop can ignore
        # stale clipboard data left over from a prior capture. Without this,
        # a 2nd `take_screenshot()` call sees the OLD image still sitting in
        # the clipboard and "captures" it instantly — firing on_complete
        # before the user has even drawn the new selection.
        prev_b64 = getattr(self, "_last_screenshot_b64", None)

        pyautogui.hotkey('win', 'shift', 's')

        self._screenshot_pending = True

        def _capture_after_snip():
            """Poll clipboard for image (up to 15s), then save for AI."""
            from PIL import ImageGrab
            import io, base64

            captured = False
            # Poll clipboard every 0.5s for up to 15 seconds
            for _ in range(30):
                time.sleep(0.5)
                try:
                    img = ImageGrab.grabclipboard()
                    if img:
                        buf = io.BytesIO()
                        img.save(buf, format='PNG')
                        buf.seek(0)
                        b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
                        new_data_url = f"data:image/png;base64,{b64}"
                        # Skip the leftover image from the previous snip —
                        # only accept a genuinely new clipboard image.
                        if new_data_url == prev_b64:
                            continue
                        self._last_screenshot_b64 = new_data_url
                        self._last_screenshot_time = time.time()
                        print("[SCREENSHOT] Captured for AI analysis")
                        captured = True

                        # Show AI button glow (10s countdown)
                        self.after(0, self._start_screenshot_glow)

                        # If the AI drawer is currently open, push the
                        # screenshot straight into its image slot so
                        # the user can immediately add a prompt and
                        # hit Send. If the drawer is closed it'll be
                        # picked up next time the user opens it (see
                        # _toggle_ai_drawer's pending_image_b64 path).
                        self.after(0, self._push_screenshot_to_drawer,
                                   new_data_url)

                        # Save to folder if configured
                        save_dir = self.settings.get("screenshot_save_dir", "").strip()
                        if save_dir and os.path.isdir(save_dir):
                            fname = datetime.datetime.now().strftime("screenshot_%Y%m%d_%H%M%S.png")
                            path = os.path.join(save_dir, fname)
                            img.save(path)
                            print(f"[SCREENSHOT] Saved: {path}")
                        break
                except (OSError, Exception):
                    pass
            if not captured:
                print("[SCREENSHOT] No image captured after 15s")

            # Restore pen draw mode if it was active
            if pen_was_drawing:
                self.after(0, lambda: self._pen_restore_after_screenshot())

            self._screenshot_pending = False

            # Notify caller (e.g. editor) that snip session is over so it can
            # restore its own state (active tool, cursor, etc.)
            if on_complete is not None:
                try:
                    self.after(0, on_complete)
                except Exception as e:
                    print(f"[SCREENSHOT] on_complete failed: {e}")

        threading.Thread(target=_capture_after_snip, daemon=True).start()

    def _pen_restore_after_screenshot(self):
        """Restore pen draw mode after screenshot capture."""
        if (hasattr(self, '_pen_overlay') and self._pen_overlay and
                self._pen_overlay.winfo_exists()):
            self._pen_overlay.set_click_through(False)
            if hasattr(self, '_pen_toolbar') and self._pen_toolbar:
                self._pen_toolbar.sync_draw_mode()

    def _start_screenshot_glow(self):
        """Bright glow on AI button for 10 seconds to indicate screenshot ready."""
        self._screenshot_glow_active = True
        self.btn_ai.set_glow(True)
        # Auto-expire after 10 seconds
        self.after(10000, self._stop_screenshot_glow)

    def _stop_screenshot_glow(self):
        """Stop AI button glow and expire screenshot."""
        self._screenshot_glow_active = False
        self.btn_ai.set_glow(False)
        # Expire screenshot after 10s
        if (hasattr(self, '_last_screenshot_time') and
                time.time() - self._last_screenshot_time >= 10):
            self._last_screenshot_b64 = None
