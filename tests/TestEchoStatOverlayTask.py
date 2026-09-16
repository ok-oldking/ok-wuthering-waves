import unittest
from unittest.mock import Mock

from src.gui.EchoStatOverlay import ECHO_STAT_PAINTER_KEY
from src.task.EchoStatOverlayTask import EchoStatOverlayTask


class TestEchoStatOverlayTask(unittest.TestCase):
    def make_task(self, show_content):
        task = EchoStatOverlayTask.__new__(EchoStatOverlayTask)
        task.overlay_config = {"Show Custom Overlay Content": show_content}
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
            "src.task.EchoStatOverlayTask.find_echo_stat_rectangles", return_value=[Mock()]
        ):
            self.assertFalse(task.run())

        overlay.draw.assert_called_once_with(ECHO_STAT_PAINTER_KEY, task.painter.paint)
