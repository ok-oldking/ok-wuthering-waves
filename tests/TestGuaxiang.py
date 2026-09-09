import hashlib
import json
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import cv2
import numpy as np

from src.utils.guaxiang import (
    ASSET_ROOT, GuaDetection, SEARCH_REGION, TEMPLATE_COLORS,
    _load_templates, _resolve_candidates, recognize_guaxiang,
)


ROOT = Path(__file__).resolve().parents[1]
SAMPLES = json.loads((ROOT / 'tests/images/guaxiang/manifest.json').read_text(encoding='utf-8'))


def read_sample(name):
    sample = next(item for item in SAMPLES if item['name'] == name)
    return cv2.imdecode(np.fromfile(ROOT / sample['path'], dtype=np.uint8), cv2.IMREAD_COLOR)


class TestGuaxiang(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frames = {sample['name']: read_sample(sample['name']) for sample in SAMPLES}

    def test_all_eleven_original_screenshots(self):
        times = []
        _load_templates()
        for sample in SAMPLES:
            with self.subTest(sample=sample['name']):
                raw = (ROOT / sample['path']).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), sample['sha256'])
                frame = self.frames[sample['name']]
                before = frame.copy()
                start = time.perf_counter()
                result = recognize_guaxiang(frame, hud_visible=True)
                times.append((time.perf_counter() - start) * 1000)
                self.assertEqual(result.sequence, sample['expected'], result)
                self.assertEqual(len(result.detections), len(sample['expected']))
                self.assertEqual(result.region, SEARCH_REGION)
                self.assertTrue(np.array_equal(frame, before), 'Recognition must not modify captured frames')
                centers = [item.box[0] + item.box[2] / 2 for item in result.detections]
                self.assertEqual(centers, sorted(centers))
        print(f'Guaxiang 11 screenshots: warm mean={np.mean(times):.2f} ms max={max(times):.2f} ms')

    def test_scaled_screenshots(self):
        # 人工缩放只验证坐标/插值，不代表对应分辨率的实机截图验证。
        for width, height in ((1280, 720), (1920, 1080), (2560, 1440)):
            for sample in SAMPLES:
                with self.subTest(size=(width, height), sample=sample['name']):
                    frame = cv2.resize(self.frames[sample['name']], (width, height))
                    result = recognize_guaxiang(frame, hud_visible=True)
                    self.assertEqual(result.sequence, sample['expected'], result)

    def test_synthetic_widescreen_center_anchor(self):
        for sample in SAMPLES:
            with self.subTest(sample=sample['name']):
                frame = np.zeros((900, 2100, 3), dtype=np.uint8)
                frame[:, 250:1850] = self.frames[sample['name']]
                result = recognize_guaxiang(frame, hud_visible=True)
                self.assertEqual(result.sequence, sample['expected'], result)
                self.assertEqual(result.region, (930, 725, 230, 70))

    def test_positions_are_searched_not_fixed_slots(self):
        frame = self.frames['mixed4'].copy()
        roi = frame[725:795, 680:910].copy()
        frame[725:795, 680:910] = np.roll(roi, (5, -9), axis=(0, 1))
        self.assertEqual(recognize_guaxiang(frame, hud_visible=True).sequence, ['黄', '蓝', '蓝', '蓝'])

    def test_invalid_or_hidden_hud_is_not_zero(self):
        for frame in (None, np.empty((0, 0, 3), np.uint8), np.zeros((900, 1600), np.uint8),
                      np.zeros((10, 10, 3), np.uint8), np.zeros((900, 1600, 3), np.float32)):
            with self.subTest(shape=getattr(frame, 'shape', None)):
                self.assertIsNone(recognize_guaxiang(frame, hud_visible=True).sequence)
        self.assertEqual(recognize_guaxiang(self.frames['empty'], hud_visible=True).sequence, [])
        self.assertIsNone(recognize_guaxiang(self.frames['empty'], hud_visible=False).sequence)
        self.assertIsNone(recognize_guaxiang(self.frames['blue4'], hud_visible=False).sequence)

    def test_wrong_color_and_missing_templates_are_uncertain(self):
        frame = self.frames['blue1'].copy()
        # 符文形状仍在，但交换 B/R 后颜色与蓝色类别不符。
        frame[725:795, 680:910] = frame[725:795, 680:910, ::-1]
        result = recognize_guaxiang(frame, hud_visible=True)
        self.assertIsNone(result.sequence)
        self.assertEqual(result.reason, 'low_confidence')
        with patch('src.utils.guaxiang._load_templates', side_effect=FileNotFoundError):
            result = recognize_guaxiang(self.frames['blue1'], hud_visible=True)
        self.assertIsNone(result.sequence)
        self.assertEqual(result.reason, 'templates_unavailable')

    def test_five_real_glyph_patches_are_not_truncated_to_four(self):
        frame = self.frames['empty'].copy()
        glyph = self.frames['blue1'][741:777, 777:808].copy()
        for x in (683, 725, 767, 809, 851):
            frame[741:777, x:x + 31] = glyph
        result = recognize_guaxiang(frame, hud_visible=True)
        self.assertIsNone(result.sequence)
        self.assertEqual(result.reason, 'too_many_candidates', result)

    def test_duplicate_peaks_conflict_and_low_confidence(self):
        first = GuaDetection('蓝', (750, 746, 21, 27), .9, .9)
        duplicate = GuaDetection('蓝', (751, 746, 21, 27), .8, .9)
        second = GuaDetection('黄', (805, 746, 21, 27), .9, .9)
        sequence, detections, _ = _resolve_candidates([second, duplicate, first])
        self.assertEqual(sequence, ['蓝', '黄'])
        self.assertEqual(len(detections), 2)
        conflict = GuaDetection('黄', first.box, .9, .9)
        self.assertEqual(_resolve_candidates([first, conflict])[2], 'color_conflict')
        weak = GuaDetection('黄', second.box, .55, .9)
        self.assertIsNone(_resolve_candidates([first, weak])[0])

    def test_real_annotation_references(self):
        data = json.loads((ASSET_ROOT / 'coco_annotations.json').read_text(encoding='utf-8'))
        for label, _ in TEMPLATE_COLORS:
            categories = [item for item in data['categories'] if item['name'] == label]
            self.assertEqual(len(categories), 1)
            category = categories[0]
            self.assertEqual(sum(item['id'] == category['id'] for item in data['categories']), 1)
            annotations = [a for a in data['annotations'] if a['category_id'] == category['id']]
            self.assertEqual(len(annotations), 1)
            annotation = annotations[0]
            self.assertEqual(sum(a['id'] == annotation['id'] for a in data['annotations']), 1)
            images = [item for item in data['images'] if item['id'] == annotation['image_id']]
            self.assertEqual(len(images), 1)
            self.assertTrue((ASSET_ROOT / images[0]['file_name']).is_file())
            self.assertEqual(annotation['bbox'], [782, 746, 21, 27])


class TestGuaxiangCharacterIntegration(unittest.TestCase):
    def make_char(self, name='mixed4', hud=True):
        from src.char.Douling import Douling
        char = Douling.__new__(Douling)
        char._segment = 1
        char._waiting_for_guaxiang = False
        char._guaxiang_error_logged = False
        char.task = SimpleNamespace(frame=read_sample(name), in_team=Mock(return_value=(hud, 1, 3)),
                                    debug=True, draw_boxes=Mock(), screenshot=Mock(), check_combat=Mock())
        char.task.next_frame = Mock(side_effect=lambda: char.task.frame)
        char.logger = Mock()
        char.normal_attack = Mock()
        char.clock = [0.0]
        timer = patch('src.char.Douling.time.monotonic', side_effect=lambda: char.clock[0])
        timer.start()
        self.addCleanup(timer.stop)
        char.sleep = Mock(side_effect=lambda duration: char.clock.__setitem__(0, char.clock[0] + duration))
        return char

    def test_entry_results_without_screenshots_or_boxes(self):
        for name, hud, expected in (('mixed4', True, ['黄', '蓝', '蓝', '蓝']),
                                    ('empty', True, []), ('blue4', False, None)):
            with self.subTest(name=name):
                char = self.make_char(name, hud)
                self.assertEqual(char.recognize_guaxiang('entry'), expected)
                char.logger.info.assert_called_once()
                message = char.logger.info.call_args.args[0]
                self.assertIn('point=entry', message)
                self.assertIn('status=uncertain reason=' if expected is None
                              else f'count={len(expected)} sequence=', message)
                char.task.screenshot.assert_not_called()
                char.task.draw_boxes.assert_not_called()

    def test_entry_recognition_precedes_both_segments_even_when_uncertain(self):
        for segment in (1, 2):
            char = self.make_char(hud=False)
            char._segment = segment
            events = []
            char.task.in_team.side_effect = lambda: events.append('entry') or (False, 1, 3)
            char._do_segment1 = lambda: events.append(1)
            char._do_segment2 = lambda: events.append(2)
            char.do_perform()
            self.assertEqual(events, ['entry', segment])
            char.logger.info.assert_called_once()

    def test_actual_hud_detection_on_all_screenshots(self):
        from ok.feature.FeatureSet import FeatureSet
        from src.task.BaseWWTask import BaseWWTask
        features = FeatureSet(False, str(ASSET_ROOT / 'coco_annotations.json'), .002, .002, .8)
        for sample in SAMPLES:
            with self.subTest(sample=sample['name']):
                char = self.make_char(sample['name'])
                char.task.find_one = lambda name, **kwargs: max(
                    features.find_one_feature(char.task.frame, name, **kwargs),
                    key=lambda box: box.confidence, default=None)
                char.task.in_team = lambda: BaseWWTask.in_team(char.task)
                self.assertTrue(char.task.in_team()[0])
                self.assertEqual(char.recognize_guaxiang('before_heavy'), sample['expected'])
                char.logger.info.assert_not_called()
                char.task.screenshot.assert_not_called()
                char.task.draw_boxes.assert_not_called()

    def test_wait_loop_retries_and_emits_one_summary(self):
        char = self.make_char()
        results = [[], ['蓝'], None, ['黄', '蓝'], ['蓝'] * 3, ['蓝'] * 5, ['蓝'] * 4]
        char.recognize_guaxiang = Mock(side_effect=results)
        self.assertTrue(char._normal_attack_until_four_guaxiang())
        self.assertEqual(char.normal_attack.call_count, 2)
        self.assertEqual(char.sleep.call_count, 6)
        self.assertAlmostEqual(char.clock[0], .6)
        self.assertEqual(char.task.next_frame.call_count, 7)
        self.assertEqual(char.task.check_combat.call_count, 7)
        char.logger.info.assert_called_once()
        message = char.logger.info.call_args.args[0]
        for field in ('count=4', 'sequence=蓝,蓝,蓝,蓝', 'attempts=7', 'elapsed=', 'action=continue_to_heavy'):
            self.assertIn(field, message)
        self.assertFalse(char._waiting_for_guaxiang)

    def test_capture_failure_does_not_accept_stale_four_gua(self):
        char = self.make_char()
        char.task.next_frame.side_effect = [None, char.task.frame]
        char.recognize_guaxiang = Mock(return_value=['蓝'] * 4)
        self.assertTrue(char._normal_attack_until_four_guaxiang())
        char.normal_attack.assert_called_once_with()
        char.recognize_guaxiang.assert_called_once_with('before_heavy')

    def test_timeout_and_attempt_limit_emit_abort_summary(self):
        for reason in ('timeout', 'max_attempts'):
            with self.subTest(reason=reason):
                char = self.make_char('blue1')
                clock = [0.0]
                if reason == 'timeout':
                    char.sleep.side_effect = lambda duration: clock.__setitem__(0, clock[0] + 1.0)
                else:
                    char.GUAXIANG_MAX_ATTEMPTS = 2
                with patch('src.char.Douling.time.monotonic', side_effect=lambda: clock[0]):
                    self.assertFalse(char._normal_attack_until_four_guaxiang())
                char.logger.info.assert_not_called()
                char.logger.warning.assert_called_once()
                message = char.logger.warning.call_args.args[0]
                for field in ('action=abort', f'reason={reason}', 'count=1', 'attempts=', 'elapsed='):
                    self.assertIn(field, message)
                self.assertFalse(char._waiting_for_guaxiang)

    def test_exception_warning_is_limited_to_once_per_wait(self):
        char = self.make_char()
        char.GUAXIANG_MAX_ATTEMPTS = 3
        char.task.in_team.side_effect = RuntimeError('capture unavailable')
        for _ in range(2):
            char.logger.reset_mock()
            self.assertFalse(char._normal_attack_until_four_guaxiang())
            messages = [call.args[0] for call in char.logger.warning.call_args_list]
            self.assertEqual(sum('error=capture unavailable' in message for message in messages), 1)
            self.assertEqual(sum('action=abort' in message for message in messages), 1)
        char.logger.reset_mock()
        self.assertIsNone(char.recognize_guaxiang('entry'))
        char.logger.warning.assert_called_once()

    def test_task_stop_and_combat_end_interrupt_wait(self):
        from ok.task.exceptions import TaskDisabledException
        from src.task.BaseCombatTask import NotInCombatException
        for error in (TaskDisabledException(), NotInCombatException('combat ended')):
            with self.subTest(error=type(error).__name__):
                char = self.make_char()
                char.task.check_combat.side_effect = error
                char.recognize_guaxiang = Mock()
                with self.assertRaises(type(error)):
                    char._normal_attack_until_four_guaxiang()
                char.recognize_guaxiang.assert_not_called()
                char.normal_attack.assert_not_called()
                self.assertFalse(char._waiting_for_guaxiang)

    def test_second_segment_only_releases_heavy_on_success(self):
        for success in (False, True):
            char = self.make_char()
            events = []
            char.task.jump = lambda **kwargs: events.append('jump')
            char.flying = Mock(return_value=False)
            char.wait_down = Mock()
            char._normal_attack_until_four_guaxiang = lambda: events.append('gate') or success
            char._heavy_attack_hold = lambda duration: events.append(('heavy', duration))
            char.click_echo = lambda **kwargs: events.append('echo')
            char.click_liberation = lambda: events.append('liberation')
            char.switch_next_char = lambda: events.append('switch')
            char._do_segment2()
            expected = ['jump', 'gate']
            if success:
                expected += [('heavy', 2.5), 'echo', 'liberation']
            self.assertEqual(events, expected + ['switch'])
            self.assertEqual(char._segment, 1)


if __name__ == '__main__':
    unittest.main()
