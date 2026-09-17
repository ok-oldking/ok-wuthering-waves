"""OCR-row grouping and native painting for the Echo stat debug overlay."""

from __future__ import annotations

from dataclasses import dataclass
import re


ECHO_STAT_PAINTER_KEY = "echo-stat-boxes"
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


def find_echo_stat_rectangles(ocr_boxes, screen_width, screen_height):
    """Build rows from the exact OCR Boxes rendered by the debug overlay."""
    if not screen_width or not screen_height:
        return []

    left_rows = _find_ocr_rows(
        ocr_boxes, screen_width * 0.09, screen_width * 0.38,
        screen_height * 0.20, screen_height * 0.54,
    )
    right_rows = _find_ocr_rows(
        ocr_boxes, screen_width * 0.76, screen_width * 0.99,
        screen_height * 0.18, screen_height * 0.47,
    )
    screen_text = " ".join(str(box.name) for box in ocr_boxes)
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
        return []

    rectangles = [StatRectangle(*row, color=(255, 0, 0)) for row in rows[:2]]
    rectangles.extend(StatRectangle(*row, color=(255, 255, 255)) for row in rows[2:7])
    return rectangles


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
        rows.append((round(left), round(top), round(right - left), round(bottom - top)))
    return rows[:7]


class EchoStatBoxPainter:
    def __init__(self):
        self.rectangles = []

    def update(self, rectangles):
        self.rectangles = list(rectangles)

    def paint(self, canvas, _overlay):
        for rectangle in self.rectangles:
            canvas.rectangle(
                rectangle.x, rectangle.y, rectangle.width, rectangle.height,
                color=rectangle.color, line_width=1,
            )
