"""卦象主体匹配：整区搜索、颜色校验、去重后从左到右返回。

输入为游戏客户区 BGR 截图；hud_visible 由调用方确认。模板来自 COCO
标注的真实截图，强光圈只作为干扰，不作为计数依据。
"""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

from src.Labels import Labels


REFERENCE_SIZE = (1600, 900)
SEARCH_REGION = (680, 725, 230, 70)
MATCH_THRESHOLD = 0.65
CANDIDATE_THRESHOLD = 0.50
COLOR_THRESHOLD = 0.60
MAX_GUAXIANG = 4
ASSET_ROOT = Path(__file__).resolve().parents[2] / 'assets'
TEMPLATE_COLORS = ((Labels.douling_gua_blue, '蓝'), (Labels.douling_gua_yellow, '黄'))


@dataclass(frozen=True)
class GuaDetection:
    color: str
    box: tuple[int, int, int, int]
    score: float
    color_score: float


@dataclass
class GuaResult:
    sequence: list[str] | None
    detections: list[GuaDetection]
    region: tuple[int, int, int, int] | None
    reason: str = 'ok'


def _stroke_image(image):
    # 去除缓慢变化的背景和光晕，保留符文笔画及笔画间隙。
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32)
    return gray - cv2.GaussianBlur(gray, (0, 0), 2)


@lru_cache(maxsize=1)
def _load_templates():
    data = json.loads((ASSET_ROOT / 'coco_annotations.json').read_text(encoding='utf-8'))
    images = {item['id']: item for item in data['images']}
    categories = {item['name']: item['id'] for item in data['categories']}
    templates = []
    for label, color in TEMPLATE_COLORS:
        annotations = [a for a in data['annotations'] if a['category_id'] == categories[label]]
        if len(annotations) != 1:
            raise ValueError(f'{label}: expected one annotated template')
        annotation = annotations[0]
        source = images[annotation['image_id']]
        if (source['width'], source['height']) != REFERENCE_SIZE:
            raise ValueError(f'{label}: unexpected template reference resolution')
        path = ASSET_ROOT / source['file_name']
        frame = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError(f'{label}: unreadable template image')
        x, y, w, h = map(int, annotation['bbox'])
        patch = frame[y:y + h, x:x + w]
        if patch.shape[:2] != (h, w) or min(w, h) < 3:
            raise ValueError(f'{label}: invalid template bounding box')
        pixels = patch.astype(np.float32)
        # 白色笔画中心可能过曝；只用模板中有明显色调的像素校验颜色。
        tint_mask = (np.abs(pixels[:, :, 0] - pixels[:, :, 2]) > 30) & (pixels.max(axis=2) > 150)
        if not tint_mask.any():
            raise ValueError(f'{label}: template has no colored pixels')
        templates.append((color, _stroke_image(patch), tint_mask))
    return tuple(templates)


def _search_region(width, height):
    # 与项目 hcenter=True 的坐标方式一致：水平居中，底部 HUD 按底边锚定。
    scale = min(width / REFERENCE_SIZE[0], height / REFERENCE_SIZE[1])
    x, y, w, h = SEARCH_REGION
    return (round(width / 2 + (x - REFERENCE_SIZE[0] / 2) * scale),
            round(height - (REFERENCE_SIZE[1] - y) * scale),
            round(w * scale), round(h * scale))


def _same_gua(first, second):
    x1, y1, w1, h1 = first.box
    x2, y2, w2, h2 = second.box
    return (abs(x1 + w1 / 2 - x2 - w2 / 2) < min(w1, w2) * 0.6
            and abs(y1 + h1 / 2 - y2 - h2 / 2) < min(h1, h2) * 0.6)


def _resolve_candidates(candidates):
    selected = []
    for candidate in sorted(candidates, key=lambda item: item.score, reverse=True):
        existing = next((item for item in selected if _same_gua(item, candidate)), None)
        if existing is not None:
            if existing.color != candidate.color:
                return None, candidates, 'color_conflict'
            continue
        selected.append(candidate)
    selected.sort(key=lambda item: item.box[0] + item.box[2] / 2)
    if len(selected) > MAX_GUAXIANG:
        return None, selected, 'too_many_candidates'
    if any(item.score < MATCH_THRESHOLD or item.color_score < COLOR_THRESHOLD for item in selected):
        return None, selected, 'low_confidence'
    return [item.color for item in selected], selected, 'ok'


def recognize_guaxiang(frame, *, hud_visible):
    """识别单帧；不刷新截图、不等待、不发送输入。

    [] 表示有效 HUD 中没有匹配候选；None 表示不可用或不确定。
    hud_visible=False 时不把隐藏的 HUD 当作零卦象。
    """
    if not hud_visible:
        return GuaResult(None, [], None, 'hud_hidden')
    if (not isinstance(frame, np.ndarray) or frame.dtype != np.uint8
            or frame.ndim != 3 or frame.shape[2] != 3):
        return GuaResult(None, [], None, 'invalid_frame')
    height, width = frame.shape[:2]
    region = x, y, w, h = _search_region(width, height)
    if w < 21 or h < 27 or x < 0 or y < 0 or x + w > width or y + h > height:
        return GuaResult(None, [], region, 'invalid_frame')
    roi = cv2.resize(frame[y:y + h, x:x + w], SEARCH_REGION[2:], interpolation=cv2.INTER_LINEAR)
    try:
        templates = _load_templates()
    except (OSError, ValueError, KeyError, cv2.error):
        return GuaResult(None, [], region, 'templates_unavailable')
    strokes = _stroke_image(roi)
    candidates = []
    for color, template, tint_mask in templates:
        th, tw = template.shape
        scores = cv2.matchTemplate(strokes, template, cv2.TM_CCOEFF_NORMED)
        # 每个颜色最多检查 5 个：已足以判定超出合法数量，且循环始终有界。
        for _ in range(MAX_GUAXIANG + 1):
            _, score, _, (cx, cy) = cv2.minMaxLoc(scores)
            if not np.isfinite(score) or score < CANDIDATE_THRESHOLD:
                break
            patch = roi[cy:cy + th, cx:cx + tw].astype(np.float32)
            difference = (patch[:, :, 0] - patch[:, :, 2])[tint_mask]
            color_score = float(np.mean(difference > 12 if color == '蓝' else difference < -12))
            box = (x + round(cx * w / SEARCH_REGION[2]), y + round(cy * h / SEARCH_REGION[3]),
                   round(tw * w / SEARCH_REGION[2]), round(th * h / SEARCH_REGION[3]))
            candidates.append(GuaDetection(color, box, float(score), color_score))
            # 抑制同一符文附近的相邻匹配峰，保留不同位置的符文。
            scores[max(0, cy - th // 2):cy + th // 2 + 1,
                   max(0, cx - tw // 2):cx + tw // 2 + 1] = -1
    sequence, detections, reason = _resolve_candidates(candidates)
    return GuaResult(sequence, detections, region, reason)
