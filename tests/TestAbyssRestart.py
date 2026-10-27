import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

from src.combat.CombatCheck import CombatCheck
from src.task.BaseCombatTask import BaseCombatTask


class TestAbyssRestart(unittest.TestCase):
    def make_task(self):
        task = BaseCombatTask.__new__(BaseCombatTask)
        task.skip_combat_check = False
        task._in_combat = False
        task._abyss_force_combat_until = 0
        task.reset_to_false = Mock()
        task.ocr = Mock(return_value=[])
        task.find_abyss_start_marker = Mock(return_value=object())
        task.wait_ocr = Mock(return_value=[object()])
        task.wait_until = Mock(return_value=True)
        task.walk_to_box = Mock(return_value=True)
        task.find_f_with_text = Mock()
        task.box_of_screen = Mock()
        task.load_chars = Mock(return_value=True)
        task.send_key = Mock()
        task.click = Mock()
        return task

    def test_idle_arena_starts_without_opening_menu(self):
        task = self.make_task()
        with patch('src.task.BaseCombatTask.time.monotonic', return_value=100):
            self.assertTrue(task.restart_combat_in_abyss())
        task.send_key.assert_called_once_with('f')
        task.click.assert_not_called()
        self.assertTrue(task._in_combat)
        self.assertEqual(task._abyss_force_combat_until, 105)
        self.assertFalse(task.skip_combat_check)

    def test_success_and_failure_results_rechallenge_directly(self):
        for result in ('success', 'failure'):
            with self.subTest(result=result):
                task = self.make_task()
                button = object()
                task.ocr.side_effect = lambda *args, **kwargs: [button] if kwargs['match'].search('重新挑战') else []
                task.restart_combat_in_abyss()
                task.click.assert_called_once_with(button, after_sleep=1)
                task.send_key.assert_called_once_with('f')
                task.wait_until.assert_called_once()

    def test_combat_and_death_open_rechallenge_menu(self):
        for state in ('combat', 'dead'):
            with self.subTest(state=state):
                task = self.make_task()
                task.find_abyss_start_marker.return_value = None
                task.restart_combat_in_abyss()
                self.assertEqual(task.send_key.call_args_list[0].args, ('esc',))
                self.assertEqual(task.send_key.call_args_list[-1].args, ('f',))
                task.click.assert_called_once_with(task.wait_ocr.return_value[0], after_sleep=1)

    def test_failed_navigation_does_not_force_combat(self):
        task = self.make_task()
        task.walk_to_box.return_value = False
        with self.assertRaisesRegex(RuntimeError, 'reach'):
            task.restart_combat_in_abyss()
        task.send_key.assert_not_called()
        self.assertFalse(task.skip_combat_check)
        self.assertFalse(task._in_combat)
        self.assertEqual(task._abyss_force_combat_until, 0)

    def test_rechallenge_ocr_excludes_pause_dialog_explanation(self):
        task = self.make_task()
        task.restart_combat_in_abyss()
        pattern = task.ocr.call_args.kwargs['match']
        self.assertIsNone(pattern.search(
            '【返回】将清空当前进度并结束挑战，【重新挑战】将重开当前队伍的挑战'))
        for label in ('重新挑战', '重新挑戰', 'Rechallenge'):
            self.assertIsNotNone(pattern.search(label))

    def test_result_confirmation_is_accepted_before_navigation(self):
        task = self.make_task()
        retry, confirm = object(), object()
        task.ocr.side_effect = [[], [], [retry], [], [confirm]]
        task.wait_until.side_effect = lambda *args, **kwargs: kwargs['post_action']()
        task.restart_combat_in_abyss()
        self.assertEqual([call.args[0] for call in task.click.call_args_list], [retry, confirm])
        task.send_key.assert_called_once_with('f')

    def test_forced_combat_expires_after_five_seconds(self):
        task = self.make_task()
        task._abyss_force_combat_until = 105
        with patch.object(CombatCheck, 'do_check_in_combat', return_value=False) as normal_check:
            with patch('src.task.BaseCombatTask.time.monotonic', return_value=104.99):
                self.assertTrue(task.do_check_in_combat(False))
                normal_check.assert_not_called()
            with patch('src.task.BaseCombatTask.time.monotonic', return_value=105):
                self.assertFalse(task.do_check_in_combat(False))
                normal_check.assert_called_once_with(False)

    def test_reset_clears_forced_combat(self):
        task = self.make_task()
        task._abyss_force_combat_until = 105
        with patch.object(CombatCheck, 'do_reset_to_false', return_value=False):
            self.assertFalse(task.do_reset_to_false())
        self.assertEqual(task._abyss_force_combat_until, 0)

    def test_active_countdown_prevents_false_combat_end_after_target_loss(self):
        task = self.make_task()
        task._abyss_combat_active = True
        task.in_team = Mock(return_value=(True, 1, 3))
        task.get_abyss_remaining_time = Mock(return_value=173.42)
        task.scene = Mock()
        task.scene.set_in_combat.return_value = True
        with patch.object(CombatCheck, 'do_check_in_combat', return_value=False) as normal:
            self.assertTrue(task.do_check_in_combat(False))
            normal.assert_not_called()
            task.get_abyss_remaining_time.return_value = None
            self.assertFalse(task.do_check_in_combat(False))
            normal.assert_called_once_with(False)

    def test_tower_success_confirms_results_before_rechallenging(self):
        task = self.make_task()
        confirm, retry = object(), object()
        def ocr(*args, **kwargs):
            if kwargs['match'].search('确认成绩'):
                return [confirm]
            if kwargs['match'].search('重新挑战'):
                return [retry]
            return []
        task.ocr.side_effect = ocr
        task.restart_combat_in_abyss()
        self.assertEqual([call.args[0] for call in task.click.call_args_list], [confirm, retry])

    def test_selected_tower_floor_starts_without_escaping_to_another_page(self):
        task = self.make_task()
        task.find_abyss_start_marker.return_value = None
        start = object()
        task.ocr.side_effect = lambda *args, **kwargs: [start] if kwargs['match'].search('挑战开始') else []
        task.restart_combat_in_abyss()
        task.click.assert_called_once_with(start, after_sleep=1)
        task.send_key.assert_called_once_with('f')

    def test_tower_team_confirmation_uses_open_challenge_label(self):
        task = self.make_task()
        task.find_abyss_start_marker.return_value = None
        start = object()
        task.ocr.side_effect = lambda *args, **kwargs: [start] if kwargs['match'].search('开启挑战') else []
        task.restart_combat_in_abyss()
        task.click.assert_called_once_with(start, after_sleep=1)
        task.send_key.assert_called_once_with('f')

    def test_timer_reader_does_not_accept_hp_or_hud_decorations(self):
        task = self.make_task()
        task.box_of_screen_scaled = Mock()
        for text, expected in [('04:53:49', 293.49), ('03:12', 192), ('18476/18476', None), ('12:99', None)]:
            task.ocr.return_value = [Mock(name='unused')]
            task.ocr.return_value[0].name = text
            self.assertEqual(task.get_abyss_remaining_time(force=True), expected)

    def switch_task(self):
        task = self.make_task()
        current, target = Mock(), Mock()
        current.index, current.char_type, current.is_sub_dps = 0, 'Healer', False
        current.last_switch_time = 100
        target.index, target.char_type, target.intro_motion_freeze_duration = 1, 'MainDps', .9
        target.wait_switch.return_value = False
        task._choose_switch_target = Mock(return_value=target)
        task.update_lib_portrait_icon = Mock()
        task.check_combat = Mock()
        task.next_frame = Mock()
        task.sleep = Mock()
        task.log_debug = Mock()
        task.add_freeze_duration = Mock()
        task.switch_char_time_out = 5
        task.raise_not_in_combat = Mock(side_effect=RuntimeError('switch timed out'))
        return task, current, target

    def test_switch_waits_for_party_hud_to_return_during_intro(self):
        task, current, target = self.switch_task()
        task.in_team = Mock(side_effect=[(True, 0, 3), (False, -1, 0), (False, -1, 0), (True, 1, 3)])
        with patch('src.task.BaseCombatTask.time', SimpleNamespace(time=lambda: 100)):
            task.switch_next_char(current, free_intro=True)
        task.raise_not_in_combat.assert_not_called()
        current.switch_out.assert_called_once_with(con_full=True)
        self.assertTrue(target.is_current_char)
        task.next_frame.assert_called_once()

    def test_switch_still_times_out_when_party_hud_never_returns(self):
        task, current, target = self.switch_task()
        task.in_team = Mock(return_value=(False, -1, 0))
        with patch('src.task.BaseCombatTask.time', SimpleNamespace(time=Mock(side_effect=[100, 106]))):
            with self.assertRaisesRegex(RuntimeError, 'switch timed out'):
                task.switch_next_char(current, free_intro=True)
        current.switch_out.assert_not_called()


if __name__ == '__main__':
    unittest.main()
