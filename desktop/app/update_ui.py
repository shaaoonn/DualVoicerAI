"""Update UI mixin — Settings → "Check for Update" subsystem.

The Settings panel has a single button that walks the user through:
**Check** → **Download** (with progress bar) → **Install** (launches the
installer EXE then quits). The actual HTTP / version / checksum logic
lives in ``updater.py``; this mixin is the UI side of that flow plus a
notification helper used by the background update poller.

Method discipline:

* No ``__init__``. Pure method collection.
* Reaches into ``self.btn_check_update``, ``self.update_status_label``,
  ``self.update_progress`` — Tk widgets created by SettingsPanel.
* Reaches into ``self.after`` (CTk) for thread→UI marshalling.
* Imports ``APP_VERSION`` / ``UPDATE_REPO_URL`` from ``app.constants``
  and ``format_size`` from ``app.helpers`` rather than re-importing
  through main.py.
"""

from __future__ import annotations

import os
import threading
import tkinter as tk
from tkinter import messagebox

from app.constants import APP_VERSION, UPDATE_REPO_URL
from app.helpers import format_size
from updater import UpdateChecker, UpdateDownloader, UpdateInstaller


try:
    import winsound  # type: ignore
    _HAS_WINSOUND = True
except ImportError:
    _HAS_WINSOUND = False


class UpdateUIMixin:
    """Mixed into VoiceTypingApp — handles Settings → Check for Update flow."""

    def handle_update_ready(self, version, file_path, notes):
        """Called from background thread when update is ready"""
        def show_popup():
            try:
                # Play notification sound if possible
                try: winsound.MessageBeep(winsound.MB_ICONASTERISK)
                except Exception: pass
                
                msg = f"🎉 New Update Ready! (v{version})\n\nIt has been downloaded in the background.\nWould you like to install it now?"
                if messagebox.askyesno("Update Ready", msg):
                    UpdateInstaller.install_update(file_path)
            except Exception as e:
                print(f"[ERROR] Update popup failed: {e}")
                
        # Schedule on main thread
        self.after(0, show_popup)

    def check_for_update(self):
        """Check for software updates from GitHub"""
        try:
            # Disable button during check
            self.btn_check_update.configure(state="disabled", text="⏳ Checking...")
            self.update_status_label.configure(text="Connecting to update server...", text_color="#f39c12")
            
            # Create update checker
            checker = UpdateChecker(APP_VERSION, UPDATE_REPO_URL)
            
            # Check for updates in background
            def check_thread():
                result = checker.check_for_updates()
                self.after(0, lambda: self.handle_update_check_result(result))
            
            threading.Thread(target=check_thread, daemon=True).start()
            
        except Exception as e:
            print(f"[ERROR] Update check failed: {e}")
            self.btn_check_update.configure(state="normal", text="🔄 Check for Update")
            self.update_status_label.configure(
                text=f"Update check failed: {str(e)}", 
                text_color="#e74c3c"
            )
    
    def handle_update_check_result(self, result):
        """Handle the result of update check"""
        try:
            if result.get("available"):
                # New version available
                new_version = result.get("version")
                release_notes = result.get("release_notes", "New update available")
                download_url = result.get("download_url")
                
                self.update_status_label.configure(
                    text=f"🎉 New version {new_version} available!", 
                    text_color="#27ae60"
                )
                
                # Change button to download
                self.btn_check_update.configure(
                    state="normal",
                    text=f"⬇ Download Version {new_version}",
                    fg_color="#27ae60",
                    hover_color="#229954",
                    command=lambda: self.download_update(download_url, new_version)
                )
                
                # Show release notes
                messagebox.showinfo(
                    "Update Available",
                    f"New version {new_version} is available!\n\n"
                    f"Release Notes:\n{release_notes}\n\n"
                    f"Click 'Download Version {new_version}' button to update."
                )
                
            elif result.get("error"):
                # Error occurred
                self.update_status_label.configure(
                    text=result.get("message", "Update check failed"), 
                    text_color="#e74c3c"
                )
                self.btn_check_update.configure(state="normal", text="🔄 Check for Update")
                
            else:
                # Already latest version
                self.update_status_label.configure(
                    text="✅ You are using the latest version", 
                    text_color="#27ae60"
                )
                self.btn_check_update.configure(state="normal", text="🔄 Check for Update")
                
        except Exception as e:
            print(f"[ERROR] Update result handling failed: {e}")
            self.btn_check_update.configure(state="normal", text="🔄 Check for Update")
    
    def download_update(self, download_url, version):
        """Download the update installer"""
        try:
            # Disable button and show progress
            self.btn_check_update.configure(state="disabled", text="⬇ Downloading...")
            self.update_status_label.configure(text="Downloading update...", text_color="#3498db")
            self.update_progress.pack(fill="x", pady=(0, 5))  # Show progress bar
            self.update_progress.set(0)
            
            # Create downloader with progress callback
            downloader = UpdateDownloader(
                download_url,
                progress_callback=self.on_download_progress
            )
            
            # Download in background
            downloader.download_async(
                completion_callback=lambda path: self.on_download_complete(path, version)
            )
            
        except Exception as e:
            print(f"[ERROR] Download initiation failed: {e}")
            self.update_status_label.configure(
                text=f"Download failed: {str(e)}", 
                text_color="#e74c3c"
            )
            self.btn_check_update.configure(state="normal", text="🔄 Check for Update")
            self.update_progress.pack_forget()
    
    def on_download_progress(self, progress, downloaded, total):
        """Update progress bar during download"""
        try:
            self.update_progress.set(progress / 100.0)
            status_text = f"Downloading: {format_size(downloaded)} / {format_size(total)} ({progress:.1f}%)"
            self.update_status_label.configure(text=status_text, text_color="#3498db")
        except Exception as e:
            print(f"[ERROR] Progress update failed: {e}")
    
    def on_download_complete(self, installer_path, version):
        """Handle download completion"""
        try:
            if installer_path and os.path.exists(installer_path):
                # Download successful
                self.update_status_label.configure(
                    text=f"✅ Download complete! Ready to install v{version}", 
                    text_color="#27ae60"
                )
                self.update_progress.set(1.0)
                
                # Change button to install
                self.btn_check_update.configure(
                    state="normal",
                    text=f"🚀 Install Version {version}",
                    fg_color="#9b59b6",
                    hover_color="#8e44ad",
                    command=lambda: self.install_update(installer_path)
                )
                
                # Ask user if they want to install now
                response = messagebox.askyesno(
                    "Download Complete",
                    f"Version {version} has been downloaded successfully!\n\n"
                    f"Do you want to install it now?\n\n"
                    f"The application will close and the installer will run."
                )
                
                if response:
                    self.install_update(installer_path)
                    
            else:
                # Download failed
                self.update_status_label.configure(
                    text="❌ Download failed. Please try again.", 
                    text_color="#e74c3c"
                )
                self.btn_check_update.configure(state="normal", text="🔄 Check for Update")
                self.update_progress.pack_forget()
                
        except Exception as e:
            print(f"[ERROR] Download completion handling failed: {e}")
            self.update_status_label.configure(
                text=f"Error: {str(e)}", 
                text_color="#e74c3c"
            )
            self.btn_check_update.configure(state="normal", text="🔄 Check for Update")
    
    def install_update(self, installer_path):
        """Install the downloaded update"""
        try:
            # Confirm installation
            response = messagebox.askyesno(
                "Install Update",
                "The application will close and the installer will run.\n\n"
                "Do you want to continue?"
            )
            
            if response:
                self.update_status_label.configure(
                    text="🚀 Launching installer...", 
                    text_color="#9b59b6"
                )
                
                # Run installer and close app
                UpdateInstaller.install_update(installer_path, close_current_app=True)
                
        except Exception as e:
            print(f"[ERROR] Installation failed: {e}")
            messagebox.showerror(
                "Installation Error",
                f"Failed to launch installer:\n{str(e)}\n\n"
                f"Please run the installer manually from:\n{installer_path}"
            )
