"""Nightmare Nest: retry the lock in place, then skip the nest if still lost.

- Enemies such as Shuangji fly out of the nest area; the task must not chase
  them all the way out.
- When the lock fails, retry in place N times, then move to the next nest.
- If the enemy really died (an F pickup prompt is present), pick up as usual
  and do not treat it as a lost target.
- With retries disabled (the default outside this task), behaviour is unchanged.
"""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from src.combat.CombatCheck import CombatCheck
from src.task.NightmareNestTask import NestTarget, NightmareNestTask


class LockSettingsTest(unittest.TestCase):

    def test_defaults_are_five_seconds_and_two_retries(self):
        task = NightmareNestTask.__new__(NightmareNestTask)
        task.config = {}
        task._apply_lock_settings()
        self.assertEqual(task.target_enemy_time_out, 5)
        self.assertEqual(task.target_enemy_retry_timeout, 5)
        self.assertEqual(task.target_enemy_retry_count, 2)
        self.assertFalse(task.target_lost_give_up)

    def test_config_is_clamped_and_bad_values_fall_back(self):
        task = NightmareNestTask.__new__(NightmareNestTask)
        task.config = {'Lock Retry Timeout (s)': '999', 'Lock Retries': 'not-a-number'}
        task._apply_lock_settings()
        self.assertEqual(task.target_enemy_time_out, 60)
        self.assertEqual(task.target_enemy_retry_count, 2)


class RetryTargetTest(unittest.TestCase):

    def make_check(self, retries=2, timeout=5):
        check = CombatCheck.__new__(CombatCheck)
        check.target_enemy_retry_count = retries
        check.target_enemy_retry_timeout = timeout
        check.target_lost_give_up = False
        check._target_retried_this_episode = False
        check.log_warning = Mock()
        check.tr = lambda text: text
        check.sleep = Mock()
        check.target_enemy = Mock(return_value=False)
        return check

    def test_retry_stops_on_success(self):
        check = self.make_check()
        check.target_enemy.side_effect = [False, True]
        self.assertTrue(check._retry_target_before_give_up())
        self.assertEqual(check.target_enemy.call_count, 2)
        self.assertEqual(check.target_enemy.call_args.kwargs['time_out'], 5)
        self.assertFalse(check.target_lost_give_up)

    def test_give_up_after_all_retries_fail(self):
        check = self.make_check(retries=3)
        self.assertFalse(check._retry_target_before_give_up())
        self.assertEqual(check.target_enemy.call_count, 3)
        self.assertTrue(check.target_lost_give_up)

    def test_no_retry_when_disabled(self):
        check = self.make_check(retries=0)
        self.assertFalse(check._retry_target_before_give_up())
        check.target_enemy.assert_not_called()
        self.assertFalse(check.target_lost_give_up)

    def test_only_one_retry_round_per_lost_target(self):
        check = self.make_check()
        check._retry_target_before_give_up()
        first_count = check.target_enemy.call_count
        check._retry_target_before_give_up()
        self.assertEqual(check.target_enemy.call_count, first_count)


class NestSkipTest(unittest.TestCase):

    def make_task(self, loot=False):
        task = NightmareNestTask.__new__(NightmareNestTask)
        task._capture_mode = False
        task.target_lost_give_up = False
        task.config = {}
        task.log_info = Mock()
        task.tr = lambda text: text
        task.esc_world_confirm = Mock()
        task.click = Mock()
        task.sleep = Mock()
        task.next_frame = Mock()
        task.run_until = Mock()
        task.wait_feature = Mock(return_value=SimpleNamespace(name='gray_teleport'))
        task._travel_to_nest_or_skip = Mock(return_value=True)
        # With loot: first hit -> pick up -> no more; the lost-target check
        # then sees loot again, proving a real kill is not treated as lost.
        task.find_f_with_text = Mock(side_effect=[True, False, True] if loot else [False, False])
        task.send_key = Mock()
        task.wait_in_team_and_world = Mock(return_value=True)
        task.walk_find_echo = Mock(return_value=True)
        task._should_continue_combat_after_pickup = Mock(return_value=False)

        def _lose_target(**_kwargs):
            task.target_lost_give_up = True
            return True

        task.combat_once = _lose_target
        return task

    def test_target_lost_without_loot_skips_nest(self):
        task = self.make_task(loot=False)
        task.combat_nest(NestTarget(box=object(), cache_key='nest-a'))
        task.next_frame.assert_called()
        task.esc_world_confirm.assert_not_called()
        messages = [str(call) for call in task.log_info.call_args_list]
        self.assertTrue(any('跳过当前聚落' in text for text in messages), messages)

    def test_enemy_died_with_loot_still_picks_up(self):
        task = self.make_task(loot=True)
        task.combat_nest(NestTarget(box=object(), cache_key='nest-b'))
        messages = [str(call) for call in task.log_info.call_args_list]
        self.assertFalse(any('跳过当前聚落' in text for text in messages), messages)
        self.assertFalse(task.target_lost_give_up)


if __name__ == '__main__':
    unittest.main(verbosity=2)
