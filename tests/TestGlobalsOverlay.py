import unittest
from unittest.mock import Mock

from ok import og
from src.globals import Globals


class TestGlobalsOverlay(unittest.TestCase):
    def setUp(self):
        self.previous_window_visible = Globals._game_window_visible
        Globals._game_window_visible = False
        self.previous_app = getattr(og, "app", None)
        self.app = Mock()
        self.app.ok_config = {"use_overlay": True}
        self.overlay = Mock()
        self.app.get_overlay_view.return_value = self.overlay
        og.app = self.app

    def tearDown(self):
        Globals._game_window_visible = self.previous_window_visible
        og.app = self.previous_app

    def test_debug_box_setting_change_updates_overlay_without_waiting_for_a_frame(self):
        Globals.apply_echo_score_setting_change("Show Debug Boxes", True)

        self.overlay.set_boxes_enabled.assert_called_once_with(True)

    def test_echo_box_switch_clears_custom_painter_immediately(self):
        Globals.apply_echo_score_setting_change("显示主副词条框体", False)

        self.overlay.clear_draw.assert_called_once_with("echo-stat-boxes")

    def test_disable_score_clears_boxes_and_status(self):
        Globals.apply_echo_score_setting_change("启用声骸评分", False)

        self.assertEqual(
            [call.args[0] for call in self.overlay.clear_draw.call_args_list],
            ["echo-stat-boxes", "echo-score-status"],
        )

    def test_background_game_keeps_overlay_visible(self):
        hwnd_window = Mock(exists=True, visible=False)
        with unittest.mock.patch.object(og, "device_manager", Mock(hwnd_window=hwnd_window)):
            Globals._update_game_overlay(False, 10, 20, 1600, 900, 1600, 900, 1.0)

        self.overlay.update_overlay.assert_called_once_with(
            True, 10, 20, 1600, 900, 1600, 900, 1.0
        )
