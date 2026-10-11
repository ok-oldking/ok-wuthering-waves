import unittest
from pathlib import Path

import cv2
import numpy as np

from src.utils.douling_energy import _energy_regions, recognize_energy


SAMPLES = {'none_shaoyin_shaoyang': 'none', 'shaoyang': 'shaoyang',
           'shaoyin': 'shaoyin', 'shaoyin_and_shaoyang': 'both'}


def read_image(name):
    path = Path(__file__).parent / 'images' / f'{name}.png'
    frame = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError(f'Cannot decode {path}')
    return frame


class TestDoulingEnergy(unittest.TestCase):
    def test_four_states_and_readonly_frames(self):
        for name, expected in SAMPLES.items():
            with self.subTest(image=name):
                frame = read_image(name)
                self.assertEqual(frame.shape, (1080, 1920, 3))
                before = frame.copy()
                frame.setflags(write=False)
                self.assertEqual(recognize_energy(frame, hud_visible=True).state, expected)
                np.testing.assert_array_equal(frame, before)
                self.assertEqual(recognize_energy(frame, hud_visible=False).reason, 'hud_hidden')

    def test_invalid_and_obscured_frames_are_uncertain(self):
        for frame in (None, [], np.empty((0, 0, 3), np.uint8), np.zeros((1080, 1920), np.uint8),
                      np.zeros((1080, 1920, 4), np.uint8), np.zeros((10, 10, 3), np.uint8),
                      np.zeros((1080, 1920, 3), np.float32)):
            with self.subTest(shape=getattr(frame, 'shape', None)):
                self.assertEqual(recognize_energy(frame, hud_visible=True).reason, 'invalid_frame')
        for x, y, w, h in _energy_regions(1920, 1080):
            frame = read_image('shaoyin_and_shaoyang')
            frame[y:y + h, x:x + w] = 0
            self.assertEqual(recognize_energy(frame, hud_visible=True).reason, 'bar_not_visible')

    def test_outside_regions_and_local_glare_do_not_change_state(self):
        for name, expected in SAMPLES.items():
            with self.subTest(image=name):
                frame = read_image(name)
                altered = np.full_like(frame, (0, 0, 255))
                for x, y, w, h in _energy_regions(1920, 1080):
                    altered[y:y + h, x:x + w] = frame[y:y + h, x:x + w]
                self.assertEqual(recognize_energy(altered, hud_visible=True).state, expected)
        frame = read_image('none_shaoyin_shaoyang')
        for (x, y, _, h), color in zip(_energy_regions(1920, 1080), ((40, 220, 255), (255, 120, 40))):
            frame[y:y + h, x:x + 12] = color
        self.assertEqual(recognize_energy(frame, hud_visible=True).state, 'none')

    def test_scaled_wide_and_tall_hud(self):
        for name, expected in SAMPLES.items():
            source = cv2.resize(read_image(name), (1600, 900))
            wide, tall = np.zeros((900, 2100, 3), np.uint8), np.zeros((1100, 1600, 3), np.uint8)
            wide[:, 250:1850], tall[200:] = source, source
            # 人工缩放只验证采样，不代替对应分辨率的实机截图。
            for frame in (cv2.resize(source, (1280, 720)), cv2.resize(source, (2560, 1440)), wide, tall):
                with self.subTest(image=name, shape=frame.shape):
                    self.assertEqual(recognize_energy(frame, hud_visible=True).state, expected)


if __name__ == '__main__':
    unittest.main()
