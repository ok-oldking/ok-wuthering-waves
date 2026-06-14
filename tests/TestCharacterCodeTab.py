import os
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from ok.util.config import Config
from src.char.Chixia import Chixia
from src.char.CustomCharLoader import clear_custom_char_cache, is_custom_char_enabled, save_custom_char_code
from src.char.Mortefi import Mortefi
from src.gui.CharacterCodeTab import CharacterCodeTab


class TestCharacterCodeTab(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.old_config_folder = Config.config_folder
        self.temp_dir = tempfile.TemporaryDirectory()
        Config.config_folder = self.temp_dir.name
        clear_custom_char_cache()

    def tearDown(self):
        clear_custom_char_cache()
        Config.config_folder = self.old_config_folder
        self.temp_dir.cleanup()

    def test_builtin_mode_persists_when_switching_between_custom_saved_chars(self):
        save_custom_char_code(Mortefi, self._custom_code(Mortefi), use_custom=True)
        save_custom_char_code(Chixia, self._custom_code(Chixia), use_custom=True)

        tab = CharacterCodeTab()
        try:
            tab.char_list.setCurrentRow(self._row_for_char(tab, Chixia))
            self.assertTrue(tab.custom_radio.isChecked())

            tab.builtin_radio.setChecked(True)
            self.assertFalse(is_custom_char_enabled(Chixia))

            tab.char_list.setCurrentRow(self._row_for_char(tab, Mortefi))
            self.assertTrue(tab.custom_radio.isChecked())

            tab.char_list.setCurrentRow(self._row_for_char(tab, Chixia))
            self.assertTrue(tab.builtin_radio.isChecked())
            self.assertFalse(tab.custom_radio.isChecked())
        finally:
            tab.deleteLater()

    def _row_for_char(self, tab, char_cls):
        for row in range(tab.char_list.count()):
            item = tab.char_list.item(row)
            if item.data(Qt.UserRole) == char_cls.__name__:
                return row
        raise AssertionError(f"{char_cls.__name__} not found in character list")

    def _custom_code(self, char_cls):
        class_name = char_cls.__name__
        return f"""
from src.char.{class_name} import {class_name} as Builtin{class_name}


class {class_name}(Builtin{class_name}):
    custom_marker = True
"""


if __name__ == "__main__":
    unittest.main()
