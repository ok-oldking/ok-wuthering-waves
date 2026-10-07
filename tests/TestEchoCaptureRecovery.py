import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.echo_capture_recovery import CaptureRecoveryMonitor, read_echo_frame
from ok.task.exceptions import CaptureException


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
    def test_missing_capture_skips_ocr_without_disabling_task(self):
        task = SimpleNamespace(executor=SimpleNamespace(method=None), ocr=Mock())
        self.assertIsNone(read_echo_frame(task))
        task.ocr.assert_not_called()

    def test_capture_disappearing_during_ocr_does_not_read_none_width(self):
        task = SimpleNamespace(executor=SimpleNamespace(method=SimpleNamespace(width=1600, height=900)))
        def lose_capture():
            task.executor.method = None
            return ["old frame"]
        task.ocr = lose_capture
        self.assertIsNone(read_echo_frame(task))

    def test_ocr_from_previous_hwnd_is_discarded(self):
        window = SimpleNamespace(hwnd=100, exists=True)
        task = SimpleNamespace(executor=SimpleNamespace(method=SimpleNamespace(width=1600, height=900)))
        def restart_game():
            window.hwnd = 200
            return ["old frame"]
        task.ocr = restart_game
        self.assertIsNone(read_echo_frame(task, window))

    def test_transient_capture_exception_is_waited_out(self):
        task = SimpleNamespace(executor=SimpleNamespace(method=SimpleNamespace(width=1600, height=900)),
                               ocr=Mock(side_effect=CaptureException("window closed")))
        self.assertIsNone(read_echo_frame(task))
        task.ocr = Mock(return_value=["new frame"])
        self.assertEqual((["new frame"], 1600, 900), read_echo_frame(task))

    def test_unrelated_ocr_errors_are_not_hidden(self):
        task = SimpleNamespace(executor=SimpleNamespace(method=SimpleNamespace(width=1600, height=900)),
                               ocr=Mock(side_effect=AttributeError("unrelated OCR error")))
        with self.assertRaises(AttributeError):
            read_echo_frame(task)

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

    def test_repeated_restarts_with_reused_hwnd_force_new_capture(self):
        self.manager.hwnd_window.hwnd = 100
        self.manager.hwnd_window.exists = True
        self.manager.capture_method = FakeCapture(connected=True)
        self.assertFalse(self.monitor.poll())
        for cycle in range(3):
            self.manager.hwnd_window.exists = False
            self.assertFalse(self.monitor.poll())
            self.manager.hwnd_window.exists = True
            # BitBlt still reports connected and the selected HWND is unchanged.
            self.assertTrue(self.monitor.poll())
            self.assertEqual(cycle + 1, self.manager.refreshes)

    def test_hwnd_change_during_retry_delay_remains_pending(self):
        self.manager.hwnd_window.hwnd = 100
        self.manager.hwnd_window.exists = True
        self.manager.capture_method = FakeCapture(connected=True)
        with patch("src.echo_capture_recovery.time.monotonic", side_effect=[0, 1, 2, 6]):
            self.assertFalse(self.monitor.poll())
            self.manager.hwnd_window.hwnd = 200
            self.assertTrue(self.monitor.poll())
            self.manager.hwnd_window.hwnd = 300
            self.manager.preferred["real_hwnd"] = 300
            self.assertFalse(self.monitor.poll())
            self.assertTrue(self.monitor.poll())
        self.assertEqual(2, self.manager.refreshes)

    def test_connected_capture_that_never_produced_a_frame_is_retried(self):
        self.manager.hwnd_window.hwnd = 100
        self.manager.hwnd_window.exists = True
        self.manager.capture_method = FakeCapture(connected=True)
        with patch("src.echo_capture_recovery.time.monotonic", side_effect=[10, 19, 20]):
            self.assertFalse(self.monitor.poll())
            self.assertFalse(self.monitor.poll())
            self.assertTrue(self.monitor.poll())
        self.assertEqual(1, self.manager.refreshes)

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
