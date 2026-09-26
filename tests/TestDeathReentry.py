import unittest
from unittest.mock import patch

from src.task.BaseCombatTask import BaseCombatTask, CharRevivedException
from src.task.FarmEchoTask import FarmEchoTask
from src.task.TacetTask import TacetTask


def combat_results(deaths):
    calls = []

    def combat_once(*args, **kwargs):
        calls.append(kwargs)
        if len(calls) <= deaths:
            raise CharRevivedException('char dead')
        return True

    return combat_once, calls


class TestTacetDeathReentry(unittest.TestCase):

    def make_task(self, deaths):
        task = TacetTask.__new__(TacetTask)
        task.stamina_once = 60
        task.teleports = []
        task.logs = []
        task.combat_once, task.combat_calls = combat_results(deaths)
        noop = lambda *args, **kwargs: None
        for name in ('info_incr', 'sleep', 'openF2Book', 'click_relative', 'open_boss_book',
                     'click_team_challenge', 'wait_in_team_and_world', 'walk_to_treasure', 'pick_f',
                     'wait_click_skip_dialog_confirm'):
            setattr(task, name, noop)
        task.get_stamina = lambda: (120, 0, 120)
        task.teleport_to_tacet = lambda index: task.teleports.append(index)
        task.has_claim_stamina = lambda: True
        task.use_stamina = lambda once, must_use: (False, once)
        task.log_info = lambda message, **kwargs: task.logs.append(message)
        return task

    def test_reenter_from_f2_book_after_revive(self):
        task = self.make_task(deaths=1)

        task.farm_tacet(config={'Which Tacet Suppression to Farm': 1})

        self.assertEqual([0, 0], task.teleports)
        self.assertEqual(2, len(task.combat_calls))
        self.assertIn('farm_tacet: death recovered, re-enter from F2 book', task.logs)

    def test_stop_after_max_recovery_retries(self):
        task = self.make_task(deaths=99)

        self.assertIsNone(task.farm_tacet(config={'Which Tacet Suppression to Farm': 1}))

        self.assertEqual(3, len(task.teleports))
        self.assertEqual(3, len(task.combat_calls))
        self.assertIn('farm_tacet: exceeded recovery retries (3), stop farming', task.logs)


class TestFarmEchoDeathReentry(unittest.TestCase):

    def make_task(self, deaths, teleport_enabled=True, repeat=2):
        task = FarmEchoTask.__new__(FarmEchoTask)
        task.config = {'Repeat Farm Count': repeat}
        task.combat_wait_time = 0
        task.bypass_end_wait = True
        task._just_entered_boss_realm = False
        task.teleports = []
        task.logs = []
        task.combat_once, task.combat_calls = combat_results(deaths)
        noop = lambda *args, **kwargs: None
        for name in ('manage_boss_parameters', 'log_debug', 'log_error', 'init_parameters', 'in_realm_check',
                     'manage_boss_interactions', 'sleep', 'check_boss_name', 'incr_drop'):
            setattr(task, name, noop)
        task.in_realm = lambda: True
        task.in_combat = lambda *args, **kwargs: True
        task.pick_echo = lambda: True
        task.teleport_to_boss_enabled = lambda: teleport_enabled

        def teleport():
            task.teleports.append(True)
            task._just_entered_boss_realm = True

        task.teleport_to_configured_boss_and_prepare = teleport
        task.log_info = lambda message, **kwargs: task.logs.append(message)
        return task

    def test_realm_revive_exits_and_heals_only_when_teleport_enabled(self):
        task = FarmEchoTask.__new__(FarmEchoTask)
        task._in_realm = True
        with patch.object(BaseCombatTask, 'revive_action', return_value=True) as base_revive:
            task.teleport_to_boss_enabled = lambda: False
            self.assertFalse(task.revive_action())
            base_revive.assert_not_called()

            task.teleport_to_boss_enabled = lambda: True
            self.assertTrue(task.revive_action())
            base_revive.assert_called_once()

    def test_teleport_again_and_do_not_count_death_round(self):
        task = self.make_task(deaths=1, repeat=2)

        task.do_run()

        self.assertEqual(2, len(task.teleports))
        self.assertEqual(3, len(task.combat_calls))
        self.assertIn('farm 4c: death recovered, teleport to boss again', task.logs)

    def test_stop_after_max_recovery_retries(self):
        task = self.make_task(deaths=99, repeat=10)

        task.do_run()

        self.assertEqual(3, len(task.teleports))
        self.assertEqual(3, len(task.combat_calls))
        self.assertIn('farm 4c: exceeded recovery retries (3), stop farming', task.logs)

    def test_revive_without_teleport_still_stops_task(self):
        task = self.make_task(deaths=1, teleport_enabled=False)

        with self.assertRaises(CharRevivedException):
            task.do_run()
        self.assertEqual([], task.teleports)


if __name__ == '__main__':
    unittest.main()
