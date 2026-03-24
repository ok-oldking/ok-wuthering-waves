import unittest
from unittest.mock import MagicMock, patch

from ok import Box
from src.task.DailyTask import DailyTask


class TestDailyTaskLogic(unittest.TestCase):

    def make_task(self):
        task = DailyTask.__new__(DailyTask)
        task.config = {
            'Auto Farm all Nightmare Nest': False,
            'Farm Nightmare Nest for Daily Echo': False,
        }
        task.support_tasks = ["Tacet Suppression", "Forgery Challenge", "Simulation Challenge"]
        task.ensure_main = MagicMock()
        task.go_to_tower = MagicMock()
        task.open_daily = MagicMock()
        task.send_key = MagicMock()
        task.get_task_by_class = MagicMock()
        task.claim_daily = MagicMock()
        task.claim_mail = MagicMock()
        task.claim_battle_pass = MagicMock()
        task.sleep = MagicMock()
        task.info_set = MagicMock()
        task.log_info = MagicMock()
        task.log_debug = MagicMock()
        task.log_error = MagicMock()
        task.run_task_by_class = MagicMock()
        return task

    @patch('src.task.DailyTask.WWOneTimeTask.run', autospec=True)
    def test_claims_daily_reward_when_reward_is_already_ready(self, mock_base_run):
        task = self.make_task()
        task.open_daily.return_value = (180, True)

        task.run()

        mock_base_run.assert_called_once_with(task)
        task.claim_daily.assert_called_once()
        task.claim_mail.assert_called_once()
        task.claim_battle_pass.assert_called_once()
        task.get_task_by_class.assert_not_called()
        task.send_key.assert_not_called()

    def test_click_daily_reward_box_prefers_ocr_located_reward(self):
        task = self.make_task()
        task.ocr = MagicMock(return_value=[Box(2300, 1280, 70, 30, name='100')])
        task.click = MagicMock()

        result = task.click_daily_reward_box(100)

        self.assertTrue(result)
        task.click.assert_called_once()
        click_box = task.click.call_args.args[0]
        self.assertLess(click_box.y, 1280)
        self.assertGreater(click_box.height, 30)

    def test_click_daily_reward_box_falls_back_when_ocr_not_found(self):
        task = self.make_task()
        task.ocr = MagicMock(return_value=[])
        task.click = MagicMock()

        result = task.click_daily_reward_box(100)

        self.assertFalse(result)
        task.click.assert_called_once_with(0.90, 0.85, after_sleep=1)

    def test_claim_daily_skips_top_claim_click_when_points_already_ready(self):
        task = self.make_task()
        task.claim_daily = DailyTask.claim_daily.__get__(task, DailyTask)
        task.open_daily = MagicMock()
        task.get_total_daily_points = MagicMock(return_value=100)
        task.click = MagicMock()
        task.click_daily_reward_box = MagicMock()
        task.ensure_main = MagicMock()

        task.claim_daily()

        task.click.assert_not_called()
        task.ensure_main.assert_called_once_with(time_out=10)
        task.open_daily.assert_not_called()
        task.click_daily_reward_box.assert_called_once_with(100)


if __name__ == '__main__':
    unittest.main()
