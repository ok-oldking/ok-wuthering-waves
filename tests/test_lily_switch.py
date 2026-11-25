import unittest

from src.char.BaseChar import BaseChar, CharType, SwitchPriority
from src.char.Lily import Lily
from src.task.BaseCombatTask import BaseCombatTask


class _Task:
    now = 1000.0
    freeze = 0.0

    def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
        return 10000 if start < 0 else self.now - start - self.freeze


class _MainDps(BaseChar):
    pass


class _SubDps(BaseChar):
    pass


class LilySwitchTest(unittest.TestCase):
    def setUp(self):
        self.task = _Task()
        self.lily = Lily(self.task, 0, char_type=CharType.HEALER)
        self.main = _MainDps(self.task, 1, char_type=CharType.MAIN_DPS)
        self.sub = _SubDps(self.task, 2, char_type=CharType.SUB_DPS)
        for char, ago in ((self.lily, 60), (self.main, 20), (self.sub, 6)):
            char.last_switch_in_time = self.task.now - ago
            char.last_buff_time = self.task.now - ago
        self.combat = BaseCombatTask.__new__(BaseCombatTask)
        self.combat.chars = self.task.chars = [self.lily, self.main, self.sub]

    def cast(self, elapsed):
        """Her Liberation was cast `elapsed` seconds ago, so Slumberland can last 50 s."""
        self.lily.slumberland_start = self.task.now - elapsed
        self.lily.slumberland_block = 50

    def choose(self, current, has_intro):
        return self.combat._choose_switch_target(current, has_intro)

    def test_awake_lily_is_still_the_unbuffed_healer_pick(self):
        self.assertIs(self.choose(self.sub, False), self.lily)
        self.assertIs(self.choose(self.sub, True), self.lily)

    def test_plain_switch_in_skips_her_until_slumberland_lapses(self):
        for elapsed in (5, 25.1, 49.9):
            with self.subTest(elapsed=elapsed):
                self.cast(elapsed)
                self.assertIs(self.choose(self.sub, False), self.main)
        self.cast(50.1)
        self.assertIs(self.choose(self.sub, False), self.lily)

    def test_main_dps_plain_switch_no_longer_lands_on_sleeping_lily(self):
        # 40 s after the cast her own buff has run out, so she is the support with
        # the least buff left and the main DPS would be handed to her.
        self.cast(40)
        self.assertIs(self.choose(self.main, False), self.sub)
        self.assertIs(self.choose(self.main, True), self.lily)

    def test_block_agrees_with_the_support_chain_limit(self):
        # After one support-to-support switch without intro the selector goes back
        # to the main DPS. A sleeping Lily must not change that; an Intro after
        # 25 s still takes her, because it ends Slumberland.
        self.cast(40)
        self.combat.support_chain_without_intro = 1
        self.assertIs(self.choose(self.sub, False), self.main)
        self.assertIs(self.choose(self.sub, True), self.lily)

    def test_intro_switch_in_is_refused_for_25s_then_taken(self):
        self.cast(5)
        self.assertIs(self.choose(self.sub, True), self.main)
        self.cast(24.9)
        self.assertIs(self.choose(self.sub, True), self.main)
        self.cast(25.1)
        self.assertIs(self.choose(self.sub, True), self.lily)

    def test_intro_lockout_can_be_turned_off(self):
        self.lily.SLUMBERLAND_INTRO_LOCKOUT = 0
        self.cast(5)
        self.assertIs(self.choose(self.sub, True), self.lily)
        self.assertIs(self.choose(self.sub, False), self.main)

    def test_team_keeps_rotating_while_she_is_blocked(self):
        self.cast(8)
        self.assertIs(self.choose(self.sub, False), self.main)
        self.assertIs(self.choose(self.sub, True), self.main)
        self.main.last_switch_in_time = self.task.now
        self.assertIs(self.choose(self.main, False), self.sub)
        self.assertIs(self.choose(self.main, True), self.sub)

    def test_two_character_team_waits_for_the_intro_window(self):
        self.combat.chars = [self.main, self.lily]
        self.cast(8)
        self.assertIs(self.choose(self.main, False), self.main)
        self.assertIs(self.choose(self.main, True), self.main)
        self.cast(25.1)
        self.assertIs(self.choose(self.main, False), self.main)
        self.assertIs(self.choose(self.main, True), self.lily)

    def test_healer_lockout_fallback_does_not_route_around_the_block(self):
        self.cast(8)
        self.lily.last_full_con_switch_time = self.task.now - 8
        self.assertTrue(self.lily.healer_full_con_switch_locked())
        self.assertIs(self.choose(self.sub, False), self.main)
        self.assertIs(self.choose(self.sub, True), self.main)
        self.combat.chars = [self.sub, self.lily]
        self.assertIs(self.choose(self.sub, False), self.sub)
        self.assertIs(self.choose(self.sub, True), self.sub)

    def test_found_asleep_holds_the_selector_off_briefly(self):
        self.lily.slumberland_start = self.task.now - 5
        self.lily.slumberland_block = 10
        self.assertIs(self.choose(self.sub, False), self.main)
        # 11 s later a sighting no longer blocks her, while a cast 11 s ago still does.
        self.lily.slumberland_start = self.task.now - 11
        self.assertIs(self.choose(self.sub, False), self.lily)
        self.cast(11)
        self.assertIs(self.choose(self.sub, False), self.main)

    def test_time_stops_do_not_use_the_window_up(self):
        self.task.freeze = 3
        self.cast(49)
        self.assertIs(self.choose(self.sub, False), self.main)
        self.cast(24)
        self.assertIs(self.choose(self.sub, True), self.main)
        self.cast(53.1)
        self.assertIs(self.choose(self.sub, False), self.lily)
        self.cast(28.1)
        self.assertIs(self.choose(self.sub, True), self.lily)
