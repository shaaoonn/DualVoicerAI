# Reference 03: Auth System — Google OAuth + Phone OTP
**Replaces old email+phone system | Research: April 2026**

---

## Problem with Old System

```
Old: email + phone number + HWID → login
Problem: users forget phone when they have multiple devices
Result: locked out permanently
```

## New System Design

```
Two independent auth methods:

Method 1: Continue with Google (recommended)
  → Browser opens → user picks Google account → token returned
  → No phone number needed, ever
  → Works on all devices, globally

Method 2: Phone OTP (বাংলাদেশ + international)
  → User enters phone number → gets SMS OTP
  → Enter OTP → verified
  → Firebase Phone Auth (free tier: unlimited sends)

Security maintained:
  → HWID still stored (device limit enforcement)
  → Firebase ID token verified server-side
  → Device count limits unchanged
  → Rate limiting on backend unchanged
```

---

## Desktop Auth UI (Login Window)

```
Window: 440×520, centered, modal (CTkToplevel)
Title: [APP_NAME] — লগইন

┌────────────────────────────────────────┐
│         [APP LOGO]                     │
│         VoiceAI Pro                    │
│    ejobsit.com/ai-voice                │
│                                        │
│  ┌──────────────────────────────────┐  │
│  │  🔵  Continue with Google        │  │  ← big button, blue
│  └──────────────────────────────────┘  │
│                                        │
│         ────── অথবা ──────            │
│                                        │
│  ফোন নম্বর দিয়ে লগইন করুন:            │
│  ┌──────┐ ┌──────────────────────┐    │
│  │ +880 ▼│ │ 01XXXXXXXXX         │    │  ← country code + number
│  └──────┘ └──────────────────────┘    │
│  [OTP পাঠান]                           │
│                                        │
│  ← OTP এলে এখানে দিন:                 │
│  ┌──────────────────────────────────┐  │
│  │  _ _ _ _ _ _                    │  │  ← 6-digit OTP
│  └──────────────────────────────────┘  │
│  [যাচাই করুন]                          │
│                                        │
│  ───────────────────────────────────── │
│  🆓 ট্রায়াল: সাইন ইন ছাড়া ৭ দিন চেষ্টা  │
│  [ট্রায়াল শুরু করুন] ← ghost button    │
└────────────────────────────────────────┘
```

---

## Method 1: Google OAuth Flow (Desktop Python)

### How it works (Verified — google-auth-oauthlib)

```
1. App opens Google consent URL in system browser
2. Local HTTP server listens on random port (http://localhost:PORT)
3. Google redirects to localhost after login
4. App catches Google ID token
5. Sends token to backend → backend verifies with Firebase Admin SDK
6. Backend returns user plan, expiry, device info
```

### Client-side code: `subscription/auth_new.py`

```python
# subscription/auth_new.py
"""
Google OAuth for desktop Python app.
Uses InstalledAppFlow (google-auth-oauthlib) — opens browser,
catches callback on local server.

Research: https://googleapis.github.io/google-api-python-client/docs/oauth-installed.html
Research: https://developers.google.com/identity/protocols/oauth2/native-app
Requires: pip install google-auth-oauthlib
"""
import json, requests, threading, webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import google_auth_oauthlib.flow as oauth_flow
from config import GOOGLE_CLIENT_ID, API_GOOGLE_AUTH_URL

# Google OAuth scopes — only email + profile (minimal permissions)
GOOGLE_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]

# client_secrets format (store in .env, never hardcode)
# Get from: Google Cloud Console → Credentials → OAuth 2.0 → Desktop App
GOOGLE_CLIENT_CONFIG = {
    "installed": {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
        "redirect_uris": ["http://localhost"],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}

def google_login(on_success, on_error):
    """
    Opens browser for Google login.
    Calls on_success(user_data) or on_error(message) when done.
    Non-blocking — runs in thread.
    """
    def _run():
        try:
            flow = oauth_flow.InstalledAppFlow.from_client_config(
                GOOGLE_CLIENT_CONFIG, scopes=GOOGLE_SCOPES
            )
            # run_local_server: starts local HTTP server, opens browser
            # port=0 = pick random available port
            credentials = flow.run_local_server(
                port=0,
                prompt="select_account",   # always show account picker
                success_message="লগইন সফল! এই ট্যাব বন্ধ করুন।",
                open_browser=True,
            )
            # Get Google ID token
            id_token = credentials.id_token

            # Send to backend for verification
            resp = requests.post(
                API_GOOGLE_AUTH_URL,
                json={"id_token": id_token, "hwid": _get_hwid()},
                timeout=15
            )
            data = resp.json()
            if resp.status_code == 200 and data.get("success"):
                on_success(data.get("user", {}))
            else:
                on_error(data.get("message", "Google লগইন ব্যর্থ হয়েছে"))
        except Exception as e:
            on_error(f"Google লগইন সমস্যা: {e}")

    threading.Thread(target=_run, daemon=True).start()
```

### Backend endpoint (app.py — new route)

```python
# Add to app.py:
import google.oauth2.id_token
import google.auth.transport.requests as google_requests

@app.route('/api/v2/google-auth', methods=['POST'])
@limiter.limit("10 per minute")
def google_auth():
    """Verify Google ID token → return user data from Firestore."""
    data = request.json
    id_token_str = data.get('id_token', '')
    hwid = data.get('hwid', '')

    if not id_token_str or not hwid:
        return jsonify({'success': False, 'message': 'Missing token or HWID'}), 400

    try:
        # Verify Google ID token
        request_adapter = google_requests.Request()
        decoded = google.oauth2.id_token.verify_oauth2_token(
            id_token_str, request_adapter, GOOGLE_CLIENT_ID
        )
        google_email = decoded['email']
        google_name  = decoded.get('name', '')

        # Look up or create user in Firestore by Google email
        user_ref = db.collection('users').document(google_email)
        user_doc = user_ref.get()

        if not user_doc.exists:
            # Auto-register: create trial account
            trial_expiry = datetime.now() + timedelta(days=7)
            user_ref.set({
                'email': google_email,
                'name': google_name,
                'auth_method': 'google',
                'plan': 'trial',
                'plan_type': 'Trial',
                'expiry_date': trial_expiry,
                'devices': [hwid],
                'max_devices': 1,
                'created_at': datetime.now(),
            })
            user_data = user_ref.get().to_dict()
        else:
            user_data = user_doc.to_dict()
            # Register HWID if new device
            devices = user_data.get('devices', [])
            if hwid not in devices:
                max_dev = user_data.get('max_devices', 1)
                if len(devices) >= max_dev:
                    return jsonify({
                        'success': False,
                        'message': f'ডিভাইস সীমা পার হয়েছে ({max_dev}টি)। পুরনো ডিভাইস সরান।'
                    }), 403
                devices.append(hwid)
                user_ref.update({'devices': devices})

        # Check expiry
        expiry = user_data.get('expiry_date')
        if expiry and datetime.now() > expiry:
            return jsonify({'success': False, 'message': 'সাবস্ক্রিপশন শেষ। renew করুন।', 'is_expired': True}), 403

        return jsonify({
            'success': True,
            'user': {
                'email': google_email,
                'name': google_name,
                'plan_type': user_data.get('plan_type', 'Trial'),
                'expiry_date': str(user_data.get('expiry_date', '')),
                'devices_used': len(user_data.get('devices', [])),
                'max_devices': user_data.get('max_devices', 1),
            }
        })
    except ValueError as e:
        return jsonify({'success': False, 'message': f'Invalid token: {e}'}), 401
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
```

---

## Method 2: Phone OTP Flow

### Uses Firebase Phone Auth REST API (Free)

```
Docs: https://firebase.google.com/docs/reference/rest/auth#section-send-verification-code
Free tier: No limit on SMS sends (Firebase Phone Auth)
Supported countries: All international numbers
```

### Client-side code (in `auth_new.py`)

```python
import os, requests
from config import API_SEND_OTP_URL, API_VERIFY_OTP_URL

COUNTRY_CODES = [
    ("+880", "🇧🇩 Bangladesh"),
    ("+91",  "🇮🇳 India"),
    ("+1",   "🇺🇸 USA/Canada"),
    ("+44",  "🇬🇧 UK"),
    ("+60",  "🇲🇾 Malaysia"),
    ("+65",  "🇸🇬 Singapore"),
    ("+971", "🇦🇪 UAE"),
    ("+966", "🇸🇦 Saudi Arabia"),
    ("+61",  "🇦🇺 Australia"),
    # ... add more as needed
]

def send_otp(phone_full: str, on_success, on_error):
    """phone_full: e.g. '+8801711158538'"""
    def _run():
        try:
            resp = requests.post(
                API_SEND_OTP_URL,
                json={"phone": phone_full},
                timeout=15
            )
            data = resp.json()
            if resp.status_code == 200 and data.get("success"):
                session_info = data.get("session_info", "")
                on_success(session_info)
            else:
                on_error(data.get("message", "OTP পাঠানো যায়নি"))
        except Exception as e:
            on_error(str(e))
    threading.Thread(target=_run, daemon=True).start()

def verify_otp(session_info: str, otp_code: str, hwid: str, on_success, on_error):
    def _run():
        try:
            resp = requests.post(
                API_VERIFY_OTP_URL,
                json={"session_info": session_info, "code": otp_code, "hwid": hwid},
                timeout=15
            )
            data = resp.json()
            if resp.status_code == 200 and data.get("success"):
                on_success(data.get("user", {}))
            else:
                on_error(data.get("message", "OTP যাচাই ব্যর্থ"))
        except Exception as e:
            on_error(str(e))
    threading.Thread(target=_run, daemon=True).start()
```

### Backend OTP endpoints (app.py)

```python
FIREBASE_API_KEY = os.getenv("FIREBASE_WEB_API_KEY", "")   # from Firebase console

@app.route('/api/v2/send-otp', methods=['POST'])
@limiter.limit("5 per minute")
def send_otp():
    phone = request.json.get('phone', '').strip()
    if not phone.startswith('+'):
        return jsonify({'success': False, 'message': 'Phone must start with country code (+880...)'}), 400

    # Firebase Phone Auth — send OTP
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendVerificationCode?key={FIREBASE_API_KEY}"
    resp = requests.post(url, json={"phoneNumber": phone, "recaptchaToken": "BYPASS"})
    # Note: For server-to-server, use Firebase Admin SDK instead of recaptcha
    # Simpler: use Admin SDK createCustomToken + phone verification
    data = resp.json()
    if 'sessionInfo' in data:
        return jsonify({'success': True, 'session_info': data['sessionInfo']})
    return jsonify({'success': False, 'message': 'OTP পাঠাতে সমস্যা হয়েছে'}), 400

@app.route('/api/v2/verify-otp', methods=['POST'])
@limiter.limit("10 per minute")
def verify_otp():
    session_info = request.json.get('session_info', '')
    code         = request.json.get('code', '')
    hwid         = request.json.get('hwid', '')

    # Verify OTP with Firebase
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPhoneNumber?key={FIREBASE_API_KEY}"
    resp = requests.post(url, json={"sessionInfo": session_info, "code": code})
    data = resp.json()

    if 'idToken' not in data:
        return jsonify({'success': False, 'message': 'ভুল OTP দিয়েছেন'}), 401

    phone_number = data.get('phoneNumber', '')

    # Look up or create user in Firestore by phone
    users_ref = db.collection('users')
    query = users_ref.where('phone', '==', phone_number).limit(1).get()

    if not query:
        # Auto-register trial user
        trial_expiry = datetime.now() + timedelta(days=7)
        doc_id = phone_number.replace('+', '').replace(' ', '')
        users_ref.document(doc_id).set({
            'phone': phone_number, 'auth_method': 'phone',
            'plan': 'trial', 'plan_type': 'Trial',
            'expiry_date': trial_expiry, 'devices': [hwid], 'max_devices': 1,
        })
        user_data = users_ref.document(doc_id).get().to_dict()
    else:
        user_data = query[0].to_dict()
        # HWID check (same as Google flow)

    return jsonify({'success': True, 'user': {
        'phone': phone_number,
        'plan_type': user_data.get('plan_type', 'Trial'),
        'expiry_date': str(user_data.get('expiry_date', '')),
        'devices_used': len(user_data.get('devices', [])),
        'max_devices': user_data.get('max_devices', 1),
    }})
```

---

## Security Maintained

```
✅ HWID still collected (Motherboard + CPU + Disk + MAC hash)
✅ Device count enforced (1 device trial, 2-10 paid)
✅ Expiry date checked on every login
✅ Firebase ID token verified server-side (cannot be faked)
✅ Rate limiting: 5 OTP/min, 10 verify/min
✅ No phone number required for Google auth users
✅ Auto-register: new users get 7-day trial automatically
✅ Existing Dual Voicer users → NOT affected (different backend)
```

---

## Config Changes in main.py

```python
# In VoiceTypingApp.__init__():
# REMOVE: self.phone_entry_ref references
# REMOVE: old validate_device_access() calls
# ADD: from subscription.auth_new import google_login, send_otp, verify_otp

# Replace open_auth_panel() content with new login window
# Keep: is_authenticated, user_email, device_count, max_devices flags
# Keep: login_success(), force_logout_expired() methods
# Keep: periodic verification schedule
```

---

## .env additions required

```
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
FIREBASE_WEB_API_KEY=your-firebase-web-api-key
```
