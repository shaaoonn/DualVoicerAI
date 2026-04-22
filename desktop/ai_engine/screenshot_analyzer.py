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
from i18n import tr


def _get_system_prompt() -> str:
    """Returns the screenshot-analysis system prompt in the active UI language.
    Looked up at call-time so language switches take effect immediately."""
    return tr("ai_screenshot_system")


# Backwards-compatible module-level reference (resolved at import time);
# prefer _get_system_prompt() to honour live language changes.
SCREENSHOT_SYSTEM_PROMPT = _get_system_prompt()


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
    sys_prompt = system_prompt or _get_system_prompt()
    user_text = user_prompt or tr("ai_screenshot_user_default")

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
