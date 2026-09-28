import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.echo_capture_recovery import CaptureRecoveryMonitor


class FakeCapture:
    def __init__(self, connected=False):
        self.is_connected = connected
        self.closes = 0

    def connected(self):
        return self.is_connected

    def close(self):
        self.closes += 1


class FakeDeviceManager:
    def __init__(self):
        self.hwnd_window = SimpleNamespace(hwnd=0, exists=False)
        self.executor = SimpleNamespace(paused=False, _last_frame_time=0, current_task=None)
        self.capture_method = FakeCapture()
        self.preferred = {"device": "windows", "real_hwnd": 100}
        self.refreshes = 0

    def get_preferred_device(self):
        return self.preferred

    def refresh(self):
        self.refreshes += 1


class TestEchoCaptureRecovery(unittest.TestCase):
    def setUp(self):
        self.manager = FakeDeviceManager()
        self.exit_event = threading.Event()
        self.monitor = CaptureRecoveryMonitor(
            self.manager, self.exit_event, retry_delay=5,
        )

    def test_game_restart_reconnects_without_restart_of_host(self):
        self.manager.hwnd_window.hwnd = 100
        self.manager.hwnd_window.exists = True
        with patch("src.echo_capture_recovery.time.monotonic", return_value=10):
            self.assertTrue(self.monitor.poll())
            self.assertFalse(self.monitor.poll())
        self.assertEqual(1, self.manager.refreshes)
        self.assertEqual(1, self.manager.capture_method.closes)

        self.manager.hwnd_window.exists = False
        self.assertFalse(self.monitor.poll())
        self.manager.hwnd_window.hwnd = 200
        self.manager.hwnd_window.exists = True
        with patch("src.echo_capture_recovery.time.monotonic", return_value=11):
            self.assertTrue(self.monitor.poll())
        self.assertEqual(2, self.manager.refreshes)

    def test_failed_reconnect_is_retried_but_not_on_every_poll(self):
        self.manager.hwnd_window.hwnd = 100
        self.manager.hwnd_window.exists = True
        with patch("src.echo_capture_recovery.time.monotonic", side_effect=[10, 12, 15]):
            self.assertTrue(self.monitor.poll())
            self.assertFalse(self.monitor.poll())
            self.assertTrue(self.monitor.poll())
        self.assertEqual(2, self.manager.refreshes)

    def test_only_active_disconnected_capture_is_restarted(self):
        self.manager.hwnd_window.hwnd = 100
        self.manager.hwnd_window.exists = True
        self.manager.executor.paused = True
        self.assertFalse(self.monitor.poll())
        self.manager.executor.paused = False
        self.manager.capture_method = None
        # A failed WGC/BitBlt startup may leave capture_method=None. It must
        # remain retryable while the user has screenshot capture enabled.
        self.assertTrue(self.monitor.poll())
        self.manager.capture_method = FakeCapture(connected=True)
        self.assertFalse(self.monitor.poll())
        self.assertEqual(1, self.manager.refreshes)

    def test_connected_bitblt_is_refreshed_for_new_hwnd_and_stale_selection(self):
        self.manager.capture_method = FakeCapture(connected=True)
        self.manager.hwnd_window.hwnd = 100
        self.manager.hwnd_window.exists = True
        self.assertFalse(self.monitor.poll())

        # A newly started game has another HWND, while BitBlt.connected()
        # misleadingly remains true because it only checks window existence.
        self.manager.hwnd_window.hwnd = 200
        self.assertTrue(self.monitor.poll())
        self.assertEqual(1, self.manager.capture_method.closes)
        self.assertEqual(1, self.manager.refreshes)

    def test_connected_capture_without_new_frames_is_refreshed(self):
        self.manager.capture_method = FakeCapture(connected=True)
        self.manager.hwnd_window.hwnd = 100
        self.manager.hwnd_window.exists = True
        self.manager.executor._last_frame_time = 80
        with patch("src.echo_capture_recovery.time.time", return_value=91):
            self.assertTrue(self.monitor.poll())
        self.assertEqual(1, self.manager.refreshes)

    def test_missing_preferred_device_is_refreshed_even_if_bitblt_reports_connected(self):
        self.manager.capture_method = FakeCapture(connected=True)
        self.manager.hwnd_window.hwnd = 100
        self.manager.hwnd_window.exists = True
        self.manager.preferred = None
        self.assertTrue(self.monitor.poll())
        self.assertEqual(1, self.manager.refreshes)

    def test_minimized_window_does_not_retry_until_usable(self):
        self.manager.hwnd_window.hwnd = 100
        self.manager.hwnd_window.exists = True
        self.manager.hwnd_window.pos_valid = False
        self.assertFalse(self.monitor.poll())
        self.assertEqual(0, self.manager.refreshes)

    def test_does_not_interrupt_another_active_task_for_stale_frame(self):
        self.manager.capture_method = FakeCapture(connected=True)
        self.manager.hwnd_window.hwnd = 100
        self.manager.hwnd_window.exists = True
        self.manager.executor._last_frame_time = 80
        self.manager.executor.current_task = SimpleNamespace()
        with patch("src.echo_capture_recovery.time.time", return_value=91):
            self.assertFalse(self.monitor.poll())
        self.assertEqual(0, self.manager.refreshes)

    def test_shutdown_stops_reconnect_checks(self):
        self.manager.hwnd_window.hwnd = 100
        self.manager.hwnd_window.exists = True
        self.exit_event.set()
        self.assertFalse(self.monitor.poll())
        self.assertEqual(0, self.manager.refreshes)


if __name__ == "__main__":
    unittest.main()
