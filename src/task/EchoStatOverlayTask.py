"""Live OCR debug boxes for Echo detail and tuning panels."""

from ok import TriggerTask

from src.gui.EchoStatOverlay import (
    ECHO_STAT_PAINTER_KEY,
    EchoStatBoxPainter,
    find_echo_stat_rectangles,
)
from src.task.BaseWWTask import BaseWWTask


class EchoStatOverlayTask(TriggerTask, BaseWWTask):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_config.update({"_enabled": True})
        self.trigger_interval = 0.5
        self.name = "🛠️ Echo Stat Boxes"
        self.description = "Outline main and substats on Echo detail and tuning panels"
        self.overlay_config = self.get_global_config("Development Overlay")
        self.painter = EchoStatBoxPainter()

    def run(self):
        overlay = self.get_overlay_view()
        if overlay is None:
            return False
        # This is project-specific HUD content, not the framework's noisy
        # detection-box layer.  It therefore follows the dedicated custom
        # overlay switch the user can enable without generic OCR boxes.
        if not self.overlay_config.get("Show Custom Overlay Content", True):
            self.painter.update([])
            overlay.clear_draw(ECHO_STAT_PAINTER_KEY)
            return False

        # This is the exact full-frame OCR result whose Boxes are rendered by
        # the red debug layer.  We only regroup and recolour those Boxes.
        ocr_boxes = self.ocr()
        rectangles = find_echo_stat_rectangles(ocr_boxes, self.width, self.height)
        self.painter.update(rectangles)
        if rectangles:
            overlay.draw(ECHO_STAT_PAINTER_KEY, self.painter.paint)
        else:
            overlay.clear_draw(ECHO_STAT_PAINTER_KEY)
        return False
