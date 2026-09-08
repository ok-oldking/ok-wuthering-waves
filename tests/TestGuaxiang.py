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
TEAM = ('Carlotta', 'Douling', 'Zhezhi')
TEAM_FILE = ROOT / 'configs/custom_teams/Carlotta__Douling__Zhezhi/Douling.py'


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


@unittest.skipUnless(TEAM_FILE.is_file(), 'Local ignored custom team is not installed')
class TestGuaxiangTeamIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from ok.util.config import Config
        from src.char.CustomCharLoader import load_team_char_class
        from src.char.Douling import Douling
        with patch.object(Config, 'config_folder', str(ROOT / 'configs')):
            cls.team_class = load_team_char_class(Douling, TEAM)
        if cls.team_class is Douling:
            raise AssertionError('Expected the installed custom team class')

    def make_char(self, name='mixed4', hud=True, debug=False):
        char = self.team_class.__new__(self.team_class)
        char.task = SimpleNamespace(frame=read_sample(name), in_team=Mock(return_value=(hud, 1, 3)),
                                    debug=debug, draw_boxes=Mock(), screenshot=Mock(), check_combat=Mock())
        char.task.next_frame = Mock(side_effect=lambda: char.task.frame)
        char.logger = Mock()
        return char

    def test_actual_team_entry_and_debug_boxes(self):
        char = self.make_char(debug=True)
        self.assertEqual(char.recognize_guaxiang(), ['黄', '蓝', '蓝', '蓝'])
        char.task.in_team.assert_called_once_with()
        self.assertIn('count=4 sequence=黄,蓝,蓝,蓝', char.logger.info.call_args.args[0])
        self.assertEqual(len(char.task.draw_boxes.call_args_list[-1].args[1]), 4)

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
                self.assertTrue(char.task.in_team()[0], 'Real team HUD templates must match')
                self.assertEqual(char.recognize_guaxiang(), sample['expected'])

    def test_empty_hidden_and_error_logs(self):
        for name, hud, expected in (('empty', True, []), ('blue4', False, None)):
            with self.subTest(name=name, hud=hud):
                char = self.make_char(name, hud)
                self.assertEqual(char.recognize_guaxiang(), expected)
                self.assertIn('count=0' if hud else 'status=uncertain', char.logger.info.call_args.args[0])
                char.task.screenshot.assert_called_once()
        char = self.make_char()
        char.task.in_team.side_effect = RuntimeError('unavailable screenshot')
        self.assertIsNone(char.recognize_guaxiang())
        char.logger.warning.assert_called_once()

    def test_screenshot_uses_the_recognition_frame_and_survives_capture_reuse(self):
        char = self.make_char()
        expected_frame = char.task.frame.copy()
        detect = Mock(wraps=recognize_guaxiang)
        with patch.dict(self.team_class.recognize_guaxiang.__globals__, {'detect_guaxiang': detect}):
            self.assertEqual(char.recognize_guaxiang('before_heavy'), ['黄', '蓝', '蓝', '蓝'])
        char.task.screenshot.assert_called_once()
        screenshot_call = char.task.screenshot.call_args
        self.assertTrue(screenshot_call.args[0].startswith('guaxiang/before_heavy_'))
        self.assertIs(screenshot_call.kwargs['frame'], detect.call_args.args[0])
        self.assertIsNot(screenshot_call.kwargs['frame'], char.task.frame)
        self.assertFalse(screenshot_call.kwargs['show_box'])
        char.task.frame[:] = 0
        self.assertTrue(np.array_equal(screenshot_call.kwargs['frame'], expected_frame))
        self.assertIn(f'screenshot_name={screenshot_call.args[0]}', char.logger.info.call_args.args[0])

    def test_screenshot_failure_does_not_change_recognition_result(self):
        char = self.make_char()
        char.task.screenshot.side_effect = OSError('screenshot queue unavailable')
        self.assertEqual(char.recognize_guaxiang('entry'), ['黄', '蓝', '蓝', '蓝'])
        self.assertIn('[DoulingScreenshot]', char.logger.warning.call_args.args[0])
        self.assertIn('screenshot_name=failed', char.logger.info.call_args.args[0])

    def test_both_fixed_phases_keep_action_order_and_timings(self):
        for phase in ('start_douling', 'douling_loop'):
            for hud in (True, False):
                with self.subTest(phase=phase, hud=hud):
                    char = self.make_char(hud=hud)
                    char._rotation_phase = lambda: phase
                    events = []
                    def refresh_frame():
                        # 入场不确定不应阻止原来的前半段；跳 a 后拿到四个才放行。
                        char.task.in_team.return_value = (True, 1, 3)
                        return char.task.frame
                    char.task.next_frame.side_effect = refresh_frame
                    char.task.check_combat.side_effect = lambda: self.assertFalse(char.skip_combat_check())
                    char._wait_for_entry = lambda: events.append('entry')
                    recognize = char.recognize_guaxiang
                    def sample_once(sample_point):
                        events.append(('recognize', sample_point))
                        return recognize(sample_point)
                    char.recognize_guaxiang = sample_once
                    char._tap_normal = lambda count=1: events.append(('normal', count))
                    char._tap_resonance = lambda post_sleep: events.append(('resonance', post_sleep)) or True
                    char.sleep = lambda duration: events.append(('sleep', duration))
                    char._jump = lambda: events.append('jump')
                    char._hold_long_heavy = lambda: events.append('heavy')
                    char._tap_echo = lambda: events.append('echo')
                    char._cast_liberation = lambda: events.append('liberation') or True
                    char._switch_to_phase = lambda next_phase: events.append(('switch', next_phase))
                    char.do_perform()
                    self.assertEqual(events, ['entry', ('recognize', 'entry'), ('normal', 2), ('resonance', 0),
                                              ('sleep', .8), ('normal', 1), 'jump', ('normal', 1),
                                              ('recognize', 'before_heavy'), 'heavy', 'echo', 'liberation',
                                              ('switch', 'zhezhi_bridge')])
                    self.assertEqual(char.task.in_team.call_count, 2)
                    recognition_logs = [call.args[0] for call in char.logger.info.call_args_list
                                        if call.args[0].startswith('[DoulingRecognition]')]
                    self.assertEqual(len(recognition_logs), 2)
                    self.assertEqual(char.task.screenshot.call_count, 2)
                    self.assertFalse(char._performing_fixed_rotation)
                    self.assertFalse(char._waiting_for_guaxiang)
                    self.assertEqual(char.NORMAL_ATTACK_INTERVAL, .3)
                    self.assertEqual(char.JUMP_INTERVAL, .3)
                    self.assertEqual(char.LONG_HEAVY_DURATION, 2.5)

    def test_wait_loop_keeps_attacking_through_incomplete_and_uncertain_results(self):
        char = self.make_char()
        char._performing_fixed_rotation = True
        results = [[], ['蓝'], None, ['黄', '蓝'], ['黄', '蓝', '蓝'], ['蓝'] * 5,
                   ['黄', '蓝', '蓝', '蓝']]
        char.recognize_guaxiang = Mock(side_effect=results)
        char.normal_attack = Mock()
        char.sleep = Mock()
        char.task.check_combat.side_effect = lambda: self.assertFalse(char.skip_combat_check())
        char._normal_attack_until_four_guaxiang()
        self.assertEqual(char.normal_attack.call_count, 6)
        self.assertEqual([call.args for call in char.sleep.call_args_list], [(0.3,)] * 6)
        self.assertEqual(char.task.next_frame.call_count, 7)
        self.assertEqual(char.task.check_combat.call_count, 7)
        self.assertEqual(char.recognize_guaxiang.call_count, 7)
        self.assertIn('continue_to_heavy', char.logger.info.call_args.args[0])
        self.assertFalse(char._waiting_for_guaxiang)
        self.assertTrue(char.skip_combat_check(), 'Original fixed-axis protection resumes after the loop')

    def test_capture_failure_does_not_accept_stale_four_gua(self):
        char = self.make_char()
        char.task.next_frame.side_effect = [None, char.task.frame]
        char.recognize_guaxiang = Mock(return_value=['蓝'] * 4)
        char._tap_normal = Mock()
        char._normal_attack_until_four_guaxiang()
        char._tap_normal.assert_called_once_with()
        char.recognize_guaxiang.assert_called_once_with('before_heavy')

    def test_incomplete_gate_never_reaches_heavy_before_task_stop(self):
        from ok.task.exceptions import TaskDisabledException
        for phase in ('start_douling', 'douling_loop'):
            with self.subTest(phase=phase):
                char = self.make_char()
                char._rotation_phase = lambda: phase
                char._wait_for_entry = Mock()
                char.recognize_guaxiang = Mock(side_effect=[[], ['蓝'] * 3, None])
                char._tap_normal = Mock()
                char._tap_resonance = Mock(return_value=True)
                char.sleep = Mock()
                char._jump = Mock()
                char._hold_long_heavy = Mock()
                char._tap_echo = Mock()
                char._cast_liberation = Mock()
                char._switch_to_phase = Mock()
                char.task.next_frame.side_effect = [char.task.frame, char.task.frame, TaskDisabledException()]
                with self.assertRaises(TaskDisabledException):
                    char.do_perform()
                self.assertEqual(char._tap_normal.call_count, 5)  # 原有三次调用，加两次补卦象普攻
                char._jump.assert_called_once()
                char._tap_resonance.assert_called_once()
                char._hold_long_heavy.assert_not_called()
                char._tap_echo.assert_not_called()
                char._cast_liberation.assert_not_called()
                char._switch_to_phase.assert_not_called()
                self.assertFalse(char._waiting_for_guaxiang)
                self.assertFalse(char._performing_fixed_rotation)

    def test_combat_end_interrupts_wait_loop(self):
        from src.task.BaseCombatTask import NotInCombatException
        char = self.make_char()
        char._performing_fixed_rotation = True
        char.task.check_combat.side_effect = NotInCombatException('combat ended')
        char.recognize_guaxiang = Mock()
        char._tap_normal = Mock()
        with self.assertRaises(NotInCombatException):
            char._normal_attack_until_four_guaxiang()
        char.recognize_guaxiang.assert_not_called()
        char._tap_normal.assert_not_called()
        self.assertFalse(char._waiting_for_guaxiang)

    def test_other_phases_skip_recognition(self):
        char = self.make_char()
        char._rotation_phase = lambda: 'start_carlotta'
        char.switch_next_char = Mock()
        char.do_perform()
        char.task.in_team.assert_not_called()
        char.switch_next_char.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
