"""Live OCR debug boxes for Echo detail and tuning panels."""

from ok import TriggerTask, og

from src.gui.EchoStatOverlay import (
    ECHO_STAT_PAINTER_KEY,
    EchoStatBoxPainter,
    analyze_echo_stats,
)
from src.task.BaseWWTask import BaseWWTask


class EchoStatOverlayTask(TriggerTask, BaseWWTask):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_config.update({"_enabled": True})
        self.trigger_interval = 0.5
        self.name = "🛠️ Echo Stat Boxes"
        self.description = "Outline main and substats on Echo detail and tuning panels"
        self.echo_score_config = self.get_global_config("声骸评分")
        self.painter = EchoStatBoxPainter()

    def run(self):
        overlay = self.get_overlay_view()
        if overlay is None:
            return False
        # This project-specific HUD content has its own switch on the Echo
        # Score tab and remains independent from the framework debug boxes.
        if not self.echo_score_config.get("显示主副词条框体", True):
            self.painter.update([])
            overlay.clear_draw(ECHO_STAT_PAINTER_KEY)
            return False

        # A background capture can temporarily be empty even though the game
        # window still exists.  Preserve the last recognized Echo annotations
        # instead of clearing them while the user inspects another program.
        hwnd_window = getattr(getattr(og, "device_manager", None), "hwnd_window", None)
        if (hwnd_window is not None and hwnd_window.exists and not hwnd_window.visible
                and self.painter.rectangles):
            return False

        # This is the exact full-frame OCR result whose Boxes are rendered by
        # the red debug layer.  We only regroup and recolour those Boxes.
        ocr_boxes = self.ocr()
        from src.echo_score import DEFAULT_TEMPLATE
        template_name = self.echo_score_config.get("角色评分模板", DEFAULT_TEMPLATE)
        analysis = analyze_echo_stats(ocr_boxes, self.width, self.height, template_name)
        self.painter.update(
            analysis.rectangles,
            analysis.row_scores,
            analysis.summary,
            analysis.tier_labels,
            analysis.tier_colors,
        )
        if analysis.rectangles:
            overlay.draw(ECHO_STAT_PAINTER_KEY, self.painter.paint)
        else:
            overlay.clear_draw(ECHO_STAT_PAINTER_KEY)
        return False
