"""Background update poller.

A daemon-threaded class that wakes once an hour, asks
``updater.UpdateChecker`` if there's a newer version, downloads it
silently to the user's Downloads folder if so, and then fires a
callback that the main thread can use to show a "ready to install"
toast.

This file is intentionally tiny — the heavy lifting (HTTP, version
parsing, checksum, installer launch) lives in ``updater.py``. This
module is only the *scheduler* + *callback bridge* around it.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Callable, Optional

from updater import UpdateChecker, UpdateDownloader


class BackgroundUpdateManager:
    """Daemon that polls for app updates in the background.

    Lifecycle:

    1. Construct with ``(app_version, repo_url, on_update_ready)``.
    2. Call ``.start()`` — spawns a daemon thread that runs ``_run_loop``.
    3. The thread sleeps 30 s (let the app finish booting), then loops
       forever: check → maybe download → wait 1 hour → repeat. The
       hour-long wait is broken into 1-second sleeps so ``stop_event``
       lets us exit promptly on app shutdown.
    4. When an update is downloaded successfully, ``on_update_ready``
       is invoked with ``(version, installer_path, release_notes)`` —
       the main thread schedules a UI popup based on that.

    Errors during a check are caught + logged but do not stop the loop;
    the next iteration tries again.
    """

    def __init__(
        self,
        app_version: str,
        repo_url: str,
        on_update_ready_callback: Optional[Callable[[str, str, str], None]],
    ) -> None:
        self.app_version = app_version
        self.repo_url = repo_url
        self.on_update_ready = on_update_ready_callback
        self.checker = UpdateChecker(app_version, repo_url)
        self.stop_event = threading.Event()

    # ── Lifecycle ────────────────────────────────────────────────

    def start(self) -> None:
        """Begin polling on a daemon thread. Safe to call once."""
        threading.Thread(target=self._run_loop, daemon=True).start()

    def stop(self) -> None:
        """Request the poll loop to exit. The thread checks this every
        second during its hour-long wait, so it can take up to ~1 s to
        respond."""
        self.stop_event.set()

    # ── Internals ────────────────────────────────────────────────

    def _run_loop(self) -> None:
        print("[UPDATE] Background update manager started")
        # Initial check after 30 seconds (let app load first)
        time.sleep(30)

        while not self.stop_event.is_set():
            try:
                self._check_and_process()
            except Exception as e:
                print(f"[UPDATE] Background check failed: {e}")

            # Wait 1 hour before next check; respect stop_event every
            # second so we can exit promptly on shutdown.
            for _ in range(3600):
                if self.stop_event.is_set():
                    return
                time.sleep(1)

    def _check_and_process(self) -> None:
        print("[UPDATE] Checking for updates silently...")
        result = self.checker.check_for_updates()

        if result.get("available"):
            print(f"[UPDATE] New version found: {result.get('version')}")
            download_url = result.get("download_url")

            # Download silently. UpdateDownloader writes to the user's
            # Downloads folder; that's fine for the background path
            # because the installer is what the user actually clicks.
            downloader = UpdateDownloader(download_url)
            print("[UPDATE] Starting background download...")
            path = downloader.download_update()

            if path and os.path.exists(path):
                print(f"[UPDATE] Download complete: {path}")
                # Notify main thread so it can pop a "ready to install"
                # toast / dialog at a UI-safe time.
                if self.on_update_ready:
                    self.on_update_ready(
                        result.get("version"),
                        path,
                        result.get("release_notes"),
                    )
        else:
            print("[UPDATE] No update found")
