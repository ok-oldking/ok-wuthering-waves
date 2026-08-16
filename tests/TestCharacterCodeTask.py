import base64
import io
import tempfile
import unittest
from types import SimpleNamespace

from ok.task.web import call_task_tab_operation, configured_web_custom_tabs
from ok.ui.web.app import register_task_tabs
from ok.util.config import Config
from PIL import Image

from src.char.Chixia import Chixia
from src.char.CustomCharLoader import clear_custom_char_cache, is_custom_char_enabled
from src.task.CharacterCodeTask import CharacterCodeTask
from config import config


class TestCharacterCodeTask(unittest.TestCase):
    def test_qt_and_web_tabs_have_separate_configuration(self):
        self.assertEqual(
            ["src.task.CharacterCodeTask", "CharacterCodeTask"],
            configured_web_custom_tabs(config["web_tabs"])[0],
        )
        self.assertEqual(
            [["src.gui.CharacterCodeTab", "CharacterCodeTab"]],
            config["custom_tabs"],
        )

    def setUp(self):
        self.old_config_folder = Config.config_folder
        self.temp_dir = tempfile.TemporaryDirectory()
        Config.config_folder = self.temp_dir.name
        clear_custom_char_cache()
        self.executor = SimpleNamespace(scene=None)
        self.executor.get_all_tasks = lambda: [self.task]
        app = SimpleNamespace(tr=lambda value: value)
        self.task = CharacterCodeTask(executor=self.executor, app=app)
        self.task.after_init(executor=self.executor, scene=None)

    def tearDown(self):
        self.task.on_destroy()
        clear_custom_char_cache()
        Config.config_folder = self.old_config_folder
        self.temp_dir.cleanup()

    def test_exposes_character_state_through_allowlisted_task_api(self):
        manifest = register_task_tabs([self.task])[0].manifest()
        self.assertEqual(manifest["id"], "character-code")
        self.assertFalse(manifest["task_controls"])

        characters = call_task_tab_operation(self.task, "query", "characters")
        chixia = next(item for item in characters if item["class_name"] == "Chixia")

        self.assertFalse(chixia["has_custom"])
        detail = call_task_tab_operation(
            self.task, "query", "character", {"class_name": "Chixia"}
        )
        self.assertIn("class Chixia", detail["builtin_code"])
        self.assertFalse(detail["use_custom"])
        self.assertTrue(detail["image_data_url"].startswith("data:image/png;base64,"))
        image_bytes = base64.b64decode(detail["image_data_url"].split(",", 1)[1])
        with Image.open(io.BytesIO(image_bytes)) as image:
            self.assertLessEqual(image.width, 48)
            self.assertLessEqual(image.height, 48)

    def test_save_mode_and_reset_match_qt_character_storage(self):
        code = self._custom_code(Chixia)
        saved = call_task_tab_operation(
            self.task,
            "action",
            "save",
            {"class_name": "Chixia", "code": code},
        )

        self.assertTrue(saved["has_custom"])
        self.assertTrue(saved["use_custom"])
        self.assertEqual(saved["code"], code)
        self.assertTrue(is_custom_char_enabled(Chixia))

        builtin = call_task_tab_operation(
            self.task,
            "action",
            "mode",
            {"class_name": "Chixia", "use_custom": False},
        )
        self.assertFalse(builtin["use_custom"])
        self.assertNotEqual(builtin["code"], code)

        reset = call_task_tab_operation(
            self.task, "action", "reset", {"class_name": "Chixia"}
        )
        self.assertFalse(reset["has_custom"])
        self.assertFalse(is_custom_char_enabled(Chixia))

    @staticmethod
    def _custom_code(char_cls):
        class_name = char_cls.__name__
        return f"""
from src.char.{class_name} import {class_name} as Builtin{class_name}


class {class_name}(Builtin{class_name}):
    custom_marker = True
"""


if __name__ == "__main__":
    unittest.main()
