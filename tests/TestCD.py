import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from config import config
from ok.test.TaskTestCase import TaskTestCase
from src.task.AutoCombatTask import AutoCombatTask

config['debug'] = True


class TestCD(TaskTestCase):
    task_class = AutoCombatTask
    config = config

    @staticmethod
    def cd_text(name, x):
        return SimpleNamespace(name=name, x=x)

    def test_cd1(self):
        self.task.do_reset_to_false()
        self.set_image('tests/images/in_combat.png')
        self.task.load_chars()
        self.task.ocr = Mock(return_value=[
            self.cd_text('9.9', 1400),
        ])
        self.assertFalse(self.task.has_cd('resonance'))
        self.assertFalse(self.task.has_cd('liberation'))
        self.assertTrue(self.task.has_cd('echo'))

    def test_cd3(self):
        self.task.do_reset_to_false()
        self.set_image('tests/images/in_combat3.png')
        self.task.load_chars()
        self.task.ocr = Mock(return_value=[
            self.cd_text('9.9', 1300),
            self.cd_text('9.9', 1400),
            self.cd_text('9.9', 1480),
        ])
        self.assertTrue(self.task.has_cd('resonance'))
        self.assertTrue(self.task.has_cd('liberation'))
        self.assertTrue(self.task.has_cd('echo'))


if __name__ == '__main__':
    unittest.main()
