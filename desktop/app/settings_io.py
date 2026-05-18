"""Settings I/O + toast/popup helpers.

Cluster of methods that persist user preferences, open the Settings
panel + Instructions window, and show short-lived user feedback
(toasts, error popups, network warning).

The Settings panel UI itself lives in ``ui/settings_panel.py`` — this
mixin is just the entry point + the dozens of tiny callback handlers
that the panel's sliders / switches / dropdowns invoke when the user
changes a setting. Each writes to ``self.settings`` and calls
``save_settings()`` to persist.
"""

from __future__ import annotations

import json
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from i18n import tr


class SettingsIOMixin:
    """Mixed into VoiceTypingApp — settings persistence + toast/popup helpers."""

    def _cache_microphones(self):
        """Cache microphone list in background for fast settings panel loading"""
        try:
            import pyaudio
            p = pyaudio.PyAudio()
            mic_list = ["Default Microphone"]
            mic_map = {"Default Microphone": None}
            
            counter = 1
            for i in range(p.get_device_count()):
                dev = p.get_device_info_by_index(i)
                if dev.get('maxInputChannels') <= 0: continue
                
                name = dev.get('name')
                try:
                    if isinstance(name, bytes): name = name.decode('utf-8', 'ignore')
                except UnicodeDecodeError: pass
                
                lower_name = name.lower()
                if any(x in lower_name for x in ["mapper", "primary sound", "stereo mix", "speaker", "output", "hands-free"]):
                    continue
                if dev.get('hostApi') != 0: continue
                
                label = f"{counter}. {name}"
                mic_list.append(label)
                mic_map[label] = i
                counter += 1
            
            p.terminate()
            self._cached_mic_list = mic_list
            self._cached_mic_map = mic_map
            print(f"[INFO] Cached {len(mic_list)} microphones")
        except Exception as e:
            print(f"[ERROR] Mic cache: {e}")

    def _show_ai_error(self, message: str):
        from config import APP_NAME
        messagebox.showwarning(APP_NAME, message)

    def _show_lock_popup(self, message: str):
        import webbrowser
        popup = ctk.CTkToplevel(self)
        popup.geometry("380x160")
        popup.title("\u09b8\u09be\u09ac\u09b8\u09cd\u0995\u09cd\u09b0\u09bf\u09aa\u09b6\u09a8 \u09aa\u09cd\u09b0\u09df\u09cb\u099c\u09a8")
        popup.attributes("-topmost", True)
        ctk.CTkLabel(popup, text=message, font=("Segoe UI", 12),
                     wraplength=340, justify="center").pack(pady=20)
        ctk.CTkButton(popup, text="\u09b8\u09be\u09ac\u09b8\u09cd\u0995\u09cd\u09b0\u09be\u0987\u09ac \u0995\u09b0\u09c1\u09a8",
                      command=lambda: [webbrowser.open("https://ejobsit.com/ai-voice"),
                                       popup.destroy()]).pack(pady=4)
        ctk.CTkButton(popup, text="\u09ac\u09be\u09a4\u09bf\u09b2", fg_color="#333333",
                      command=popup.destroy).pack()
        popup.after(8000, popup.destroy)

    def open_settings_panel(self):
        from ui.settings_panel import SettingsPanel
        if self._settings_win is None or not self._settings_win.winfo_exists():
            self._settings_win = SettingsPanel(parent=self, app_ref=self)
            self._settings_win.attributes("-topmost", True)
        self._settings_win.focus()
        self._settings_win.lift()

    def show_instructions(self):
        txt = tr("instructions_text")
        # Legacy hardcoded text replaced by tr("instructions_text") - see desktop/i18n.py
        info_win = ctk.CTkToplevel(self)
        info_win.title(tr("instructions_window_title"))
        info_win.attributes('-topmost', True)  # Set topmost first
        
        # Position to the RIGHT of settings window
        if self.settings_window and self.settings_window.winfo_exists():
            try:
                # Position to the right side of settings window
                x = self.settings_window.winfo_x() + self.settings_window.winfo_width() + 10
                y = self.settings_window.winfo_y()
                info_win.geometry(f"500x750+{x}+{y}")
            except tk.TclError:
                info_win.geometry("500x750")
        else:
            info_win.geometry("500x750")

        info_win.resizable(False, False)
        info_win.lift()  # Bring to front
        info_win.focus_force()  # Take focus
        
        # Schedule another lift to ensure it stays on top
        info_win.after(100, lambda: info_win.lift())

        try: info_win.iconbitmap(self.icon_path)
        except tk.TclError: pass
        
        # Header with Logo
        head_frame = ctk.CTkFrame(info_win, fg_color="transparent")
        head_frame.pack(pady=(15, 10))
        
        try:
            if self.icon_path:
                from PIL import Image
                img = Image.open(self.icon_path)
                logo_img = ctk.CTkImage(light_image=img, dark_image=img, size=(50, 50))
                ctk.CTkLabel(head_frame, text="", image=logo_img).pack(side="left", padx=10)
        except (OSError, tk.TclError): pass

        l = ctk.CTkLabel(head_frame, text="ডুয়েল ভয়েসার গাইডলাইন", font=("Segoe UI", 18, "bold"), text_color="#f39c12")
        l.pack(side="left")
        
        textbox = ctk.CTkTextbox(info_win, font=("Segoe UI", 13), text_color="#ecf0f1", fg_color="#2c3e50")
        textbox.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        textbox.insert("0.0", txt)
        textbox.configure(state="disabled")

    def toggle_desktop_visibility(self):
        val = bool(self.desk_switch.get())
        self.settings["show_desktop_icon"] = val
        if val: self.deiconify()
        else: self.withdraw()
        self.save_settings()  # Auto-save on toggle

    def save_settings(self):
        """Save all settings to AppData file"""
        try:
            if hasattr(self, 'settings_file'):
                with open(self.settings_file, 'w', encoding='utf-8') as f:
                    json.dump(self.settings, f, indent=2, ensure_ascii=False)
            # Update button labels after save
            self.after(0, self.update_button_labels)
        except Exception as e:
            print(f"[WARNING] Failed to save settings: {e}")


    def reset_engine_with_feedback(self):
        """User-facing reset (called from Settings → Reset Engine button).
        Runs the silent reset and pops a small toast so the user knows it
        actually happened - otherwise the click feels like nothing changed."""
        ok = self._silent_reset()
        # Show a tiny toast next to the widget so the user sees feedback
        try:
            self._show_toast(
                "✓ Engine reset" if ok else "⚠ Reset busy - try again",
                color=("#1A5A1A" if ok else "#8B5A20"))
        except Exception as e:
            print(f"[reset toast] {e}")

    def _show_toast(self, text: str, color: str = "#1A5A1A", duration_ms: int = 1400):
        """Floating non-blocking toast near the widget. Self-dismissing."""
        try:
            toast = ctk.CTkToplevel(self)
            toast.overrideredirect(True)
            toast.attributes('-topmost', True)
            toast.configure(fg_color=color)
            wx, wy, wh = self.winfo_x(), self.winfo_y(), self.winfo_height()
            toast.geometry(f"220x32+{wx}+{wy + wh + 6}")
            ctk.CTkLabel(toast, text=text, text_color="white",
                         fg_color=color, font=("Segoe UI", 12, "bold"),
                         height=32, corner_radius=8).pack(fill="both", expand=True)
            def _dismiss():
                try: toast.destroy()
                except tk.TclError: pass
            toast.after(duration_ms, _dismiss)
        except tk.TclError:
            pass

    def close_settings(self):
        self.save_settings()
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.destroy()
        if hasattr(self, '_settings_win') and self._settings_win and self._settings_win.winfo_exists():
            self._settings_win.destroy()
        try: self.on_hover_leave(None)
        except Exception: pass

    def update_max_opacity(self, v):
        self.settings["max_opacity"] = v
        self.attributes('-alpha', v)
        self.save_settings()

    def update_idle_opacity(self, v):
        self.settings["idle_opacity"] = v
        self.save_settings()
    
    def toggle_sound(self):
        """Apply sound-effect toggle. Settings dict is already updated by the
        settings panel from the switch's var.get() - we only persist + log."""
        self.save_settings()
        print(f"[SETTINGS] Sound {'enabled' if self.settings.get('sound_enabled', True) else 'disabled'}")

    def toggle_labels(self):
        """Toggle button label visibility"""
        show = self.settings.get("show_labels", True)
        for btn in [self.btn_bn, self.btn_en, self.btn_read, self.btn_ai]:
            btn.set_labels_visible(show)
        self.save_settings()
    
    def update_timeout(self, v):
        self.settings["auto_timeout"] = "99999" if v == "∞" else v
        self.save_settings()

    def update_speed(self, v):
        self.settings["reading_speed"] = v
        self.save_settings()

    def update_noise_threshold(self, v):
        """Update noise filter threshold (slider callback)"""
        threshold = int(v)
        self.settings["noise_threshold"] = threshold
        
        # Update label in real-time
        if hasattr(self, 'noise_label'):
            self.noise_label.configure(text=str(threshold))
        
        # Apply new settings immediately
        self.apply_mic_sensitivity()
        self.save_settings()
        print(f"[SETTINGS] Noise threshold changed to: {threshold}")

    def show_network_error(self):
        # Prevent stacking multiple notifications
        if getattr(self, '_network_toast_showing', False):
            return
        self._network_toast_showing = True

        try:
            # Create floating toast notification near widget
            toast = ctk.CTkToplevel(self)
            toast.overrideredirect(True)
            toast.attributes('-topmost', True)
            toast.configure(fg_color="#e74c3c")

            # Position near widget
            wx = self.winfo_x()
            wy = self.winfo_y()
            wh = self.winfo_height()
            toast.geometry(f"200x30+{wx}+{wy + wh + 5}")

            label = ctk.CTkLabel(toast, text="⚠ No Internet", text_color="white",
                                 fg_color="#e74c3c", font=("Segoe UI", 12, "bold"),
                                 height=30, corner_radius=8)
            label.pack(fill="both", expand=True)

            # Auto-dismiss after 1.5 seconds
            def dismiss():
                try:
                    toast.destroy()
                except tk.TclError: pass
                self._network_toast_showing = False

            toast.after(1500, dismiss)
        except tk.TclError:
            self._network_toast_showing = False
