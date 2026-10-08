import json
from pathlib import Path
import tempfile
import runpy
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import numpy as np
from ok.feature.Box import Box

from ok import og
from src.echo_capture_recovery import read_echo_frame
from src.echo_runtime import EchoScoreRuntime
from src.gui.EchoStatOverlay import analyze_echo_stats

from scripts.build_echo_score_okscript import build_import_folder


class TestEchoScorePackage(unittest.TestCase):
    def test_generated_package_scores_three_restarts_while_host_remains_paused(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = build_import_folder(Path(temp) / "echo-score", "9.9.9")
            task = self.make_portable_worker(folder, Mock(side_effect=EchoScoreRuntime))
            task._executor.paused = True
            task._executor._last_frame_time = 0
            task._executor.current_task = None
            image = np.zeros((900, 1600, 3), dtype=np.uint8)
            capture = SimpleNamespace(width=1600, height=900,
                get_frame=Mock(return_value=image), connected=lambda: True, close=Mock())
            task._executor.method = capture
            task._settings = Mock(return_value={"启用声骸评分": True, "角色评分模板": "角色-通用"})
            task._ensure_overlay.return_value = Mock()
            boxes = [Box(48, 42, 120, 30, name="聲骸強化")]
            for y, label, value in ((212, "生命", "22.8%"), (248, "生命", "2280"),
                                     (285, "共鳴效率", "10.8%"), (319, "共鳴解放傷害加成", "10.1%")):
                boxes.extend([Box(177, y, 180, 28, name=label), Box(478, y, 70, 28, name=value)])
            task.ocr_fun = Mock(return_value=lambda *args: (boxes, boxes))
            task.render_score.__globals__["analyze_echo_stats"].side_effect = analyze_echo_stats
            window = SimpleNamespace(hwnd=100, exists=True, visible=True, pos_valid=True)
            manager = SimpleNamespace(hwnd_window=window, executor=task._executor, capture_method=capture,
                get_preferred_device=lambda: {"device": "windows", "real_hwnd": window.hwnd}, refresh=Mock())
            with patch.object(og, "device_manager", manager), patch.object(EchoScoreRuntime, "start"):
                task.after_init(executor=task._executor)
                runtime = task.score_runtime
                self.assertFalse(runtime.poll())
                task._executor.paused = False
                runtime.poll()
                task._executor.paused = True
                for cycle in range(3):
                    window.exists = False
                    runtime.poll()
                    window.exists = True
                    window.hwnd += 1
                    runtime.poll()
                    self.assertTrue(task._executor.paused)
                    rectangles, scores, summary = task.painter.update.call_args.args[:3]
                    self.assertEqual(4, len(rectangles))
                    self.assertIn("当前评分：", summary)
                    self.assertTrue(task.enabled)
                self.assertEqual(3, manager.refresh.call_count)
                self.assertEqual(4, task._ensure_overlay.return_value.draw.call_count // 2)
                task.on_destroy()

    def make_portable_worker(self, folder, monitor_factory):
        # Load the actual generated adapter, isolating its imported helpers.
        monitor_factory.return_value.stopped = False
        helpers = {
            "echo_score": SimpleNamespace(DEFAULT_TEMPLATE="角色-通用"),
            "echo_capture_recovery": SimpleNamespace(read_echo_frame=read_echo_frame),
            "echo_runtime": SimpleNamespace(EchoScoreRuntime=monitor_factory),
            "echo_overlay_recovery": SimpleNamespace(ensure_echo_overlay=Mock()),
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
        task.ocr_default_threshold = 0.2
        return task

    def test_imported_worker_survives_capture_removed_during_ocr(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = build_import_folder(Path(temp) / "echo-score", "9.9.9")
            task = self.make_portable_worker(folder, Mock(return_value=Mock()))
            overlay = Mock()
            task._ensure_overlay.return_value = overlay
            task._settings = Mock(return_value={"启用声骸评分": True})
            task._executor.method = SimpleNamespace(width=1600, height=900,
                get_frame=lambda: np.zeros((900, 1600, 3), dtype=np.uint8))
            def close_game(*args):
                task._executor.method = None
                return [], []
            task.ocr_fun = Mock(return_value=close_game)
            window = SimpleNamespace(hwnd=100, exists=True, visible=True)
            with patch.object(og, "device_manager", SimpleNamespace(hwnd_window=window)):
                task.after_init(executor=task._executor)
                self.assertFalse(task.render_score())
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
                factory.assert_called_once_with(task, manager, task.executor.exit_event)
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
                factory.assert_called_once_with(task, manager, task.executor.exit_event)

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
                "echo_score.py", "echo_text.py", "echo_capture_recovery.py", "echo_runtime.py", "echo_overlay_recovery.py",
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
            self.assertIn("ensure_echo_overlay", worker)
            self.assertIn("EchoScoreRuntime", worker)
            self.assertIn("direct=True", worker)


if __name__ == "__main__":
    unittest.main()
