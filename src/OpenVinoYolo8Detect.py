from typing import Tuple

from openvino import Core
import cv2
import numpy as np

from ok import Logger, Box, sort_boxes

logger = Logger.get_logger(__name__)


class OpenVinoYolo8Detect:

    def __init__(self, weights='echo.onnx', model_h=640, model_w=640, iou_thres=0.45):
        self.dic_labels = {0: 'echo'}
        self.weights = weights
        self.model_size = (model_w, model_h)
        self.iou_threshold = iou_thres
        self.openfile_name_model = weights

        self.core = Core()

        try:
            model = self.core.read_model(model=self.openfile_name_model)

            device_used = "CPU"
            is_compiled = False

            if "NPU" in self.core.available_devices:
                try:
                    self.compiled_model = self.core.compile_model(
                        model=model,
                        device_name="NPU",
                        config={"PERFORMANCE_HINT": "LATENCY"}
                    )
                    device_used = "NPU"
                    is_compiled = True
                except Exception:
                    pass

            if not is_compiled:
                self.compiled_model = self.core.compile_model(
                    model=model,
                    device_name="CPU",
                    config={"PERFORMANCE_HINT": "LATENCY"}
                )

            self.input_layer = self.compiled_model.input(0)
            self.output_layer = self.compiled_model.output(0)
            self.input_width = self.input_layer.shape[2]
            self.input_height = self.input_layer.shape[3]
            logger.info(
                f"OpenVINO model compiled successfully for {device_used} {self.input_width}x{self.input_height}."
            )
        except Exception as e:
            logger.error(f"Error initializing OpenVINO: {e}")
            raise RuntimeError("Could not initialize OpenVINO model") from e

    def letterbox(self, img: np.ndarray, new_shape: Tuple[int, int] = (640, 640)) -> Tuple[np.ndarray, Tuple[int, int]]:
        shape = img.shape[:2]

        r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])

        new_unpad = int(round(shape[1] * r)), int(round(shape[0] * r))
        dw, dh = (new_shape[1] - new_unpad[0]) / 2, (new_shape[0] - new_unpad[1]) / 2

        if shape[::-1] != new_unpad:
            img = cv2.resize(img, new_unpad, interpolation=cv2.INTER_LINEAR)
        top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
        left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
        img = cv2.copyMakeBorder(img, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(114, 114, 114))

        return img, (top, left)

    def _preprocess(self, img):
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        img, pad = self.letterbox(img, (self.input_width, self.input_height))

        image_data = np.array(img, dtype=np.float32) / 255.0
        image_data = np.transpose(image_data, (2, 0, 1))
        image_data = np.expand_dims(image_data, axis=0)

        return image_data, pad

    def _postprocess(self, outputs, padding, orig_shape, confidence_threshold, label):
        outputs = np.transpose(np.squeeze(outputs[0]))

        gain = min(self.input_height / orig_shape[0], self.input_width / orig_shape[1])

        outputs[:, 0] -= padding[1]
        outputs[:, 1] -= padding[0]

        scores_data = outputs[:, 4:]
        max_scores = np.max(scores_data, axis=1)
        class_ids = np.argmax(scores_data, axis=1)

        mask = max_scores >= confidence_threshold
        if label != -1:
            mask &= (class_ids == label)

        filtered_boxes = outputs[mask, :4]
        filtered_scores = max_scores[mask]
        filtered_class_ids = class_ids[mask]

        if len(filtered_boxes) == 0:
            return []

        left = (filtered_boxes[:, 0] - filtered_boxes[:, 2] / 2) / gain
        top = (filtered_boxes[:, 1] - filtered_boxes[:, 3] / 2) / gain
        width = filtered_boxes[:, 2] / gain
        height = filtered_boxes[:, 3] / gain

        boxes = np.column_stack((left, top, width, height)).astype(int).tolist()
        scores = filtered_scores.tolist()
        class_ids_list = filtered_class_ids.tolist()

        indices = cv2.dnn.NMSBoxes(boxes, scores, confidence_threshold, self.iou_threshold)

        results = []
        if len(indices) > 0:
            for i in np.array(indices).flatten():
                box = boxes[i]
                box_obj = Box(box[0], box[1], box[2], box[3])
                box_obj.name = self.dic_labels.get(int(class_ids_list[i]), 'unknown')
                box_obj.confidence = scores[i]
                results.append(box_obj)

        return results

    def detect(self, image, threshold=0.5, label=-1):
        try:
            h, w = image.shape[:2]
            img_data, pad = self._preprocess(image)

            results = self.compiled_model({self.input_layer: img_data})
            outputs = results[self.output_layer]

            boxes = self._postprocess(outputs, pad, (h, w), threshold, label)

            return sort_boxes(boxes)
        except Exception as e:
            logger.error(f'OpenVINO yolo detect error: {e}')
            return
