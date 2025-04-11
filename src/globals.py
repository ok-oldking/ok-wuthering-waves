import os.path
from os import path

import cv2
from PySide6.QtCore import Signal, QObject

from ok import Config, Logger, get_path_relative_to_exe
from src.OpenVinoYoloDetect import OpenVinoYoloDetect

logger = Logger.get_logger(__name__)


class Globals(QObject):

    def __init__(self, exit_event):
        super().__init__()
        self._yolo_model = None
        self.mini_map_arrow = None
        self.logged_in = False

    @property
    def yolo_model(self):
        if self._yolo_model is None:
            self._yolo_model =  OpenVinoYoloDetect(weights=get_path_relative_to_exe(os.path.join("assets","yolo", "yolov5s_320.onnx")))
        return self._yolo_model

    def yolo_detect(self, image, threshold=0.5, label=-1):
        return self.yolo_model.detect(image, threshold=threshold, label=label)



if __name__ == "__main__":
    glbs = Globals(exit_event=None)
