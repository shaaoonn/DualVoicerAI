# subscription/freemium.py
import os, json, datetime

class FreemiumGate:
    TRIAL_HOURS     = 24
    GATED_FEATURES  = {"ai", "tts", "punctuation", "settings"}

    def __init__(self, app_data_dir: str):
        self._file = os.path.join(app_data_dir, ".freemium.json")
        self._data = self._load()

    def _load(self) -> dict:
        if os.path.exists(self._file):
            try:
                with open(self._file) as f: return json.load(f)
            except (json.JSONDecodeError, OSError): pass
        data = {"first_install": datetime.datetime.now().isoformat()}
        self._save(data)
        return data

    def _save(self, data):
        try:
            os.makedirs(os.path.dirname(self._file), exist_ok=True)
            with open(self._file, "w") as f: json.dump(data, f)
        except (json.JSONDecodeError, OSError): pass

    def is_trial_active(self) -> bool:
        try:
            installed = datetime.datetime.fromisoformat(self._data["first_install"])
            return (datetime.datetime.now()-installed).total_seconds() < self.TRIAL_HOURS*3600
        except (KeyError, ValueError): return False

    def is_subscribed(self, app) -> bool:
        return getattr(app, "is_authenticated", False)

    def can_use(self, feature: str, app) -> bool:
        from config import DEV_MODE
        if DEV_MODE:           return True   # Phase 1: always allowed
        if feature == "voice_typing": return True
        if feature not in self.GATED_FEATURES: return True
        if self.is_trial_active():   return True
        if self.is_subscribed(app):  return True
        return False

    def get_remaining_hours(self) -> float:
        try:
            installed = datetime.datetime.fromisoformat(self._data["first_install"])
            remaining = self.TRIAL_HOURS*3600 - (datetime.datetime.now()-installed).total_seconds()
            return max(0.0, remaining/3600)
        except (KeyError, ValueError): return 0.0

    def get_lock_message(self, feature: str) -> str:
        msgs = {
            "ai":          "\U0001f916 AI \u09ab\u09bf\u099a\u09be\u09b0 \u09ac\u09cd\u09af\u09ac\u09b9\u09be\u09b0 \u0995\u09b0\u09a4\u09c7 \u09b8\u09be\u09ac\u09b8\u09cd\u0995\u09cd\u09b0\u09be\u0987\u09ac \u0995\u09b0\u09c1\u09a8",
            "tts":         "\U0001f50a Text-to-Speech \u09ac\u09cd\u09af\u09ac\u09b9\u09be\u09b0 \u0995\u09b0\u09a4\u09c7 \u09b8\u09be\u09ac\u09b8\u09cd\u0995\u09cd\u09b0\u09be\u0987\u09ac \u0995\u09b0\u09c1\u09a8",
            "punctuation": "\u270f\ufe0f \u09a6\u09be\u09dc\u09bf \u0995\u09ae\u09be \u09b8\u09cd\u09ac\u09df\u0982\u0995\u09cd\u09b0\u09bf\u09df \u0995\u09b0\u09a4\u09c7 \u09b8\u09be\u09ac\u09b8\u09cd\u0995\u09cd\u09b0\u09be\u0987\u09ac \u0995\u09b0\u09c1\u09a8",
            "settings":    "\u2699\ufe0f \u09b8\u09c7\u099f\u09bf\u0982\u09b8 \u09aa\u09b0\u09bf\u09ac\u09b0\u09cd\u09a4\u09a8 \u0995\u09b0\u09a4\u09c7 \u09b8\u09be\u09ac\u09b8\u09cd\u0995\u09cd\u09b0\u09be\u0987\u09ac \u0995\u09b0\u09c1\u09a8",
        }
        return msgs.get(feature, "\u09b8\u09be\u09ac\u09b8\u09cd\u0995\u09cd\u09b0\u09bf\u09aa\u09b6\u09a8 \u09aa\u09cd\u09b0\u09df\u09cb\u099c\u09a8")
