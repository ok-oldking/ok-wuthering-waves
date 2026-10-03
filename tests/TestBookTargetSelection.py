import unittest
from types import SimpleNamespace

from ok import Box

from src.task.BaseWWTask import BaseWWTask

# F2 challenge list structures in game version 3.7 (newest region first).
TACET = [4, 5, 5, 7]
FORGERY = [5, 5, 5, 5]
WEEKLY = [2, 2, 3, 4]
BOSS = [2, 4, 7, 1, 9]


class FakeBookList:
    """F2 challenge list at 16:9 in screen-height units, measured from a 3.7 recording at 1080p."""
    row_h = 153 / 1080
    header_h = 67 / 1080
    pad = 215 / 1080
    track_bottom = 953 / 1080
    search_top, search_bottom = 0.229, 0.861 - 60 / 1080  # the whole button template must fit in the search box
    layouts = {  # first button y at the top of the list, track top, visible list height
        'normal': (327 / 1080, 213 / 1080, 725 / 1080),
        'weekly': (386 / 1080, 272 / 1080, 671 / 1080),  # an extra "remaining claims" row sits above the list
    }

    def __init__(self, structure, layout='normal', click_mode='edge'):
        self.first_y, self.track_top, self.view_h = self.layouts[layout]
        self.click_mode = click_mode
        region_ends = set()
        end = 0
        for size in structure[:-1]:
            end += size
            region_ends.add(end)
        self.offsets = [0.0]
        crossed = 0
        for serial in range(1, sum(structure) + 1):
            self.offsets.append((serial - 1) * self.row_h + crossed * self.header_h)
            if serial in region_ends:
                crossed += 1
        self.content_h = self.offsets[-1] + self.pad
        self.track_len = self.track_bottom - self.track_top
        self.thumb_h = self.track_len * self.view_h / self.content_h
        self.pos = 0.0

    def thumb_top(self):
        return self.track_top + self.pos * self.track_len / self.content_h

    def click_track(self, y):
        top = self.thumb_top()
        if top <= y <= top + self.thumb_h:
            return
        if self.click_mode == 'edge':  # in game the thumb edge nearest to the click moves onto it
            top = y - self.thumb_h if y > top else y
        else:
            top = y - self.thumb_h / 2
        top = min(max(top, self.track_top), self.track_bottom - self.thumb_h)
        self.pos = (top - self.track_top) * self.content_h / self.track_len

    def visible(self):
        rows = []
        for serial in range(1, len(self.offsets)):
            y = self.first_y + self.offsets[serial] - self.pos
            if self.search_top <= y <= self.search_bottom:
                rows.append((serial, y))
        return rows


def make_task(book, height=1080):
    task = BaseWWTask.__new__(BaseWWTask)
    width = height * 16 // 9
    task._executor = SimpleNamespace(method=SimpleNamespace(width=width, height=height))
    record = SimpleNamespace(row=None, scrolls=0)
    bar_x = round(0.973 * width)

    task._find_book_scroll_thumb = lambda: Box(bar_x - 3, book.thumb_top() * height, 6, book.thumb_h * height)
    task._find_book_buttons = lambda: [Box(bar_x - 100, y * height, 44, 80, name=str(serial))
                                       for serial, y in book.visible()]

    def click(x, y=None, **kwargs):
        if isinstance(x, Box):
            record.row = int(x.name)
        else:
            record.scrolls += 1
            book.click_track(y)

    task.click = click
    task.sleep = lambda *args, **kwargs: None
    task.log_info = lambda *args, **kwargs: None
    task.draw_boxes = lambda *args, **kwargs: None
    task.wait_feature = lambda *args, **kwargs: SimpleNamespace(name='fast_travel_custom')
    return task, record


class TestBookTargetSelection(unittest.TestCase):
    lists = {'tacet': (TACET, 'normal'), 'forgery': (FORGERY, 'normal'), 'weekly': (WEEKLY, 'weekly'),
             'boss': (BOSS, 'normal')}

    def test_every_serial_is_reached_with_one_scroll(self):
        for height in (1080, 1440):
            for name, (structure, layout) in self.lists.items():
                for serial in range(1, sum(structure) + 1):
                    with self.subTest(height=height, list=name, serial=serial):
                        task, record = make_task(FakeBookList(structure, layout), height)
                        task.click_on_book_target(serial, sum(structure), structure)
                        self.assertEqual(serial, record.row)
                        self.assertLessEqual(record.scrolls, 1)

    def test_future_structures_need_no_code_change(self):
        # Shapes the lists may grow into: more regions, one long region, many one-item regions.
        cases = [([9, 9, 9, 9, 9], 'normal'), ([30], 'normal'), ([1] * 12, 'normal'), ([3, 5, 5, 7, 2], 'normal'),
                 ([2, 3, 3, 4, 2], 'weekly')]
        for structure, layout in cases:
            for serial in range(1, sum(structure) + 1):
                with self.subTest(structure=structure, serial=serial):
                    task, record = make_task(FakeBookList(structure, layout))
                    task.click_on_book_target(serial, sum(structure), structure)
                    self.assertEqual(serial, record.row)
                    self.assertLessEqual(record.scrolls, 1)

    def test_closed_loop_still_lands_when_track_clicks_behave_differently(self):
        for name, (structure, layout) in self.lists.items():
            for serial in range(1, sum(structure) + 1):
                with self.subTest(list=name, serial=serial):
                    task, record = make_task(FakeBookList(structure, layout, click_mode='centre'))
                    task.click_on_book_target(serial, sum(structure), structure)
                    self.assertEqual(serial, record.row)

    def test_stale_structure_raises_instead_of_clicking_a_scrolled_row(self):
        # The game added a boss to a region but the task still has the old structure.
        cases = [([4, 5, 5, 7], [2, 5, 5, 7], 'normal'), ([2, 2, 3, 4], [1, 2, 3, 4], 'weekly'),
                 ([3, 4, 7, 1, 9], BOSS, 'normal'), ([2, 4, 7, 1, 10], BOSS, 'normal')]
        for actual, configured, layout in cases:
            first_page = len(FakeBookList(configured, layout).visible())
            for serial in range(first_page + 1, sum(configured) + 1):
                with self.subTest(actual=actual, configured=configured, serial=serial):
                    task, record = make_task(FakeBookList(actual, layout))
                    with self.assertRaises(ValueError):
                        task.click_on_book_target(serial, sum(configured), configured)
                    self.assertIsNone(record.row)


if __name__ == '__main__':
    unittest.main()
