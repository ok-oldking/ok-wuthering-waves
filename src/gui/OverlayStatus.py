"""Project-specific painters for the native game overlay."""

import ctypes
import os


STATUS_TEXT = "WUWA.ICEHE.LIFE | Powered by OKWW x XWUID"


def paint_okww_status(canvas, overlay):
    """Draw a bold Echo overlay status label at the bottom of every game screen."""
    if os.name != "nt":
        return

    from ok.ui.overlay import win32_gdi

    width = getattr(overlay, "_frame_width", 0)
    height = getattr(overlay, "_frame_height", 0)
    if width <= 0 or height <= 0:
        return

    font_height = -max(24, round(height * 0.03 * canvas.ratio))
    font = win32_gdi.gdi32.CreateFontW(
        font_height, 0, 0, 0, 700, 0, 0, 0, 1, 0, 0, 5, 0, "Segoe UI"
    )
    old_font = win32_gdi.gdi32.SelectObject(canvas.hdc, font)
    try:
        text_size = win32_gdi.SIZE()
        win32_gdi.gdi32.GetTextExtentPoint32W(
            canvas.hdc, STATUS_TEXT, len(STATUS_TEXT), ctypes.byref(text_size)
        )
        x = max(0, (round(width * canvas.ratio) - text_size.cx) // 2)
        y = round(height * 0.955 * canvas.ratio)
        # Draw a scaled black halo first.  Fixed-pixel offsets look uneven on
        # different game resolutions and were the source of the jagged border.
        outline = max(1, round(2 * canvas.ratio))
        win32_gdi.gdi32.SetTextColor(canvas.hdc, win32_gdi._rgb(0, 0, 0))
        for dx, dy in ((-outline, 0), (outline, 0), (0, -outline), (0, outline),
                       (-outline, -outline), (-outline, outline),
                       (outline, -outline), (outline, outline)):
            win32_gdi.gdi32.TextOutW(
                canvas.hdc, x + dx, y + dy, STATUS_TEXT, len(STATUS_TEXT)
            )
        # Orange remains distinct from the red/white stat boxes while the
        # black halo keeps it readable over both dark and luminous backgrounds.
        win32_gdi.gdi32.SetTextColor(canvas.hdc, win32_gdi._rgb(255, 145, 35))
        win32_gdi.gdi32.TextOutW(canvas.hdc, x, y, STATUS_TEXT, len(STATUS_TEXT))
    finally:
        win32_gdi.gdi32.SelectObject(canvas.hdc, old_font)
        win32_gdi.gdi32.DeleteObject(font)
