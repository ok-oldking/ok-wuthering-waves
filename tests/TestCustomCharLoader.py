import tempfile
import unittest

from ok.util.config import Config
from src.Labels import Labels
from src.char.CharFactory import get_char_by_pos
from src.char.CustomCharLoader import clear_custom_char_cache, get_custom_char_file, load_custom_char_class, \
    remove_custom_char_code, save_custom_char_code, set_custom_char_enabled
from src.char.Mortefi import Mortefi


class TestCustomCharLoader(unittest.TestCase):
    def setUp(self):
        self.old_config_folder = Config.config_folder
        self.temp_dir = tempfile.TemporaryDirectory()
        Config.config_folder = self.temp_dir.name
        clear_custom_char_cache()

    def tearDown(self):
        clear_custom_char_cache()
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

    def test_factory_replaces_old_char_when_active_class_changes(self):
        class FoundChar:
            confidence = 0.99

        class Task:
            debug = False

            def find_one(self, *args, **kwargs):
                return FoundChar()

            def log_info(self, *args, **kwargs):
                pass

        code = """
from src.char.Mortefi import Mortefi as BuiltinMortefi


class Mortefi(BuiltinMortefi):
    custom_marker = True
"""
        save_custom_char_code(Mortefi, code, use_custom=True)
        task = Task()
        old_char = Mortefi(task, 0, char_name=Labels.char_mortefi, confidence=0.99)

        char = get_char_by_pos(task, None, 0, old_char)

        self.assertIsNot(type(char), Mortefi)
        self.assertTrue(char.custom_marker)


if __name__ == "__main__":
    unittest.main()
