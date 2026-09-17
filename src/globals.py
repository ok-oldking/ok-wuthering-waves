import os.path

import cv2

from ok import Config, Logger, get_path_relative_to_exe, og
from ok.core.events import communicate
from src.gui.OverlayStatus import paint_okww_status

logger = Logger.get_logger(__name__)


class Globals:
    _game_window_visible = False

    def __init__(self, exit_event):
        self._yolo_model = None
        self.mini_map_arrow = None
        self.logged_in = False
        # get_overlay_view() connects the framework's foreground-only handler
        # first.  Our handler runs afterwards and restores visibility while the
        # game window still exists, so annotations remain inspectable when the
        # user switches to another application.
        app = getattr(og, "app", None)
        if app is not None:
            app.get_overlay_view()
        communicate.window.connect(self._update_game_overlay)

    def on_show_main_window(self, main_window):
        """Upgrade the template dropdown to an editable, searchable selector."""
        from src.gui.SearchableTemplateDropdown import install_searchable_template_dropdown
        install_searchable_template_dropdown(main_window)

    @staticmethod
    def _update_game_overlay(visible, *geometry):
        """Keep the Echo overlay visible while the game window still exists."""
        device_manager = getattr(og, "device_manager", None)
        hwnd_window = getattr(device_manager, "hwnd_window", None)
        game_exists = bool(getattr(hwnd_window, "exists", visible))
        has_geometry = len(geometry) < 6 or bool(geometry[4] and geometry[5])
        Globals._game_window_visible = game_exists and has_geometry

        app = getattr(og, "app", None)
        overlay = app.get_overlay_view() if app is not None else None
        if overlay is not None and geometry:
            overlay.update_overlay(Globals._game_window_visible, *geometry)
        Globals._apply_game_overlay()

    @classmethod
    def apply_echo_score_setting_change(cls, key, value):
        """Apply switches from the Echo Score tab immediately."""
        if key == "Show Debug Boxes":
            cls._apply_game_overlay({key: value})
            return
        if key != "显示主副词条框体" or value:
            return
        app = getattr(og, "app", None)
        if app is None:
            return
        overlay = app.get_overlay_view()
        if overlay is not None:
            from src.gui.EchoStatOverlay import ECHO_STAT_PAINTER_KEY
            overlay.clear_draw(ECHO_STAT_PAINTER_KEY)

    @classmethod
    def _apply_game_overlay(cls, pending_changes=None):
        app = getattr(og, "app", None)
        global_config = getattr(og, "global_config", None)
        if app is None or global_config is None:
            return
        overlay_config = dict(global_config.get_config("声骸评分"))
        if pending_changes:
            overlay_config.update(pending_changes)
        show_boxes = overlay_config.get("Show Debug Boxes", False)
        overlay = app.get_overlay_view()
        if overlay is None:
            return
        overlay.set_boxes_enabled(show_boxes)
        if cls._game_window_visible:
            overlay.draw("okww-status", paint_okww_status)
        else:
            overlay.clear_draw("okww-status")

    @property
    def yolo_model(self):
        if self._yolo_model is None:
            weights = get_path_relative_to_exe(os.path.join("assets", "echo_model", "echo.onnx"))
            if og.config.get("ocr").get("params").get("use_openvino"):
                logger.info("yolo_model Using OpenVinoYolo8Detect")
                from src.OpenVinoYolo8Detect import OpenVinoYolo8Detect
                self._yolo_model = OpenVinoYolo8Detect(
                    weights=weights)
            else:
                logger.info("yolo_model Using OnnxYolo8Detect")
                from src.OnnxYolo8Detect import OnnxYolo8Detect
                self._yolo_model = OnnxYolo8Detect(
                    weights=weights)
        return self._yolo_model

    def yolo_detect(self, image, threshold=0.6, label=-1):
        return self.yolo_model.detect(image, threshold=threshold, label=label)


if __name__ == "__main__":
    glbs = Globals(exit_event=None)
