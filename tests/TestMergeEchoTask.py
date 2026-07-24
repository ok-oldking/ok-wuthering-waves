import unittest
from unittest.mock import Mock, call

from config import key_config_option
from src.task.DailyTask import (
    ADDITIONAL_TASKS,
    AUTO_FARM_NIGHTMARE_NEST,
    CHECK_WEEKLY_GARDEN,
    MERGE_ECHO_IF_DISCARDED_OVER_1000,
    TELEPORT_AND_FARM_4C_ECHO,
    DailyTask,
)
from src.task.FarmEchoTask import FarmEchoTask
from src.task.MergeEchoTask import FULL_BATCH_PATTERN, MergeEchoTask
from src.task.NightmareNestTask import NightmareNestTask


class TestMergeEchoTask(unittest.TestCase):

    def test_echo_group_and_global_bag_hotkey_metadata(self):
        executor = Mock()
        executor.scene = None
        executor.global_config.get_config.return_value = {}
        app = Mock()

        merge_task = MergeEchoTask(executor, app)
        farm_task = FarmEchoTask(executor, app)

        self.assertEqual(merge_task.group_name, "Echo")
        self.assertEqual(farm_task.group_name, "Echo")
        self.assertNotIn("Bag Key", merge_task.default_config)
        self.assertEqual(key_config_option.default_config["Bag Key"], "b")
        self.assertIn("Bag Key", key_config_option.config_description)

    def setUp(self):
        self.task = MergeEchoTask.__new__(MergeEchoTask)
        self.task.key_config = {"Bag Key": "v"}
        self.task.ensure_main = Mock()
        self.task.send_key = Mock()
        self.task.in_team_and_world = Mock(return_value=False)
        self.task.wait_until = Mock(
            side_effect=lambda predicate, **kwargs: predicate()
        )
        self.task.sleep = Mock()
        self.task.wait_click_skip_dialog_confirm = Mock(return_value=True)
        self.task.click_relative = Mock()
        self.task.ocr = Mock(return_value=[])
        self.task.log_info = Mock()
        self.task.log_error = Mock()
        self.task.notify_if_not_enough = True

    def test_stops_when_selected_echoes_do_not_fill_a_batch(self):
        self.task.run()

        self.assertEqual(self.task.ensure_main.call_count, 2)
        self.task.send_key.assert_called_once_with("v")
        predicate = self.task.wait_until.call_args.args[0]
        self.assertTrue(predicate())
        self.assertEqual(
            self.task.wait_until.call_args.kwargs,
            {"time_out": 5, "raise_if_not_found": False},
        )
        self.task.ocr.assert_called_once_with(
            0.670,
            0.660,
            0.895,
            0.958,
            match=FULL_BATCH_PATTERN,
        )
        self.assertEqual(
            self.task.click_relative.call_args_list,
            [
                call(0.602, 0.124, after_sleep=0.5),
                call(0.520, 0.904, after_sleep=2),
                call(0.041, 0.918, after_sleep=1),
                call(0.826, 0.840, after_sleep=0.5),
                call(0.717, 0.204, after_sleep=0.5),
                call(0.041, 0.918, after_sleep=0.5),
                call(0.310, 0.915, after_sleep=0.5),
            ],
        )

    def test_merges_full_batches_until_less_than_100_remain(self):
        self.task.wait_click_skip_dialog_confirm.side_effect = [
            True,
            False,
        ]
        self.task.ocr.side_effect = [[object()], []]

        self.task.run()

        self.assertEqual(
            self.task.wait_click_skip_dialog_confirm.call_args_list,
            [call(), call()],
        )
        self.assertEqual(self.task.sleep.call_args_list, [call(1), call(2), call(3)])
        self.assertEqual(
            self.task.click_relative.call_args_list[-4:],
            [
                call(0.310, 0.915, after_sleep=0.5),
                call(0.782, 0.910),
                call(0.496, 0.972, after_sleep=1),
                call(0.310, 0.915, after_sleep=0.5),
            ],
        )
        self.assertEqual(self.task.ocr.call_count, 2)
        self.assertEqual(self.task.ensure_main.call_count, 2)

    def test_alerts_and_stops_when_bag_hotkey_fails(self):
        self.task.wait_until = Mock(return_value=False)

        self.task.run()

        self.task.log_error.assert_called_once_with(
            "can not open bag with hotkey v",
            notify=True,
        )
        self.task.sleep.assert_not_called()
        self.task.wait_click_skip_dialog_confirm.assert_not_called()
        self.task.click_relative.assert_not_called()
        self.assertEqual(self.task.ensure_main.call_count, 1)

    def test_alerts_and_returns_to_main_when_1000_echo_dialog_is_absent(self):
        self.task.wait_click_skip_dialog_confirm.return_value = False

        self.task.run()

        self.task.log_error.assert_called_once_with(
            "Must have 1000 discarded Echo to Run",
            notify=True,
        )
        self.assertEqual(self.task.ensure_main.call_count, 2)
        self.task.click_relative.assert_not_called()
        self.task.ocr.assert_not_called()

    def test_quietly_returns_when_not_enough_notification_is_disabled(self):
        self.task.wait_click_skip_dialog_confirm.return_value = False
        self.task.notify_if_not_enough = False

        self.task.run()

        self.task.log_error.assert_not_called()
        self.assertEqual(self.task.ensure_main.call_count, 2)
        self.task.click_relative.assert_not_called()
        self.task.ocr.assert_not_called()


class TestDailyMergeEchoTask(unittest.TestCase):

    def test_daily_additional_tasks_metadata(self):
        executor = Mock()
        executor.scene = None
        executor.global_config.get_config.return_value = {}

        daily_task = DailyTask(executor, Mock())

        self.assertEqual(daily_task.default_config[ADDITIONAL_TASKS], [CHECK_WEEKLY_GARDEN])
        self.assertEqual(
            daily_task.config_type[ADDITIONAL_TASKS],
            {
                "type": "multi_selection",
                "options": [
                    CHECK_WEEKLY_GARDEN,
                    AUTO_FARM_NIGHTMARE_NEST,
                    MERGE_ECHO_IF_DISCARDED_OVER_1000,
                    TELEPORT_AND_FARM_4C_ECHO,
                ],
            },
        )
        self.assertNotIn("Continue Farm After Daily", daily_task.default_config)
        self.assertNotIn(CHECK_WEEKLY_GARDEN, daily_task.default_config)
        self.assertNotIn(AUTO_FARM_NIGHTMARE_NEST, daily_task.default_config)
        self.assertNotIn(MERGE_ECHO_IF_DISCARDED_OVER_1000, daily_task.default_config)

    def test_daily_runs_only_post_daily_selected_tasks(self):
        daily_task = DailyTask.__new__(DailyTask)
        daily_task.config = {
            ADDITIONAL_TASKS: [
                CHECK_WEEKLY_GARDEN,
                AUTO_FARM_NIGHTMARE_NEST,
                MERGE_ECHO_IF_DISCARDED_OVER_1000,
                TELEPORT_AND_FARM_4C_ECHO,
            ],
        }
        daily_task.check_weekly_garden = Mock()
        daily_task.check_discarded_echo = Mock()
        daily_task.run_task_by_class = Mock()

        daily_task.run_additional_tasks()

        daily_task.check_weekly_garden.assert_called_once_with()
        daily_task.check_discarded_echo.assert_called_once_with()
        self.assertEqual(
            daily_task.run_task_by_class.call_args_list,
            [call(FarmEchoTask)],
        )

    def test_daily_suppresses_and_restores_not_enough_echo_notification(self):
        daily_task = DailyTask.__new__(DailyTask)
        daily_task.info_set = Mock()
        daily_task.log_info = Mock()
        merge_echo_task = Mock()
        merge_echo_task.notify_if_not_enough = True
        daily_task.get_task_by_class = Mock(return_value=merge_echo_task)

        def assert_notification_suppressed(task_class):
            self.assertIs(task_class, MergeEchoTask)
            self.assertFalse(merge_echo_task.notify_if_not_enough)

        daily_task.run_task_by_class = Mock(side_effect=assert_notification_suppressed)

        daily_task.check_discarded_echo()

        daily_task.run_task_by_class.assert_called_once_with(MergeEchoTask)
        self.assertTrue(merge_echo_task.notify_if_not_enough)

    def test_daily_rejects_farm_echo_without_teleport(self):
        daily_task = DailyTask.__new__(DailyTask)
        daily_task.config = {ADDITIONAL_TASKS: [TELEPORT_AND_FARM_4C_ECHO]}
        farm_echo_task = Mock()
        farm_echo_task.config = {"Teleport to Boss": "No"}
        daily_task.get_task_by_class = Mock(return_value=farm_echo_task)
        daily_task.log_error = Mock()
        daily_task.tr = lambda message: message

        self.assertFalse(daily_task.validate_additional_tasks())
        daily_task.log_error.assert_called_once_with(
            'Teleport and Farm 4C Echo requires "Teleport to Boss" to be enabled in Farm Echo Task.',
            notify=True,
        )

    def test_daily_rejects_nightmare_without_selection(self):
        daily_task = DailyTask.__new__(DailyTask)
        daily_task.config = {ADDITIONAL_TASKS: [AUTO_FARM_NIGHTMARE_NEST]}
        nightmare_task = Mock()
        nightmare_task.config = {"Which to Farm": []}
        daily_task.get_task_by_class = Mock(return_value=nightmare_task)
        daily_task.log_error = Mock()
        daily_task.tr = lambda message: message

        self.assertFalse(daily_task.validate_additional_tasks())
        daily_task.log_error.assert_called_once_with(
            'Auto Farm all Nightmare Nest requires at least one "Which to Farm" option.',
            notify=True,
        )

    def test_daily_accepts_valid_additional_task_configs(self):
        daily_task = DailyTask.__new__(DailyTask)
        daily_task.config = {
            ADDITIONAL_TASKS: [TELEPORT_AND_FARM_4C_ECHO, AUTO_FARM_NIGHTMARE_NEST],
        }
        farm_echo_task = Mock()
        farm_echo_task.config = {"Teleport to Boss": "Boss Challenge"}
        nightmare_task = Mock()
        nightmare_task.config = {"Which to Farm": ["Nightmare Purification"]}
        daily_task.get_task_by_class = Mock(
            side_effect=lambda task_class: {
                FarmEchoTask: farm_echo_task,
                NightmareNestTask: nightmare_task,
            }[task_class],
        )
        daily_task.log_error = Mock()

        self.assertTrue(daily_task.validate_additional_tasks())
        daily_task.log_error.assert_not_called()

    def test_daily_stops_before_initialization_when_additional_config_is_invalid(self):
        daily_task = DailyTask.__new__(DailyTask)
        daily_task.validate_additional_tasks = Mock(return_value=False)
        daily_task.ensure_main = Mock()

        daily_task.run()

        daily_task.ensure_main.assert_not_called()


if __name__ == "__main__":
    unittest.main()
