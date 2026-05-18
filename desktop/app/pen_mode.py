"""Pen-mode lifecycle — toggle, open, close, draw/view mode, animation.

The "pen tools" panel slides out from the left of the toolbar, showing
draw/view/highlighter/eraser/text/handwrite buttons that drive
``ui_components.pen_overlay.PenOverlay``. This mixin owns the
animation, the z-order dance with the editor window, and the screenshot
restore path.

Owned state:
  - _pen_overlay, _pen_toolbar, _editor_win
  - _pen_tools_expanded, _pen_anim_job, _panel_container
"""

from __future__ import annotations

import os
import threading
import time
import tkinter as tk


class PenModeMixin:
    """Mixed into VoiceTypingApp — pen-mode lifecycle + slide animation."""

    def open_editor_window(self):
        """Open the built-in editor window.
        Closes pen overlay first (its fullscreen input_win blocks editor).
        Restores previous session if available."""
        # Always close embedded pen panel first (even if editor already exists)
        self._close_pen_mode_immediate()

        if hasattr(self, '_editor_win') and self._editor_win is not None:
            try:
                if self._editor_win.winfo_exists():
                    self._editor_win.deiconify()
                    self._editor_win.lift()
                    # Show toolbar if hidden
                    if hasattr(self._editor_win, '_show_toolbar'):
                        self._editor_win._show_toolbar()
                    # Restart auto-save if stopped
                    if not self._editor_win._autosave_job:
                        self._editor_win._schedule_autosave()
                    # Re-apply user-edited shortcuts so toggle/hotkey changes
                    # made while editor was hidden take effect now.
                    try:
                        if hasattr(self._editor_win, '_apply_shortcuts'):
                            self._editor_win.after(50, self._editor_win._apply_shortcuts)
                    except Exception as e:
                        print(f"[EDITOR] re-apply shortcuts failed: {e}")
                    # Hide main widget - editor has all controls
                    self.withdraw()
                    return
            except tk.TclError:
                pass

        from ui.editor_window import EditorWindow, SESSION_FILE
        # Pass None as parent so editor is independent Toplevel
        # (otherwise withdraw() on main widget hides editor too)
        self._editor_win = EditorWindow(None, self)
        # Restore previous session if exists
        if os.path.exists(SESSION_FILE):
            try:
                self._editor_win._load_dvai(SESSION_FILE)
            except Exception as e:
                print(f"[EDITOR] Session restore failed: {e}")
        # Hide main widget - editor toolbar has all controls
        self.withdraw()

    def toggle_pen_mode(self):
        """Toggle pen mode: off → draw → view (click-through) → draw → ..."""
        # If editor is open AND visible, bring it to focus instead of pen overlay
        if hasattr(self, '_editor_win') and self._editor_win is not None:
            try:
                if (self._editor_win.winfo_exists()
                        and self._editor_win.winfo_viewable()):
                    self._editor_win.lift()
                    if hasattr(self._editor_win, '_show_toolbar'):
                        self._editor_win._show_toolbar()
                    return
            except tk.TclError:
                pass

        if not hasattr(self, '_pen_overlay') or self._pen_overlay is None:
            # No overlay → create and enter draw mode
            self._open_pen_mode()
        elif self._pen_overlay.is_click_through:
            # View mode → switch to draw mode
            self._pen_set_draw_mode()
        else:
            # Draw mode → switch to view mode (strokes stay)
            self._pen_set_view_mode()

    def _open_pen_mode(self):
        """Open pen overlay + embedded toolbar (slide-out), enter draw mode."""
        try:
            from ui_components.pen_overlay import PenOverlay
            from ui_components.pen_toolbar import PenToolbar

            self._pen_overlay = PenOverlay(self, on_close_callback=self._close_pen_mode)
            preset = self.settings.get("size_preset", "medium")
            btn_s_now = self.BTN_SIZES.get(preset, 72)
            self._pen_toolbar = PenToolbar(
                self._panel_container,  # parent = panel container frame
                self._pen_overlay,
                self,
                mode="embedded",
                on_retract=self._retract_pen_tools,
                scale=btn_s_now / 72.0,
            )

            # Main toolbar: pen icon → mouse icon
            self.btn_pen.configure(text="\U0001f5b1\ufe0f")
            self._animate_tools_open()
            self.after(200, self._pen_ensure_topmost)
            print("[PEN] Pen mode opened (draw)")
        except Exception as e:
            # ``print`` goes to NullWriter in --windowed EXE, so the
            # user can't see why pen mode failed to open. Persist the
            # full traceback to %APPDATA%/DualVoicer/pen_error.log so
            # we have something to diagnose from in production.
            self._log_pen_error(f"_open_pen_mode failed: {e}")
            print(f"[PEN] Failed to open: {e}")
            import traceback; traceback.print_exc()
            self._pen_overlay = None
            self._pen_toolbar = None

    def _log_pen_error(self, message: str) -> None:
        """Write pen-mode failures to %APPDATA%/DualVoicer/pen_error.log.

        Mirrors the TTSMixin._log_tts_error pattern. We need this
        because --windowed EXE silences ``print`` (NullWriter), so any
        exception in the pen-mode open/close path is otherwise invisible
        to the user.
        """
        try:
            import datetime
            import traceback
            log_path = os.path.join(
                os.environ.get('APPDATA', os.path.expanduser('~')),
                'DualVoicer',
                'pen_error.log',
            )
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(f"\n[{datetime.datetime.now()}] {message}\n")
                f.write(traceback.format_exc())
        except OSError:
            pass

    def _pen_set_draw_mode(self):
        """Switch to draw mode (pen captures events)."""
        if self._pen_overlay:
            self._pen_overlay.set_click_through(False)
            self.btn_pen.configure(text="\U0001f5b1\ufe0f")
            if self._pen_toolbar:
                self._pen_toolbar.sync_draw_mode()

    def _pen_set_view_mode(self):
        """Switch to view mode (click-through, strokes stay)."""
        if self._pen_overlay:
            self._pen_overlay.set_click_through(True)
            self.btn_pen.configure(text="\U0001f58a\ufe0f")
            if self._pen_toolbar:
                self._pen_toolbar.sync_view_mode()

    # ── Pen tools slide-out animation ───────────────────

    def _animate_tools_open(self):
        """Slide tools panel out from RIGHT edge - left edge stays fixed."""
        preset = self.settings.get("size_preset", "medium")
        btn_s = self.BTN_SIZES.get(preset, 72)
        base_w, h = self._calc_dims(btn_s)
        panel_w = self._calc_tools_panel_w(btn_s)
        target_w = base_w + panel_w

        # Position stays fixed - panel grows rightward
        wx, wy = self.winfo_x(), self.winfo_y()

        # Off-screen check — use the bounds of the monitor the widget
        # is CURRENTLY on, not winfo_screenwidth() (which only returns
        # the primary monitor's width on Windows). Without this the
        # widget would teleport to the primary monitor whenever the
        # user opened pen mode while it was on a secondary monitor.
        mon_left, mon_right = self._get_current_monitor_bounds(wx, wy)

        if wx + target_w > mon_right:
            wx = max(mon_left, mon_right - target_w)

        # Place pen toolbar frame (already child of _panel_container)
        tools_frame = self._pen_toolbar.get_root_widget()
        tools_frame.pack(fill="both", expand=True)
        self._panel_container.configure(width=1, height=h)
        self._panel_container.pack_propagate(False)
        self._panel_container.pack(side="right", fill="y")

        self._pen_tools_expanded = True
        steps = 8
        step_pw = panel_w / steps

        def _step(i, pw_so_far):
            if i >= steps:
                self._panel_container.configure(width=panel_w)
                self.geometry(f"{target_w}x{h}+{wx}+{wy}")
                # Open animation done — now measure actual toolbar width and
                # tighten the container so there's no gap on the right.
                self.after(40, self._refit_panel_to_toolbar)
                return
            pw_so_far += step_pw
            pw_int = int(pw_so_far)
            self._panel_container.configure(width=pw_int)
            self.geometry(f"{base_w + pw_int}x{h}+{wx}+{wy}")
            self._pen_anim_job = self.after(16, lambda: _step(i + 1, pw_so_far))

        _step(0, 0.0)

    def _animate_tools_close(self, on_done=None):
        """Retract tools panel from RIGHT - left edge stays fixed."""
        preset = self.settings.get("size_preset", "medium")
        btn_s = self.BTN_SIZES.get(preset, 72)
        base_w, h = self._calc_dims(btn_s)
        panel_w = self._calc_tools_panel_w(btn_s)

        wx, wy = self.winfo_x(), self.winfo_y()  # Position stays fixed
        steps = 8
        step_pw = panel_w / steps

        def _step(i, pw_remaining):
            if i >= steps:
                self._panel_container.pack_forget()
                self._pen_tools_expanded = False
                self.geometry(f"{base_w}x{h}+{wx}+{wy}")
                if on_done:
                    on_done()
                return
            pw_remaining -= step_pw
            pw_int = max(1, int(pw_remaining))
            self._panel_container.configure(width=pw_int)
            self.geometry(f"{base_w + pw_int}x{h}+{wx}+{wy}")
            self._pen_anim_job = self.after(16, lambda: _step(i + 1, pw_remaining))

        _step(0, float(panel_w))

    def _retract_pen_tools(self):
        """Called when embedded toolbar Close is clicked - retract + cleanup."""
        def _after_retract():
            if hasattr(self, '_pen_toolbar') and self._pen_toolbar:
                try:
                    self._pen_toolbar.destroy()
                except Exception:
                    pass
                self._pen_toolbar = None
            if hasattr(self, '_pen_overlay') and self._pen_overlay:
                try:
                    self._pen_overlay.destroy()
                except Exception:
                    pass
                self._pen_overlay = None
            self.btn_pen.configure(text="\U0001f58a\ufe0f")
            print("[PEN] Pen mode closed (retracted)")

        self._animate_tools_close(on_done=_after_retract)

    def _close_pen_mode(self):
        """Close pen overlay + toolbar with retract animation."""
        try:
            if getattr(self, '_pen_tools_expanded', False):
                self._retract_pen_tools()
            else:
                # Fallback (standalone mode or already retracted)
                if hasattr(self, '_pen_toolbar') and self._pen_toolbar:
                    try:
                        self._pen_toolbar.destroy()
                    except Exception:
                        pass
                    self._pen_toolbar = None
                if hasattr(self, '_pen_overlay') and self._pen_overlay:
                    try:
                        self._pen_overlay.destroy()
                    except Exception:
                        pass
                    self._pen_overlay = None
                self.btn_pen.configure(text="\U0001f58a\ufe0f")
                print("[PEN] Pen mode closed")
        except Exception as e:
            print(f"[PEN] Error closing: {e}")

    def _close_pen_mode_immediate(self):
        """Close pen overlay + toolbar immediately (no animation).
        Used when editor needs to open right away."""
        try:
            # Cancel any running animation
            if self._pen_anim_job:
                try:
                    self.after_cancel(self._pen_anim_job)
                except Exception:
                    pass
                self._pen_anim_job = None

            # Destroy toolbar
            if hasattr(self, '_pen_toolbar') and self._pen_toolbar:
                try:
                    self._pen_toolbar.destroy()
                except Exception:
                    pass
                self._pen_toolbar = None

            # Destroy overlay
            if hasattr(self, '_pen_overlay') and self._pen_overlay:
                try:
                    self._pen_overlay.destroy()
                except Exception:
                    pass
                self._pen_overlay = None

            # Restore panel + window size immediately
            if getattr(self, '_pen_tools_expanded', False):
                self._panel_container.pack_forget()
                self._pen_tools_expanded = False
                preset = self.settings.get("size_preset", "medium")
                btn_s = self.BTN_SIZES.get(preset, 72)
                base_w, h = self._calc_dims(btn_s)
                wx, wy = self.winfo_x(), self.winfo_y()
                # Clamp the post-close position to the visible bounds
                # of the monitor under the widget. Without this, on a
                # mixed-DPI multi-monitor setup the widget can end up
                # off-screen on the right edge of a smaller secondary
                # monitor after collapsing.
                mon_left, mon_right = self._get_current_monitor_bounds(wx, wy)
                if wx + base_w > mon_right:
                    wx = max(mon_left, mon_right - base_w)
                self.geometry(f"{base_w}x{h}+{wx}+{wy}")

            self.btn_pen.configure(text="\U0001f58a\ufe0f")
            self.update_idletasks()  # Force tkinter to process all pending destroys
            print("[PEN] Pen mode closed (immediate)")
        except Exception as e:
            print(f"[PEN] Error closing immediate: {e}")

    def _pen_ensure_topmost(self):
        """Ensure correct z-order: input < main widget < render.
        Toolbar is always embedded (no separate Toplevel)."""
        try:
            if hasattr(self, '_pen_overlay') and self._pen_overlay and self._pen_overlay.winfo_exists():
                self._pen_overlay.lift_input()
                self.lift()
                self._pen_overlay.lift_render()
        except tk.TclError:
            pass

    def _get_current_monitor_bounds(self, x: int, y: int) -> tuple[int, int]:
        """Return (left, right) screen-X bounds of the monitor that
        contains point ``(x, y)``.

        Single source of truth for both ``_animate_tools_open`` and
        ``_close_pen_mode_immediate`` — the pen-mode-open and pen-mode-
        close paths used to apply different (or no) monitor-aware
        clamping, which let the widget teleport across monitors on
        close in mixed-DPI multi-monitor setups. Centralising the
        lookup here keeps both paths consistent.

        Falls back to ``(0, winfo_screenwidth())`` (i.e. primary
        monitor) if the Win32 query fails — safer than crashing the
        pen-mode lifecycle on multi-monitor edge cases.
        """
        try:
            import ctypes
            from ctypes import byref, wintypes

            class _PT(ctypes.Structure):
                _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

            class _RECT(ctypes.Structure):
                _fields_ = [
                    ("left",   wintypes.LONG),
                    ("top",    wintypes.LONG),
                    ("right",  wintypes.LONG),
                    ("bottom", wintypes.LONG),
                ]

            class _MI(ctypes.Structure):
                _fields_ = [
                    ("cbSize",    wintypes.DWORD),
                    ("rcMonitor", _RECT),
                    ("rcWork",    _RECT),
                    ("dwFlags",   wintypes.DWORD),
                ]

            MONITOR_DEFAULTTONEAREST = 2
            user32 = ctypes.windll.user32
            hmon = user32.MonitorFromPoint(_PT(x, y), MONITOR_DEFAULTTONEAREST)
            mi = _MI()
            mi.cbSize = ctypes.sizeof(_MI)
            user32.GetMonitorInfoW(hmon, byref(mi))
            return mi.rcMonitor.left, mi.rcMonitor.right
        except Exception:
            return 0, self.winfo_screenwidth()

