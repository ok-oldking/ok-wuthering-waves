import os
import random
import time
from typing import Tuple

# import onnxruntime as ort # Removed onnxruntime
from openvino import Core  # Added OpenVINO Core
import cv2
import numpy as np

from ok import Logger, Box, sort_boxes

logger = Logger.get_logger(__name__)


class OpenVinoYolo8Detect:  # Renamed class

    def __init__(self, weights='echo.onnx', model_h=640, model_w=640, iou_thres=0.45):
        """
        yolov OpenVINO inference
        dic_labels: {0: 'person', 1: 'bicycle'}
        """
        self.dic_labels = {0: 'echo'}
        self.weights = weights
        self.model_size = (model_w, model_h)
        self.iou_threshold = iou_thres
        self.openfile_name_model = weights

        # --- OpenVINO Initialization ---
        self.core = Core()
        # self.core.set_property("CPU", {"INFERENCE_NUM_THREADS": str(1)})
        device = "CPU"  # Default device, tries GPU then CPU etc.

        try:
            logger.info(f"Compiling OpenVINO model for {device}...")
            # Read and compile the ONNX model directly
            model = self.core.read_model(model=self.openfile_name_model)
            self.compiled_model = self.core.compile_model(model=model, device_name=device,
            config={"PERFORMANCE_HINT": "LATENCY"},)
            # Get input/output names (usually one input, one output for YOLOv5)
            self.input_layer = self.compiled_model.input(0)
            self.output_layer = self.compiled_model.output(0)
            self.input_width = self.input_layer.shape[2]
            self.input_height = self.input_layer.shape[3]
            logger.info(f"OpenVINO model compiled successfully for {self.compiled_model} {self.input_width}x{self.input_height}.")
        except Exception as e:
            logger.error(f"Error initializing OpenVINO: {e}")
            raise RuntimeError("Could not initialize OpenVINO model") from e
        # --- End OpenVINO Initialization ---

    def letterbox(self, img: np.ndarray, new_shape: Tuple[int, int] = (640, 640)) -> Tuple[np.ndarray, Tuple[int, int]]:
        """
        Resize and reshape images while maintaining aspect ratio by adding padding.

        Args:
            img (np.ndarray): Input image to be resized.
            new_shape (Tuple[int, int]): Target shape (height, width) for the image.

        Returns:
            (np.ndarray): Resized and padded image.
            (Tuple[int, int]): Padding values (top, left) applied to the image.
        """
        shape = img.shape[:2]  # current shape [height, width]

        # Scale ratio (new / old)
        r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])

        # Compute padding
        new_unpad = int(round(shape[1] * r)), int(round(shape[0] * r))
        dw, dh = (new_shape[1] - new_unpad[0]) / 2, (new_shape[0] - new_unpad[1]) / 2  # wh padding

        if shape[::-1] != new_unpad:  # resize
            img = cv2.resize(img, new_unpad, interpolation=cv2.INTER_LINEAR)
        top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
        left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
        img = cv2.copyMakeBorder(img, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(114, 114, 114))

        return img, (top, left)

    def _preprocess(self, img):
        """图像预处理（保持宽高比的缩放填充） - unchanged"""
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        img, pad = self.letterbox(img, (self.input_width, self.input_height))

        # Normalize the image data by dividing it by 255.0
        image_data = np.array(img) / 255.0

        # Transpose the image to have the channel dimension as the first dimension
        image_data = np.transpose(image_data, (2, 0, 1))  # Channel first

        # Expand the dimensions of the image data to match the expected input shape
        image_data = np.expand_dims(image_data, axis=0).astype(np.float32)

        # Return the preprocessed image data
        return image_data, pad


    def _postprocess(self,  outputs, padding, orig_shape, confidence_threshold, label):
        """
        Perform post-processing on the model's output to extract and visualize detections.

        This method processes the raw model output to extract bounding boxes, scores, and class IDs.
        It applies non-maximum suppression to filter overlapping detections and draws the results on the input image.

        Args:
            input_image (np.ndarray): The input image.
            output (List[np.ndarray]): The output arrays from the model.
            pad (Tuple[int, int]): Padding values (top, left) used during letterboxing.

        Returns:
            (np.ndarray): The input image with detections drawn on it.
        """
        # Transpose and squeeze the output to match the expected shape
        outputs = np.transpose(np.squeeze(outputs[0]))

        # Get the number of rows in the outputs array
        rows = outputs.shape[0]

        # Lists to store the bounding boxes, scores, and class IDs of the detections
        boxes = []
        scores = []
        class_ids = []

        # Calculate the scaling factors for the bounding box coordinates
        gain = min(orig_shape[0] / orig_shape[0], self.input_width / orig_shape[1])

        outputs[:, 0] -= padding[1]
        outputs[:, 1] -= padding[0]

        # Iterate over each row in the outputs array
        for i in range(rows):
            # Extract the class scores from the current row
            classes_scores = outputs[i][4:]

            # Find the maximum score among the class scores
            max_score = np.amax(classes_scores)
            class_id = np.argmax(classes_scores)
            # If the maximum score is above the confidence threshold
            if max_score >= confidence_threshold and (label==-1 or label==class_id):
                # Get the class ID with the highest score


                # Extract the bounding box coordinates from the current row
                x, y, w, h = outputs[i][0], outputs[i][1], outputs[i][2], outputs[i][3]

                # Calculate the scaled coordinates of the bounding box
                left = int((x - w / 2) / gain)
                top = int((y - h / 2) / gain)
                width = int(w / gain)
                height = int(h / gain)

                # Add the class ID, score, and box coordinates to the respective lists
                class_ids.append(class_id)
                scores.append(max_score)
                boxes.append([left, top, width, height])

        # Apply non-maximum suppression to filter out overlapping bounding boxes
        indices = cv2.dnn.NMSBoxes(boxes, scores, confidence_threshold, self.iou_threshold)

        # Iterate over the selected indices after non-maximum suppression
        results = []
        for i in indices:
            # Get the box, score, and class ID corresponding to the index
            box = boxes[i]
            box_obj = Box(box[0], box[1], box[2], box[3])  # Use Box class if available
            box_obj.name = self.dic_labels.get(int(class_ids[i]), 'unknown')
            box_obj.confidence = scores[i]
            results.append(box_obj)
            # Draw the detection on the input image
            # self.draw_detections(input_image, box, score, class_id)
        return results

    # 推理
    def detect(self, image, threshold=0.5, label=-1):
        '''
        预测
        '''
        try:
            h, w = image.shape[:2]
            img_data, pad = self._preprocess(image)
            # input_tensor = np.expand_dims(img_data, axis=0)  # Add batch dimension

            # --- OpenVINO Inference ---
            # Input is a dictionary {input_layer_name: data}
            # Output is a dictionary {output_layer_name: data}
            results = self.compiled_model({self.input_layer: img_data})
            # Extract the output tensor using the output layer obtained during init
            outputs = results[self.output_layer]
            # --- End OpenVINO Inference ---
            boxes = self._postprocess(outputs, pad, (h, w), threshold, label)

            return sort_boxes(boxes)
        except Exception as e:
            logger.error(f'OpenVINO yolo detect error:', e)  # Added exc_info
            return []


# --- Main execution part needs to be updated to use the new class ---
if __name__ == '__main__':
    # Ensure ok module and Box class are available, or provide stubs
    class MockLogger:
        def get_logger(self, name): return self

        def debug(self, msg, *args): print(f"DEBUG: {msg}")

        def info(self, msg, *args): print(f"INFO: {msg}")

        def warning(self, msg, *args): print(f"WARN: {msg}")

        def error(self, msg, *args, **kwargs): print(f"ERROR: {msg}")


    class MockOk:
        class og: use_dml = False  # Simulate ok.og.use_dml if needed

        Logger = MockLogger()


    if 'ok' not in globals():  # Define stubs if 'ok' module is not present
        ok = MockOk()
        Logger = ok.Logger


        class Box:
            def __init__(self, x, y, w, h):
                self.x, self.y, self.w, self.h = x, y, w, h
                self.name = "unknown"
                self.confidence = 0.0

            def __repr__(self):
                return f"Box(x={self.x}, y={self.y}, w={self.w}, h={self.h}, name='{self.name}', conf={self.confidence:.2f})"

    image_path = "tests/images/echo.png"
    weights = "assets/echo_model/best.xml"  # OpenVINO reads ONNX directly
    model_h = 640
    model_w = 640


    # NOTE: You need a real ONNX model at the 'weights' path for inference to work.
    if not os.path.exists(weights):
        print(f"ERROR: Model file not found at {weights}. Inference will fail.")
        print("Please download or place yolov5s_320.onnx in assets/yolo/")
        # Create a dummy file to avoid immediate crash during init, but it won't work
        # with open(weights, 'w') as f: f.write('') # This won't be a valid model

    # Use the new OpenVINO class
    yolov = OpenVinoYolo8Detect(weights=weights, model_w=model_w, model_h=model_h)

    # Test 1
    big_img = cv2.imdecode(np.fromfile(file=image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if big_img is None:
        print(f"Error loading image: {image_path}")
    else:
        start_time = time.time()
        for i in range(100):
            res_loc = yolov.detect(big_img, label=0)  # label=12 -> '声骸'
        end_time = time.time()
        print(f"Detection 1 time: {(end_time - start_time) * 1000:.2f} ms")

    # Test 2
    img2 = cv2.imread("tests/images/echo2.png")
    if img2 is None:
        print("Error loading image: tests/images/echo2.png")
    else:
        start_time = time.time()
        for i in range(100):
            res_loc = yolov.detect(img2, label=0)
        end_time = time.time()
        print(f"Detection 2 time: {(end_time - start_time) * 1000:.2f} ms")

