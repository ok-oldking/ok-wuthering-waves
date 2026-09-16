import unittest
from unittest.mock import ANY, Mock

from src.task.OverlayStatusTask import OVERLAY_PAINTER_KEY, OverlayStatusTask


class TestOverlayStatusTask(unittest.TestCase):
    @staticmethod
    def make_task(show_content=True, show_boxes=False, overlay_enabled=True):
        task = OverlayStatusTask.__new__(OverlayStatusTask)
        task.overlay_config = {
            "Show Custom Overlay Content": show_content,
            "Show Debug Boxes": show_boxes,
        }
        task._app = Mock()
        task._app.ok_config = {"use_overlay": overlay_enabled}
        return task

    def test_draws_status_in_open_world(self):
        task = self.make_task()
        overlay = Mock()
        task.get_overlay_view = Mock(return_value=overlay)
        task.in_world = Mock(return_value=True)

        self.assertFalse(task.run())
        overlay.draw.assert_called_once_with(OVERLAY_PAINTER_KEY, ANY)
        overlay.clear_draw.assert_not_called()

    def test_clears_status_outside_open_world(self):
        task = self.make_task()
        overlay = Mock()
        task.get_overlay_view = Mock(return_value=overlay)
        task.in_world = Mock(return_value=False)

        self.assertFalse(task.run())
        overlay.clear_draw.assert_called_once_with(OVERLAY_PAINTER_KEY)
        overlay.draw.assert_not_called()

    def test_disabled_setting_closes_overlay(self):
        task = self.make_task(show_content=False, show_boxes=False)
        overlay = Mock()
        task.get_overlay_view = Mock(return_value=overlay)

        self.assertFalse(task.run())
        overlay.clear_draw.assert_called_once_with(OVERLAY_PAINTER_KEY)
        task._app.set_overlay_setting.assert_called_once_with("boxes", False)

    def test_debug_boxes_do_not_enable_custom_content(self):
        task = self.make_task(show_content=False, show_boxes=True)
        overlay = Mock()
        task.get_overlay_view = Mock(return_value=overlay)

        self.assertFalse(task.run())
        overlay.set_boxes_enabled.assert_called_once_with(True)
        overlay.draw.assert_not_called()
        overlay.clear_draw.assert_called_once_with(OVERLAY_PAINTER_KEY)
        task._app.set_overlay_setting.assert_not_called()
