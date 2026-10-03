import unittest
from unittest.mock import Mock

from src.task.FarmEchoTask import FarmEchoTask


def make_task(config, is_team):
    task = FarmEchoTask.__new__(FarmEchoTask)
    task.config = config
    task.total_weekly_number = 9
    task.total_boss_number = 20
    task.nightmare_structure = [5, 10]
    for name in ('ensure_main', 'info_set', 'openF2Book', 'open_boss_book', 'click', 'click_configured_boss_level',
                 'click_team_challenge', 'wait_click_travel', 'wait_in_team_and_world', 'sleep'):
        setattr(task, name, Mock())
    task.book_targets = []
    task.click_on_book_target = lambda serial, total, structure=None: task.book_targets.append(
        (serial, total, structure)) or is_team
    return task


class TestFarmEchoTeleport(unittest.TestCase):

    def test_special_nightmare_is_found_after_the_nightmare_nests(self):
        task = make_task({'Teleport to Boss': 'Special Nightmare', 'Which Special Nightmare to Teleport': 3},
                         is_team=True)

        self.assertTrue(task.teleport_to_configured_boss())

        task.open_boss_book.assert_called_once_with('mengyan')
        self.assertEqual([(8, 15, [5, 10])], task.book_targets)
        task.click_team_challenge.assert_called_once_with()
        task.click_configured_boss_level.assert_not_called()

    def test_boss_challenge_target_is_unchanged(self):
        task = make_task({'Teleport to Boss': 'Boss Challenge', 'Which Boss Challenge to Teleport': 3},
                         is_team=False)

        self.assertFalse(task.teleport_to_configured_boss())

        task.open_boss_book.assert_called_once_with('qiangdi')
        self.assertEqual([(3, 20, None)], task.book_targets)
        task.wait_click_travel.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
