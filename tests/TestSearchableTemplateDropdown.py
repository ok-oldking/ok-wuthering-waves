import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QComboBox, QHBoxLayout, QWidget

from src.gui.SearchableTemplateDropdown import (
    TemplateSearchComboBox,
    install_searchable_template_dropdown,
)


class FakeTemplateWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.key = "角色评分模板"
        self.config = {self.key: "爱弥斯"}
        self.tr_options = ["爱弥斯-通用", "洛瑟菈-霜渐", "洛瑟菈-声骸"]
        self.tr_dict = {name: name for name in self.tr_options}
        self.layout = QHBoxLayout(self)
        self.combo_box = QComboBox(self)
        self.layout.addWidget(self.combo_box)

    def update_config(self, value):
        self.config[self.key] = value


class TestSearchableTemplateDropdown(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_installs_searchable_selector_and_only_persists_exact_matches(self):
        widget = FakeTemplateWidget()
        tab = SimpleNamespace(
            option=SimpleNamespace(name="声骸评分"),
            config_widget_by_key={widget.key: widget},
        )
        main_window = SimpleNamespace(global_config_tabs=[tab])

        combo = install_searchable_template_dropdown(main_window)

        self.assertIsInstance(combo, TemplateSearchComboBox)
        self.assertEqual("爱弥斯-通用", widget.config[widget.key])
        combo.setText("洛瑟菈")
        self.assertEqual("爱弥斯-通用", widget.config[widget.key])
        combo.setText("洛瑟菈-声骸")
        self.assertEqual("洛瑟菈-声骸", widget.config[widget.key])


if __name__ == "__main__":
    unittest.main()
