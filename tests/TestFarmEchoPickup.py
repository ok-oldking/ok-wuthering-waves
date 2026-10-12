import unittest
from unittest.mock import Mock, call

from src.task.FarmEchoTask import FarmEchoTask
from src.task.BaseWWTask import BaseWWTask


def make_task(config=None):
    task = FarmEchoTask.__new__(FarmEchoTask)
    task.config = config or {}
    task.info = {}
    task.combat_wait_time = 0
    task.bypass_end_wait = True
    task._in_realm = False
    task._has_treasure = False
    task._just_entered_boss_realm = True
    task.is_revived = False
    task.yolo_time_out = 8
    task.yolo_threshold = 0.5
    task.logger = Mock()
    for name in (
        'in_realm', 'manage_boss_parameters', 'init_parameters', 'teleport_to_boss_enabled',
        'teleport_to_configured_boss_and_prepare', 'in_realm_check', 'manage_boss_interactions',
        'in_combat', 'check_boss_name', 'combat_once', 'pick_echo', 'middle_click',
        'yolo_find_echo', 'run_in_circle_to_find_echo', 'walk_find_echo',
        'back_and_forth_find_echo', 'incr_drop', 'sleep', 'log_info', 'log_debug'
    ):
        setattr(task, name, Mock())
    task.in_realm.return_value = False
    task.teleport_to_boss_enabled.return_value = False
    task.in_combat.return_value = True
    return task


class TestFarmEchoPickup(unittest.TestCase):

    def test_pick_echo_on_face_skips_middle_click(self):
        task = make_task({"Repeat Farm Count": 1})
        task.pick_echo.return_value = True

        task.do_run()

        task.pick_echo.assert_called_once()
        task.middle_click.assert_not_called()
        task.incr_drop.assert_called_once_with(True)

    def test_pick_echo_failure_triggers_middle_click_before_movement(self):
        task = make_task({"Repeat Farm Count": 1, "Echo Pickup Method": "Run in Circle"})
        task.pick_echo.return_value = False
        task.run_in_circle_to_find_echo.return_value = True
        steps = Mock()
        steps.attach_mock(task.middle_click, 'middle_click')
        steps.attach_mock(task.run_in_circle_to_find_echo, 'run_in_circle_to_find_echo')

        task.do_run()

        self.assertEqual(
            [call.middle_click(after_sleep=0.2), call.run_in_circle_to_find_echo(circle_count=2)],
            steps.mock_calls
        )
        task.incr_drop.assert_called_once_with(True)

    def test_pick_echo_failure_triggers_middle_click_before_yolo(self):
        task = make_task({"Repeat Farm Count": 1, "Echo Pickup Method": "Yolo"})
        task.pick_echo.return_value = False
        task.yolo_find_echo.return_value = (True, False)
        steps = Mock()
        steps.attach_mock(task.middle_click, 'middle_click')
        steps.attach_mock(task.yolo_find_echo, 'yolo_find_echo')

        task.do_run()

        self.assertEqual(
            [
                call.middle_click(after_sleep=0.2),
                call.yolo_find_echo(turn=False, use_color=False, time_out=8, threshold=0.5)
            ],
            steps.mock_calls
        )
        task.incr_drop.assert_called_once_with(True)

    def test_pick_echo_failure_triggers_middle_click_before_back_and_forth(self):
        task = make_task({"Repeat Farm Count": 1, "Echo Pickup Method": "Back and Forth"})
        task.pick_echo.return_value = False
        task.back_and_forth_find_echo.return_value = True
        steps = Mock()
        steps.attach_mock(task.middle_click, 'middle_click')
        steps.attach_mock(task.back_and_forth_find_echo, 'back_and_forth_find_echo')

        task.do_run()

        self.assertEqual(
            [call.middle_click(after_sleep=0.2), call.back_and_forth_find_echo()],
            steps.mock_calls
        )
        task.incr_drop.assert_called_once_with(True)

    def test_back_and_forth_find_echo_forward_success(self):
        task = BaseWWTask.__new__(BaseWWTask)
        task.absorb_echo_text = Mock(return_value="Echo")
        task.find_f_with_text = Mock(return_value=False)
        task.send_key_and_wait_f = Mock(return_value=True)
        task.pick_f = Mock(return_value=True)
        task.pick_echo = Mock(return_value=False)

        res = BaseWWTask.back_and_forth_find_echo(task, forward_time=2.0, backward_time=4.0)

        self.assertTrue(res)
        task.send_key_and_wait_f.assert_called_once_with(
            'w', raise_if_not_found=False, time_out=2.0, target_text="Echo", check_combat=True
        )

    def test_back_and_forth_find_echo_backward_success(self):
        task = BaseWWTask.__new__(BaseWWTask)
        task.absorb_echo_text = Mock(return_value="Echo")
        task.find_f_with_text = Mock(return_value=False)
        task.send_key_and_wait_f = Mock(side_effect=[False, True])
        task.pick_f = Mock(return_value=True)
        task.pick_echo = Mock(return_value=False)

        res = BaseWWTask.back_and_forth_find_echo(task, forward_time=2.0, backward_time=4.0)

        self.assertTrue(res)
        self.assertEqual(
            [
                call('w', raise_if_not_found=False, time_out=2.0, target_text="Echo", check_combat=True),
                call('s', raise_if_not_found=False, time_out=4.0, target_text="Echo", check_combat=True),
            ],
            task.send_key_and_wait_f.mock_calls
        )


if __name__ == '__main__':
    unittest.main()
