# ai_engine/screenshot_analyzer.py
"""Screenshot AI Analyzer - Captures clipboard image and sends to vision model.

Features:
  - Grabs image from Windows clipboard (after snip/screenshot)
  - Converts to base64 for OpenRouter vision API
  - Smart system prompt: extracts text, describes images,
    auto-replies to chat screenshots (Facebook/WhatsApp/Messenger)
"""

import base64, io, time
from typing import Optional, Tuple


# ── System prompt for screenshot analysis ──
SCREENSHOT_SYSTEM_PROMPT = """তুমি একজন অত্যন্ত দক্ষ ভিজ্যুয়াল বিশ্লেষক এবং AI সহকারী। ব্যবহারকারী তোমাকে একটি স্ক্রিনশট দিচ্ছে। নিচের নিয়ম অনুসরণ করো:

📋 যদি স্ক্রিনশটে টেক্সট থাকে:
- সমস্ত দৃশ্যমান টেক্সট হুবহু লিখে দাও (OCR)
- টেক্সটের ভাষা বুঝে সেই ভাষায় লেখো

🖼️ যদি কোনো ছবি/গ্রাফিক্স থাকে:
- ছবিতে কী আছে তা বর্ণনা করো
- চার্ট/গ্রাফ থাকলে ডেটা ব্যাখ্যা করো

💬 যদি এটি চ্যাট/মেসেজিং অ্যাপের স্ক্রিনশট হয় (Facebook, WhatsApp, Messenger, Telegram, Viber, IMO, Instagram DM, Discord, Slack, Teams ইত্যাদি):
- কথোপকথনের সারসংক্ষেপ দাও
- সর্বশেষ মেসেজের উপযুক্ত উত্তর লিখে দাও
- উত্তরের ভাষা কথোপকথনের ভাষা অনুসারে হবে
- উত্তরটি স্বাভাবিক, বন্ধুসুলভ এবং প্রাসঙ্গিক হবে

📧 যদি ইমেইলের স্ক্রিনশট হয়:
- ইমেইলের সারসংক্ষেপ দাও
- উপযুক্ত রিপ্লাই ড্রাফট লিখে দাও

📄 যদি ডকুমেন্ট/ওয়েবপেজের স্ক্রিনশট হয়:
- মূল বিষয়বস্তু সংক্ষেপে তুলে ধরো

⚠️ গুরুত্বপূর্ণ নিয়ম:
- সংক্ষিপ্ত কিন্তু সম্পূর্ণ উত্তর দাও
- কোনো ভূমিকা বা অপ্রয়োজনীয় ব্যাখ্যা দিও না
- সরাসরি কাজের উত্তর দাও"""


def grab_clipboard_image() -> Optional[str]:
    """Grab image from clipboard and return as base64 data URL.
    Returns None if no image in clipboard."""
    try:
        from PIL import ImageGrab
        img = ImageGrab.grabclipboard()
        if img is None:
            return None

        # Convert to PNG bytes
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        return f"data:image/png;base64,{b64}"
    except Exception as e:
        print(f"[SCREENSHOT AI] Clipboard grab failed: {e}")
        return None


def build_vision_messages(image_data_url: str,
                          user_prompt: str = "",
                          system_prompt: str = "") -> list:
    """Build multimodal messages for OpenRouter vision API.

    Args:
        image_data_url: base64 data URL (data:image/png;base64,...)
        user_prompt: Optional extra instruction from user
        system_prompt: Override default system prompt
    """
    sys_prompt = system_prompt or SCREENSHOT_SYSTEM_PROMPT
    user_text = user_prompt or "এই স্ক্রিনশটটি বিশ্লেষণ করো।"

    messages = [
        {"role": "system", "content": sys_prompt},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_text},
                {
                    "type": "image_url",
                    "image_url": {"url": image_data_url}
                }
            ]
        }
    ]
    return messages


async def analyze_screenshot(image_data_url: str,
                             user_prompt: str = "",
                             system_prompt: str = "") -> str:
    """Full pipeline: build messages → call vision API → return result."""
    from ai_engine.openrouter import complete_vision

    messages = build_vision_messages(image_data_url, user_prompt, system_prompt)
    return await complete_vision(messages)
