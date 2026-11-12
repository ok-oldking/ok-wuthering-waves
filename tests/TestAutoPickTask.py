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
    combat = Mock()
    combat.check_abyss_start.return_value = None
    task.get_task_by_class = Mock(return_value=combat)
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

    def test_xinyao_icon_never_sends_f_on_repeated_checks(self):
        task = make_task(self.source_frame())
        for _ in range(3):
            self.assertIs(task.run(), False)
        task.send_key.assert_not_called()
        self.assertEqual(task.get_task_by_class.return_value.check_abyss_start.call_args_list,
                         [call(True)] * 3)

    def test_xinyao_icon_blocks_different_prompt(self):
        # Independent screenshot: same icon, different prompt and background.
        frame = cv2.imread('tests/images/xinyao_interaction_different_prompt.png')
        self.assertIsNotNone(frame)
        task = make_task(frame)
        for _ in range(3):
            self.assertIs(task.run(), False)
        task.send_key.assert_not_called()
        self.assertEqual(task.get_task_by_class.return_value.check_abyss_start.call_args_list,
                         [call(True)] * 3)

    def test_xinyao_icon_without_text_still_blocks_whitelisted_pickup(self):
        frame = self.source_frame()
        # Keep only the icon: the guard must not depend on the prompt's language.
        frame[449:480, 1106:1282] = 0
        task = make_task(frame)
        task.config['Pick Up White List'] = ['吸收', 'Absorb']
        task.find_f_with_text = Mock(return_value=True)
        self.assertIs(task.run(), False)
        task.send_key.assert_not_called()
        task.find_f_with_text.assert_not_called()

    def test_xinyao_icon_at_scaled_and_centered_ultrawide_sizes(self):
        source = self.source_frame()
        for width, height in ((1280, 720), (1920, 1080), (2560, 1440),
                              (3840, 2160), (2560, 1080)):
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
        # Retain the F key and text, removing only the blocked icon.
        frame[449:480, 1076:1106] = 0
        task = make_task(frame)
        self.assertIs(task.run(), True)
        self.assertEqual(task.send_key.call_args_list, [call('f')] * 3)

    def test_icon_on_another_row_does_not_block_selected_pickup(self):
        for dy in (-60, 60):
            with self.subTest(offset=dy):
                frame = self.source_frame()
                icon = frame[449:480, 1076:1106].copy()
                frame[449:480, 1076:1106] = 0
                frame[449 + dy:480 + dy, 1076:1106] = icon
                task = make_task(frame)
                self.assertIs(task.run(), True)
                self.assertEqual(task.send_key.call_args_list, [call('f')] * 3)

    def test_absent_f_sends_no_keys(self):
        task = make_task(np.zeros_like(self.source_frame()))
        self.assertIsNone(task.run())
        task.send_key.assert_not_called()


if __name__ == '__main__':
    unittest.main()
