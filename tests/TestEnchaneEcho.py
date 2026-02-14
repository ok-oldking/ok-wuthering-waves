import time
import unittest
from config import config
from ok.test.TaskTestCase import TaskTestCase
from src.task.AutoCombatTask import AutoCombatTask
from src.task.EnhanceEchoTask import EnhanceEchoTask

config['debug'] = True


class TestEnchaneEcho(TaskTestCase):
    task_class = EnhanceEchoTask
    config = config

    def test_0_level(self):
        self.set_image('tests/images/echo_enhance.png')
        is_0_level = self.task.is_0_level()
        self.task.screenshot('in_combat.png', show_box=True)
        time.sleep(1)
        self.assertTrue(is_0_level)


if __name__ == '__main__':
    unittest.main()
