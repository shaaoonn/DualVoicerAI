"""Authentication panel + API-driven login/subscription flow.

Originally inlined in ``VoiceTypingApp`` as ~650 lines spanning login
dialog construction, device-access validation against the EJOBSIT
backend, auto-login on app launch, subscription status polling, and
logout. Lifted into a single mixin file because:

* The whole subsystem shares a coherent set of self.* state
  (is_authenticated, user_email, device_count, max_devices,
  user_cache, settings, freemium) — splitting per-method would force
  every method into ``self`` parameter passing.
* Auth is naturally request/response oriented; the Tk dialog
  construction is verbose but mechanical.

Method discipline:

* No ``__init__`` here — pure method collection mixed into
  ``VoiceTypingApp`` via multiple inheritance.
* All UI calls go through ``self.after(0, ...)`` to land on the Tk
  main thread (the API threads themselves run on daemon threads
  spawned by ``validate_device_access``).
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
import tkinter as tk
import webbrowser
import winreg
from datetime import datetime
from tkinter import messagebox

import customtkinter as ctk
import requests

from config import API_GOOGLE_AUTH_URL


class AuthPanelMixin:
    """Mixed into VoiceTypingApp — provides login UI + API flow + auto-login."""

    def auto_login_if_saved(self):
        """Attempt auto-login using saved credentials"""
        saved_email, saved_phone = self.load_login_config()
        if saved_email and saved_phone:
            print(f"[INFO] Attempting auto-login for {saved_email}")
            # Mark that auto-login is being attempted
            self._auto_login_attempted = True
            
            # Store phone for validate_device_access to use
            self._auto_login_phone = saved_phone 
            
            threading.Thread(
                target=self.validate_device_access,
                args=(saved_email, None, None, True),
                daemon=True
            ).start()
        else:
            # No saved credentials, clear flag
            self._auto_login_attempted = False
    
    def check_and_add_to_startup(self):
        try:
            exe_path = sys.executable
            # Only enact if running as compiled EXE
            if getattr(sys, 'frozen', False):
                # Wrap in quotes so paths containing spaces are handled correctly
                # by Windows startup (without quotes, spaces split into arguments)
                quoted_path = f'"{exe_path}"'
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_ALL_ACCESS)
                try:
                    winreg.SetValueEx(key, "DualVoicer", 0, winreg.REG_SZ, quoted_path)
                except OSError:
                    pass
                finally:
                    winreg.CloseKey(key)
        except OSError: pass

    def open_auth_panel(self):
        """Open authentication panel - Web-First model (no registration here)"""
        # Web-First model (no registration here)

        
        # Check if already open
        if hasattr(self, 'auth_window') and self.auth_window is not None and self.auth_window.winfo_exists():
            self.auth_window.lift()
            self.auth_window.focus_force()
            return

        # Create auth dialog
        self.auth_window = ctk.CTkToplevel(self)
        dialog = self.auth_window # Use local var for convenience
        dialog.title("Dual Voicer - Login")
        dialog.geometry("450x540") # Increased height for logo
        dialog.resizable(False, False)
        dialog.attributes('-topmost', True)
        
        # Position to the RIGHT of settings window
        try:
            if self.settings_window and self.settings_window.winfo_exists():
                x = self.settings_window.winfo_x() + self.settings_window.winfo_width() + 10
                y = self.settings_window.winfo_y()
                dialog.geometry(f"450x540+{x}+{y}")
            else:
                dialog.geometry("450x540+100+100")
        except tk.TclError:
            dialog.geometry("450x540+100+100")
        
        dialog.lift()  # Bring to front
        dialog.focus_force()  # Take focus
        # Schedule another lift to ensure it stays on top
        dialog.after(100, lambda: dialog.lift())
            
        try: dialog.after(200, lambda: dialog.iconbitmap(self.icon_path))
        except tk.TclError: pass
        
        # Logo and Title
        header_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        header_frame.pack(pady=(20, 10))
        
        # Load larger logo for dialog
        try:
            if self.icon_path:
                from PIL import Image
                img = Image.open(self.icon_path)
                logo_img = ctk.CTkImage(light_image=img, dark_image=img, size=(64, 64))
                ctk.CTkLabel(header_frame, text="", image=logo_img).pack(pady=(0, 5))
        except (OSError, tk.TclError): pass

        ctk.CTkLabel(
            header_frame, text="Dual Voicer Premium", 
            font=("Segoe UI", 20, "bold"), text_color="#667eea"  # Logo Blue
        ).pack()
        
        ctk.CTkLabel(
            header_frame, text="Login to activate premium features", 
            font=("Arial", 11), text_color="#95a5a6"
        ).pack()
        
        # Input Fields
        input_frame = ctk.CTkFrame(dialog)
        input_frame.pack(fill="x", padx=30, pady=10)
        
        email_entry = ctk.CTkEntry(
            input_frame, placeholder_text="Enter your Email (Gmail Only)",
            height=40, font=("Segoe UI", 12)
        )
        email_entry.pack(fill="x", pady=(10, 5), padx=10)
        
        # Pre-fill email/phone if saved
        saved_email, saved_phone = self.load_login_config()
        if saved_email:
            email_entry.insert(0, saved_email)
            
        phone_entry = ctk.CTkEntry(
            input_frame, placeholder_text="Phone Number (e.g. 017...)",
            height=40, font=("Segoe UI", 12)
        )
        phone_entry.pack(fill="x", pady=(5, 10), padx=10)
        
        if saved_phone:
            phone_entry.insert(0, saved_phone)
        
        # Reference for API usage
        self.phone_entry_ref = phone_entry
        
        # Status Label
        status_label = ctk.CTkLabel(dialog, text="", font=("Arial", 11))
        status_label.pack(pady=5)
        
        # Login Handler
        def handle_login():
            """Validate existing user login with email + phone verification"""
            email = email_entry.get().strip().lower()
            phone = phone_entry.get().strip()
            
            if not email or "@" not in email:
                status_label.configure(text="Please enter a valid email address", text_color="#e74c3c")
                return
            
            # Gmail-only validation
            if not email.endswith('@gmail.com'):
                status_label.configure(text="⚠️ Only Gmail addresses are allowed", text_color="#e74c3c")
                return
                
            if len(phone) < 11:
                status_label.configure(text="⚠️ Please enter a valid phone number", text_color="#e74c3c")
                return
            
            status_label.configure(text="Authenticating...", text_color="#f39c12")
            dialog.update()
            
            # Run login validation in background (Using Secure API)
            threading.Thread(
                target=self.validate_device_access,
                args=(email, dialog, status_label),
                daemon=True
            ).start()
        
        # Action Buttons Frame
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=5)
        
        # Login Button
        ctk.CTkButton(
            btn_frame, text="🔓 Login", width=180, height=40,
            fg_color="#764ba2", hover_color="#6b46a3",  # Logo Purple
            font=("Segoe UI", 12, "bold"),
            command=handle_login
        ).pack(side="left", padx=5)
        
        # Cancel Button
        ctk.CTkButton(
            btn_frame, text="Cancel", width=180, height=40,
            fg_color="#4a5568", hover_color="#2d3748",  # Dark Gray
            command=dialog.destroy
        ).pack(side="left", padx=5)
        
        # Separator
        separator = ctk.CTkFrame(dialog, height=1, fg_color="#34495e")
        separator.pack(fill="x", padx=30, pady=10)
        
        # Registration Links
        links_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        links_frame.pack(pady=5)
        
        ctk.CTkLabel(
            links_frame, text="Don't have an account?",
            font=("Arial", 10), text_color="#95a5a6"
        ).pack()
        
        # Website Registration Buttons
        web_btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        web_btn_frame.pack(pady=5)
        
        # Trial signup handler with HWID
        def open_trial_signup():
            """Open trial signup with HWID parameter and warning"""
            hwid = self.get_stable_hwid()
            
            # Show warning about trial limit
            messagebox.showinfo(
                "Trial Signup",
                "🎁 Free Trial Information:\n\n"
                "• Each computer can only create ONE free trial\n"
                "• Trial period: 7 days\n"
                "• If you've already used a trial on this computer,\n"
                "  please purchase a subscription instead\n\n"
                "Opening browser for trial signup..."
            )
            
            # Open website with HWID parameter
            signup_url = f"https://dualvoicer.ejobsit.com/?trial=yes&hwid={hwid}"
            webbrowser.open(signup_url)
        
        # Free Trial Button - Opens Website with HWID
        ctk.CTkButton(
            web_btn_frame, text="🎁 Start Free Trial", width=180, height=35,
            fg_color="#667eea", hover_color="#5a67d8",  # Logo Blue
            font=("Segoe UI", 11, "bold"),
            command=open_trial_signup
        ).pack(side="left", padx=5)
        
        # Buy Subscription Button - Opens Website
        ctk.CTkButton(
            web_btn_frame, text="💳 Buy Subscription", width=180, height=35,
            fg_color="#9f7aea", hover_color="#805ad5",  # Logo Light Purple
            font=("Segoe UI", 11, "bold"),
            command=lambda: webbrowser.open("https://dualvoicer.ejobsit.com")
        ).pack(side="left", padx=5)
        
        # Bind Enter key to login
        email_entry.bind("<Return>", lambda e: phone_entry.focus())
        phone_entry.bind("<Return>", lambda e: handle_login())
    
    def validate_device_access(self, email, dialog, status_label, is_auto_login=False):
        """SECURE API LOGIN: Validates user via Website API"""
        def _api_login_thread():
            try:
                # API Endpoint
                API_URL = "https://dualvoicer.ejobsit.com/api/desktop-login"
                
                # Retrieve phone number - New Logic
                phone_number = ""
                if is_auto_login:
                    phone_number = getattr(self, '_auto_login_phone', "")
                elif hasattr(self, 'phone_entry_ref'):
                    try:
                        phone_number = self.phone_entry_ref.get().strip()
                    except (tk.TclError, AttributeError): pass
                
                payload = {
                    "email": email,
                    "phone": phone_number,
                    "hwid": self.hardware_id
                }
                
                print(f"[API] Checking login for {email} with phone...")
                
                try:
                    response = requests.post(API_URL, json=payload, timeout=10)
                    data = response.json()
                    
                    if response.status_code == 200 and data.get("success"):
                        # SUCCESS from API - but check expiry first!
                        user = data.get("user", {})
                        
                        # CRITICAL: Check expiry BEFORE allowing login
                        expiry_str = user.get("expiry_date") or user.get("expires_at")
                        plan_type = user.get("plan_type", "Premium")
                        
                        if expiry_str:
                            try:
                                # Parse expiry date (ISO format from API)
                                if isinstance(expiry_str, str):
                                    expiry_datetime = datetime.datetime.fromisoformat(expiry_str.replace('Z', '+00:00').replace('+00:00', ''))
                                else:
                                    expiry_datetime = expiry_str
                                
                                if datetime.datetime.now() > expiry_datetime:
                                    # EXPIRED! Block login
                                    if plan_type.lower() == "trial":
                                        error_msg = tr("err_trial_expired")
                                    else:
                                        error_msg = tr("err_subscription_expired")
                                    
                                    # Clear saved config for expired users
                                    try:
                                        if hasattr(self, 'config_file') and os.path.exists(self.config_file):
                                            os.remove(self.config_file)
                                    except OSError: pass
                                    
                                    if is_auto_login:
                                        print(f"[SECURITY] Auto-login blocked: Trial/Subscription expired")
                                        # Show login panel for expired users
                                        self.after(0, self.force_logout_expired)
                                        return
                                    
                                    self.after(0, lambda: self.login_failed(error_msg, status_label))
                                    return
                            except Exception as e:
                                print(f"[WARNING] Expiry check failed: {e}")

                        # --- REMOVED LEGACY FIRESTORE CHECK ---
                        # Security is now fully handled by the API response (plan_type & expiry)
                        # and Server-side One-Device-One-Trial logic.
                        # --------------------------------------

                        # Cache user data for UI (Plan Info)
                        self.user_cache = user
                        self.user_email = email # Ensure this is set
                        
                        devices_used = user.get("devices_used", 1)
                        max_devices = user.get("max_devices", 1)
                        
                        self.after(0, lambda: self.login_success(email, phone_number, devices_used, max_devices, dialog, is_auto_login))
                        return
                        
                    else:
                        # FAIL returned by API
                        error_msg = data.get("message", "Login Failed")
                        
                        if is_auto_login:
                             print(f"[API] Auto-login blocked: {error_msg}")
                             try: os.remove(self.config_file)
                             except OSError: pass
                             return
                        
                        self.after(0, lambda: self.login_failed(error_msg, status_label))
                        return
                        
                except requests.exceptions.RequestException as e:
                    # Network Error
                    print(f"[API] Network Error: {e}")
                    if is_auto_login:
                        return
                    
                    self.after(0, lambda: self.login_failed(tr("err_server_connection"), status_label))
                    
            except Exception as e:
                print(f"[API] System Error: {e}")
                if not is_auto_login:
                    self.after(0, lambda: self.login_failed(f"System Error: {e}", status_label))

        # Run network request in thread
        threading.Thread(target=_api_login_thread, daemon=True).start()
    
    def login_success(self, email, phone, device_count, max_devices=2, dialog=None, is_auto_login=False):
        """Handle successful login"""
        # Close login dialog immediately to prevent "stuck" UI
        if dialog:
            try: dialog.destroy()
            except tk.TclError: pass
            
        self.user_email = email
        self.user_phone = phone # Store phone for background verification
        self.is_authenticated = True
        self.device_count = device_count
        self.max_devices = max_devices  # Store for display
        
        # Save login for auto-login next time
        self.save_login_config(email, phone)
        
        # Fetch user plan info from Firestore to show in button
        self.fetch_and_update_plan_info()
        
        # Show success message
        if not is_auto_login:
            messagebox.showinfo(
                "Login Successful", 
                f"✅ Login Successful!\n\nWelcome Back!\n\nEmail: {email}\nDevices: {device_count}/{max_devices}"
            )
        else:
            print(f"[INFO] Auto-login successful for {email}")
        
        # Update window title to show premium status
        self.update_window_title()
        
        # SECURITY: Save last verification timestamp
        self._last_verified = time.time()
        
        # SECURITY: Start periodic re-verification (every 24 hours)
        self.schedule_periodic_verification()

    def schedule_periodic_verification(self):
        """SECURITY: Schedule periodic online verification to prevent offline abuse"""
        # Re-verify every 24 hours (86400000 ms)
        def verify_periodically():
            if self.is_authenticated and self.user_email:
                print("[SECURITY] Periodic verification triggered (24h)")
                threading.Thread(
                    target=self.verify_subscription_status,
                    daemon=True
                ).start()
            # Schedule next check
            self.after(86400000, verify_periodically)  # 24 hours

        # First check after 24 hours
        self.after(86400000, verify_periodically)
    
    def verify_subscription_status(self):
        """SECURITY: Verify subscription via API (Replaces Legacy Firestore Check)"""
        try:
            # Check for internet first (simple DNS check or similar, but requests will handle it)
            API_URL = "https://dualvoicer.ejobsit.com/api/desktop-login"
            
            # Use stored phone or try to get from config
            phone = getattr(self, 'user_phone', '')
            if not phone:
                 _, phone = self.load_login_config()
            
            payload = {
                "email": self.user_email,
                "phone": phone,
                "hwid": self.hardware_id
            }
            
            print("[SECURITY] Verifying subscription via API...")
            response = requests.post(API_URL, json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                     user = data.get("user", {})
                     # Check expiry from API response
                     expiry_str = user.get("expiry_date") or user.get("expires_at")
                     
                     if expiry_str:
                        try:
                            if isinstance(expiry_str, str):
                                expiry_dt = datetime.datetime.fromisoformat(expiry_str.replace('Z', '+00:00').replace('+00:00', ''))
                            else:
                                expiry_dt = expiry_str
                                
                            if datetime.datetime.now() > expiry_dt:
                                print("[SECURITY] API says: Expired")
                                self.after(0, self.force_logout_expired)
                                return
                        except (KeyError, ValueError, TypeError): pass

                     # Check if device is still in allowed list (API handles this logic too, but good to check user obj)
                     # Actually, if API returns success=True, it means device is allowed.
                     
                     # Update local cache
                     self.user_cache = user
                     self.device_count = user.get("devices_used", 1)
                     self.max_devices = user.get("max_devices", 1)
                     self.after(0, self.fetch_and_update_plan_info)
                     
                     print("[SECURITY] Verification Successful")
                     self._last_verified = time.time()
                     return
                else:
                    print(f"[SECURITY] API Verification Failed: {data.get('message')}")
                    # If API explicitly says failed (e.g. device removed), logout
                    if "device" in data.get("message", "").lower() or "expire" in data.get("message", "").lower():
                         self.after(0, self.force_logout_expired)
            else:
                print(f"[SECURITY] API Error {response.status_code}")
                # Don't logout on 500/404 errors, maybe temp server issue
                
        except Exception as e:
            print(f"[SECURITY] Verification connection error: {e}")
            # Offline is okay, we let them continue until next check
    
    def force_logout_expired(self):
        """SECURITY: Force logout when subscription/verification fails"""
        self.is_authenticated = False
        self.user_email = None
        self.clear_login_config()
        self.update_window_title()
        messagebox.showwarning(
            tr("title_subscription_ended"),
            tr("msg_subscription_ended"),
        )
        self.open_auth_panel()
    
    def login_failed(self, message, status_label):
        """Handle failed login"""
        if status_label:
            status_label.configure(text=message, text_color="#e74c3c")
        else:
            print(f"[ERROR] Login failed: {message}")
    
    def handle_logout(self):
        """Handle user logout"""
        # Confirm logout
        response = messagebox.askyesno(
            "Logout",
            "Are you sure you want to logout?\n\n"
            "You will need to login again next time."
        )
        
        if response:
            # Clear saved login config
            self.clear_login_config()
            
            # Reset authentication state
            self.is_authenticated = False
            self.user_email = None
            self.device_count = 0
            
            # Update window title
            self.update_window_title()
            
            # Update UI to Logged Out state
            self.fetch_and_update_plan_info()
            
            print("[INFO] User logged out successfully")
            
            # Show login panel
            self.open_auth_panel()
    
    
    def fetch_and_update_plan_info(self):
        """Fetch plan info from Local Cache and update UI (Handles Login & Logout states)"""
        try:
            # Check if login button frame exists
            if not hasattr(self, 'login_btn_frame') or not self.login_btn_frame.winfo_exists():
                return
            
            # Case 1: Logged Out
            if not self.user_email:
                # Clear frame
                for widget in self.login_btn_frame.winfo_children():
                    widget.destroy()
                
                # Recreate login button
                self.btn_login = ctk.CTkButton(
                    self.login_btn_frame, text="  🔐 Login / Activate",
                    fg_color="#764ba2", hover_color="#6b46a3",
                    font=("Segoe UI", 12, "bold"), height=35,
                    command=self.open_auth_panel
                )
                self.btn_login.pack(fill="x")
                
                if self.expiry_info_label:
                    self.expiry_info_label.configure(text="")
                return
            
            # Use cached data if available
            user_data = getattr(self, 'user_cache', {})
            if not user_data:
                # If no cache but email exists, maybe show basic info
                plan_type = "..."
                days_remaining = 0
            else:
                plan_type = user_data.get('plan_display', 'Premium')
                expiry_str = user_data.get('expiry_date')
                
                # Calculate days remaining
                days_remaining = 0
                if expiry_str and expiry_str != 'N/A':
                    try:
                        # Parse YYYY-MM-DD
                        exp_date = datetime.datetime.strptime(expiry_str, '%Y-%m-%d')
                        days_remaining = (exp_date - datetime.datetime.now()).days
                    except (ValueError, TypeError):
                        pass

            # Update button with plan info - SIDE BY SIDE LAYOUT using GRID
            if hasattr(self, 'login_btn_frame') and self.login_btn_frame is not None and self.login_btn_frame.winfo_exists():
                emoji = "🎁" if "trial" in plan_type.lower() else "✓"
                
                # Clear any existing pack/grid slaves
                for widget in self.login_btn_frame.winfo_children():
                    widget.destroy()
                    
                # Configure grid for 55-45 split
                self.login_btn_frame.grid_columnconfigure(0, weight=6)
                self.login_btn_frame.grid_columnconfigure(1, weight=4)
                self.login_btn_frame.configure(fg_color="transparent")
                
                # LEFT: Plan Info Box
                # Softer colors
                plan_color = "#219150" if plan_type.lower() in ["premium", "unlimited"] else "#d35400" 
                if "trial" in plan_type.lower(): plan_color = "#d35400" # Softer Orange
                
                # Plan Label as Button
                display_text = f"{emoji} {plan_type}"
                
                plan_btn = ctk.CTkButton(
                    self.login_btn_frame,
                    text=display_text,
                    fg_color=plan_color,
                    hover_color=plan_color,
                    font=("Segoe UI", 12, "bold"),
                    height=32,
                    state="normal"
                )
                plan_btn.grid(row=0, column=0, sticky="ew", padx=(0, 5))
                
                # Store reference
                self.btn_login = plan_btn
                
                # RIGHT: Logout Button
                self.btn_logout = ctk.CTkButton(
                    self.login_btn_frame,
                    text="Logout",
                    fg_color="#7f8c8d", # Gray instead of Red
                    hover_color="#95a5a6",
                    font=("Segoe UI", 11, "bold"),
                    height=32,
                    width=80,
                    command=self.handle_logout
                )
                self.btn_logout.grid(row=0, column=1, sticky="ew", padx=(5, 0))
            
            # Update expiry info label WITH DEVICE COUNT
            if self.expiry_info_label:
                # Add Device Count
                device_info = f" • Device: {getattr(self, 'device_count', 1)}/{getattr(self, 'max_devices', 2)}"
                
                if days_remaining > 0:
                    self.expiry_info_label.configure(
                        text=f"{days_remaining} days remaining{device_info}",
                        text_color="#27ae60"
                    )
                elif days_remaining == 0:
                    self.expiry_info_label.configure(
                        text=f"Expires today!{device_info}",
                        text_color="#f39c12"
                    )
                else:
                    self.expiry_info_label.configure(
                        text=f"Expired{device_info}",
                        text_color="#e74c3c"
                    )
                    # Note: Expired users should already be blocked at login time
                    # This is just a fallback UI indicator
                    
        except Exception as e:
            print(f"[ERROR] Failed to update plan info: {e}")
            # Fallback
            pass
    

    def check_authenticate_on_startup(self):
        """SECURITY: Force authentication on startup if not logged in"""
        from config import DEV_MODE
        if DEV_MODE:
            return  # Skip auth in dev mode
        # Check if auto-login is in progress
        if hasattr(self, '_auto_login_attempted'):
            return
        
        if not self.is_authenticated:
            # Try auto-login first
            saved_email, _ = self.load_login_config()
            
            if saved_email:
                print(f"[SECURITY] Found saved login for: {saved_email}. Attempting auto-login...")
                self._auto_login_attempted = True
                
                # Run validation in background to avoid freezing UI
                threading.Thread(
                    target=self.validate_device_access,
                    args=(saved_email, None, None, True), # is_auto_login=True
                    daemon=True
                ).start()
            else:
                print("[SECURITY] No saved login found - opening login panel")
                self.update_window_title()  # Show "Unregistered"
                self.open_auth_panel()
    
    def update_window_title(self):
        """Update window title based on authentication status"""
        if self.is_authenticated:
            plan_type = "Premium"  # You can check Firestore for plan_type if needed
            self.title(f"Dual Voicer ({plan_type})")
        else:
            self.title("Dual Voicer (Unregistered)")
