import unittest
from unittest.mock import MagicMock, patch

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

    def test_click_daily_reward_box_uses_fallback_coordinate(self):
        task = self.make_task()
        task.click = MagicMock()

        result = task.click_daily_reward_box(100)

        self.assertFalse(result)
        task.click.assert_called_once_with(0.93, 0.88, after_sleep=1)

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

    def test_claim_daily_logs_error_and_continues_when_points_still_low(self):
        task = self.make_task()
        task.claim_daily = DailyTask.claim_daily.__get__(task, DailyTask)
        task.open_daily = MagicMock()
        task.get_total_daily_points = MagicMock(side_effect=[0, 0])
        task.click = MagicMock()
        task.click_daily_reward_box = MagicMock()
        task.ensure_main = MagicMock()
        task.log_error = MagicMock()

        result = task.claim_daily()

        self.assertFalse(result)
        task.ensure_main.assert_called_once_with(time_out=5)
        task.open_daily.assert_called_once()
        task.click.assert_called_once_with(0.87, 0.17, after_sleep=0.5)
        task.click_daily_reward_box.assert_not_called()
        task.log_error.assert_called_once_with("Can't complete daily task, may need to increase stamina manually!")


if __name__ == '__main__':
    unittest.main()
