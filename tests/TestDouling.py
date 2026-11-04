import unittest
from types import SimpleNamespace

from config import config
from ok.test.TaskTestCase import TaskTestCase
from src.char.Douling import Douling
from src.task.AutoCombatTask import AutoCombatTask

config['debug'] = True


class TestDouling(TaskTestCase):
    task_class = AutoCombatTask
    config = config

    def read_gua(self, image):
        self.set_image(image)
        return Douling(self.task, 0).gua()

    def test_gua_plain_and_highlighted(self):
        self.assertEqual('GZZZ', self.read_gua('tests/images/douling_gua_gzzz.png'))

    def test_gua_three(self):
        self.assertEqual('ZZG', self.read_gua('tests/images/douling_gua_zzg.png'))

    def test_gua_single_on_bright_background(self):
        self.assertEqual('G', self.read_gua('tests/images/douling_gua_g.png'))

    def test_gua_1080p(self):
        self.assertEqual('GZZZ', self.read_gua('tests/images/douling_gua_gzzz_1080p.png'))

    def test_gua_not_on_field(self):
        self.assertEqual('', self.read_gua('tests/images/33forte.png'))


class TestDoulingHeavyHold(unittest.TestCase):

    def make(self, readings, flying=()):
        events = []
        task = SimpleNamespace(mouse_down=lambda: events.append('down'), mouse_up=lambda: events.append('up'),
                               next_frame=lambda: None)
        char = Douling(task, 0)
        seq = list(readings)
        flying_seq = list(flying)
        char.gua = lambda: seq.pop(0) if seq else ''
        char.flying = lambda: flying_seq.pop(0) if flying_seq else False
        char.check_combat = lambda: None
        char.wait_down = lambda: None
        char.sleep = lambda t: None
        return char, events, seq

    def test_single_hexagram_skips_heavy(self):
        char, events, _ = self.make(['G'])
        char._heavy_attack_hold(2.5)
        self.assertEqual([], events)

    def test_releases_when_fewer_than_two_left(self):
        # before, then two segments consume four hexagrams
        char, events, seq = self.make(['GZZZ', 'GZZZ', 'GZ', 'GZ', '', '', 'unused'])
        char._heavy_attack_hold(2.5)
        self.assertEqual(['down', 'up'], events)
        self.assertEqual(['unused'], seq)

    def test_retry_skips_when_one_hexagram_left(self):
        # knocked up after the first enhanced heavy, only one hexagram is left for the retry
        char, events, _ = self.make(['GZZ', 'Z'], flying=[True])
        char._heavy_attack_hold(2.5)
        self.assertEqual(['down', 'up'], events)

    def test_retry_unreadable_keeps_fixed_hold(self):
        char, events, seq = self.make(['GZ', '', 'unused'], flying=[True])
        char._heavy_attack_hold(0.05)
        self.assertEqual(['down', 'up', 'down', 'up'], events)
        self.assertEqual(['unused'], seq)

    def test_unreadable_keeps_fixed_hold(self):
        char, events, _ = self.make([''])
        char._heavy_attack_hold(0.05)
        self.assertEqual(['down', 'up'], events)


if __name__ == '__main__':
    unittest.main()
