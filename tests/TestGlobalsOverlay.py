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

    def test_initialization_disables_persisted_notification_providers(self):
        notification = {
            key: True for key in Globals._notification_switches
        }
        previous_global_config = getattr(og, "global_config", None)
        og.global_config = Mock()
        og.global_config.get_config.return_value = notification
        try:
            Globals(Mock())
        finally:
            og.global_config = previous_global_config

        self.assertFalse(any(notification.values()))

    def test_notification_group_is_removed_from_settings(self):
        notification_config = Mock()
        notification_card = Mock(config=notification_config)
        other_card = Mock(config=Mock())
        settings = Mock(config_groups=[notification_card, other_card])
        main_window = Mock(setting_tab=settings)
        previous_global_config = getattr(og, "global_config", None)
        og.global_config = Mock()
        og.global_config.get_config.return_value = notification_config
        try:
            Globals._hide_notification_settings(main_window)
        finally:
            og.global_config = previous_global_config

        notification_card.hide.assert_called_once()
        self.assertEqual([other_card], settings.config_groups)
        notification_card.deleteLater.assert_not_called()

    def test_debug_box_setting_change_updates_overlay_without_waiting_for_a_frame(self):
        Globals.apply_echo_score_setting_change("Show Debug Boxes", True)

        self.overlay.set_boxes_enabled.assert_called_once_with(True)

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
