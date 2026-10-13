import unittest

import cv2
import numpy as np

from ok.feature.Box import Box, relative_box
from src.task.EnhanceEchoTask import EnhanceEchoTask, slot_corner


class FakeEnhanceTask:
    """Drives the drop/lock status checks with scripted feature boxes.

    find_best_match_in_box records every call it receives, so a test can
    assert the search box covers both sibling templates: a sibling template
    larger than the search area crashes cv2.matchTemplate (#1238, #1291).
    """

    def __init__(self, boxes, match_name):
        self.boxes = boxes
        self.match_name = match_name
        self.search_calls = []
        self.fail_reason = ''
        self.config = {}
        self.counters = {}

    def get_box_by_name(self, name):
        return self.boxes[name]

    def find_best_match_in_box(self, box, names, threshold=0):
        self.search_calls.append((box, names, threshold))
        return Box(0, 0, 1, 1, name=self.match_name)

    def info_incr(self, name):
        self.counters[name] = self.counters.get(name, 0) + 1

    def info_get(self, name):
        return self.counters.get(name, 0)

    def send_key(self, key, after_sleep=0):
        """No-op: key presses do not affect the search-box geometry."""

    def log_info(self, *args, **kwargs):
        """No-op: logging is irrelevant to the assertions."""

    def screenshot_echo(self, name):
        """No-op: screenshots are irrelevant to the assertions."""

    def esc(self):
        """No-op: leaving the screen is irrelevant to the assertions."""

    def wait_ocr(self, *args, **kwargs):
        return None


class FakeSelectTask:
    """Scripts the bag grid: which card holds the gold selection frame and
    whether the selected echo is +0.

    3.7 keeps the just-enhanced echo selected (and scrolled into view) when
    returning to the bag, so the task must pick a +0 echo itself. Toggling
    the sort order twice scrolls back to the top and selects the first card;
    clicking an empty slot keeps the old selection.
    """

    list_to_top = EnhanceEchoTask.list_to_top
    click_0_level_slot = EnhanceEchoTask.click_0_level_slot

    def __init__(self, zero_level_results=(), selected=0, empty_slots=(), frames=None):
        self.zero_level_results = list(zero_level_results)
        self.selected = selected
        self.empty_slots = empty_slots
        self.frames = frames or [np.zeros((1080, 1920, 3), np.uint8)] * 2
        self.frame = self.frames[0]
        self.clicks = []

    def click(self, x, y, after_sleep=0):
        if (x, y) == (0.35, 0.917):
            self.clicks.append('sort order')
            self.selected = 0
            self.frame = self.frames[1]
            return
        slot = next(i for i in range(24)
                    if abs(slot_corner(i)[0] + 0.037 - x) < 1e-9 and abs(slot_corner(i)[1] + 0.08 - y) < 1e-9)
        self.clicks.append(f'card {slot + 1}')
        if slot not in self.empty_slots:
            self.selected = slot

    def find_selected_slot(self):
        return self.selected

    def box_of_screen(self, x, y, to_x, to_y):
        return relative_box(1920, 1080, x, y, to_x=to_x, to_y=to_y)

    def wait_until(self, condition, time_out=0):
        return condition()

    def is_0_level(self):
        return self.zero_level_results.pop(0)

    def sleep(self, timeout):
        """No-op: the fake grid has no animation."""

    def log_info(self, *args, **kwargs):
        """No-op: logging is irrelevant to the assertions."""


def bag_frame(gold_slot=None, edge_bgr=(177, 228, 228)):
    """A dark bag grid; gold_slot gets a thin frame just outside its card."""
    frame = np.full((1080, 1920, 3), (75, 70, 40), np.uint8)
    if gold_slot is not None:
        x, y = slot_corner(gold_slot)
        cv2.rectangle(frame, (round(x * 1920) - 3, round(y * 1080) - 4),
                      (round((x + 0.074) * 1920) + 2, round((y + 0.1667) * 1080) + 2), edge_bgr, 3)
    return frame


class TestEnhanceEchoStatusBox(unittest.TestCase):
    # Sibling templates deliberately differ in size, with the sibling BIGGER
    # than the anchor box: the geometry that crashed the lock pair in
    # #1238/#1291.

    def assertCovers(self, search, template_box):
        self.assertLessEqual(search.x, template_box.x)
        self.assertLessEqual(search.y, template_box.y)
        self.assertGreaterEqual(search.x + search.width,
                                template_box.x + template_box.width)
        self.assertGreaterEqual(search.y + search.height,
                                template_box.y + template_box.height)

    def test_drop_search_box_covers_both_drop_templates(self):
        dropped = Box(534, 152, 28, 26, name='echo_dropped')
        not_dropped = Box(534, 151, 28, 29, name='echo_not_dropped')
        task = FakeEnhanceTask({'echo_dropped': dropped,
                                'echo_not_dropped': not_dropped},
                               match_name='echo_dropped')

        EnhanceEchoTask.trash_and_esc(task)

        [(search, names, threshold)] = task.search_calls
        self.assertEqual(names, ['echo_dropped', 'echo_not_dropped'])
        self.assertEqual(threshold, 0.7)
        self.assertCovers(search, dropped)
        self.assertCovers(search, not_dropped)

    def test_lock_search_box_covers_both_lock_templates(self):
        locked = Box(631, 152, 23, 26, name='echo_locked')
        not_locked = Box(631, 151, 24, 29, name='echo_not_locked')
        task = FakeEnhanceTask({'echo_locked': locked,
                                'echo_not_locked': not_locked},
                               match_name='echo_locked')

        EnhanceEchoTask.lock_and_esc(task)

        [(search, names, threshold)] = task.search_calls
        self.assertEqual(names, ['echo_locked', 'echo_not_locked'])
        self.assertEqual(threshold, 0.7)
        self.assertCovers(search, locked)
        self.assertCovers(search, not_locked)

    def test_gold_frame_marks_the_selected_card(self):
        task = FakeSelectTask()
        for slot in (0, 4, 18, 23):
            task.frame = bag_frame(slot)
            self.assertEqual(slot, EnhanceEchoTask.find_selected_slot(task))

    def test_no_selected_card_without_gold_frame(self):
        task = FakeSelectTask()
        task.frame = bag_frame()
        self.assertIsNone(EnhanceEchoTask.find_selected_slot(task))
        task.frame = bag_frame(4, edge_bgr=(235, 235, 230))  # a white hover outline is not a selection
        self.assertIsNone(EnhanceEchoTask.find_selected_slot(task))

    def test_start_from_the_card_the_user_selected(self):
        task = FakeSelectTask(selected=3)

        self.assertEqual(3, EnhanceEchoTask.find_start_slot(task))

        self.assertEqual(['sort order', 'sort order'], task.clicks)

    def test_start_from_first_card_when_no_selection_found(self):
        task = FakeSelectTask(selected=None)

        self.assertEqual(0, EnhanceEchoTask.find_start_slot(task))

    def test_start_rejected_when_list_was_scrolled(self):
        rng = np.random.default_rng(0)
        scrolled, top = (rng.integers(0, 256, (1080, 1920, 3), np.uint8) for _ in range(2))
        task = FakeSelectTask(selected=3, frames=[scrolled, top])

        with self.assertRaises(Exception):
            EnhanceEchoTask.find_start_slot(task)

    def test_start_card_is_used_when_it_is_0_level(self):
        task = FakeSelectTask([True])

        self.assertTrue(EnhanceEchoTask.select_0_level_echo(task, 3))

        self.assertEqual(['card 4'], task.clicks)

    def test_list_returns_to_top_when_start_card_is_enhanced(self):
        task = FakeSelectTask([False, True])

        self.assertTrue(EnhanceEchoTask.select_0_level_echo(task, 3))

        self.assertEqual(['card 4', 'sort order', 'sort order', 'card 4'], task.clicks)

    def test_list_returns_to_top_first_after_a_kept_echo(self):
        task = FakeSelectTask([True])

        self.assertTrue(EnhanceEchoTask.select_0_level_echo(task, 3, to_top=True))

        self.assertEqual(['sort order', 'sort order', 'card 4'], task.clicks)

    def test_empty_start_slot_never_enhances_skipped_echo(self):
        # Everything from the start card on is done and gone: the start slot is
        # empty and the selection rests on a skipped +0 echo to its left.
        task = FakeSelectTask([True, True], selected=2, empty_slots=(3,))

        self.assertFalse(EnhanceEchoTask.select_0_level_echo(task, 3))

        self.assertEqual(['card 4', 'sort order', 'sort order', 'card 4'], task.clicks)

    def test_no_0_level_echo_left(self):
        task = FakeSelectTask([False, False])

        self.assertFalse(EnhanceEchoTask.select_0_level_echo(task, 3))

        self.assertEqual(['card 4', 'sort order', 'sort order', 'card 4'], task.clicks)


if __name__ == '__main__':
    unittest.main()
