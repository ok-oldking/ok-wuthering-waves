import unittest
from config import config
from ok.test.TaskTestCase import TaskTestCase
from src.task.DailyTask import DailyTask
from src.task.FarmEchoTask import FarmEchoTask
from src.task.FiveToOneTask import FiveToOneTask

config['debug'] = True


class TestWorld(TaskTestCase):
    task_class = FarmEchoTask
    config = config

    def test_find_boss_check_mark(self):
        self.set_image('tests/images/teleport_boss.png')
        box = self.task.find_boss_check_mark()
        self.logger.info(f'box = {box}')
        self.assertTrue(bool(box))


if __name__ == '__main__':
    unittest.main()
