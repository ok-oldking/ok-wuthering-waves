import ast
from pathlib import Path
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from src.task.NaturalStamina import natural_reading, natural_only, farm_current_stamina


class FakeTask:
    def __init__(self, current=120, refill=False):
        self.current, self.refill, self.actions = current, refill, []

    def get_stamina(self):
        return self.current, 500, self.current + 500

    def use_stamina(self, **kwargs):
        raise AssertionError('Native reserve handler must not execute')

    def sleep(self, *args):
        pass

    def click_dialog_right_button(self):
        self.actions.append('double')

    def click_dialog_left_button(self):
        self.actions.append('single')

    def wait_feature(self, *args, **kwargs):
        return self.refill

    def back(self, **kwargs):
        self.actions.append('cancel')


class NaturalStaminaTests(unittest.TestCase):
    def test_reserve_masked_and_unknown_rejected(self):
        self.assertEqual(natural_reading((20, 500, 520)), (20, 0, 20))
        for current in [-1, None, True, '120']:
            with self.assertRaises(RuntimeError):
                natural_reading((current, 500, 500))

    def test_cost_and_continuation_ignore_daily_quota(self):
        for current, cost, expected in [(60,60,(False,60)), (100,60,(False,60)),
                                         (120,60,(False,120)), (180,60,(True,120)),
                                         (80,40,(False,80)), (120,40,(True,80))]:
            task = FakeTask(current)
            with natural_only(task):
                self.assertEqual(task.use_stamina(once=cost, must_use=999), expected)
            self.assertNotIn('get_stamina', task.__dict__)
            self.assertNotIn('use_stamina', task.__dict__)

    def test_below_cost_and_unexpected_refill_cancel(self):
        for task, expected in [(FakeTask(20), ['cancel']),
                               (FakeTask(120, True), ['double', 'cancel'])]:
            with natural_only(task), self.assertRaises(RuntimeError):
                task.use_stamina()
            self.assertEqual(task.actions, expected)

    def test_instance_override_restored_even_on_error(self):
        task = FakeTask()
        read = lambda: (60,10,70)
        task.get_stamina = read
        with self.assertRaises(ValueError):
            with natural_only(task):
                raise ValueError()
        self.assertIs(task.get_stamina, read)

    def test_native_plan_no_daily_quota_and_no_false_completion(self):
        for remaining in [20, 60]:
            child = FakeTask(remaining)
            child.stamina_once = 60
            calls, logs = [], []
            child.farm_tacet = lambda **kwargs: calls.append(kwargs)
            child.ensure_main = lambda **kwargs: None
            child.openF2Book = lambda page: None
            config = {'Which to Farm': 'tacet'}
            parent = SimpleNamespace(config=config, support_tasks=['tacet','forgery','simulation'],
                                     get_task_by_class=lambda cls: child, log_info=logs.append)
            modules = {}
            for name in ['TacetTask','ForgeryTask','SimulationTask']:
                module = ModuleType('src.task.' + name)
                setattr(module, name, type(name, (), {}))
                modules[module.__name__] = module
            with patch.dict('sys.modules', modules):
                if remaining >= 60:
                    with self.assertRaises(RuntimeError):
                        farm_current_stamina(parent)
                    self.assertEqual(logs, [])
                else:
                    farm_current_stamina(parent)
                    self.assertIn('current=20 cost=60', logs[0])
            self.assertEqual(calls, [dict(daily=False,used_stamina=0,config=config)])


if __name__ == '__main__':
    unittest.main()
