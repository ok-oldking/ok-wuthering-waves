import unittest
from unittest.mock import Mock

from ok import og
from src.gui.EchoStatOverlay import ECHO_STAT_PAINTER_KEY
from src.task.EchoStatOverlayTask import EchoStatOverlayTask


class TestEchoStatOverlayTask(unittest.TestCase):
    def setUp(self):
        self.previous_device_manager = getattr(og, "device_manager", None)
        og.device_manager = None

    def tearDown(self):
        og.device_manager = self.previous_device_manager

    def make_task(self, show_content):
        task = EchoStatOverlayTask.__new__(EchoStatOverlayTask)
        task.echo_score_config = {
            "角色评分模板": "通用",
            "显示主副词条框体": show_content,
        }
        task.painter = Mock()
        task._executor = Mock()
        task._executor.method.width = 1600
        task._executor.method.height = 900
        return task

    def test_custom_content_switch_clears_echo_stat_boxes(self):
        task = self.make_task(show_content=False)
        task.get_overlay_view = Mock(return_value=Mock())

        self.assertFalse(task.run())
        task.get_overlay_view.return_value.clear_draw.assert_called_once_with(ECHO_STAT_PAINTER_KEY)

    def test_custom_content_switch_draws_recognized_boxes(self):
        task = self.make_task(show_content=True)
        overlay = Mock()
        task.get_overlay_view = Mock(return_value=overlay)
        task.ocr = Mock(return_value=[])
        with unittest.mock.patch(
            "src.task.EchoStatOverlayTask.analyze_echo_stats",
            return_value=Mock(rectangles=[Mock()], row_scores=[1.0], summary="score"),
        ):
            self.assertFalse(task.run())

        overlay.draw.assert_called_once_with(ECHO_STAT_PAINTER_KEY, task.painter.paint)

    def test_background_game_preserves_last_recognized_boxes(self):
        task = self.make_task(show_content=True)
        overlay = Mock()
        task.get_overlay_view = Mock(return_value=overlay)
        task.ocr = Mock()
        task.painter.rectangles = [Mock()]
        og.device_manager = Mock(hwnd_window=Mock(exists=True, visible=False))

        self.assertFalse(task.run())

        task.ocr.assert_not_called()
        overlay.clear_draw.assert_not_called()
