import time
import unittest

import cv2

from config import config
from ok.test.TaskTestCase import TaskTestCase
from src.task.FarmMapTask import FarmMapTask

config['debug'] = True


class TestTacet(TaskTestCase):
    task_class = FarmMapTask
    config = config

    def test_absorb(self):
        # self.set_image('tests/images/absorb.png')
        image = cv2.imread('tests/images/absorb.png')
        result = self.task.ocr()
        # angle, box = self.task.get_my_angle()
        self.assertTrue(len(result) > 0)



if __name__ == '__main__':
    unittest.main()
