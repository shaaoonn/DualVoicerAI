# ai_engine/text_processor.py
"""
3-mode AI flow:
  MODE A (Question)  -> text ends with '?' -> answer appended below
  MODE B (Continue)  -> text ends with trigger word -> continue the text
  MODE C (Command)   -> everything else -> replace with AI output
"""
import re, asyncio
from ai_engine.openrouter import complete
from ai_engine.format_handler import format_for_paste

CONTINUE_TRIGGERS = [
    "\u099a\u09be\u09b2\u09bf\u09df\u09c7 \u09af\u09be\u0993", "continue", "\u09b2\u09bf\u0996\u09a4\u09c7 \u09a5\u09be\u0995\u09cb",
    "go on", "keep going", "\u098f\u0997\u09bf\u09df\u09c7 \u09af\u09be\u0993", "...",
]

# Rich mode: tell AI to use full markdown with headings, lists, bold, etc.
RICH_FORMAT_INSTRUCTION = """

আউটপুট ফরম্যাট: স্বাভাবিক Markdown ব্যবহার করো:
- শিরোনাম লাগলে ## বা ### ব্যবহার করো
- **bold** শুধু সত্যিকারের গুরুত্বপূর্ণ শব্দে, অতিরিক্ত bold করো না — স্বাভাবিক লেখার মতো লেখো
- _italic_ খুব কম ব্যবহার করো
- তালিকা দরকার হলে - bullet ব্যবহার করো
- কোড থাকলে `code` ব্যবহার করো
মনে রাখো: বাস্তব মানুষের লেখার মতো স্বাভাবিক হবে, প্রতিটা শব্দ bold করো না।"""

PLAIN_FORMAT_INSTRUCTION = "\n\n\u0986\u0989\u099f\u09aa\u09c1\u099f: plain text, \u0995\u09cb\u09a8\u09cb markdown \u09a8\u09df\u0964"


class TextProcessor:
    def __init__(self, system_instruction="", output_format="plain"):
        self.system = system_instruction or (
            "\u09a4\u09c1\u09ae\u09bf \u098f\u0995\u099c\u09a8 \u09a6\u0995\u09cd\u09b7 \u09ac\u09be\u0982\u09b2\u09be \u0993 \u0987\u0982\u09b0\u09c7\u099c\u09bf \u09b2\u09c7\u0996\u0995 \u09b8\u09b9\u0995\u09be\u09b0\u09c0\u0964 \u09b8\u0982\u0995\u09cd\u09b7\u09bf\u09aa\u09cd\u09a4 \u0989\u09a4\u09cd\u09a4\u09b0 \u09a6\u09be\u0993\u0964")
        self.format = output_format

    def _detect_mode(self, text):
        t = text.strip()
        if t.endswith("?"): return "question"
        for trig in CONTINUE_TRIGGERS:
            if t.lower().endswith(trig.lower()): return "continue"
        return "command"

    def _build_messages(self, text, mode):
        fmt = PLAIN_FORMAT_INSTRUCTION if self.format == "plain" else RICH_FORMAT_INSTRUCTION
        sys_msg = self.system + fmt

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
