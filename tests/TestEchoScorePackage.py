import json
from pathlib import Path
import tempfile
import unittest

from scripts.build_echo_score_okscript import build_import_folder


class TestEchoScorePackage(unittest.TestCase):
    def test_direct_import_folder_is_self_contained_and_has_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = build_import_folder(Path(temp) / "echo-score", "9.9.9")
            manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))

            self.assertEqual({
                "file_name": "echo-score",
                "script_name": "声骸评分",
                "version": "9.9.9",
            }, manifest)
            for name in (
                "echo_score.py", "xwuid_echo_data.py", "echo_stat_overlay.py",
                "overlay_status.py", "echo_score_settings.py", "echo_score_task.py",
            ):
                text = (folder / name).read_text(encoding="utf-8")
                self.assertNotIn("from src.", text)

            settings = (folder / "echo_score_settings.py").read_text(encoding="utf-8")
            self.assertIn("card.setExpand(True)", settings)
            self.assertIn("输入角色名搜索", settings)
            self.assertIn("card.onetime = False", settings)
            self.assertIn('"Show Debug Boxes": {"hidden": True}', settings)

            worker = (folder / "echo_score_task.py").read_text(encoding="utf-8")
            self.assertIn("remembered_template", worker)
            self.assertIn('set_overlay_setting("boxes", True)', worker)
            self.assertIn("overlay.set_boxes_enabled(False)", worker)


if __name__ == "__main__":
    unittest.main()
