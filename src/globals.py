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
        communicate.window.connect(self._update_game_overlay)

    @staticmethod
    def _update_game_overlay(visible, *_args):
        """Draw the development marker as soon as the game window is visible."""
        Globals._game_window_visible = bool(visible)
        Globals._apply_game_overlay()

    @classmethod
    def apply_overlay_setting_change(cls, key, value):
        """Apply a Settings-page switch immediately, before Config persists it."""
        cls._apply_game_overlay({key: value})

    @classmethod
    def _apply_game_overlay(cls, pending_changes=None):
        app = getattr(og, "app", None)
        global_config = getattr(og, "global_config", None)
        if app is None or global_config is None:
            return
        overlay_config = dict(global_config.get_config("Development Overlay"))
        if pending_changes:
            overlay_config.update(pending_changes)
        show_content = overlay_config.get("Show Custom Overlay Content", True)
        show_boxes = overlay_config.get("Show Debug Boxes", False)
        overlay = app.get_overlay_view()
        if overlay is None:
            return
        overlay.set_boxes_enabled(show_boxes)
        if cls._game_window_visible and show_content:
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
