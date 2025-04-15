import unittest
from config import config
from ok.test.TaskTestCase import TaskTestCase
from src.task.AutoCombatTask import AutoCombatTask

config['debug'] = True


class TestCombatCheck(TaskTestCase):
    task_class = AutoCombatTask
    config = config

    def test_con_full(self):
        self.task.do_reset_to_false()
        self.set_image('tests/images/con_full.png')
        # in_combat = self.task.in_combat()
        # self.assertTrue(in_combat)
        #
        # self.task.do_reset_to_false()
        # self.set_image('tests/images/con_full.png')
        # in_combat = self.task.in_combat()
        # self.assertTrue(in_combat)
        self.task.load_chars()
        con_full = self.task.get_current_char().is_con_full()
        self.assertTrue(con_full)


if __name__ == '__main__':
    unittest.main()
