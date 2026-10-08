"""Restore native overlays whose game owner was destroyed or replaced."""

from ok.util.logger import Logger


logger = Logger.get_logger(__name__)


def native_window_owner(hwnd):
    import win32gui
    return win32gui.GetWindow(hwnd, 4)  # GW_OWNER


def ensure_echo_overlay(app, window, *, debug_boxes=False):
    if app is None:
        return None
    from ok.ui.overlay import win32_gdi
    win32_gdi.HWND_TOPMOST = -2  # Stay game-bound, never system-topmost.
    if not app.ok_config.get("use_overlay", False):
        app.set_overlay_setting("boxes", True)
    overlay = app.get_overlay_view()
    if overlay is not None and getattr(overlay, "_native_available", False) is True:
        hwnd = getattr(overlay, "_hwnd", 0)
        owner = getattr(overlay, "_owner_hwnd", 0)
        target = getattr(window, "hwnd", 0) if getattr(window, "exists", False) else 0
        dead = not hwnd or not win32_gdi.user32.IsWindow(hwnd)
        # Across processes Windows may detach rather than destroy the popup.
        # The cached _owner_hwnd then lies (especially with HWND reuse).
        actual_owner = native_window_owner(hwnd) if not dead else 0
        wrong_owner = target and (owner != target or actual_owner != target)
        if dead or wrong_owner:
            logger.info(f"Recreating Echo overlay: native={hwnd}, old owner={owner}, new owner={target}")
            # The host caches the Python object even after its native window
            # dies or loses its owner. Its public getter cannot fix that.
            app._close_overlay(wait=False)
            if not target:
                return None
            overlay = app.get_overlay_view()
    if overlay is not None:
        overlay.set_boxes_enabled(bool(debug_boxes))
        if window is not None:
            overlay.sync_source_window(window)
    return overlay
