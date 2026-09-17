from ok import TriggerTask

from src.gui.OverlayStatus import paint_okww_status
from src.task.BaseWWTask import BaseWWTask


OVERLAY_PAINTER_KEY = "okww-status"


class OverlayStatusTask(TriggerTask, BaseWWTask):
    """Keeps a small development status label in sync with the game scene."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_config.update({"_enabled": True})
        self.trigger_interval = 0.5
        self.name = "🛠️ Overlay Status"
        self.description = "Show ECHO development status in the game overlay"
        self.echo_score_config = self.get_global_config("声骸评分")

    def run(self):
        show_boxes = self.echo_score_config.get("Show Debug Boxes", False)
        app = self._app
        if not app.ok_config.get("use_overlay", False):
            app.ok_config["use_overlay"] = True
        overlay = self.get_overlay_view()
        if overlay is None:
            return False
        overlay.set_boxes_enabled(show_boxes)

        overlay.draw(OVERLAY_PAINTER_KEY, paint_okww_status)
        return False
