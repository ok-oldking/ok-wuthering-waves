import time
import unittest
from config import config
from ok.test.TaskTestCase import TaskTestCase
from src.task.AutoCombatTask import AutoCombatTask
from src.task.DailyTask import DailyTask

config['debug'] = True


class TestEcho(TaskTestCase):
    task_class = DailyTask
    config = config

    def test_find_echo(self):
        self.set_image('tests/images/echo.png')
        echos = self.task.find_echos(threshold=0.3)
        self.task.log_info('Found1 {} echos'.format(len(echos)))
        self.assertEqual(1, len(echos))
        time.sleep(1)
        self.task.screenshot('echo1', show_box=True)
        self.set_image('tests/images/echo2.png')
        echos = self.task.find_echos()
        self.task.log_info('Found2 {} echos'.format(len(echos)))
        time.sleep(1)
        self.task.screenshot('echo2', show_box=True)
        self.assertEqual(1, len(echos))
        time.sleep(1)


if __name__ == '__main__':
    unittest.main()
