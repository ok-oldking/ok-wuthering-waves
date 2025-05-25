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
        self.set_image('tests/images/con_full.png')
        self.task.load_chars()
        forte_count = self.task.get_current_char().count_gray_forte()
        self.task.sleep(1)
        self.assertEqual(forte_count, 12)

    def test_forte2(self):
        self.task.do_reset_to_false()
        self.set_image('tests/images/forte2.png')
        self.task.load_chars()
        forte_count = self.task.get_current_char().count_gray_forte()
        self.task.sleep(1)
        self.assertEqual(forte_count, 3)

    def test_forte3(self):
        self.task.do_reset_to_false()
        self.set_image('tests/images/in_combat4.png')
        self.assertTrue(self.task.in_combat())
        forte_count = self.task.get_current_char().count_gray_forte()
        self.task.sleep(1)
        self.assertEqual(forte_count, 41)

    def test_forte4(self):
        self.task.do_reset_to_false()
        self.set_image('tests/images/in_combat.png')
        self.task.load_chars()
        forte_count = self.task.get_current_char().count_gray_forte()
        self.task.sleep(1)
        self.assertGreater(forte_count, 13)

    def test_forte5(self):
        self.task.do_reset_to_false()
        self.set_image('tests/images/forte4.png')
        self.task.load_chars()
        forte_count = self.task.get_current_char().count_gray_forte()
        self.task.sleep(1)
        self.assertEqual(forte_count, 20)

    def test_forte6(self):
        self.task.do_reset_to_false()
        self.set_image('tests/images/forte6.png')
        self.task.load_chars()
        forte_count = self.task.get_current_char().count_gray_forte()
        self.task.sleep(1)
        self.assertEqual(forte_count, 13)

    def test_forte7(self):
        self.task.do_reset_to_false()
        self.set_image('tests/images/forte6.png')
        self.task.load_chars()
        forte_count = self.task.get_current_char().count_gray_forte()
        self.task.sleep(1)
        self.assertEqual(forte_count, 13)


if __name__ == '__main__':
    unittest.main()
