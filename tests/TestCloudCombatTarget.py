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

    def test_compressed_health_bars_at_supported_resolutions(self):
        root = Path(__file__).resolve().parents[1]
        with TemporaryDirectory() as directory, \
                patch.object(self.task, 'is_browser', return_value=True), \
                patch.object(self.task, '_in_combat', True):
            for filename, expected in [('cloud_combat_long_action.png', True),
                                       ('cloud_combat_low_health.png', True),
                                       ('cloud_world_unlocked.png', False)]:
                source = cv2.imread(str(root / 'tests/images' / filename))
                self.assertIsNotNone(source)
                for width, height in [(1920, 1080), (1600, 900), (2560, 1440)]:
                    with self.subTest(filename=filename, resolution=(width, height)):
                        image = Path(directory) / f'{Path(filename).stem}_{width}.png'
                        self.assertTrue(cv2.imwrite(str(image), cv2.resize(
                            source, (width, height), interpolation=cv2.INTER_AREA)))
                        self.set_image(str(image))
                        self.assertEqual(expected, bool(self.task.has_health_bar()))

    def test_visible_compressed_health_bar_prevents_retarget_after_grace(self):
        self.set_image('tests/images/cloud_combat_low_health.png')
        with patch.object(self.task, 'is_browser', return_value=True), \
                patch.object(self.task, '_in_combat', True), \
                patch.object(self.task, '_abyss_force_combat_until', 0), \
                patch.object(self.task, '_cloud_health_lost_at', 1), \
                patch.object(self.task, '_in_liberation', False), \
                patch.object(self.task.scene, 'in_combat', return_value=None), \
                patch.object(self.task.scene, 'set_in_combat', return_value=True), \
                patch.object(self.task, 'check_f_break'), \
                patch.object(self.task, 'get_current_char', return_value=None), \
                patch.object(self.task, 'on_combat_check', return_value=True), \
                patch.object(self.task, 'target_enemy') as retarget:
            self.assertFalse(self.task.has_target())
            self.assertTrue(self.task.do_check_in_combat(False))
            retarget.assert_not_called()

    def test_cloud_target_states_at_supported_resolutions(self):
        root = Path(__file__).resolve().parents[1]
        with TemporaryDirectory() as directory, \
                patch.object(self.task, 'is_browser', return_value=True), \
                patch.object(self.task, 'allow_target_box_short_combat_check', return_value=False):
            # 锁定时图标外圈为金色; 未锁定(有敌人或在大世界)外圈为灰色
            for filename, expected in [('tests/images/cloud_target_locked.png', True),
                                       ('tests/images/cloud_target_unlocked.png', False),
                                       ('tests/images/cloud_world_unlocked.png', False),
                                       ('ok_templates/63.png', False),
                                       ('ok_templates/64.png', True)]:
                source = cv2.imread(str(root / filename))
                self.assertIsNotNone(source)
                for width, height in [(1920, 1080), (1600, 900), (2560, 1440)]:
                    with self.subTest(filename=filename, resolution=(width, height)):
                        image = Path(directory) / f'{Path(filename).stem}_{width}.png'
                        self.assertTrue(cv2.imwrite(str(image), cv2.resize(
                            source, (width, height), interpolation=cv2.INTER_AREA)))
                        self.set_image(str(image))
                        self.task.esc_count = 0
                        self.assertEqual(expected, bool(self.task.has_target()))
