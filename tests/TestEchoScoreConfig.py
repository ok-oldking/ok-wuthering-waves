import unittest

from config import config
from src.echo_score import DEFAULT_TEMPLATE, template_names
from src.gui.OverlayStatus import STATUS_TEXT


class TestEchoScoreConfig(unittest.TestCase):
    def test_echo_score_tab_is_immediately_after_game_hotkey(self):
        visible_tabs = [
            option.name
            for option in config["global_configs"]
            if option.show_at_tab
        ]

        self.assertEqual(visible_tabs[:2], ["Game Hotkey", "声骸评分"])

    def test_echo_box_switch_lives_on_echo_score_tab(self):
        options = {option.name: option for option in config["global_configs"]}

        self.assertEqual(options["声骸评分"].default_config, {
            "角色评分模板": DEFAULT_TEMPLATE,
            "显示主副词条框体": True,
            "Show Debug Boxes": False,
        })
        self.assertNotIn("Development Overlay", options)

    def test_template_dropdown_contains_every_xwuid_template(self):
        option = next(item for item in config["global_configs"] if item.name == "声骸评分")
        self.assertEqual(template_names(), option.config_type["角色评分模板"]["options"])

    def test_status_label_identifies_echo_overlay(self):
        self.assertEqual(STATUS_TEXT, "ECHO-ON")


if __name__ == "__main__":
    unittest.main()
