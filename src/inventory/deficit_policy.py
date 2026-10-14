"""库存或图像配置的独立逻辑，不启动游戏，不修改已有任务计划。"""

from __future__ import annotations

import time
from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from src.inventory import material_equivalence as equivalence


def validate_plan(
    rows: list[dict[str, Any]], routes: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """核对材料目标、顺序与副本绑定，返回独立副本。"""
    if not isinstance(rows, list) or not 1 <= len(rows) <= 128:
        raise ValueError("请添加1–128个材料目标")
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"id", "name", "target", "route"}:
            raise ValueError("库存目标格式无效")
        if (
            not isinstance(row["id"], str)
            or not row["id"]
            or row["id"] in seen
            or (not isinstance(row["name"], str))
            or (not row["name"])
            or (type(row["target"]) is not int)
            or (not 0 <= row["target"] <= 10000000)
            or (not isinstance(row["route"], str))
            or (row["route"] not in routes)
        ):
            raise ValueError("材料、目标数量或刷取入口无效")
        route = routes[row["route"]]
        if (
            not isinstance(route, dict)
            or type(route.get("cost")) is not int
            or (not 1 <= route["cost"] <= 240)
            or (row["id"] not in route.get("materials", []))
        ):
            raise ValueError("材料与刷取入口不匹配")
        seen.add(row["id"])
    return deepcopy(rows)


def quantities(
    report: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    game: str,
    not_before: datetime,
    now: datetime | None = None,
) -> dict[str, int]:
    """只接受本轮新证据中的完整、准确库存。"""
    now = now or datetime.now(UTC)
    if (
        not isinstance(report, dict)
        or report.get("schema") != "inventory-report/v1"
        or report.get("game") != game
        or (not isinstance(report.get("materials"), list))
    ):
        raise RuntimeError("本次仓库报告无效，停止补刷")
    selected = {row["id"]: row for row in rows}
    found = {}
    for row in report["materials"]:
        if not isinstance(row, dict) or row.get("id") not in selected:
            continue
        material = selected[row["id"]]
        if row["id"] in found:
            raise RuntimeError("仓库材料身份重复，停止补刷")
        proofs = row.get("evidence", [])
        if (
            row.get("name") != material["name"]
            or row.get("status") != "confirmed"
            or type(row.get("quantity")) is not int
            or (row["quantity"] < 0)
            or (not isinstance(proofs, list))
            or (len(proofs) < 2)
        ):
            raise RuntimeError(f"{material['name']}数量未核实，停止补刷")
        try:
            dates = [datetime.fromisoformat(proof["captured_at"]) for proof in proofs]
            if any(
                value.tzinfo is None or not not_before <= value <= now
                for value in dates
            ):
                raise ValueError("old observation")
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("库存证据不是本轮新截图，停止补刷") from exc
        found[row["id"]] = row["quantity"]
    if set(found) != set(selected):
        raise RuntimeError("部分目标材料尚未识别，停止补刷；未知不当作0")
    return found


def run_cycle(
    rows: list[dict[str, Any]],
    routes: dict[str, dict[str, Any]],
    *,
    game: str,
    inspect: Callable[[], dict[str, Any]],
    read_stamina: Callable[[], int],
    farm_once: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any] | None],
    journal: Callable[[dict[str, Any]], None],
    pending: dict[str, Any] | None = None,
    guard: Callable[[], None] = lambda: None,
    clock: Callable[[], float] = time.monotonic,
    utcnow: Callable[[], datetime] = lambda: datetime.now(UTC),
    max_runs: int = 32,
    max_seconds: float = 3600,
    conversion_families: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """按顺序补缺，每场重新查库存；不负责导航或恢复体力。"""
    if game not in ("wuwa", "zzz"):
        raise ValueError("不支持的库存保持游戏")
    rows = validate_plan(rows, routes)
    families = equivalence.validate_families(conversion_families or [])
    read_rows = equivalence.observation_rows(rows, families)
    if pending:
        raise RuntimeError("上次补刷扣体力尚未核实，请先检查日志")
    if (
        type(max_runs) is not int
        or not 1 <= max_runs <= 32
        or (not 1 <= max_seconds <= 3600)
    ):
        raise ValueError("库存保持执行预算无效")
    started, receipts, stagnant, skipped = (clock(), [], {}, {})

    def finish(state: str, stock: dict[str, int]) -> dict[str, Any]:
        """生成本次执行结果，不改变真实库存。"""
        evaluated = equivalence.evaluate(rows, stock, families)
        return {
            "state": state,
            "receipts": receipts,
            "stock": stock,
            "equivalence": evaluated,
            "unavailable": [
                {
                    "material_id": row["id"],
                    "route": row["route"],
                    "reason": skipped[row["route"]],
                }
                for row in rows
                if row["route"] in skipped and evaluated["deficits"][row["id"]] > 0
            ],
        }

    def check() -> None:
        """检查暂停、停止与执行时限。"""
        guard()
        if clock() - started >= max_seconds:
            raise TimeoutError("库存保持超时，停止，不继续刷取")

    def scan() -> dict[str, int]:
        """读取新的库存报告并验证证据时间。"""
        check()
        floor = utcnow()
        report = inspect()
        check()
        return quantities(report, read_rows, game=game, not_before=floor, now=utcnow())

    stock = scan()
    while True:
        check()
        evaluated = equivalence.evaluate(rows, stock, families)
        deficits = [row for row in rows if evaluated["deficits"][row["id"]] > 0]
        target = next((row for row in deficits if row["route"] not in skipped), None)
        if target is None:
            return finish("routes_unavailable" if deficits else "targets_met", stock)
        before = read_stamina()
        cost = routes[target["route"]]["cost"]
        if type(before) is not int or before < 0:
            raise RuntimeError("自然体力未核实，停止补刷")
        if before < cost:
            return finish("stamina_insufficient", stock)
        if len(receipts) >= max_runs:
            return finish("run_budget_reached", stock)
        check()
        transaction = {
            "material_id": target["id"],
            "route": target["route"],
            "stamina_before": before,
            "stock_before": stock[target["id"]],
            "cost": cost,
            "created_at": utcnow().isoformat(),
            "pending": True,
        }
        journal(deepcopy(transaction))
        run_started = clock()
        outcome = farm_once(deepcopy(target), deepcopy(routes[target["route"]]))
        check()
        after = read_stamina()
        if outcome is not None:
            if (
                not isinstance(outcome, dict)
                or outcome
                != {
                    "state": "route_unavailable",
                    "reason": "free_weekly_quota_remaining",
                }
                or game != "zzz"
                or (routes[target["route"]].get("category") != "恶名狩猎")
            ):
                raise RuntimeError("材料副本返回结果无效，保留待核实记录")
            if (
                type(after) is not int
                or not 0 <= after - before <= int((clock() - run_started) // 360) + 2
            ):
                raise RuntimeError("未核实本场未扣体力，保留待核实记录，不跳过重刷")
            latest = scan()
            if latest != stock:
                raise RuntimeError("未扣体力的库存核对不一致，保留待核实记录")
            journal({})
            skipped[target["route"]] = outcome["reason"]
            stock = latest
            continue
        regenerated = after - before + cost if type(after) is int else None
        if (
            regenerated is None
            or not 0 <= regenerated <= int((clock() - run_started) // 360) + 2
        ):
            raise RuntimeError("单场体力消耗未核实，保留待核实记录，不重刷")
        latest = scan()
        if any(latest[key] < stock[key] for key in stock):
            raise RuntimeError("刷取后库存反而减少，停止并保留待核实记录")
        contributing_ids = next(
            (
                [item["id"] for item in family["members"]]
                for family in families
                if any((item["id"] == target["id"] for item in family["members"]))
            ),
            [target["id"]],
        )
        progressed = any(latest[key] > stock[key] for key in contributing_ids)
        stagnant[target["id"]] = 0 if progressed else stagnant.get(target["id"], 0) + 1
        transaction.update(
            pending=False, stamina_after=after, stock_after=latest[target["id"]]
        )
        receipts.append(transaction)
        journal({})
        stock = latest
        if stagnant[target["id"]] >= 3:
            raise RuntimeError(
                "连续3场目标材料数量未增加，请检查所选副本与材料品质；停止浪费体力"
            )
