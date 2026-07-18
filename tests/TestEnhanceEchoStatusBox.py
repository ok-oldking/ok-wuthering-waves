import unittest

from ok.feature.Box import Box
from src.task.EnhanceEchoTask import EnhanceEchoTask


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


if __name__ == '__main__':
    unittest.main()
