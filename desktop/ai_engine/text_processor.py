# ai_engine/text_processor.py
"""
3-mode AI flow:
  MODE A (Question)  -> text ends with '?' -> answer appended below
  MODE B (Continue)  -> text ends with trigger word -> continue the text
  MODE C (Command)   -> everything else -> replace with AI output

The system prompt is structured so the user's own System Instruction and
Knowledge Base are treated as MANDATORY rules — not soft hints. Format
instructions come last so they cannot drown out the user's intent.
"""
import re, asyncio
from ai_engine.openrouter import complete
from ai_engine.format_handler import format_for_paste
from i18n import tr

# Continue triggers stay multilingual - they are spoken/typed words the user
# might end a prompt with, regardless of UI language.
CONTINUE_TRIGGERS = [
    "\u099a\u09be\u09b2\u09bf\u09df\u09c7 \u09af\u09be\u0993", "continue", "\u09b2\u09bf\u0996\u09a4\u09c7 \u09a5\u09be\u0995\u09cb",
    "go on", "keep going", "\u098f\u0997\u09bf\u09df\u09c7 \u09af\u09be\u0993", "...",
]

# Format instructions are looked up per-call so language switches take effect.
def _rich_format_instruction() -> str:
    return tr("ai_rich_format_instruction")

def _plain_format_instruction() -> str:
    return tr("ai_plain_format_instruction")

# Backwards-compatible module-level references (resolved at import time).
RICH_FORMAT_INSTRUCTION = _rich_format_instruction()
PLAIN_FORMAT_INSTRUCTION = _plain_format_instruction()


def build_system_message(system_instruction: str,
                         knowledge_base: str,
                         format_instruction: str) -> str:
    """Compose a strict, layered system prompt.

    Layer order (most authoritative first):
      1. SYSTEM RULES from user (highest priority — MUST be obeyed)
      2. KNOWLEDGE BASE (the ONLY source of truth when relevant)
      3. FORMATTING (lowest priority — only governs output shape)

    Each layer is fenced so the model cannot mistake user content for a
    new instruction.
    """
    sys_clean = (system_instruction or "").strip()
    kb_clean  = (knowledge_base or "").strip()
    fmt_clean = (format_instruction or "").strip()

    parts = []

    # ── 1. Authoritative system rules ────────────────────────────────
    if sys_clean:
        parts.append(
            "=== SYSTEM RULES (HIGHEST PRIORITY — MUST FOLLOW EXACTLY) ===\n"
            f"{sys_clean}\n"
            "=== END OF SYSTEM RULES ===\n"
            "\n"
            "These rules override every other instruction in this prompt. "
            "Do NOT rephrase, ignore, or apologise for them. Apply them to "
            "every response without exception."
        )

    # ── 2. Knowledge base (single source of truth) ───────────────────
    if kb_clean:
        parts.append(
            "\n=== KNOWLEDGE BASE (USE THIS AS THE ONLY SOURCE OF TRUTH) ===\n"
            f"{kb_clean}\n"
            "=== END OF KNOWLEDGE BASE ===\n"
            "\n"
            "Rules for using the knowledge base:\n"
            "1. When the user's question can be answered from the knowledge base, "
            "answer ONLY from it. Do NOT invent facts not present here.\n"
            "2. If the answer is partially in the knowledge base, use what is "
            "there and clearly mark anything you add from general knowledge.\n"
            "3. If the user explicitly asks something unrelated to the "
            "knowledge base, you may answer normally but still respect the "
            "SYSTEM RULES above.\n"
            "4. Quote prices, names, course titles, contact info, and policy "
            "wording EXACTLY as written in the knowledge base — never paraphrase."
        )

    # ── 3. Format guidance (lowest priority) ─────────────────────────
    if fmt_clean:
        parts.append(
            "\n=== OUTPUT FORMAT (lowest priority) ===\n"
            f"{fmt_clean}\n"
            "=== END OF OUTPUT FORMAT ==="
        )

    if not parts:
        return tr("ai_text_system_default")

    return "\n".join(parts)


class TextProcessor:
    def __init__(self, system_instruction="", output_format="plain",
                 knowledge_base=""):
        # Keep the user's raw instruction so build_system_message can frame it.
        self.system_instruction = system_instruction or tr("ai_text_system_default")
        self.knowledge_base     = knowledge_base or ""
        self.format             = output_format
        # Backwards-compatible alias used by older code paths
        self.system = self.system_instruction

    def _detect_mode(self, text):
        t = text.strip()
        if t.endswith("?"): return "question"
        for trig in CONTINUE_TRIGGERS:
            if t.lower().endswith(trig.lower()): return "continue"
        return "command"

    def _build_messages(self, text, mode):
        fmt = (PLAIN_FORMAT_INSTRUCTION if self.format == "plain"
               else RICH_FORMAT_INSTRUCTION)
        sys_msg = build_system_message(
            self.system_instruction, self.knowledge_base, fmt
        )

        if mode == "question":
            user = f"\u098f\u0987 \u09aa\u09cd\u09b0\u09b6\u09cd\u09a8\u09c7\u09b0 \u0989\u09a4\u09cd\u09a4\u09b0 \u09a6\u09be\u0993:\n\n{text}"
        elif mode == "continue":
            clean = text
            for t in CONTINUE_TRIGGERS:
                clean = re.sub(re.escape(t), "", clean, flags=re.IGNORECASE).strip()
            user = f"\u09a8\u09bf\u099a\u09c7\u09b0 \u09b2\u09c7\u0996\u09be\u099f\u09be \u098f\u0995\u0987 tone-\u098f \u099a\u09be\u09b2\u09bf\u09df\u09c7 \u09b2\u09c7\u0996\u09cb:\n\n{clean}"
        else:
            user = f"\u09a8\u09bf\u099a\u09c7\u09b0 \u09a8\u09bf\u09b0\u09cd\u09a6\u09c7\u09b6 \u0985\u09a8\u09c1\u09af\u09be\u09df\u09c0 \u0995\u09be\u099c \u0995\u09b0\u09cb:\n\n{text}"

        return [{"role":"system","content":sys_msg}, {"role":"user","content":user}]

    def _merge(self, original, ai_out, mode):
        if self.format == "plain":
            out = format_for_paste(ai_out, "plain")
        else:
            # Rich mode: keep raw markdown (will be converted to HTML at paste time)
            out = ai_out.strip()

        if mode == "question": return f"{original}\n\n{out}"
        if mode == "continue":
            clean = original
            for t in CONTINUE_TRIGGERS:
                clean = re.sub(re.escape(t),"",clean,flags=re.IGNORECASE).strip()
            return f"{clean} {out}"
        return out

    async def process(self, selected_text: str) -> str:
        mode = self._detect_mode(selected_text)
        ai_out = await complete(self._build_messages(selected_text, mode))
        return self._merge(selected_text, ai_out, mode)
