"""真实领取凭证、自然恢复与库存增量共同核对，不能仅按余额猜扣费。"""
from datetime import datetime, timezone
import unittest
from src.inventory import deficit_policy as policy


class RegenerationTests(unittest.TestCase):
    def cycle(self, *, proof=True, gain=True, ticks=1, cost=40):
        now = datetime.now(timezone.utc)
        stock, stamina = [0], [100]
        self.journal = []
        rows = [{'id': 'a', 'name': '材料', 'target': 1, 'route': 'a'}]
        routes = {'a': {'cost': cost, 'materials': ['a']}}

        def report():
            return {'schema': 'inventory-report/v1', 'game': 'wuwa', 'materials': [
                {'id': 'a', 'name': '材料', 'quantity': stock[0], 'status': 'confirmed',
                 'evidence': [{'captured_at': now.isoformat()}] * 2}]}

        def farm(row, route):
            stamina[0] -= cost - ticks
            stock[0] += int(gain)
            return {'state': 'claimed', 'cost': cost, 'claims': 1} if proof else None

        return policy.run_cycle(rows, routes, game='wuwa', inspect=report,
            read_stamina=lambda: stamina[0], farm_once=farm, journal=self.journal.append,
            utcnow=lambda: now, clock=lambda: 0)

    def test_valid_single_claim_and_natural_tick_finishes(self):
        self.assertEqual(self.cycle()['state'], 'targets_met')
        self.assertEqual(self.journal[-1], {})

    def test_tick_without_claim_proof_remains_pending(self):
        with self.assertRaises(RuntimeError):
            self.cycle(proof=False)
        self.assertTrue(self.journal[-1]['pending'])

    def test_no_stock_gain_cannot_verify_ambiguous_charge(self):
        with self.assertRaises(RuntimeError):
            self.cycle(gain=False)
        self.assertTrue(self.journal[-1]['pending'])

    def test_one_cost_zero_loss_without_proof_is_not_success(self):
        with self.assertRaises(RuntimeError):
            self.cycle(proof=False, cost=1)
        self.assertTrue(self.journal[-1]['pending'])

    def test_impossible_recovery_is_not_accepted(self):
        with self.assertRaises(RuntimeError):
            self.cycle(ticks=10)
        self.assertTrue(self.journal[-1]['pending'])
