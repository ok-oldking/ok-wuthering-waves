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
        self.previous_global_config = getattr(og, "global_config", None)
        self.global_config = Mock()
        self.global_config.get_config.return_value = {
            "Show Custom Overlay Content": True,
            "Show Debug Boxes": False,
        }
        og.app = self.app
        og.global_config = self.global_config

    def tearDown(self):
        Globals._game_window_visible = self.previous_window_visible
        og.app = self.previous_app
        og.global_config = self.previous_global_config

    def test_visible_game_window_draws_status(self):
        Globals._update_game_overlay(True)

        self.overlay.draw.assert_called_once()
        self.overlay.set_boxes_enabled.assert_called_once_with(False)

    def test_hidden_game_window_clears_status(self):
        Globals._update_game_overlay(False)

        self.overlay.clear_draw.assert_called_once_with("okww-status")

    def test_setting_change_updates_overlay_without_waiting_for_a_frame(self):
        Globals._game_window_visible = True

        Globals.apply_overlay_setting_change("Show Custom Overlay Content", False)

        self.overlay.clear_draw.assert_called_once_with("okww-status")
        self.overlay.set_boxes_enabled.assert_called_once_with(False)
