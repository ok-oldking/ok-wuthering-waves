import time
import unittest
from unittest.mock import Mock

import cv2

from config import config
from ok.test.TaskTestCase import TaskTestCase
from src.task.FarmMapTask import FarmMapTask

config['debug'] = True


class TestTacet(TaskTestCase):
    task_class = FarmMapTask
    config = config

    def test_absorb(self):
        self.set_image('tests/images/absorb.png')
        # image = cv2.imread('tests/images/absorb.png')
        self.task.find_f_with_text = Mock(return_value=True)
        self.task.send_key = Mock()
        self.task.handle_claim_button = Mock(return_value=False)
        result = self.task.pick_echo()
        # angle, box = self.task.get_my_angle()
        self.assertTrue(result)
        self.task.find_f_with_text.assert_called_once_with(target_text=self.task.absorb_echo_text())
        self.task.send_key.assert_called_once_with('f')


if __name__ == '__main__':
    unittest.main()
