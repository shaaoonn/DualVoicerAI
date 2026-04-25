# ai_engine/screenshot_analyzer.py
"""Screenshot AI Analyzer - Captures clipboard image and sends to vision model.

Features:
  - Grabs image from Windows clipboard (after snip/screenshot)
  - Converts to base64 for OpenRouter vision API
  - System prompt is layered: user's Image System Instruction (mandatory) +
    Knowledge Base (single source of truth) + format hints (lowest priority)
"""

import base64, io
from typing import Optional
from i18n import tr


def _get_system_prompt() -> str:
    """Default screenshot-analysis system prompt (UI language aware)."""
    return tr("ai_screenshot_system")


# Backwards-compatible module-level reference
SCREENSHOT_SYSTEM_PROMPT = _get_system_prompt()


def grab_clipboard_image() -> Optional[str]:
    """Grab image from clipboard and return as base64 data URL."""
    try:
        from PIL import ImageGrab
        img = ImageGrab.grabclipboard()
        if img is None:
            return None

        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        return f"data:image/png;base64,{b64}"
    except Exception as e:
        print(f"[SCREENSHOT AI] Clipboard grab failed: {e}")
        return None


def _build_layered_system_prompt(user_image_instruction: str,
                                 knowledge_base: str) -> str:
    """Compose the screenshot system prompt with the user's image instruction
    as the top-priority rule, the knowledge base as the source of truth, and
    the default screenshot helper instructions as the fallback baseline."""
    parts = []

    user_instr = (user_image_instruction or "").strip()
    kb         = (knowledge_base or "").strip()

    if user_instr:
        parts.append(
            "=== IMAGE SYSTEM RULES (HIGHEST PRIORITY — MUST FOLLOW EXACTLY) ===\n"
            f"{user_instr}\n"
            "=== END OF IMAGE SYSTEM RULES ===\n"
            "\n"
            "These rules apply to every screenshot. Obey them strictly. Do "
            "NOT rephrase, ignore, or apologise for them."
        )

    if kb:
        parts.append(
            "\n=== KNOWLEDGE BASE (USE THIS AS THE ONLY SOURCE OF TRUTH) ===\n"
            f"{kb}\n"
            "=== END OF KNOWLEDGE BASE ===\n"
            "\n"
            "Rules for using the knowledge base while analysing the image:\n"
            "1. If the screenshot shows a question, message, comment or chat "
            "that the knowledge base can answer — answer ONLY from the "
            "knowledge base. Do not invent facts not present here.\n"
            "2. Quote prices, names, course titles, contact info, schedules "
            "and policy wording EXACTLY as written. Never paraphrase them.\n"
            "3. If the image is unrelated to the knowledge base, you may "
            "answer normally but still respect the IMAGE SYSTEM RULES above.\n"
            "4. Match the language of the message in the screenshot."
        )

    # Always include the default screenshot helper baseline (lowest priority).
    # If the user provided no instruction, this becomes the primary guidance.
    baseline = _get_system_prompt()
    if baseline:
        if parts:
            parts.append(
                "\n=== FALLBACK SCREENSHOT GUIDANCE (lowest priority) ===\n"
                f"{baseline}\n"
                "=== END OF FALLBACK GUIDANCE ==="
            )
        else:
            parts.append(baseline)

    return "\n".join(parts) if parts else baseline


def build_vision_messages(image_data_url: str,
                          user_prompt: str = "",
                          system_prompt: str = "",
                          knowledge_base: str = "") -> list:
    """Build multimodal messages for OpenRouter vision API.

    Args:
        image_data_url: base64 data URL (data:image/png;base64,...)
        user_prompt:    Optional extra instruction from the end-user
        system_prompt:  The user's "Image System Instruction" from settings
        knowledge_base: The user's "Knowledge Base" from settings — injected
                        with strict-source-of-truth framing.
    """
    sys_prompt = _build_layered_system_prompt(system_prompt, knowledge_base)
    user_text  = user_prompt or tr("ai_screenshot_user_default")

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
                             system_prompt: str = "",
                             knowledge_base: str = "") -> str:
    """Full pipeline: build messages → call vision API → return result."""
    from ai_engine.openrouter import complete_vision

    messages = build_vision_messages(
        image_data_url, user_prompt, system_prompt, knowledge_base
    )
    return await complete_vision(messages)
