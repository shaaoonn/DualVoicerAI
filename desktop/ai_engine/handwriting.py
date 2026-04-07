"""Google Handwriting Recognition via unofficial Input Tools API.

Converts pen strokes (x/y coordinate lists) into recognized text.
API endpoint is fetched from remote_config so it can be updated
server-side without an app update.
"""

import threading

import requests

from remote_config import get_remote_config, DEFAULTS


class HandwritingRecognizer:
    """Async handwriting recognition with callback pattern."""

    def __init__(self, on_result, on_error=None):
        """
        on_result(text: str) — called on main thread with recognized text.
        on_error(error: str) — called on main thread if recognition fails.
        """
        self._on_result = on_result
        self._on_error = on_error

    def recognize(self, strokes, language="en", width=800, height=600,
                  pre_context=""):
        """Send strokes to Google API in a background thread.

        strokes: List[List[Tuple[float, float]]]
            Each inner list is one pen stroke as (x, y) coordinate pairs.
        language: 'en' or 'bn' (or any Google-supported language code).
        width, height: Canvas dimensions for writing_guide.
        pre_context: Previously recognized text (up to 20 chars) for
            word boundary detection and spacing.
        """
        threading.Thread(
            target=self._do_recognize,
            args=(strokes, language, width, height, pre_context),
            daemon=True,
        ).start()

    def _do_recognize(self, strokes, language, width, height, pre_context):
        """Background thread: call API and invoke callback."""
        try:
            # Convert strokes to Google's ink format:
            # Each stroke = [x_array, y_array, timestamp_array]
            ink = []
            for stroke_points in strokes:
                if not stroke_points:
                    continue
                xs = [int(p[0]) for p in stroke_points]
                ys = [int(p[1]) for p in stroke_points]
                # Timestamps: sequential ms values (Google expects these)
                ts = list(range(0, len(xs) * 20, 20))
                ink.append([xs, ys, ts])

            if not ink:
                return

            request = {
                "writing_guide": {
                    "writing_area_width": width,
                    "writing_area_height": height,
                },
                "ink": ink,
                "language": language,
                "max_num_results": 5,
                "max_completions": 0,
            }
            if pre_context:
                request["pre_context"] = pre_context[-20:]

            payload = {
                "options": "enable_pre_space",
                "requests": [request],
            }

            config = get_remote_config()
            url = config.get("handwriting_api_url", DEFAULTS["handwriting_api_url"])

            resp = requests.post(url, json=payload, timeout=5)
            resp.raise_for_status()
            data = resp.json()

            # Response format: ["SUCCESS", [["", [candidate1, candidate2, ...]]]]
            if data and data[0] == "SUCCESS" and len(data) > 1:
                candidates = data[1][0][1]
                if candidates:
                    self._on_result(candidates[0])
                    return

            # No candidates
            if self._on_error:
                self._on_error("No recognition result")

        except requests.RequestException as e:
            if self._on_error:
                self._on_error(f"Network error: {e}")
        except (ValueError, KeyError, IndexError) as e:
            if self._on_error:
                self._on_error(f"Parse error: {e}")
