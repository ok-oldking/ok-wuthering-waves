"""Small application hooks needed by the score overlay."""

from ok import og
from ok.core.events import communicate


class Globals:
    _game_window_visible = False
    _notification_switches = (
        "System Notification",
        "Discord Notification",
        "Telegram Notification",
        "Enterprise WeChat Webhook Notification",
        "QQ Bot API Notification",
        "SMTP Notification",
        "QQ Desktop Notification (Not Reliable)",
        "WeChat Desktop Notification (Not Reliable)",
    )

    def __init__(self, exit_event):
        notification_config = og.global_config.get_config("Notification")
        for key in self._notification_switches:
            if notification_config.get(key):
                notification_config[key] = False
        app = getattr(og, "app", None)
        if app is not None:
            app.get_overlay_view()
        communicate.window.connect(self._update_game_overlay)

    def on_show_main_window(self, main_window):
        from src.gui.SearchableTemplateDropdown import install_searchable_template_dropdown
        self._hide_notification_settings(main_window)
        self._customize_related_projects(main_window)
        install_searchable_template_dropdown(main_window)

    @staticmethod
    def _customize_related_projects(main_window):
        """Keep relevant upstream projects and add the scoring-data source."""
        from ok.ui.qt.about.ProjectCard import ProjectCard

        about_tab = getattr(main_window, "about_tab", None)
        if about_tab is None:
            return
        cards = list(about_tab.findChildren(ProjectCard))
        if not cards:
            return
        grid_widget = cards[0].parentWidget()
        layout = grid_widget.layout()
        keep_urls = {
            "https://github.com/ok-oldking/ok-script",
            "https://github.com/ok-oldking/ok-script-app",
            "https://github.com/ok-oldking/ok-wuthering-waves",
        }
        kept = []
        for card in cards:
            layout.removeWidget(card)
            if card.url.rstrip("/") in keep_urls:
                kept.append(card)
            else:
                card.hide()
                card.deleteLater()

        xwuid_url = "https://github.com/Loping151/XutheringWavesUID"
        kept.append(ProjectCard("XutheringWavesUID", xwuid_url, parent=grid_widget))
        for index, card in enumerate(kept):
            layout.addWidget(card, index // 2, index % 2)

    @staticmethod
    def _hide_notification_settings(main_window):
        """Remove the framework's internal notification card from Settings."""
        setting_tab = getattr(main_window, "setting_tab", None)
        notification_config = og.global_config.get_config("Notification")
        cards = getattr(setting_tab, "config_groups", None)
        if cards is None:
            return
        for card in tuple(cards):
            if getattr(card, "config", None) is notification_config:
                card.hide()
                cards.remove(card)

    @staticmethod
    def _update_game_overlay(visible, *geometry):
        hwnd_window = getattr(getattr(og, "device_manager", None), "hwnd_window", None)
        game_exists = bool(getattr(hwnd_window, "exists", visible))
        has_geometry = len(geometry) < 6 or bool(geometry[4] and geometry[5])
        Globals._game_window_visible = game_exists and has_geometry
        app = getattr(og, "app", None)
        overlay = app.get_overlay_view() if app is not None else None
        if overlay is not None and geometry:
            overlay.update_overlay(Globals._game_window_visible, *geometry)

    @classmethod
    def apply_echo_score_setting_change(cls, key, value):
        app = getattr(og, "app", None)
        if app is None:
            return
        overlay = app.get_overlay_view()
        if overlay is None:
            return
        if key == "Show Debug Boxes":
            overlay.set_boxes_enabled(bool(value))
        if key == "启用声骸评分" and not value:
            from src.gui.EchoStatOverlay import ECHO_STAT_PAINTER_KEY
            from src.task.EchoStatOverlayTask import STATUS_PAINTER_KEY
            overlay.clear_draw(ECHO_STAT_PAINTER_KEY)
            overlay.clear_draw(STATUS_PAINTER_KEY)
