"""Diagnostic benchmark for cooldown OCR frequency. Not a unit test.

Run: python -m unittest tests._bench_cd
Simulates combat-loop frames (scene reset per frame) querying has_cd,
counting OCR invocations and wall time.
"""
import time
import unittest

from config import config
from ok.test.TaskTestCase import TaskTestCase
from src.task.AutoCombatTask import AutoCombatTask

config['debug'] = True

FRAMES = 50


class BenchCD(TaskTestCase):
    task_class = AutoCombatTask
    config = config

    def test_bench(self):
        t = self.task
        t.do_reset_to_false()
        self.set_image('tests/images/in_combat.png')
        t.load_chars()
        calls = {'n': 0}
        orig = t.ocr

        def counting_ocr(*a, **k):
            calls['n'] += 1
            return orig(*a, **k)

        t.ocr = counting_ocr
        try:
            start = time.time()
            for _ in range(FRAMES):
                t.scene.reset()  # what next_frame does between combat-loop iterations
                t.has_cd('resonance')
                t.has_cd('liberation')
            wall = time.time() - start
        finally:
            t.ocr = orig
        print(f'\nBENCH_CD frames={FRAMES} ocr_calls={calls["n"]} wall={wall:.2f}s '
              f'per_frame={wall / FRAMES * 1000:.1f}ms', flush=True)


if __name__ == '__main__':
    unittest.main()
