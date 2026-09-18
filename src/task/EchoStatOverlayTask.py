"""Background OCR and score overlay for one Echo panel."""

from ok import TriggerTask, og

from src.echo_score import DEFAULT_TEMPLATE
from src.gui.EchoStatOverlay import ECHO_STAT_PAINTER_KEY, EchoStatBoxPainter, analyze_echo_stats
from src.gui.OverlayStatus import paint_okww_status

STATUS_PAINTER_KEY = "echo-score-status"


class EchoStatOverlayTask(TriggerTask):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_config.update({"_enabled": True})
        self.trigger_interval = 0.5
        self.name = "声骸评分后台识别"
        self.description = "实时识别查看/调谐界面的单个声骸"
        self.visible = False
        self.echo_score_config = self.get_global_config("声骸评分")
        self.painter = EchoStatBoxPainter()

    def post_init(self):
        app = getattr(og, "app", None)
        if app is not None:
            app.set_overlay_setting("boxes", True)

    def run(self):
        overlay = self.get_overlay_view()
        if overlay is None:
            return False
        if not self.echo_score_config.get("启用声骸评分", True):
            self._clear(overlay, include_status=True)
            return False

        overlay.draw(STATUS_PAINTER_KEY, paint_okww_status)
        overlay.set_boxes_enabled(bool(self.echo_score_config.get("Show Debug Boxes", False)))
        if not self.echo_score_config.get("显示主副词条框体", True):
            self._clear(overlay)
            return False

        hwnd_window = getattr(getattr(og, "device_manager", None), "hwnd_window", None)
        if (hwnd_window is not None and hwnd_window.exists and not hwnd_window.visible
                and self.painter.rectangles):
            return False

        analysis = analyze_echo_stats(
            self.ocr(), self.width, self.height,
            self.echo_score_config.get("角色评分模板", DEFAULT_TEMPLATE),
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

    def _clear(self, overlay, include_status=False):
        self.painter.update([])
        overlay.clear_draw(ECHO_STAT_PAINTER_KEY)
        if include_status:
            overlay.clear_draw(STATUS_PAINTER_KEY)

    def on_destroy(self):
        overlay = self.get_overlay_view()
        if overlay is not None:
            self._clear(overlay, include_status=True)
