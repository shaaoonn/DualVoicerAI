"""Tray icon + button-hover micro-animations.

Lifts two small clusters of methods out of main.py:

* **Tray icon** (init_tray_icon, withdraw_to_tray, show_from_tray,
  quit_app_tray) — the pystray bridge that lets the user hide the
  widget into the system tray and bring it back via right-click menu.
* **Hover/press animations** (on_button_hover_enter / _leave,
  animate_button_press, on_settings_hover_enter / _leave) — the 5%-up,
  95%-down scale tweaks on the four main spectrum buttons and the
  settings cog. Lives here because it's small, isolated, and largely
  visual fluff.

Together they're ~70 lines — tiny mixin, but worth its own file
because the methods don't naturally belong to any larger subsystem.
"""

from __future__ import annotations

import tkinter as tk

import pystray
from PIL import Image
from pystray import MenuItem as item


class TrayMixin:
    """Mixed into VoiceTypingApp — tray icon menu + button hover animations."""

    def init_tray_icon(self):
        try:
            image = Image.open(self.icon_path)
            menu = (item('Show', self.show_from_tray), item('Exit', self.quit_app_tray))
            self.tray_icon = pystray.Icon("DV", image, "Dual Voicer", menu)
            self.tray_icon.run()
        except Exception: pass

    def withdraw_to_tray(self):
        # Tear down any open dropdown so its CTkToplevel doesn't linger
        # while the main window is hidden.
        self._close_active_dropdown()
        self.withdraw()

    def show_from_tray(self,i,m): 
        self.settings["show_desktop_icon"] = True
        self.after(0,self.deiconify)
        self.after(0,self.lift)

    def quit_app_tray(self,i,m): self.tray_icon.stop(); self.shutdown_flag.set(); self.quit()

    def on_button_hover_enter(self, event, button, original_size):
        """Animate button scale up on hover for micro-interaction UX"""
        try:
            # Scale up by 5% (reduced from 10% to prevent clipping)
            new_w = int(original_size[0] * 1.05)
            new_h = int(original_size[1] * 1.05)
            button.configure(width=new_w, height=new_h)
            
            # Update image size if exists
            if hasattr(button, 'cget') and button.cget('image'):
                img = button.cget('image')
                if hasattr(img, 'configure'):
                    img.configure(size=(new_w, new_h))
            
            # Special handling for sound button - also scale settings icon
            if button == getattr(self, 'btn_read', None):
                if hasattr(self, 'btn_settings'):
                    settings_w = int(20 * 1.05)
                    self.btn_settings.configure(width=settings_w, height=settings_w)
        except tk.TclError: pass

    def on_button_hover_leave(self, event, button, original_size):
        """Restore button to original size on hover leave"""
        try:
            button.configure(width=original_size[0], height=original_size[1])
            
            # Restore image size
            if hasattr(button, 'cget') and button.cget('image'):
                img = button.cget('image')
                if hasattr(img, 'configure'):
                    img.configure(size=original_size)
            
            # Special handling for sound button - restore settings icon
            if button == getattr(self, 'btn_read', None):
                if hasattr(self, 'btn_settings'):
                    self.btn_settings.configure(width=20, height=20)
        except tk.TclError: pass

    def animate_button_press(self, button, original_size):
        """Quick press animation - shrink then restore"""
        try:
            # Shrink to 95%
            shrink_w = int(original_size[0] * 0.95)
            shrink_h = int(original_size[1] * 0.95)
            button.configure(width=shrink_w, height=shrink_h)
            
            # Restore after 100ms
            self.after(100, lambda: button.configure(width=original_size[0], height=original_size[1]))
        except tk.TclError: pass

    def on_settings_hover_enter(self, event):
        """Settings icon gets extra big when hovered (on top of sound hover effect)"""
        try:
            # Settings goes to 110% (extra 5% on top of sound's 5%)
            self.btn_settings.configure(width=24, height=24)
        except tk.TclError: pass

    def on_settings_hover_leave(self, event):
        """Restore settings to sound hover size (not original - sound might still be hovered)"""
        try:
            # Back to 105% (sound hover size)
            self.btn_settings.configure(width=21, height=21)
        except tk.TclError: pass
