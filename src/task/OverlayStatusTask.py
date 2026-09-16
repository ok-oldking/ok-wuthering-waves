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
        self.description = "Show OKWW development status in the game overlay"
        self.overlay_config = self.get_global_config("Development Overlay")

    def run(self):
        show_content = self.overlay_config.get("Show Custom Overlay Content", True)
        show_boxes = self.overlay_config.get("Show Debug Boxes", False)
        enabled = show_content or show_boxes
        app = self._app
        if not enabled:
            overlay = self.get_overlay_view()
            if overlay is not None:
                overlay.clear_draw(OVERLAY_PAINTER_KEY)
            if app.ok_config.get("use_overlay", False):
                app.set_overlay_setting("boxes", False)
            return False

        if not app.ok_config.get("use_overlay", False):
            app.ok_config["use_overlay"] = True
        overlay = self.get_overlay_view()
        if overlay is None:
            return False
        overlay.set_boxes_enabled(show_boxes)

        if show_content and self.in_world():
            overlay.draw(OVERLAY_PAINTER_KEY, paint_okww_status)
        else:
            overlay.clear_draw(OVERLAY_PAINTER_KEY)
        return False
