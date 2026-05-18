"""Window chrome — focus, drag, hover, fullscreen detection.

Win32-heavy plumbing that keeps the floating widget feeling like a
proper Windows tool window:

* **Focus management** — WS_EX_NOACTIVATE so a click on a button
  doesn't yank focus from whatever the user was typing in.
* **Drag handling** — the toolbar background acts as a drag handle.
* **Hover opacity** — bump alpha on mouse-enter, drop on mouse-leave.
* **Fullscreen detection** — poll every 1.5s; hide on fullscreen apps.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import threading
import time
import tkinter as tk

import pyautogui


class WindowChromeMixin:
    """Mixed into VoiceTypingApp — focus / drag / fullscreen / hover."""

    def _set_no_activate(self):
        """Prevent this window from stealing focus when clicked.
        Uses Windows WS_EX_NOACTIVATE extended style."""
        try:
            import ctypes
            from ctypes import wintypes
            GWL_EXSTYLE = -20
            WS_EX_NOACTIVATE = 0x08000000
            WS_EX_APPWINDOW  = 0x00040000
            WS_EX_TOOLWINDOW = 0x00000080

            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style = style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
            style = style & ~WS_EX_APPWINDOW
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
            print("[FOCUS] WS_EX_NOACTIVATE set - widget won't steal focus")
        except Exception as e:
            print(f"[FOCUS] Failed to set NOACTIVATE: {e}")

    def _force_foreground(self, hwnd) -> bool:
        """Reliable SetForegroundWindow that bypasses Windows'
        anti-focus-stealing rule by attaching this thread's input queue
        to the target window's thread. Used by the AI drawer when
        handing focus back to the previously-active app so type_text
        lands in the right window. Returns True on success."""
        if not hwnd:
            return False
        try:
            import ctypes
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            cur_thread = kernel32.GetCurrentThreadId()
            target_thread = user32.GetWindowThreadProcessId(hwnd, None)
            if not target_thread:
                return False
            attached = False
            if target_thread != cur_thread:
                attached = bool(user32.AttachThreadInput(
                    cur_thread, target_thread, True))
            try:
                user32.BringWindowToTop(hwnd)
                ok = bool(user32.SetForegroundWindow(hwnd))
            finally:
                if attached:
                    user32.AttachThreadInput(
                        cur_thread, target_thread, False)
            return ok
        except Exception as e:
            print(f"[FOCUS] _force_foreground failed: {e}")
            return False

    def _toggle_no_activate(self, on: bool) -> bool:
        """Flip the WS_EX_NOACTIVATE bit on this Toplevel and re-apply the
        frame so the change takes effect immediately. Used by AI drawer
        to temporarily allow keyboard focus on its textbox while open,
        then restore the no-steal-focus behaviour on close."""
        try:
            import ctypes
            GWL_EXSTYLE       = -20
            WS_EX_NOACTIVATE  = 0x08000000
            SWP_NOMOVE        = 0x0002
            SWP_NOSIZE        = 0x0001
            SWP_NOZORDER      = 0x0004
            SWP_FRAMECHANGED  = 0x0020
            user32 = ctypes.windll.user32
            hwnd = user32.GetParent(self.winfo_id())
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            new_style = (style | WS_EX_NOACTIVATE) if on \
                else (style & ~WS_EX_NOACTIVATE)
            if new_style != style:
                user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
                user32.SetWindowPos(
                    hwnd, 0, 0, 0, 0, 0,
                    SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER
                    | SWP_FRAMECHANGED)
            return True
        except Exception as e:
            print(f"[FOCUS] toggle NOACTIVATE failed: {e}")
            return False

    def on_hover_enter(self, event):
        self.attributes('-alpha', self.settings["max_opacity"])

    def on_hover_leave(self, event):
        sw = self.settings_window or getattr(self, '_settings_win', None)
        if sw and sw.winfo_exists():
            self.attributes('-alpha', self.settings["max_opacity"])
        else:
            self.attributes('-alpha', self.settings["idle_opacity"])

    def on_press(self, event): 
        self.drag_start["x"] = event.x_root
        self.drag_start["y"] = event.y_root
        self.drag_start["root_x"] = self.winfo_x()
        self.drag_start["root_y"] = self.winfo_y()
        self.is_dragging = False  # Reset flag
        self.drag_started = False  # Track if drag motion started
        
        # Save the currently focused window to restore focus after button click
        try:
            self._previous_foreground = ctypes.windll.user32.GetForegroundWindow()
        except (OSError, AttributeError):
            self._previous_foreground = None

    def on_drag(self, event):
        dx = event.x_root - self.drag_start["x"]
        dy = event.y_root - self.drag_start["y"]
        threshold = 5

        if not self.drag_started and (abs(dx) > threshold or abs(dy) > threshold):
            self.drag_started = True
            self.is_dragging = True
            # Hide dropdown arrows + dismiss any open dropdown so they
            # don't float in the wrong place during/after the drag.
            self._hide_arrows_for_drag()
            self._close_active_dropdown()

        if self.is_dragging:
            x = self.drag_start["root_x"] + dx
            y = self.drag_start["root_y"] + dy
            self.geometry(f"+{x}+{y}")

    def _on_bg_release(self, event):
        """Save position after dragging the toolbar background."""
        if self.is_dragging:
            try:
                self.settings["window_x"] = self.winfo_x()
                self.settings["window_y"] = self.winfo_y()
                self.save_settings()
            except Exception:
                pass
        self.is_dragging = False
        self._show_arrows()

    # ── Dropdown arrow visibility + active-popup management ─────

    def _hide_arrows_for_drag(self):
        try:
            self.frame.itemconfigure("dropdown_arrows", state="hidden")
        except Exception:
            pass

    def _show_arrows(self):
        try:
            self.frame.itemconfigure("dropdown_arrows", state="normal")
        except Exception:
            pass

    def on_release(self, event, cmd):
        # SAVE POSITION after dragging
        if self.is_dragging:
            try:
                new_x = self.winfo_x()
                new_y = self.winfo_y()
                self.settings["window_x"] = new_x
                self.settings["window_y"] = new_y
                self.save_settings()
                print(f"[POSITION] Saved new position: ({new_x}, {new_y})")
            except Exception as e:
                print(f"[WARNING] Failed to save position: {e}")
            self._show_arrows()

        # Only trigger command if not dragging
        if not self.is_dragging:
            cmd()
            # Restore focus to previous window using alt+tab (works better than SetForegroundWindow)
            threading.Thread(target=lambda: (time.sleep(0.02), pyautogui.hotkey('alt', 'tab')), daemon=True).start()

    def is_fullscreen_app_running(self):
        """
        SMART Fullscreen Detection:
        - Returns True when a window covers the ENTIRE screen AND overlaps the taskbar
        - Works for YouTube fullscreen, games, VLC fullscreen, etc.
        """
        try:
            user32 = ctypes.windll.user32
            
            # Get the foreground window
            foreground_hwnd = user32.GetForegroundWindow()
            if not foreground_hwnd:
                return False
            
            # Exclude our own window + pen overlay/toolbar
            try:
                my_hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
                if foreground_hwnd == my_hwnd:
                    return False
                # Exclude ALL pen overlay HWNDs (render + input windows)
                if hasattr(self, '_pen_overlay') and self._pen_overlay:
                    for ph in self._pen_overlay.get_all_hwnds():
                        if foreground_hwnd == ph:
                            return False
                # Exclude pen toolbar HWND (standalone mode only)
                if (hasattr(self, '_pen_toolbar') and self._pen_toolbar
                        and getattr(self._pen_toolbar, '_mode', '') == 'standalone'):
                    tb_hwnd = self._pen_toolbar.get_hwnd()
                    if tb_hwnd and foreground_hwnd == tb_hwnd:
                        return False
            except (tk.TclError, OSError): pass
            
            # Get window class name - exclude desktop/shell
            class_name = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(foreground_hwnd, class_name, 256)
            
            # Always exclude these (desktop, shell, our window)
            always_exclude = ["Progman", "WorkerW", "Shell_TrayWnd", "TkTopLevel", "CTk"]
            if class_name.value in always_exclude:
                return False
            
            # Get screen dimensions (primary monitor)
            screen_width = user32.GetSystemMetrics(0)
            screen_height = user32.GetSystemMetrics(1)
            
            # Get foreground window rect
            rect = ctypes.wintypes.RECT()
            user32.GetWindowRect(foreground_hwnd, ctypes.byref(rect))
            
            window_width = rect.right - rect.left
            window_height = rect.bottom - rect.top
            
            # Check if window covers entire screen
            covers_full_screen = (
                window_width >= screen_width and 
                window_height >= screen_height and
                rect.left <= 0 and 
                rect.top <= 0
            )
            
            if not covers_full_screen:
                return False
            
            # KEY CHECK: Does this window cover the taskbar area?
            taskbar_hwnd = user32.FindWindowW("Shell_TrayWnd", None)
            if taskbar_hwnd:
                taskbar_rect = ctypes.wintypes.RECT()
                user32.GetWindowRect(taskbar_hwnd, ctypes.byref(taskbar_rect))
                
                # If foreground window's bottom extends to or past taskbar top, it's fullscreen
                if rect.bottom >= taskbar_rect.top:
                    print(f"[FULLSCREEN] Detected: {class_name.value}")
                    return True
            
            return False
            
        except Exception as e:
            return False
    
    def monitor_topmost(self):
        """
        Monitor window position and ensure it stays on top.
        AUTO-HIDE when fullscreen apps are running.
        RE-ENFORCE topmost every cycle to prevent going behind other windows.
        """
        try:
            if not self.winfo_exists():
                return

            # Initialize state
            if not hasattr(self, '_hidden_for_fullscreen'):
                self._hidden_for_fullscreen = False

            # If editor is open and visible, skip topmost enforcement
            # (main widget is hidden; editor manages its own window)
            editor_open = (hasattr(self, '_editor_win') and self._editor_win
                           and self._editor_win.winfo_exists()
                           and self._editor_win.winfo_viewable())
            if editor_open:
                self.after(1500, self.monitor_topmost)
                return

            # Always check fullscreen (widget should hide during games/videos)
            try:
                is_fs = self.is_fullscreen_app_running()
                self._handle_fullscreen_result(is_fs)
            except Exception:
                pass

            # RE-ENFORCE topmost: prevent widget from going behind other windows
            if not self._hidden_for_fullscreen:
                pen_active = (hasattr(self, '_pen_overlay') and self._pen_overlay
                              and self._pen_overlay.winfo_exists())

                if pen_active:
                    # Z-order: input < MAIN WIDGET < render
                    # Toolbar is embedded in main widget (no separate Toplevel)
                    try:
                        self._pen_overlay.lift_input()      # Input at bottom
                        self.attributes('-topmost', True)
                        self.lift()                          # Main widget above input
                        self._pen_overlay.lift_render()      # Render above main
                    except tk.TclError:
                        pass
                else:
                    self.attributes('-topmost', True)
                    self.lift()

            self.after(1500, self.monitor_topmost)
        except Exception:
            try:
                self.after(1500, self.monitor_topmost)
            except tk.TclError:
                pass
    
    def _handle_fullscreen_result(self, is_fullscreen):
        """Handle fullscreen detection result on main thread.
        When pen mode is active, NEVER hide - pen should work over fullscreen apps.
        When editor is open, don't restore main widget (it's deliberately hidden)."""
        try:
            # Pen mode overrides fullscreen auto-hide
            pen_active = hasattr(self, '_pen_overlay') and self._pen_overlay is not None

            # If editor is open, don't deiconify main widget
            editor_open = (hasattr(self, '_editor_win') and self._editor_win
                           and self._editor_win.winfo_exists()
                           and self._editor_win.winfo_viewable())

            if is_fullscreen and not pen_active:
                if not self._hidden_for_fullscreen:
                    self._hidden_for_fullscreen = True
                    if not editor_open:
                        self.withdraw()
                    print("[FULLSCREEN] Widget hidden")
            else:
                if self._hidden_for_fullscreen:
                    self._hidden_for_fullscreen = False
                    if not editor_open:
                        self.deiconify()
                        self.attributes('-topmost', True)
                        self.lift()
                    print("[FULLSCREEN] Widget shown")
        except tk.TclError:
            pass
