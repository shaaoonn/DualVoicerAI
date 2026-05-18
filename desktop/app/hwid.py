"""Hardware fingerprint + login-config persistence.

The HWID is a persistent device identifier we use for:

* Subscription enforcement (one license = one device).
* Anti-piracy (a leaked installer + license still only works on the
  original machine).

Strategy: hash several stable hardware components (motherboard UUID,
CPU ID, primary disk serial, MAC address) into a 32-character ID
prefixed ``DV-``. The first call generates + persists the ID to
``<app_data_dir>/.hwid``; every subsequent call reads it back. The
file survives uninstall (lives in ``%APPDATA%``), so reinstalling the
app on the same machine yields the same HWID.

Login config (the saved email/phone for auto-login) is unrelated to
the HWID semantically but lives in the same file because both are
small per-device JSON / text blobs that the auth flow reads/writes
together.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import subprocess
import uuid


# ─────────────────────────────────────────────────────────────────────────────
# Hardware ID
# ─────────────────────────────────────────────────────────────────────────────

def get_stable_hwid(app_data_dir: str) -> str:
    """Return the persistent device fingerprint.

    Read-or-write semantics:

    1. If ``<app_data_dir>/.hwid`` already exists with a plausible
       value (>10 chars), return it as-is.
    2. Otherwise, generate a fresh ID from hardware components and
       persist it to that file before returning.

    The generation strategy combines whichever components Windows
    exposes (motherboard UUID, CPU ID, disk serial, MAC). If two or
    more components succeed, the ID is a SHA-256 hash of the sorted
    combo — stable across reboots, reinstalls, even Windows upgrades.
    If fewer than two succeed (e.g. on a locked-down VM), we fall
    back to a random UUID so we never return an empty string.

    Parameters
    ----------
    app_data_dir:
        Directory to read/write ``.hwid`` from. Typically
        ``%APPDATA%/DualVoicer``. Created if it doesn't exist.

    Returns
    -------
    str
        The HWID, always prefixed with ``DV-``.
    """
    hwid_file = os.path.join(app_data_dir, ".hwid")

    # Step 1 — return existing HWID if present.
    try:
        if os.path.exists(hwid_file):
            with open(hwid_file, "r") as f:
                saved_hwid = f.read().strip()
                if saved_hwid and len(saved_hwid) > 10:
                    print(f"[HWID] Using saved HWID: {saved_hwid[:8]}...")
                    return saved_hwid
    except Exception as e:
        print(f"[HWID] Error reading saved HWID: {e}")

    # Step 2 — generate from hardware components.
    hwid_parts: list[str] = []

    # Component 1: Motherboard UUID
    try:
        cmd = 'powershell -Command "(Get-CimInstance -ClassName Win32_ComputerSystemProduct).UUID"'
        output = subprocess.check_output(
            cmd, shell=True, stderr=subprocess.DEVNULL, timeout=5
        ).decode().strip()
        if output and output.lower() not in ("", "none", "to be filled by o.e.m."):
            hwid_parts.append(f"MB:{output}")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        pass

    # Component 2: CPU ID
    try:
        cmd = 'powershell -Command "(Get-CimInstance -ClassName Win32_Processor).ProcessorId"'
        output = subprocess.check_output(
            cmd, shell=True, stderr=subprocess.DEVNULL, timeout=5
        ).decode().strip()
        if output:
            hwid_parts.append(f"CPU:{output}")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        pass

    # Component 3: Primary disk serial
    try:
        cmd = (
            'powershell -Command "(Get-CimInstance -ClassName Win32_DiskDrive | '
            'Select-Object -First 1).SerialNumber"'
        )
        output = subprocess.check_output(
            cmd, shell=True, stderr=subprocess.DEVNULL, timeout=5
        ).decode().strip()
        if output:
            hwid_parts.append(f"DISK:{output}")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        pass

    # Component 4: MAC address (uuid.getnode → 48-bit MAC)
    try:
        mac = format(uuid.getnode(), "012x")
        hwid_parts.append(f"MAC:{mac}")
    except Exception:
        pass

    if len(hwid_parts) >= 2:
        combined = "|".join(sorted(hwid_parts))
        hwid_hash = hashlib.sha256(combined.encode()).hexdigest()[:32]
        new_hwid = f"DV-{hwid_hash.upper()}"
        print(f"[HWID] Generated from {len(hwid_parts)} hardware components")
    else:
        # Fallback: random UUID. The user can still authenticate but
        # the device fingerprint won't survive reinstalls.
        new_hwid = f"DV-{str(uuid.uuid4()).replace('-', '').upper()[:32]}"
        print("[HWID] Generated random HWID (no hardware info available)")

    # Step 3 — persist for next launch.
    try:
        os.makedirs(app_data_dir, exist_ok=True)
        with open(hwid_file, "w") as f:
            f.write(new_hwid)
        print(f"[HWID] Saved new HWID: {new_hwid[:8]}...")
    except Exception as e:
        print(f"[HWID] Warning: Could not save HWID: {e}")

    return new_hwid


# ─────────────────────────────────────────────────────────────────────────────
# Login config (email + phone for auto-login)
# ─────────────────────────────────────────────────────────────────────────────

def save_login_config(config_file: str, email: str, phone: str) -> None:
    """Write the user's email + phone to ``config_file`` as JSON.

    Used after a successful login so the next launch can auto-restore
    the session without prompting the user again. Records a timestamp
    for future diagnostics.
    """
    try:
        config = {
            "email": email,
            "phone": phone,
            "last_login": datetime.datetime.now().isoformat(),
        }
        with open(config_file, "w") as f:
            json.dump(config, f)
        print(f"[INFO] Login config saved for {email}")
    except Exception as e:
        print(f"[WARNING] Failed to save config: {e}")


def load_login_config(config_file: str) -> tuple[str | None, str | None]:
    """Read the saved login config.

    Returns ``(email, phone)`` if a valid file exists, else
    ``(None, None)``. Errors are swallowed (and logged) so callers
    can treat "no file" and "broken file" identically.
    """
    try:
        if os.path.exists(config_file):
            with open(config_file, "r") as f:
                config = json.load(f)
            return config.get("email"), config.get("phone")
    except Exception as e:
        print(f"[WARNING] Failed to load config: {e}")
    return None, None


def clear_login_config(config_file: str) -> None:
    """Delete the saved login config (used on explicit logout)."""
    try:
        if os.path.exists(config_file):
            os.remove(config_file)
            print("[INFO] Login config cleared")
    except Exception as e:
        print(f"[WARNING] Failed to clear config: {e}")
