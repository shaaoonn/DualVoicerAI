# ai_engine/tts_detector.py
"""
Auto-detect language of text -> pick matching edge_tts voice.
Supports fast-langdetect (preferred) or langdetect (fallback).
"""
try:
    from fast_langdetect import detect as fl_detect
    _USE_FAST = True
except ImportError:
    from langdetect import detect as _ld_detect
    _USE_FAST = False

# ISO 639-1 -> preferred edge_tts voice
LANG_TO_VOICE = {
    "bn":    "bn-BD-NabanitaNeural",
    "en":    "en-US-JennyNeural",
    "hi":    "hi-IN-SwaraNeural",
    "ur":    "ur-PK-UzmaNeural",
    "ar":    "ar-SA-ZariyahNeural",
    "zh":    "zh-CN-XiaoxiaoNeural",
    "zh-cn": "zh-CN-XiaoxiaoNeural",
    "zh-tw": "zh-TW-HsiaoChenNeural",
    "ja":    "ja-JP-NanamiNeural",
    "ko":    "ko-KR-SunHiNeural",
    "fr":    "fr-FR-DeniseNeural",
    "de":    "de-DE-KatjaNeural",
    "es":    "es-ES-ElviraNeural",
    "it":    "it-IT-ElsaNeural",
    "pt":    "pt-BR-FranciscaNeural",
    "ru":    "ru-RU-SvetlanaNeural",
    "tr":    "tr-TR-EmelNeural",
    "id":    "id-ID-GadisNeural",
    "ms":    "ms-MY-YasminNeural",
    "th":    "th-TH-PremwadeeNeural",
    "vi":    "vi-VN-HoaiMyNeural",
    "pl":    "pl-PL-ZofiaNeural",
    "nl":    "nl-NL-ColetteNeural",
    "sv":    "sv-SE-SofieNeural",
    "da":    "da-DK-ChristelNeural",
    "fi":    "fi-FI-NooraNeural",
    "cs":    "cs-CZ-VlastaNeural",
    "hu":    "hu-HU-NoemiNeural",
    "ro":    "ro-RO-AlinaNeural",
    "uk":    "uk-UA-PolinaNeural",
    "el":    "el-GR-AthinaNeural",
    "ta":    "ta-IN-PallaviNeural",
    "af":    "af-ZA-AdriNeural",
    "sw":    "sw-KE-ZuriNeural",
}
DEFAULT_VOICE = "en-US-JennyNeural"

def detect_language(text: str) -> str:
    if not text or len(text.strip()) < 3:
        return "en"
    try:
        if _USE_FAST:
            results = fl_detect(text.strip(), model='lite', k=1)
            if results:
                return results[0].get('lang', 'en').lower()
        else:
            return _ld_detect(text.strip()).lower()
    except Exception:
        pass
    return "en"

def get_tts_voice(text: str, fallback_lang: str = "en-US") -> str:
    detected = detect_language(text)
    if detected in LANG_TO_VOICE:
        return LANG_TO_VOICE[detected]
    prefix = detected.split("-")[0]
    if prefix in LANG_TO_VOICE:
        return LANG_TO_VOICE[prefix]
    stt_prefix = fallback_lang.split("-")[0].lower()
    if stt_prefix in LANG_TO_VOICE:
        return LANG_TO_VOICE[stt_prefix]
    return DEFAULT_VOICE
