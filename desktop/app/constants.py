"""App-wide constants — version, default settings, UI palette.

Lifted out of ``main.py`` so:

* Multiple mixin files can import the same constants without going
  through ``main`` (which would create a circular-import nightmare).
* Tweaking a colour or a default value doesn't require touching the
  monolithic main file.

Everything here is **immutable module-level data**. No functions, no
classes. If you find yourself wanting to add logic here, push it into a
separate module instead.
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# Identity & versioning
# ─────────────────────────────────────────────────────────────────────────────

APP_VERSION = "4.0.8"
"""Semantic version string surfaced in Settings → About and the update
check API request. Bump on every release."""

UPDATE_REPO_URL = "https://raw.githubusercontent.com/shaaoonn/DualVoicer-Dist/main"
"""Base URL of the distribution repo that hosts version.json + the
installer EXE. Used by ``updater.UpdateChecker``."""


# ─────────────────────────────────────────────────────────────────────────────
# Settings
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_SETTINGS: dict = {
    "max_opacity": 0.95,
    "idle_opacity": 0.4,
    "scale": 1.0,
    "reading_speed": "1.0",
    "auto_timeout": "15",
    "show_desktop_icon": True,
    "sound_enabled": True,
    "show_labels": True,
    "mic_sensitivity": "normal",
    "noise_threshold": 100,
    "mic_index": None,
    "window_x": None,
    "window_y": 0,
}
"""Default values for every persisted setting key. Merged into the
loaded settings.json at startup so newly-added keys always have a value
even on existing installs.

The fuller ``NEW_SETTINGS_KEYS`` dict in ``config.py`` adds AI / voice /
TTS / shortcut keys on top of this base. See ``settings_io`` mixin for
the merge logic."""


# ─────────────────────────────────────────────────────────────────────────────
# UI dimensions & colours
# ─────────────────────────────────────────────────────────────────────────────

BTN_SIZES: dict = {
    "mini":   36,
    "tiny":   48,
    "small":  56,
    "medium": 72,
    "large":  84,
    "xlarge": 96,
}
"""Pixel size (square) of each of the four main spectrum buttons, keyed
by Settings → Size preset. ``medium`` is the default. Same map is also
inlined at the few module-level call sites in ``main.py`` that need it
before ``VoiceTypingApp`` exists (e.g. ``--pos=`` arg restore)."""

TOOLBAR_BG = "#302D5E"
"""Solid colour drawn behind the toolbar buttons. Approximates the
middle of the toolbar gradient so any pixel that gets composited
behind a button corner blends in nicely. Used by SpectrumButton when
computing corner-blend masks."""


# Drawer palette (the embedded dropdown system under the ▼ arrows).
# Picked to match the widget toolbar's blue-purple gradient.
DRAWER_BG       = "#22214B"  # base drawer panel background
DRAWER_HEADER   = "#2E305E"  # header strip / active-row highlight
DRAWER_ROW_BG   = "#2A2A55"  # idle row background
DRAWER_ROW_HV   = "#3A3870"  # row hover state
DRAWER_ACTIVE   = "#FFD700"  # gold accent on the currently-selected row
DRAWER_TEXT     = "#F0F2F8"  # row text colour
DRAWER_MUTED    = "#9BA3C7"  # secondary text (e.g. ▼ Capture row hint)
DRAWER_BORDER   = "#404778"  # divider line between drawer and toolbar
