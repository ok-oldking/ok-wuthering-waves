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
        self.assertTrue(is_0_level)

    def test_find_add_mat(self):
        self.set_image('tests/images/find_add_mat.png')
        find_add_mat = self.task.find_add_mat()
        self.task.screenshot('find_add_mat.png', show_box=True)
        time.sleep(1)
        self.assertTrue(find_add_mat)


if __name__ == '__main__':
    unittest.main()
