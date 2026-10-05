import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import cv2
import numpy as np

from config import config
from ok.test.TaskTestCase import TaskTestCase
from src.task.SkipDialogTask import AutoDialogTask

config['debug'] = True


class TestSkipDialogWideMode(TaskTestCase):
    task_class = AutoDialogTask
    config = config

    def test_finds_skip_dialog_icons(self):
        cases = (
            ('assets/images/1.png', 'skip_dialog_new'),
            ('ok_templates/53.png', 'skip_dialog'),
        )

        for image, expected_feature in cases:
            with self.subTest(image=image):
                self.set_image(image)

                skip = self.task.find_skip()

                self.assertIsNotNone(skip)
                self.assertEqual(expected_feature, skip.name)

    def test_new_skip_ignores_transparent_background_at_supported_resolutions(self):
        template = cv2.imread('assets/images/1.png')[350:418, 136:206]
        transparent = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY) < 180
        with TemporaryDirectory() as directory:
            image = str(Path(directory) / 'frame.png')
            empty = str(Path(directory) / 'empty.png')
            for width, height in ((1280, 720), (1920, 1080), (2560, 1440), (3840, 2160),
                                  (3440, 1440)):
                scale = min(width / 3840, height / 2160)
                for background in ((20, 20, 20), (100, 100, 100), (175, 175, 175), (20, 100, 180), None):
                    with self.subTest(resolution=(width, height), background=background):
                        button = template.copy()
                        if background is None:
                            button = cv2.convertScaleAbs(button, alpha=0.65)
                        else:
                            button[transparent] = background
                        button = cv2.resize(button, (round(70 * scale), round(68 * scale)))
                        frame = np.zeros((height, width, 3), dtype=np.uint8)
                        x, y = round(174 * scale), round(98 * scale)
                        frame[y:y + button.shape[0], x:x + button.shape[1]] = button
                        cv2.imwrite(image, frame)
                        cv2.imwrite(empty, np.zeros_like(frame))
                        self.set_image(image)
                        skip = self.task.find_skip()
                        self.assertIsNotNone(skip)
                        self.assertEqual('skip_dialog_new', skip.name)
                        with patch.object(self.task, 'click_box', side_effect=lambda *args, **kwargs: self.set_image(empty)) as click:
                            self.assertTrue(self.task.try_click_skip())
                            click.assert_called_once()

    def test_new_skip_rejects_flat_background_and_missing_skip_bar(self):
        template = cv2.imread('assets/images/1.png')[350:418, 136:206]
        with TemporaryDirectory() as directory:
            image = str(Path(directory) / 'frame.png')
            for value in (0, 100, 255):
                with self.subTest(background=value):
                    cv2.imwrite(image, np.full((1080, 1920, 3), value, dtype=np.uint8))
                    self.set_image(image)
                    self.assertIsNone(self.task.find_skip())
            button = cv2.resize(template, (35, 34))
            button[:, 22:30] = 255
            frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
            frame[49:83, 87:122] = button
            cv2.imwrite(image, frame)
            self.set_image(image)
            self.assertIsNone(self.task.find_skip())

    def test_finds_and_clicks_wide_mode_confirm_dialog(self):
        self.set_image('ok_templates/19.png')
        self.task.click = Mock()
        self.task.sleep = Mock()

        clicked = self.task.click_skip_dialog_confirm()

        self.assertTrue(clicked)
        self.assertEqual(2, self.task.click.call_count)


if __name__ == '__main__':
    unittest.main()
