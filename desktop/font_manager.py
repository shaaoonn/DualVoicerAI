# font_manager.py
"""Font Manager - Registers bundled fonts with Windows and provides
language-to-font mapping for handwriting recognition output.

Fonts are registered per-process using AddFontResourceExW (no admin
privileges needed, fonts only available while the app runs)."""

import os
import ctypes

# ── Win32 Font Registration ──────────────────────────────

FR_PRIVATE = 0x10  # font only visible to this process

_gdi32 = ctypes.windll.gdi32
_AddFontResourceExW = _gdi32.AddFontResourceExW
_AddFontResourceExW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_void_p]
_AddFontResourceExW.restype = ctypes.c_int

_RemoveFontResourceExW = _gdi32.RemoveFontResourceExW
_RemoveFontResourceExW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_void_p]
_RemoveFontResourceExW.restype = ctypes.c_int

# ── Font Directory ───────────────────────────────────────

FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")

# ── Language → Default Font Mapping ──────────────────────
# Keys: language code used in handwriting recognition
# Values: (font_family_name, ttf_filename)
#
# font_family_name = the name Windows/tkinter uses after registration
# ttf_filename = file in desktop/fonts/

LANG_FONTS = {
    # Bengali - user-provided handwriting font
    "bn": ("Li Alinur Nobin Unicode", "Li Alinur Nobin Unicode.ttf"),

    # Latin-script languages - Playpen Sans (handwriting style)
    "en": ("Playpen Sans", "PlaypenSans-Regular.ttf"),
    "es": ("Playpen Sans", "PlaypenSans-Regular.ttf"),
    "fr": ("Playpen Sans", "PlaypenSans-Regular.ttf"),
    "de": ("Playpen Sans", "PlaypenSans-Regular.ttf"),
    "pt": ("Playpen Sans", "PlaypenSans-Regular.ttf"),
    "id": ("Playpen Sans", "PlaypenSans-Regular.ttf"),
    "tr": ("Playpen Sans", "PlaypenSans-Regular.ttf"),
    "vi": ("Playpen Sans", "PlaypenSans-Regular.ttf"),

    # Cyrillic & Greek - also covered by Playpen Sans
    "ru": ("Playpen Sans", "PlaypenSans-Regular.ttf"),
    "el": ("Playpen Sans", "PlaypenSans-Regular.ttf"),

    # Devanagari - Dekko (handwriting feel)
    "hi": ("Dekko", "Dekko-Regular.ttf"),
    "ne": ("Dekko", "Dekko-Regular.ttf"),

    # Arabic script
    "ar": ("Playpen Sans Arabic", "PlaypenSansArabic-Regular.ttf"),

    # Urdu - Nastaliq style
    "ur": ("Noto Nastaliq Urdu", "NotoNastaliqUrdu-Regular.ttf"),

    # Hebrew
    "he": ("Playpen Sans Hebrew", "PlaypenSansHebrew-Regular.ttf"),

    # Thai
    "th": ("Noto Sans Thai", "NotoSansThai-Regular.ttf"),

    # CJK
    "zh": ("Ma Shan Zheng", "MaShanZheng-Regular.ttf"),
    "zh-CN": ("Ma Shan Zheng", "MaShanZheng-Regular.ttf"),
    "zh-TW": ("Ma Shan Zheng", "MaShanZheng-Regular.ttf"),
    "ja": ("Klee One", "KleeOne-Regular.ttf"),
    "ko": ("Gaegu", "Gaegu-Regular.ttf"),

    # South Asian
    "ta": ("Noto Sans Tamil", "NotoSansTamil-Regular.ttf"),
    "te": ("Noto Sans Telugu", "NotoSansTelugu-Regular.ttf"),
    "gu": ("Noto Sans Gujarati", "NotoSansGujarati-Regular.ttf"),
    "pa": ("Noto Sans Gurmukhi", "NotoSansGurmukhi-Regular.ttf"),
    "si": ("Noto Sans Sinhala", "NotoSansSinhala-Regular.ttf"),

    # Southeast Asian
    "my": ("Noto Sans Myanmar", "NotoSansMyanmar-Regular.ttf"),
    "km": ("Battambang", "Battambang-Regular.ttf"),

    # Caucasian
    "ka": ("Noto Sans Georgian", "NotoSansGeorgian-Regular.ttf"),
    "hy": ("Noto Sans Armenian", "NotoSansArmenian-Regular.ttf"),

    # Sinhala (alternate spelling)
    "si-LK": ("Noto Sans Sinhala", "NotoSansSinhala-Regular.ttf"),

    # Sri Lankan variant
    "ta-LK": ("Noto Sans Tamil", "NotoSansTamil-Regular.ttf"),

    # Yaldevi for Sinhala formal
    "si-formal": ("Yaldevi", "Yaldevi-Regular.ttf"),
}

# ── Public API ───────────────────────────────────────────

_registered_fonts = []  # track for cleanup


def register_all_fonts():
    """Register all TTF files in the fonts/ directory with Windows.
    Call once at app startup."""
    global _registered_fonts

    if not os.path.isdir(FONTS_DIR):
        print(f"[FONTS] Directory not found: {FONTS_DIR}")
        return 0

    count = 0
    for fname in os.listdir(FONTS_DIR):
        if not fname.lower().endswith(".ttf"):
            continue
        path = os.path.join(FONTS_DIR, fname)
        result = _AddFontResourceExW(path, FR_PRIVATE, None)
        if result > 0:
            _registered_fonts.append(path)
            count += 1
        else:
            print(f"[FONTS] Failed to register: {fname}")

    print(f"[FONTS] Registered {count} fonts from {FONTS_DIR}")
    return count


def unregister_all_fonts():
    """Remove registered fonts. Call on app exit."""
    for path in _registered_fonts:
        _RemoveFontResourceExW(path, FR_PRIVATE, None)
    _registered_fonts.clear()


def get_font_for_language(lang_code: str) -> str:
    """Return the font family name for a language code.
    Falls back to Playpen Sans (Latin) if unknown."""
    entry = LANG_FONTS.get(lang_code)
    if entry:
        return entry[0]
    # Try base language (e.g., "bn-BD" → "bn")
    base = lang_code.split("-")[0]
    entry = LANG_FONTS.get(base)
    if entry:
        return entry[0]
    return "Playpen Sans"  # fallback


def get_all_hw_fonts() -> list:
    """Return list of all available handwriting font family names
    (deduplicated, for font selector dropdown)."""
    seen = set()
    fonts = []
    for family, _ in LANG_FONTS.values():
        if family not in seen:
            seen.add(family)
            fonts.append(family)
    return fonts
