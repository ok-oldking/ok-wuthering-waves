import unittest
from config import config
from ok.test.TaskTestCase import TaskTestCase
from src.task.FarmMapTask import FarmMapTask

config['debug'] = True


class TestTacet(TaskTestCase):
    task_class = FarmMapTask
    config = config

    def test_find_treasure_icon(self):
        self.set_image('tests/images/angle_130.png')
        angle, box = self.task.get_angle()
        self.logger.info(f'test_find_treasure_icon {angle, box}')
        self.assertTrue(100 <= angle <= 200)

    def test_find_stars(self):
        self.set_image('tests/images/stars.png')
        stars = self.task.find_stars()
        self.logger.info(f'find_stars {stars}')
        self.assertEqual(3, len(stars))

        angle1 = self.task.get_angle_to_star(stars[0])
        angle2 = self.task.get_angle_to_star(stars[1])
        angle3 = self.task.get_angle_to_star(stars[2])
        self.assertTrue(100 <= angle1 <= 180)
        self.assertTrue(0 <= angle2 <= 90)
        self.assertTrue(-45 <= angle3 <= 0)

if __name__ == '__main__':
    unittest.main()
