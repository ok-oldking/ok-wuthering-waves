"""Shared startup helpers for source and packaged launches."""

import ctypes
import os
import sys


def ensure_windows_admin():
    """Relaunch with elevation so the overlay can follow an elevated game."""
    if os.name != "nt" or ctypes.windll.shell32.IsUserAnAdmin():
        return True

    script = os.path.abspath(sys.argv[0])
    result = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        sys.executable,
        f'"{script}"',
        os.path.dirname(script),
        1,
    )
    if result <= 32:
        raise RuntimeError("Administrator permission is required to display the game overlay.")
    return False


def configure_game_bound_overlay():
    """Keep the overlay above its game owner without making it system-topmost."""
    if os.name != "nt":
        return
    from ok.ui.overlay import win32_gdi

    # Win32GdiOverlay uses this value as SetWindowPos's insert-after target.
    # HWND_NOTOPMOST preserves the owned-window relationship with the game,
    # while allowing unrelated windows above the game to cover the overlay.
    win32_gdi.HWND_TOPMOST = -2  # HWND_NOTOPMOST
