# Reference 06: Phase 2 — Backend + Website + Firebase
**শুধু Phase 1 শেষ হওয়ার পরে এই ফাইল পড়বে**

---

## Phase 2 Overview

```
কাজ:
1. নতুন Firebase project তৈরি (আলাদা — Dual Voicer থেকে আলাদা)
2. নতুন Flask backend (নতুন domain)
3. Google OAuth + Phone OTP endpoint
4. bKash payment (copy from old app.py — already working)
5. Landing page (simple, conversion-focused)
6. Coolify VPS deployment
```

---

## §setup: Firebase Project Setup

```
Steps:
1. console.firebase.google.com → "Add project" → নতুন নাম (e.g. ejobsit-ai-voice)
2. Authentication → Sign-in method:
   ✅ Google (enable করুন)
   ✅ Phone (enable করুন)
3. Firestore Database → Create → Production mode
4. Project Settings → Service accounts → Generate new private key
   → Save as: backend/firebase_credentials.json (gitignored!)
5. Project Settings → Web app config → copy apiKey etc.
   → Save in backend/.env as FIREBASE_WEB_API_KEY=...
6. Google Cloud Console → APIs & Credentials → OAuth 2.0 Client IDs
   → Application type: Desktop app
   → Download as client_secret.json
   → Copy client_id and client_secret to desktop app .env
```

---

## §flask: New Flask Backend

```
Domain: [new-domain].ejobsit.com (create on Coolify)
Copy from: dualvoicer-web/app.py (base)
Remove: old email+phone login routes
Add: /api/v2/google-auth, /api/v2/send-otp, /api/v2/verify-otp
Keep: /api/pay, /api/callback (bKash — already working)
Keep: /api/latest-download, /admin/* routes

New Firestore collection: 'ai_voice_users' (NOT 'users' — avoid conflict)
```

### Firestore Schema

```
Collection: ai_voice_users
Document ID: google_email OR phone_number (normalized)

Fields:
  email:         string (Google email or "")
  phone:         string ("" or "+8801711158538")
  auth_method:   "google" | "phone"
  name:          string
  plan:          "trial" | "basic" | "pro" | "team"
  plan_type:     "Trial" | "Basic" | "Pro" | "Team"
  expiry_date:   timestamp
  devices:       array of HWID strings
  max_devices:   int (1=trial, 2=basic, 3=pro, 10=team)
  created_at:    timestamp
  last_login:    timestamp
```

---

## §payment: bKash Integration

```python
# Copy from existing app.py — already tested and working
# Routes to keep exactly:
# POST /api/pay        → initiate bKash payment
# GET  /api/callback   → bKash payment callback
# GET  /success        → success page

# Only change:
# 1. Update Firestore collection name to 'ai_voice_users'
# 2. Update plan amounts/names
# 3. Update success redirect URL to new domain

# Plans (BDT):
PLANS = {
    "basic": {"price": 199, "days": 30, "max_devices": 2},
    "pro":   {"price": 399, "days": 30, "max_devices": 3},
    "team":  {"price": 899, "days": 30, "max_devices": 10},
}
```

---

## §website: Landing Page

```
Simple Flask template: templates/index.html
Content:
  - Hero: "AI দিয়ে ভয়েস টাইপিং এখন আরো স্মার্ট"
  - Feature cards (5): Voice typing, AI, Smart Paste, Multi-language, TTS
  - Pricing table (3 plans)
  - Download button → /api/latest-download
  - Login/Register → in-app handles this

Stack: HTML + Tailwind CSS CDN (no build step needed)
Language: বাংলা primary, English secondary
```

---

## §deploy: Coolify VPS Deployment

```bash
# On Contabo VPS (same as CRM automation):
# Create new service in Coolify

# 1. New Dockerfile for backend:
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8000", "app:app"]

# 2. Environment variables in Coolify:
FIREBASE_CREDENTIALS_JSON=<base64 encoded credentials>
FIREBASE_WEB_API_KEY=xxx
GOOGLE_CLIENT_ID=xxx
BKASH_USERNAME=xxx
BKASH_PASSWORD=xxx
BKASH_APP_KEY=xxx
BKASH_APP_SECRET=xxx

# 3. Domain: new-domain.ejobsit.com
# 4. SSL: Let's Encrypt (Coolify handles automatically)

# Existing services on VPS are NOT affected
```

---

## Phase 2 Checklist

```
□ Firebase project created (separate from Dual Voicer)
□ Google OAuth enabled in Firebase console
□ Phone Auth enabled in Firebase console
□ Service account key saved (gitignored)
□ Flask backend running locally
□ /api/v2/google-auth endpoint tested
□ /api/v2/send-otp endpoint tested  
□ /api/v2/verify-otp endpoint tested
□ bKash payment working (test mode)
□ Landing page looks good
□ Deployed to Coolify
□ Domain configured + SSL working
□ SKILL.md Phase 2 progress updated ✅
→ Then start Phase 3
```
