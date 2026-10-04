import unittest
from unittest.mock import Mock, call, patch

from src.task.FarmEchoTask import FarmEchoTask
from src.task.WWOneTimeTask import WWOneTimeTask


def make_task(config, is_team):
    task = FarmEchoTask.__new__(FarmEchoTask)
    task.config = config
    task.info = {}
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

    # With too few waveplates (incl. reserve), a "no rewards, enter anyway?" popup shows after
    # solo challenge and before the team screen.
    def test_weekly_challenge_confirms_low_waveplate_popup_before_team_screen(self):
        task = make_task({'Teleport to Boss': 'Weekly Challenge', 'Which Weekly Boss to Teleport': 2},
                         is_team=True)
        task.wait_click_skip_dialog_confirm = Mock()
        steps = Mock()
        for name in ('click_configured_boss_level', 'click', 'wait_click_skip_dialog_confirm', 'click_team_challenge'):
            steps.attach_mock(getattr(task, name), name)

        self.assertTrue(task.teleport_to_configured_boss())

        self.assertEqual([call.click_configured_boss_level(), call.click(0.880, 0.911, after_sleep=2),
                          call.wait_click_skip_dialog_confirm(time_out=1), call.click_team_challenge()],
                         steps.mock_calls)

    def test_reentry_from_f_confirms_low_waveplate_popup_before_starting(self):
        task = make_task({}, is_team=True)
        task.wait_until = Mock(return_value=True)
        task.send_key = Mock()
        task.init_parameters = Mock()
        task.wait_click_skip_dialog_confirm = Mock()
        steps = Mock()
        for name in ('click', 'wait_click_skip_dialog_confirm', 'wait_in_team_and_world'):
            steps.attach_mock(getattr(task, name), name)

        task.enter_configured_boss_realm_from_f()

        self.assertEqual([call.click(0.880, 0.911, after_sleep=2), call.wait_click_skip_dialog_confirm(time_out=1),
                          call.click(0.908, 0.919, after_sleep=5), call.wait_in_team_and_world(time_out=120)],
                         steps.mock_calls)

    def test_popup_mistaken_for_claim_is_retried_at_most_three_times(self):
        task = make_task({}, is_team=True)
        task.do_run = Mock(side_effect=RuntimeError('Teleport to boss failed'))
        task.handle_claim_button = Mock(return_value=True)
        task.handle_monthly_card = Mock(return_value=False)

        with patch.object(WWOneTimeTask, 'run'), self.assertRaises(RuntimeError):
            task.run()

        self.assertEqual(4, task.do_run.call_count)

    def test_farm_continues_after_claim_popup_is_closed(self):
        task = make_task({}, is_team=True)
        task.do_run = Mock(side_effect=[RuntimeError('Teleport to boss failed'), None])
        task.handle_claim_button = Mock(return_value=True)
        task.handle_monthly_card = Mock(return_value=False)

        with patch.object(WWOneTimeTask, 'run'):
            task.run()

        self.assertEqual(2, task.do_run.call_count)


if __name__ == '__main__':
    unittest.main()
