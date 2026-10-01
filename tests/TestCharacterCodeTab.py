import os
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QFontDatabase, QImage, QPainter

from PySide6.QtWidgets import QApplication, QDialog, QStyleOptionViewItem
from qfluentwidgets import ComboBox, LineEdit, MessageBox, MessageBoxBase, TableWidget, TextEdit

from ok.util.config import Config
from src.char.Chixia import Chixia
from src.char.Aemeath import Aemeath
from src.char.Augusta import Augusta
from src.char.Baizhi import Baizhi
from src.char.Chisa import Chisa
from src.Labels import Labels
from src.char.CustomCharLoader import (
    TEAM_CODE_MODE_BUILTIN, TEAM_CODE_MODE_IMPORT, TEAM_CODE_STATE_NONE, clear_team_char_cache,
    create_custom_team, delete_custom_team, export_custom_team, get_custom_team_folder, get_team_code_mode,
    read_builtin_char_code, read_team_char_code, read_team_import_code, save_team_char_code,
    save_team_import_code, set_team_code_mode, switch_all_teams_code_mode, switch_team_code_mode,
    team_code_state,
)
from src.char.Mortefi import Mortefi
from src.char.Suisui import Suisui
from src.char.Verina import Verina
from src.char.YangyangXuanling import YangyangXuanling
from src.gui.CharacterCodeTab import (
    STATE_DOT_SIZE, CharacterCodeTab, ExportTeamDialog, ImportTeamDialog,
    TeamSelectionDialog, WorkshopDialog, fetch_workshop_codes, team_state_color, workshop_team_url,
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

    @staticmethod
    def _imported_code(class_name):
        return (
            f"from src.char.{class_name} import {class_name} as Builtin{class_name}\n"
            "\n\n"
            f"class {class_name}(Builtin{class_name}):\n"
            '    team_marker = "imported"\n'
        )

    def test_reset_button_switches_team_code_between_imported_and_built_in(self):
        team = (Mortefi, Chixia, Verina)
        create_custom_team(team)
        for char_cls in team:
            save_team_char_code(team, char_cls, read_builtin_char_code(char_cls))
            save_team_import_code(team, char_cls, read_builtin_char_code(char_cls))
        imported_code = self._imported_code(Mortefi.__name__)
        save_team_char_code(team, Mortefi, imported_code)
        save_team_import_code(team, Mortefi, imported_code)
        set_team_code_mode(team, TEAM_CODE_MODE_IMPORT)

        tab = CharacterCodeTab()
        try:
            with (
                patch("src.gui.CharacterCodeTab.MessageBox") as message_box,
                patch("src.gui.CharacterCodeTab.show_info_bar"),
            ):
                message_box.return_value.exec.return_value = True
                self.assertEqual(tab.reset_button.text(), "Switch to Built In Code")

                tab.member_combo.setCurrentIndex(tab.member_combo.findData(Mortefi.__name__))
                self.assertIs(tab.current_char_cls, Mortefi)
                self.assertEqual(tab.editor.toPlainText(), imported_code)

                tab.reset_button.click()

                self.assertEqual(read_team_char_code(team, Mortefi), read_builtin_char_code(Mortefi))
                self.assertEqual(read_team_import_code(team, Mortefi), imported_code)
                self.assertEqual(get_team_code_mode(team), TEAM_CODE_MODE_BUILTIN)
                self.assertEqual(tab.editor.toPlainText(), read_builtin_char_code(Mortefi))
                self.assertEqual(tab.reset_button.text(), "Switch to Imported Code")

                tab.reset_button.click()

                self.assertEqual(read_team_char_code(team, Mortefi), imported_code)
                self.assertEqual(read_team_import_code(team, Mortefi), imported_code)
                self.assertEqual(get_team_code_mode(team), TEAM_CODE_MODE_IMPORT)
                self.assertEqual(tab.editor.toPlainText(), imported_code)
                self.assertEqual(tab.reset_button.text(), "Switch to Built In Code")
        finally:
            tab.deleteLater()

    def test_workshop_url_uses_sorted_team_slug(self):
        self.assertEqual(
            workshop_team_url((Baizhi, Augusta, Aemeath)),
            "https://okwwcharcode.ok-script.com/teams/Aemeath_Augusta_Baizhi.json",
        )

    def test_workshop_url_sanitizes_character_name_punctuation(self):
        self.assertEqual(
            workshop_team_url((YangyangXuanling, Chisa, Suisui)),
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

    # --- team code mode marker and global switch ---------------------------------

    def _make_teams(self):
        """Team A runs imported code, team B still runs built in code but owns an
        imported copy, team C was never imported at all."""
        team_a = (Mortefi, Chixia, Verina)
        team_b = (Chisa, Baizhi, Aemeath)
        team_c = (Augusta, Suisui, YangYangSp)
        for team in (team_a, team_b, team_c):
            create_custom_team(team)
        for char_cls in team_a:
            save_team_char_code(team_a, char_cls, self._imported_code(char_cls.__name__))
            save_team_import_code(team_a, char_cls, self._imported_code(char_cls.__name__))
        set_team_code_mode(team_a, TEAM_CODE_MODE_IMPORT)
        for char_cls in team_b:
            save_team_import_code(team_b, char_cls, self._imported_code(char_cls.__name__))
        # team C stays on untouched built in code with no imported copy
        return team_a, team_b, team_c

    @staticmethod
    def _names(team):
        return tuple(sorted(char_cls.__name__ for char_cls in team))

    def _assert_painted_state(self, image, state):
        colors = {image.pixelColor(x, y).name() for x in range(image.width()) for y in range(image.height())}
        other = TEAM_CODE_MODE_IMPORT if state == TEAM_CODE_MODE_BUILTIN else TEAM_CODE_MODE_BUILTIN
        self.assertIn(team_state_color(state).name(), colors)
        self.assertNotIn(team_state_color(other).name(), colors)

    def _assert_icon_color(self, button, state):
        # button.icon() drops the color of a colored fluent icon, only the painted button keeps it
        self._assert_painted_state(button.grab().toImage(), state)

    @staticmethod
    def _painted_row(tab, item):
        """Paint one row with the delegate of the list; a hidden list has no room for every row."""
        team_list = tab.team_list
        index = team_list.indexFromItem(item)
        option = QStyleOptionViewItem()
        team_list.initViewItemOption(option)
        option.rect = QRect(QPoint(0, 0), QSize(300, team_list.itemDelegate().sizeHint(option, index).height()))
        image = QImage(option.rect.size(), QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        team_list.itemDelegate().paint(painter, option, index)
        painter.end()
        return image

    def _assert_team_marked(self, tab, team, state):
        _row, item = self._row(tab, team)
        self._assert_painted_state(self._painted_row(tab, item), state)

    def _row(self, tab, team):
        for row in range(tab.team_list.count()):
            item = tab.team_list.item(row)
            if tuple(item.data(Qt.UserRole)) == self._names(team):
                return row, item
        raise AssertionError(f"team {team} missing from the list")

    def test_team_list_marks_imported_and_built_in_code(self):
        """A team is blue exactly while its members run imported code."""
        team_a, team_b, team_c = self._make_teams()

        tab = CharacterCodeTab()
        try:
            for team, state, tooltip in (
                    (team_a, TEAM_CODE_MODE_IMPORT, "Imported code is in effect"),
                    (team_b, TEAM_CODE_MODE_BUILTIN, "Built in code is in effect"),
                    (team_c, TEAM_CODE_MODE_BUILTIN, "Never imported code, skipped by Switch All")):
                _row, item = self._row(tab, team)
                self._assert_team_marked(tab, team, state)
                self.assertEqual(item.toolTip(), tooltip)
        finally:
            tab.deleteLater()

    def test_team_state_dot_is_level_with_the_team_name(self):
        """The style would center an icon on the row, while the text lands up to two
        pixels lower; the dot has to line up with the text instead."""
        # the offscreen platform has no fonts and draws every glyph as a box
        font_file = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "msyh.ttc"
        if not font_file.is_file():
            self.skipTest("needs Microsoft YaHei, the font the team list uses for Chinese")
        font_id = QFontDatabase.addApplicationFont(str(font_file))
        self.addCleanup(QFontDatabase.removeApplicationFont, font_id)
        team_a, _team_b, _team_c = self._make_teams()

        tab = CharacterCodeTab()
        try:
            _row, item = self._row(tab, team_a)
            item.setText("炽霞, 莫特斐, 维里奈")
            image = self._painted_row(tab, item)
            ratio = image.devicePixelRatio()
            core = team_state_color(TEAM_CODE_MODE_IMPORT).name()
            dot = [(x, y) for y in range(image.height()) for x in range(image.width())
                   if image.pixelColor(x, y).name() == core]
            text_left = max(x for x, _y in dot) + round(STATE_DOT_SIZE * ratio)
            ink = Counter(y for y in range(image.height()) for x in range(text_left, image.width())
                          if image.pixelColor(x, y).alpha() >= 128)
            # glyph body only: rows with a tenth of the densest row, which drops comma tails
            body = [y for y, count in ink.items() if count >= 0.1 * max(ink.values())]
            dot_rows = [y for _x, y in dot]
            dot_middle = (min(dot_rows) + max(dot_rows) + 1) / 2 / ratio
            text_middle = (min(body) + max(body) + 1) / 2 / ratio
            self.assertLessEqual(abs(dot_middle - text_middle), 0.5, (dot_middle, text_middle))
        finally:
            tab.deleteLater()

    def test_imported_code_equal_to_built_in_code_still_counts_as_imported(self):
        """An import may ship the built in code unchanged; the team still runs imported code."""
        team = (Mortefi, Chixia, Verina)
        create_custom_team(team)
        for char_cls in team:
            save_team_import_code(team, char_cls, read_builtin_char_code(char_cls))
        set_team_code_mode(team, TEAM_CODE_MODE_IMPORT)

        tab = CharacterCodeTab()
        try:
            self._assert_team_marked(tab, team, TEAM_CODE_MODE_IMPORT)
            self.assertEqual(tab.reset_button.text(), "Switch to Built In Code")
            self.assertTrue(tab.switch_all_button.isEnabled())
        finally:
            tab.deleteLater()

    def test_never_imported_team_only_resets_the_editor(self):
        """A created team has nothing to switch: its button puts the built in code of
        the current character into the editor and writes nothing."""
        team = (Mortefi, Chixia, Verina)
        create_custom_team(team)
        local_code = read_builtin_char_code(Mortefi) + "\n# local only\n"
        save_team_char_code(team, Mortefi, local_code)

        tab = CharacterCodeTab()
        try:
            self.assertIs(tab.current_char_cls, Chixia)
            self.assertEqual(tab.reset_button.text(), "Reset to Built In")
            self.assertFalse(tab.reset_button.isEnabled())

            tab.member_combo.setCurrentIndex(tab.member_combo.findData(Mortefi.__name__))
            self.assertEqual(tab.reset_button.text(), "Reset to Built In")
            self.assertTrue(tab.reset_button.isEnabled())
            with (
                patch("src.gui.CharacterCodeTab.MessageBox") as message_box,
                patch("src.gui.CharacterCodeTab.show_info_bar"),
            ):
                message_box.return_value.exec.return_value = True
                tab.reset_button.click()

            self.assertEqual(tab.editor.toPlainText(), read_builtin_char_code(Mortefi))
            self.assertFalse(tab.reset_button.isEnabled())
            self.assertEqual(read_team_char_code(team, Mortefi), local_code)
            self.assertEqual(team_code_state(team), TEAM_CODE_STATE_NONE)
        finally:
            tab.deleteLater()

    def test_save_gives_a_never_imported_team_imported_code_without_asking(self):
        team = (Mortefi, Chixia, Verina)
        create_custom_team(team)

        tab = CharacterCodeTab()
        try:
            code = self._imported_code(Chixia.__name__)
            self.assertIs(tab.current_char_cls, Chixia)
            tab.editor.setPlainText(code)
            with (
                patch("src.gui.CharacterCodeTab.MessageBox") as message_box,
                patch("src.gui.CharacterCodeTab.show_info_bar") as info_bar,
            ):
                tab.save_button.click()

            message_box.assert_not_called()
            self.assertIn("The whole team's current code is now its imported code.", info_bar.call_args[0][1])
            self.assertEqual(team_code_state(team), TEAM_CODE_MODE_IMPORT)
            self.assertEqual(read_team_import_code(team, Chixia), code)
            self.assertEqual(read_team_import_code(team, Mortefi), read_builtin_char_code(Mortefi))
            self._assert_team_marked(tab, team, TEAM_CODE_MODE_IMPORT)
            self.assertEqual(tab.reset_button.text(), "Switch to Built In Code")
            self.assertFalse(tab._has_unsaved_changes())
        finally:
            tab.deleteLater()

    def test_save_on_built_in_code_asks_before_replacing_the_imported_code(self):
        _team_a, team_b, _team_c = self._make_teams()

        tab = CharacterCodeTab()
        try:
            row, _item = self._row(tab, team_b)
            tab.team_list.setCurrentRow(row)
            char_cls = tab.current_char_cls
            edited_code = read_builtin_char_code(char_cls) + "\n# edited\n"
            tab.editor.setPlainText(edited_code)
            with (
                patch("src.gui.CharacterCodeTab.MessageBox") as message_box,
                patch("src.gui.CharacterCodeTab.show_info_bar"),
            ):
                message_box.return_value.exec.return_value = False
                tab.save_button.click()

                self.assertIn("Baizhi", message_box.call_args[0][1])
                self.assertEqual(team_code_state(team_b), TEAM_CODE_MODE_BUILTIN)
                self.assertEqual(read_team_char_code(team_b, char_cls), read_builtin_char_code(char_cls))
                self.assertEqual(read_team_import_code(team_b, char_cls), self._imported_code(char_cls.__name__))

                message_box.return_value.exec.return_value = True
                tab.save_button.click()

            self.assertEqual(team_code_state(team_b), TEAM_CODE_MODE_IMPORT)
            self.assertEqual(read_team_import_code(team_b, char_cls), edited_code)
            self.assertEqual(read_team_import_code(team_b, Baizhi), read_builtin_char_code(Baizhi))
        finally:
            tab.deleteLater()

    def test_team_switch_updates_the_marker_of_that_team(self):
        team_a, _team_b, _team_c = self._make_teams()

        tab = CharacterCodeTab()
        try:
            row, _item = self._row(tab, team_a)
            tab.team_list.setCurrentRow(row)

            with (
                patch("src.gui.CharacterCodeTab.MessageBox") as message_box,
                patch("src.gui.CharacterCodeTab.show_info_bar"),
                patch.object(CharacterCodeTab, "_reload_live_team_code", return_value=0),
            ):
                message_box.return_value.exec.return_value = True
                tab.reset_button.click()

            self._assert_team_marked(tab, team_a, TEAM_CODE_MODE_BUILTIN)
            self.assertEqual(get_team_code_mode(team_a), TEAM_CODE_MODE_BUILTIN)
            # the global button follows the very same state
            self.assertEqual(tab.switch_all_button.text(), "Switch All to Imported Code")
        finally:
            tab.deleteLater()

    def test_switch_all_button_icon_matches_the_state_it_switches_to(self):
        team_a, team_b, _team_c = self._make_teams()

        tab = CharacterCodeTab()
        try:
            row, _item = self._row(tab, team_a)
            tab.team_list.setCurrentRow(row)
            self.assertEqual(tab.current_team, self._names(team_a))
            self.assertEqual(tab.reset_button.text(), "Switch to Built In Code")
            self._assert_icon_color(tab.reset_button, TEAM_CODE_MODE_BUILTIN)
            # team B is not on imported code yet, so the global button offers it
            self.assertEqual(tab.switch_all_button.text(), "Switch All to Imported Code")
            self._assert_icon_color(tab.switch_all_button, TEAM_CODE_MODE_IMPORT)

            set_team_code_mode(team_b, TEAM_CODE_MODE_IMPORT)
            tab._refresh_team_list()
            # every switchable team is imported now, so the button flips direction
            self.assertEqual(tab.switch_all_button.text(), "Switch All to Built In Code")
            self._assert_icon_color(tab.switch_all_button, TEAM_CODE_MODE_BUILTIN)
        finally:
            tab.deleteLater()

    def test_switch_all_code_mode_switches_every_team_that_owns_imported_code(self):
        team_a, team_b, team_c = self._make_teams()

        tab = CharacterCodeTab()
        try:
            with (
                patch("src.gui.CharacterCodeTab.MessageBox") as message_box,
                patch("src.gui.CharacterCodeTab.show_info_bar"),
            ):
                message_box.return_value.exec.return_value = True
                tab.switch_all_button.click()

            self.assertEqual(get_team_code_mode(team_b), TEAM_CODE_MODE_IMPORT)
            self.assertEqual(read_team_char_code(team_b, Baizhi), self._imported_code("Baizhi"))
            self.assertEqual(get_team_code_mode(team_a), TEAM_CODE_MODE_IMPORT)
            # team C never imported code, so nothing was adopted for it
            self.assertEqual(team_code_state(team_c), TEAM_CODE_STATE_NONE)

            with (
                patch("src.gui.CharacterCodeTab.MessageBox") as message_box,
                patch("src.gui.CharacterCodeTab.show_info_bar"),
            ):
                message_box.return_value.exec.return_value = True
                tab.switch_all_button.click()

            for team in (team_a, team_b):
                self.assertEqual(get_team_code_mode(team), TEAM_CODE_MODE_BUILTIN)
            self.assertEqual(team_code_state(team_c), TEAM_CODE_STATE_NONE)
        finally:
            tab.deleteLater()

    def test_switch_all_code_mode_keeps_the_imported_copy_of_every_team(self):
        team_a, team_b, _team_c = self._make_teams()
        for char_cls in team_a:
            save_team_import_code(team_a, char_cls, self._imported_code(char_cls.__name__))
        save_team_char_code(team_a, Mortefi, self._imported_code(Mortefi.__name__))
        set_team_code_mode(team_a, TEAM_CODE_MODE_IMPORT)

        tab = CharacterCodeTab()
        try:
            with (
                patch("src.gui.CharacterCodeTab.MessageBox") as message_box,
                patch("src.gui.CharacterCodeTab.show_info_bar"),
            ):
                message_box.return_value.exec.return_value = True
                tab.switch_all_button.click()
                tab.switch_all_button.click()

            self.assertEqual(get_team_code_mode(team_a), TEAM_CODE_MODE_BUILTIN)
            self.assertEqual(read_team_char_code(team_a, Mortefi), read_builtin_char_code(Mortefi))
            self.assertEqual(read_team_import_code(team_a, Mortefi), self._imported_code(Mortefi.__name__))
            self.assertEqual(get_team_code_mode(team_b), TEAM_CODE_MODE_BUILTIN)
            self.assertTrue(read_team_import_code(team_b, Chisa))
        finally:
            tab.deleteLater()

    def test_switch_all_code_mode_keeps_locally_edited_code_out_of_the_switch(self):
        _team_a, _team_b, team_c = self._make_teams()
        local_code = read_builtin_char_code(Augusta) + "\n# local only\n"
        save_team_char_code(team_c, Augusta, local_code)

        tab = CharacterCodeTab()
        try:
            with (
                patch("src.gui.CharacterCodeTab.MessageBox") as message_box,
                patch("src.gui.CharacterCodeTab.show_info_bar"),
            ):
                message_box.return_value.exec.return_value = True
                tab._switch_all_code_mode()

            self.assertEqual(read_team_char_code(team_c, Augusta), local_code)
            self.assertEqual(get_team_code_mode(team_c), TEAM_CODE_MODE_BUILTIN)
            self.assertEqual(team_code_state(team_c), TEAM_CODE_STATE_NONE)
        finally:
            tab.deleteLater()

    def test_switch_all_code_mode_without_any_imported_team_reports_and_does_nothing(self):
        create_custom_team((Mortefi, Chixia, Verina))

        tab = CharacterCodeTab()
        try:
            self.assertFalse(tab.switch_all_button.isEnabled())
            with (
                patch("src.gui.CharacterCodeTab.show_info_bar") as info_bar,
                patch("src.gui.CharacterCodeTab.MessageBox") as message_box,
            ):
                tab._switch_all_code_mode()

            info_bar.assert_called_once()
            self.assertIn("No team has imported code to switch.", info_bar.call_args[0][1])
            message_box.assert_not_called()
            self.assertEqual(tab.switch_all_button.text(), "Switch All to Imported Code")
        finally:
            tab.deleteLater()

    def test_switch_with_discarded_changes_asks_once_and_keeps_the_member(self):
        team_a, _team_b, _team_c = self._make_teams()

        tab = CharacterCodeTab()
        try:
            row, _item = self._row(tab, team_a)
            tab.team_list.setCurrentRow(row)
            tab.member_combo.setCurrentIndex(1)
            char_cls = tab.current_char_cls
            tab.editor.setPlainText(tab.editor.toPlainText() + "\n# unsaved\n")
            with (
                patch("src.gui.CharacterCodeTab.MessageBox") as message_box,
                patch("src.gui.CharacterCodeTab.show_info_bar"),
                patch.object(CharacterCodeTab, "_confirm_switch_changes", return_value="discard"),
                patch.object(CharacterCodeTab, "_confirm_discard_changes", return_value=True) as discard,
            ):
                message_box.return_value.exec.return_value = True
                tab.switch_all_button.click()

            discard.assert_not_called()
            self.assertEqual(tab.member_combo.currentIndex(), 1)
            self.assertIs(tab.current_char_cls, char_cls)
            self.assertEqual(tab.editor.toPlainText(), read_team_char_code(team_a, char_cls))
            self.assertFalse(tab._has_unsaved_changes())
        finally:
            tab.deleteLater()

    def test_switching_teams_with_unsaved_changes_asks_once(self):
        team_a, team_b, _team_c = self._make_teams()

        tab = CharacterCodeTab()
        try:
            row_a, _item = self._row(tab, team_a)
            tab.team_list.setCurrentRow(row_a)
            tab.editor.setPlainText(tab.editor.toPlainText() + "\n# unsaved\n")
            row_b, _item = self._row(tab, team_b)
            with patch.object(CharacterCodeTab, "_confirm_discard_changes", return_value=True) as discard:
                tab.team_list.setCurrentRow(row_b)

            discard.assert_called_once()
            self.assertEqual(tab.current_team, self._names(team_b))
        finally:
            tab.deleteLater()

    def test_switch_all_reloads_every_switched_team(self):
        team_a, team_b, _team_c = self._make_teams()
        switch_team_code_mode(team_b, TEAM_CODE_MODE_IMPORT)

        tab = CharacterCodeTab()
        try:
            with (
                patch("src.gui.CharacterCodeTab.MessageBox") as message_box,
                patch("src.gui.CharacterCodeTab.show_info_bar"),
                patch.object(CharacterCodeTab, "_reload_live_team_code", return_value=0) as reload,
            ):
                message_box.return_value.exec.return_value = True
                tab.switch_all_button.click()

            self.assertEqual({call.args[0] for call in reload.call_args_list},
                             {self._names(team_a), self._names(team_b)})
        finally:
            tab.deleteLater()

    def test_switch_all_partial_failure_leaves_the_failed_team_whole(self):
        team_a, team_b, _team_c = self._make_teams()
        switch_team_code_mode(team_a, TEAM_CODE_MODE_BUILTIN)
        from src.char import CustomCharLoader
        load_class = CustomCharLoader._load_team_char_class_from_file

        def load_or_fail(char_cls, team, path):
            if char_cls is Baizhi:
                raise RuntimeError("broken member")
            return load_class(char_cls, team, path)

        tab = CharacterCodeTab()
        try:
            with (
                patch("src.gui.CharacterCodeTab.MessageBox") as message_box,
                patch("src.gui.CharacterCodeTab.show_info_bar") as info_bar,
                patch("src.char.CustomCharLoader._load_team_char_class_from_file", side_effect=load_or_fail),
            ):
                message_box.return_value.exec.return_value = True
                tab.switch_all_button.click()

            self.assertEqual(team_code_state(team_a), TEAM_CODE_MODE_IMPORT)
            self.assertEqual(team_code_state(team_b), TEAM_CODE_MODE_BUILTIN)
            for char_cls in team_b:
                self.assertEqual(read_team_char_code(team_b, char_cls), read_builtin_char_code(char_cls))
            self.assertEqual(info_bar.call_args.kwargs["title"], "Partially Completed")
            self.assertTrue(info_bar.call_args.kwargs["error"])
        finally:
            tab.deleteLater()

    def test_switch_asks_before_dropping_code_neither_side_keeps(self):
        _team_a, team_b, _team_c = self._make_teams()
        local_code = read_builtin_char_code(Baizhi) + "\n# local only\n"
        save_team_char_code(team_b, Baizhi, local_code)

        tab = CharacterCodeTab()
        try:
            row, _item = self._row(tab, team_b)
            tab.team_list.setCurrentRow(row)
            self.assertEqual(tab.reset_button.text(), "Switch to Imported Code")
            with (
                patch("src.gui.CharacterCodeTab.show_info_bar"),
                patch.object(CharacterCodeTab, "_confirm_switch_changes", return_value="cancel") as ask,
            ):
                tab.reset_button.click()

            self.assertIn("Baizhi", ask.call_args[0][1])
            self.assertEqual(read_team_char_code(team_b, Baizhi), local_code)
            self.assertEqual(team_code_state(team_b), TEAM_CODE_MODE_BUILTIN)

            with (
                patch("src.gui.CharacterCodeTab.show_info_bar"),
                patch.object(CharacterCodeTab, "_confirm_switch_changes", return_value="save"),
            ):
                tab.reset_button.click()

            self.assertEqual(team_code_state(team_b), TEAM_CODE_MODE_IMPORT)
            self.assertEqual(read_team_char_code(team_b, Baizhi), local_code)
            self.assertEqual(read_team_import_code(team_b, Baizhi), local_code)
            self.assertEqual(read_team_import_code(team_b, Chisa), read_builtin_char_code(Chisa))
        finally:
            tab.deleteLater()

    def test_workshop_import_asks_first_and_selects_the_imported_team(self):
        team_a = (Mortefi, Chixia, Verina)
        team_b = (Chisa, Baizhi, Aemeath)
        create_custom_team(team_b)
        for char_cls in team_b:
            save_team_char_code(team_b, char_cls, self._imported_code(char_cls.__name__))
        archive = export_custom_team(
            team_b, Path(self.temp_dir.name) / "out", "Team", "Description", "Tester", "1")
        delete_custom_team(team_b)
        create_custom_team(team_a)

        tab = CharacterCodeTab()
        try:
            tab.editor.setPlainText(tab.editor.toPlainText() + "\n# unsaved\n")
            with (
                patch("src.gui.CharacterCodeTab.fetch_all_workshop_teams", return_value=[]) as fetch,
                patch("src.gui.CharacterCodeTab.WorkshopDialog"),
                patch.object(CharacterCodeTab, "_confirm_discard_changes", return_value=False),
            ):
                tab._open_workshop()
            fetch.assert_not_called()
            self.assertTrue(tab._has_unsaved_changes())

            with (
                patch("src.gui.CharacterCodeTab.fetch_all_workshop_teams", return_value=[]) as fetch,
                patch("src.gui.CharacterCodeTab.WorkshopDialog"),
                patch.object(CharacterCodeTab, "_confirm_discard_changes", return_value=True) as discard,
                patch.object(ImportTeamDialog, "exec", return_value=True),
                patch("src.gui.CharacterCodeTab.show_info_bar"),
            ):
                tab._open_workshop()
                fetch.assert_called_once()
                # the very call the workshop import makes after downloading
                tab._preview_and_import_archive(archive, expected_team=None)

            discard.assert_called_once()
            self.assertEqual(tab.current_team, self._names(team_b))
            self.assertEqual(tuple(tab.team_list.currentItem().data(Qt.UserRole)), self._names(team_b))
            self.assertEqual(team_code_state(team_b), TEAM_CODE_MODE_IMPORT)
        finally:
            tab.deleteLater()

    def test_switch_all_teams_code_mode_ignores_unknown_mode(self):
        with self.assertRaises(ValueError):
            switch_all_teams_code_mode("nonsense")


if __name__ == "__main__":
    unittest.main()
