import unittest

import cv2

from config import config
from ok.test.TaskTestCase import TaskTestCase
from src.char.BaseChar import Elements
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
        self.assertTrue(con_full)

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

    def test_con_arc_from_live_1080p_crops(self):
        # Crops of the con box captured live; expected fill judged from the image.
        cases = [
            ('con_arc_spectro_full', Elements.SPECTRO, 1, 1),
            ('con_arc_spectro_96', Elements.SPECTRO, 0.9, 0.99),  # small gap at 3 o'clock: not full
            ('con_arc_spectro_85', Elements.SPECTRO, 0.78, 0.9),  # used to read as full
            ('con_arc_wind_80', Elements.WIND, 0.72, 0.88),  # used to read 0.99
            ('con_arc_wind_25', Elements.WIND, 0.18, 0.32),
            ('con_arc_wind_18', Elements.WIND, 0.1, 0.25),  # short arc used to read 0
            ('con_arc_wind_empty', Elements.WIND, 0, 0),
        ]
        for name, element, low, high in cases:
            with self.subTest(name):
                image = cv2.imread(f'tests/images/{name}.png')
                con = self.task.measure_con_arc(image, element)
                self.assertGreaterEqual(con, low)
                self.assertLessEqual(con, high)

    def test_con_full6(self):
        self.task.do_reset_to_false()
        self.set_image('tests/images/con_full2.png')
        self.task.load_chars()
        con_full = self.task.get_current_char().is_con_full()
        self.assertTrue(con_full)


if __name__ == '__main__':
    unittest.main()
