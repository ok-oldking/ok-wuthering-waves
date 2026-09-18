import os
import json
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from qfluentwidgets import ComboBox, LineEdit, MessageBoxBase, TableWidget, TextEdit

from ok.util.config import Config
from src.char.Chixia import Chixia
from src.char.Aemeath import Aemeath
from src.char.Augusta import Augusta
from src.char.Baizhi import Baizhi
from src.char.Chisa import Chisa
from src.Labels import Labels
from src.char.CustomCharLoader import (
    clear_team_char_cache, create_custom_team, get_custom_team_folder, read_team_char_code,
)
from src.char.Mortefi import Mortefi
from src.char.Suisui import Suisui
from src.char.Verina import Verina
from src.char.YangYangSp import YangYangSp
from src.gui.CharacterCodeTab import (
    CharacterCodeTab, ExportTeamDialog, ImportTeamDialog, TeamSelectionDialog,
    WorkshopDialog, fetch_workshop_codes, workshop_team_url,
)


class TestCharacterCodeTab(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.old_config_folder = Config.config_folder
        self.temp_dir = tempfile.TemporaryDirectory()
        Config.config_folder = self.temp_dir.name
        clear_team_char_cache()

    def tearDown(self):
        clear_team_char_cache()
        Config.config_folder = self.old_config_folder
        self.temp_dir.cleanup()

    def test_team_lists_three_editable_character_codes(self):
        team = (Mortefi, Chixia, Verina)
        create_custom_team(team)

        tab = CharacterCodeTab()
        try:
            self.assertEqual(tab.team_list.count(), 1)
            self.assertEqual(tab.member_combo.count(), 3)
            self.assertIsNotNone(tab.current_char_cls)
            self.assertEqual(tab.editor.toPlainText(), read_team_char_code(team, tab.current_char_cls))
        finally:
            tab.deleteLater()

    def test_create_team_defaults_to_detected_team(self):
        tab = CharacterCodeTab()
        try:
            task = SimpleNamespace(chars=[
                Chixia(None, 0, char_name=Labels.char_chixia),
                Mortefi(None, 1, char_name=Labels.char_mortefi),
                Verina(None, 2, char_name=Labels.char_verina),
            ])
            tab.executor = SimpleNamespace(onetime_tasks=[task], trigger_tasks=[])
            self.assertEqual(set(tab._detected_team()), {Chixia, Mortefi, Verina})
        finally:
            tab.deleteLater()

    def test_delete_team_button_deletes_selected_team(self):
        team = (Mortefi, Chixia, Verina)
        create_custom_team(team)
        tab = CharacterCodeTab()
        try:
            with (
                patch("src.gui.CharacterCodeTab.MessageBox") as message_box,
                patch("src.gui.CharacterCodeTab.show_info_bar"),
            ):
                message_box.return_value.exec.return_value = True
                tab.delete_team_button.click()

            self.assertFalse(get_custom_team_folder(team).exists())
            self.assertEqual(tab.team_list.count(), 0)
            self.assertFalse(tab.delete_team_button.isEnabled())
        finally:
            tab.deleteLater()

    def test_workshop_url_uses_sorted_team_slug(self):
        self.assertEqual(
            workshop_team_url((Baizhi, Augusta, Aemeath)),
            "https://okwwcharcode.ok-script.com/teams/Aemeath_Augusta_Baizhi.json",
        )

    def test_workshop_url_sanitizes_character_name_punctuation(self):
        self.assertEqual(
            workshop_team_url((YangYangSp, Chisa, Suisui)),
            "https://okwwcharcode.ok-script.com/teams/Chisa_Suisui_Yangyang_Xuanling.json",
        )

    def test_workshop_codes_are_sorted_by_timestamp_descending(self):
        payload = {
            "members": ["Aemeath", "Augusta", "Baizhi"],
            "codes": [{"name": "older", "timestamp": 10}, {"name": "newer", "timestamp": 20}],
        }

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def read(self, _size):
                return json.dumps(payload).encode("utf-8")

        with (
            patch("src.gui.CharacterCodeTab.urlopen", return_value=Response()),
            patch("src.gui.CharacterCodeTab.logger.info") as log_info,
        ):
            codes = fetch_workshop_codes((Aemeath, Augusta, Baizhi))
        self.assertEqual([code["name"] for code in codes], ["newer", "older"])
        log_info.assert_called_once_with(
            "char code workshop request: "
            "https://okwwcharcode.ok-script.com/teams/Aemeath_Augusta_Baizhi.json"
        )

    def test_workshop_404_is_an_empty_list(self):
        error = HTTPError("https://example.invalid", 404, "Not Found", {}, None)
        with patch("src.gui.CharacterCodeTab.urlopen", side_effect=error):
            self.assertEqual(fetch_workshop_codes((Aemeath, Augusta, Baizhi)), [])

    def test_team_dialogs_use_fluent_widgets(self):
        parent = CharacterCodeTab()
        try:
            create_dialog = TeamSelectionDialog(
                [Aemeath, Augusta, Baizhi], [Aemeath, Augusta, Baizhi], parent)
            export_dialog = ExportTeamDialog("Aemeath_Augusta_Baizhi", parent)
            import_dialog = ImportTeamDialog(
                {"name": "Team", "description": "Description", "version": "1.0.0"},
                "Aemeath, Augusta, Baizhi", parent)
            workshop_dialog = WorkshopDialog([{
                "name": "Team", "description": "Description", "author": "Author",
                "version": "1.0.0", "timestamp": 1, "sizeFormatted": "1 KB",
            }], "Aemeath, Augusta, Baizhi", parent)
            dialogs = (create_dialog, export_dialog, import_dialog, workshop_dialog)
            self.assertTrue(all(isinstance(dialog, MessageBoxBase) for dialog in dialogs))
            self.assertTrue(all(isinstance(combo, ComboBox) for combo in create_dialog.combos))
            self.assertIsInstance(export_dialog.name_edit, LineEdit)
            self.assertIsInstance(export_dialog.description_edit, TextEdit)
            self.assertIsNotNone(workshop_dialog.findChild(TableWidget))
            self.assertIn("Aemeath, Augusta, Baizhi", workshop_dialog.windowTitle())
            self.assertEqual(workshop_dialog.yesButton.text(), "Close")
        finally:
            parent.deleteLater()


if __name__ == "__main__":
    unittest.main()
