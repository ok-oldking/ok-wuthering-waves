import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
from ok.feature.Box import Box

from src.echo_capture_recovery import read_echo_frame
from src.echo_runtime import EchoScoreRuntime, serialize_shared_ocr


class TestEchoRuntime(unittest.TestCase):
    def make_runtime(self):
        executor = SimpleNamespace(paused=True, _last_frame_time=time.time(), current_task=None)
        capture = Mock()
        capture.connected.return_value = True
        manager = SimpleNamespace(executor=executor, capture_method=capture,
            hwnd_window=SimpleNamespace(hwnd=100, exists=True, visible=True, pos_valid=True),
            get_preferred_device=lambda: {"device": "windows", "real_hwnd": 100}, refresh=Mock())
        task = SimpleNamespace(executor=executor, render_score=Mock(return_value=True),
            score_enabled=Mock(return_value=True))
        runtime = EchoScoreRuntime(task, manager, threading.Event())
        return runtime, task, manager

    def test_no_scoring_before_first_capture_start(self):
        runtime, task, manager = self.make_runtime()
        self.assertFalse(runtime.poll())
        task.render_score.assert_not_called()
        manager.refresh.assert_not_called()

    def test_start_immediately_followed_by_pause_is_not_missed(self):
        runtime, task, manager = self.make_runtime()
        # A started TaskExecutor has a thread even if the game became invalid
        # before the first 0.5-second scoring tick observed paused=False.
        task.executor.thread = threading.current_thread()
        self.assertTrue(runtime.poll())
        self.assertTrue(runtime.capture_started)
        self.assertTrue(task.executor.paused)
        task.render_score.assert_called_once()

    def test_three_restarts_after_host_automatic_pause_still_render(self):
        runtime, task, manager = self.make_runtime()
        task.executor.paused = False
        self.assertTrue(runtime.poll())
        # The host's minimized-window path sets paused=True and leaves it so
        # after the new game starts. We must not resume any automation tasks.
        task.executor.paused = True
        for cycle in range(3):
            manager.hwnd_window.exists = False
            runtime.poll()
            manager.hwnd_window.exists = True
            manager.hwnd_window.hwnd = 200 + cycle
            runtime.poll()
            self.assertTrue(task.executor.paused)
        self.assertEqual(7, task.render_score.call_count)
        self.assertEqual(3, manager.refresh.call_count)

    def test_score_heartbeat_prevents_reconnect_storm_while_host_is_paused(self):
        runtime, task, manager = self.make_runtime()
        task.executor.paused = False
        runtime.poll()
        task.executor.paused = True
        task.executor._last_frame_time = 1
        with patch("src.echo_capture_recovery.time.time", return_value=100):
            runtime.recovery.record_frame()
            runtime.poll()
        manager.refresh.assert_not_called()

    def test_disabled_switch_does_not_reconnect_a_paused_host(self):
        runtime, task, manager = self.make_runtime()
        runtime.capture_started = True
        task.score_enabled.return_value = False
        manager.capture_method = None
        runtime.poll()
        manager.refresh.assert_not_called()
        task.render_score.assert_called_once()  # Clear stale output.

    def test_stop_prevents_future_rendering(self):
        runtime, task, manager = self.make_runtime()
        task.executor.paused = False
        runtime.stop()
        self.assertTrue(runtime.stopped)
        self.assertFalse(runtime.poll())
        task.render_score.assert_not_called()

    def test_real_scoring_thread_retries_error_without_disabling_host_tasks(self):
        runtime, task, manager = self.make_runtime()
        task.executor.paused = False
        task.executor.ocr_lib = Mock(return_value=Mock())
        task.disable = Mock()
        resumed = threading.Event()
        calls = []

        def render():
            calls.append(True)
            if len(calls) == 1:
                raise RuntimeError("capture switched during OCR")
            resumed.set()
            return True

        task.render_score = render
        runtime.interval = 0.01
        try:
            runtime.start()
            with patch("src.echo_runtime.logger.error"):
                self.assertTrue(resumed.wait(2))
            task.disable.assert_not_called()
        finally:
            runtime.stop()
            runtime._thread.join(1)
        self.assertFalse(runtime._thread.is_alive())

    def test_direct_ocr_uses_fresh_capture_not_paused_executor_frame(self):
        image = np.zeros((900, 1600, 3), dtype=np.uint8)
        capture = SimpleNamespace(width=1600, height=900, get_frame=Mock(return_value=image))
        task = SimpleNamespace(executor=SimpleNamespace(method=capture, paused=True),
            ocr=Mock(side_effect=AssertionError("must not read executor.frame")),
            ocr_fun=Mock(return_value=Mock(return_value=([Box(5, 5, 10, 10, name="攻击")], []))),
            ocr_default_threshold=0.2)
        result = read_echo_frame(task, SimpleNamespace(hwnd=100, exists=True, pos_valid=True), direct=True)
        self.assertEqual((1600, 900), result[1:])
        task.ocr.assert_not_called()
        self.assertIs(image, task.ocr_fun.return_value.call_args.args[1])
        self.assertTrue(task.executor.paused)

    def test_serialized_ocr_returns_same_wrapper_to_host_and_worker(self):
        engine = Mock()
        original = Mock(return_value=engine)
        executor = SimpleNamespace(ocr_lib=original)
        serialize_shared_ocr(executor)
        wrapper = executor.ocr_lib()
        serialize_shared_ocr(executor)
        self.assertIs(wrapper, executor.ocr_lib())
        wrapper.ocr("frame")
        engine.ocr.assert_called_once_with("frame")
        original.assert_called_once_with("default")


if __name__ == "__main__":
    unittest.main()
