"""Read-only scoring loop independent of OKWW's automation pause state."""

import threading
import time

from ok.util.logger import Logger

try:
    from .echo_capture_recovery import CaptureRecoveryMonitor
except ImportError:  # Portable OK Script import.
    from echo_capture_recovery import CaptureRecoveryMonitor


logger = Logger.get_logger(__name__)


class _SerializedOCR:
    def __init__(self, engine):
        self.engine = engine
        self.lock = threading.RLock()

    def ocr(self, *args, **kwargs):
        with self.lock:
            return self.engine.ocr(*args, **kwargs)

    def __call__(self, *args, **kwargs):
        with self.lock:
            return self.engine(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.engine, name)


def serialize_shared_ocr(executor):
    """Serialize complete OCR pipelines used by scoring and host tasks.

    ONNX sessions may be thread-safe, but detector/recognizer wrappers can
    contain scratch state. Do not run the shared pipeline concurrently.
    """
    if getattr(executor, "_echo_serialized_ocr", False):
        return
    original = executor.ocr_lib
    engines = {}
    lock = threading.Lock()

    def ocr_lib(name="default"):
        with lock:
            if name not in engines:
                engines[name] = _SerializedOCR(original(name))
            return engines[name]

    executor.ocr_lib = ocr_lib
    executor._echo_serialized_ocr = True


class EchoScoreRuntime:
    def __init__(self, task, device_manager, exit_event, interval=0.5):
        self.task = task
        self.device_manager = device_manager
        self.exit_event = exit_event
        self.interval = interval
        self.capture_started = False
        self.recovery = CaptureRecoveryMonitor(
            device_manager, exit_event,
            allow_paused=lambda: self.capture_started and self.task.score_enabled(),
        )
        self._stop_event = threading.Event()
        self._thread = None
        self._last_error = None
        self._last_error_at = 0

    def start(self):
        if self._thread is None:
            serialize_shared_ocr(self.task.executor)
            self._thread = threading.Thread(target=self._run, name="EchoScoreRuntime", daemon=True)
            self._thread.start()

    def stop(self):
        self._stop_event.set()
        self.recovery.stop()

    @property
    def stopped(self):
        return self._stop_event.is_set() or self.exit_event.is_set()

    def _run(self):
        while not self.exit_event.is_set() and not self._stop_event.wait(self.interval):
            try:
                self.poll()
                self._last_error = None
            except Exception as error:
                # This read-only loop must not disable an imported task after
                # a transient window/capture failure. Retry without unpausing
                # the host or resuming combat, clicks, or queued tasks.
                now = time.monotonic()
                if str(error) != self._last_error or now - self._last_error_at >= 30:
                    logger.error("Echo score runtime failed; will retry", error)
                    self._last_error, self._last_error_at = str(error), now

    def poll(self):
        if self.exit_event.is_set() or self._stop_event.is_set():
            return False
        # Retain the initial Screenshot/Start contract. Once capture has been
        # started, only the public scoring switch controls this read-only loop.
        if not self.capture_started and (not self.task.executor.paused
                or getattr(self.task.executor, "thread", None) is not None):
            self.capture_started = True
            logger.info("Echo scoring capture activated; automation pause will not stop read-only scoring")
        if not self.capture_started:
            return False
        self.recovery.poll()
        if self.task.render_score():
            self.recovery.record_frame()
        return True
