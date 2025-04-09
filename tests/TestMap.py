import time
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
        angle, box = self.task.get_my_angle()
        self.logger.info(f'test_find_treasure_icon {angle, box}')
        self.assertTrue(100 <= angle <= 200)

    def test_find_path(self):
        self.set_image('tests/images/path.png')
        self.task.load_stars(wait_world=False)

        self.set_image('tests/images/mini_map.png')
        # self.task.my_box = self.task.box_of_screen(0.45, 0.17, 0.62, 0.54)
        star, distance, angle = self.task.find_direction_angle(screenshot=True)
        time.sleep(5)
        self.logger.info(f'test_find_path {star, distance, angle}')
        self.assertTrue(1 <= distance <= 50)


if __name__ == '__main__':
    unittest.main()
