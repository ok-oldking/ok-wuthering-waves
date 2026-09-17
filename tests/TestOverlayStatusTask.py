import unittest
from unittest.mock import ANY, Mock

from src.task.OverlayStatusTask import OVERLAY_PAINTER_KEY, OverlayStatusTask


class TestOverlayStatusTask(unittest.TestCase):
    @staticmethod
    def make_task(show_boxes=False, overlay_enabled=True):
        task = OverlayStatusTask.__new__(OverlayStatusTask)
        task.echo_score_config = {
            "显示主副词条框体": True,
            "Show Debug Boxes": show_boxes,
        }
        task._app = Mock()
        task._app.ok_config = {"use_overlay": overlay_enabled}
        return task

    def test_draws_status_on_every_game_screen(self):
        task = self.make_task()
        overlay = Mock()
        task.get_overlay_view = Mock(return_value=overlay)

        self.assertFalse(task.run())
        overlay.draw.assert_called_once_with(OVERLAY_PAINTER_KEY, ANY)
        overlay.clear_draw.assert_not_called()

    def test_enables_native_overlay_when_needed(self):
        task = self.make_task(overlay_enabled=False)
        overlay = Mock()
        task.get_overlay_view = Mock(return_value=overlay)

        self.assertFalse(task.run())
        self.assertTrue(task._app.ok_config["use_overlay"])
        overlay.draw.assert_called_once_with(OVERLAY_PAINTER_KEY, ANY)

    def test_debug_boxes_remain_independently_configurable(self):
        task = self.make_task(show_boxes=True)
        overlay = Mock()
        task.get_overlay_view = Mock(return_value=overlay)

        self.assertFalse(task.run())
        overlay.set_boxes_enabled.assert_called_once_with(True)
        overlay.draw.assert_called_once_with(OVERLAY_PAINTER_KEY, ANY)
