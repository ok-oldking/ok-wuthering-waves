"""Background OCR and score overlay for one Echo panel."""

from ok import TriggerTask, og

from src.echo_score import DEFAULT_TEMPLATE
from src.gui.EchoStatOverlay import ECHO_STAT_PAINTER_KEY, EchoStatBoxPainter, analyze_echo_stats
from src.gui.OverlayStatus import paint_okww_status

STATUS_PAINTER_KEY = "echo-score-status"


class EchoStatOverlayTask(TriggerTask):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.trigger_interval = 0.5
        self.name = "声骸评分后台识别"
        self.description = "实时识别查看/调谐界面的单个声骸"
        self.visible = False
        self.echo_score_config = self.get_global_config("声骸评分")
        self.debug_config = self.get_global_config("开发调试")
        self.painter = EchoStatBoxPainter()
        self.auto_matched_template = None

    def on_create(self):
        """This hidden worker is controlled by the public score switch only."""
        self._enabled = True
        if not self.config.get("_enabled", False):
            self.config["_enabled"] = True

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

        overlay.set_boxes_enabled(bool(self.debug_config.get("Show Debug Boxes", False)))

        hwnd_window = getattr(getattr(og, "device_manager", None), "hwnd_window", None)
        if (hwnd_window is not None and hwnd_window.exists and not hwnd_window.visible
                and self.painter.rectangles):
            return False

        analysis = analyze_echo_stats(
            self.ocr(), self.width, self.height,
            self.echo_score_config.get("角色评分模板", DEFAULT_TEMPLATE),
            auto_match=bool(self.echo_score_config.get("自动匹配评分模板", False)),
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
                # The watermark is a scoring-state indicator, not a global
                # overlay label.  It only appears when this frame is a
                # recognized single-Echo view with a calculated score.
                overlay.draw(STATUS_PAINTER_KEY, paint_okww_status)
            else:
                overlay.clear_draw(STATUS_PAINTER_KEY)
        else:
            overlay.clear_draw(ECHO_STAT_PAINTER_KEY)
            overlay.clear_draw(STATUS_PAINTER_KEY)
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
