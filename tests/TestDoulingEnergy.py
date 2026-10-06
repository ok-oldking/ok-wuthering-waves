import hashlib
import json
import unittest
from pathlib import Path

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


if __name__ == '__main__':
    unittest.main()
