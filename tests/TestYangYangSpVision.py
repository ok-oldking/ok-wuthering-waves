import unittest
from pathlib import Path

import cv2
import numpy as np

from ok.feature.FeatureSet import FeatureSet
from src.char.YangYangSpVision import YangYangSpVision
from src.task.process_feature import process_feature


ROOT = Path(__file__).resolve().parents[1]


def fixture(index, width=3840, height=2159):
    crop = cv2.imread(str(ROOT / f'tests/images/yangyang_sp/hud_{index:02d}.png'))
    frame = np.zeros((2159, 3840, 3), dtype=np.uint8)
    frame[1820:2060, 2770:3740] = crop
    return cv2.resize(frame, (width, height)) if (width, height) != (3840, 2159) else frame


def feature_matcher():
    features = FeatureSet(False, str(ROOT / 'assets/coco_annotations.json'), 0.002, 0.002,
                          feature_processor=process_feature)

    def find_one(label, frame, **kwargs):
        boxes = features.find_one_feature(frame, label, limit=1, **kwargs)
        return boxes[0] if boxes else None

    return find_one


class TestYangYangSpVision(unittest.TestCase):
    EXPECTED = [
        ('sword', False, '', False),
        ('feather', False, '', False),
        ('sword', False, 'crescent', False),
        ('feather', False, 'feather', False),
        ('azure', True, '', False),
        ('feather', True, '', False),
        ('air', False, '', False),
        ('followup', False, '', False),
        ('feather', True, 'feather', True),
        ('feather', True, 'feather', True),
    ]

    def test_screenshots_at_multiple_resolutions(self):
        for width, height in [(3840, 2159), (3840, 2160), (2560, 1440), (1920, 1080), (1600, 900)]:
            matcher = feature_matcher()
            for index, expected in enumerate(self.EXPECTED):
                with self.subTest(index=index, resolution=(width, height)):
                    state = YangYangSpVision().observe(fixture(index, width, height), matcher)
                    self.assertEqual(state.signature, expected, state.scores)

    def test_blank_frame_never_requests_a_skill(self):
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        state = YangYangSpVision().observe(frame, feature_matcher())
        self.assertEqual(state.signature, ('unknown', False, '', False))

    def test_bright_flash_or_pink_overlay_is_not_a_skill(self):
        matcher = feature_matcher()
        for color in [(255, 255, 255), (200, 40, 240)]:
            frame = np.full((1080, 1920, 3), color, dtype=np.uint8)
            state = YangYangSpVision().observe(frame, matcher)
            self.assertEqual(state.signature, ('unknown', False, '', False))

    def test_other_character_huds_do_not_trigger_yangyang_skills(self):
        matcher = feature_matcher()
        for name in ['aemeath_lib.png', 'combat_has_cd.png', 'luhesi_lib_in_cd.png']:
            with self.subTest(name=name):
                frame = cv2.imread(str(ROOT / 'tests/images' / name))
                self.assertIsNotNone(frame)
                state = YangYangSpVision().observe(frame, matcher)
                self.assertFalse(state.heavy_ready or state.followup or state.enhanced_e or state.liberation_ready,
                                 state)

    def test_same_glyph_without_ring_is_not_ready(self):
        matcher = feature_matcher()
        for index in (4, 5, 8):
            frame = fixture(index)
            b, g, r = cv2.split(frame.astype(np.int16))
            pink = (r > 145) & (b > 100) & (r - g > 55) & (b - g > 25)
            frame[pink] = 0
            state = YangYangSpVision().observe(frame, matcher)
            self.assertFalse(state.heavy_ready or state.enhanced_e or state.liberation_ready, state)


if __name__ == '__main__':
    unittest.main()
