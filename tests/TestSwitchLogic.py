import time
import unittest

from config import config
from ok.test.TaskTestCase import TaskTestCase
from src.char.BaseChar import BaseChar, CharType, SwitchPriority
from src.task.AutoCombatTask import AutoCombatTask

config['debug'] = True


class MustChar(BaseChar):
    def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
        return SwitchPriority.MUST


class NoChar(BaseChar):
    def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
        return SwitchPriority.NO


class TestSwitchLogic(TaskTestCase):
    """Characterization tests for the _choose_switch_target decision rules."""
    task_class = AutoCombatTask
    config = config

    def make_char(self, index, char_type, cls=BaseChar, switched_in=0.0, buff_time=None,
                  buffed_ago=None, switched_out_ago=None):
        char = cls(self.task, index, char_name=f'char{index}', char_type=char_type,
                   buff_time=buff_time)
        char.last_switch_in_time = switched_in
        if buffed_ago is not None:
            char.last_buff_time = time.time() - buffed_ago
        if switched_out_ago is not None:
            char.last_switch_time = time.time() - switched_out_ago
        return char

    def set_team(self, *chars):
        self.task.freeze_durations = []
        self.task.chars = list(chars)
        return chars

    def test_intro_prefers_main_dps_over_older_sub(self):
        current, sub, main = self.set_team(
            self.make_char(0, CharType.HEALER),
            self.make_char(1, CharType.SUB_DPS, switched_in=5),
            self.make_char(2, CharType.MAIN_DPS, switched_in=10))
        self.assertIs(self.task._choose_switch_target(current, has_intro=True), main)

    def test_intro_must_priority_wins(self):
        current, must_sub, main = self.set_team(
            self.make_char(0, CharType.HEALER),
            self.make_char(1, CharType.SUB_DPS, cls=MustChar),
            self.make_char(2, CharType.MAIN_DPS))
        self.assertIs(self.task._choose_switch_target(current, has_intro=True), must_sub)

    def test_no_priority_is_excluded(self):
        current, no_healer, sub = self.set_team(
            self.make_char(0, CharType.MAIN_DPS),
            self.make_char(1, CharType.HEALER, cls=NoChar),
            self.make_char(2, CharType.SUB_DPS))
        self.assertIs(self.task._choose_switch_target(current, has_intro=False), sub)

    def test_all_no_priority_keeps_current(self):
        current, a, b = self.set_team(
            self.make_char(0, CharType.MAIN_DPS),
            self.make_char(1, CharType.HEALER, cls=NoChar),
            self.make_char(2, CharType.SUB_DPS, cls=NoChar))
        self.assertIs(self.task._choose_switch_target(current, has_intro=False), current)

    def test_main_current_picks_lowest_buff_remaining(self):
        # healer buff expires in ~4s, sub in ~10s -> healer needs refreshing first
        current, healer, sub = self.set_team(
            self.make_char(0, CharType.MAIN_DPS),
            self.make_char(1, CharType.HEALER, buff_time=24, buffed_ago=20),
            self.make_char(2, CharType.SUB_DPS, buff_time=14, buffed_ago=4))
        self.assertIs(self.task._choose_switch_target(current, has_intro=False), healer)

    def test_switch_cd_filters_recently_switched_out(self):
        # sub would win the buff rules (older switch-in) but left field 0.5s ago
        current, sub, healer = self.set_team(
            self.make_char(0, CharType.MAIN_DPS),
            self.make_char(1, CharType.SUB_DPS, switched_in=1, switched_out_ago=0.5),
            self.make_char(2, CharType.HEALER, switched_in=5, switched_out_ago=30))
        self.assertIs(self.task._choose_switch_target(current, has_intro=False), healer)

    def test_sub_current_with_buff_targets_main(self):
        # current sub has an active buff and the healer is buffed too -> go main
        current, healer, main = self.set_team(
            self.make_char(0, CharType.SUB_DPS, buff_time=14, buffed_ago=2),
            self.make_char(1, CharType.HEALER, buff_time=24, buffed_ago=2),
            self.make_char(2, CharType.MAIN_DPS))
        current.last_buff_time = time.time() - 2
        self.assertIs(self.task._choose_switch_target(current, has_intro=False), main)

    def test_rule3_prefers_unbuffed_healer(self):
        current = self.make_char(0, CharType.SUB_DPS, buff_time=0)
        healer = self.make_char(1, CharType.HEALER, buff_time=24)
        sub = self.make_char(2, CharType.SUB_DPS, buff_time=14)
        self.set_team(current, healer, sub)
        self.assertIs(self.task._choose_switch_target(current, has_intro=False), healer)


if __name__ == '__main__':
    unittest.main()
