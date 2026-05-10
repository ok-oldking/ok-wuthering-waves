import unittest
from config import config
from ok.test.TaskTestCase import TaskTestCase
from src.task.AutoCombatTask import AutoCombatTask

config['debug'] = True


class TestForte(TaskTestCase):
    task_class = AutoCombatTask
    config = config

    def test_forte1(self):
        self.task.do_reset_to_false()
        self.set_image('tests/images/treasure2.png')
        self.task.load_chars()
        self.assertIsNone(self.task.find_mouse_forte())

    def test_forte2(self):
        self.task.do_reset_to_false()
        self.set_image('tests/images/33forte.png')
        self.task.load_chars()
        forte = self.task.find_mouse_forte()
        # self.task.sleep(1)
        # self.task.screenshot('forte', show_box=True)
        # self.task.sleep(1)
        self.assertIsNotNone(forte)

    def test_forte4(self):
        self.task.do_reset_to_false()
        self.set_image('tests/images/33_forte_2.png')
        self.task.load_chars()
        forte = self.task.find_mouse_forte()
        self.assertIsNotNone(forte)

    def test_forte5(self):
        self.task.do_reset_to_false()
        self.set_image('tests/images/33_forte_3.png')
        self.task.load_chars()
        forte = self.task.find_mouse_forte()
        self.assertIsNotNone(forte)

    def test_forte3(self):
        self.task.do_reset_to_false()
        self.set_image('ok_templates/3.png')
        self.task.load_chars()
        self.assertIsNotNone(self.task.find_mouse_forte())


if __name__ == '__main__':
    unittest.main()
