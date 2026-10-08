import unittest
from unittest.mock import Mock
import numpy as np

from ok import og
from src.gui.EchoStatOverlay import ECHO_STAT_PAINTER_KEY
from src.task.EchoStatOverlayTask import EchoStatOverlayTask


class TestEchoStatOverlayTask(unittest.TestCase):
    def make_task(self):
        task = EchoStatOverlayTask.__new__(EchoStatOverlayTask)
        task.echo_score_config = {
            "启用声骸评分": True,
            "自动匹配评分模板": False,
            "角色评分模板": "通用",
        }
        task.debug_config = {"Show Debug Boxes": False}
        task.painter = Mock()
        task._executor = Mock()
        task._executor.method.width = 1600
        task._executor.method.height = 900
        task._executor.method.get_frame.return_value = np.zeros((900, 1600, 3), dtype=np.uint8)
        task.ocr_default_threshold = 0.2
        task.ocr = Mock(return_value=[])
        task.ocr_fun = Mock(return_value=lambda *args: (task.ocr(), []))
        # Render path, not the host's no-op trigger scheduling hook.
        task.get_overlay_view = Mock()
        return task

    def setUp(self):
        self.previous_device_manager = getattr(og, "device_manager", None)
        og.device_manager = None
        self.overlay_patch = unittest.mock.patch("src.task.EchoStatOverlayTask.ensure_echo_overlay")
        self.ensure_overlay = self.overlay_patch.start()

    def tearDown(self):
        self.overlay_patch.stop()
        og.device_manager = self.previous_device_manager

    def test_disabled_feature_clears_score_and_status(self):
        task = self.make_task()
        task.echo_score_config["启用声骸评分"] = False
        overlay = Mock()
        task.get_overlay_view = Mock(return_value=overlay)
        self.ensure_overlay.return_value = overlay

        self.assertFalse(task.render_score())
        self.assertEqual(
            [call.args[0] for call in overlay.clear_draw.call_args_list],
            ["echo-stat-boxes", "echo-score-status"],
        )

    def test_unrecognized_page_clears_status_watermark(self):
        task = self.make_task()
        overlay = Mock()
        task.get_overlay_view = Mock(return_value=overlay)
        self.ensure_overlay.return_value = overlay
        task.ocr = Mock(return_value=[])

        self.assertTrue(task.render_score())
        overlay.clear_draw.assert_any_call("echo-score-status")

    def test_missing_capture_clears_overlay_and_can_resume_next_frame(self):
        task = self.make_task()
        overlay = Mock()
        task.get_overlay_view = Mock(return_value=overlay)
        self.ensure_overlay.return_value = overlay
        task._executor.method = None
        task.ocr = Mock(return_value=[])
        self.assertFalse(task.render_score())
        task.ocr.assert_not_called()
        overlay.clear_draw.assert_any_call("echo-score-status")
        task._executor.method = Mock(width=1600, height=900)
        task._executor.method.get_frame.return_value = np.zeros((900, 1600, 3), dtype=np.uint8)
        self.assertTrue(task.render_score())
        task.ocr.assert_called_once()

    def test_hidden_worker_repairs_legacy_disabled_state(self):
        task = EchoStatOverlayTask.__new__(EchoStatOverlayTask)
        task.config = {"_enabled": False}

        task.on_create()

        self.assertTrue(task.enabled)
        self.assertTrue(task.config["_enabled"])

    def test_enabled_score_draws_recognized_boxes(self):
        task = self.make_task()
        overlay = Mock()
        task.get_overlay_view = Mock(return_value=overlay)
        self.ensure_overlay.return_value = overlay
        task.ocr = Mock(return_value=[])
        with unittest.mock.patch(
            "src.task.EchoStatOverlayTask.analyze_echo_stats",
            return_value=Mock(
                rectangles=[Mock()], row_scores=[1.0], summary="score", tier_labels=["1档"],
                tier_colors=[(80, 235, 130)],
            ),
        ):
            self.assertTrue(task.render_score())

        overlay.draw.assert_any_call(ECHO_STAT_PAINTER_KEY, task.painter.paint)

    def test_auto_match_setting_is_forwarded_to_analysis(self):
        task = self.make_task()
        task.echo_score_config["自动匹配评分模板"] = True
        overlay = Mock()
        task.get_overlay_view = Mock(return_value=overlay)
        self.ensure_overlay.return_value = overlay
        task.ocr = Mock(return_value=[])
        with unittest.mock.patch(
            "src.task.EchoStatOverlayTask.analyze_echo_stats",
            return_value=Mock(
                rectangles=[], row_scores=[], summary="", tier_labels=[], tier_colors=[],
            ),
        ) as analyze:
            task.render_score()

        self.assertTrue(analyze.call_args.kwargs["auto_match"])

    def test_background_game_preserves_last_recognized_boxes(self):
        task = self.make_task()
        overlay = Mock()
        task.get_overlay_view = Mock(return_value=overlay)
        self.ensure_overlay.return_value = overlay
        task.ocr = Mock()
        task.painter.rectangles = [Mock()]
        og.device_manager = Mock(hwnd_window=Mock(exists=True, visible=False))

        self.assertFalse(task.render_score())

        task.ocr.assert_not_called()
        overlay.clear_draw.assert_not_called()
