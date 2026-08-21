import tempfile
import unittest
import zipfile
import json
from pathlib import Path
from unittest.mock import patch

from ok.util.config import Config
from src.Labels import Labels
from src.char.Baizhi import Baizhi
from src.char.Chixia import Chixia
from src.char.CharFactory import apply_team_char_classes
from src.char.CustomCharLoader import (
    clear_custom_char_cache, clear_team_char_cache, create_custom_team, export_custom_team,
    get_custom_char_file, get_team_char_file, import_custom_team, inspect_team_archive,
    list_custom_teams, load_custom_char_class, remove_custom_char_code, save_custom_char_code,
    save_team_char_code, set_custom_char_enabled,
)
from src.char.Mortefi import Mortefi
from src.char.Verina import Verina


class TestCustomCharLoader(unittest.TestCase):
    def setUp(self):
        self.old_config_folder = Config.config_folder
        self.temp_dir = tempfile.TemporaryDirectory()
        Config.config_folder = self.temp_dir.name
        clear_custom_char_cache()
        clear_team_char_cache()

    def tearDown(self):
        clear_custom_char_cache()
        clear_team_char_cache()
        Config.config_folder = self.old_config_folder
        self.temp_dir.cleanup()

    def test_loads_enabled_custom_char_class(self):
        code = """
from src.char.Mortefi import Mortefi as BuiltinMortefi


class Mortefi(BuiltinMortefi):
    custom_marker = True
"""
        save_custom_char_code(Mortefi, code, use_custom=True)

        custom_cls = load_custom_char_class(Mortefi)

        self.assertIsNot(custom_cls, Mortefi)
        self.assertTrue(custom_cls.custom_marker)
        self.assertTrue(issubclass(custom_cls, Mortefi))

    def test_disabled_custom_char_uses_builtin_class(self):
        code = """
from src.char.Mortefi import Mortefi as BuiltinMortefi


class Mortefi(BuiltinMortefi):
    custom_marker = True
"""
        save_custom_char_code(Mortefi, code, use_custom=True)
        set_custom_char_enabled(Mortefi, False)

        self.assertIs(load_custom_char_class(Mortefi), Mortefi)

    def test_remove_custom_char_code_deletes_file_and_uses_builtin_class(self):
        code = """
from src.char.Mortefi import Mortefi as BuiltinMortefi


class Mortefi(BuiltinMortefi):
    custom_marker = True
"""
        save_custom_char_code(Mortefi, code, use_custom=True)

        remove_custom_char_code(Mortefi)

        self.assertFalse(get_custom_char_file(Mortefi).exists())
        self.assertIs(load_custom_char_class(Mortefi), Mortefi)

    def test_failed_save_restores_previous_custom_code(self):
        code = """
from src.char.Mortefi import Mortefi as BuiltinMortefi


class Mortefi(BuiltinMortefi):
    custom_marker = True
"""
        save_custom_char_code(Mortefi, code, use_custom=True)

        with self.assertRaises(RuntimeError):
            save_custom_char_code(Mortefi, "class NotMortefi: pass", use_custom=True)

        self.assertEqual(get_custom_char_file(Mortefi).read_text(encoding="utf-8"), code)
        self.assertTrue(load_custom_char_class(Mortefi).custom_marker)

    def test_team_code_only_applies_to_matching_team(self):
        class Task:
            chars = []

        team = (Mortefi, Chixia, Verina)
        create_custom_team(team)
        code = """
from src.char.Mortefi import Mortefi as BuiltinMortefi


class Mortefi(BuiltinMortefi):
    custom_marker = "matching-team"
"""
        save_team_char_code(team, Mortefi, code)
        task = Task()
        task.chars = [
            Mortefi(task, 0, char_name=Labels.char_mortefi, confidence=0.99),
            Chixia(task, 1, char_name=Labels.char_chixia, confidence=0.99),
            Verina(task, 2, char_name=Labels.char_verina, confidence=0.99),
        ]

        apply_team_char_classes(task, task.chars)

        self.assertEqual(task.chars[0].custom_marker, "matching-team")

        other_task = Task()
        other_task.chars = [
            Mortefi(other_task, 0, char_name=Labels.char_mortefi, confidence=0.99),
            Chixia(other_task, 1, char_name=Labels.char_chixia, confidence=0.99),
            Baizhi(other_task, 2, char_name=Labels.char_baizhi, confidence=0.99),
        ]
        apply_team_char_classes(other_task, other_task.chars)
        self.assertIs(type(other_task.chars[0]), Mortefi)

    def test_same_character_can_have_different_code_in_two_teams(self):
        first_team = (Mortefi, Chixia, Verina)
        second_team = (Mortefi, Chixia, Baizhi)
        create_custom_team(first_team)
        create_custom_team(second_team)
        first_code = self._team_code("first")
        second_code = self._team_code("second")
        save_team_char_code(first_team, Mortefi, first_code)
        save_team_char_code(second_team, Mortefi, second_code)

        class Task:
            chars = []

        first_task = Task()
        first_task.chars = self._chars(first_task, Verina)
        second_task = Task()
        second_task.chars = self._chars(second_task, Baizhi)
        apply_team_char_classes(first_task, first_task.chars)
        apply_team_char_classes(second_task, second_task.chars)

        self.assertEqual(first_task.chars[0].team_marker, "first")
        self.assertEqual(second_task.chars[0].team_marker, "second")
        self.assertIsNot(type(first_task.chars[0]), type(second_task.chars[0]))

    def test_list_custom_teams_skips_unreadable_team_folder(self):
        valid_team = (Mortefi, Chixia, Verina)
        create_custom_team(valid_team)
        unreadable_folder = Path(self.temp_dir.name) / "custom_teams" / "Aemeath__Augusta__Baizhi"
        unreadable_folder.mkdir()
        original_is_file = Path.is_file

        def is_file(path):
            if path.parent == unreadable_folder:
                raise PermissionError(5, "Access is denied", str(path))
            return original_is_file(path)

        with patch.object(Path, "is_file", is_file):
            teams = list_custom_teams()

        self.assertEqual(teams, [tuple(sorted(
            (cls.__name__ for cls in valid_team), key=str.casefold
        ))])

    def test_export_and_import_team_archive(self):
        team = (Mortefi, Chixia, Verina)
        create_custom_team(team)
        archive = export_custom_team(
            team, self.temp_dir.name, name="My Team", description="Rotation",
            author="Tester", version="1.2.3",
        )
        self.assertEqual(archive.name, "My_Team_Tester_1.2.3.zip")
        with zipfile.ZipFile(archive) as exported:
            manifest = json.loads(exported.read("team.json"))
            self.assertEqual(set(manifest), {"name", "description", "author", "version", "team"})
            self.assertEqual(manifest["name"], "My_Team")
            self.assertEqual(manifest["team"], ", ".join(sorted(manifest["team"].split(", "), key=str.casefold)))

        info = inspect_team_archive(archive)
        self.assertNotIn("\r", info["codes"][Mortefi.__name__])
        import_custom_team(info)
        self.assertEqual(info["team"], tuple(sorted((cls.__name__ for cls in team), key=str.casefold)))
        self.assertNotIn(b"\r\r\n", get_team_char_file(team, Mortefi).read_bytes())

    @staticmethod
    def _team_code(marker):
        return f'''\nfrom src.char.Mortefi import Mortefi as BuiltinMortefi\n\n\nclass Mortefi(BuiltinMortefi):\n    team_marker = "{marker}"\n'''

    @staticmethod
    def _chars(task, third_cls):
        third_label = Labels.char_verina if third_cls is Verina else Labels.char_baizhi
        return [
            Mortefi(task, 0, char_name=Labels.char_mortefi, confidence=0.99),
            Chixia(task, 1, char_name=Labels.char_chixia, confidence=0.99),
            third_cls(task, 2, char_name=third_label, confidence=0.99),
        ]


if __name__ == "__main__":
    unittest.main()
