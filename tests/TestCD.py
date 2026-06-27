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
        self.task.load_chars()
        self.assertFalse(self.task.has_cd('resonance'))
        self.assertFalse(self.task.has_cd('liberation'))
        self.assertTrue(self.task.has_cd('echo'))

    def test_cd3(self):
        self.task.do_reset_to_false()
        self.set_image('tests/images/in_combat3.png')
        self.task.load_chars()
        self.assertTrue(self.task.has_cd('resonance'))
        self.assertTrue(self.task.has_cd('liberation'))
        self.assertTrue(self.task.has_cd('echo'))

    def count_ocr(self):
        calls = {'n': 0}
        orig = self.task.ocr

        def counting_ocr(*a, **k):
            calls['n'] += 1
            return orig(*a, **k)

        self.task.ocr = counting_ocr
        self.addCleanup(setattr, self.task, 'ocr', orig)
        return calls

    def test_cd_reading_is_cached_across_frames(self):
        self.task.do_reset_to_false()
        self.set_image('tests/images/in_combat.png')
        self.task.load_chars()
        calls = self.count_ocr()
        first = self.task.get_cd('echo')
        self.task.scene.reset()  # next combat-loop frame
        second = self.task.get_cd('echo')
        self.assertEqual(calls['n'], 1)
        self.assertTrue(self.task.has_cd('echo'))
        self.assertLessEqual(second, first)  # cached value counts down, not refreshed

    def test_invalidate_cd_forces_reread(self):
        self.task.do_reset_to_false()
        self.set_image('tests/images/in_combat.png')
        self.task.load_chars()
        calls = self.count_ocr()
        self.task.get_cd('echo')
        self.task.invalidate_cd(self.task.get_current_char().index)
        self.task.get_cd('echo')
        self.assertEqual(calls['n'], 2)


if __name__ == '__main__':
    unittest.main()
