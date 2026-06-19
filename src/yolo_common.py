import cv2
import numpy as np

from ok import Box


def postprocess(outputs, padding, gain, confidence_threshold, label, iou_threshold, dic_labels):
    """Vectorized YOLOv8 post-processing shared by the ONNX and OpenVINO backends.

    The backends only differ in how ``gain`` is computed (different attributes and,
    historically, a different width/height ordering), so each backend computes its
    own ``gain`` and passes it in here; the candidate filtering, box scaling and NMS
    are identical and live here to avoid duplication.

    Args:
        outputs: raw model output; ``outputs[0]`` is the (1, 4+num_classes, anchors)
            tensor (a list element for ONNX Runtime, a batched ndarray for OpenVINO).
        padding: (pad_top, pad_left) from the letterbox step.
        gain: letterbox scale factor (model_size / original_size), computed by caller.
        confidence_threshold: minimum class score to keep a detection.
        label: keep only this class id, or -1 for all classes.
        iou_threshold: NMS IoU threshold.
        dic_labels: {class_id: name} used to name the returned boxes.

    Returns:
        list[Box]: detected boxes in original-image coordinates (may be empty).
    """
    outputs = np.transpose(np.squeeze(outputs[0]))

    # Adjust x/y centers for the letterbox padding.
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

    indices = cv2.dnn.NMSBoxes(boxes, scores, confidence_threshold, iou_threshold)

    results = []
    if len(indices) > 0:
        for i in np.array(indices).flatten():
            box = boxes[i]
            box_obj = Box(box[0], box[1], box[2], box[3])
            box_obj.name = dic_labels.get(int(class_ids_list[i]), 'unknown')
            box_obj.confidence = scores[i]
            results.append(box_obj)
    return results
