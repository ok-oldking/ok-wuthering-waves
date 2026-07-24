import unittest
from unittest.mock import Mock, call

from config import key_config_option
from src.task.DailyTask import DailyTask
from src.task.FarmEchoTask import FarmEchoTask
from src.task.MergeEchoTask import FULL_BATCH_PATTERN, MergeEchoTask


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


class TestDailyMergeEchoTask(unittest.TestCase):

    def test_daily_option_defaults_to_false(self):
        executor = Mock()
        executor.scene = None
        executor.global_config.get_config.return_value = {}

        daily_task = DailyTask(executor, Mock())

        self.assertFalse(daily_task.default_config["Check Discarded Echo"])

    def test_daily_skips_discarded_echo_check_when_disabled(self):
        daily_task = DailyTask.__new__(DailyTask)
        daily_task.config = {"Check Discarded Echo": False}
        daily_task.run_task_by_class = Mock()

        daily_task.check_discarded_echo()

        daily_task.run_task_by_class.assert_not_called()

    def test_daily_runs_merge_echo_task_when_enabled(self):
        daily_task = DailyTask.__new__(DailyTask)
        daily_task.config = {"Check Discarded Echo": True}
        daily_task.info_set = Mock()
        daily_task.log_info = Mock()
        daily_task.run_task_by_class = Mock()

        daily_task.check_discarded_echo()

        daily_task.run_task_by_class.assert_called_once_with(MergeEchoTask)


if __name__ == "__main__":
    unittest.main()
