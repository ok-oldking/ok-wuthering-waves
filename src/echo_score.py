"""Echo score calculation adapted from the local wuwa-stat-echo project."""

from __future__ import annotations

import json
from dataclasses import dataclass


# Snapshot of E:\wuwa-stat-echo\backend\consts.py.  Keeping the values local
# makes the development client independent from the sibling checkout.
TEMPLATE_DATA = json.loads(r'''{"通用":{"echo_max_score":{"4":80,"3":80,"1":80},"mainstat_scores":{"4C":[6.61,2.25],"3C属伤":[5.21,1.57],"3C攻击":[5.16,1.57],"3C其它":[1.57,0],"1C":[4.76,0]},"substat_weight":{"共鸣效率":0.3,"普攻":0.05,"重击":0.05,"共鸣技能":0.05,"共鸣解放":0.05}},"暗主":{"echo_max_score":{"4":82.527,"3":78.527,"1":74.977},"mainstat_scores":{"4C":[6.66,2.27],"3C属伤":[5.25,1.59],"3C攻击":[5.25,1.59],"3C其它":[1.59,0],"1C":[4.8,0]},"substat_weight":{"共鸣效率":0.5,"普攻":0.275,"共鸣技能":0.22,"共鸣解放":0.605}},"椿":{"echo_max_score":{"4":83.8,"3":79.8,"1":76.25},"mainstat_scores":{"4C":[6.56,2.23],"3C属伤":[5.2,1.6],"3C攻击":[5.2,1.6],"3C其它":[1.6,0],"1C":[4.72,0]},"substat_weight":{"共鸣效率":0.15,"普攻":0.715,"共鸣解放":0.275}},"珂莱塔":{"echo_max_score":{"4":86.066,"3":82.066,"1":78.516},"mainstat_scores":{"4C":[6.39,2.17],"3C属伤":[5.02,1.52],"3C攻击":[5.02,1.52],"3C其它":[1.52,0],"1C":[4.58,0]},"substat_weight":{"共鸣效率":0.2,"共鸣技能":0.91}},"今汐":{"echo_max_score":{"4":83.8,"3":79.8,"1":76.25},"mainstat_scores":{"4C":[6.56,2.23],"3C属伤":[5.16,1.56],"3C攻击":[5.16,1.56],"3C其它":[1.56,0],"1C":[4.72,0]},"substat_weight":{"共鸣效率":0.25,"共鸣技能":0.715,"共鸣解放":0.33}},"长离":{"echo_max_score":{"4":83.17,"3":79.17,"1":75.62},"mainstat_scores":{"4C":[6.61,2.25],"3C属伤":[5.21,1.57],"3C攻击":[5.21,1.57],"3C其它":[1.57,0],"1C":[4.76,0]},"substat_weight":{"共鸣效率":0.3,"共鸣技能":0.66,"共鸣解放":0.44}},"坎特蕾拉":{"echo_max_score":{"4":83.17,"3":79.17,"1":75.62},"mainstat_scores":{"4C":[6.61,2.25],"3C属伤":[5.21,1.57],"3C攻击":[5.21,1.57],"3C其它":[1.57,0],"1C":[4.76,0]},"substat_weight":{"共鸣效率":0.5,"普攻":0.66}},"折枝":{"echo_max_score":{"4":81.89,"3":77.89,"1":74.34},"mainstat_scores":{"4C":[6.71,2.28],"3C属伤":[5.29,1.6],"3C攻击":[5.29,1.6],"3C其它":[1.6,0],"1C":[4.84,0]},"substat_weight":{"共鸣效率":0.2,"普攻":0.55,"重击":0.22,"共鸣技能":0.22}},"忌炎":{"echo_max_score":{"4":83.8,"3":79.8,"1":76.25},"mainstat_scores":{"4C":[6.56,2.23],"3C属伤":[5.16,1.56],"3C攻击":[5.16,1.56],"3C其它":[1.56,0],"1C":[4.72,0]},"substat_weight":{"共鸣效率":0.3,"普攻":0.165,"重击":0.715,"共鸣技能":0.33}},"相里要":{"echo_max_score":{"4":83.8,"3":79.8,"1":76.25},"mainstat_scores":{"4C":[6.56,2.23],"3C属伤":[5.16,1.56],"3C攻击":[5.16,1.56],"3C其它":[1.56,0],"1C":[4.72,0]},"substat_weight":{"共鸣效率":0.3,"普攻":0.165,"共鸣技能":0.22,"共鸣解放":0.715}},"洛可可":{"echo_max_score":{"4":85.25,"3":81.25,"1":77.7},"mainstat_scores":{"4C":[6.45,2.19],"3C属伤":[5.07,1.53],"3C攻击":[5.07,1.53],"3C其它":[1.53,0],"1C":[4.63,0]},"substat_weight":{"共鸣效率":0.3,"重击":0.84}},"布兰特":{"echo_max_score":{"4":77.33,"3":74.03,"1":71.88},"mainstat_scores":{"4C":[7.11,1.06],"3C属伤":[5.57,0.74],"3C攻击":[5.57,0.74],"3C其它":[5.57,0.74],"1C":[5,0]},"substat_weight":{"攻击":0.44,"攻击固定值":0.044,"共鸣效率":0.8,"普攻":0.66,"共鸣解放":0.165}},"菲比":{"echo_max_score":{"4":78.76,"3":74.76,"1":71.21},"mainstat_scores":{"4C":[6.98,2.38],"3C属伤":[5.51,1.67],"3C攻击":[5.21,1.57],"3C其它":[1.57,0],"1C":[5.05,0]},"substat_weight":{"暴击":1.58,"共鸣效率":0.1,"普攻":0.088,"重击":0.66,"共鸣技能":0.055,"共鸣解放":0.187}},"赞妮":{"echo_max_score":{"4":83.8,"3":79.8,"1":76.25},"mainstat_scores":{"4C":[6.56,2.23],"3C属伤":[5.16,1.56],"3C攻击":[5.16,1.56],"3C其它":[1.56,0],"1C":[4.72,0]},"substat_weight":{"共鸣效率":0.3,"重击":0.715,"共鸣解放":0.154}},"夏空":{"echo_max_score":{"4":82.78,"3":78.78,"1":75.23},"mainstat_scores":{"4C":[6.64,2.26],"3C属伤":[5.23,1.58],"3C攻击":[5.23,1.58],"3C其它":[1.58,0],"1C":[4.78,0]},"substat_weight":{"共鸣效率":0.3,"普攻":0.506,"重击":0.363,"共鸣解放":0.627}},"卡提希娅":{"echo_max_score":{"4":79.726,"3":76.871,"1":78.986},"mainstat_scores":{"4C":[6.89,0],"3C属伤":[5.46,0],"3C攻击":[5.46,0],"3C其它":[0,0],"1C":[4.32,2.16]},"substat_weight":{"攻击":0,"攻击固定值":0,"生命":1.1,"生命固定值":0.01,"共鸣效率":0.1,"普攻":0.704,"共鸣解放":0.308}},"露帕":{"echo_max_score":{"4":84.059,"3":80.059,"1":76.509},"mainstat_scores":{"4C":[6.54,2.23],"3C属伤":[5.15,1.56],"3C攻击":[5.15,1.56],"3C其它":[1.56,0],"1C":[4.7,0]},"substat_weight":{"共鸣效率":0.2,"普攻":0.077,"重击":0.055,"共鸣技能":0.231,"共鸣解放":0.737}},"弗洛洛":{"echo_max_score":{"4":84.059,"3":80.059,"1":76.509},"mainstat_scores":{"4C":[6.54,2.23],"3C属伤":[5.15,1.56],"3C攻击":[5.15,1.56],"3C其它":[1.56,0],"1C":[4.7,0]},"substat_weight":{"共鸣技能":0.737}},"奥古斯塔":{"echo_max_score":{"4":85.161,"3":81.161,"1":77.611},"mainstat_scores":{"4C":[6.45,2.2],"3C属伤":[5.08,1.54],"3C攻击":[5.08,1.54],"3C其它":[1.54,0],"1C":[4.63,0]},"substat_weight":{"重击":0.832,"共鸣效率":0.2}},"尤诺":{"echo_max_score":{"4":83.804,"3":79.804,"1":76.254},"mainstat_scores":{"4C":[6.56,2.23],"3C属伤":[5.16,1.56],"3C攻击":[5.16,1.56],"3C其它":[1.56,0],"1C":[4.72,0]},"substat_weight":{"共鸣效率":0.2,"共鸣解放":0.715}},"嘉贝莉娜":{"echo_max_score":{"4":80.358,"3":76.358,"1":72.808},"mainstat_scores":{"4C":[6.56,2.23],"3C属伤":[5.4,1.63],"3C攻击":[5.4,1.63],"3C其它":[1.63,0],"1C":[4.94,0]},"substat_weight":{"共鸣效率":0.2,"重击":0.418}},"陆赫斯":{"echo_max_score":{"4":85.915,"3":81.915,"1":78.365},"mainstat_scores":{"4C":[6.4,2.18],"3C属伤":[5.03,1.52],"3C攻击":[5.03,1.52],"3C其它":[1.52,0],"1C":[4.59,0]},"substat_weight":{"攻击":1.15,"普攻":0.847,"共鸣效率":0.15}},"爱弥斯":{"echo_max_score":{"4":85.642,"3":81.642,"1":78.092},"mainstat_scores":{"4C":[6.42,2.18],"3C属伤":[5.05,1.53],"3C攻击":[5.05,1.53],"3C其它":[1.53,0],"1C":[4.6,0]},"substat_weight":{"攻击固定值":0.12,"共鸣解放":0.77,"共鸣效率":0.2}},"达妮娅":{"echo_max_score":{"4":85.939,"3":83.88,"1":84.979},"mainstat_scores":{"4C":[6.14,1.74],"3C属伤":[5.36,1.49],"3C攻击":[5.36,1.49],"3C其它":[1.49,0],"1C":[7.41,0]},"substat_weight":{"攻击":1.2,"攻击固定值":0.11,"共鸣效率":0.2,"共鸣解放":0.85}},"丽贝卡":{"echo_max_score":{"4":85.475,"3":83.416,"1":82.715},"mainstat_scores":{"4C":[5.18,1.47],"3C属伤":[5.39,1.49],"3C攻击":[5.39,1.49],"3C其它":[1.49,0],"1C":[6.52,0]},"substat_weight":{"攻击":1.2,"攻击固定值":0.11,"共鸣效率":0.25,"共鸣解放":0.09,"普攻":0.81}},"露西":{"echo_max_score":{"4":86.518,"3":84.46,"1":83.758},"mainstat_scores":{"4C":[6.1,1.73],"3C属伤":[5.32,1.47],"3C攻击":[5.32,1.47],"3C其它":[1.47,0],"1C":[6.44,0]},"substat_weight":{"攻击":1.2,"攻击固定值":0.11,"共鸣效率":0.2,"重击":0.9}},"穗穗":{"echo_max_score":{"4":54.427,"3":52.478,"1":58.154},"mainstat_scores":{"4C":[10.61,0],"3C属伤":[7.84,5.29],"3C攻击":[7.84,5.29],"3C其它":[7.84,5.29],"1C":[7.84,5.29]},"substat_weight":{"暴击":0.1,"暴击伤害":0.33,"攻击":0,"攻击固定值":0,"共鸣效率":1,"共鸣技能":0.33,"生命":1.2,"生命固定值":0.01}},"清霄":{"echo_max_score":{"4":83.051,"3":79.801,"1":79.1},"mainstat_scores":{"4C":[6.62,2.25],"3C属伤":[5.63,1.56],"3C攻击":[5.63,1.56],"3C其它":[1.56,0],"1C":[6.82,0]},"substat_weight":{"暴击":1.7,"暴击伤害":1,"攻击":1.2,"攻击固定值":0.11,"共鸣效率":0.2,"重击":0.77,"普攻":0.44,"共鸣解放":0.605}}}''')

DEFAULT_WEIGHTS = {"暴击": 2.0, "暴击伤害": 1.0, "攻击": 1.1, "攻击固定值": 0.1}
MAX_SUBSTAT_VALUES = {
    "暴击": 10.5, "暴击伤害": 21.0, "攻击": 11.6, "防御": 14.7,
    "生命": 11.6, "攻击固定值": 60.0, "防御固定值": 70.0,
    "生命固定值": 580.0, "共鸣效率": 12.4, "普攻": 11.6,
    "重击": 11.6, "共鸣技能": 11.6, "共鸣解放": 11.6,
}


@dataclass(frozen=True)
class EchoScoreResult:
    cost: int
    cost_key: str
    row_scores: tuple[float, ...]
    current_score: float
    potential_score: float


def template_names():
    return list(TEMPLATE_DATA)


def calculate_echo_score(template_name, cost, cost_key, main_rows, sub_rows):
    template = TEMPLATE_DATA.get(template_name, TEMPLATE_DATA["通用"])
    denominator = float(template["echo_max_score"].get(str(cost), 0))
    if denominator <= 0:
        return None

    weights = dict(DEFAULT_WEIGHTS)
    weights.update(template["substat_weight"])
    main_scores = list(template["mainstat_scores"].get(cost_key, (0.0, 0.0)))
    if cost_key == "3C其它":
        main_scores = [0.0, sum(main_scores)]
    main_scores = (main_scores + [0.0, 0.0])[:len(main_rows)]

    sub_scores = [weights.get(row.stat_name, 0.0) * row.value / denominator * 50 for row in sub_rows]
    current = sum(main_scores) + sum(sub_scores)

    selected = {row.stat_name for row in sub_rows}
    remaining_slots = max(0, 5 - len(selected))
    candidates = sorted((
        weights.get(name, 0.0) * value / denominator * 50
        for name, value in MAX_SUBSTAT_VALUES.items() if name not in selected
    ), reverse=True)
    potential = current + sum(candidates[:remaining_slots])
    return EchoScoreResult(
        cost=cost,
        cost_key=cost_key,
        row_scores=tuple(main_scores + sub_scores),
        # Match JavaScript toFixed used by wuwa-stat-echo at half-cent values.
        current_score=float(f"{current + 1e-9:.2f}"),
        potential_score=float(f"{potential + 1e-9:.2f}"),
    )
