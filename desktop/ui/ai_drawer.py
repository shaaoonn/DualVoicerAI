# ui/ai_drawer.py
"""Embedded compact AI bar that slides out from the bottom of the
main toolbar widget when the user clicks the AI button's ▼ arrow.

Unlike the previous floating CTkToplevel popup, this drawer is a
plain `tk.Frame` parented to the main widget's drawer host — so it
moves with the widget when dragged, survives monitor changes, and
isn't affected by overrideredirect-Toplevel focus quirks.

Layout (one compact row):
  [📷] [───── prompt entry ─────] [✕] [➤ Send]

When an image is attached, a thin preview row appears above the
input row showing a 36×36 thumbnail + filename + ✕.
"""

from __future__ import annotations

import base64
import io
import os
import threading
from typing import Optional

import tkinter as tk
from PIL import Image, ImageGrab, ImageTk


# Dark palette (matches the widget toolbar)
BG_BAR        = "#22214B"
BG_INPUT      = "#2A2A55"
BG_BTN        = "#3A3870"
BG_BTN_HOVER  = "#4A4880"
BORDER        = "#404778"
TEXT_PRIMARY  = "#F0F2F8"
TEXT_MUTED    = "#9BA3C7"
TEXT_SUBTLE   = "#7A82A6"
ACCENT        = "#FFD700"
ACCENT_HOVER  = "#FFE34D"
ACCENT_TEXT   = "#1A1A2E"
ERROR         = "#FF6B6B"
OK            = "#7DD87D"

_IMG_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif"}


class AIDrawer(tk.Frame):
    """Compact embedded AI bar."""

    def __init__(self, parent, app, width: int,
                  captured_selection: str = "",
                  previous_foreground_hwnd=None,
                  pending_image_b64: Optional[str] = None, **kw):
        super().__init__(parent, bg=BG_BAR, highlightthickness=1,
                         highlightbackground=BORDER,
                         highlightcolor=BORDER, **kw)
        self.app = app
        # NOTE: do NOT assign to self._w — Tk reserves that for the
        # widget pathname (string). Overwriting it with an int makes
        # any subsequent Tk operation crash with "unsupported operand
        # type(s) for +: 'int' and 'str'".
        self._width_px = width

        # State
        self._image_pil: Optional[Image.Image] = None
        self._image_label: str = ""
        self._busy = False
        self._tk_thumb = None
        # Selection captured BEFORE we stole keyboard focus, plus the
        # window we'll hand foreground back to before typing the result.
        self._captured_selection = (captured_selection or "").strip()
        self._prev_foreground_hwnd = previous_foreground_hwnd

        self._build_body()

        # If the widget's screenshot button captured an image just
        # before the drawer was opened, preload it so the user can
        # immediately add a prompt and Send.
        if pending_image_b64:
            self.set_image_from_b64(
                pending_image_b64, label="Screenshot")
        # If a non-trivial selection was captured, surface it in the
        # status row so the user knows it'll be sent along.
        elif self._captured_selection:
            n = len(self._captured_selection)
            self._set_status(
                f"Selected text from screen ({n} chars) will be sent.",
                ok=True)

        # NOTE: per user request the drawer does NOT pre-fill the
        # prompt textbox from a previous session. Otherwise an old
        # prompt would silently combine with a freshly-captured
        # screenshot on the next drawer open, and the AI would answer
        # something the user no longer wants. Each drawer open starts
        # with an empty prompt.

    # ── Public API for screenshot push from main.py ──────────────

    def set_image_from_b64(self, b64_url: str,
                            label: str = "Image") -> None:
        """Decode a 'data:image/png;base64,...' URL into a PIL image
        and load it into the drawer's image slot. Used by main.py
        when the widget's 📷 screenshot button captures something
        and the drawer is open (or the user opens it shortly after)."""
        img = self._pil_from_b64_url(b64_url)
        if img is None:
            return
        self._set_image(img, label)
        try:
            self._set_status(
                f"{label} attached — type a prompt and Send.",
                ok=True)
        except Exception:
            pass

    def _pil_from_b64_url(self, b64_url: str) -> Optional[Image.Image]:
        try:
            b64 = b64_url.split(",", 1)[1] if "," in b64_url else b64_url
            raw = base64.b64decode(b64)
            return Image.open(io.BytesIO(raw))
        except Exception as e:
            print(f"[AIDrawer] decode b64 failed: {e}")
            return None

    def focus_entry(self):
        """Public — called by main.py after stripping NOACTIVATE so
        keyboard input lands in the prompt textbox."""
        try:
            self._entry.focus_force()
            # Move caret to end so existing pre-fill isn't selected
            # by accident
            self._entry.mark_set("insert", "end")
        except Exception:
            pass

    # ── Layout ───────────────────────────────────────────────────

    def _build_body(self):
        # Image preview strip (initially hidden — only appears when an
        # image is attached). Shows a 36×36 thumbnail + filename + ✕.
        self._img_strip = tk.Frame(self, bg=BG_INPUT)

        # Pre-create thumbnail / label widgets
        self._img_thumb = tk.Label(
            self._img_strip, bg=BG_BAR, width=4)
        self._img_thumb.pack(side="left", padx=4, pady=4)
        self._img_text = tk.Label(
            self._img_strip, text="", bg=BG_INPUT, fg=TEXT_MUTED,
            font=("Segoe UI", 7), anchor="w", justify="left")
        self._img_text.pack(side="left", fill="x", expand=True, padx=4)
        tk.Button(
            self._img_strip, text="✕", bg=BG_INPUT, fg=TEXT_MUTED,
            activebackground=BG_BTN_HOVER, activeforeground=TEXT_PRIMARY,
            font=("Segoe UI", 7, "bold"), relief="flat", bd=0,
            cursor="hand2", padx=8,
            command=self._clear_image).pack(side="right", padx=2)

        # ── Main input area ──
        # One bordered container that holds:
        #   • A wide textbox at the top (auto-grows 2..5 lines)
        #   • A thin icon row at the bottom-right with [+] and [➤]
        # Per user request the previous standalone 📷 (image picker)
        # and big ➤ Send buttons have been removed — they're replaced
        # by the small + and ➤ pinned to the textbox's bottom-right
        # so the typing area is as wide as possible.
        self._entry_container = tk.Frame(
            self, bg=BG_INPUT, highlightthickness=1,
            highlightbackground=BORDER, highlightcolor=BORDER)
        self._entry_container.pack(fill="both", expand=True,
                                     padx=6, pady=6)

        # Icon row — packed FIRST at side="bottom" so it reserves the
        # bottom strip; the textbox above it then fills/expands into
        # the remaining top space.
        icon_row = tk.Frame(self._entry_container, bg=BG_INPUT)
        icon_row.pack(side="bottom", fill="x", padx=4, pady=(0, 4))
        # Spacer pushes the two icons to the right edge.
        tk.Frame(icon_row, bg=BG_INPUT).pack(
            side="left", fill="x", expand=True)
        # + (image picker — replaces the old 📷 button)
        self._plus_btn = tk.Button(
            icon_row, text="+",
            bg=BG_INPUT, fg=TEXT_MUTED,
            activebackground=BG_BTN_HOVER,
            activeforeground=TEXT_PRIMARY,
            font=("Segoe UI", 9, "bold"),
            relief="flat", bd=0, cursor="hand2",
            padx=8, pady=0,
            command=self._on_pick_image)
        self._plus_btn.pack(side="left", padx=2)
        # ➤ (send — replaces the old big yellow Send button)
        self._send_btn = tk.Button(
            icon_row, text="➤",
            bg=ACCENT, fg=ACCENT_TEXT,
            activebackground=ACCENT_HOVER,
            activeforeground=ACCENT_TEXT,
            font=("Segoe UI", 8, "bold"),
            relief="flat", bd=0, cursor="hand2",
            padx=10, pady=0,
            command=self._on_send)
        self._send_btn.pack(side="left", padx=(2, 0))

        # Prompt textbox — fills all remaining (top) space inside the
        # container. height=2 starts at 2 lines and grows up to 5
        # before Tk's natural scrolling kicks in (mouse wheel works
        # out of the box on tk.Text). Font shrunk to 0.7× per user
        # request (was 11pt → now 8pt).
        self._entry = tk.Text(
            self._entry_container, height=2, wrap="word",
            bg=BG_INPUT, fg=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY,
            font=("Segoe UI", 8), relief="flat", bd=0,
            highlightthickness=0,
            padx=8, pady=4)
        self._entry.pack(side="top", fill="both", expand=True)
        self._entry.bind("<Control-v>", self._on_paste, add="+")
        self._entry.bind("<Control-V>", self._on_paste, add="+")
        self._entry.bind("<Return>", self._on_enter, add="+")
        self._entry.bind("<Shift-Return>", lambda e: None, add="+")
        self._entry.bind("<Control-Return>", self._on_enter, add="+")
        # Auto-grow on every change
        self._entry.bind("<<Modified>>", self._on_entry_modified,
                          add="+")

        # Inline status row (very small, hidden by default)
        self._status = tk.Label(
            self, text="", bg=BG_BAR, fg=TEXT_SUBTLE,
            font=("Segoe UI", 7), anchor="w")

        # Try to focus the entry once we're realised
        self.after(120, self._focus_entry)

    def _on_entry_modified(self, _e=None):
        """Auto-grow the textbox 2..5 lines based on visible content.
        Beyond 5 lines tk.Text's natural scrolling (incl. mouse wheel)
        takes over so the drawer doesn't grow indefinitely."""
        try:
            try:
                # `count` with "displaylines" includes wrapped lines
                count = self._entry.count(
                    "1.0", "end-1c", "displaylines")
                n_lines = int(count[0]) if count else 1
            except Exception:
                # Fallback if the option isn't available
                text = self._entry.get("1.0", "end-1c")
                n_lines = text.count("\n") + 1
            n_lines = max(1, n_lines)
            new_h = max(2, min(5, n_lines))
            cur_h = int(self._entry.cget("height"))
            if new_h != cur_h:
                self._entry.configure(height=new_h)
                self._fit_drawer_height()
        finally:
            try:
                # Reset so <<Modified>> fires again on next change
                self._entry.edit_modified(False)
            except Exception:
                pass

    def _focus_entry(self):
        try: self._entry.focus_set()
        except Exception: pass

    # ── Image handling ───────────────────────────────────────────

    def _show_image_strip(self):
        if not self._img_strip.winfo_ismapped():
            # Pack ABOVE the entry container so it sits between the
            # drawer's top border and the textbox.
            self._img_strip.pack(fill="x", side="top",
                                  before=self._entry_container,
                                  padx=6, pady=(6, 0))

    def _hide_image_strip(self):
        if self._img_strip.winfo_ismapped():
            self._img_strip.pack_forget()
        self._fit_drawer_height()

    def _clear_image(self):
        self._image_pil = None
        self._image_label = ""
        self._tk_thumb = None
        self._img_thumb.configure(image="", text="")
        self._img_text.configure(text="")
        self._hide_image_strip()

    def _set_image(self, pil_img: Image.Image, label: str):
        try:
            pil_img = pil_img.copy()
            pil_img.thumbnail((1920, 1920), Image.LANCZOS)
        except Exception:
            pass
        self._image_pil = pil_img
        self._image_label = label
        try:
            thumb = pil_img.copy()
            thumb.thumbnail((36, 36), Image.LANCZOS)
            self._tk_thumb = ImageTk.PhotoImage(thumb)
            self._img_thumb.configure(image=self._tk_thumb, text="")
        except Exception as e:
            self._img_thumb.configure(text="🖼", image="")
            print(f"[AIDrawer] thumbnail failed: {e}")
        w, h = pil_img.size
        self._img_text.configure(text=f"{label}   {w}×{h}px")
        self._show_image_strip()
        self._fit_drawer_height()

    def _fit_drawer_height(self):
        """Resize the parent drawer host to fit current content."""
        try:
            self.update_idletasks()
            new_h = self.winfo_reqheight()
            host = self.master   # _drawer_host
            host.configure(height=new_h)
            # Tell the app to grow the Toplevel to match
            self.app._grow_geometry_for_drawer(new_h)
        except Exception:
            pass

    def _on_pick_image(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            parent=self.winfo_toplevel(),
            title="Pick an image to send to AI",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.webp *.gif"),
                       ("All files", "*.*")])
        if not path:
            return
        try:
            img = Image.open(path)
        except Exception as e:
            self._set_status(f"Couldn't open image: {e}", error=True)
            return
        self._set_image(img, os.path.basename(path))
        self._focus_entry()

    def _on_paste(self, _e=None):
        try:
            payload = ImageGrab.grabclipboard()
        except Exception:
            payload = None
        if isinstance(payload, Image.Image):
            self._set_image(payload, "Pasted image")
            return "break"
        if isinstance(payload, list):
            for p in payload:
                if isinstance(p, str) and \
                        os.path.splitext(p)[1].lower() in _IMG_EXTS:
                    try:
                        img = Image.open(p)
                        self._set_image(img, os.path.basename(p))
                        return "break"
                    except Exception:
                        pass
        return None  # let default text paste happen

    # ── Send / dispatch ──────────────────────────────────────────

    def _on_enter(self, _e=None):
        if self._busy:
            return "break"
        self._on_send()
        return "break"

    def _on_send(self):
        if self._busy:
            return
        prompt = self._entry.get("1.0", "end-1c").strip()

        # Use the selection captured BEFORE we stole focus (in
        # main.py::_toggle_ai_drawer). We can NOT re-Ctrl+C here —
        # the drawer textbox now owns keyboard focus, so Ctrl+C
        # would copy from the prompt textbox instead of the user's
        # original app.
        selected_text = self._captured_selection

        if (not prompt
                and not selected_text
                and self._image_pil is None):
            self._set_status(
                "Type a prompt, select text on screen before opening, "
                "or attach an image.", error=True)
            return

        # NOTE: prompt persistence intentionally removed — see __init__
        # comment about not pre-filling. Saving here would be dead
        # code now that we never read the value back.

        self._busy = True
        self._send_btn.configure(text="⏳", state="disabled")
        bits = []
        if prompt:        bits.append("prompt")
        if selected_text: bits.append(f"selection ({len(selected_text)} ch)")
        if self._image_pil is not None: bits.append("image")
        self._set_status("Sending to AI: " + " + ".join(bits) + " …")

        threading.Thread(
            target=self._worker,
            args=(prompt, self._image_pil, selected_text),
            daemon=True
        ).start()

    def _worker(self, prompt: str, image_pil: Optional[Image.Image],
                 selected_text: str = ""):
        # Build a STRUCTURED user message that labels every input the
        # user provided so the model can tell them apart and follow
        # instructions like "fix the spelling of the selected text" or
        # "compare the selected text against the image".
        #
        # Labels are intentionally human-readable and very explicit
        # because the AI is told (in the system prompt) to look up
        # these labels when the user's instruction references things
        # like "the selected text", "the image", "the selection", etc.
        has_image = image_pil is not None
        user_message = self._build_labeled_user_message(
            prompt=prompt,
            selected_text=selected_text,
            has_image=has_image,
        )

        try:
            if has_image:
                # Vision path. analyze_screenshot() uses complete_vision()
                # which opens a FRESH aiohttp session each call — so
                # asyncio.run() is safe here (no shared-session loop bug).
                import asyncio
                from ai_engine.screenshot_analyzer import analyze_screenshot
                buf = io.BytesIO()
                image_pil.save(buf, format="PNG")
                buf.seek(0)
                b64 = base64.b64encode(buf.getvalue()).decode("ascii")
                url = f"data:image/png;base64,{b64}"
                sys_prompt = self.app.settings.get("image_system_prompt", "")
                kb         = self.app.settings.get("knowledge_base", "")
                # Wrap the system prompt with multi-input guidance so
                # the model can resolve references like "the selected
                # text" / "the image" / "this picture" correctly.
                sys_prompt = self._wrap_system_prompt_with_label_guide(
                    sys_prompt,
                    has_prompt=bool(prompt),
                    has_selection=bool(selected_text),
                    has_image=True,
                )
                result = asyncio.run(analyze_screenshot(
                    url, user_prompt=user_message,
                    system_prompt=sys_prompt,
                    knowledge_base=kb))
            else:
                # Text path. complete() uses the SINGLETON aiohttp
                # session bound to the persistent executor loop in
                # openrouter.py. Calling it from a fresh asyncio.run()
                # loop crashes with "Timeout context manager should be
                # used inside a task". Dispatch via run_on_executor()
                # to bridge back to the loop that owns the session.
                from ai_engine.openrouter import complete, run_on_executor
                sys_prompt = self.app.settings.get("ai_system_prompt", "")
                kb = (self.app.settings.get("knowledge_base") or "").strip()
                kb_section = (
                    f"\n\n=== KNOWLEDGE BASE ===\n{kb}\n=== END ===\n"
                    if kb else "")
                base_sys = (
                    f"{sys_prompt}{kb_section}\n\n"
                    "Reply directly. No preface. Match the user's "
                    "language."
                )
                system_msg = self._wrap_system_prompt_with_label_guide(
                    base_sys,
                    has_prompt=bool(prompt),
                    has_selection=bool(selected_text),
                    has_image=False,
                )
                messages = [
                    {"role": "system", "content": system_msg},
                    {"role": "user",   "content": user_message},
                ]
                result = run_on_executor(complete(messages))
        except Exception as e:
            err = f"AI failed: {e}"
            print(f"[AIDrawer] {err}")
            try:
                self.after(0, lambda m=err: self._on_error(m))
            except Exception:
                pass
            return
        try:
            self.after(0, lambda r=result: self._on_result(r))
        except Exception:
            pass

    # ── Multi-input prompt construction ──────────────────────────

    def _build_labeled_user_message(self, *, prompt: str,
                                     selected_text: str,
                                     has_image: bool) -> str:
        """Compose the user-side message with explicit labeled
        sections so the model can distinguish:
          • the user's INSTRUCTION (free-form prompt)
          • SELECTED TEXT grabbed via Ctrl+C from the user's screen
          • the attached IMAGE (referenced separately in vision payload)

        When only one input is present we skip the labels so the model
        isn't distracted by ceremony for trivial single-input cases."""
        prompt = (prompt or "").strip()
        selected_text = (selected_text or "").strip()

        # Single-input fast paths — no need for headings.
        if not selected_text and not has_image:
            return prompt
        if not prompt and not selected_text and has_image:
            # Vision path with no prompt — give the model a default
            # instruction since the multimodal payload still needs
            # SOME text content.
            return "Describe the attached image."
        if not prompt and selected_text and not has_image:
            return selected_text

        # Multi-input — label every section we have.
        parts = []
        if prompt:
            parts.append(
                "=== USER INSTRUCTION ===\n"
                f"{prompt}"
            )
        if selected_text:
            parts.append(
                "=== SELECTED TEXT (from the user's screen — refer to "
                "this when the instruction mentions \"selected text\", "
                "\"the selection\", \"this text\", etc.) ===\n"
                f"{selected_text}\n"
                "=== END SELECTED TEXT ==="
            )
        if has_image:
            parts.append(
                "=== ATTACHED IMAGE ===\n"
                "(see the image attached to this message — refer to it "
                "when the instruction mentions \"the image\", \"the "
                "picture\", \"the screenshot\", etc.)"
            )
        return "\n\n".join(parts)

    def _wrap_system_prompt_with_label_guide(self, base_sys: str, *,
                                              has_prompt: bool,
                                              has_selection: bool,
                                              has_image: bool) -> str:
        """Append a small "how to read the user message" guide to the
        system prompt. Only added when more than one input is present
        — single-input messages don't need the explanation."""
        n_inputs = int(has_prompt) + int(has_selection) + int(has_image)
        if n_inputs < 2:
            return base_sys
        labels = []
        if has_prompt:    labels.append("\"USER INSTRUCTION\"")
        if has_selection: labels.append("\"SELECTED TEXT\"")
        if has_image:     labels.append("\"ATTACHED IMAGE\"")
        labels_str = ", ".join(labels)
        guide = (
            "\n\n=== INPUT STRUCTURE ===\n"
            "The user has provided multiple inputs in this turn. "
            "Each is clearly labeled below as a section: "
            f"{labels_str}. Treat each section according to its "
            "label. When the USER INSTRUCTION refers to \"the "
            "selected text\", \"the selection\", or \"this text\", "
            "look at the SELECTED TEXT section. When it refers to "
            "\"the image\", \"the picture\", or \"the screenshot\", "
            "look at the ATTACHED IMAGE. Do NOT confuse the user's "
            "instruction with the content they want you to operate on."
        )
        return base_sys + guide

    def _on_result(self, text: str):
        text = (text or "").strip()
        if not text:
            self._on_error("AI returned empty response.")
            return

        # Hand foreground back to the window the user was in BEFORE
        # opening the drawer, then type. Without this swap, type_text
        # would land in the drawer textbox instead of the user's app
        # (because we stripped NOACTIVATE on open and Tk holds the
        # current OS foreground).
        #
        # A naked SetForegroundWindow() call from a non-foreground
        # thread is blocked by Windows' anti-focus-stealing guard, so
        # ~50% of the time the typing leaks back into the drawer.
        # The app's _force_foreground uses AttachThreadInput to bypass
        # this — same helper used by main.py::_close_drawer.
        if not self.app._force_foreground(self._prev_foreground_hwnd):
            # Fallback — alt+tab is the proven path used elsewhere in
            # the codebase (main.py:on_release).
            try:
                import pyautogui
                pyautogui.hotkey("alt", "tab")
            except Exception as e:
                print(f"[AIDrawer] alt+tab fallback failed: {e}")

        # Wait until the OS has actually switched foreground, with a
        # small budget. This kills the typing-into-drawer race.
        try:
            import ctypes, time
            user32 = ctypes.windll.user32
            target = self._prev_foreground_hwnd or 0
            for _ in range(15):  # up to ~300ms
                if user32.GetForegroundWindow() == target:
                    break
                time.sleep(0.02)
        except Exception:
            pass

        try:
            self.app.type_text(text)
        except Exception as e:
            self._on_error(f"Couldn't type result: {e}")
            return
        self._set_status("✓ Typed into previous field.", ok=True)
        # Re-enable Send for follow-up prompts.
        self._busy = False
        try:
            self._send_btn.configure(text="➤", state="normal")
        except Exception:
            pass


    def _on_error(self, msg: str):
        self._busy = False
        try:
            self._send_btn.configure(text="➤", state="normal")
        except Exception:
            pass
        self._set_status(msg, error=True)

    def _set_status(self, msg: str, error: bool = False, ok: bool = False):
        try:
            color = ERROR if error else (OK if ok else TEXT_SUBTLE)
            self._status.configure(text=msg, fg=color)
            if not self._status.winfo_ismapped():
                self._status.pack(fill="x", padx=8, pady=(0, 4))
            self._fit_drawer_height()
        except Exception:
            pass

    def _on_cancel(self):
        try:
            self.app._close_drawer()
        except Exception:
            pass
