import unittest
from config import config
from ok.test.TaskTestCase import TaskTestCase
from src.task.AutoCombatTask import AutoCombatTask

config['debug'] = True


class TestCon(TaskTestCase):
    task_class = AutoCombatTask
    config = config

    def test_con_full(self):
        self.task.do_reset_to_false()
        self.set_image('tests/images/con_full.png')
        self.task.load_chars()
        con_full = self.task.get_current_char().is_con_full()
        self.assertTrue(con_full)

    def test_con_full2(self):
        self.task.do_reset_to_false()
        self.set_image('tests/images/in_combat.png')
        self.task.load_chars()
        con_full = self.task.get_current_char().is_con_full()
        self.assertFalse(con_full)

    def test_con_full3(self):
        self.task.do_reset_to_false()
        self.set_image('tests/images/all_cd_1080p.png')
        self.task.load_chars()
        con = self.task.get_current_char().get_current_con()
        self.task.log_info(f'{self.task.get_current_char()} con = {con}')
        con_full = self.task.get_current_char().is_con_full()
        self.assertTrue(con_full)

    def test_con_full4(self):
        self.task.do_reset_to_false()
        self.set_image('tests/images/absorb.png')
        self.task.load_chars()
        con_full = self.task.get_current_char().is_con_full()
        self.assertFalse(con_full)

    def test_con_full5(self):
        self.task.do_reset_to_false()
        self.set_image('tests/images/angle_130.png')
        self.task.load_chars()
        con = self.task.get_current_char().get_current_con()
        self.task.log_info(f'{self.task.get_current_char()} con = {con}')
        con_full = self.task.get_current_char().is_con_full()
        self.assertFalse(con_full)

    def test_con_full6(self):
        self.task.do_reset_to_false()
        self.set_image('tests/images/con_full2.png')
        self.task.load_chars()
        con_full = self.task.get_current_char().is_con_full()
        self.assertTrue(con_full)


if __name__ == '__main__':
    unittest.main()
