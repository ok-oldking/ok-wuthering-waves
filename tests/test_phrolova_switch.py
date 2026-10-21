import unittest
from unittest.mock import Mock

from src.char.BaseChar import BaseChar, CharType, SwitchPriority
from src.char.Cantarella import Cantarella
from src.char.Phrolova import Phrolova
from src.char.ShoreKeeper import ShoreKeeper
from src.char.Suisui import Suisui
from src.task.BaseCombatTask import BaseCombatTask


class _Task:
    now = 1000.0
    freeze = 0.0
    current_index = 0

    def __init__(self):
        self.f_break = Mock(return_value=True)
        self.send_key = Mock()

    def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
        return 10000 if start < 0 else self.now - start - self.freeze

    def in_team(self):
        return True, self.current_index, 3

    def has_char(self, char_class):
        return any(isinstance(char, char_class) for char in self.chars)


class PhrolovaSwitchTest(unittest.TestCase):
    def setUp(self):
        self.task = _Task()
        self.phrolova = Phrolova(self.task, 0, char_name='char_phrolova')
        self.cantarella = Cantarella(self.task, 1, char_name='char_cantarella', char_type=CharType.HEALER)
        self.shorekeeper = ShoreKeeper(self.task, 2, char_name='char_shorekeeper', char_type=CharType.HEALER)
        self.phrolova.last_liberation = self.task.now - 1
        self.cantarella.last_full_con_switch_time = self.task.now - 8
        self.shorekeeper.last_full_con_switch_time = self.task.now - 10
        self.combat = BaseCombatTask.__new__(BaseCombatTask)
        self.combat.chars = self.task.chars = [self.phrolova, self.cantarella, self.shorekeeper]

    def test_ultimate_skips_pre_switch_execution(self):
        self.assertFalse(self.phrolova.f_break(check_f_on_switch=True))
        self.task.f_break.assert_not_called()

    def test_ultimate_preserves_execution_after_switch(self):
        self.task.current_index = self.cantarella.index
        self.assertTrue(self.phrolova.f_break(check_f_on_switch=True))
        self.task.f_break.assert_called_once()

    def test_execution_resumes_at_ultimate_expiry(self):
        for elapsed, freeze, expected in ((23.9, 0, False), (24, 0, True), (25, 2, False), (26, 2, True)):
            with self.subTest(elapsed=elapsed, freeze=freeze):
                self.task.f_break.reset_mock()
                self.task.freeze = freeze
                self.phrolova.last_liberation = self.task.now - elapsed
                self.assertEqual(self.phrolova.f_break(check_f_on_switch=True), expected)
                self.assertEqual(self.task.f_break.call_count, int(expected))

    def test_execution_is_available_before_first_ultimate(self):
        self.phrolova.last_liberation = -1
        self.assertTrue(self.phrolova.f_break(check_f_on_switch=True))

    def test_manual_and_forced_execution_are_preserved(self):
        self.assertTrue(self.phrolova.f_break())
        self.assertTrue(self.phrolova.f_break(check_f_on_switch=True, force=True))
        self.task.send_key.assert_called_once_with('f', after_sleep=0.05)
        self.assertEqual(self.task.f_break.call_count, 2)

    def test_phrolova_can_leave_when_both_healers_are_locked(self):
        self.assertIs(self.combat._choose_switch_target(self.phrolova, True), self.shorekeeper)

    def test_fallback_uses_remaining_lockout_with_freeze(self):
        self.task.freeze = 3
        self.cantarella.last_full_con_switch_time = self.task.now - 15
        self.shorekeeper.last_full_con_switch_time = self.task.now - 17
        self.assertTrue(self.shorekeeper.healer_full_con_switch_locked())
        self.assertIs(self.combat._choose_switch_target(self.phrolova, True), self.shorekeeper)

    def test_full_concerto_healer_can_leave_during_ultimate(self):
        self.assertIs(self.combat._choose_switch_target(self.shorekeeper, True), self.cantarella)

    def test_unfinished_healer_stays_to_build_concerto(self):
        self.assertIs(self.combat._choose_switch_target(self.shorekeeper, False), self.shorekeeper)

    def test_unlocked_target_is_preferred_over_lockout_fallback(self):
        self.cantarella.last_full_con_switch_time = -1
        self.assertIs(self.combat._choose_switch_target(self.phrolova, True), self.cantarella)

    def test_fallback_preserves_character_specific_no_priority(self):
        suisui = Suisui(self.task, 1, char_type=CharType.HEALER)
        suisui.last_forte3_switch = self.task.now - 12
        suisui.last_full_con_switch_time = self.task.now - 12
        self.combat.chars = self.task.chars = [self.phrolova, suisui, self.shorekeeper]
        self.assertEqual(suisui.get_switch_priority(self.phrolova, True), SwitchPriority.NO)
        self.assertIs(self.combat._choose_switch_target(self.phrolova, True), self.shorekeeper)
        self.combat.chars = [self.phrolova, suisui]
        self.assertIs(self.combat._choose_switch_target(self.phrolova, True), self.phrolova)

    def test_healer_lockout_still_overrides_must_when_normal_target_exists(self):
        self.cantarella.get_switch_priority = Mock(return_value=SwitchPriority.MUST)
        self.shorekeeper.last_full_con_switch_time = -1
        self.assertIs(self.combat._choose_switch_target(self.phrolova, True), self.shorekeeper)

    def test_team_healers_can_execute_on_switch(self):
        for healer in (self.cantarella, self.shorekeeper):
            with self.subTest(healer=healer):
                self.assertTrue(healer.f_break(check_f_on_switch=True))
        self.assertEqual(self.task.f_break.call_count, 2)
        self.assertFalse(Suisui(self.task, 1, char_type=CharType.HEALER).check_f_on_switch)
        self.assertFalse(BaseChar(self.task, 1, char_type=CharType.HEALER).check_f_on_switch)

    def test_intro_switch_during_ultimate_reaches_switch_key_without_execution(self):
        actions = []
        self.task.f_break.side_effect = lambda: actions.append('f_break') or True
        self.combat.update_lib_portrait_icon = Mock()
        self.combat.check_combat = Mock()
        self.combat.log_debug = Mock()
        self.combat.sleep = Mock()
        self.combat.click = Mock()
        self.combat.add_freeze_duration = Mock()
        self.combat.in_team = self.task.in_team
        self.phrolova.current_con = 1

        def switch(key):
            actions.append('switch')
            self.task.current_index = key - 1

        self.combat.send_key = switch
        self.combat.switch_next_char(self.phrolova)
        self.assertEqual(actions, ['switch'])
        self.assertEqual(self.task.current_index, self.shorekeeper.index)
        self.assertTrue(self.shorekeeper.has_intro)

    def test_non_intro_switch_still_executes_after_teammate_arrives(self):
        actions = []
        self.task.f_break.side_effect = lambda: actions.append('f_break') or True
        self.task.get_current_con = lambda: 0
        self.task.is_con_full = lambda: False
        self.combat.update_lib_portrait_icon = Mock()
        self.combat.check_combat = Mock()
        self.combat.log_debug = Mock()
        self.combat.sleep = Mock()
        self.combat.click = Mock()
        self.combat.in_team = self.task.in_team

        def switch(key):
            actions.append('switch')
            self.task.current_index = key - 1

        self.combat.send_key = switch
        self.combat.switch_next_char(self.phrolova)
        self.assertEqual(actions, ['switch', 'f_break'])
        self.assertEqual(self.task.current_index, self.shorekeeper.index)


if __name__ == '__main__':
    unittest.main()
