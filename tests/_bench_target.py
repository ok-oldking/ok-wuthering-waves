"""Diagnostic benchmark for has_target lock-on detection. Not a unit test.

Run: python -m unittest tests._bench_target
Prints per-fixture template confidences (has/no) per search box, the
detector verdict, and gold-ring color percentage at the match.
"""
import os
import unittest

import cv2

from config import config
from ok.test.TaskTestCase import TaskTestCase
from src.task.AutoCombatTask import AutoCombatTask

config['debug'] = True


class BenchTarget(TaskTestCase):
    task_class = AutoCombatTask
    config = config

    def test_bench(self):
        from src.combat.CombatCheck import target_enemy_color_yellow
        t = self.task
        print('\nBENCH_START', flush=True)
        for f in sorted(os.listdir('tests/images')):
            path = f'tests/images/{f}'
            if cv2.imread(path) is None:
                continue
            self.set_image(path)
            t.esc_count = 1  # disable bear-echo esc/sleep branch for benching
            has_name, no_name = t.get_target_names()
            boxes = [t.get_box_by_name(has_name).scale(1.1),
                     t.get_box_by_name('box_target_enemy_long'),
                     t.get_box_by_name('target_box_long2'),
                     t.get_box_by_name(has_name).scale(1.1, 2.0)]
            details = []
            gold = -1.0
            for box in boxes:
                ch = t.find_one(has_name, box=box, threshold=0.3)
                cn = t.find_one(no_name, box=box, threshold=0.3)
                details.append(f'{(ch.confidence if ch else 0):.2f}/{(cn.confidence if cn else 0):.2f}')
                if gold < 0:
                    best = ch if (ch and (not cn or ch.confidence >= cn.confidence)) else cn
                    if best:
                        gold = t.calculate_color_percentage(target_enemy_color_yellow, best)
            verdict = t.has_target()
            print(f'BENCH {f:28s} verdict={str(bool(verdict)):5s} '
                  f'h/n per box: {" ".join(details)} gold={gold:.3f}', flush=True)
        print('BENCH_END', flush=True)


if __name__ == '__main__':
    unittest.main()
