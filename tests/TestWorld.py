import unittest
from config import config
from ok.test.TaskTestCase import TaskTestCase
from src.task.DailyTask import DailyTask
from src.task.FiveToOneTask import FiveToOneTask

config['debug'] = True


class TestWorld(TaskTestCase):
    task_class = DailyTask
    config = config

    def test_in_world(self):
        self.task.do_reset_to_false()
        self.set_image('tests/images/all_cd_1080p.png')
        self.assertFalse(bool(self.task.in_realm()))
        in_world = self.task.in_world()
        self.logger.info(f'in_world = {in_world}')
        self.assertIsNotNone(in_world)


if __name__ == '__main__':
    unittest.main()
