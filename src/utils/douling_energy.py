"""卜灵少阳/少阴能量条的独立单帧识别；红框标注不参与识别。

输入为游戏客户区 BGR 截图，调用方确认当前显示卜灵 HUD。
左右能量各只有有/无两种情况，不计算能量百分比。
"""

from dataclasses import dataclass
from typing import Literal

import numpy as np


REFERENCE_SIZE = (1920, 1080)
SHAOYANG_REGION = (813, 980, 110, 27)
SHAOYIN_REGION = (978, 980, 112, 27)
BRIGHTNESS_THRESHOLD = 130
COLOR_FRACTION_THRESHOLD = 0.15
COLUMN_PIXEL_THRESHOLD = 0.10
COLOR_COLUMNS_THRESHOLD = 0.60
VISIBLE_FRACTION_THRESHOLD = 0.03
VISIBLE_COLUMNS_THRESHOLD = 0.30

EnergyState = Literal['none', 'shaoyang', 'shaoyin', 'both']


@dataclass(frozen=True)
class EnergyResult:
    state: EnergyState | None
    reason: str = 'ok'


def _energy_regions(width, height):
    scale = min(width / REFERENCE_SIZE[0], height / REFERENCE_SIZE[1])
    regions = []
    for x, y, w, h in (SHAOYANG_REGION, SHAOYIN_REGION):
        regions.append((round(width / 2 + (x - REFERENCE_SIZE[0] / 2) * scale),
                        round(height - (REFERENCE_SIZE[1] - y) * scale),
                        round(w * scale), round(h * scale)))
    return tuple(regions)


def _color_present(mask):
    # 能量覆盖整条；要求横向分布，排除局部光点。
    return (float(mask.mean()) >= COLOR_FRACTION_THRESHOLD
            and float((mask.mean(axis=0) > COLUMN_PIXEL_THRESHOLD).mean()) >= COLOR_COLUMNS_THRESHOLD)


def recognize_energy(frame, *, hud_visible):
    """返回 none/shaoyang/shaoyin/both；失败返回 state=None 和原因。

    hud_visible 必须由调用方确认卜灵 HUD 可见，不能只判断队伍 UI。
    不刷新截图、不等待、不发送输入、不记录日志，也不修改传入帧。
    颜色占比仅用于二值判断，不代表能量数值。
    """
    if not hud_visible:
        return EnergyResult(None, 'hud_hidden')
    if (not isinstance(frame, np.ndarray) or frame.dtype != np.uint8
            or frame.ndim != 3 or frame.shape[2] != 3):
        return EnergyResult(None, 'invalid_frame')
    height, width = frame.shape[:2]
    regions = _energy_regions(width, height)
    present = []
    for index, (x, y, w, h) in enumerate(regions):
        if w < 20 or h < 6 or x < 0 or y < 0 or x + w > width or y + h > height:
            return EnergyResult(None, 'invalid_frame')
        # 使用有符号通道差，避免 uint8 减法溢出；只复制局部区域。
        pixels = frame[y:y + h, x:x + w].astype(np.int16)
        blue, green, red = pixels[:, :, 0], pixels[:, :, 1], pixels[:, :, 2]
        bright = pixels.max(axis=2) > BRIGHTNESS_THRESHOLD
        if (float(bright.mean()) < VISIBLE_FRACTION_THRESHOLD
                or float((bright.mean(axis=0) > COLUMN_PIXEL_THRESHOLD).mean()) < VISIBLE_COLUMNS_THRESHOLD):
            return EnergyResult(None, 'bar_not_visible')
        if index == 0:
            mask = (red > BRIGHTNESS_THRESHOLD) & (red - blue > 35) & (green - blue > 20)
        else:
            mask = (blue > BRIGHTNESS_THRESHOLD) & (blue - red > 35) & (blue - green > 10)
        present.append(_color_present(mask))
    if present[0] and present[1]:
        return EnergyResult('both')
    if present[0]:
        return EnergyResult('shaoyang')
    if present[1]:
        return EnergyResult('shaoyin')
    return EnergyResult('none')
