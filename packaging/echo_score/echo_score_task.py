"""Portable OK Script adapter for Echo scoring."""

from ok import TriggerTask, og

from echo_score import DEFAULT_TEMPLATE
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

    def _ensure_overlay(self):
        # Imported scripts must initialize the host overlay lazily.
        try:
            from ok.ui.overlay import win32_gdi
            win32_gdi.HWND_TOPMOST = -2  # HWND_NOTOPMOST
        except ImportError:
            pass
        app = getattr(og, "app", None)
        if app is None:
            return None
        # ``set_overlay_setting('boxes', False)`` is the lifecycle switch for
        # the *entire* overlay, not merely OCR boxes: it persists
        # ``use_overlay=False`` and closes the native window. Keep that global
        # lifecycle enabled, then independently disable only debug boxes on the
        # overlay instance. Do not toggle True every frame, which could flash
        # OCR boxes before the following False call.
        if not app.ok_config.get("use_overlay", False):
            app.set_overlay_setting("boxes", True)
        overlay = app.get_overlay_view()
        if overlay is not None:
            overlay.set_boxes_enabled(False)
        return overlay

    def post_init(self):
        self._ensure_overlay()

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

        analysis = analyze_echo_stats(
            self.ocr(), self.width, self.height,
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
            self._clear(overlay)
        return False

    def _clear(self, overlay, include_status=False):
        self.painter.update([])
        overlay.clear_draw(ECHO_STAT_PAINTER_KEY)
        if include_status:
            overlay.clear_draw(STATUS_PAINTER_KEY)

    def on_destroy(self):
        overlay = self.get_overlay_view()
        if overlay is not None:
            self._clear(overlay, True)
