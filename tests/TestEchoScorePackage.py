import tempfile
import unittest
from pathlib import Path
import importlib
import sys
from unittest.mock import Mock
import zipfile

from ok.core.script_packager import import_script
from scripts.build_echo_score_okscript import build


class TestEchoScorePackage(unittest.TestCase):
    def test_builds_importable_self_contained_okscript(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = build(root / "dist", version="9.9.9")
            self.assertTrue(package.is_file())
            with zipfile.ZipFile(package) as archive:
                names = set(archive.namelist())
                self.assertTrue({
                    "manifest.json", "echo_score.py", "xwuid_echo_data.py",
                    "echo_stat_overlay.py", "overlay_status.py",
                    "echo_score_settings.py", "echo_score_task.py", "README.md",
                }.issubset(names))
                for name in (
                    "echo_score.py", "echo_stat_overlay.py",
                    "echo_score_settings.py", "echo_score_task.py",
                ):
                    self.assertNotIn("from src.", archive.read(name).decode("utf-8"))

            success, message, folder = import_script(package, import_base=root / "imports")
            self.assertTrue(success, message)
            self.assertEqual(Path(folder).name, "echo-score")
            sys.path.insert(0, folder)
            try:
                module = importlib.import_module("echo_score_task")
                self.assertEqual(module.EchoScoreOverlayTask.__name__, "EchoScoreOverlayTask")
                settings = importlib.import_module("echo_score_settings")
                self.assertEqual(settings.EchoScoreSettingsTask.__name__, "EchoScoreSettingsTask")
                executor = Mock()
                app = Mock()
                settings_task = settings.EchoScoreSettingsTask(executor=executor, app=app)
                worker = module.EchoScoreOverlayTask(executor=executor, app=app)
                self.assertTrue(settings_task.default_config["启用声骸评分"])
                self.assertFalse(worker.visible)
                self.assertTrue(worker.default_config["_enabled"])
            finally:
                sys.path.remove(folder)
                for name in (
                    "echo_score_task", "echo_score_settings", "echo_stat_overlay", "overlay_status",
                    "echo_score", "xwuid_echo_data",
                ):
                    sys.modules.pop(name, None)


if __name__ == "__main__":
    unittest.main()
