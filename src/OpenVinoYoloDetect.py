import os
import random
import time
# import onnxruntime as ort # Removed onnxruntime
from openvino import Core # Added OpenVINO Core
import cv2
import numpy as np


from ok import Logger, Box

logger = Logger.get_logger(__name__)

class OpenVinoYoloDetect: # Renamed class

    def __init__(self, weights='yolov5s_320.onnx', model_h=320, model_w=320, conf_thres=0.5, iou_thres=0.45):
        """
        yolov OpenVINO inference
        dic_labels: {0: 'person', 1: 'bicycle'}
        """
        self.dic_labels = {0: '玩家', 1: '副本开关', 2: '怪物', 3: '关闭', 4: '重新挑战', 5: 'F交互', 6: '滑翔翼', 7: '矿石', 8: '确定', 9: '取消', 10: '在水面', 11: '宠物', 12: '声骸', 13: '退出副本', 14: '在爬墙', 15: '无音区开关', 16: '血条', 17: '点击', 18: '复苏'}
        self.weights = weights
        self.model_size = (model_w, model_h)
        self.conf_threshold = conf_thres
        self.iou_threshold = iou_thres
        self.openfile_name_model = weights

        # --- OpenVINO Initialization ---
        self.core = Core()
        self.core.set_property("CPU", {"INFERENCE_NUM_THREADS": str(1)})
        device = "AUTO" # Default device, tries GPU then CPU etc.

        try:
            logger.info(f"Compiling OpenVINO model for {device}...")
            # Read and compile the ONNX model directly
            model = self.core.read_model(model=self.openfile_name_model)
            self.compiled_model = self.core.compile_model(model=model, device_name=device)
            # Get input/output names (usually one input, one output for YOLOv5)
            self.input_layer = self.compiled_model.input(0)
            self.output_layer = self.compiled_model.output(0)
            logger.info(f"OpenVINO model compiled successfully for {self.compiled_model}")
        except Exception as e:
             logger.error(f"Error initializing OpenVINO: {e}")
             raise RuntimeError("Could not initialize OpenVINO model") from e
        # --- End OpenVINO Initialization ---


    def _preprocess(self, image):
        """图像预处理（保持宽高比的缩放填充） - unchanged"""
        if image.shape[2] == 4:
            image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
        h, w = image.shape[:2]
        target_w, target_h = self.model_size
        scale = min(target_w / w, target_h / h)
        new_w = int(w * scale)
        new_h = int(h * scale)
        resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        dw = target_w - new_w
        dh = target_h - new_h
        top = dh // 2
        bottom = dh - top
        left = dw // 2
        right = dw - left
        padded = cv2.copyMakeBorder(resized, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(114, 114, 114))
        # Ensure layout is BGR -> RGB, HWC -> CHW
        padded = padded[:, :, ::-1].transpose(2, 0, 1)
        padded = np.ascontiguousarray(padded, dtype=np.float32) / 255.0
        return (padded, scale, (left, top))

    def _postprocess(self, outputs, scale, padding, orig_shape):
        """后处理：转换坐标并应用NMS - unchanged"""
        # The output from OpenVINO might be directly the tensor,
        # unlike ORT which returned a list.
        # Assuming 'outputs' here is the direct output tensor with shape (1, N, 85) or similar
        outputs = outputs[0] # Get rid of batch dimension if present
        scores = outputs[:, 4] * outputs[:, 5:].max(axis=1)
        valid_mask = scores > self.conf_threshold
        outputs = outputs[valid_mask]
        if outputs.size == 0:
            return []
        cxcy = outputs[:, 0:2]
        wh = outputs[:, 2:4]
        x1y1 = cxcy - wh / 2
        x2y2 = cxcy + wh / 2
        left_pad, top_pad = padding
        x1y1 -= np.array([left_pad, top_pad])
        x2y2 -= np.array([left_pad, top_pad])
        boxes = np.concatenate((x1y1, x2y2), axis=1) / scale
        boxes[:, [0, 2]] = np.clip(boxes[:, [0, 2]], 0, orig_shape[1])
        boxes[:, [1, 3]] = np.clip(boxes[:, [1, 3]], 0, orig_shape[0])
        scores = scores[valid_mask]
        class_ids = np.argmax(outputs[:, 5:], axis=1)

        # Use OpenCV NMS
        try:
            indices = cv2.dnn.NMSBoxes(boxes.tolist(), scores.tolist(), self.conf_threshold, self.iou_threshold)
            # Flatten indices if it's nested [[0], [1]] -> [0, 1]
            if isinstance(indices, np.ndarray):
                indices = indices.flatten()
        except Exception as e:
             logger.warning(f"NMS failed: {e}. Returning raw detections.")
             # Fallback: return all valid boxes before NMS if NMS fails
             return [(boxes[i], scores[i], class_ids[i]) for i in range(len(boxes))]

        return [(boxes[i], scores[i], class_ids[i]) for i in indices]

    # 推理
    def detect(self, image, threshold=0.5, label=-1):
        '''
        预测
        '''
        try:
            h, w = image.shape[:2]
            preprocessed, scale, padding = self._preprocess(image)
            input_tensor = np.expand_dims(preprocessed, axis=0) # Add batch dimension

            # --- OpenVINO Inference ---
            # Input is a dictionary {input_layer_name: data}
            # Output is a dictionary {output_layer_name: data}
            results = self.compiled_model({self.input_layer: input_tensor})
            # Extract the output tensor using the output layer obtained during init
            outputs = results[self.output_layer]
            # --- End OpenVINO Inference ---

            detections = self._postprocess(outputs, scale, padding, (h, w))

            results = []
            for box, score, class_id in detections:
                if score < threshold:
                    continue
                if label >= 0 and label != int(class_id):
                    continue

                x1, y1, x2, y2 = map(int, box)
                box_obj = Box(x1, y1, x2 - x1, y2 - y1) # Use Box class if available
                box_obj.name = self.dic_labels.get(int(class_id), 'unknown')
                box_obj.confidence = score
                results.append(box_obj)

            # logger.debug(f'results {results}') # Keep logging if needed
            return results
        except Exception as e:
            logger.error(f'OpenVINO yolo detect error:', e) # Added exc_info
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
        class og: use_dml = False # Simulate ok.og.use_dml if needed
        Logger = MockLogger()

    if 'ok' not in globals(): # Define stubs if 'ok' module is not present
        ok = MockOk()
        Logger = ok.Logger
        class Box:
            def __init__(self, x, y, w, h):
                self.x, self.y, self.w, self.h = x, y, w, h
                self.name = "unknown"
                self.confidence = 0.0
            def __repr__(self):
                return f"Box(x={self.x}, y={self.y}, w={self.w}, h={self.h}, name='{self.name}', conf={self.confidence:.2f})"

    image_path="tests/images/echo.png"
    weights="assets/yolo/yolov5s_320.onnx" # OpenVINO reads ONNX directly
    model_h=320
    model_w=320

    # Create dummy files if they don't exist for testing
    if not os.path.exists("tests/images"): os.makedirs("tests/images")
    if not os.path.exists("assets/yolo"): os.makedirs("assets/yolo")
    if not os.path.exists(image_path):
        dummy_img = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.imwrite(image_path, dummy_img)
        print(f"Created dummy image: {image_path}")
    if not os.path.exists("tests/images/echo2.png"):
        dummy_img2 = np.zeros((500, 700, 3), dtype=np.uint8)
        cv2.imwrite("tests/images/echo2.png", dummy_img2)
        print("Created dummy image: tests/images/echo2.png")
    # NOTE: You need a real ONNX model at the 'weights' path for inference to work.
    if not os.path.exists(weights):
         print(f"ERROR: Model file not found at {weights}. Inference will fail.")
         print("Please download or place yolov5s_320.onnx in assets/yolo/")
         # Create a dummy file to avoid immediate crash during init, but it won't work
         # with open(weights, 'w') as f: f.write('') # This won't be a valid model

    # Use the new OpenVINO class
    yolov = OpenVinoYoloDetect(weights=weights, model_w=model_w, model_h=model_h)

    # Test 1
    big_img = cv2.imdecode(np.fromfile(file=image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if big_img is None:
        print(f"Error loading image: {image_path}")
    else:
        start_time = time.time()
        res_loc = yolov.detect(big_img, label=12) # label=12 -> '声骸'
        end_time = time.time()
        print(f"Detection 1 time: {(end_time - start_time) * 1000:.2f} ms")
        if res_loc:
            print(res_loc[0])
        else:
            print("No detections for label 12 in first image.")

    # Test 2
    img2 = cv2.imread("tests/images/echo2.png")
    if img2 is None:
         print("Error loading image: tests/images/echo2.png")
    else:
        start_time = time.time()
        res_loc = yolov.detect(img2, label=12)
        end_time = time.time()
        print(f"Detection 2 time: {(end_time - start_time) * 1000:.2f} ms")
        if res_loc:
            print(res_loc[0])
        else:
            print("No detections for label 12 in second image.")
