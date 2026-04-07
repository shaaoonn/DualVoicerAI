"""Remote config fetcher with cache + hardcoded fallback.

Flow: local cache (if fresh) → remote URL → hardcoded defaults.
This lets us change API endpoints without pushing an app update.
"""

import json
import os
import time

import requests

_REMOTE_URL = "https://raw.githubusercontent.com/shaaoonn/DualVoicerAI/main/remote_config.json"
_CACHE_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "DualVoicer")
_CACHE_FILE = os.path.join(_CACHE_DIR, "remote_config_cache.json")
_CACHE_TTL = 3600  # 1 hour

DEFAULTS = {
    "handwriting_api_url": "https://www.google.com/inputtools/request?ime=handwriting",
    "handwriting_enabled": True,
}

_cached: dict | None = None
_cached_at: float = 0


def get_remote_config() -> dict:
    """Return merged config: remote values override defaults."""
    global _cached, _cached_at

    now = time.time()

    # 1. In-memory cache (hot path)
    if _cached and (now - _cached_at) < _CACHE_TTL:
        return _cached

    # 2. Disk cache
    try:
        if os.path.exists(_CACHE_FILE):
            mtime = os.path.getmtime(_CACHE_FILE)
            if (now - mtime) < _CACHE_TTL:
                with open(_CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                _cached = {**DEFAULTS, **data}
                _cached_at = now
                return _cached
    except (OSError, json.JSONDecodeError):
        pass

    # 3. Remote fetch
    try:
        resp = requests.get(_REMOTE_URL, timeout=5)
        resp.raise_for_status()
        data = resp.json()

        # Save to disk cache
        try:
            os.makedirs(_CACHE_DIR, exist_ok=True)
            with open(_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError:
            pass

        _cached = {**DEFAULTS, **data}
        _cached_at = now
        return _cached
    except (requests.RequestException, ValueError, KeyError):
        pass

    # 4. Hardcoded fallback
    _cached = dict(DEFAULTS)
    _cached_at = now
    return _cached
