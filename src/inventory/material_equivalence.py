"""库存或图像配置的独立逻辑，不启动游戏，不修改已有任务计划。"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

MODES = {"up_only", "bidirectional", "experience"}


def validate_families(families: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """核对同系列材料的转换方向、比例与独立身份。"""
    if not isinstance(families, list) or len(families) > 128:
        raise ValueError("材料折算系列配置无效")
    used, names = (set(), set())
    for family in families:
        if (
            not isinstance(family, dict)
            or set(family) != {"id", "mode", "members", "ratios", "source"}
            or (not isinstance(family["id"], str))
            or (not family["id"])
            or (family["id"] in names)
            or (family["mode"] not in MODES)
            or (not isinstance(family["source"], str))
            or (not family["source"].strip())
            or (not isinstance(family["members"], list))
            or (not 2 <= len(family["members"]) <= 4)
        ):
            raise ValueError("必须明确材料系列、转换方向和来源")
        names.add(family["id"])
        members = family["members"]
        for item in members:
            if (
                not isinstance(item, dict)
                or set(item) != {"id", "name"}
                or (
                    not all(
                        isinstance(item[k], str) and item[k] for k in ("id", "name")
                    )
                )
                or (item["id"] in used)
            ):
                raise ValueError("材料折算身份缺失或跨系列重复")
            used.add(item["id"])
        ratios = family["ratios"]
        expected = len(members) if family["mode"] == "experience" else len(members) - 1
        if (
            not isinstance(ratios, list)
            or len(ratios) != expected
            or any(type(n) is not int or not 1 <= n <= 10**6 for n in ratios)
            or (family["mode"] != "experience" and any(n < 2 for n in ratios))
        ):
            raise ValueError("必须明确整数合成比例或经验值")
        if family["mode"] == "experience" and ratios != sorted(set(ratios)):
            raise ValueError("经验材料须按独立、递增的真实经验值排序")
    return deepcopy(families)


def load_families(root: Path, game: str) -> list[dict[str, Any]]:
    """读取有大小限制的材料折算配置，不创建默认目标。"""
    file = Path(root) / "config/inventory-material-equivalence.json"
    if not file.exists():
        return []
    if file.stat().st_size > 1024 * 1024:
        raise ValueError("材料折算配置过大")
    data = json.loads(file.read_text(encoding="utf-8-sig"))
    if (
        not isinstance(data, dict)
        or data.get("schema") != "inventory-material-equivalence/v1"
        or (not isinstance(data.get("games"), dict))
        or (game not in ("wuwa", "zzz"))
    ):
        raise ValueError("材料折算配置或游戏身份无效")
    return validate_families(data["games"].get(game, []))


def observation_rows(
    rows: list[dict[str, Any]], families: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """补齐折算所需品质，不修改目标顺序。"""
    families = validate_families(families)
    selected = {row["id"]: row for row in rows}
    result = deepcopy(rows)
    for family in families:
        active = [item for item in family["members"] if item["id"] in selected]
        if not active:
            continue
        for item in active:
            if selected[item["id"]]["name"] != item["name"]:
                raise ValueError("材料折算名称与目标不一致")
        for item in family["members"]:
            if item["id"] not in selected:
                result.append(dict(item, target=0))
                selected[item["id"]] = item
    return result


def evaluate(
    rows: list[dict[str, Any]], stock: dict[str, int], families: list[dict[str, Any]]
) -> dict[str, Any]:
    """对同一份库存统一抵扣目标，不执行合成或分解。"""
    families = validate_families(families)
    targets = {row["id"]: row for row in rows}
    if any(
        type(stock.get(row["id"])) is not int or stock[row["id"]] < 0 for row in rows
    ):
        raise RuntimeError("目标材料数量未核实，未知不当作0")
    deficits = {row["id"]: max(0, row["target"] - stock[row["id"]]) for row in rows}
    summaries = []
    for family in families:
        members = family["members"]
        active = [item for item in members if item["id"] in targets]
        if not active:
            continue
        for item in members:
            count = stock.get(item["id"])
            if type(count) is not int or not 0 <= count <= 2**63 - 1:
                raise RuntimeError("折算所需材料数量未核实，未知不当作0")
            if item["id"] in targets and targets[item["id"]]["name"] != item["name"]:
                raise ValueError("材料折算名称与目标不一致")
        ratios = family["ratios"]
        weights = ratios if family["mode"] == "experience" else [1]
        if family["mode"] != "experience":
            for ratio in ratios:
                weights.append(weights[-1] * ratio)
        total = sum(
            (stock[item["id"]] * w for item, w in zip(members, weights, strict=True))
        )
        needed = sum(
            (
                targets[item["id"]]["target"] * w
                for item, w in zip(members, weights, strict=True)
                if item["id"] in targets
            )
        )
        if family["mode"] in ("bidirectional", "experience"):
            budget = total
            weights_by_id = {
                item["id"]: w for item, w in zip(members, weights, strict=True)
            }
            for row in rows:
                if row["id"] not in weights_by_id:
                    continue
                weight = weights_by_id[row["id"]]
                allocated = min(row["target"], budget // weight)
                budget -= allocated * weight
                deficits[row["id"]] = row["target"] - allocated
        else:
            carry = 0
            for i, item in enumerate(members):
                available = stock[item["id"]] + carry
                goal = targets.get(item["id"], {}).get("target", 0)
                allocated = min(goal, available)
                if item["id"] in targets:
                    deficits[item["id"]] = goal - allocated
                carry = (available - allocated) // ratios[i] if i < len(ratios) else 0
        summaries.append(
            {
                "family": family["id"],
                "mode": family["mode"],
                "owned_base_units": total,
                "target_base_units": needed,
                "sufficient": all(deficits[item["id"]] == 0 for item in active),
                "requires_conversion": family["mode"] != "experience"
                and any(
                    stock[item["id"]] < targets[item["id"]]["target"] for item in active
                ),
                "requires_substitution": any(
                    stock[item["id"]] < targets[item["id"]]["target"] for item in active
                ),
                "conversion_executed": False,
            }
        )
    return {
        "deficits": deficits,
        "families": summaries,
        "actual_stock": deepcopy(stock),
        "conversion_executed": False,
    }
