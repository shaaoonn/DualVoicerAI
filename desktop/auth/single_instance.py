"""Single-instance enforcement via temp-folder lock file.

The desktop app must not run two instances simultaneously — they'd
fight over the global keyboard hook, the audio device, and the system
tray slot. The classic Windows recipe is a lock file in ``%TEMP%``
holding the running PID; new processes refuse to start when an alive
PID is found there.

Originally inlined inside ``VoiceTypingApp.__init__`` (main.py:163-214).
Extracted here as pure functions so:

* No ``self.*`` dependencies — testable in isolation.
* main.py / app.app_core can drive the dance with two short calls
  (``acquire_lock`` + ``release_lock``) instead of inlining ~50 lines.
* The functions are reusable by any other entrypoint we might add in
  the future (e.g. a CLI tool that should also defer to the GUI).
"""

from __future__ import annotations

import os
import sys
import tkinter as tk
from tkinter import messagebox
from typing import Optional


def is_process_running(pid: int) -> bool:
    """Return True if a process with ``pid`` is currently alive.

    Prefers ``psutil`` (cross-platform, reliable). Falls back to
    ``os.kill(pid, 0)`` for the rare environment where psutil isn't
    bundled. Both API surfaces fail-closed: any error → False so we
    don't accidentally keep treating a stale lock as live.
    """
    try:
        import psutil
        return psutil.pid_exists(pid)
    except ImportError:
        try:
            os.kill(pid, 0)  # signal 0 = "test if process exists"
            return True
        except OSError:
            return False
    except (ValueError, OSError):
        return False


def acquire_lock(lock_file: str) -> bool:
    """Attempt to acquire the single-instance lock.

    On success: writes the current PID into ``lock_file`` and returns
    True. The caller continues launching the app normally.

    On failure (an alive instance already holds the lock): shows a
    user-facing messagebox and returns False — the caller MUST exit
    immediately. Stale locks (PID dead) are silently cleaned up; a
    corrupted lock file is removed and treated as a fresh acquire.

    Parameters
    ----------
    lock_file:
        Absolute path to the lock file. Typically
        ``os.path.join(tempfile.gettempdir(), "dual_voicer.lock")``.

    Returns
    -------
    bool
        True if the lock was acquired, False if another live instance
        already held it.
    """
    if os.path.exists(lock_file):
        try:
            with open(lock_file, "r") as f:
                old_pid = int(f.read().strip())

            if not is_process_running(old_pid):
                print(f"[INFO] Removing stale lock file (PID {old_pid} not running)")
                try:
                    os.remove(lock_file)
                except OSError:
                    pass
            else:
                # Live instance already running. Show the user the popup
                # then signal the caller to bail out.
                print(f"[INFO] App already running (PID {old_pid})")
                try:
                    messagebox.showinfo(
                        "Dual Voicer",
                        "App is already running! Check the tray icon or press Alt+Z.",
                    )
                except tk.TclError:
                    # No Tk root yet — we can't show a popup. The
                    # caller exiting is enough for the user to notice.
                    pass
                return False
        except Exception as e:
            print(f"[WARNING] Lock file check failed: {e}")
            # Corrupted lock file — try to clear and re-acquire.
            try:
                os.remove(lock_file)
            except OSError:
                pass

    # Write our PID into the now-vacant lock file.
    try:
        with open(lock_file, "w") as f:
            f.write(str(os.getpid()))
        print(f"[INFO] Lock file created with PID {os.getpid()}")
        return True
    except Exception as e:
        # If we can't even write the lock, don't block startup — print
        # a warning but proceed as if acquired. Two instances running
        # is bad, but no instances running because /tmp is borked is
        # worse.
        print(f"[ERROR] Could not create lock file: {e}")
        return True


def release_lock(lock_file: str) -> None:
    """Remove the lock file. Called at app shutdown.

    Best-effort — any failure is swallowed (the file might already
    have been removed by the OS during a crash recovery, or never
    existed if ``acquire_lock`` itself failed to write it).
    """
    try:
        if os.path.exists(lock_file):
            os.remove(lock_file)
            print("[INFO] Lock file removed")
    except OSError as e:
        print(f"[WARNING] Could not remove lock file: {e}")
