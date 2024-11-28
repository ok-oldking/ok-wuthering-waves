from ok.OK import logger

import unittest
from config import config
from ok.test.TaskTestCase import TaskTestCase
from src.task.AutoCombatTask import AutoCombatTask

config['debug'] = True


class TestCombatCheck(TaskTestCase):
    task_class = AutoCombatTask
    config = config

    def test_in_combat_check(self):
        self.set_image('tests/images/in_combat.png')
        in_combat = self.task.in_combat()
        self.assertTrue(in_combat)
        self.set_image('tests/images/in_combat2.png')
        in_combat = self.task.in_combat()
        self.assertTrue(in_combat)
        logger.debug('in_combat_check task done')


if __name__ == '__main__':
    unittest.main()
