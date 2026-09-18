"""Portable OK Script adapter for the Echo scoring feature."""

from ok import TriggerTask, og
from ok.core.events import communicate

from echo_score import DEFAULT_TEMPLATE
from echo_stat_overlay import ECHO_STAT_PAINTER_KEY, EchoStatBoxPainter, analyze_echo_stats
from overlay_status import paint_echo_status


STATUS_PAINTER_KEY = "echo-score-status"


class EchoScoreOverlayTask(TriggerTask):
    """Recognize and score the currently opened single-Echo panel."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "声骸评分后台识别"
        self.description = "识别单个声骸的主副词条，并按 XW-UID 模板评分"
        self.trigger_interval = 0.5
        self.default_config.update({"_enabled": True})
        # The official imported-script page only renders one-time task cards.
        # A separate visible settings task owns the controls, while this
        # trigger remains hidden and performs the background recognition.
        self.visible = False
        self.painter = EchoStatBoxPainter()
        self._window_connected = False

    def on_create(self):
        # Keep the hidden worker schedulable. The visible settings card owns
        # the actual feature switch, so a stale persisted _enabled value from
        # an earlier package cannot make the feature impossible to re-enable.
        super().on_create()
        self._enabled = True

    def post_init(self):
        self._ensure_overlay()

    def _ensure_overlay(self):
        """Initialize lazily because official imported tasks skip post_init()."""
        app = getattr(og, "app", None)
        if app is not None:
            app.set_overlay_setting("boxes", True)
            app.get_overlay_view()
        if not self._window_connected:
            communicate.window.connect(self._keep_overlay_visible)
            self._window_connected = True

    def _settings(self):
        for task in self.get_tasks():
            if task.__class__.__name__ == "EchoScoreSettingsTask" and task.config is not None:
                return task.config
        return {
            "启用声骸评分": True,
            "角色评分模板": DEFAULT_TEMPLATE,
            "显示主副词条框体": True,
            "Show Debug Boxes": False,
        }

    def run(self):
        self._ensure_overlay()
        overlay = self.get_overlay_view()
        if overlay is None:
            return False
        settings = self._settings()
        if not settings.get("启用声骸评分", True):
            self._clear_stat_overlay()
            overlay.clear_draw(STATUS_PAINTER_KEY)
            return False
        overlay.draw(STATUS_PAINTER_KEY, paint_echo_status)
        overlay.set_boxes_enabled(bool(settings.get("Show Debug Boxes", False)))
        if not settings.get("显示主副词条框体", True):
            self._clear_stat_overlay()
            return False

        hwnd_window = getattr(getattr(og, "device_manager", None), "hwnd_window", None)
        if (hwnd_window is not None and hwnd_window.exists and not hwnd_window.visible
                and self.painter.rectangles):
            return False

        analysis = analyze_echo_stats(
            self.ocr(), self.width, self.height,
            settings.get("角色评分模板", DEFAULT_TEMPLATE),
        )
        self.painter.update(
            analysis.rectangles, analysis.row_scores, analysis.summary,
            analysis.tier_labels, analysis.tier_colors,
        )
        if analysis.rectangles:
            overlay.draw(ECHO_STAT_PAINTER_KEY, self.painter.paint)
        else:
            overlay.clear_draw(ECHO_STAT_PAINTER_KEY)
        return False

    def _keep_overlay_visible(self, visible, *geometry):
        hwnd_window = getattr(getattr(og, "device_manager", None), "hwnd_window", None)
        game_exists = bool(getattr(hwnd_window, "exists", visible))
        has_geometry = len(geometry) < 6 or bool(geometry[4] and geometry[5])
        overlay = self.get_overlay_view()
        if overlay is not None and geometry:
            overlay.update_overlay(game_exists and has_geometry, *geometry)

    def _clear_stat_overlay(self):
        self.painter.update([])
        overlay = self.get_overlay_view()
        if overlay is not None:
            overlay.clear_draw(ECHO_STAT_PAINTER_KEY)

    def on_destroy(self):
        if self._window_connected:
            communicate.window.disconnect(self._keep_overlay_visible)
            self._window_connected = False
        overlay = self.get_overlay_view()
        if overlay is not None:
            overlay.clear_draw(ECHO_STAT_PAINTER_KEY)
            overlay.clear_draw(STATUS_PAINTER_KEY)
