"""OCR-row grouping and native painting for the Echo stat debug overlay."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
import os
import re

from src.echo_score import auto_match_template, calculate_echo_score, substat_tier, substat_tier_label


ECHO_STAT_PAINTER_KEY = "echo-stat-boxes"
TIER_TEXT_COLOR = (80, 185, 255)
LOWEST_TIER_TEXT_COLOR = (80, 235, 130)
HIGHEST_TIER_TEXT_COLOR = (255, 75, 75)
SUMMARY_TEMPLATE_COLOR = (110, 220, 255)
SUMMARY_CURRENT_COLOR = (255, 220, 80)
SUMMARY_POTENTIAL_COLOR = (120, 235, 150)
SUMMARY_CENTER_X_RATIO = 0.60
_STAT_TEXT = re.compile(
    r"攻击|生命|防御|暴击|共鸣效率|伤害加成|治疗效果|ATK|HP|DEF|Crit|Energy|DMG|Heal",
    re.IGNORECASE,
)
_VALUE_TEXT = re.compile(r"^\s*[+＋]?\d+(?:[.,]\d+)?\s*[%％]?\s*$")


@dataclass(frozen=True)
class StatRectangle:
    x: int
    y: int
    width: int
    height: int
    color: tuple[int, int, int]
    tier_x: int = 0
    tier_y: int = 0


@dataclass(frozen=True)
class RecognizedStatRow:
    x: int
    y: int
    width: int
    height: int
    stat_name: str
    value: float
    value_text: str
    tier_x: int
    tier_y: int

    def rectangle(self, color):
        return StatRectangle(
            self.x, self.y, self.width, self.height, color, self.tier_x, self.tier_y
        )


@dataclass(frozen=True)
class EchoStatAnalysis:
    rectangles: tuple[StatRectangle, ...]
    row_scores: tuple[float, ...]
    summary: str
    tier_labels: tuple[str, ...] = ()
    tier_colors: tuple[tuple[int, int, int], ...] = ()
    selected_template: str = ""


def find_echo_stat_rectangles(ocr_boxes, screen_width, screen_height):
    """Build rows from the exact OCR Boxes rendered by the debug overlay."""
    return list(analyze_echo_stats(ocr_boxes, screen_width, screen_height, "通用").rectangles)


def analyze_echo_stats(ocr_boxes, screen_width, screen_height, template_name,
                       auto_match=False, remembered_template=None):
    """Recognize one Echo panel and calculate its row and total scores."""
    if not screen_width or not screen_height:
        return EchoStatAnalysis((), (), "")

    left_rows = _find_ocr_rows(
        ocr_boxes, screen_width * 0.09, screen_width * 0.38,
        screen_height * 0.20, screen_height * 0.54,
    )
    right_rows = _find_ocr_rows(
        ocr_boxes, screen_width * 0.76, screen_width * 0.99,
        screen_height * 0.18, screen_height * 0.47,
    )
    screen_text = " ".join(str(box.name) for box in ocr_boxes)
    matched_template = auto_match_template(ocr_boxes) if auto_match else None
    automatic_template = matched_template or (remembered_template if auto_match else None)
    if automatic_template:
        template_name = automatic_template
    is_tuning_page = any(marker in screen_text for marker in (
        "声骸强化", "强化并调谐", "已完成全部调谐", "Echo Enhancement",
    ))
    is_single_echo_page = any(marker in screen_text for marker in (
        "声骸技能", "合鸣效果", "Echo Skill", "Sonata Effect",
    ))

    # Left-side stat rows are accepted only on the tuning page.  This excludes
    # the Resonator Attribute Details page and the initial Echo summary page,
    # both of which also contain six ordinary stat rows in the same area.
    if is_tuning_page and len(left_rows) >= 2:
        rows = left_rows
    elif is_single_echo_page and len(right_rows) >= 2:
        rows = right_rows
    else:
        return EchoStatAnalysis((), (), "", selected_template=matched_template or "")

    rows = rows[:7]
    main_rows, sub_rows = rows[:2], rows[2:]
    cost = _find_cost(ocr_boxes, main_rows)
    cost_key = _cost_key(cost, main_rows)
    score = calculate_echo_score(template_name, cost, cost_key, main_rows, sub_rows)
    rectangles = tuple(row.rectangle((255, 0, 0)) for row in main_rows)
    rectangles += tuple(row.rectangle((255, 255, 255)) for row in sub_rows)
    if score is None:
        return EchoStatAnalysis(rectangles, (), "", selected_template=matched_template or "")
    summary = (
        f"评分模板：{template_name}{' (自动匹配)' if automatic_template else ''}\n"
        f"当前评分：{score.current_score:.2f}\n"
        f"理论最高：{score.potential_score:.2f}"
    )
    tier_labels = ("", "") + tuple(substat_tier_label(row.stat_name, row.value) for row in sub_rows)
    tier_colors = ((255, 0, 0), (255, 0, 0)) + tuple(
        _tier_text_color(substat_tier(row.stat_name, row.value)) for row in sub_rows
    )
    return EchoStatAnalysis(
        rectangles, score.row_scores, summary, tier_labels, tier_colors,
        matched_template or "",
    )


def _find_ocr_rows(ocr_boxes, min_x, max_x, min_y, max_y):
    candidates = [box for box in ocr_boxes if min_x <= box.x <= max_x and min_y <= box.y <= max_y]
    properties = [box for box in candidates if _STAT_TEXT.search(str(box.name))]
    values = [box for box in candidates if _VALUE_TEXT.match(str(box.name))]
    rows = []
    used_values = set()
    for prop in sorted(properties, key=lambda box: (box.y + box.height / 2, box.x)):
        prop_center = prop.y + prop.height / 2
        matches = [
            value for value in values
            if id(value) not in used_values
            and value.x >= prop.x + prop.width * 0.5
            and abs((value.y + value.height / 2) - prop_center)
            <= max(9, min(prop.height, value.height) * 0.60)
        ]
        if not matches:
            continue
        value = min(matches, key=lambda item: abs((item.y + item.height / 2) - prop_center))
        used_values.add(id(value))
        left, top = min(prop.x, value.x) - 5, min(prop.y, value.y) - 3
        right = max(prop.x + prop.width, value.x + value.width) + 5
        bottom = max(prop.y + prop.height, value.y + value.height) + 3
        value_text = str(value.name)
        rows.append(RecognizedStatRow(
            round(left), round(top), round(right - left), round(bottom - top),
            _normalize_stat_name(str(prop.name), value_text),
            _numeric_value(value_text), value_text,
            round(prop.x + prop.width + 8),
            round(prop.y + max(0, (prop.height - 18) / 2)),
        ))
    return rows[:7]


def _numeric_value(text):
    match = re.search(r"\d+(?:[.,]\d+)?", str(text).replace("，", "."))
    return float(match.group(0).replace(",", ".")) if match else 0.0


def _normalize_stat_name(text, value_text):
    compact = re.sub(r"\s+", "", str(text))
    is_percent = "%" in value_text or "％" in value_text
    if "暴击伤害" in compact:
        return "暴击伤害"
    if "暴击" in compact:
        return "暴击"
    if "共鸣效率" in compact:
        return "共鸣效率"
    if "普攻" in compact:
        return "普攻"
    if "重击" in compact:
        return "重击"
    if "共鸣技能" in compact:
        return "共鸣技能"
    if "共鸣解放" in compact:
        return "共鸣解放"
    for name in ("攻击", "防御", "生命"):
        if name in compact:
            # XW-UID names percentage rolls with a trailing percent marker;
            # the unmarked name is the fixed companion/main property.
            return f"{name}%" if is_percent else name
    return compact


def _find_cost(ocr_boxes, main_rows):
    for box in ocr_boxes:
        match = re.search(r"COST\s*([134])", str(box.name), re.IGNORECASE)
        if match:
            return int(match.group(1))

    cost_labels = [box for box in ocr_boxes if re.search(r"COST", str(box.name), re.IGNORECASE)]
    digits = [box for box in ocr_boxes if str(box.name).strip() in {"1", "3", "4"}]
    for label in cost_labels:
        nearby = [
            box for box in digits
            if box.x >= label.x - 10 and box.x <= label.x + label.width + 150
            and abs((box.y + box.height / 2) - (label.y + label.height / 2)) < 35
        ]
        if nearby:
            return int(min(nearby, key=lambda box: abs(box.x - label.x)).name)

    first = main_rows[0]
    name, value = first.stat_name, first.value
    if "伤害加成" in name or name == "共鸣效率":
        return 3
    if name in {"暴击", "暴击伤害"} or "治疗" in name:
        return 4
    targets = (22.8, 38.0, 41.5) if name == "防御%" else (18.0, 30.0, 33.0)
    return (1, 3, 4)[min(range(3), key=lambda index: abs(value - targets[index]))]


def _cost_key(cost, main_rows):
    if cost != 3:
        return f"{cost}C"
    main_name = main_rows[0].stat_name
    elemental_names = ("冷凝", "热熔", "导电", "气动", "衍射", "湮灭")
    if any(name in main_name for name in elemental_names) and "伤害加成" in main_name:
        return "3C属伤"
    if "攻击" in main_name:
        return "3C攻击"
    return "3C其它"


def _tier_text_color(tier):
    if not tier:
        return TIER_TEXT_COLOR
    index, total = tier
    if index == 1:
        return LOWEST_TIER_TEXT_COLOR
    if index == total:
        return HIGHEST_TIER_TEXT_COLOR
    return TIER_TEXT_COLOR


class EchoStatBoxPainter:
    def __init__(self):
        self.rectangles = []
        self.row_scores = []
        self.summary = ""
        self.tier_labels = []
        self.tier_colors = []

    def update(self, rectangles, row_scores=(), summary="", tier_labels=(), tier_colors=()):
        self.rectangles = list(rectangles)
        self.row_scores = list(row_scores)
        self.summary = summary
        self.tier_labels = list(tier_labels)
        self.tier_colors = list(tier_colors)

    def paint(self, canvas, _overlay):
        for index, rectangle in enumerate(self.rectangles):
            canvas.rectangle(
                rectangle.x, rectangle.y, rectangle.width, rectangle.height,
                color=rectangle.color, line_width=1,
            )
            if index < len(self.row_scores):
                score_x = rectangle.x + rectangle.width + 8
                tier_label = self.tier_labels[index] if index < len(self.tier_labels) else ""
                score_lines = _score_lines(rectangle, self.row_scores[index])
                line_height = max(13, min(18, rectangle.height // 2))
                for line_index, line in enumerate(score_lines):
                    if not line:
                        continue
                    canvas.text(
                        score_x,
                        rectangle.y + line_index * line_height,
                        line,
                        color=rectangle.color,
                    )
                if tier_label:
                    tier_color = self.tier_colors[index] if index < len(self.tier_colors) else TIER_TEXT_COLOR
                    _paint_bold_text(
                        canvas,
                        rectangle.tier_x or rectangle.x,
                        rectangle.tier_y or rectangle.y,
                        tier_label,
                        tier_color,
                    )
        if self.summary:
            _paint_score_summary(canvas, _overlay, self.summary)


def _score_lines(rectangle, score):
    if abs(score) < 0.005:
        return ()
    if rectangle.color == (255, 0, 0):
        return (f"+{score:.2f}",)
    return (f"+{score:.2f}",)


def _paint_bold_text(canvas, x, y, text, color):
    """Paint an OCR-adjacent tier label with a readable bold native font."""
    if os.name != "nt":
        canvas.text(x, y, text, color=color)
        return
    from ok.ui.overlay import win32_gdi

    font = win32_gdi.gdi32.CreateFontW(
        -max(16, round(18 * canvas.ratio)), 0, 0, 0, 700, 0, 0, 0,
        1, 0, 0, 5, 0, "Microsoft YaHei UI",
    )
    old_font = win32_gdi.gdi32.SelectObject(canvas.hdc, font)
    try:
        win32_gdi.gdi32.SetBkMode(canvas.hdc, 1)
        win32_gdi.gdi32.SetTextColor(canvas.hdc, win32_gdi._rgb(*color))
        win32_gdi.gdi32.TextOutW(
            canvas.hdc, round(x * canvas.ratio), round(y * canvas.ratio), text, len(text)
        )
    finally:
        win32_gdi.gdi32.SelectObject(canvas.hdc, old_font)
        win32_gdi.gdi32.DeleteObject(font)


def _paint_score_summary(canvas, overlay, text):
    if os.name != "nt":
        return
    from ok.ui.overlay import win32_gdi

    width = round(getattr(overlay, "_frame_width", 0) * canvas.ratio)
    height = round(getattr(overlay, "_frame_height", 0) * canvas.ratio)
    if width <= 0 or height <= 0:
        return
    font = win32_gdi.gdi32.CreateFontW(
        -max(26, round(height * 0.034)), 0, 0, 0, 700, 0, 0, 0,
        1, 0, 0, 5, 0, "Microsoft YaHei UI",
    )
    old_font = win32_gdi.gdi32.SelectObject(canvas.hdc, font)
    try:
        lines = text.splitlines()
        sizes = []
        for line in lines:
            size = win32_gdi.SIZE()
            win32_gdi.gdi32.GetTextExtentPoint32W(
                canvas.hdc, line, len(line), ctypes.byref(size)
            )
            sizes.append(size)
        block_width = max(size.cx for size in sizes)
        line_height = max(size.cy for size in sizes) + max(4, round(height * 0.008))
        block_height = line_height * len(lines)
        # Keep all lines on one shared left edge, but bias the block to the
        # right. On the tuning page the stat rows and their score labels occupy
        # the left side; true screen centering made the two overlays collide.
        x = round(width * SUMMARY_CENTER_X_RATIO - block_width / 2)
        x = max(0, min(width - block_width, x))
        y = max(0, (height - block_height) // 2)
        line_colors = (SUMMARY_TEMPLATE_COLOR, SUMMARY_CURRENT_COLOR, SUMMARY_POTENTIAL_COLOR)
        for index, line in enumerate(lines):
            line_y = y + index * line_height
            for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
                win32_gdi.gdi32.SetTextColor(canvas.hdc, win32_gdi._rgb(0, 0, 0))
                win32_gdi.gdi32.TextOutW(
                    canvas.hdc, x + dx, line_y + dy, line, len(line)
                )
            color = line_colors[index] if index < len(line_colors) else SUMMARY_CURRENT_COLOR
            win32_gdi.gdi32.SetTextColor(canvas.hdc, win32_gdi._rgb(*color))
            win32_gdi.gdi32.TextOutW(canvas.hdc, x, line_y, line, len(line))
    finally:
        win32_gdi.gdi32.SelectObject(canvas.hdc, old_font)
        win32_gdi.gdi32.DeleteObject(font)
