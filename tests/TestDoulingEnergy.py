import hashlib
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import cv2
import numpy as np

from src.utils.douling_energy import (
    SHAOYANG_REGION, SHAOYIN_REGION, _energy_regions, recognize_energy,
)


ROOT = Path(__file__).resolve().parents[1]
SAMPLES = json.loads((ROOT / 'tests/images/douling_energy/manifest.json').read_text(encoding='utf-8'))


class TestDoulingEnergy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frames = {
            sample['name']: cv2.imdecode(np.fromfile(ROOT / sample['path'], dtype=np.uint8), cv2.IMREAD_COLOR)
            for sample in SAMPLES
        }

    def test_four_original_states_and_unchanged_frames(self):
        self.assertEqual({sample['expected'] for sample in SAMPLES}, {'none', 'shaoyang', 'shaoyin', 'both'})
        for sample in SAMPLES:
            with self.subTest(sample=sample['name']):
                path = ROOT / sample['path']
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), sample['sha256'])
                frame = self.frames[sample['name']]
                self.assertEqual(frame.shape, (1080, 1920, 3))
                before = frame.copy()
                for _ in range(3):
                    result = recognize_energy(frame, hud_visible=True)
                    self.assertEqual(result.state, sample['expected'], result)
                    self.assertEqual(result.reason, 'ok')
                np.testing.assert_array_equal(frame, before)

    def test_readonly_frame(self):
        frame = self.frames['shaoyin_and_shaoyang'].copy()
        frame.setflags(write=False)
        self.assertEqual(recognize_energy(frame, hud_visible=True).state, 'both')

    def test_hidden_hud_is_not_empty_energy(self):
        for name, frame in self.frames.items():
            with self.subTest(sample=name):
                result = recognize_energy(frame, hud_visible=False)
                self.assertIsNone(result.state)
                self.assertEqual(result.reason, 'hud_hidden')

    def test_invalid_frames(self):
        for frame in (None, [], np.empty((0, 0, 3), np.uint8), np.empty((0, 1920, 3), np.uint8),
                      np.zeros((1080, 1920), np.uint8), np.zeros((1080, 1920, 4), np.uint8),
                      np.zeros((1080, 1920, 3), np.float32), np.zeros((10, 10, 3), np.uint8)):
            with self.subTest(shape=getattr(frame, 'shape', None)):
                result = recognize_energy(frame, hud_visible=True)
                self.assertIsNone(result.state)
                self.assertEqual(result.reason, 'invalid_frame')

    def test_blank_or_obscured_bar_is_not_empty_energy(self):
        result = recognize_energy(np.zeros((1080, 1920, 3), np.uint8), hud_visible=True)
        self.assertIsNone(result.state)
        self.assertEqual(result.reason, 'bar_not_visible')
        for region in (SHAOYANG_REGION, SHAOYIN_REGION):
            with self.subTest(region=region):
                frame = self.frames['shaoyin_and_shaoyang'].copy()
                x, y, w, h = region
                frame[y:y + h, x:x + w] = 0
                result = recognize_energy(frame, hud_visible=True)
                self.assertIsNone(result.state)
                self.assertEqual(result.reason, 'bar_not_visible')

    def test_original_sampling_regions_do_not_contain_red_annotations(self):
        self.assertEqual(_energy_regions(1920, 1080), (SHAOYANG_REGION, SHAOYIN_REGION))
        for name, frame in self.frames.items():
            for x, y, w, h in _energy_regions(frame.shape[1], frame.shape[0]):
                with self.subTest(sample=name, region=(x, y, w, h)):
                    roi = frame[y:y + h, x:x + w]
                    red_annotation = (roi[:, :, 2] > 200) & (roi[:, :, 1] < 90) & (roi[:, :, 0] < 90)
                    self.assertFalse(red_annotation.any())

    def test_outside_regions_including_annotations_cannot_affect_result(self):
        for sample in SAMPLES:
            frame = self.frames[sample['name']]
            for color in ((0, 0, 0), (0, 0, 255), (255, 255, 255)):
                with self.subTest(sample=sample['name'], outside_color=color):
                    altered = np.empty_like(frame)
                    altered[:] = color
                    for x, y, w, h in _energy_regions(frame.shape[1], frame.shape[0]):
                        altered[y:y + h, x:x + w] = frame[y:y + h, x:x + w]
                    self.assertEqual(recognize_energy(altered, hud_visible=True).state, sample['expected'])

    def test_localized_colored_glare_is_not_energy(self):
        frame = self.frames['none_shaoyin_shaoyang'].copy()
        for region, color in ((SHAOYANG_REGION, (40, 220, 255)), (SHAOYIN_REGION, (255, 120, 40))):
            x, y, _, h = region
            frame[y:y + h, x:x + 12] = color
        self.assertEqual(recognize_energy(frame, hud_visible=True).state, 'none')

    def test_scaled_screenshots(self):
        # 人工缩放验证坐标与采样，不代替对应分辨率的实机截图。
        for size in ((1280, 720), (1920, 1080), (2560, 1440)):
            for sample in SAMPLES:
                with self.subTest(size=size, sample=sample['name']):
                    frame = cv2.resize(self.frames[sample['name']], size)
                    self.assertEqual(recognize_energy(frame, hud_visible=True).state, sample['expected'])

    def test_wide_and_tall_frames_anchor_to_center_and_bottom(self):
        for sample in SAMPLES:
            source = cv2.resize(self.frames[sample['name']], (1600, 900))
            for width, height, offset_x, offset_y in ((2100, 900, 250, 0), (1600, 1100, 0, 200)):
                with self.subTest(size=(width, height), sample=sample['name']):
                    frame = np.zeros((height, width, 3), np.uint8)
                    frame[offset_y:offset_y + 900, offset_x:offset_x + 1600] = source
                    self.assertEqual(recognize_energy(frame, hud_visible=True).state, sample['expected'])


class TestDoulingEnergyIntegration(unittest.TestCase):
    def setUp(self):
        from src.char.Douling import Douling
        self.char = Douling.__new__(Douling)
        self.char.index = 1
        self.char._segment = 1
        self.char._waiting_for_guaxiang = False
        self.char._guaxiang_error_logged = False
        self.char._energy_error_logged = False
        self.char._energy_state = None
        self.char._post_heavy_observer = None
        self.frames = {
            sample['expected']: cv2.imdecode(np.fromfile(ROOT / sample['path'], dtype=np.uint8), cv2.IMREAD_COLOR)
            for sample in SAMPLES
        }
        self.char.task = SimpleNamespace(
            frame=self.frames['both'], in_team=Mock(return_value=(True, 1, 3)),
            next_frame=Mock(side_effect=lambda: self.char.task.frame), check_combat=Mock(),
            screenshot=Mock(), draw_boxes=Mock(),
            _in_combat=True,
        )
        self.next_frame = self.char.task.next_frame
        self.char.logger = Mock()
        self.char.normal_attack = Mock()
        self.clock = [0.0]
        self.holding = False
        self.mouse_events = []

        def mouse_down():
            self.holding = True
            self.mouse_events.append(('down', self.clock[0]))

        def mouse_up():
            self.holding = False
            self.mouse_events.append(('up', self.clock[0]))

        self.char.task.mouse_down = Mock(side_effect=mouse_down)
        self.char.task.mouse_up = Mock(side_effect=mouse_up)
        self.char.flying = Mock(return_value=False)
        self.char.wait_down = Mock()
        self.char.sleep = Mock(side_effect=lambda duration: self.clock.__setitem__(0, self.clock[0] + duration))
        timer = patch('src.char.Douling.time.monotonic', side_effect=lambda: self.clock[0])
        timer.start()
        self.addCleanup(timer.stop)
        gua = patch('src.char.Douling.detect_guaxiang', return_value=SimpleNamespace(sequence=[], reason='ok'))
        self.gua = gua.start()
        self.addCleanup(gua.stop)

    def followup_frame(self, at):
        self.clock[0] = at
        return self.char.task.next_frame()

    def test_entry_energy_precedes_both_segments_on_all_four_states(self):
        for segment in (1, 2):
            for state, frame in self.frames.items():
                with self.subTest(segment=segment, state=state):
                    self.char._segment = segment
                    self.char.task.frame = frame
                    self.char.task.in_team.reset_mock()
                    self.char.logger.reset_mock()
                    observed_states = []
                    branch = Mock(side_effect=lambda: observed_states.append(self.char._energy_state))
                    setattr(self.char, f'_do_segment{segment}', branch)
                    self.char.do_perform()
                    self.assertEqual(self.char._energy_state, state)
                    branch.assert_called_once_with()
                    self.assertEqual(observed_states, [state])
                    self.char.task.in_team.assert_called_once_with()
                    self.char.task.next_frame.assert_not_called()
                    self.char.logger.info.assert_any_call(f'[DoulingEnergy] point=entry state={state}')
                    self.assertEqual(self.char.logger.info.call_count, 2)
                    self.char.task.screenshot.assert_not_called()
                    self.char.task.draw_boxes.assert_not_called()

    def test_energy_and_guaxiang_share_one_copied_frame(self):
        with patch('src.char.Douling.detect_energy', wraps=recognize_energy) as energy:
            self.char.recognize_guaxiang('entry')
        energy.assert_called_once()
        self.gua.assert_called_once()
        energy_frame = energy.call_args.args[0]
        self.assertIs(energy_frame, self.gua.call_args.args[0])
        self.assertIsNot(energy_frame, self.char.task.frame)
        np.testing.assert_array_equal(energy_frame, self.char.task.frame)
        self.assertTrue(energy.call_args.kwargs['hud_visible'])

    def test_each_valid_before_heavy_poll_updates_energy_without_extra_logs(self):
        states = iter(('none', 'shaoyin', 'both'))

        def refresh():
            self.char.task.frame = self.frames[next(states)]
            return self.char.task.frame

        self.char.task.next_frame.side_effect = refresh
        self.gua.side_effect = [SimpleNamespace(sequence=sequence, reason='ok')
                               for sequence in ([], ['蓝'], ['黄', '蓝', '蓝', '蓝'])]
        with patch('src.char.Douling.detect_energy', wraps=recognize_energy) as energy:
            self.assertTrue(self.char._normal_attack_until_four_guaxiang())
        self.assertEqual(energy.call_count, 3)
        self.assertEqual(self.char.task.in_team.call_count, 3)
        self.assertEqual(self.char.task.next_frame.call_count, 3)
        for energy_call, gua_call in zip(energy.call_args_list, self.gua.call_args_list):
            self.assertIs(energy_call.args[0], gua_call.args[0])
        self.assertEqual(self.char._energy_state, 'both')
        self.char.logger.info.assert_called_once()
        self.assertIn('energy=both', self.char.logger.info.call_args.args[0])
        self.char.task.draw_boxes.assert_not_called()
        self.char.task.screenshot.assert_not_called()

    def test_empty_refresh_clears_energy_and_does_not_use_old_frame(self):
        self.char._energy_state = 'both'
        self.char.task.next_frame.return_value = None
        self.char.task.next_frame.side_effect = None
        self.char.GUAXIANG_MAX_ATTEMPTS = 1
        with patch('src.char.Douling.detect_energy') as energy:
            self.assertFalse(self.char._normal_attack_until_four_guaxiang())
        energy.assert_not_called()
        self.gua.assert_not_called()
        self.assertIsNone(self.char._energy_state)
        self.assertIn('energy=uncertain', self.char.logger.warning.call_args.args[0])

    def test_hidden_or_other_character_hud_does_not_keep_energy(self):
        for team in ((False, -1, 1), (True, 0, 3)):
            with self.subTest(team=team):
                self.char._energy_state = 'both'
                self.char.task.in_team.return_value = team
                self.char.recognize_guaxiang('entry')
                self.assertIsNone(self.char._energy_state)
                self.char.logger.info.assert_any_call(
                    '[DoulingEnergy] point=entry status=uncertain reason=hud_hidden')

    def test_four_guaxiang_gate_does_not_require_energy(self):
        self.gua.return_value = SimpleNamespace(sequence=['蓝'] * 4, reason='ok')
        for state, frame in list(self.frames.items()) + [(None, np.zeros_like(self.frames['both']))]:
            with self.subTest(state=state):
                self.char.task.frame = frame
                self.assertTrue(self.char._normal_attack_until_four_guaxiang())
                self.assertEqual(self.char._energy_state, state)
        self.char.normal_attack.assert_not_called()

    def test_energy_exceptions_are_limited_and_do_not_stop_guaxiang(self):
        self.char.GUAXIANG_MAX_ATTEMPTS = 3
        with patch('src.char.Douling.detect_energy', side_effect=RuntimeError('energy unavailable')):
            for _ in range(2):
                self.char.logger.reset_mock()
                self.assertFalse(self.char._normal_attack_until_four_guaxiang())
                messages = [call.args[0] for call in self.char.logger.warning.call_args_list]
                self.assertEqual(sum('[DoulingEnergy]' in message for message in messages), 1)
                self.assertEqual(sum('action=abort' in message for message in messages), 1)
                self.assertIsNone(self.char._energy_state)
            self.gua.return_value = SimpleNamespace(sequence=['蓝'] * 4, reason='ok')
            self.assertTrue(self.char._normal_attack_until_four_guaxiang())
        self.assertEqual(self.gua.call_count, 7)

    def test_guaxiang_failure_still_records_energy_from_same_frame(self):
        self.gua.side_effect = RuntimeError('gua unavailable')
        self.assertIsNone(self.char.recognize_guaxiang('entry'))
        self.assertEqual(self.char._energy_state, 'both')
        self.char.logger.info.assert_called_once_with('[DoulingEnergy] point=entry state=both')

    def test_hud_check_failure_clears_energy(self):
        self.char._energy_state = 'both'
        self.char.task.in_team.side_effect = RuntimeError('capture unavailable')
        with patch('src.char.Douling.detect_energy') as energy:
            self.assertIsNone(self.char.recognize_guaxiang('entry'))
        energy.assert_not_called()
        self.assertIsNone(self.char._energy_state)

    def test_slow_energy_recognition_respects_existing_gate_deadline(self):
        def slow_energy(frame, *, hud_visible):
            self.clock[0] += 3.0
            return recognize_energy(frame, hud_visible=hud_visible)

        self.gua.return_value = SimpleNamespace(sequence=['蓝'] * 4, reason='ok')
        with patch('src.char.Douling.detect_energy', side_effect=slow_energy):
            self.assertFalse(self.char._normal_attack_until_four_guaxiang())
        self.char.normal_attack.assert_not_called()
        self.char.sleep.assert_not_called()
        self.assertIn('reason=timeout', self.char.logger.warning.call_args.args[0])

    def test_continuous_heavy_timing_fresh_frames_and_shared_results(self):
        states = iter(('none', 'shaoyang', 'shaoyin', 'both', 'none') * 3)
        capture_times, held_at_capture = [], []

        def refresh():
            capture_times.append(self.clock[0])
            held_at_capture.append(self.holding)
            self.char.task.frame = self.frames[next(states)]
            return self.char.task.frame

        self.char.task.next_frame.side_effect = refresh
        self.gua.side_effect = [SimpleNamespace(sequence=sequence, reason='ok')
                               for sequence in (['黄'], ['蓝', '蓝'], [], ['蓝'] * 4, None) * 3]
        with patch('src.char.Douling.detect_energy', wraps=recognize_energy) as energy:
            self.char._heavy_attack_hold(2.5)
            self.assertAlmostEqual(self.clock[0], 2.5)
            self.followup_frame(2.600001)
            self.followup_frame(2.800002)
        np.testing.assert_allclose(capture_times, np.arange(15) * .2, atol=3e-6)
        self.assertEqual(held_at_capture, [True] * 13 + [False] * 2)
        self.assertEqual(self.mouse_events[0], ('down', 0.0))
        self.assertEqual(self.mouse_events[1][0], 'up')
        self.assertAlmostEqual(self.mouse_events[1][1], 2.5)
        self.assertAlmostEqual(self.clock[0], 2.800002)
        self.char.task.mouse_down.assert_called_once()
        self.char.task.mouse_up.assert_called_once()
        self.assertEqual(energy.call_count, 15)
        for energy_call, gua_call in zip(energy.call_args_list, self.gua.call_args_list):
            self.assertIs(energy_call.args[0], gua_call.args[0])
        messages = [call.args[0] for call in self.char.logger.info.call_args_list]
        self.assertEqual(len(messages), 15)
        expected = (('none', 1, '黄'), ('shaoyang', 2, '蓝,蓝'), ('shaoyin', 0, '[]'),
                    ('both', 4, '蓝,蓝,蓝,蓝'), ('none', 'uncertain', 'uncertain')) * 3
        for index, (state, count, sequence) in enumerate(expected):
            point = 'during_heavy' if index < 13 else 'after_heavy'
            self.assertIn(f'point={point} attempt=1 sample={index + 1} ', messages[index])
            self.assertIn(f'count={count} sequence={sequence} energy={state}', messages[index])
        self.assertIn('elapsed=0.100s', messages[13])
        self.assertIn('elapsed=0.300s', messages[14])
        self.char.normal_attack.assert_not_called()
        self.char.task.screenshot.assert_not_called()
        self.char.task.draw_boxes.assert_not_called()
        self.assertFalse(self.holding)

    def test_continuous_heavy_empty_frames_do_not_reuse_old_results(self):
        frames = iter((self.frames['both'], None, self.frames['none'], None, self.frames['shaoyin']) * 3)

        def refresh():
            frame = next(frames)
            if frame is not None:
                self.char.task.frame = frame
            return frame

        self.char.task.next_frame.side_effect = refresh
        with patch('src.char.Douling.detect_energy', wraps=recognize_energy) as energy:
            self.char._heavy_attack_hold(2.5)
            state_after_hold = self.char._energy_state
            self.followup_frame(2.600001)
            self.followup_frame(2.800002)
        self.assertEqual(self.next_frame.call_count, 15)
        self.assertEqual(energy.call_count, 9)
        self.assertEqual(self.gua.call_count, 9)
        messages = [call.args[0] for call in self.char.logger.info.call_args_list]
        self.assertEqual(len(messages), 15)
        for index in (1, 3, 6, 8, 11, 13):
            self.assertIn('count=uncertain sequence=uncertain energy=uncertain reason=capture_failed', messages[index])
        self.assertEqual(self.char._energy_state, state_after_hold)
        self.assertFalse(self.holding)

    def test_continuous_heavy_recognition_errors_do_not_block_release(self):
        self.gua.side_effect = RuntimeError('gua unavailable')
        with patch('src.char.Douling.detect_energy', side_effect=RuntimeError('energy unavailable')):
            self.char._heavy_attack_hold(.4)
            self.assertAlmostEqual(self.clock[0], .4)
            self.followup_frame(.4)
            self.followup_frame(.61)
        self.assertEqual(self.next_frame.call_count, 4)
        self.assertEqual(self.gua.call_count, 4)
        self.assertEqual(self.char.logger.info.call_count, 4)
        self.assertIsNone(self.char._energy_state)
        for call in self.char.logger.info.call_args_list:
            self.assertIn('count=uncertain sequence=uncertain energy=uncertain', call.args[0])
        self.assertAlmostEqual(self.mouse_events[1][1], .4)
        self.assertAlmostEqual(self.clock[0], .61)
        self.assertFalse(self.holding)

    def test_continuous_heavy_slow_capture_does_not_burst_samples(self):
        capture_times = []

        def refresh():
            capture_times.append(self.clock[0])
            self.clock[0] += .3
            return self.char.task.frame

        self.char.task.next_frame.side_effect = refresh
        self.char._heavy_attack_hold(.4)
        self.assertAlmostEqual(self.clock[0], .6)
        self.followup_frame(.6)
        self.followup_frame(.9)
        np.testing.assert_allclose(capture_times, [0, .3, .6, .9])
        self.assertAlmostEqual(self.mouse_events[1][1], .6)
        self.assertAlmostEqual(self.clock[0], 1.2)
        self.assertFalse(self.holding)

    def test_stop_during_hold_propagates_and_releases_mouse(self):
        from ok.task.exceptions import TaskDisabledException
        self.char.sleep.side_effect = TaskDisabledException()
        with self.assertRaises(TaskDisabledException):
            self.char._heavy_attack_hold(.4)
        self.char.task.mouse_up.assert_called_once()
        self.assertFalse(self.holding)
        self.assertAlmostEqual(self.mouse_events[1][1], 0.0)
        self.assertIsNone(self.char._post_heavy_observer)
        self.assertIs(self.char.task.next_frame, self.next_frame)

    def test_stop_during_capture_releases_mouse(self):
        from ok.task.exceptions import TaskDisabledException
        self.char.task.next_frame.side_effect = TaskDisabledException()
        with self.assertRaises(TaskDisabledException):
            self.char._heavy_attack_hold(.4)
        self.char.task.mouse_up.assert_called_once()
        self.assertFalse(self.holding)
        self.gua.assert_not_called()

    def test_combat_end_during_hold_releases_mouse_before_recognition(self):
        from src.task.BaseCombatTask import NotInCombatException
        self.char.task.check_combat.side_effect = [None, NotInCombatException('combat ended')]
        with patch('src.char.Douling.detect_energy') as energy:
            with self.assertRaises(NotInCombatException):
                self.char._heavy_attack_hold(.4)
        self.char.task.mouse_up.assert_called_once()
        self.char.task.next_frame.assert_not_called()
        self.gua.assert_not_called()
        energy.assert_not_called()
        self.assertFalse(self.holding)

    def test_interrupted_heavy_retries_and_labels_new_attempt(self):
        self.char.flying.side_effect = lambda: self.char.task.mouse_down.call_count == 1
        self.char._heavy_attack_hold(.4)
        self.assertEqual(self.char.task.mouse_down.call_count, 2)
        self.assertEqual(self.char.task.mouse_up.call_count, 2)
        self.char.wait_down.assert_called_once()
        self.assertAlmostEqual(self.mouse_events[3][1], .41)
        self.assertAlmostEqual(self.clock[0], .41)
        self.assertFalse(self.holding)
        for call in self.char.logger.info.call_args_list:
            self.assertIn('attempt=2', call.args[0])

    def test_interrupted_heavy_is_bounded_by_three_attempts(self):
        self.char.flying.return_value = True
        self.char._heavy_attack_hold(.4)
        self.assertEqual(self.char.task.mouse_down.call_count, 3)
        self.assertEqual(self.char.task.mouse_up.call_count, 3)
        self.assertEqual(self.char.wait_down.call_count, 3)
        self.char.task.next_frame.assert_not_called()
        self.assertFalse(self.holding)

    def test_followup_actions_start_without_observation_wait(self):
        events = []
        self.char.task.jump = Mock()
        self.char._normal_attack_until_four_guaxiang = Mock(return_value=True)

        def echo(**kwargs):
            events.append(('echo', self.clock[0], self.char._post_heavy_observer is not None))
            self.followup_frame(2.650001)

        def liberation():
            events.append(('liberation', self.clock[0], self.char._post_heavy_observer is not None))
            self.followup_frame(2.850002)
            self.followup_frame(2.95)

        self.char.click_echo = echo
        self.char.click_liberation = liberation
        self.char.switch_next_char = lambda: events.append(('switch', self.clock[0], False))
        self.char._do_segment2()
        self.assertAlmostEqual(events[0][1], 2.55)
        self.assertAlmostEqual(events[1][1], 2.650001)
        self.assertTrue(events[0][2])
        self.assertTrue(events[1][2])
        self.assertEqual([event[0] for event in events], ['echo', 'liberation', 'switch'])
        messages = [call.args[0] for call in self.char.logger.info.call_args_list]
        self.assertEqual(sum('point=after_heavy' in message for message in messages), 2)
        self.assertIsNone(self.char._post_heavy_observer)
        self.assertIs(self.char.task.next_frame, self.next_frame)
        self.assertEqual(self.char._segment, 1)

    def test_observation_expires_without_catchup_or_new_capture(self):
        self.char._heavy_attack_hold(.4)
        self.next_frame.reset_mock()
        self.char.logger.info.reset_mock()
        self.followup_frame(.4)
        self.followup_frame(.45)
        self.followup_frame(.7)
        self.followup_frame(.8)
        self.followup_frame(1.0)
        self.assertEqual(self.char.task.next_frame.call_count, 5)
        self.assertEqual(self.char.logger.info.call_count, 2)
        self.assertIsNone(self.char._post_heavy_observer)
        self.assertIs(self.char.task.next_frame, self.next_frame)
        self.assertAlmostEqual(self.clock[0], 1.0)

    def test_switched_char_and_hidden_hud_do_not_report_empty_guaxiang(self):
        self.char._heavy_attack_hold(.4)
        self.char.task.in_team.return_value = (True, 0, 3)
        self.char.logger.info.reset_mock()
        from src.utils.guaxiang import recognize_guaxiang
        with patch('src.char.Douling.detect_guaxiang', wraps=recognize_guaxiang):
            self.followup_frame(.4)
        self.assertIn('count=uncertain sequence=uncertain energy=uncertain',
                      self.char.logger.info.call_args.args[0])

    def test_followup_failure_and_combat_end_cancel_observation(self):
        from ok.task.exceptions import TaskDisabledException
        self.char.task.jump = Mock()
        self.char._normal_attack_until_four_guaxiang = Mock(return_value=True)
        self.char.click_echo = Mock(side_effect=TaskDisabledException())
        self.char.click_liberation = Mock()
        with self.assertRaises(TaskDisabledException):
            self.char._do_segment2()
        self.assertIsNone(self.char._post_heavy_observer)
        self.assertIs(self.char.task.next_frame, self.next_frame)
        self.char.click_liberation.assert_not_called()
        self.char._heavy_attack_hold(.4)
        self.char.task._in_combat = False
        self.char.logger.info.reset_mock()
        self.followup_frame(self.clock[0])
        self.char.logger.info.assert_not_called()
        self.assertIsNone(self.char._post_heavy_observer)
        self.assertIs(self.char.task.next_frame, self.next_frame)

    def test_observation_only_wraps_one_task_instance_and_restores_inherited_method(self):
        from src.task.BaseCombatTask import BaseCombatTask
        task = BaseCombatTask.__new__(BaseCombatTask)
        other_task = BaseCombatTask.__new__(BaseCombatTask)
        task._in_combat = True
        task.in_team = Mock(return_value=(True, 1, 3))
        self.char.task = task
        original_method = task.next_frame.__func__
        executor = SimpleNamespace(frame=self.frames['none'],
                                   next_frame=Mock(return_value=self.frames['none']))
        with patch.object(BaseCombatTask, 'executor', executor):
            self.char._start_post_heavy_observation(1, 0, 0, 0)
            self.assertIs(other_task.next_frame.__func__, original_method)
            other_task.next_frame()
            self.char.logger.info.assert_not_called()
            self.assertIs(task.next_frame(), self.frames['none'])
            self.assertEqual(self.char.logger.info.call_count, 1)
            self.clock[0] = .4
            task.next_frame()
        self.assertIs(task.next_frame.__func__, original_method)
        self.assertNotIn('next_frame', vars(task))
        self.assertIsNone(self.char._post_heavy_observer)

    def test_observer_failure_does_not_interrupt_frame_refresh(self):
        self.char._heavy_attack_hold(.4)
        previous_energy = self.char._energy_state
        with patch.object(self.char, '_record_heavy_recognition', side_effect=RuntimeError('recognition failed')):
            self.assertIs(self.followup_frame(.4), self.char.task.frame)
        self.assertIsNone(self.char._post_heavy_observer)
        self.assertIs(self.char.task.next_frame, self.next_frame)
        self.assertEqual(self.char._energy_state, previous_energy)
        self.assertIn('observer_stopped', self.char.logger.warning.call_args.args[0])

    def test_stop_during_followup_capture_restores_original_frame_method(self):
        from ok.task.exceptions import TaskDisabledException
        self.char._heavy_attack_hold(.4)
        self.next_frame.side_effect = TaskDisabledException()
        with self.assertRaises(TaskDisabledException):
            self.followup_frame(.4)
        self.assertIsNone(self.char._post_heavy_observer)
        self.assertIs(self.char.task.next_frame, self.next_frame)
        self.char.task.mouse_up.assert_called_once()
        self.assertFalse(self.holding)


if __name__ == '__main__':
    unittest.main()
