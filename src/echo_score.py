"""XW-UID-compatible score calculation for one Echo."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math

from src.xwuid_echo_data import TEMPLATES


SCORE_PER_ECHO = 50.0
ELEMENT_NAMES = {"冷凝", "热熔", "导电", "气动", "衍射", "湮灭"}
SKILL_WEIGHT_INDEX = {
    "普攻伤害加成": 0,
    "重击伤害加成": 1,
    "共鸣技能伤害加成": 2,
    "共鸣解放伤害加成": 3,
}
_SHORT_SKILL_NAMES = {
    "普攻": "普攻伤害加成",
    "重击": "重击伤害加成",
    "共鸣技能": "共鸣技能伤害加成",
    "共鸣解放": "共鸣解放伤害加成",
}
MAX_SUBSTAT_VALUES = {
    "暴击": 10.5,
    "暴击伤害": 21.0,
    "攻击%": 11.6,
    "防御%": 14.7,
    "生命%": 11.6,
    "攻击": 60.0,
    "防御": 70.0,
    "生命": 580.0,
    "共鸣效率": 12.4,
    "普攻": 11.6,
    "重击": 11.6,
    "共鸣技能": 11.6,
    "共鸣解放": 11.6,
}
SUBSTAT_TIERS = {
    "暴击": (6.3, 6.9, 7.5, 8.1, 8.7, 9.3, 9.9, 10.5),
    "暴击伤害": (12.6, 13.8, 15.0, 16.2, 17.4, 18.6, 19.8, 21.0),
    "攻击%": (6.4, 7.1, 7.9, 8.6, 9.4, 10.1, 10.9, 11.6),
    "防御%": (8.1, 9.0, 10.0, 10.9, 11.8, 12.8, 13.8, 14.7),
    "生命%": (6.4, 7.1, 7.9, 8.6, 9.4, 10.1, 10.9, 11.6),
    "攻击": (30.0, 40.0, 50.0, 60.0),
    "防御": (40.0, 50.0, 60.0, 70.0),
    "生命": (320.0, 360.0, 390.0, 430.0, 470.0, 510.0, 540.0, 580.0),
    "共鸣效率": (6.8, 7.6, 8.4, 9.2, 10.0, 10.8, 11.6, 12.4),
    "普攻": (6.4, 7.1, 7.9, 8.6, 9.4, 10.1, 10.9, 11.6),
    "重击": (6.4, 7.1, 7.9, 8.6, 9.4, 10.1, 10.9, 11.6),
    "共鸣技能": (6.4, 7.1, 7.9, 8.6, 9.4, 10.1, 10.9, 11.6),
    "共鸣解放": (6.4, 7.1, 7.9, 8.6, 9.4, 10.1, 10.9, 11.6),
}
MAX_MAINSTAT_VALUES = {
    1: (
        {"攻击%": 18.0, "生命%": 22.8, "防御%": 22.8},
        {"生命": 2280.0},
    ),
    3: (
        {
            "攻击%": 30.0,
            "生命%": 30.0,
            "防御%": 38.0,
            "共鸣效率": 32.0,
            "冷凝伤害加成": 30.0,
            "热熔伤害加成": 30.0,
            "导电伤害加成": 30.0,
            "气动伤害加成": 30.0,
            "衍射伤害加成": 30.0,
            "湮灭伤害加成": 30.0,
        },
        {"攻击": 100.0},
    ),
    4: (
        {
            "攻击%": 33.0,
            "生命%": 33.0,
            "防御%": 41.5,
            "暴击": 22.0,
            "暴击伤害": 44.0,
            "治疗效果加成": 26.0,
        },
        {"攻击": 150.0},
    ),
}


@dataclass(frozen=True)
class EchoScoreResult:
    cost: int
    cost_key: str
    row_scores: tuple[float, ...]
    current_score: float
    potential_score: float


def _build_template_options():
    rows = [
        (str(char_id), variant, template)
        for char_id, variants in TEMPLATES.items()
        for variant, template in variants.items()
    ]
    duplicate_names = Counter(template["name"] for _, _, template in rows)
    options = {}
    for char_id, variant, template in rows:
        label = template["name"]
        if duplicate_names[label] > 1:
            label = f"{label}（{char_id}）"
        options[label] = (char_id, variant, template)
    return options


TEMPLATE_OPTIONS = _build_template_options()
DEFAULT_TEMPLATE = TEMPLATES["default"]["default"]["name"]


def template_names():
    """Return all 66 character/modal templates as unique display labels."""
    return list(TEMPLATE_OPTIONS)


def matching_template_names(text):
    """Case-insensitive contains matching used by the searchable selector."""
    query = str(text).strip().casefold()
    return [name for name in template_names() if query in name.casefold()]


def substat_tier(stat_name, value):
    """Return ``(tier, total_tiers)`` for the closest in-game roll value."""
    tiers = SUBSTAT_TIERS.get(stat_name)
    if not tiers:
        return None
    tier_index = min(range(len(tiers)), key=lambda index: abs(tiers[index] - float(value)))
    return tier_index + 1, len(tiers)


def substat_tier_label(stat_name, value):
    """Return the closest in-game roll tier, such as ``1档`` or ``8档``."""
    tier = substat_tier(stat_name, value)
    return f"{tier[0]}档" if tier else ""


def resolve_template_name(template_name):
    """Resolve an exact option or migrate a legacy bare character name."""
    if template_name in TEMPLATE_OPTIONS:
        return template_name
    if template_name == "通用":
        return DEFAULT_TEMPLATE
    prefix = f"{template_name}-"
    matches = [name for name in template_names() if name.startswith(prefix)]
    return matches[0] if matches else DEFAULT_TEMPLATE


def _selected_template(template_name):
    return TEMPLATE_OPTIONS[resolve_template_name(template_name)][2]


def _main_name(name):
    if name.endswith("伤害加成") and name.removesuffix("伤害加成") in ELEMENT_NAMES:
        return "属性伤害加成"
    return name


def _entry_weight(index, name, cost, template):
    if index < 2:
        return float(template.get("main_props", {}).get(str(cost), {}).get(_main_name(name), 0.0))

    name = _SHORT_SKILL_NAMES.get(name, name)
    sub_weights = template.get("sub_props", {})
    if name in SKILL_WEIGHT_INDEX:
        generic_weight = float(sub_weights.get("技能伤害加成", 0.0))
        skill_weights = template.get("skill_weight", [0.0, 0.0, 0.0, 0.0])
        return generic_weight * float(skill_weights[SKILL_WEIGHT_INDEX[name]])
    return float(sub_weights.get(name, 0.0))


def _truncate_2(value):
    return math.trunc((value + 1e-12) * 100.0) / 100.0


def _max_main_value(cost, index, row):
    """Return the +25 value for this main-stat slot, or its observed value."""
    slots = MAX_MAINSTAT_VALUES.get(int(cost), ())
    if index >= len(slots):
        return row.value
    return slots[index].get(row.stat_name, row.value)


def calculate_echo_score(template_name, cost, cost_key, main_rows, sub_rows):
    """Score OCR rows using XW-UID's per-entry truncation and 50-point scale."""
    template = _selected_template(template_name)
    try:
        maximum = float(template["score_max"][(1, 3, 4).index(int(cost))])
    except (KeyError, ValueError, IndexError, TypeError):
        return None
    if maximum <= 0:
        return None

    rows = list(main_rows) + list(sub_rows)
    row_scores = tuple(
        _truncate_2(
            (
                _max_main_value(cost, index, row)
                if index < len(main_rows)
                else row.value
            )
            * _entry_weight(index, row.stat_name, int(cost), template)
            / maximum * SCORE_PER_ECHO
        )
        for index, row in enumerate(rows)
    )
    existing_substats = {row.stat_name for row in sub_rows}
    remaining_slots = max(0, 5 - len(sub_rows))
    best_unrolled_scores = sorted(
        (
            _truncate_2(
                max_value * _entry_weight(2, name, int(cost), template)
                / maximum * SCORE_PER_ECHO
            )
            for name, max_value in MAX_SUBSTAT_VALUES.items()
            if name not in existing_substats
        ),
        reverse=True,
    )
    potential_score = round(
        sum(row_scores)
        + sum(best_unrolled_scores[:remaining_slots]),
        2,
    )
    return EchoScoreResult(
        cost=int(cost),
        cost_key=cost_key,
        row_scores=row_scores,
        current_score=round(sum(row_scores), 2),
        potential_score=potential_score,
    )
