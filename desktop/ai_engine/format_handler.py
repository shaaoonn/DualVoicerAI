# ai_engine/format_handler.py
import re

def strip_markdown(text: str) -> str:
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*',     r'\1', text)
    text = re.sub(r'_(.*?)_',       r'\1', text)
    text = re.sub(r'`(.*?)`',       r'\1', text)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[-*+]\s+', '\u2022 ', text, flags=re.MULTILINE)
    return text.strip()

def format_for_paste(text: str, mode: str = "plain") -> str:
    return strip_markdown(text) if mode == "plain" else text


def markdown_to_html_clipboard(md_text: str) -> bool:
    """Convert markdown to HTML and place on Windows clipboard as CF_HTML.
    Also places plain text as fallback. Returns True on success."""
    try:
        import markdown2
        import ctypes
        import ctypes.wintypes

        # Convert markdown -> HTML body
        html_body = markdown2.markdown(md_text, extras=[
            "fenced-code-blocks", "tables", "strike", "task_list"
        ])

        # Professional CSS with real heading sizes & typography
        CSS = (
            'body{font-family:Segoe UI,sans-serif;font-size:11pt;line-height:1.6;color:#222;}'
            'h1{font-size:20pt;font-weight:bold;margin:14pt 0 6pt;}'
            'h2{font-size:16pt;font-weight:bold;margin:12pt 0 5pt;}'
            'h3{font-size:13pt;font-weight:bold;margin:10pt 0 4pt;}'
            'h4{font-size:11pt;font-weight:bold;margin:8pt 0 3pt;}'
            'p{margin:4pt 0;}'
            'strong,b{font-weight:bold;}'
            'em,i{font-style:italic;}'
            'ul,ol{margin:4pt 0 4pt 20pt;}'
            'li{margin:2pt 0;}'
            'code{background:#f0f0f0;padding:2px 4px;border-radius:3px;'
            'font-family:Consolas,monospace;font-size:10pt;}'
            'pre{background:#f5f5f5;padding:8px;border-radius:4px;'
            'font-family:Consolas,monospace;font-size:10pt;overflow-x:auto;}'
            'blockquote{border-left:3px solid #ccc;margin:6pt 0;padding:4pt 12pt;color:#555;}'
            'table{border-collapse:collapse;margin:6pt 0;}'
            'th,td{border:1px solid #ccc;padding:4pt 8pt;}'
            'th{background:#f0f0f0;font-weight:bold;}'
        )

        # Build CF_HTML clipboard format
        fragment_start_marker = "<!--StartFragment-->"
        fragment_end_marker = "<!--EndFragment-->"

        prefix = (
            "Version:0.9\r\n"
            "StartHTML:{:010d}\r\n"
            "EndHTML:{:010d}\r\n"
            "StartFragment:{:010d}\r\n"
            "EndFragment:{:010d}\r\n"
        )
        dummy = prefix.format(0, 0, 0, 0)
        header_len = len(dummy.encode('utf-8'))

        html_with_markers = (
            f'<html><head><meta charset="utf-8"><style>{CSS}</style></head><body>'
            f'{fragment_start_marker}{html_body}{fragment_end_marker}'
            '</body></html>'
        )

        html_bytes = html_with_markers.encode('utf-8')
        start_html = header_len
        end_html = header_len + len(html_bytes)
        start_frag = header_len + html_bytes.find(fragment_start_marker.encode()) + len(fragment_start_marker.encode())
        end_frag = header_len + html_bytes.find(fragment_end_marker.encode())

        cf_html = prefix.format(start_html, end_html, start_frag, end_frag).encode('utf-8') + html_bytes

        # Win32 clipboard API via ctypes (64-bit safe)
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        # Set correct arg/return types for 64-bit pointer safety
        kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
        kernel32.GlobalAlloc.restype = ctypes.c_void_p
        kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
        user32.OpenClipboard.argtypes = [ctypes.c_void_p]
        user32.EmptyClipboard.argtypes = []

        CF_HTML = user32.RegisterClipboardFormatW("HTML Format")
        CF_UNICODETEXT = 13

        if not user32.OpenClipboard(0):
            return False

        try:
            user32.EmptyClipboard()

            # 1. Set CF_HTML
            size_html = len(cf_html) + 1
            h_html = kernel32.GlobalAlloc(0x0042, size_html)
            if h_html:
                p_html = kernel32.GlobalLock(h_html)
                if p_html:
                    ctypes.memmove(p_html, cf_html, len(cf_html))
                    kernel32.GlobalUnlock(h_html)
                    user32.SetClipboardData(CF_HTML, h_html)

            # 2. Set plain text fallback (CF_UNICODETEXT)
            plain = strip_markdown(md_text)
            plain_w = plain.encode('utf-16-le') + b'\x00\x00'
            size_text = len(plain_w)
            h_text = kernel32.GlobalAlloc(0x0042, size_text)
            if h_text:
                p_text = kernel32.GlobalLock(h_text)
                if p_text:
                    ctypes.memmove(p_text, plain_w, len(plain_w))
                    kernel32.GlobalUnlock(h_text)
                    user32.SetClipboardData(CF_UNICODETEXT, h_text)

            return True
        finally:
            user32.CloseClipboard()

    except Exception as e:
        print(f"[FORMAT] HTML clipboard failed: {e}, falling back to plain")
        return False
