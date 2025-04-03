import os
import random
import time
import onnxruntime as ort
import cv2
import numpy as np

import ok
from ok import Logger, Box

logger = Logger.get_logger(__name__)

class LanRenOnnxYolov():

    def __init__(self, weights='yolov5s_320.onnx', model_h=320, model_w=320, conf_thres=0.5, iou_thres=0.45):
        """
        yolov onnx推理
        providers: []   ['TensorrtExecutionProvider', 'CUDAExecutionProvider', 'CPUExecutionProvider']
        dic_labels: {0: 'person', 1: 'bicycle'}
        """
        self.dic_labels = {0: '玩家', 1: '副本开关', 2: '怪物', 3: '关闭', 4: '重新挑战', 5: 'F交互', 6: '滑翔翼', 7: '矿石', 8: '确定', 9: '取消', 10: '在水面', 11: '宠物', 12: '声骸', 13: '退出副本', 14: '在爬墙', 15: '无音区开关', 16: '血条', 17: '点击', 18: '复苏'}
        providers = []
        if ok.og.use_dml:
            providers.append('DmlExecutionProvider')
        providers.append('CPUExecutionProvider')
        self.weights=weights
        self.model_size = (model_w, model_h)
        self.conf_threshold = conf_thres
        self.iou_threshold = iou_thres
        self.openfile_name_model = weights  # 模型名称


        try:
            self.session = ort.InferenceSession(self.openfile_name_model,
                                            providers=providers)  # 在树莓派上这里不需指定推理设备
            logger.debug("yolo use DmlExecutionProvider:")
        except:
            logger.error("CUDA加速失败,使用CPU推理")
            providers=['CPUExecutionProvider']
            self.session = ort.InferenceSession(self.openfile_name_model,
                                            providers=providers)  # 在树莓派上这里不需指定推理设备

    def _preprocess(self, image):
        """图像预处理（保持宽高比的缩放填充）"""
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
        padded = padded[:, :, ::-1].transpose(2, 0, 1)
        padded = np.ascontiguousarray(padded, dtype=np.float32) / 255.0
        return (padded, scale, (left, top))

    def _postprocess(self, outputs, scale, padding, orig_shape):
        """后处理：转换坐标并应用NMS"""
        outputs = outputs[0]
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
        indices = cv2.dnn.NMSBoxes(boxes.tolist(), scores.tolist(), self.conf_threshold, self.iou_threshold)
        return [(boxes[i], scores[i], class_ids[i]) for i in indices]

    # 推理
    def detect(self, image, threshold=0.5, label=-1):
        '''
        预测
        '''
        # 图像预处理
        try:
            # orig_image = image.copy()
            h, w = image.shape[:2]
            preprocessed, scale, padding = self._preprocess(image)
            input_tensor = np.expand_dims(preprocessed, axis=0)
            outputs = self.session.run(None, {self.session.get_inputs()[0].name: input_tensor})[0]
            detections = self._postprocess(outputs, scale, padding, (h, w))
            results = []
            for box, score, class_id in detections:
                x1, y1, x2, y2 = map(int, box)
                #画框框
                if score < threshold:
                    continue
                if label >= 0 and label != int(class_id):
                    continue
                # 数据保存
                box = Box(x1,y1, x2 - x1, y2 - y1)
                box.name = self.dic_labels.get(int(class_id),'unknown')
                box.confidence = score
                results.append(box)
            logger.debug(f'results {results}')
            return results
        except Exception as e:
            logger.error('yolo detect error', e)
            return []


if __name__ == '__main__':
    image_path="tests/images/echo.png"
    weights="assets/yolo/yolov5s_320.onnx"
    model_h=320
    model_w=320
    big_img = cv2.imdecode(np.fromfile(file=image_path, dtype=np.uint8), cv2.IMREAD_COLOR)  # 加载大图

    yolov=LanRenOnnxYolov(weights=weights,model_w=model_w,model_h=model_h)
    old_time=time.time()
    res_loc =yolov.detect(big_img, label=12)
    print((time.time()-old_time)*1000,res_loc[0])

    res_loc = yolov.detect(cv2.imread("tests/images/echo2.png"), label=12)
    print((time.time() - old_time) * 1000, res_loc[0])


