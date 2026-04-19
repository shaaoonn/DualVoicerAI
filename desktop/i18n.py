"""Lightweight i18n module for VoiceAI Pro / Dual Voicer AI.

Usage:
    from i18n import tr, set_ui_language, get_ui_language

    label = tr("menu_file")
    status = tr("status_format", p=1, n=5, t="Pen", z=100)
    set_ui_language("bn")   # switch to Bengali
"""

_current_lang = "en"

_TRANSLATIONS = {
    # ─────────────────────── Editor menus ───────────────────────
    "menu_file":          {"en": "File",                "bn": "ফাইল"},
    "menu_new":           {"en": "New",                 "bn": "নতুন"},
    "menu_open":          {"en": "Open...",             "bn": "খুলুন..."},
    "menu_import":        {"en": "Import...",           "bn": "ইম্পোর্ট..."},
    "menu_save":          {"en": "Save",                "bn": "সেভ"},
    "menu_save_as":       {"en": "Save As...",          "bn": "সেভ অ্যাজ..."},
    "menu_export":        {"en": "Export",              "bn": "এক্সপোর্ট"},
    "menu_export_pdf":    {"en": "Export as PDF",       "bn": "PDF হিসেবে এক্সপোর্ট"},
    "menu_export_png":    {"en": "Export as PNG",       "bn": "PNG হিসেবে এক্সপোর্ট"},
    "menu_close":         {"en": "Close",               "bn": "বন্ধ"},
    "menu_page":          {"en": "Page",                "bn": "পেজ"},
    "menu_add_page":      {"en": "Add New Page",        "bn": "নতুন পেজ যোগ"},
    "menu_delete_page":   {"en": "Delete Current Page", "bn": "বর্তমান পেজ ডিলিট"},
    "menu_view":          {"en": "View",                "bn": "ভিউ"},
    "menu_fit":           {"en": "Fit to View",         "bn": "ফিট করুন"},
    "menu_zoom_in":       {"en": "Zoom In",             "bn": "জুম ইন"},
    "menu_zoom_out":      {"en": "Zoom Out",            "bn": "জুম আউট"},
    "menu_show_toolbar":  {"en": "Show/Hide Toolbar",   "bn": "টুলবার দেখান/লুকান"},
    "menu_help":          {"en": "Help",                "bn": "সাহায্য"},
    "menu_about":         {"en": "About",               "bn": "সম্পর্কে"},
    "menu_edit":          {"en": "Edit",                "bn": "এডিট"},
    "menu_undo":          {"en": "Undo",                "bn": "পূর্বাবস্থা"},
    "menu_redo":          {"en": "Redo",                "bn": "পুনরায়"},
    "menu_clear":         {"en": "Clear All",           "bn": "সব মুছুন"},

    # ─────────────────────── Editor toolbar tooltips ───────────────────────
    "tip_pen":         {"en": "Pen",                "bn": "পেন"},
    "tip_highlighter": {"en": "Highlighter",        "bn": "হাইলাইটার"},
    "tip_eraser":      {"en": "Eraser",             "bn": "ইরেজার"},
    "tip_text":        {"en": "Text",               "bn": "টেক্সট"},
    "tip_handwrite":   {"en": "Handwriting",        "bn": "হাতে লেখা"},
    "tip_voice":       {"en": "Voice: {code}",      "bn": "ভয়েস: {code}"},
    "tip_sound":       {"en": "Read Text",          "bn": "শব্দ পড়ুন"},
    "tip_ai":          {"en": "AI Assistant",       "bn": "AI সহায়তা"},
    "tip_screenshot":  {"en": "Screenshot",         "bn": "স্ক্রিনশট"},
    "tip_settings":    {"en": "Settings",           "bn": "সেটিংস"},
    "tip_undo":        {"en": "Undo (Ctrl+Z)",      "bn": "পূর্বাবস্থা (Ctrl+Z)"},
    "tip_redo":        {"en": "Redo (Ctrl+Y)",      "bn": "পুনরায় (Ctrl+Y)"},
    "tip_clear":       {"en": "Clear All",          "bn": "সব মুছুন"},
    "tip_close":       {"en": "Close",              "bn": "বন্ধ"},
    "tip_fullscreen":  {"en": "Fullscreen (F11)",   "bn": "পূর্ণ পর্দা (F11)"},
    "tip_pan":         {"en": "Pan (Hand)",         "bn": "প্যান (হাত)"},
    "tip_select":      {"en": "Select",             "bn": "সিলেক্ট"},
    "tip_color":       {"en": "Color",              "bn": "রং"},
    "tip_width":       {"en": "Width",              "bn": "প্রস্থ"},

    # ─────────────────────── Status bar / tool labels ───────────────────────
    "status_format":   {"en": "Page: {p}/{n} | Tool: {t} | {z}%",
                        "bn": "পেজ: {p}/{n} | টুল: {t} | {z}%"},
    "tool_pen":         {"en": "Pen",         "bn": "পেন"},
    "tool_highlighter": {"en": "Highlighter", "bn": "হাইলাইটার"},
    "tool_eraser":      {"en": "Eraser",      "bn": "ইরেজার"},
    "tool_text":        {"en": "Text",        "bn": "টেক্সট"},
    "tool_pan":         {"en": "Pan",         "bn": "প্যান"},
    "tool_select":      {"en": "Select",      "bn": "সিলেক্ট"},
    "tool_handwrite":   {"en": "Handwriting", "bn": "হাতে লেখা"},

    # ─────────────────────── Window titles ───────────────────────
    "editor_title":     {"en": "Editor — VoiceAI Pro",
                         "bn": "এডিটর — Dual Voicer AI"},
    "settings_title":   {"en": "Settings",  "bn": "সেটিংস"},
    "app_title":        {"en": "VoiceAI Pro", "bn": "Dual Voicer AI"},

    # ─────────────────────── Settings panel tabs ───────────────────────
    "tab_general":      {"en": "General",      "bn": "সাধারণ"},
    "tab_voice":        {"en": "Voice & TTS",  "bn": "ভয়েস ও TTS"},
    "tab_appearance":   {"en": "Appearance",   "bn": "চেহারা"},
    "tab_advanced":     {"en": "Advanced",     "bn": "অ্যাডভান্সড"},
    "tab_about":        {"en": "About",        "bn": "সম্পর্কে"},

    # Settings labels
    "lbl_language":     {"en": "Interface Language",  "bn": "ইন্টারফেস ভাষা"},
    "lbl_voice_lang":   {"en": "Voice Language",      "bn": "ভয়েস ভাষা"},
    "lbl_tts_voice":    {"en": "TTS Voice",           "bn": "TTS ভয়েস"},
    "lbl_speed":        {"en": "Speed",               "bn": "গতি"},
    "lbl_volume":       {"en": "Volume",              "bn": "ভলিউম"},
    "lbl_theme":        {"en": "Theme",               "bn": "থিম"},
    "lbl_restart_note": {"en": "Restart required for some changes",
                         "bn": "কিছু পরিবর্তনের জন্য রিস্টার্ট প্রয়োজন"},

    # Buttons
    "btn_save":   {"en": "Save",   "bn": "সেভ"},
    "btn_cancel": {"en": "Cancel", "bn": "বাতিল"},
    "btn_apply":  {"en": "Apply",  "bn": "প্রয়োগ"},
    "btn_close":  {"en": "Close",  "bn": "বন্ধ"},
    "btn_reset":  {"en": "Reset",  "bn": "রিসেট"},
    "btn_yes":    {"en": "Yes",    "bn": "হ্যাঁ"},
    "btn_no":     {"en": "No",     "bn": "না"},
    "btn_ok":     {"en": "OK",     "bn": "ঠিক আছে"},

    # ─────────────────────── Dialogs ───────────────────────
    "dlg_unsaved_title":   {"en": "Unsaved Changes",
                            "bn": "অসংরক্ষিত পরিবর্তন"},
    "dlg_unsaved_msg":     {"en": "You have unsaved changes. Save before closing?",
                            "bn": "অসংরক্ষিত পরিবর্তন আছে। বন্ধ করার আগে সেভ করবেন?"},
    "dlg_clear_title":     {"en": "Clear All",
                            "bn": "সব মুছুন"},
    "dlg_clear_msg":       {"en": "Clear all annotations on this page?",
                            "bn": "এই পেজের সব এনোটেশন মুছবেন?"},
    "dlg_delete_page":     {"en": "Delete this page?",
                            "bn": "এই পেজ ডিলিট করবেন?"},
    "dlg_error_title":     {"en": "Error",         "bn": "ত্রুটি"},
    "dlg_warning_title":   {"en": "Warning",       "bn": "সতর্কতা"},
    "dlg_info_title":      {"en": "Information",   "bn": "তথ্য"},
    "dlg_success_title":   {"en": "Success",       "bn": "সফল"},
    "dlg_save_failed":     {"en": "Failed to save: {err}",
                            "bn": "সেভ ব্যর্থ: {err}"},
    "dlg_open_failed":     {"en": "Failed to open: {err}",
                            "bn": "খুলতে ব্যর্থ: {err}"},
    "dlg_export_done":     {"en": "Exported to {path}",
                            "bn": "এক্সপোর্ট হয়েছে: {path}"},

    # ─────────────────────── Pen toolbar ───────────────────────
    "pt_zoom":         {"en": "Zoom",     "bn": "জুম"},
    "pt_separator":    {"en": "—",        "bn": "—"},
    "pt_close_pen":    {"en": "Close Pen Mode", "bn": "পেন মোড বন্ধ"},

    # ─────────────────────── Main widget ───────────────────────
    "main_listening":  {"en": "Listening...",      "bn": "শুনছি..."},
    "main_processing": {"en": "Processing...",     "bn": "প্রক্রিয়াকরণ..."},
    "main_speaking":   {"en": "Speaking...",       "bn": "বলছি..."},
    "main_ready":      {"en": "Ready",             "bn": "প্রস্তুত"},
    "main_paused":     {"en": "Paused",            "bn": "বিরতি"},
    "main_idle":       {"en": "Idle",              "bn": "নিষ্ক্রিয়"},
    "main_error":      {"en": "Error",             "bn": "ত্রুটি"},

    # ─────────────────────── AI / Screenshot ───────────────────────
    "ai_analyzing":    {"en": "Analyzing screenshot...",
                        "bn": "স্ক্রিনশট বিশ্লেষণ..."},
    "ai_no_text":      {"en": "No text found in image",
                        "bn": "ছবিতে কোনো টেক্সট পাওয়া যায়নি"},
    "ai_failed":       {"en": "AI request failed: {err}",
                        "bn": "AI অনুরোধ ব্যর্থ: {err}"},
    "ai_system_prompt": {
        "en": "You are a helpful assistant. Analyze the screenshot and provide a clear, concise response in English.",
        "bn": "আপনি একজন সহায়ক সহকারী। স্ক্রিনশটটি বিশ্লেষণ করে বাংলায় স্পষ্ট ও সংক্ষিপ্ত উত্তর দিন।"
    },

    # ─────────────────────── Misc ───────────────────────
    "loading":     {"en": "Loading...",   "bn": "লোড হচ্ছে..."},
    "saving":      {"en": "Saving...",    "bn": "সংরক্ষণ..."},
    "saved":       {"en": "Saved",        "bn": "সংরক্ষিত"},
    "modified":    {"en": "Modified",     "bn": "পরিবর্তিত"},
    "untitled":    {"en": "Untitled",     "bn": "শিরোনামহীন"},
}

# Available languages for the picker UI
AVAILABLE_LANGUAGES = [
    ("en", "English"),
    ("bn", "Bengali (বাংলা)"),
]


def tr(key, **kwargs):
    """Translate a key into the current UI language.

    Falls back to English, then to the key itself if missing.
    Supports {placeholder} formatting via kwargs.
    """
    entry = _TRANSLATIONS.get(key, {})
    text = entry.get(_current_lang) or entry.get("en") or key
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            pass
    return text


def set_ui_language(lang):
    """Set the active UI language (e.g., 'en' or 'bn')."""
    global _current_lang
    if lang in {code for code, _ in AVAILABLE_LANGUAGES}:
        _current_lang = lang


def get_ui_language():
    """Return the currently active UI language code."""
    return _current_lang


def get_available_languages():
    """Return list of (code, display_name) tuples for the language picker."""
    return list(AVAILABLE_LANGUAGES)
