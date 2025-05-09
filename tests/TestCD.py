import unittest
from config import config
from ok.test.TaskTestCase import TaskTestCase
from src.task.AutoCombatTask import AutoCombatTask

config['debug'] = True


class TestCD(TaskTestCase):
    task_class = AutoCombatTask
    config = config

    def test_cd1(self):
        self.task.do_reset_to_false()
        self.set_image('tests/images/in_combat.png')
        self.assertFalse(self.task.has_cd('resonance'))
        self.assertFalse(self.task.has_cd('liberation'))
        self.assertFalse(self.task.has_cd('echo'))

    def test_cd2(self):
        self.task.do_reset_to_false()
        self.set_image('tests/images/in_combat2.png')
        self.assertFalse(self.task.has_cd('resonance'))
        self.assertFalse(self.task.has_cd('liberation'))
        self.assertFalse(self.task.has_cd('echo'))

    def test_cd3(self):
        self.task.do_reset_to_false()
        self.set_image('tests/images/in_combat3.png')
        self.assertFalse(self.task.has_cd('resonance'))
        self.assertTrue(self.task.has_cd('liberation'))
        self.assertFalse(self.task.has_cd('echo'))

    def test_cd4(self):
        self.task.do_reset_to_false()
        self.set_image('tests/images/absorb.png')
        self.assertFalse(self.task.has_cd('resonance'))
        self.assertFalse(self.task.has_cd('liberation'))
        self.assertTrue(self.task.has_cd('echo'))

    def test_cd5(self):
        self.task.do_reset_to_false()
        self.set_image('tests/images/all_cd_1080p.png')
        self.assertTrue(self.task.has_cd('resonance'))
        self.assertTrue(self.task.has_cd('liberation'))
        self.assertTrue(self.task.has_cd('echo'))

    def test_cd6(self):
        self.task.do_reset_to_false()
        self.set_image('tests/images/con_full.png')
        self.assertTrue(self.task.has_cd('resonance'))
        self.assertFalse(self.task.has_cd('liberation'))
        self.assertFalse(self.task.has_cd('echo'))

    def test_cd7(self):
        self.task.do_reset_to_false()
        self.set_image('tests/images/echo.png')
        self.assertTrue(self.task.has_cd('resonance'))
        self.assertFalse(self.task.has_cd('liberation'))
        self.assertTrue(self.task.has_cd('echo'))

    def test_cd8(self):
        self.task.do_reset_to_false()
        self.set_image('tests/images/echo2.png')
        self.assertFalse(self.task.has_cd('resonance'))
        self.assertTrue(self.task.has_cd('liberation'))
        self.assertFalse(self.task.has_cd('echo'))

    def test_cd9(self):
        self.task.do_reset_to_false()
        self.set_image('tests/images/stars.png')
        self.assertFalse(self.task.has_cd('resonance'))
        self.assertFalse(self.task.has_cd('liberation'))
        self.assertFalse(self.task.has_cd('echo'))

    def test_cd10(self):
        self.task.do_reset_to_false()
        self.set_image('tests/images/treasure.png')
        self.assertFalse(self.task.has_cd('resonance'))
        self.assertFalse(self.task.has_cd('liberation'))
        self.assertFalse(self.task.has_cd('echo'))

    def test_cd11(self):
        self.task.do_reset_to_false()
        self.set_image('tests/images/treasure2.png')
        self.assertFalse(self.task.has_cd('resonance'))
        self.assertTrue(self.task.has_cd('liberation'))
        self.assertFalse(self.task.has_cd('echo'))

if __name__ == '__main__':
    unittest.main()
