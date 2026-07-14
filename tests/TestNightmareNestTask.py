import unittest
import re

from src.task.NightmareNestTask import NestTarget, NightmareNestTask


class FakeBox:

    def __init__(self, name, x=0, y=0, width=20, height=10):
        self.name = name
        self.x = x
        self.y = y
        self.width = width
        self.height = height


class TestNightmareNestTask(unittest.TestCase):

    def test_capture_success_clears_combat_before_post_combat_waits(self):
        task = NightmareNestTask.__new__(NightmareNestTask)
        task._capture_mode = True
        task._in_combat = True
        picked = []

        task.pick_f = lambda handle_claim=True: picked.append(handle_claim)
        task.has_echo_notification = lambda: True

        def reset_to_false(reason=''):
            task._in_combat = False
            task.out_of_combat_reason = reason
            return False

        task.reset_to_false = reset_to_false

        self.assertFalse(task.on_combat_check())
        self.assertEqual([False], picked)
        self.assertFalse(task._in_combat)
        self.assertEqual('echo captured', task.out_of_combat_reason)

    def test_unreachable_nest_is_cached_when_travel_does_not_enter_world(self):
        task = NightmareNestTask.__new__(NightmareNestTask)
        task._unreachable_nests = set()
        backs = []
        clicks = []
        wait_timeouts = []
        world_waits = []
        travel = FakeBox('fast_travel_custom')

        task.wait_until = lambda *args, **kwargs: wait_timeouts.append(kwargs['time_out']) or travel
        task.find_one = lambda name, **kwargs: travel if name == travel.name else None
        task.click = lambda box, **kwargs: clicks.append((box, kwargs))
        task.wait_in_team_and_world = lambda *args, **kwargs: world_waits.append(kwargs) or False
        task.back = lambda *args, **kwargs: backs.append(kwargs)
        task.log_info = lambda *args, **kwargs: None

        target = NestTarget(object(), 'go_nightmare:36:0.205')

        self.assertFalse(task._travel_to_nest_or_skip(target))
        self.assertIn(target.cache_key, task._unreachable_nests)
        self.assertEqual([1], wait_timeouts)
        self.assertEqual([(travel, {'after_sleep': 1})], clicks)
        self.assertEqual([], world_waits)
        self.assertEqual([{'after_sleep': 1}], backs)

    def test_find_nest_skips_cached_unreachable_row(self):
        task = NightmareNestTask.__new__(NightmareNestTask)
        task.count_re = re.compile(r"(\d{1,2})/(\d{1,2})")
        task.queues = [lambda: None]
        task._unreachable_nests = {'<lambda>:36:10'}
        task.log_info = lambda *args, **kwargs: None
        task.height_of_screen = lambda value: 1000 * value
        task.width_of_screen = lambda value: 2000 * value
        ocr_calls = []

        count_boxes = [
            FakeBox('0/36', y=200),
            FakeBox('0/36', y=300),
        ]

        def ocr(*args, **kwargs):
            ocr_calls.append((args, kwargs))
            return count_boxes

        task.ocr = ocr

        target = task.find_nest()

        self.assertIsInstance(target, NestTarget)
        self.assertIs(target.box, count_boxes[1])
        self.assertEqual('<lambda>:36:15', target.cache_key)
        self.assertEqual(1800, target.box.x)
        self.assertEqual(1, len(ocr_calls))

    def test_cache_key_ignores_small_ocr_position_jitter(self):
        task = NightmareNestTask.__new__(NightmareNestTask)
        task.queues = [lambda: None]
        task.height_of_screen = lambda value: 1000 * value

        first = task._make_nest_cache_key(FakeBox('0/36', y=200), '36')
        shifted = task._make_nest_cache_key(FakeBox('0/36', y=202), '36')

        self.assertEqual(first, shifted)


if __name__ == '__main__':
    unittest.main()
