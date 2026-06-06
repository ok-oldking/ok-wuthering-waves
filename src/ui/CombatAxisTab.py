from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSizePolicy
from qfluentwidgets import FluentIcon

from ok.gui.widget.Tab import Tab
from src.ui.CustomAxisEditor import CustomAxisEditorWidget


class CombatAxisTab(Tab):
    name = "战斗"
    icon = FluentIcon.CALORIES
    add_after_default_tabs = False
    position = None

    def __init__(self):
        super().__init__()
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        editor = CustomAxisEditorWidget(
            script_file='configs/custom_axis_script.txt',
            image_file='configs/custom_axis_flow.png',
            profiles_file='configs/custom_axis_profiles.json',
            close_on_save=False,
        )
        editor.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        editor.setMinimumWidth(1000)
        editor.setMinimumHeight(max(760, editor.minimumSizeHint().height()))
        self.add_card("打轴构建器", editor)
        self.view.setMinimumSize(1040, editor.minimumHeight() + 72)
