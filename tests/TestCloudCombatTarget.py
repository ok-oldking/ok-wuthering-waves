from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import cv2

from config import config
from ok.test.TaskTestCase import TaskTestCase
from src.task.AutoCombatTask import AutoCombatTask


class TestCloudCombatTarget(TaskTestCase):
    task_class = AutoCombatTask
    config = deepcopy(config)

    def test_cloud_target_states_at_supported_resolutions(self):
        root = Path(__file__).resolve().parents[1]
        with TemporaryDirectory() as directory, \
                patch.object(self.task, 'is_browser', return_value=True), \
                patch.object(self.task, 'allow_target_box_short_combat_check', return_value=False):
            for filename, expected in [('63.png', False), ('64.png', True)]:
                source = cv2.imread(str(root / 'ok_templates' / filename))
                self.assertIsNotNone(source)
                for width, height in [(1920, 1080), (1600, 900), (2560, 1440)]:
                    with self.subTest(filename=filename, resolution=(width, height)):
                        image = Path(directory) / f'{Path(filename).stem}_{width}.png'
                        self.assertTrue(cv2.imwrite(str(image), cv2.resize(
                            source, (width, height), interpolation=cv2.INTER_AREA)))
                        self.set_image(str(image))
                        self.task.esc_count = 0
                        self.assertEqual(expected, bool(self.task.has_target()))
