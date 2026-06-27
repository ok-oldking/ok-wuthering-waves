"""Diagnostic benchmark for forte detection. Not a unit test.

Run: python -m unittest tests._bench_forte
Prints per-fixture raw confidences for mouse_forte / e_forte template
matches and the is_forte_full white percentage.

assets/images/33.png and assets/images/31.png are the annotation source
frames for mouse_forte and e_forte respectively - positives by construction.
"""
import os
import unittest

import cv2

from config import config
from ok.test.TaskTestCase import TaskTestCase
from src.char.BaseChar import forte_white_color
from src.task.AutoCombatTask import AutoCombatTask
from src.task.BaseWWTask import binarize_for_matching

config['debug'] = True


class BenchForte(TaskTestCase):
    task_class = AutoCombatTask
    config = config

    def probe(self, name, **kwargs):
        box = self.task.find_one(name, threshold=0.05, **kwargs)
        return box.confidence if box else 0.0

    def test_bench(self):
        t = self.task
        files = [f'tests/images/{f}' for f in sorted(os.listdir('tests/images'))]
        files += ['assets/images/33.png', 'assets/images/31.png']
        print('\nBENCH_START', flush=True)
        for path in files:
            if cv2.imread(path) is None:
                continue
            self.set_image(path)
            mouse = self.probe('mouse_forte', horizontal_variance=0.025, vertical_variance=0.015,
                               frame_processor=binarize_for_matching)
            e = self.probe('e_forte', horizontal_variance=0.025,
                           frame_processor=binarize_for_matching)
            box = t.box_of_screen_scaled(3840, 2160, 2251, 1993, 2311, 2016, name='forte_full', hcenter=True)
            white = t.calculate_color_percentage(forte_white_color, box)
            verdict_m = bool(t.find_mouse_forte())
            verdict_e = bool(t.find_e_forte())
            cap = glyph = -1.0
            ebox = t.find_one('e_forte', horizontal_variance=0.025, threshold=0.5,
                              frame_processor=binarize_for_matching)
            if ebox:
                cap = t.calculate_color_percentage({'r': (200, 255), 'g': (200, 255), 'b': (200, 255)}, ebox)
                glyph = t.calculate_color_percentage({'r': (0, 110), 'g': (0, 110), 'b': (0, 110)}, ebox)
            print(f'BENCH {os.path.basename(path):28s} mouse={mouse:.2f}({str(verdict_m):5s}) '
                  f'e={e:.2f}({str(verdict_e):5s}) cap={cap:.2f} glyph={glyph:.2f} '
                  f'forte_white={white:.3f}', flush=True)
        print('BENCH_END', flush=True)


if __name__ == '__main__':
    unittest.main()
