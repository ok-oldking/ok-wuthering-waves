import unittest

from src.task.BaseCombatTask import CharDeadException
from src.task.DomainTask import DomainTask


class TestDomainDelayedDeath(unittest.TestCase):

    def test_delayed_revive_prompt_uses_existing_death_recovery(self):
        task = DomainTask.__new__(DomainTask)
        observed = {}

        def wait_feature(name, **kwargs):
            observed['feature'] = name
            observed.update(kwargs)
            return True

        def raise_not_in_combat(message, **kwargs):
            observed['message'] = message
            observed.update(kwargs)
            raise CharDeadException(message)

        task.wait_feature = wait_feature
        task.raise_not_in_combat = raise_not_in_combat

        with self.assertRaises(CharDeadException):
            task.wait_for_delayed_revive_prompt()

        self.assertEqual(observed['feature'], 'revive_confirm_hcenter_vcenter')
        self.assertEqual(observed['threshold'], 0.8)
        self.assertEqual(observed['time_out'], 3)
        self.assertFalse(observed['raise_if_not_found'])
        self.assertTrue(observed['revive_prompt_detected'])
        self.assertIn('delayed revive prompt', observed['message'])

    def test_missing_revive_prompt_continues_to_treasure(self):
        task = DomainTask.__new__(DomainTask)
        task.stamina_once = 40
        events = []
        task.info_incr = lambda *args, **kwargs: None
        task.walk_until_f = lambda **kwargs: events.append('enter')
        task.pick_f = lambda **kwargs: events.append('pick')
        task.combat_once = lambda: events.append('combat')
        task.wait_feature = lambda *args, **kwargs: False
        task.walk_to_treasure = lambda: events.append('treasure')
        task.use_stamina = lambda **kwargs: (False, 40)
        task.sleep = lambda *_: None
        task.click = lambda *args, **kwargs: None
        task.make_sure_in_world = lambda: None
        task.log_info = lambda *args, **kwargs: None

        self.assertEqual(task.farm_in_domain(must_use=40), (True, 0))
        self.assertEqual(events[:4], ['enter', 'pick', 'combat', 'treasure'])

    def test_confirmed_prompt_is_not_detected_twice(self):
        task = DomainTask.__new__(DomainTask)
        task.wait_feature = lambda *args, **kwargs: self.fail('不应重复等待复苏弹窗')
        task.log_info = lambda *args, **kwargs: None
        task.reset_to_false = lambda **kwargs: False
        task.revive_action = lambda: False
        task.info_set = lambda *args, **kwargs: None

        with self.assertRaises(CharDeadException):
            task.raise_not_in_combat(
                'delayed revive prompt detected after combat', revive_prompt_detected=True)

    def test_delayed_death_skips_treasure_and_enters_recovery(self):
        task = DomainTask.__new__(DomainTask)
        task.stamina_once = 40
        events = []
        task.info_incr = lambda *args, **kwargs: None
        task.walk_until_f = lambda **kwargs: None
        task.pick_f = lambda **kwargs: None
        task.combat_once = lambda: None
        task.wait_for_delayed_revive_prompt = lambda: (_ for _ in ()).throw(
            CharDeadException('delayed revive prompt'))
        task.walk_to_treasure = lambda: events.append('treasure')
        task.make_sure_in_world = lambda: events.append('recover')
        task.log_info = lambda *args, **kwargs: None

        self.assertEqual(task.farm_in_domain(must_use=80), (False, 80))
        self.assertEqual(events, ['recover'])


if __name__ == '__main__':
    unittest.main()
