# ui_components/spectrum_button.py
"""SpectrumButton — Color emoji icons + glossy ring + spectrum animation."""
import tkinter as tk
import math
import colorsys
from PIL import Image, ImageDraw, ImageFont, ImageTk


# Best Windows emoji icons
EMOJI = {
    "BN":  "\U0001f399",   # 🎙 studio microphone
    "EN":  "\U0001f399",   # 🎙 studio microphone
    "SND": "\U0001f50a",   # 🔊 speaker loud
    "AI":  "\u2728",       # ✨ sparkles (original)
}
PAUSE_EMOJI = "\u23f8\ufe0f"  # ⏸️ pause


class SpectrumButton(tk.Canvas):
    BAR_COUNT = 5
    ANIM_MS   = 50

    def __init__(self, parent, size=76, label="", command=None, colors=None,
                 toolbar_bg="#2E305E", **kw):
        super().__init__(parent, width=size, height=size,
                         bg=toolbar_bg, highlightthickness=0, **kw)
        self._toolbar_bg = toolbar_bg
        self.size = size
        self.label = label
        self._display_label = label
        self.command = command
        self.colors = colors or {}
        self._state = "idle"
        self._icon_mode = "play"
        self._hover = False
        self._bars = [0.08] * self.BAR_COUNT
        self._phase = 0.0
        self._job = None
        self._pressed = False
        self._press_x = self._press_y = 0
        self._drag_started = False
        self._photo = None
        self._glow = False
        self._show_label = True

        self._draw()
        self.bind("<Button-1>", self._on_down)
        self.bind("<B1-Motion>", self._on_motion)
        self.bind("<ButtonRelease-1>", self._on_up)
        self.bind("<Enter>", lambda e: self._on_hover(True))
        self.bind("<Leave>", lambda e: self._on_hover(False))

    def set_state(self, s):
        self._state = s
        if s == "idle":
            self._bars = [0.08]*self.BAR_COUNT; self._stop(); self._draw()
        else:
            self._start()

    def set_glow(self, enabled: bool):
        """Enable/disable bright glow ring (no animation)."""
        self._glow = enabled
        if self._state == "idle":
            self._draw()

    def set_icon_mode(self, m):
        self._icon_mode = m
        if self._state == "idle": self._draw()

    def set_display_label(self, t):
        self._display_label = t
        if self._state == "idle": self._draw()

    def set_labels_visible(self, visible: bool):
        self._show_label = visible
        self._draw()

    def resize(self, n):
        self.size = n; self.config(width=n, height=n); self._draw()

    # ── Idle (PIL rendered) ───────────────────────────
    def _draw(self):
        self.delete("all")
        if self._state == "idle":
            self._render_idle()
        else:
            self._render_active()

    def _render_idle(self):
        sz = self.size
        big = sz * 2
        # Fill with toolbar bg so corners blend with gradient toolbar
        try:
            c = self._toolbar_bg.lstrip("#")
            bg_rgba = (int(c[0:2],16), int(c[2:4],16), int(c[4:6],16), 255)
        except (ValueError, IndexError):
            bg_rgba = (46, 48, 94, 255)
        img = Image.new("RGBA", (big, big), bg_rgba)
        d = ImageDraw.Draw(img, "RGBA")
        cx = cy = big // 2
        pad = 6
        r = big // 2 - pad

        # ── Glossy 3D background circle ──
        # Outer dark ring
        d.ellipse([pad, pad, big-pad, big-pad], fill=(22, 24, 32, 255))
        # Inner gradient: top lighter, bottom darker (3D depth)
        inner_r = r - 4
        for i in range(inner_r, 0, -1):
            t = i / inner_r
            # Vertical gradient: top = brighter steel, bottom = darker
            y_ratio = 0.5  # center weighting
            top_v = int(52 + 18*t) if not self._hover else int(60 + 20*t)
            bot_v = int(32 + 8*t) if not self._hover else int(38 + 10*t)
            v = int(top_v * 0.6 + bot_v * 0.4)
            d.ellipse([cx-i, cy-i, cx+i, cy+i], fill=(v, v, int(v*1.05), 255))

        # ── Top highlight (glass reflection) ──
        hl_r = int(inner_r * 0.7)
        for i in range(hl_r, 0, -1):
            alpha = int(12 * (i / hl_r))
            d.ellipse([cx-i, cy - inner_r + int(inner_r*0.1), cx+i, cy - inner_r + hl_r],
                      fill=(255, 255, 255, alpha))

        # ── Ring ──
        if self.label == "AI":
            self._ring_rainbow(d, cx, cy, r)
        else:
            self._ring_metallic(d, cx, cy, r)

        # ── Icon ──
        # SND-pause uses vector pause bars (pixel-perfect centering).
        # Color emoji centering via font metrics is unreliable — different
        # glyphs (🔊 vs ⏸️) have inconsistent bearings/advance widths so
        # anchor="mm" or textbbox math leaves them visibly shifted.
        if self.label == "SND" and self._icon_mode == "pause":
            # Two white rounded rectangles (vector pause symbol)
            bar_h = int(big * 0.30)
            bar_w = max(4, int(big * 0.07))
            gap   = max(3, int(big * 0.06))
            top   = cy - bar_h // 2
            x_left  = cx - gap // 2 - bar_w
            x_right = cx + gap // 2
            radius  = max(2, bar_w // 3)
            d.rounded_rectangle(
                [x_left, top, x_left + bar_w, top + bar_h],
                radius=radius, fill=(255, 255, 255, 255))
            d.rounded_rectangle(
                [x_right, top, x_right + bar_w, top + bar_h],
                radius=radius, fill=(255, 255, 255, 255))
        else:
            emoji = EMOJI.get(self.label, self.label)
            emoji_sz = int(sz * 0.52)  # ~52% of button size — bigger, clearer
            try:
                efont = ImageFont.truetype("seguiemj.ttf", emoji_sz)
            except OSError:
                try: efont = ImageFont.truetype("segoeui.ttf", emoji_sz)
                except OSError: efont = ImageFont.load_default()

            # Render-and-recenter: render glyph to a temp surface, find its
            # actual non-transparent bbox, then composite at the true center.
            # This bypasses font-metric quirks entirely.
            try:
                pad = emoji_sz
                tmp = Image.new("RGBA", (pad * 3, pad * 3), (0, 0, 0, 0))
                td = ImageDraw.Draw(tmp)
                td.text((pad, pad), emoji,
                        font=efont, fill=(255, 255, 255, 255), embedded_color=True)
            except TypeError:
                # Older Pillow without embedded_color — fall back without it
                pad = emoji_sz
                tmp = Image.new("RGBA", (pad * 3, pad * 3), (0, 0, 0, 0))
                td = ImageDraw.Draw(tmp)
                td.text((pad, pad), emoji, font=efont, fill=(255, 255, 255, 255))
            bb = tmp.getbbox()
            if bb:
                glyph = tmp.crop(bb)
                gw, gh = glyph.size
                paste_x = cx - gw // 2
                paste_y = cy - gh // 2 - int(sz * 0.04)
                img.alpha_composite(glyph, (paste_x, paste_y))
            else:
                # Nothing rendered (font missing) — final fallback
                d.text((cx, cy), emoji, font=efont,
                       fill=(255, 255, 255, 255), anchor="mm")

        # ── Label (bigger, bold, gold) ──
        if self._show_label:
            lbl_sz = max(7, int(sz * 0.24))  # 2/3 of previous 0.36
            try: lfont = ImageFont.truetype("segoeuib.ttf", lbl_sz)
            except OSError:
                try: lfont = ImageFont.truetype("segoeui.ttf", lbl_sz)
                except OSError: lfont = ImageFont.load_default()
            lbb = d.textbbox((0, 0), self._display_label, font=lfont)
            lw = lbb[2] - lbb[0]
            lh = lbb[3] - lbb[1]
            lcolor = (255, 215, 0, 255) if self._hover else (218, 175, 32, 255)
            ly = big - lh - pad - 2
            d.text((cx - lw//2, ly), self._display_label, fill=lcolor, font=lfont)

        # Downscale
        img = img.resize((sz, sz), Image.LANCZOS)
        self._photo = ImageTk.PhotoImage(img)
        self.create_image(0, 0, anchor="nw", image=self._photo)

    def _ring_metallic(self, d, cx, cy, r, segments=48):
        """Metallic silver ring — 3D shading."""
        w = 4
        for i in range(segments):
            a = i * (360 / segments)
            # Simulate light from top-left
            light = 0.55 + 0.3*math.cos(math.radians(a - 30))
            if self._hover: light += 0.1
            v = int(255 * max(0.2, min(0.75, light)))
            d.arc([cx-r, cy-r, cx+r, cy+r], start=a, end=a + 360/segments + 1,
                  fill=(v, v, int(v*1.02), 255), width=w)

    def _ring_rainbow(self, d, cx, cy, r):
        """Rainbow gradient ring for AI. Bright when _glow is active."""
        w = 6 if self._glow else 5
        if self._glow:
            sat, val = 0.85, 0.95
        elif self._hover:
            sat, val = 0.55, 0.72
        else:
            sat, val = 0.35, 0.5
        for i in range(60):
            rgb = colorsys.hsv_to_rgb(i/60, sat, val)
            c = (int(rgb[0]*255), int(rgb[1]*255), int(rgb[2]*255), 255)
            d.arc([cx-r, cy-r, cx+r, cy+r],
                  start=i*6, end=(i+1)*6+1, fill=c, width=w)

    # ── Active (PIL rendered for smooth circles) ────────────

    def _render_active(self):
        sz = self.size
        big = sz * 2
        s = sz / 76.0

        # Parse toolbar bg
        try:
            c = self._toolbar_bg.lstrip("#")
            bg_rgba = (int(c[0:2],16), int(c[2:4],16), int(c[4:6],16), 255)
        except (ValueError, IndexError):
            bg_rgba = (48, 45, 94, 255)

        img = Image.new("RGBA", (big, big), bg_rgba)
        d = ImageDraw.Draw(img, "RGBA")
        cx = cy = big // 2
        pad = 6
        r = big // 2 - pad

        # Dark circle fill
        d.ellipse([pad, pad, big - pad, big - pad], fill=(30, 32, 48, 255))

        # Animated ring color
        if self._state == "listening":
            p = 0.65 + 0.35 * math.sin(self._phase * 0.18)
            v = int(140 + 80 * p)
            ring_color = (v, v, v, 255)
        else:
            p = 0.6 + 0.4 * math.sin(self._phase * 0.12)
            ring_color = (int(74+20*p), int(106+20*p), int(143+20*p), 255)

        # Ring (PIL arc — smooth)
        d.ellipse([pad, pad, big - pad, big - pad],
                  outline=ring_color, width=6)

        # Bars (rectangles — no AA needed)
        bw = max(8, int(10 * s)); gap = max(10, int(14 * s))
        total = self.BAR_COUNT * bw + (self.BAR_COUNT - 1) * gap
        sx = cx - total // 2
        for i, h in enumerate(self._bars):
            bh = max(6, int(r * h))
            x1 = sx + i * (bw + gap)
            y1, y2 = cy - bh // 2, cy + bh // 2
            if self._state == "listening":
                gv = int(90 + 140 * h)
                bc = (gv, gv, gv, 255)
            else:
                t = (math.sin(self._phase * 0.1 + i * 0.9) + 1) / 2
                bc = (int(60+60*t), int(90+60*t), int(130+80*t), 255)
            d.rectangle([x1, y1, x1 + bw, y2], fill=bc)

        # Label (bold, gold)
        if self._show_label:
            lbl_sz = max(10, int(sz * 0.36))
            try: lfont = ImageFont.truetype("segoeuib.ttf", lbl_sz)
            except OSError:
                try: lfont = ImageFont.truetype("segoeui.ttf", lbl_sz)
                except OSError: lfont = ImageFont.load_default()
            lbb = d.textbbox((0, 0), self._display_label, font=lfont)
            lw = lbb[2] - lbb[0]
            ly = big - (lbb[3] - lbb[1]) - pad - 2
            d.text((cx - lw // 2, ly), self._display_label,
                   fill=(218, 175, 32, 255), font=lfont)

        # Downscale with anti-aliasing
        img = img.resize((sz, sz), Image.LANCZOS)
        self._photo = ImageTk.PhotoImage(img)
        self.create_image(0, 0, anchor="nw", image=self._photo)

    # ── Animation ─────────────────────────────────────
    def _start(self):
        if not self._job: self._animate()
    def _stop(self):
        if self._job: self.after_cancel(self._job); self._job = None
    def _animate(self):
        self._phase += 1.0; mid = self.BAR_COUNT//2
        if self._state == "listening":
            for i in range(self.BAR_COUNT):
                d = abs(i-mid)/mid if mid else 0
                w = math.sin(self._phase*0.25+i*0.75)*0.5+0.5
                self._bars[i] = max(0.04, w*(1-d*0.25))
        elif self._state == "ai_thinking":
            for i in range(self.BAR_COUNT):
                self._bars[i] = 0.35+0.55*(math.sin(self._phase*0.12+i*1.1)*0.5+0.5)
        self._draw()
        self._job = self.after(self.ANIM_MS, self._animate)

    # ── Input ─────────────────────────────────────────
    def _on_down(self, e):
        self._pressed=True; self._drag_started=False
        self._press_x,self._press_y=e.x_root,e.y_root
    def _on_motion(self, e):
        if self._pressed and not self._drag_started:
            if abs(e.x_root-self._press_x)>5 or abs(e.y_root-self._press_y)>5:
                self._drag_started=True
    def _on_up(self, e):
        if self._pressed and not self._drag_started and self.command: self.command()
        self._pressed=False; self._drag_started=False
    def _on_hover(self, entering):
        self._hover=entering
        if self._state=="idle": self._draw()
