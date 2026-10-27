import unittest
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch
from pathlib import Path

import cv2
import numpy as np
from ok import Box
from ok.feature.FeatureSet import FeatureSet

from src.char.BaseChar import CharType
from src.char.Roccia import Roccia


class TestRocciaCombat(unittest.TestCase):
    def test_air_charge_recognition_on_independent_capture_and_ground_negative(self):
        root = Path(__file__).resolve().parents[1]
        for positive in (True, False):
            crop = cv2.imread(str(root / 'tests/images' / f'roccia_air_{"positive" if positive else "negative"}.png'))
            frame = np.zeros((2160, 3840, 3), dtype=np.uint8)
            frame[1930:2040, 1580:2190] = crop
            for scale in (1, .5):
                with self.subTest(positive=positive, scale=scale):
                    image = cv2.resize(frame, (0, 0), fx=scale, fy=scale)
                    features = FeatureSet(False, None, .002, .002, template_folder=str(root / 'assets/templates'))
                    matches = features.find_feature(image, 'roccia_air_forte', threshold=.7,
                                                   box=Box(int(1580*scale), int(1930*scale), int(610*scale), int(110*scale)))
                    self.assertEqual(bool(matches), positive)

    def make_char(self, c6=False):
        task = Mock()
        task.char_config = {'Roccia C6': c6}
        return Roccia(task, 0, char_type=CharType.SUB_DPS)

    def test_real_faces_distinguish_spare_charge_from_last_charge(self):
        root = Path(__file__).resolve().parents[1]
        fixtures = root / 'tests/images/roccia_air_animation'
        sequences = json.loads((fixtures / 'sequences.json').read_text(encoding='utf-8'))['sequences']
        for sequence in sequences:
            strip = cv2.imread(str(fixtures / sequence['file']))
            for scale in (1, .5):
                features = FeatureSet(False, None, .002, .002, template_folder=str(root / 'assets/templates'))
                char = self.make_char(True)
                box = Box(int(1580*scale), int(1930*scale), int(610*scale), int(110*scale))
                char.task.box_of_screen_scaled.return_value = box
                def find_one(name, box, threshold):
                    found = features.find_feature(char.task.frame, name, box=box, threshold=threshold)
                    return found[0] if found else None
                char.task.find_one.side_effect = find_one
                for index, count in [(0, 2), (len(sequence['samples'])-2, 1), (len(sequence['samples'])-1, 0)]:
                    with self.subTest(trial=sequence['trial'], scale=scale, count=count):
                        frame = np.zeros((2160, 3840, 3), dtype=np.uint8)
                        frame[1930:2040, 1580:2190] = strip[index*110:(index+1)*110]
                        char.task.frame = cv2.resize(frame, (0, 0), fx=scale, fy=scale)
                        self.assertEqual(char.air_forte_ready(), bool(count))
                        self.assertEqual(char._air_forte_charges, count)

    def test_spare_charge_bridges_only_one_unconfirmed_hold(self):
        char = self.make_char(True)
        char.need_fast_perform = Mock(return_value=False)
        char.is_mouse_forte_full = Mock(return_value=True)
        clock = SimpleNamespace(now=0, held=False)
        holds = []
        def air():
            char._air_forte_charges = 2 if clock.now < .5 else 0
            return bool(char._air_forte_charges)
        def sleep(seconds):
            if clock.held:
                holds.append(seconds)
            clock.now += seconds
        char.air_forte_ready = air
        char.task.next_frame.side_effect = lambda: setattr(clock, 'now', clock.now + .05)
        char.task.mouse_down.side_effect = lambda: setattr(clock, 'held', True)
        char.task.mouse_up.side_effect = lambda: setattr(clock, 'held', False)
        char.sleep = sleep
        with patch('src.char.Roccia.time.monotonic', side_effect=lambda: clock.now):
            self.assertTrue(char.plunge())
        self.assertEqual(holds[:2], [.4, .4])
        self.assertTrue(all(duration == 1.6 for duration in holds[2:]), holds)
        self.assertFalse(clock.held)

    def test_c6_configuration_changes_effective_role(self):
        self.assertEqual(self.make_char().char_type, CharType.SUB_DPS)
        self.assertEqual(self.make_char(True).char_type, CharType.MAIN_DPS)

    def test_air_charges_work_without_generic_mouse_hint(self):
        char = self.make_char(True)
        char.need_fast_perform = Mock(return_value=False)
        char.is_mouse_forte_full = Mock(return_value=False)
        char.air_forte_ready = Mock(side_effect=lambda: clock.now < .5)
        clock = SimpleNamespace(now=0)
        char.sleep = lambda seconds: setattr(clock, 'now', clock.now + seconds)
        char.task.next_frame.side_effect = lambda: setattr(clock, 'now', clock.now + .05)
        with patch('src.char.Roccia.time.monotonic', side_effect=lambda: clock.now):
            self.assertTrue(char.plunge())
        char.task.mouse_down.assert_called_once()
        char.task.send_key_up.assert_called_once_with('w')

    def test_real_animation_sequences_keep_aerial_timing_and_exit_after_depletion(self):
        root = Path(__file__).resolve().parents[1]
        fixtures = root / 'tests/images/roccia_air_animation'
        sequences = json.loads((fixtures / 'sequences.json').read_text(encoding='utf-8'))['sequences']
        for sequence in sequences:
            for scale in (1, .5):
                with self.subTest(trial=sequence['trial'], scale=scale):
                    strip = cv2.imread(str(fixtures / sequence['file']))
                    crops = [strip[i*110:(i+1)*110] for i in range(len(sequence['samples']))]
                    features = FeatureSet(False, None, .002, .002, template_folder=str(root / 'assets/templates'))
                    char = self.make_char(True)
                    char.need_fast_perform = Mock(return_value=False)
                    clock = SimpleNamespace(now=0, index=0, held=False)
                    # The prompt can persist during the flash, but depleted
                    # charges with no new ground resource are no longer ready.
                    char.is_mouse_forte_full = Mock(side_effect=lambda: clock.index != len(crops)-1)
                    holds, observed, sampled_indices = [], [], []
                    def set_frame(index):
                        frame = np.zeros((2160, 3840, 3), dtype=np.uint8)
                        frame[1930:2040, 1580:2190] = crops[index]
                        char.task.frame = cv2.resize(frame, (0, 0), fx=scale, fy=scale)
                    # Check every captured phase, then replay by capture timing:
                    # a held input can span several video frames.
                    for index, sample in enumerate(sequence['samples']):
                        set_frame(index)
                        matches = features.find_feature(char.task.frame, 'roccia_air_forte', threshold=.7,
                                                        box=Box(int(1580*scale), int(1930*scale), int(610*scale), int(110*scale)))
                        if scale == 1:
                            self.assertEqual(bool(matches), sample['visible'])
                    def next_frame():
                        clock.now += .05
                        clock.index = max(i for i, sample in enumerate(sequence['samples']) if sample['offset'] <= clock.now)
                        sampled_indices.append(clock.index)
                        set_frame(clock.index)
                    def find_one(name, box, threshold):
                        result = features.find_feature(char.task.frame, name, box=box, threshold=threshold)
                        return result[0] if result else None
                    def sleep(seconds):
                        if clock.held and seconds > .2:
                            holds.append(seconds)
                        clock.now += seconds
                    char.task.next_frame.side_effect = next_frame
                    char.task.find_one.side_effect = find_one
                    original_air = char.air_forte_ready
                    def air():
                        result = original_air()
                        observed.append(result)
                        return result
                    char.air_forte_ready = air
                    char.task.box_of_screen_scaled.return_value = Box(int(1580*scale), int(1930*scale), int(610*scale), int(110*scale))
                    char.task.mouse_down.side_effect = lambda: setattr(clock, 'held', True)
                    char.task.mouse_up.side_effect = lambda: setattr(clock, 'held', False)
                    char.sleep = sleep
                    with patch('src.char.Roccia.time.monotonic', side_effect=lambda: clock.now):
                        self.assertTrue(char.plunge())
                    first_miss = observed.index(False)
                    self.assertTrue(any(observed[first_miss+1:]), 'Confirm the face again after the flash')
                    self.assertEqual(sampled_indices[-1], len(crops)-1, 'Reach depletion before exiting')
                    self.assertFalse(observed[-1])
                    self.assertGreaterEqual(len(holds), 2, 'The remaining charge must be reached after the flash')
                    self.assertTrue(all(duration == .4 for duration in holds), holds)
                    self.assertLess(clock.now, 5, 'Depleted charges must terminate despite the generic hint')
                    self.assertFalse(clock.held)
                    char.task.send_key_up.assert_called_once_with('w')

    def test_last_charge_allows_prompt_ground_reentry(self):
        char = self.make_char(True)
        char.need_fast_perform = Mock(return_value=False)
        clock = SimpleNamespace(now=0, held=False)
        holds = []
        char.task.next_frame.side_effect = lambda: setattr(clock, 'now', clock.now + .05)
        char.task.mouse_down.side_effect = lambda: setattr(clock, 'held', True)
        char.task.mouse_up.side_effect = lambda: setattr(clock, 'held', False)
        char.air_forte_ready = Mock(side_effect=lambda: clock.now < .5 or 2.1 < clock.now < 2.6)
        char.is_mouse_forte_full = Mock(side_effect=lambda: clock.now < 2.1)
        def sleep(seconds):
            if clock.held:
                holds.append((clock.now, seconds))
            clock.now += seconds
        char.sleep = sleep
        with patch('src.char.Roccia.time.monotonic', side_effect=lambda: clock.now):
            self.assertTrue(char.plunge())
        self.assertEqual([duration for _, duration in holds], [.4, 1.6, .4])
        self.assertLess(holds[1][0], 1, 'Do not block ground re-entry after the last charge')
        self.assertFalse(clock.held)

    def test_air_confirmation_does_not_leak_into_next_plunge(self):
        char = self.make_char(True)
        char.need_fast_perform = Mock(return_value=False)
        char.is_mouse_forte_full = Mock(return_value=False)
        clock = SimpleNamespace(now=0)
        char.task.next_frame.side_effect = lambda: setattr(clock, 'now', clock.now + .1)
        char.sleep = lambda seconds: setattr(clock, 'now', clock.now + seconds)
        char.air_forte_ready = Mock(side_effect=lambda: clock.now < .5)
        with patch('src.char.Roccia.time.monotonic', side_effect=lambda: clock.now):
            self.assertTrue(char.plunge())
            char.task.mouse_down.reset_mock()
            self.assertFalse(char.plunge())
            char.task.mouse_down.assert_not_called()

    def test_interrupted_heavy_attack_releases_mouse_and_movement(self):
        char = self.make_char(True)
        char.need_fast_perform = Mock(return_value=False)
        char.air_forte_ready = Mock(return_value=True)
        char.sleep = Mock(side_effect=RuntimeError('combat interrupted'))
        with self.assertRaisesRegex(RuntimeError, 'interrupted'):
            char.plunge()
        char.task.mouse_up.assert_called()
        char.task.send_key_up.assert_called_once_with('w')

    def test_ground_entry_uses_full_wind_up_and_is_not_mistaken_for_air(self):
        char = self.make_char(True)
        char.need_fast_perform = Mock(return_value=False)
        char.air_forte_ready = Mock(return_value=False)
        char.is_mouse_forte_full = Mock(return_value=True)
        char.sleep = Mock()
        with patch('src.char.Roccia.time.monotonic', side_effect=[0, .1, .1, 9, 9.1]):
            self.assertFalse(char.plunge())
        self.assertEqual(char.sleep.call_args_list[0].args, (1.6,))
