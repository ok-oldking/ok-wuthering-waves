import unittest
from unittest.mock import Mock, patch

from ok.task.exceptions import WaitFailedException

from src.task.BaseCombatTask import BaseCombatTask, CharRevivedException
from src.task.DomainTask import DomainTask
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


def record_heal_point(task, name):
    flags = []
    original = getattr(task, name)

    def wrapper(*args, **kwargs):
        flags.append(task.realm_entry_at_heal_point)
        return original(*args, **kwargs)

    setattr(task, name, wrapper)
    return flags


class TestTacetDeathReentry(unittest.TestCase):

    def make_task(self, deaths):
        task = TacetTask.__new__(TacetTask)
        task.stamina_once = 60
        task.tr = str
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

        self.assertEqual(60, task.farm_tacet(config={'Which Tacet Suppression to Farm': 1}))

        self.assertEqual([0, 0], task.teleports)
        self.assertEqual(2, len(task.combat_calls))
        self.assertIn('farm_tacet: death recovered, re-enter from F2 book', task.logs)

    def test_stop_after_max_recovery_retries(self):
        task = self.make_task(deaths=99)

        self.assertEqual(0, task.farm_tacet(config={'Which Tacet Suppression to Farm': 1}))

        self.assertEqual(3, len(task.teleports))
        self.assertEqual(3, len(task.combat_calls))
        self.assertIn('farm_tacet: exceeded recovery retries (3), stop farming', task.logs)

    def test_heal_point_set_only_after_recovery(self):
        task = self.make_task(deaths=2)
        task.realm_entry_at_heal_point = True  # 上一次运行的残留
        flags = record_heal_point(task, 'combat_once')

        task.farm_tacet(config={'Which Tacet Suppression to Farm': 1})

        self.assertEqual([False, True, True], flags)

    def test_rechallenge_clicks_detected_button_without_teleporting_again(self):
        task = self.make_task(deaths=0)
        task.use_stamina = Mock(side_effect=[(True, 120), (False, 120)])
        task.wait_until = lambda condition, **kwargs: condition()
        rechallenge_button = Mock()
        task.ocr = Mock(return_value=[rechallenge_button])
        task.click = Mock()
        task.click_relative = Mock()

        stamina_spent = task.farm_tacet(config={'Which Tacet Suppression to Farm': 1})

        self.assertEqual(240, stamina_spent)
        self.assertEqual([0], task.teleports)
        self.assertEqual(2, len(task.combat_calls))
        task.click.assert_called_once_with(rechallenge_button, after_sleep=0.2)
        task.click_relative.assert_called_once_with(0.365, 0.853, hcenter=True)

    def test_resumes_active_arena_when_combat_stopped_before_reward(self):
        task = self.make_task(deaths=0)
        task.walk_to_treasure = Mock(side_effect=[WaitFailedException(), None])
        task.in_realm = Mock(return_value=True)
        task.wait_combat = Mock(return_value=True)

        self.assertEqual(60, task.farm_tacet(config={'Which Tacet Suppression to Farm': 1}))
        self.assertEqual([0], task.teleports)
        self.assertEqual(2, len(task.combat_calls))

    def test_missing_reward_without_active_combat_still_fails(self):
        task = self.make_task(deaths=0)
        task.walk_to_treasure = Mock(side_effect=WaitFailedException())
        task.in_realm = Mock(return_value=True)
        task.wait_combat = Mock(return_value=False)

        with self.assertRaises(WaitFailedException):
            task.farm_tacet(config={'Which Tacet Suppression to Farm': 1})

        self.assertEqual(1, len(task.combat_calls))


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

    def test_heal_point_set_only_after_recovery(self):
        task = self.make_task(deaths=2, repeat=1)
        task.realm_entry_at_heal_point = True  # 上一次运行的残留
        flags = record_heal_point(task, 'combat_once')

        task.do_run()

        self.assertEqual([False, True, True], flags)

    def test_walk_in_boss_entry_clears_heal_point(self):
        for is_team, expected in ((True, True), (False, False)):
            with self.subTest(is_team=is_team):
                task = FarmEchoTask.__new__(FarmEchoTask)
                task.config = {'Teleport to Boss': 'Boss Challenge', 'Which Boss Challenge to Teleport': 1}
                task.total_boss_number = 20
                task.realm_entry_at_heal_point = True
                noop = lambda *args, **kwargs: None
                for name in ('ensure_main', 'info_set', 'openF2Book', 'open_boss_book', 'click_team_challenge',
                             'wait_click_travel', 'wait_in_team_and_world', 'sleep'):
                    setattr(task, name, noop)
                task.click_on_book_target = lambda *args: is_team

                task.teleport_to_configured_boss()

                self.assertEqual(expected, task.realm_entry_at_heal_point)


class TestDomainHealPoint(unittest.TestCase):

    def test_heal_point_set_only_after_recovery(self):
        task = DomainTask.__new__(DomainTask)
        task.stamina_once = 40
        task.tr = str
        task.realm_entry_at_heal_point = True  # 上一次运行的残留
        task.open_F2_book_and_get_stamina = lambda: (120, 0, 120)
        task.sleep = task.log_info = lambda *args, **kwargs: None
        task.info_incr = task.pick_f = task.walk_to_treasure = task.click = Mock()
        task.make_sure_in_world = Mock()
        task.walk_until_f = Mock(return_value=True)
        task.combat_once = Mock(side_effect=[CharRevivedException(), CharRevivedException(), True])
        task.use_stamina = Mock(return_value=(False, 40))
        flags = record_heal_point(task, 'combat_once')

        task.farm_domain_with_recovery_loop(0, lambda: None)

        self.assertEqual([False, True, True], flags)

    def test_missing_rechallenge_prompt_reenters_with_remaining_budget(self):
        task = DomainTask.__new__(DomainTask)
        task.stamina_once = 40
        task.tr = str
        task.open_F2_book_and_get_stamina = Mock(side_effect=[(120, 100, 220), (40, 100, 140)])
        for name in ('sleep', 'log_info', 'info_incr', 'pick_f', 'walk_to_treasure',
                     'click', 'make_sure_in_world', 'combat_once', 'rechallenge_domain'):
            setattr(task, name, Mock())
        task.walk_until_f = Mock(side_effect=[True, False, True])
        task.use_stamina = Mock(side_effect=[(True, 80), (False, 40)])
        enter = Mock(side_effect=lambda: self.assertFalse(task.realm_entry_at_heal_point))

        task.farm_domain_with_recovery_loop(120, enter)

        self.assertEqual(2, enter.call_count)
        self.assertEqual(2, task.combat_once.call_count)
        self.assertEqual([120, 40], [call.kwargs['must_use'] for call in task.use_stamina.call_args_list])
        self.assertEqual([True, False, True],
                         [call.kwargs['raise_if_not_found'] for call in task.walk_until_f.call_args_list])
        task.rechallenge_domain.assert_called_once()
        self.assertEqual(2, task.make_sure_in_world.call_count)


class TestReviveAtHealPoint(unittest.TestCase):

    def make_task(self, cls, heal_point, in_realm=True):
        task = cls.__new__(cls)
        task.realm_entry_at_heal_point = heal_point
        task.teleport_timeout = 100
        task.exits = []
        task.teleports = []
        noop = lambda *args, **kwargs: True
        for name in ('close_revive_popup', 'send_key', 'sleep', 'wait_click_feature', 'wait_in_team_and_world'):
            setattr(task, name, noop)
        task.in_realm = lambda: in_realm
        task.ensure_main = lambda *args, **kwargs: task.exits.append(True)
        task.revive_at_tower_and_heal = lambda: task.teleports.append(True)
        return task

    def test_base_revive_skips_teleport_when_realm_entry_at_heal_point(self):
        for heal_point, in_realm, teleports in ((True, True, 0), (False, True, 1), (True, False, 1)):
            with self.subTest(heal_point=heal_point, in_realm=in_realm):
                task = self.make_task(TacetTask, heal_point, in_realm)

                self.assertTrue(task.revive_action())

                self.assertEqual(teleports, len(task.teleports))
                self.assertEqual(1 - teleports, len(task.exits))  # 跳过传送时仍要退本

    def test_domain_revive_skips_teleport_when_realm_entry_at_heal_point(self):
        for heal_point, teleports in ((True, 0), (False, 1)):
            with self.subTest(heal_point=heal_point):
                task = self.make_task(DomainTask, heal_point)

                self.assertTrue(task.revive_action())

                self.assertEqual(teleports, len(task.teleports))


if __name__ == '__main__':
    unittest.main()
