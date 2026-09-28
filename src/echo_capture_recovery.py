"""Reconnect an active OK Script capture after the game process is restarted."""

import threading
import time

from ok.util.logger import Logger


logger = Logger.get_logger(__name__)


class CaptureRecoveryMonitor:
    def __init__(self, device_manager, exit_event, interval=1.0, retry_delay=5.0,
                 stale_frame_delay=10.0):
        self.device_manager = device_manager
        self.exit_event = exit_event
        self.interval = interval
        self.retry_delay = retry_delay
        self.stale_frame_delay = stale_frame_delay
        self._last_attempt = float("-inf")
        self._last_hwnd = 0
        self._stop_event = threading.Event()
        self._thread = None

    def start(self):
        if self._thread is None:
            self._thread = threading.Thread(
                target=self._run, name="EchoCaptureRecovery", daemon=True,
            )
            self._thread.start()

    def stop(self):
        self._stop_event.set()

    def _run(self):
        while not self.exit_event.is_set() and not self._stop_event.wait(self.interval):
            try:
                self.poll()
            except Exception as error:
                logger.error("Echo capture recovery check failed", error)

    def poll(self):
        """Refresh a started capture if its target or latest frame is stale."""
        manager = self.device_manager
        if manager is None or self.exit_event.is_set() or self._stop_event.is_set():
            return False

        window = getattr(manager, "hwnd_window", None)
        hwnd = getattr(window, "hwnd", 0) if getattr(window, "exists", False) else 0
        if not hwnd:
            self._last_hwnd = 0
            self._last_attempt = float("-inf")
            return False
        if not getattr(window, "pos_valid", True):
            return False

        executor = getattr(manager, "executor", None)
        capture = getattr(manager, "capture_method", None)
        if executor is None or executor.paused:
            return False
        now = time.monotonic()
        hwnd_changed = self._last_hwnd not in (0, hwnd)
        self._last_hwnd = hwnd
        preferred = manager.get_preferred_device()
        preferred_hwnd = preferred.get("real_hwnd") if preferred else None
        wrong_selection = preferred is None or (
            preferred.get("device") == "windows"
            and preferred_hwnd not in (None, 0, hwnd)
        )
        connected = capture is not None and capture.connected()
        last_frame = getattr(executor, "_last_frame_time", 0)
        current_task = getattr(executor, "current_task", None)
        another_task_running = current_task is not None and current_task.__class__.__name__ not in (
            "EchoStatOverlayTask", "EchoScoreOverlayTask",
        )
        stale_frame = (
            last_frame > 0 and time.time() - last_frame >= self.stale_frame_delay
            and not another_task_running
        )
        if not (hwnd_changed or wrong_selection or not connected or stale_frame):
            return False
        if now - self._last_attempt < self.retry_delay:
            return False
        self._last_attempt = now
        reason = (
            "new game HWND" if hwnd_changed else
            "stale selected HWND" if wrong_selection else
            "capture disconnected" if not connected else "no recent frames"
        )
        logger.info(f"Refreshing Echo capture for HWND {hwnd}: {reason}")
        # BitBlt.connected() only checks that the *window* exists, so it can
        # report True while its old GDI context returns no frames. Release it
        # before the normal device refresh, which also updates preferred
        # pc_<hwnd> and the overlay source through OK Script's device signal.
        if capture is not None:
            try:
                capture.close()
            except Exception as error:
                logger.error("Failed to close stale Echo capture", error)
        manager.refresh()
        return True
