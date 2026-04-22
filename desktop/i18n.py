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
    "editor_title":     {"en": "Editor - VoiceAI Pro",
                         "bn": "এডিটর - Dual Voicer AI"},
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
    "pt_separator":    {"en": "-",        "bn": "-"},
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

    # ─────────────────────── Settings panel - sidebar nav ───────────────────────
    "set_nav_general":      {"en": "⚙️  General",       "bn": "⚙️  সাধারণ"},
    "set_nav_language":     {"en": "🌐  Language",      "bn": "🌐  ভাষা"},
    "set_nav_ai":           {"en": "🤖  AI Settings",   "bn": "🤖  AI সেটিংস"},
    "set_nav_tts":          {"en": "🔊  TTS",           "bn": "🔊  টিটিএস"},
    "set_nav_subscription": {"en": "🔑  Subscription",  "bn": "🔑  সাবস্ক্রিপশন"},
    "set_nav_about":        {"en": "ℹ️  About",         "bn": "ℹ️  সম্পর্কে"},

    "set_btn_save":         {"en": "Save",              "bn": "সংরক্ষণ"},
    "set_btn_close":        {"en": "Close",             "bn": "বন্ধ করুন"},
    "set_window_title":     {"en": "{app} - Settings",  "bn": "{app} - সেটিংস"},

    # ─────────────────────── Settings panel - General tab ───────────────────────
    "set_sec_account":      {"en": "👤 Account",        "bn": "👤 অ্যাকাউন্ট"},
    "set_btn_logout":       {"en": "Logout",            "bn": "লগআউট"},
    "set_acct_expiry":      {"en": "Expires: {expiry}  •  Devices: {dev}/{max}",
                             "bn": "মেয়াদ: {expiry}  •  ডিভাইস: {dev}/{max}"},

    "set_sec_settings":     {"en": "🔧 Settings",       "bn": "🔧 সাধারণ"},
    "set_lbl_desktop_icon": {"en": "Desktop Icon",      "bn": "ডেস্কটপ আইকন"},
    "set_lbl_sound_fx":     {"en": "Sound Effects",     "bn": "সাউন্ড ইফেক্ট"},
    "set_lbl_btn_labels":   {"en": "Button Labels",     "bn": "বাটন লেবেল"},

    "set_sec_editor":       {"en": "📝 Editor",         "bn": "📝 এডিটর"},
    "set_btn_open_editor":  {"en": "📝 Open Editor",    "bn": "📝 এডিটর খুলুন"},

    "set_sec_ui_lang":      {"en": "🗣️ Interface Language",
                             "bn": "🗣️ ইন্টারফেস ভাষা"},
    "set_lbl_restart_lang": {"en": "Restart the app to fully apply the language change.",
                             "bn": "ভাষা পরিবর্তন সম্পূর্ণভাবে প্রয়োগ করতে অ্যাপ পুনরায় চালু করুন।"},

    "set_sec_microphone":   {"en": "🎙️ Microphone",     "bn": "🎙️ মাইক্রোফোন"},
    "set_lbl_noise_filter": {"en": "Noise Filter",      "bn": "নয়েজ ফিল্টার"},
    "set_lbl_pause_left":   {"en": "← Less Pause",      "bn": "← মাঝে বিরতি"},
    "set_lbl_pause_right":  {"en": "More Sensitive →",  "bn": "আবার লিখি →"},

    "set_sec_appearance":   {"en": "🎨 Appearance & Behavior",
                             "bn": "🎨 চেহারা ও আচরণ"},
    "set_lbl_idle_opacity": {"en": "Idle Opacity",      "bn": "নিষ্ক্রিয় অস্বচ্ছতা"},
    "set_lbl_active_opacity":{"en": "Active Opacity",   "bn": "সক্রিয় অস্বচ্ছতা"},
    "set_lbl_widget_size":  {"en": "Widget Size",       "bn": "উইজেট আকার"},
    "set_lbl_auto_timeout": {"en": "Auto Stop Timeout", "bn": "অটো স্টপ টাইমআউট"},

    "set_sec_actions":      {"en": "🛠️ Actions",        "bn": "🛠️ অ্যাকশন"},
    "set_btn_reset_engine": {"en": "⟳  Reset Engine",   "bn": "⟳  ইঞ্জিন রিসেট"},
    "set_btn_update":       {"en": "↑  Update (v{ver})","bn": "↑  আপডেট (v{ver})"},

    "set_sec_screenshot":   {"en": "📷 Screenshot Save Folder",
                             "bn": "📷 স্ক্রীনশট সেভ ফোল্ডার"},
    "set_lbl_screenshot_help": {"en": "Choose where AI screenshots are saved on your computer.",
                                "bn": "AI স্ক্রীনশট কোথায় সেভ হবে সেই ফোল্ডার নির্বাচন করুন।"},
    "set_lbl_not_set":      {"en": "Not set - using default Pictures folder",
                             "bn": "সেট করা নেই - ডিফল্ট Pictures ফোল্ডার ব্যবহৃত হবে"},
    "set_btn_browse":       {"en": "Browse",            "bn": "ব্রাউজ"},
    "set_dlg_pick_ss_dir":  {"en": "Screenshot Save Folder",
                             "bn": "স্ক্রিনশট সংরক্ষণ ফোল্ডার"},

    # ─────────────────────── Settings panel - Language tab ───────────────────────
    "set_sec_voice_lang":   {"en": "🌐 Voice Typing Language",
                             "bn": "🌐 ভয়েস টাইপিং ভাষা"},
    "set_voice_lang_help":  {"en": "Pick a language for each button. Powered by Google Speech API.",
                             "bn": "প্রতিটি বাটনের জন্য আলাদা ভাষা সিলেক্ট করুন। Google Speech API ব্যবহার হয়।"},
    "set_lbl_btn1":         {"en": "🎙️ Button 1 (Left)",  "bn": "🎙️ বাটন ১ (বাম)"},
    "set_lbl_btn2":         {"en": "🎙️ Button 2 (Right)", "bn": "🎙️ বাটন ২ (মাঝ)"},
    "set_lang_change_note": {"en": "💡 Language changes apply instantly.",
                             "bn": "💡 ভাষা পরিবর্তন তাৎক্ষণিকভাবে কার্যকর হয়।"},

    # ─────────────────────── Settings panel - AI tab ───────────────────────
    "set_sec_ai":           {"en": "🤖 AI Assistant",   "bn": "🤖 AI সহকারী"},
    "set_ai_hotkeys":       {"en": "Ctrl+Shift+A: AI on selected text  |  Ctrl+Shift+V: Smart Paste",
                             "bn": "Ctrl+Shift+A: সিলেক্টেড টেক্সটে AI  |  Ctrl+Shift+V: স্মার্ট পেস্ট"},
    "set_lbl_enable_ai":    {"en": "Enable AI",          "bn": "AI সক্রিয় করুন"},

    "set_sec_output_fmt":   {"en": "Output Format",     "bn": "আউটপুট ফরম্যাট"},
    "set_fmt_plain":        {"en": "Plain Text",        "bn": "প্লেইন টেক্সট"},
    "set_fmt_plain_desc":   {"en": "No formatting - straight text",
                             "bn": "কোনো formatting নেই - সরাসরি টেক্সট"},
    "set_fmt_rich":         {"en": "Rich (Markdown)",   "bn": "রিচ (Markdown)"},
    "set_fmt_rich_desc":    {"en": "**bold**, _italic_, • bullet etc.",
                             "bn": "**bold**, _italic_, • bullet সহ"},

    "set_sec_ai_model":     {"en": "AI Model",          "bn": "AI মডেল"},
    "set_ai_model_note":    {"en": "Gemini Flash = Fast | GPT-4o Mini = Smart | Claude Haiku = Refined",
                             "bn": "Gemini Flash = দ্রুত | GPT-4o Mini = স্মার্ট | Claude Haiku = সুনির্দিষ্ট"},

    "set_sec_sys_prompt":   {"en": "System Instruction","bn": "সিস্টেম ইন্সট্রাকশন"},
    "set_sys_prompt_help":  {"en": "Tell the AI how to behave. e.g. 'Always respond in formal English.'",
                             "bn": "AI-কে কীভাবে আচরণ করতে হবে বলুন।  'সবসময় ফরমাল বাংলায় লিখবে'"},
    "set_sys_prompt_default":{"en": "You are a skilled writing assistant. Keep replies concise.",
                             "bn": "তুমি একজন দক্ষ বাংলা ও ইংরেজি লেখক সহকারী। সংক্ষিপ্ত উত্তর দাও।"},

    "set_sec_img_prompt":   {"en": "🖼️ Image System Instruction (Screenshot AI)",
                             "bn": "🖼️ ইমেজ সিস্টেম ইন্সট্রাকশন (স্ক্রিনশট AI)"},
    "set_img_prompt_help":  {"en": "Used when you press the AI button on a screenshot. Leave blank for default.",
                             "bn": "স্ক্রিনশট নিয়ে AI বাটন চাপলে এই ইন্সট্রাকশন ব্যবহার হবে। খালি রাখলে ডিফল্ট ব্যবহার হবে।"},

    "set_sec_kb":           {"en": "📚 Knowledge Base (for Smart Paste)",
                             "bn": "📚 নলেজ বেজ (Smart Paste-এর জন্য)"},
    "set_kb_help":          {"en": "Pressing Ctrl+Shift+V uses this info to write a reply to the copied message.\n"
                                   "Examples: course prices, office hours, FAQ, return policy etc.",
                             "bn": "Ctrl+Shift+V চাপলে AI এই তথ্য ব্যবহার করে কপি করা মেসেজের উত্তর তৈরি করবে।\n"
                                   "উদাহরণ: কোর্সের দাম, অফিস সময়, FAQ, রিটার্ন পলিসি ইত্যাদি।"},
    "set_kb_footer":        {"en": "⌨️  Ctrl+Shift+V  →  Copied message + Knowledge Base → AI reply pasted",
                             "bn": "⌨️  Ctrl+Shift+V  →  কপি করা মেসেজ + নলেজ বেজ → AI reply paste হবে"},

    # ─────────────────────── Settings panel - TTS tab ───────────────────────
    "set_sec_tts":          {"en": "🔊 Text-to-Speech Settings",
                             "bn": "🔊 Text-to-Speech সেটিংস"},
    "set_lbl_tts_auto":     {"en": "Auto-detect language",
                             "bn": "ভাষা স্বয়ংক্রিয়ভাবে শনাক্ত করুন"},
    "set_tts_auto_help":    {"en": "On: detect typed text language and use the right voice\n"
                                   "Off: pick a voice manually below (may not work for all languages)",
                             "bn": "চালু: typed text-এর ভাষা detect করে সঠিক voice বাজাবে\n"
                                   "বন্ধ: নিচ থেকে manually voice চুন (সব ভাষায় কাজ নাও করতে পারে)"},
    "set_lbl_reading_speed":{"en": "Reading Speed",     "bn": "পড়ার গতি"},

    # ─────────────────────── Settings panel - Subscription tab ───────────────────────
    "set_sec_subscription": {"en": "🔑 Plan & Subscription",
                             "bn": "🔑 প্ল্যান ও সাবস্ক্রিপশন"},
    "set_current_plan":     {"en": "Current Plan: {plan}",
                             "bn": "বর্তমান প্ল্যান: {plan}"},
    "set_plan_free":        {"en": "Free",              "bn": "ফ্রি"},
    "set_plan_basic":       {"en": "Basic",             "bn": "বেসিক"},
    "set_plan_pro":         {"en": "Pro",               "bn": "প্রো"},
    "set_plan_team":        {"en": "Team",              "bn": "টিম"},
    "set_plan_free_price":  {"en": "$0",                "bn": "৳০"},
    "set_plan_basic_price": {"en": "$2/mo",             "bn": "৳১৯৯/মাস"},
    "set_plan_pro_price":   {"en": "$4/mo",             "bn": "৳৩৯৯/মাস"},
    "set_plan_team_price":  {"en": "$10/mo",            "bn": "৳৮৯৯/মাস"},
    "set_plan_free_feat":   {"en": "Voice typing for life",
                             "bn": "Voice typing আজীবন"},
    "set_plan_basic_feat":  {"en": "AI 200 calls/day, 2 PCs",
                             "bn": "AI 200 calls/day, 2 PC"},
    "set_plan_pro_feat":    {"en": "AI unlimited, 3 PCs",
                             "bn": "AI আনলিমিটেড, 3 PC"},
    "set_plan_team_feat":   {"en": "AI unlimited, 10 PCs",
                             "bn": "AI আনলিমিটেড, 10 PC"},
    "set_btn_subscribe":    {"en": "Subscribe →",       "bn": "সাবস্ক্রাইব করুন →"},

    # ─────────────────────── Settings panel - About tab ───────────────────────
    "set_about_powered":    {"en": "Powered by EJOSB IT\nejobsit.com",
                             "bn": "Powered by EJOSB IT\nejobsit.com"},
    "set_btn_visit_website":{"en": "Visit Website",     "bn": "ওয়েবসাইট ভিজিট করুন"},
    "set_about_copyright":  {"en": "© 2025-2026 EJOSB IT • Developed by Ahsanullah Shaon",
                             "bn": "© 2025-2026 EJOSB IT • Developed by Ahsanullah Shaon"},
    "set_about_version":    {"en": "Version {ver}",     "bn": "সংস্করণ {ver}"},

    # ─────────────────────── Misc ───────────────────────
    "loading":     {"en": "Loading...",   "bn": "লোড হচ্ছে..."},
    "saving":      {"en": "Saving...",    "bn": "সংরক্ষণ..."},
    "saved":       {"en": "Saved",        "bn": "সংরক্ষিত"},
    "modified":    {"en": "Modified",     "bn": "পরিবর্তিত"},
    "untitled":    {"en": "Untitled",     "bn": "শিরোনামহীন"},

    # ─────────────────────── Editor dialogs ───────────────────────
    "dlg_delete_title":      {"en": "Delete",                "bn": "ডিলিট"},
    "dlg_delete_last_page":  {"en": "Cannot delete the last page.",
                              "bn": "শেষ পেজ ডিলিট করা যাবে না।"},
    "dlg_delete_page_title": {"en": "Delete Page",           "bn": "পেজ ডিলিট"},
    "dlg_delete_page_q":     {"en": "Delete page {n}?",      "bn": "পেজ {n} ডিলিট করতে চান?"},
    "dlg_zoom_label":        {"en": "Zoom {z}%",             "bn": "জুম {z}%"},
    "color_white":           {"en": "White",                 "bn": "সাদা"},
    "color_black":           {"en": "Black",                 "bn": "কালো"},
    "color_gray":            {"en": "Gray",                  "bn": "ধূসর"},
    "color_graph":           {"en": "Graph Paper",           "bn": "গ্রাফ পেপার"},
    "dlg_new_file_title":    {"en": "New File",              "bn": "নতুন ফাইল"},
    "dlg_lbl_background":    {"en": "Background",            "bn": "ব্যাকগ্রাউন্ড"},
    "dlg_lbl_page_size":     {"en": "Page Size",             "bn": "পেজ সাইজ"},
    "dlg_btn_custom_size":   {"en": "Custom Size (inches)...","bn": "কাস্টম সাইজ (ইঞ্চি)..."},
    "dlg_width_title":       {"en": "Width",                 "bn": "প্রস্থ"},
    "dlg_width_prompt":      {"en": "Width (inches):",       "bn": "প্রস্থ (ইঞ্চি):"},
    "dlg_height_title":      {"en": "Height",                "bn": "উচ্চতা"},
    "dlg_height_prompt":     {"en": "Height (inches):",      "bn": "উচ্চতা (ইঞ্চি):"},
    "dlg_error_title":       {"en": "Error",                 "bn": "ত্রুটি"},
    "dlg_info_title":        {"en": "Info",                  "bn": "তথ্য"},
    "dlg_success_title":     {"en": "Success",               "bn": "সফল"},
    "dlg_invalid_number":    {"en": "Please enter a valid number.",
                              "bn": "সঠিক সংখ্যা দিন।"},
    "ftype_all_supported":   {"en": "All Supported",         "bn": "সকল সমর্থিত"},
    "ftype_image":           {"en": "Image",                 "bn": "ছবি"},
    "ftype_dvai":            {"en": "DVAI Project",          "bn": "DVAI প্রজেক্ট"},
    "err_image_open":        {"en": "Could not open image:\n{e}",
                              "bn": "ছবি খুলতে পারেনি:\n{e}"},
    "err_image_import":      {"en": "Could not import image:\n{e}",
                              "bn": "ছবি ইম্পোর্ট করতে পারেনি:\n{e}"},
    "err_pymupdf_missing":   {"en": "PyMuPDF is not installed.\npip install PyMuPDF",
                              "bn": "PyMuPDF ইন্সটল নেই।\npip install PyMuPDF"},
    "err_pymupdf_short":     {"en": "PyMuPDF is not installed.",
                              "bn": "PyMuPDF ইন্সটল নেই।"},
    "err_pdf_open":          {"en": "Could not open PDF:\n{e}",
                              "bn": "PDF খুলতে পারেনি:\n{e}"},
    "err_pdf_import":        {"en": "Could not import PDF:\n{e}",
                              "bn": "PDF ইম্পোর্ট করতে পারেনি:\n{e}"},
    "err_file_load":         {"en": "Could not load file:\n{e}",
                              "bn": "ফাইল লোড করতে পারেনি:\n{e}"},
    "msg_loading_n":         {"en": "Loading... {i}/{n}",
                              "bn": "লোড হচ্ছে... {i}/{n}"},
    "msg_exporting_n":       {"en": "Exporting... {i}/{n}",
                              "bn": "এক্সপোর্ট হচ্ছে... {i}/{n}"},
    "msg_no_pages_export":   {"en": "No pages to export.",
                              "bn": "এক্সপোর্ট করার মতো পেজ নেই।"},
    "dlg_save_pdf_title":    {"en": "Save PDF",              "bn": "PDF সেভ করুন"},
    "dlg_pdf_export_title":  {"en": "PDF Export",            "bn": "PDF এক্সপোর্ট"},
    "msg_pdf_exported":      {"en": "PDF exported:\n{path}",
                              "bn": "PDF এক্সপোর্ট হয়েছে:\n{path}"},
    "err_pdf_export":        {"en": "PDF export failed:\n{e}",
                              "bn": "PDF এক্সপোর্ট ব্যর্থ:\n{e}"},
    "dlg_save_image_title":  {"en": "Save Image",            "bn": "ইমেজ সেভ করুন"},
    "dlg_save_image_multi":  {"en": "Save Image (page numbers will be appended)",
                              "bn": "ইমেজ সেভ করুন (পেজ নম্বর যোগ হবে)"},
    "msg_saved_to":          {"en": "Saved to:\n{path}",
                              "bn": "সেভ হয়েছে:\n{path}"},
    "msg_saved_pages":       {"en": "{n} pages saved:\n{base}_*.{ext}",
                              "bn": "{n} পেজ সেভ হয়েছে:\n{base}_*.{ext}"},
    "err_save_failed":       {"en": "Save failed:\n{e}",
                              "bn": "সেভ ব্যর্থ:\n{e}"},

    # ─────────────────────── Pen toolbar ───────────────────────
    "tb_separator":          {"en": "── More ──",            "bn": "── আরো ──"},
    "tb_zoom":               {"en": "Zoom {z}%",             "bn": "জুম {z}%"},
    "tb_thickness_pen":      {"en": "Pen",                   "bn": "পেন"},
    "tb_thickness_font":     {"en": "Font",                  "bn": "ফন্ট"},
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


# Per-script font choice - Segoe UI has no Bengali glyphs, so on Windows it
# falls back to a low-quality bitmap renderer that produces visibly aliased
# Bengali text. Nirmala UI is Microsoft's Indic font with proper anti-aliasing
# and ligatures and looks dramatically crisper than the fallback.
_FONT_BY_LANG = {
    "en": "Segoe UI",
    "bn": "Nirmala UI",
}


def get_ui_font():
    """Return the best UI font family for the active language."""
    return _FONT_BY_LANG.get(_current_lang, "Segoe UI")
