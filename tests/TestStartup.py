import unittest
from unittest.mock import patch

from src.startup import configure_game_bound_overlay


class TestStartup(unittest.TestCase):
    def test_windows_overlay_is_not_system_topmost(self):
        import ok.ui.overlay.win32_gdi as win32_gdi

        previous = win32_gdi.HWND_TOPMOST
        try:
            with patch("src.startup.os.name", "nt"):
                configure_game_bound_overlay()
            self.assertEqual(win32_gdi.HWND_TOPMOST, -2)
        finally:
            win32_gdi.HWND_TOPMOST = previous


if __name__ == "__main__":
    unittest.main()
