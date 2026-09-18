import unittest

from config import config
from ok.util.GlobalConfig import GlobalConfig, register_notification_options
from src.echo_score import DEFAULT_TEMPLATE, template_names
from src.gui.OverlayStatus import STATUS_TEXT


class TestEchoScoreConfig(unittest.TestCase):
    def test_echo_score_is_the_only_app_config_tab(self):
        visible_tabs = [
            option.name
            for option in config["global_configs"]
            if option.show_at_tab
        ]

        self.assertEqual(visible_tabs, ["声骸评分"])

    def test_framework_notification_config_is_hidden_and_disabled(self):
        options = {option.name: option for option in config["global_configs"]}
        notification = options["Notification"]

        self.assertFalse(notification.show_at_tab)
        self.assertTrue(notification.default_config)
        self.assertFalse(any(notification.default_config.values()))

        global_config = GlobalConfig(config["global_configs"])
        register_notification_options(global_config)
        visible_tabs = [
            option.name
            for _, _, option in global_config.get_all_visible_configs()
            if option.show_at_tab
        ]
        self.assertEqual(["声骸评分"], visible_tabs)

    def test_score_tab_has_one_enable_switch_and_debug_lives_in_settings(self):
        options = {option.name: option for option in config["global_configs"]}

        self.assertEqual(options["声骸评分"].default_config, {
            "启用声骸评分": True,
            "自动匹配评分模板": False,
            "角色评分模板": DEFAULT_TEMPLATE,
        })
        self.assertFalse(options["开发调试"].show_at_tab)
        self.assertEqual(options["开发调试"].default_config, {"Show Debug Boxes": False})
        self.assertNotIn("Development Overlay", options)

    def test_minimal_app_registers_only_hidden_score_worker(self):
        self.assertEqual(config["onetime_tasks"], [])
        self.assertEqual(config["trigger_tasks"], [
            ["src.task.EchoStatOverlayTask", "EchoStatOverlayTask"]
        ])
        self.assertNotIn("scene", config)
        self.assertNotIn("template_matching", config)
        self.assertNotIn("custom_tasks", config)
        self.assertEqual(config["gui_title"], "声骸评分")
        self.assertTrue(config["use_overlay"])

    def test_template_dropdown_contains_every_xwuid_template(self):
        option = next(item for item in config["global_configs"] if item.name == "声骸评分")
        self.assertEqual(template_names(), option.config_type["角色评分模板"]["options"])

    def test_status_label_identifies_echo_overlay(self):
        self.assertEqual(STATUS_TEXT, "WUWA.ICEHE.LIFE | Powered by OKWW x XWUID")

    def test_about_credits_both_upstreams_and_combined_license(self):
        about = config["about"]
        self.assertIn("XutheringWavesUID", about)
        self.assertIn("GPL-3.0", about)
        self.assertIn("AGPL-3.0", about)


if __name__ == "__main__":
    unittest.main()
