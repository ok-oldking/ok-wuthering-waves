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

    def test_finds_skip_dialog_icons_with_frame_processor(self):
        cases = (
            ('ok_templates/47.png', 'skip_dialog_new'),
            ('ok_templates/53.png', 'skip_dialog'),
        )

        for image, expected_feature in cases:
            with self.subTest(image=image):
                self.set_image(image)

                skip = self.task.find_skip()

                self.assertIsNotNone(skip)
                self.assertEqual(expected_feature, skip.name)

    def test_clicks_tinted_skip_icon_on_ultrawide_screens(self):
        # The fixture keeps its original screen dimensions, with unrelated areas white.
        original = cv2.imread('tests/images/21-9_quest_skip.png')
        with TemporaryDirectory() as directory:
            image = str(Path(directory) / 'frame.png')
            empty = str(Path(directory) / 'empty.png')
            for width, height in ((2560, 1080), (3440, 1440), (5120, 2160)):
                with self.subTest(resolution=(width, height)):
                    frame = cv2.resize(original, (width, height))
                    cv2.imwrite(image, frame)
                    cv2.imwrite(empty, np.zeros_like(frame))
                    self.set_image(image)

                    skip = self.task.find_skip()

                    self.assertIsNotNone(skip)
                    self.assertEqual('skip_dialog', skip.name)
                    scale = height / 2160
                    self.assertAlmostEqual(skip.x, 179 * scale, delta=2)
                    self.assertAlmostEqual(skip.y, 104 * scale, delta=2)
                    with patch.object(self.task, 'click_box',
                                      side_effect=lambda *args, **kwargs: self.set_image(empty)) as click:
                        self.assertTrue(self.task.try_click_skip())
                    click.assert_called_once()
                    self.assertAlmostEqual(click.call_args.args[0].x, skip.x, delta=1)
                    self.assertIsNone(self.task.find_skip())

    def test_skip_detector_rejects_flat_backgrounds(self):
        with TemporaryDirectory() as directory:
            image = str(Path(directory) / 'frame.png')
            for color in ((0, 0, 0), (100, 100, 100), (255, 255, 255), (160, 140, 100)):
                with self.subTest(color=color):
                    frame = np.full((1080, 2560, 3), color, dtype=np.uint8)
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

    def test_clicks_story_summary_on_ultrawide_screen(self):
        self.set_image('tests/images/skip_quest_confirm_21_9.jpg')
        with patch.object(self.task, 'click') as click, \
                patch.object(self.task, 'sleep'), \
                patch.object(self.task, 'in_team_and_world', return_value=False):
            self.assertTrue(self.task.check_skip())

        click.assert_called_once()
        button = click.call_args.args[0]
        self.assertEqual('skip_quest_confirm', button.name)
        # The right-hand Skip Story button, not Continue Watching on the left.
        self.assertGreater(button.x, 1950)
        self.assertLess(button.x + button.width, 2370)
        self.assertGreater(button.y, 960)
        self.assertLess(button.y + button.height, 1070)

    def test_finds_story_summary_buttons_in_both_ui_sizes(self):
        for image, feature in (
                ('ok_templates/10.png', 'skip_quest_confirm'),
                ('ok_templates/9.png', 'skip_quest_confirm_new')):
            with self.subTest(image=image):
                self.set_image(image)
                with patch.object(self.task, 'click') as click, patch.object(self.task, 'sleep'):
                    self.assertTrue(self.task.skip_confirm())
                self.assertEqual(feature, click.call_args.args[0].name)


if __name__ == '__main__':
    unittest.main()
