"""Small application hooks needed by the score overlay."""

from ok import og
from ok.core.events import communicate


class Globals:
    _game_window_visible = False

    def __init__(self, exit_event):
        app = getattr(og, "app", None)
        if app is not None:
            app.get_overlay_view()
        communicate.window.connect(self._update_game_overlay)

    def on_show_main_window(self, main_window):
        from src.gui.SearchableTemplateDropdown import install_searchable_template_dropdown
        install_searchable_template_dropdown(main_window)

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
        if key == "显示主副词条框体" and not value:
            from src.gui.EchoStatOverlay import ECHO_STAT_PAINTER_KEY
            overlay.clear_draw(ECHO_STAT_PAINTER_KEY)
        if key == "启用声骸评分" and not value:
            from src.gui.EchoStatOverlay import ECHO_STAT_PAINTER_KEY
            from src.task.EchoStatOverlayTask import STATUS_PAINTER_KEY
            overlay.clear_draw(ECHO_STAT_PAINTER_KEY)
            overlay.clear_draw(STATUS_PAINTER_KEY)
