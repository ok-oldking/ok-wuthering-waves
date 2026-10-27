import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call

import cv2
import numpy as np

from config import config
from ok.feature.FeatureSet import FeatureSet
from src.task.AutoPickTask import AutoPickTask


def make_task(frame):
    task = AutoPickTask.__new__(AutoPickTask)
    task._executor = SimpleNamespace(
        frame=frame, feature_set=FeatureSet(False, None, **config['template_matching']))
    task.scene = Mock()
    task.scene.in_team.return_value = True
    task.config = {'Pick Up White List': [], 'Pick Up Black List': []}
    task.send_key = Mock()
    task.sleep = Mock()
    task.next_frame = Mock()
    task.log_debug = Mock()
    return task


class TestAutoPickTask(unittest.TestCase):
    def source_frame(self):
        frame = cv2.imread('ok_templates/62.png')
        self.assertIsNotNone(frame)
        return frame

    def test_xinyao_well_never_sends_f_on_repeated_checks(self):
        task = make_task(self.source_frame())
        for _ in range(3):
            self.assertIs(task.run(), False)
        task.send_key.assert_not_called()

    def test_xinyao_well_at_scaled_and_centered_ultrawide_sizes(self):
        source = self.source_frame()
        for width, height in ((1920, 1080), (2560, 1440), (3840, 2160), (2560, 1080)):
            with self.subTest(resolution=(width, height)):
                scaled = cv2.resize(source, (round(1600 * height / 900), height))
                frame = np.zeros((height, width, 3), dtype=np.uint8)
                offset = (width - scaled.shape[1]) // 2
                frame[:, offset:offset + scaled.shape[1]] = scaled
                task = make_task(frame)
                self.assertIs(task.run(), False)
                task.send_key.assert_not_called()

    def test_ordinary_pickup_still_sends_f(self):
        frame = self.source_frame()
        # Remove the well prompt while retaining the real F key from the screenshot.
        frame[449:481, 1075:1282] = 0
        task = make_task(frame)
        self.assertIs(task.run(), True)
        self.assertEqual(task.send_key.call_args_list, [call('f')] * 3)

    def test_well_on_another_row_does_not_block_selected_pickup(self):
        frame = self.source_frame()
        prompt = frame[449:481, 1075:1282].copy()
        frame[449:481, 1075:1282] = 0
        frame[509:541, 1075:1282] = prompt
        task = make_task(frame)
        self.assertIs(task.run(), True)
        self.assertEqual(task.send_key.call_args_list, [call('f')] * 3)

    def test_absent_f_sends_no_keys(self):
        task = make_task(np.zeros_like(self.source_frame()))
        self.assertIsNone(task.run())
        task.send_key.assert_not_called()


if __name__ == '__main__':
    unittest.main()
