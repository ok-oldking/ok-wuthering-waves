import unittest
from types import SimpleNamespace
from unittest.mock import patch

from config import config
from ok.test.TaskTestCase import TaskTestCase
from src.task.DailyTask import DailyTask
from src.task.DoubleDropRules import FORGERY, SIMULATION, TACET

config['debug'] = True


class TestDoubleDropRecognition(TaskTestCase):
    task_class = DailyTask
    config = config

    def test_tacet_badge_only(self):
        self.set_image('tests/images/double_drop_badges_tacet.png')
        activities = self.task.detect_double_drop_activities_from_frame()
        self.assertEqual(activities, {SIMULATION: False, FORGERY: False, TACET: True})

    def test_one_mode_ocr_failure_does_not_discard_other_badges(self):
        def fake_ocr(box=None, **kwargs):
            if 'Forgery' in box.name:
                raise RuntimeError('ocr failed')
            return [SimpleNamespace(name='UP')]

        with patch.object(self.task, 'ocr', side_effect=fake_ocr), \
                patch.object(self.task, 'calculate_color_percentage', return_value=0.1):
            activities = self.task.detect_double_drop_activities_from_frame()
        self.assertEqual(activities, {SIMULATION: True, FORGERY: False, TACET: True})


if __name__ == '__main__':
    unittest.main()
