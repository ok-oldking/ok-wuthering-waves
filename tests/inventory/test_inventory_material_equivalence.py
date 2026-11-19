import unittest
from copy import deepcopy
from datetime import UTC, datetime

from src.inventory import deficit_policy as policy

eq = policy.equivalence


class EquivalenceTests(unittest.TestCase):
    def setUp(self):
        self.family = {
            "id": "same-family",
            "mode": "up_only",
            "members": [
                {"id": "low", "name": "低阶"},
                {"id": "middle", "name": "中阶"},
                {"id": "high", "name": "高阶"},
            ],
            "ratios": [3, 3],
            "source": "synthetic recipe, not live proof",
        }
        self.rows = [{"id": "high", "name": "高阶", "target": 2, "route": "r"}]

    def test_low_and_middle_can_fill_high_target_exactly(self):
        result = eq.evaluate(
            self.rows, {"low": 9, "middle": 3, "high": 0}, [self.family]
        )
        self.assertEqual(result["deficits"], {"high": 0})
        self.assertFalse(result["conversion_executed"])

    def test_upward_only_high_does_not_fill_low_target(self):
        rows = [{"id": "low", "name": "低阶", "target": 1, "route": "r"}]
        self.assertEqual(
            eq.evaluate(rows, {"low": 0, "middle": 0, "high": 10}, [self.family])[
                "deficits"
            ]["low"],
            1,
        )

    def test_bidirectional_high_can_fill_low(self):
        self.family["mode"] = "bidirectional"
        rows = [{"id": "low", "name": "低阶", "target": 9, "route": "r"}]
        self.assertEqual(
            eq.evaluate(rows, {"low": 0, "middle": 0, "high": 1}, [self.family])[
                "deficits"
            ]["low"],
            0,
        )

    def test_same_stock_not_spent_twice_for_multiple_quality_targets(self):
        self.family["mode"] = "bidirectional"
        rows = [{"id": "low", "name": "低阶", "target": 1, "route": "r"}, *self.rows]
        result = eq.evaluate(rows, {"low": 0, "middle": 0, "high": 2}, [self.family])
        self.assertEqual(result["deficits"], {"low": 0, "high": 1})
        self.assertFalse(result["families"][0]["sufficient"])

    def test_lower_target_reserved_before_upward_conversion(self):
        rows = [*self.rows, {"id": "low", "name": "低阶", "target": 1, "route": "r"}]
        result = eq.evaluate(rows, {"low": 18, "middle": 0, "high": 0}, [self.family])
        self.assertEqual(result["deficits"], {"high": 1, "low": 0})

    def test_rounding_cannot_invent_fractional_high_material(self):
        self.assertEqual(
            eq.evaluate(self.rows, {"low": 17, "middle": 0, "high": 0}, [self.family])[
                "deficits"
            ]["high"],
            1,
        )

    def test_unknown_zero_and_other_families_are_distinct(self):
        with self.assertRaises(RuntimeError):
            eq.evaluate(
                self.rows, {"low": None, "middle": 100, "high": 0}, [self.family]
            )
        self.assertEqual(
            eq.evaluate(self.rows, {"low": 0, "middle": 0, "high": 0}, [self.family])[
                "deficits"
            ]["high"],
            2,
        )
        with self.assertRaises(ValueError):
            eq.validate_families(
                [self.family, dict(self.family, id="another-attribute")]
            )

    def test_experience_uses_actual_values_not_three_to_one(self):
        self.family.update(mode="experience", ratios=[1000, 3000, 20000])
        self.assertEqual(
            eq.evaluate(self.rows, {"low": 40, "middle": 0, "high": 0}, [self.family])[
                "deficits"
            ]["high"],
            0,
        )
        self.assertEqual(
            eq.evaluate(self.rows, {"low": 39, "middle": 0, "high": 0}, [self.family])[
                "deficits"
            ]["high"],
            1,
        )

    def test_inspection_expands_siblings_without_mutating_targets(self):
        original = deepcopy(self.rows)
        self.assertEqual(
            [r["id"] for r in eq.observation_rows(self.rows, [self.family])],
            ["high", "low", "middle"],
        )
        self.assertEqual(self.rows, original)

    def test_conversion_already_sufficient_never_farms_or_journals(self):
        now = datetime.now(UTC)

        def inspect():
            return {
                "schema": "inventory-report/v1",
                "game": "wuwa",
                "materials": [
                    dict(
                        item,
                        status="confirmed",
                        quantity={"low": 18, "middle": 0, "high": 0}[item["id"]],
                        evidence=[{"captured_at": now.isoformat()}] * 2,
                    )
                    for item in self.family["members"]
                ],
            }

        result = policy.run_cycle(
            self.rows,
            {"r": {"cost": 40, "materials": ["high"]}},
            game="wuwa",
            inspect=inspect,
            read_stamina=lambda: self.fail("no stamina check needed"),
            farm_once=lambda *_: self.fail("must not farm"),
            journal=lambda _: self.fail("no journal"),
            utcnow=lambda: now,
            conversion_families=[self.family],
        )
        self.assertEqual(result["state"], "targets_met")
        self.assertEqual(result["stock"]["high"], 0)

    def test_low_quality_drop_is_progress_before_first_high_can_be_crafted(self):
        now = datetime.now(UTC)
        stock = {"low": 0, "middle": 0, "high": 0}
        stamina = [400]
        runs = []
        self.rows[0]["target"] = 1

        def inspect():
            return {
                "schema": "inventory-report/v1",
                "game": "wuwa",
                "materials": [
                    dict(
                        item,
                        status="confirmed",
                        quantity=stock[item["id"]],
                        evidence=[{"captured_at": now.isoformat()}] * 2,
                    )
                    for item in self.family["members"]
                ],
            }

        def farm(*_):
            runs.append(1)
            stock["low"] += 1
            stamina[0] -= 40

        result = policy.run_cycle(
            self.rows,
            {"r": {"cost": 40, "materials": ["high"]}},
            game="wuwa",
            inspect=inspect,
            read_stamina=lambda: stamina[0],
            farm_once=farm,
            journal=lambda _: None,
            utcnow=lambda: now,
            conversion_families=[self.family],
        )
        self.assertEqual(result["state"], "targets_met")
        self.assertEqual(len(runs), 9)


if __name__ == "__main__":
    unittest.main()
