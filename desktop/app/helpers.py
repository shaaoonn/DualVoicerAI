"""Module-level helper functions used across the app.

These are pure functions (no Tk dependencies, no global mutable state)
that lived inline at the top of ``main.py``. Lifting them into a small
module so:

* `main.py` shrinks.
* Tests can call them without spinning up ``VoiceTypingApp``.
* Other modules (e.g. ``app.background_updates``) can ``from app.helpers
  import format_size`` without circular-importing main.

There is intentionally NO class here — these are stateless functions.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile


# ─────────────────────────────────────────────────────────────────────────────
# Public helpers
# ─────────────────────────────────────────────────────────────────────────────

def format_size(bytes_val: float) -> str:
    """Format a byte count as a human-readable size string.

    Walks up the binary-prefix ladder (B → KB → MB → GB → TB) until the
    value fits in the current unit. Used for download-progress UI in the
    update flow.

    >>> format_size(0)
    '0.0 B'
    >>> format_size(2048)
    '2.0 KB'
    >>> format_size(5 * 1024 * 1024)
    '5.0 MB'
    """
    for unit in ("B", "KB", "MB", "GB"):
        if bytes_val < 1024:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f} TB"


def resource_path(relative_path: str) -> str:
    """Resolve a bundled asset path that works in both dev and PyInstaller.

    * **Frozen build** (``--onefile`` EXE): assets are extracted to
      ``sys._MEIPASS`` at launch. We resolve relative to that.
    * **Dev run** (``python main.py``): assets sit next to the source
      file. We resolve relative to ``__file__`` so the lookup keeps
      working no matter what working directory the user launched from.

    Earlier the dev fallback used ``os.path.abspath('.')`` which broke
    silently when the app was launched from outside ``desktop/`` (e.g.
    from the project root) — start/end SFX WAVs would fail to load.
    Resolving against ``__file__`` avoids that.

    Parameters
    ----------
    relative_path:
        Path fragment relative to the resource root (e.g.
        ``"end-sound.wav"`` or ``"fonts/SolaimanLipi.ttf"``).

    Returns
    -------
    str
        Absolute path to the asset on the local filesystem.
    """
    try:
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except Exception:
        # NB: based on this module's location (desktop/app/helpers.py),
        # the desktop/ directory is its PARENT. Most assets live there
        # (e.g. desktop/end-sound.wav), so resolve relative to that.
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def silent_restart(app_instance=None) -> None:
    """Restart the running app process invisibly.

    Used by Settings → Reset / Restart, and by the update-installer
    path. Steps:

    1. Snapshot the window position so the post-restart instance can
       reopen at the same place. (Saved to ``self.settings`` first as
       memory, then to the settings JSON as a durable backup.)
    2. Remove the single-instance lock file so the new process can
       acquire it.
    3. Spawn the replacement process — ``sys.executable`` in frozen
       mode, the current Python interpreter in dev mode.
    4. Tear down the current process via ``os._exit(0)``.

    Failures are swallowed silently because the app runs in
    ``--windowed`` mode where exceptions surface nowhere useful. If the
    restart fails the user just sees nothing happen, which is acceptable
    fallback behaviour.

    Parameters
    ----------
    app_instance:
        Optional ``VoiceTypingApp`` instance. When provided we save its
        current geometry into ``app_instance.settings`` and JSON-persist
        via ``app_instance.settings_file``. When ``None``, restart still
        happens but the new instance falls back to the default geometry.
    """
    try:
        pos_x, pos_y = 100, 100

        if app_instance:
            try:
                pos_x = app_instance.winfo_x()
                pos_y = app_instance.winfo_y()

                # Save to settings file as backup (so the new process
                # picks up the position even if --pos= argv parsing
                # fails for any reason).
                app_instance.settings["window_x"] = pos_x
                app_instance.settings["window_y"] = pos_y
                if hasattr(app_instance, "settings_file"):
                    with open(app_instance.settings_file, "w") as f:
                        json.dump(app_instance.settings, f, indent=2)
            except Exception:
                pass

        # Drop the lock so the replacement process can start clean.
        lock_file = os.path.join(tempfile.gettempdir(), "dual_voicer.lock")
        try:
            if os.path.exists(lock_file):
                os.remove(lock_file)
        except OSError:
            pass

        if getattr(sys, "frozen", False):
            # FROZEN (PyInstaller EXE)
            executable = sys.executable
            cmd_args = [executable, f"--pos={pos_x},{pos_y}"]

            # Windowed mode: plain Popen is enough — we don't need any
            # of the CREATE_NO_WINDOW / startupinfo dance.
            subprocess.Popen(cmd_args, shell=False)
        else:
            # DEV mode: hand off to a fresh interpreter via execl so we
            # genuinely replace the current process (cleanest restart
            # semantically — Python state is wiped).
            python = sys.executable
            os.execl(python, python, *sys.argv)

        # Stop the current instance cleanly if a Tk app was given,
        # then force-kill so background daemon threads don't hold the
        # process open.
        if app_instance:
            try:
                app_instance.quit()
            except Exception:
                pass

        os._exit(0)

    except Exception:
        # --windowed mode swallows tracebacks; nothing to log to.
        # Don't crash the caller — just bail out and let them carry on.
        pass


def install_socket_default_timeout(seconds: float = 10.0) -> None:
    """Pin the global socket default timeout.

    The Google STT API call (``speech_recognition.recognize_google``)
    uses ``urllib`` under the hood, which honours
    ``socket.setdefaulttimeout``. 10 seconds covers large audio chunks
    without letting a stalled connection hang the recognition loop
    forever.

    Called once at module import time from ``main.py``; exposed here as
    a function so it's discoverable and testable.
    """
    socket.setdefaulttimeout(seconds)
