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

    def test_config_labels_are_localized(self):
        from ok import og
        self.assertEqual(og.app.tr('Double Drop Rules'), '双倍刷取规则')
        self.assertEqual(og.app.tr('Double Drop Simulation Count'), '双倍模拟领域次数')
        self.assertEqual(og.app.tr('Double Drop Tacet Count'), '双倍无音区次数')
        self.assertEqual(og.app.tr('Tacet Suppression runs during the event, 0-3.'),
                         '活动期间无音区的刷取次数，0-3。')

    def test_config_form_builds_localized_rows(self):
        import copy
        import tempfile

        from ok.ui.qt.tasks.config_editors import DropDownEditor
        from ok.ui.qt.tasks.config_form import ConfigForm
        from ok.util.config import Config
        from src.task.DoubleDropRules import (
            DOUBLE_DROP_RULES,
            DOUBLE_DROP_SIMULATION_MATERIAL,
        )

        with tempfile.TemporaryDirectory() as folder:
            config_copy = Config('DoubleDropFormTest', copy.deepcopy(self.task.default_config), folder=folder)
            config_copy[DOUBLE_DROP_RULES] = True
            form = ConfigForm(self.task, config_copy, self.task.default_config,
                              self.task.config_description, self.task.config_type)
            try:
                self.assertEqual(form.config_widget_by_key[DOUBLE_DROP_RULES].title_label.text(),
                                 '双倍刷取规则')
                material = form.config_widget_by_key[DOUBLE_DROP_SIMULATION_MATERIAL]
                self.assertIsInstance(material, DropDownEditor)
                self.assertIn('双倍模拟领域材料', material.title_label.text())
            finally:
                form.deleteLater()

    def assert_activities(self, image, expected):
        self.set_image(image)
        activities = self.task.detect_double_drop_activities_from_frame()
        self.assertEqual(activities, expected)

    def test_all_badges_active(self):
        self.assert_activities('tests/images/double_drop_badges_all.png', {
            SIMULATION: True, FORGERY: True, TACET: True})

    def test_no_badge_active(self):
        self.assert_activities('tests/images/double_drop_badges_none.png', {
            SIMULATION: False, FORGERY: False, TACET: False})

    def test_simulation_badge_only(self):
        self.assert_activities('tests/images/double_drop_badges_simulation.png', {
            SIMULATION: True, FORGERY: False, TACET: False})

    def test_forgery_badge_only(self):
        self.assert_activities('tests/images/double_drop_badges_forgery.png', {
            SIMULATION: False, FORGERY: True, TACET: False})

    def test_tacet_badge_only(self):
        self.assert_activities('tests/images/double_drop_badges_tacet.png', {
            SIMULATION: False, FORGERY: False, TACET: True})

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
