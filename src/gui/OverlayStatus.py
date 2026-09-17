"""Project-specific painters for the native game overlay."""

import ctypes
import os


STATUS_TEXT = "ECHO-ON"


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
        win32_gdi.gdi32.SetTextColor(canvas.hdc, win32_gdi._rgb(80, 255, 120))
        win32_gdi.gdi32.TextOutW(canvas.hdc, x, y, STATUS_TEXT, len(STATUS_TEXT))
    finally:
        win32_gdi.gdi32.SelectObject(canvas.hdc, old_font)
        win32_gdi.gdi32.DeleteObject(font)
