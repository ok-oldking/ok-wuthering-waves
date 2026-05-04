import unittest
from unittest.mock import MagicMock

from src.task.FarmEchoTask import FarmEchoTask


class TestFarmEchoFlow(unittest.TestCase):

    def make_task(self):
        task = FarmEchoTask.__new__(FarmEchoTask)
        task.log_info = MagicMock()
        task.send_key = MagicMock()
        task.wait_click_feature = MagicMock()
        task.sleep = MagicMock()
        task.wait_until = MagicMock()
        task.in_combat = MagicMock(return_value=False)
        task.find_treasure_icon = MagicMock(return_value=False)
        task.find_f_with_text = MagicMock(return_value=False)
        return task

    def test_restart_realm_challenge_clicks_restart_and_waits_for_next_state(self):
        task = self.make_task()

        result = task.restart_realm_challenge()

        self.assertTrue(result)
        task.send_key.assert_called_once_with('esc', after_sleep=0.5)
        task.wait_click_feature.assert_called_once()
        task.sleep.assert_called_once_with(1)
        task.wait_until.assert_called_once()

    def test_collect_realm_echo_and_restart_collects_before_restart(self):
        task = self.make_task()
        task.config = {'Echo Pickup Method': 'Walk'}
        task._in_realm = True
        task.yolo_time_out = 8
        task.yolo_threshold = 0.5
        task.pick_echo = MagicMock(return_value=False)
        task.walk_find_echo = MagicMock(return_value=True)
        task.incr_drop = MagicMock()
        task.restart_realm_challenge = MagicMock(return_value=True)

        result = task.collect_realm_echo_and_restart()

        self.assertTrue(result)
        task.pick_echo.assert_called_once()
        task.walk_find_echo.assert_called_once_with(time_out=2, backward_time=1)
        task.incr_drop.assert_called_once_with(True)
        task.restart_realm_challenge.assert_called_once()

    def test_realm_drop_should_restart_without_extra_search_cycle(self):
        task = self.make_task()
        task._in_realm = True
        task.incr_drop = MagicMock()
        task.restart_realm_challenge = MagicMock()

        dropped = True
        task.incr_drop(dropped)
        if task._in_realm and dropped:
            task.restart_realm_challenge()

        task.incr_drop.assert_called_once_with(True)
        task.restart_realm_challenge.assert_called_once()


if __name__ == '__main__':
    unittest.main()
