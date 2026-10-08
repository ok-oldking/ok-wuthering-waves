"""Portable OK Script adapter for Echo scoring."""

from ok import TriggerTask, og

from echo_score import DEFAULT_TEMPLATE
from echo_capture_recovery import read_echo_frame
from echo_runtime import EchoScoreRuntime
from echo_overlay_recovery import ensure_echo_overlay
from echo_stat_overlay import ECHO_STAT_PAINTER_KEY, EchoStatBoxPainter, analyze_echo_stats
from overlay_status import paint_okww_status


STATUS_PAINTER_KEY = "echo-score-status"


class EchoScoreOverlayTask(TriggerTask):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "声骸评分后台识别"
        self.description = "识别单个声骸并按 XW-UID 模板评分"
        self.trigger_interval = 0.5
        self.visible = False
        self.painter = EchoStatBoxPainter()
        self.auto_matched_template = None

    def on_create(self):
        self._enabled = True
        if not self.config.get("_enabled", False):
            self.config["_enabled"] = True
        # Official OKWW calls after_init/on_create for imported tasks, but
        # post_init only for built-ins. The monitor must already run when OCR
        # has no frames, otherwise the worker cannot recover itself.
        self._ensure_runtime()

    def _ensure_runtime(self):
        if getattr(self, "score_runtime", None) is not None:
            return
        manager = getattr(og, "device_manager", None)
        if manager is not None:
            self.score_runtime = EchoScoreRuntime(self, manager, self.executor.exit_event)
            self.capture_recovery = self.score_runtime.recovery
            self.score_runtime.start()

    def _ensure_overlay(self):
        app = getattr(og, "app", None)
        # ``set_overlay_setting('boxes', False)`` is the lifecycle switch for
        # the *entire* overlay, not merely OCR boxes: it persists
        # ``use_overlay=False`` and closes the native window. Keep that global
        # lifecycle enabled, then independently disable only debug boxes on the
        # overlay instance. Do not toggle True every frame, which could flash
        # OCR boxes before the following False call.
        window = getattr(getattr(og, "device_manager", None), "hwnd_window", None)
        return ensure_echo_overlay(app, window)

    def post_init(self):
        self._ensure_overlay()
        self._ensure_runtime()

    def _settings(self):
        for task in self.get_tasks():
            if task.__class__.__name__ == "EchoScoreSettingsTask" and task.config is not None:
                return task.config
        return {
            "启用声骸评分": True,
            "自动匹配评分模板": False,
            "角色评分模板": DEFAULT_TEMPLATE,
            "Show Debug Boxes": False,
        }

    def run(self):
        self._ensure_runtime()
        # Recognition runs independently: TaskExecutor can pause automatically
        # or skip every trigger before run() when a game has no capture frames.
        return False

    def score_enabled(self):
        return bool(self._settings().get("启用声骸评分", True))

    def render_score(self):
        overlay = self._ensure_overlay()
        if overlay is None:
            return False
        settings = self._settings()
        # The portable import is always a non-development build. Ignore stale
        # cached values from older package versions and keep OCR boxes off.
        if not settings.get("启用声骸评分", True):
            self._clear(overlay, True)
            return False

        hwnd_window = getattr(getattr(og, "device_manager", None), "hwnd_window", None)
        if (hwnd_window is not None and hwnd_window.exists and not hwnd_window.visible
                and self.painter.rectangles):
            return False

        frame = read_echo_frame(self, hwnd_window, direct=True)
        if frame is None:
            self._clear(overlay, True)
            return False
        boxes, width, height = frame
        if getattr(self, "score_runtime", None) is not None and self.score_runtime.stopped:
            return False
        analysis = analyze_echo_stats(
            boxes, width, height,
            settings.get("角色评分模板", DEFAULT_TEMPLATE),
            auto_match=bool(settings.get("自动匹配评分模板", False)),
            remembered_template=getattr(self, "auto_matched_template", None),
        )
        if getattr(analysis, "selected_template", None):
            self.auto_matched_template = analysis.selected_template
        self.painter.update(
            analysis.rectangles, analysis.row_scores, analysis.summary,
            analysis.tier_labels, analysis.tier_colors,
        )
        if analysis.rectangles:
            overlay.draw(ECHO_STAT_PAINTER_KEY, self.painter.paint)
            if analysis.summary:
                overlay.draw(STATUS_PAINTER_KEY, paint_okww_status)
            else:
                overlay.clear_draw(STATUS_PAINTER_KEY)
        else:
            self._clear(overlay, True)
        return True

    def _clear(self, overlay, include_status=False):
        self.painter.update([])
        overlay.clear_draw(ECHO_STAT_PAINTER_KEY)
        if include_status:
            overlay.clear_draw(STATUS_PAINTER_KEY)

    def on_destroy(self):
        if runtime := getattr(self, "score_runtime", None):
            runtime.stop()
        overlay = self.get_overlay_view()
        if overlay is not None:
            self._clear(overlay, True)
