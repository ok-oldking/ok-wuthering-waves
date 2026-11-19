import unittest
from datetime import UTC, datetime, timedelta

from src.inventory import deficit_policy as policy


class DeficitPolicyTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(UTC)
        self.rows = [
            {"id": "a", "name": "材料甲", "target": 2, "route": "first"},
            {"id": "b", "name": "材料乙", "target": 1, "route": "second"},
        ]
        self.routes = {
            "first": {"cost": 40, "materials": ["a"]},
            "second": {"cost": 60, "materials": ["b"]},
        }
        self.stock, self.stamina, self.runs, self.journals = (
            {"a": 0, "b": 0},
            240,
            [],
            [],
        )

    def report(self):
        return {
            "schema": "inventory-report/v1",
            "game": "wuwa",
            "materials": [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "quantity": self.stock[row["id"]],
                    "status": "confirmed",
                    "evidence": [
                        {"captured_at": self.now.isoformat()} for _ in range(2)
                    ],
                }
                for row in self.rows
            ],
        }

    def farm(self, target, route):
        self.assertTrue(self.journals[-1]["pending"])
        self.runs.append(target["id"])
        self.stamina -= route["cost"]
        self.stock[target["id"]] += 1

    def run_cycle(self, **overrides):
        kwargs = {
            "game": "wuwa",
            "inspect": self.report,
            "read_stamina": lambda: self.stamina,
            "farm_once": self.farm,
            "journal": self.journals.append,
            "utcnow": lambda: self.now,
        }
        kwargs.update(overrides)
        return policy.run_cycle(self.rows, self.routes, **kwargs)

    def test_list_order_then_all_met_no_extra_stage(self):
        result = self.run_cycle()
        self.assertEqual(result["state"], "targets_met")
        self.assertEqual(self.runs, ["a", "a", "b"])
        self.assertEqual(self.stamina, 100)
        self.assertEqual(self.journals[-1], {})

    def test_stamina_shortage_does_not_refill_or_skip_priority(self):
        self.stamina = 50
        result = self.run_cycle()
        self.assertEqual(result["state"], "stamina_insufficient")
        self.assertEqual(self.runs, ["a"])
        self.assertEqual(self.stamina, 10)

    def test_unknown_target_stops_before_any_farm(self):

        def unknown():
            report = self.report()
            report["materials"][0].update(status="unverified", quantity=None)
            return report

        with self.assertRaisesRegex(RuntimeError, "未核实"):
            self.run_cycle(inspect=unknown)
        self.assertEqual(self.runs, [])

    def test_historical_report_not_reused(self):
        report = self.report()
        for row in report["materials"]:
            row["evidence"][0]["captured_at"] = (
                self.now - timedelta(seconds=1)
            ).isoformat()
        with self.assertRaisesRegex(RuntimeError, "新截图"):
            self.run_cycle(inspect=lambda: report)
        self.assertEqual(self.journals, [])

    def test_missing_duplicate_wrong_game_rejected(self):
        for change in ("missing", "duplicate", "game"):
            report = self.report()
            if change == "missing":
                report["materials"].pop()
            elif change == "duplicate":
                report["materials"].append(report["materials"][0])
            else:
                report["game"] = "zzz"
            with self.assertRaises(RuntimeError):
                self.run_cycle(inspect=lambda report=report: report)
        self.assertEqual(self.runs, [])

    def test_wrong_cost_preserves_pending_and_no_second_farm(self):

        def wrong(target, route):
            self.runs.append(target["id"])
            self.stamina -= 80

        with self.assertRaisesRegex(RuntimeError, "消耗未核实"):
            self.run_cycle(farm_once=wrong)
        self.assertEqual(self.runs, ["a"])
        self.assertTrue(self.journals[-1]["pending"])

    def test_failed_journal_never_calls_farm(self):
        with self.assertRaisesRegex(OSError, "disk"):
            self.run_cycle(journal=lambda _: (_ for _ in ()).throw(OSError("disk")))
        self.assertEqual(self.runs, [])

    def test_partial_cost_is_not_confirmed_as_regeneration(self):
        def underpaid(target, route):
            self.stamina -= route['cost'] - 1
            self.runs.append(target['id'])
        with self.assertRaisesRegex(RuntimeError, '消耗未核实'):
            self.run_cycle(farm_once=underpaid)
        self.assertEqual(self.runs, ['a'])
        self.assertTrue(self.journals[-1]['pending'])

    def test_pending_restart_cannot_observe_or_spend(self):
        with self.assertRaisesRegex(RuntimeError, "尚未核实"):
            self.run_cycle(
                pending={"pending": True}, inspect=lambda: self.fail("no scan")
            )

    def test_three_runs_without_quantity_gain_stop(self):

        def stagnant(target, route):
            self.stamina -= route["cost"]
            self.runs.append(target["id"])

        with self.assertRaisesRegex(RuntimeError, "连续3场"):
            self.run_cycle(farm_once=stagnant)
        self.assertEqual(self.runs, ["a", "a", "a"])

    def test_budget_caps_runs(self):
        result = self.run_cycle(max_runs=1)
        self.assertEqual(result["state"], "run_budget_reached")
        self.assertEqual(self.runs, ["a"])

    def test_plan_wrong_route_and_duplicates_rejected(self):
        self.rows[0]["route"] = "second"
        with self.assertRaises(ValueError):
            self.run_cycle()
        self.assertEqual(self.runs, [])

    def unavailable(self, target, route):
        self.assertTrue(self.journals[-1]["pending"])
        self.runs.append(target["id"])
        return {"state": "route_unavailable", "reason": "free_weekly_quota_remaining"}

    def quota_cycle(self, **overrides):
        self.routes["first"]["category"] = "恶名狩猎"

        def report():
            value = self.report()
            value["game"] = "zzz"
            return value

        def farm(target, route):
            return (
                self.unavailable(target, route)
                if target["route"] == "first"
                else self.farm(target, route)
            )

        return self.run_cycle(
            **dict({"game": "zzz", "inspect": report, "farm_once": farm}, **overrides)
        )

    def test_native_pre_spend_refusal_skips_route_then_other_deficit_in_order(self):
        result = self.quota_cycle()
        self.assertEqual(self.runs, ["a", "b"])
        self.assertEqual(self.stamina, 180)
        self.assertEqual(result["state"], "routes_unavailable")
        self.assertEqual(result["stock"], {"a": 0, "b": 1})
        self.assertEqual([row["material_id"] for row in result["receipts"]], ["b"])
        self.assertEqual(
            result["unavailable"],
            [
                {
                    "material_id": "a",
                    "route": "first",
                    "reason": "free_weekly_quota_remaining",
                }
            ],
        )
        self.assertEqual(self.journals[-1], {})

    def test_refusal_with_stamina_change_does_not_clear_pending_or_farm_next(self):

        def charged(target, route):
            self.stamina -= route["cost"]
            return self.unavailable(target, route)

        with self.assertRaisesRegex(RuntimeError, "未扣体力"):
            self.quota_cycle(farm_once=charged)
        self.assertEqual(self.runs, ["a"])
        self.assertTrue(self.journals[-1]["pending"])

    def test_refusal_stock_change_or_unknown_never_skips(self):
        for unknown in (False, True):
            self.setUp()

            def changed(target, route):
                self.stock["a"] += 1
                return self.unavailable(target, route)

            def report(unknown=unknown):
                value = self.report()
                value["game"] = "zzz"
                if unknown and self.runs:
                    value["materials"][0].update(status="unverified", quantity=None)
                return value

            with self.subTest(unknown=unknown), self.assertRaises(RuntimeError):
                self.quota_cycle(farm_once=changed, inspect=report)
            self.assertEqual(self.runs, ["a"])
            self.assertTrue(self.journals[-1]["pending"])

    def test_refusal_cannot_be_used_for_wuwa_or_non_weekly_route_or_unknown_reason(
        self,
    ):
        for mode in ("wuwa", "simulation", "unknown", "extra"):
            self.setUp()
            self.routes["first"]["category"] = "恶名狩猎"

            def report(mode=mode):
                value = self.report()
                value["game"] = "wuwa" if mode == "wuwa" else "zzz"
                return value

            def refused(target, route, mode=mode):
                value = self.unavailable(target, route)
                if mode == "unknown":
                    value["reason"] = "ocr_unknown"
                if mode == "extra":
                    value["spent"] = False
                return value

            if mode == "simulation":
                self.routes["first"].pop("category")
            with (
                self.subTest(mode=mode),
                self.assertRaisesRegex(RuntimeError, "返回结果无效"),
            ):
                self.run_cycle(
                    game="wuwa" if mode == "wuwa" else "zzz",
                    inspect=report,
                    farm_once=refused,
                )
            self.assertTrue(self.journals[-1]["pending"])

    def test_skipped_route_not_retried_after_other_material_runs_out_of_stamina(self):
        self.rows[1]["target"] = 5
        self.stamina = 70
        result = self.quota_cycle()
        self.assertEqual(result["state"], "stamina_insufficient")
        self.assertEqual(self.runs, ["a", "b"])
        self.assertEqual(len(result["unavailable"]), 1)

    def test_unknown_native_failure_never_skips_or_clears_pending(self):

        def failed(target, route):
            raise RuntimeError("native-unknown")

        with self.assertRaisesRegex(RuntimeError, "native-unknown"):
            self.quota_cycle(farm_once=failed)
        self.assertTrue(self.journals[-1]["pending"])

    def test_refusal_clear_journal_failure_never_runs_next_material(self):

        def journal(record):
            if not record:
                raise OSError("clear-failed")
            self.journals.append(record)

        with self.assertRaisesRegex(OSError, "clear-failed"):
            self.quota_cycle(journal=journal)
        self.assertEqual(self.runs, ["a"])
        self.assertTrue(self.journals[-1]["pending"])

    def test_shared_route_refusal_report_preserves_all_unsatisfied_targets(self):
        self.rows[1]["route"] = "first"
        self.routes["first"]["materials"].append("b")
        result = self.quota_cycle()
        self.assertEqual(self.runs, ["a"])
        self.assertEqual(result["state"], "routes_unavailable")
        self.assertEqual(
            [row["material_id"] for row in result["unavailable"]], ["a", "b"]
        )
        self.assertEqual(result["receipts"], [])

    def test_no_deficit_means_no_route_probe(self):
        self.stock = {"a": 2, "b": 1}
        result = self.quota_cycle()
        self.assertEqual(result["state"], "targets_met")
        self.assertEqual(result["unavailable"], [])
        self.assertEqual(self.runs, [])


if __name__ == "__main__":
    unittest.main()
