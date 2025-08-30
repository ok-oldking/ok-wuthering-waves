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
        self.task.ensure_leviator = return_true
        self.task.do_reset_to_false()
        self.set_image('tests/images/in_combat.png')
        in_combat = self.task.in_combat()
        self.assertTrue(in_combat)

    def test_in_combat_check3(self):
        self.task.ensure_leviator = return_true
        self.task.do_reset_to_false()
        self.set_image('tests/images/in_combat3.png')
        in_combat = self.task.in_combat()
        self.assertTrue(in_combat)
        self.logger.debug('in_combat_check task done')

    def test_in_combat_check4(self):
        self.task.ensure_leviator = return_true
        self.task.do_reset_to_false()
        self.set_image('tests/images/in_combat4.png')
        in_combat = self.task.in_combat()
        self.logger.debug('in_combat_check task done')
        self.task.screenshot('in_combat4', show_box=True)
        self.task.sleep(1)
        self.assertTrue(in_combat)


if __name__ == '__main__':
    unittest.main()
