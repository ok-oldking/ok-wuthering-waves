import unittest

from ok.task.task import BaseTask
from src.task.BaseWWTask import BaseWWTask
from src.task.DailyTask import ADDITIONAL_TASKS, TELEPORT_AND_FARM_4C_ECHO, DailyTask
from src.task.FarmEchoTask import FarmEchoTask


class FakeFarmEchoTask:
    """Picks one echo as soon as it runs."""

    incr_drop = BaseWWTask.incr_drop

    def __init__(self):
        self.start_time = 0  # ok-script default; only the executor sets it when it starts a task
        self.info = {}

    def run(self):
        self.incr_drop(True)


class FakeDailyTask:
    run_additional_tasks = DailyTask.run_additional_tasks
    run_task_by_class = BaseTask.run_task_by_class

    def __init__(self):
        self.config = {ADDITIONAL_TASKS: [TELEPORT_AND_FARM_4C_ECHO]}
        self.info = {}
        self.farm_echo_task = FakeFarmEchoTask()

    def get_task_by_class(self, cls):
        assert cls is FarmEchoTask
        return self.farm_echo_task

    def log_info(self, *args, **kwargs):
        """No-op: logging is irrelevant to the assertions."""


class TestDailyTaskEchoRate(unittest.TestCase):

    def test_echo_per_hour_counts_from_the_4c_start(self):
        daily = FakeDailyTask()

        daily.run_additional_tasks()

        # one echo right after the 4C start; before the fix the rate was
        # measured from 1970 and rounded to 0
        self.assertEqual(1, daily.info['Echo Count'])
        self.assertEqual(3600, daily.info['Echo per Hour'])


if __name__ == '__main__':
    unittest.main()
