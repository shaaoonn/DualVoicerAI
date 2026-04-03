# ai_engine/clipboard_guard.py
import pyperclip, pyautogui, time

class ClipboardGuard:
    def __init__(self): self._saved = ""

    def get_selected_text(self) -> str:
        try:    self._saved = pyperclip.paste()
        except: self._saved = ""
        pyautogui.hotkey("ctrl", "c")
        time.sleep(0.18)
        return pyperclip.paste()

    def paste_result(self, text: str, output_format: str = "plain"):
        """Paste result. If output_format='rich', use HTML clipboard for formatting."""
        if output_format == "rich":
            from ai_engine.format_handler import markdown_to_html_clipboard
            if markdown_to_html_clipboard(text):
                # HTML clipboard set successfully, just Ctrl+V
                time.sleep(0.05)
                pyautogui.hotkey("ctrl", "v")
                time.sleep(0.12)
                try: pyperclip.copy(self._saved)
                except: pass
                return

        # Plain text fallback
        pyperclip.copy(text)
        time.sleep(0.05)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.12)
        try: pyperclip.copy(self._saved)
        except: pass
