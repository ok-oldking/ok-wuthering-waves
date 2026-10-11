import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

from src.utils.guaxiang import GuaDetection, _resolve_candidates, recognize_guaxiang


SAMPLES = {
    'douling_empty': [], 'douling_gua_blue': ['蓝'], 'blue2': ['蓝'] * 2,
    'blue3': ['蓝'] * 3, 'douling_gua_yellow': ['黄'],
    'douling_gua_mixed4': ['黄', '蓝', '蓝', '蓝'], 'none_shaoyin_shaoyang': ['黄'] * 4,
}


def read_image(name):
    path = Path(__file__).parent / 'images' / f'{name}.png'
    frame = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError(f'Cannot decode {path}')
    return frame


class TestGuaxiang(unittest.TestCase):
    def test_screenshots_and_unchanged_frames(self):
        for name, expected in SAMPLES.items():
            with self.subTest(image=name):
                frame = read_image(name)
                before = frame.copy()
                result = recognize_guaxiang(frame, hud_visible=True)
                self.assertEqual(result.sequence, expected)
                self.assertEqual(len(result.detections), len(expected))
                np.testing.assert_array_equal(frame, before)

    def test_scaled_shifted_and_widescreen_hud(self):
        source = read_image('douling_gua_mixed4')
        wide = np.zeros((900, 2100, 3), np.uint8)
        wide[:, 250:1850] = source
        shifted = source.copy()
        shifted[725:795, 680:910] = np.roll(source[725:795, 680:910], (5, -9), axis=(0, 1))
        # 人工缩放只验证坐标和插值，不代替对应分辨率的实机截图。
        for frame in (cv2.resize(source, (1280, 720)), cv2.resize(source, (2560, 1440)), wide, shifted):
            with self.subTest(shape=frame.shape):
                self.assertEqual(recognize_guaxiang(frame, hud_visible=True).sequence,
                                 SAMPLES['douling_gua_mixed4'])

    def test_invalid_and_hidden_hud_are_uncertain(self):
        for frame in (None, np.empty((0, 0, 3), np.uint8), np.zeros((900, 1600), np.uint8),
                      np.zeros((10, 10, 3), np.uint8), np.zeros((900, 1600, 3), np.float32)):
            with self.subTest(shape=getattr(frame, 'shape', None)):
                self.assertEqual(recognize_guaxiang(frame, hud_visible=True).reason, 'invalid_frame')
        self.assertIsNone(recognize_guaxiang(read_image('douling_empty'), hud_visible=False).sequence)

    def test_wrong_color_and_missing_templates(self):
        frame = read_image('douling_gua_blue')
        frame[725:795, 680:910] = frame[725:795, 680:910, ::-1]
        self.assertEqual(recognize_guaxiang(frame, hud_visible=True).reason, 'low_confidence')
        with patch('src.utils.guaxiang._load_templates', side_effect=FileNotFoundError):
            self.assertEqual(recognize_guaxiang(frame, hud_visible=True).reason, 'templates_unavailable')

    def test_candidate_sorting_duplicates_and_uncertainty(self):
        blue = GuaDetection('蓝', (750, 746, 21, 27), .9, .9)
        yellow = GuaDetection('黄', (805, 746, 21, 27), .9, .9)
        duplicate = GuaDetection('蓝', (751, 746, 21, 27), .8, .9)
        self.assertEqual(_resolve_candidates([yellow, duplicate, blue])[0], ['蓝', '黄'])
        for candidates, reason in (([blue, GuaDetection('黄', blue.box, .9, .9)], 'color_conflict'),
                                   ([GuaDetection('蓝', blue.box, .55, .9)], 'low_confidence'),
                                   ([GuaDetection('蓝', (x, 746, 21, 27), .9, .9)
                                     for x in range(680, 881, 40)], 'too_many_candidates')):
            with self.subTest(reason=reason):
                sequence, _, actual = _resolve_candidates(candidates)
                self.assertIsNone(sequence)
                self.assertEqual(actual, reason)


if __name__ == '__main__':
    unittest.main()
