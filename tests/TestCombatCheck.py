import time
import unittest
from config import config
from ok.test.TaskTestCase import TaskTestCase
from src.task.AutoCombatTask import AutoCombatTask

config['debug'] = True


def return_true():
    return True


class TestCombatCheck(TaskTestCase):
    task_class = AutoCombatTask
    config = config

    def test_in_combat_check(self):
        self.task.ensure_levitator = return_true
        self.task.do_reset_to_false()
        self.set_image('tests/images/in_combat.png')
        in_combat = self.task.in_combat()
        # self.task.screenshot('in_combat.png', show_box=True)
        # time.sleep(1)
        self.assertTrue(in_combat)

    def test_4k_combat_check(self):
        self.task.ensure_levitator = return_true
        self.task.do_reset_to_false()
        self.set_image("xanylabeling/project_dir/57d8d801-BitBlt_True_3840x2160_1759986393607.1733_original.png")
        in_combat = self.task.in_combat()
        # self.task.screenshot('in_combat4k.png', show_box=True)
        # time.sleep(1)
        self.assertTrue(in_combat)

    def test_not_in_combat_check(self):
        self.task.ensure_levitator = return_true
        self.task.do_reset_to_false()
        self.set_image('tests/images/in_combat3.png')
        in_combat = self.task.in_combat()
        self.assertFalse(in_combat)

    def test_in_combat_cloud(self):
        self.task.ensure_levitator = return_true
        self.task.do_reset_to_false()
        self.task.is_browser = return_true
        self.set_image('tests/images/cloud_game_combat.png')
        in_combat = self.task.in_combat()
        self.assertTrue(in_combat)

    def test_in_combat_cloud2(self):
        self.task.ensure_levitator = return_true
        self.task.do_reset_to_false()
        self.task.is_browser = return_true
        self.set_image('xanylabeling/project_dir/browser_in_combat.png')
        in_combat = self.task.in_combat()
        self.assertTrue(in_combat)


if __name__ == '__main__':
    unittest.main()
