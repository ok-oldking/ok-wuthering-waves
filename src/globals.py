import os.path
import time
from os import path
from pathlib import Path

import cv2
from PySide6.QtCore import Signal, QObject, QTimer, Qt
from qfluentwidgets import FluentIcon, PushButton

from ok import Config, Logger, get_path_relative_to_exe, og

logger = Logger.get_logger(__name__)


class Globals(QObject):

    def __init__(self, exit_event):
        super().__init__()
        self._yolo_model = None
        self._position_detector = None
        self.mini_map_arrow = None
        self.logged_in = False
        self._continuous_capture_timer = None
        self._continuous_capture_count = 0

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

    @property
    def position_detector(self):
        if self._position_detector is None:
            from src.utils.positionDetector import PositionDetector
            logger.info("Initializing PositionDetector")
            self._position_detector = PositionDetector()
        return self._position_detector

    def on_show_main_window(self, main_window):
        try:
            start_tab = main_window.start_tab
            start_card = start_tab.start_card
            layout = start_card.hBoxLayout
            capture_button = start_card.capture_button

            self._continuous_capture_button = PushButton(FluentIcon.VIDEO, self.tr("Continuous Capture"))
            self._continuous_capture_button.setCheckable(True)
            self._continuous_capture_button.clicked.connect(self._toggle_continuous_capture)

            index = layout.indexOf(capture_button)
            layout.insertWidget(index + 1, self._continuous_capture_button, 0, Qt.AlignRight)
            layout.insertSpacing(index + 2, 6)

            self._continuous_capture_timer = QTimer()
            self._continuous_capture_timer.timeout.connect(self._continuous_capture_frame)

            logger.info("Continuous capture button added to StartCard")
        except Exception as e:
            logger.error(f"Failed to add continuous capture button: {e}")

    def _toggle_continuous_capture(self, checked):
        if checked:
            self._continuous_capture_count = 0
            self._continuous_capture_timer.start(2000)
            self._continuous_capture_button.setText(self.tr("Stop Capture"))
            logger.info("Continuous capture started")
        else:
            self._continuous_capture_timer.stop()
            self._continuous_capture_button.setText(self.tr("Continuous Capture"))
            logger.info(f"Continuous capture stopped, total frames: {self._continuous_capture_count}")

    def _continuous_capture_frame(self):
        try:
            if og.device_manager.capture_method is None:
                logger.warning("No capture method available, stopping continuous capture")
                self._continuous_capture_button.setChecked(False)
                self._toggle_continuous_capture(False)
                return

            frame = og.device_manager.capture_method.get_frame()
            if frame is None:
                logger.warning("Failed to capture frame")
                return

            screenshots_folder = Path(og.config.get('screenshots_folder', 'screenshots'))
            screenshots_folder.mkdir(parents=True, exist_ok=True)

            timestamp = int(time.time() * 1000)
            filename = f"continuous_{timestamp}.png"
            filepath = screenshots_folder / filename

            cv2.imwrite(str(filepath), frame)
            self._continuous_capture_count += 1

            if self._continuous_capture_count % 10 == 0:
                logger.debug(f"Continuous capture: {self._continuous_capture_count} frames saved")
        except Exception as e:
            logger.error(f"Error in continuous capture: {e}")


if __name__ == "__main__":
    glbs = Globals(exit_event=None)
