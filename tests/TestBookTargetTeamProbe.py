import unittest

from src.task.BaseWWTask import BaseWWTask


class FakeBox:

    def __init__(self, name='', x=0, y=0, width=10, height=10):
        self.name = name
        self.x = x
        self.y = y
        self.width = width
        self.height = height


def make_task(probe_name, probes=None):
    task = BaseWWTask.__new__(BaseWWTask)
    task.sleep = lambda *args, **kwargs: None
    task._find_book_scroll_top = lambda: 0.42
    task.box_of_screen = lambda *args, **kwargs: None
    task.find_feature = lambda *args, **kwargs: [FakeBox('boss_proceed', y=100)]
    task.click = lambda *args, **kwargs: None
    task.draw_boxes = lambda *args, **kwargs: None

    def wait_feature(features, **kwargs):
        if probes is not None:
            probes.append(list(features))
        return FakeBox(probe_name)

    task.wait_feature = wait_feature
    return task


class TestBookTargetTeamProbe(unittest.TestCase):

    def test_team_screen_is_detected_by_start_challenge(self):
        task = make_task('team_start_challenge')

        self.assertTrue(task.click_on_book_target(1, 20))

    def test_level_select_screen_is_still_detected_by_close_button(self):
        task = make_task('team_close')

        self.assertTrue(task.click_on_book_target(1, 20))

    def test_open_world_travel_is_not_treated_as_team(self):
        task = make_task('gray_teleport')

        self.assertFalse(task.click_on_book_target(1, 20))

    def test_probe_lists_both_team_features(self):
        probes = []
        task = make_task('team_start_challenge', probes)

        task.click_on_book_target(1, 20)

        self.assertIn('team_start_challenge', probes[0])
        self.assertIn('team_close', probes[0])


if __name__ == '__main__':
    unittest.main()
