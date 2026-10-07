import json
from pathlib import Path
import tempfile
import runpy
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from ok import og
from src.echo_capture_recovery import read_echo_frame

from scripts.build_echo_score_okscript import build_import_folder


class TestEchoScorePackage(unittest.TestCase):
    def make_portable_worker(self, folder, monitor_factory):
        # Load the actual generated adapter, isolating its imported helpers.
        helpers = {
            "echo_score": SimpleNamespace(DEFAULT_TEMPLATE="角色-通用"),
            "echo_capture_recovery": SimpleNamespace(CaptureRecoveryMonitor=monitor_factory, read_echo_frame=read_echo_frame),
            "echo_stat_overlay": SimpleNamespace(
                ECHO_STAT_PAINTER_KEY="echo-stat-boxes", EchoStatBoxPainter=Mock(), analyze_echo_stats=Mock()),
            "overlay_status": SimpleNamespace(paint_okww_status=Mock()),
        }
        with patch.dict(sys.modules, helpers):
            cls = runpy.run_path(str(folder / "echo_score_task.py"))["EchoScoreOverlayTask"]
        task = cls.__new__(cls)
        task.config = {"_enabled": False}
        task._executor = SimpleNamespace(exit_event=threading.Event(), scene=None)
        task.load_config = Mock()
        task._ensure_overlay = Mock(return_value=None)
        task.get_overlay_view = Mock(return_value=None)
        task.painter = Mock(rectangles=[])
        return task

    def test_imported_worker_survives_capture_removed_during_ocr(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = build_import_folder(Path(temp) / "echo-score", "9.9.9")
            task = self.make_portable_worker(folder, Mock(return_value=Mock()))
            overlay = Mock()
            task._ensure_overlay.return_value = overlay
            task._settings = Mock(return_value={"启用声骸评分": True})
            task._executor.method = SimpleNamespace(width=1600, height=900)
            def close_game():
                task._executor.method = None
                return []
            task.ocr = close_game
            window = SimpleNamespace(hwnd=100, exists=True, visible=True)
            with patch.object(og, "device_manager", SimpleNamespace(hwnd_window=window)):
                task.after_init(executor=task._executor)
                self.assertFalse(task.run())
            self.assertTrue(task.enabled)
            overlay.clear_draw.assert_any_call("echo-score-status")

    def test_official_import_lifecycle_starts_recovery_without_post_init(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = build_import_folder(Path(temp) / "echo-score", "9.9.9")
            recovery = Mock()
            factory = Mock(return_value=recovery)
            task = self.make_portable_worker(folder, factory)
            manager = Mock()
            with patch.object(og, "device_manager", manager):
                # Official TaskManager calls after_init, but never post_init
                # when loading imported scripts. Verify that exact lifecycle.
                task.after_init(executor=task._executor)
                factory.assert_called_once_with(manager, task.executor.exit_event)
                recovery.start.assert_called_once()
                task._ensure_overlay.assert_not_called()
                task.post_init()
                task.run()
                factory.assert_called_once()
                recovery.start.assert_called_once()
                task.on_destroy()
                recovery.stop.assert_called_once()

    def test_import_retries_monitor_initialization_if_manager_arrives_late(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = build_import_folder(Path(temp) / "echo-score", "9.9.9")
            factory = Mock(return_value=Mock())
            task = self.make_portable_worker(folder, factory)
            with patch.object(og, "device_manager", None):
                task.after_init(executor=task._executor)
                factory.assert_not_called()
            manager = Mock()
            with patch.object(og, "device_manager", manager):
                task.run()
                factory.assert_called_once_with(manager, task.executor.exit_event)

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
                "echo_score.py", "echo_text.py", "echo_capture_recovery.py",
                "xwuid_echo_data.py", "echo_stat_overlay.py",
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
            self.assertIn("CaptureRecoveryMonitor", worker)


if __name__ == "__main__":
    unittest.main()
