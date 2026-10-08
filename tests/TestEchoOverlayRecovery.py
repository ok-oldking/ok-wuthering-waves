import os
import subprocess
import sys
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.echo_overlay_recovery import ensure_echo_overlay


class TestEchoOverlayRecovery(unittest.TestCase):
    def test_stale_native_object_is_replaced_not_reused(self):
        old = SimpleNamespace(_native_available=True, _hwnd=123, _owner_hwnd=100)
        fresh = Mock(_native_available=False)
        app = Mock(ok_config={"use_overlay": True})
        app.get_overlay_view.side_effect = [old, fresh]
        window = SimpleNamespace(hwnd=200, exists=True)
        with patch("ok.ui.overlay.win32_gdi.user32.IsWindow", return_value=False):
            self.assertIs(fresh, ensure_echo_overlay(app, window))
        app._close_overlay.assert_called_once_with(wait=False)
        fresh.sync_source_window.assert_called_once_with(window)
        fresh.set_boxes_enabled.assert_called_once_with(False)

    def test_even_live_ownerless_overlay_rebinds_to_new_game(self):
        old = SimpleNamespace(_native_available=True, _hwnd=123, _owner_hwnd=0)
        fresh = Mock()
        app = Mock(ok_config={"use_overlay": True})
        app.get_overlay_view.side_effect = [old, fresh]
        with patch("ok.ui.overlay.win32_gdi.user32.IsWindow", return_value=True), \
                patch("src.echo_overlay_recovery.native_window_owner", return_value=0):
            ensure_echo_overlay(app, SimpleNamespace(hwnd=200, exists=True))
        app._close_overlay.assert_called_once_with(wait=False)

    def test_reused_game_hwnd_with_detached_native_owner_is_rebound(self):
        old = SimpleNamespace(_native_available=True, _hwnd=123, _owner_hwnd=200)
        fresh = Mock()
        app = Mock(ok_config={"use_overlay": True})
        app.get_overlay_view.side_effect = [old, fresh]
        with patch("ok.ui.overlay.win32_gdi.user32.IsWindow", return_value=True), \
                patch("src.echo_overlay_recovery.native_window_owner", return_value=0):
            self.assertIs(fresh, ensure_echo_overlay(app, SimpleNamespace(hwnd=200, exists=True)))
        app._close_overlay.assert_called_once_with(wait=False)

    @unittest.skipUnless(os.name == "nt", "Windows native lifecycle integration")
    def test_real_native_owner_exit_and_three_restarts(self):
        # A hidden, separate helper process substitutes for the game. Unlike
        # the old fake HWND tests this exercises owner detachment/destruction,
        # a dead native render thread, and the host's stale Python cache.
        from ok.ui.overlay.win32_gdi import Win32GdiOverlay, user32
        from ok.util.handler import ExitEvent

        helper = """
import ctypes, sys
u = ctypes.WinDLL('user32', use_last_error=True)
u.CreateWindowExW.argtypes = [ctypes.c_uint32, ctypes.c_wchar_p, ctypes.c_wchar_p,
    ctypes.c_uint32, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
u.CreateWindowExW.restype = ctypes.c_void_p
u.DestroyWindow.argtypes = [ctypes.c_void_p]
h = u.CreateWindowExW(0, 'STATIC', 'Echo lifecycle test (hidden)', 0x80000000,
    0, 0, 160, 90, None, None, None, None)
assert h
print(h, flush=True)
sys.stdin.readline()
u.DestroyWindow(h)
"""
        window = SimpleNamespace(hwnd=0, exists=False, visible=False, x=0, y=0,
            window_width=160, window_height=90, width=160, height=90, scaling=1.0)
        exit_event = ExitEvent()

        class HostCache:
            ok_config = {"use_overlay": True}
            overlay_window = None

            def get_overlay_view(self):
                if self.overlay_window is None:
                    self.overlay_window = Win32GdiOverlay(window, exit_event=exit_event)
                return self.overlay_window

            def _close_overlay(self, wait=False):
                overlay, self.overlay_window = self.overlay_window, None
                overlay.close(wait=wait)

        app = HostCache()
        previous = None
        old_topmost = __import__("ok.ui.overlay.win32_gdi", fromlist=["HWND_TOPMOST"]).HWND_TOPMOST
        try:
            for cycle in range(4):  # Initial process plus three restarts.
                process = subprocess.Popen([sys.executable, "-c", helper], stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW)
                try:
                    window.hwnd = int(process.stdout.readline().strip())
                    window.exists = True
                    overlay = ensure_echo_overlay(app, window)
                    self.assertIsNot(previous, overlay)
                    self.assertTrue(user32.IsWindow(overlay._hwnd))
                    self.assertEqual(window.hwnd, overlay._owner_hwnd)
                    process.communicate("exit\n", timeout=5)
                    window.exists = False
                    if cycle == 1:
                        # Also test native destruction without close(), as
                        # the host cache remains marked open in this case.
                        user32.PostMessageW(overlay._hwnd, 0x0010, 0, 0)  # WM_CLOSE
                    deadline = time.monotonic() + 3
                    while cycle == 1 and overlay._hwnd and user32.IsWindow(overlay._hwnd) and time.monotonic() < deadline:
                        time.sleep(0.02)
                    if cycle == 1:
                        self.assertFalse(overlay._hwnd and user32.IsWindow(overlay._hwnd))
                    self.assertIs(app.overlay_window, overlay)  # Host still caches dead object.
                    previous = overlay
                finally:
                    if process.poll() is None:
                        process.communicate("exit\n", timeout=5)
        finally:
            if app.overlay_window is not None:
                app._close_overlay(wait=True)
            exit_event.set()
            import ok.ui.overlay.win32_gdi as native
            native.HWND_TOPMOST = old_topmost


if __name__ == "__main__":
    unittest.main()
