import unittest
from unittest.mock import Mock, patch

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

    def test_sleeping_lily_keeps_healer_identity_and_lockout_recording(self):
        self.cast(0.1)
        self.assertTrue(self.lily.is_healer)
        self.lily.switch_out(con_full=True)
        self.assertGreater(self.lily.last_full_con_switch_time, 0)
        self.assertEqual(self.lily.last_full_con_switch_time, self.lily.last_switch_time)

    def _wire_switch_mock(self, current_idx):
        sent = []

        def send_key(key):
            sent.append(key)
            current_idx[0] = int(key) - 1

        self.combat.in_team = lambda: (True, current_idx[0], len(self.combat.chars))
        self.combat.send_key = send_key
        self.combat.sleep = Mock()
        self.task.in_team = self.combat.in_team
        self.task.send_key = send_key
        self.task.sleep = self.combat.sleep
        return sent

    def test_switch_healer_skips_sleeping_lily(self):
        self.main.is_current_char = True
        self.combat.switch_healer_enabled = lambda: True
        current_idx = [1]
        sent = self._wire_switch_mock(current_idx)

        self.cast(40)
        with patch.object(self.main, 'switch_other_char') as sw:
            self.combat.switch_healer()
        sw.assert_not_called()

        # When another awake healer is present, switch_healer chooses them instead.
        other_healer = _SubDps(self.task, 2, char_type=CharType.HEALER)
        self.combat.chars = self.task.chars = [self.lily, self.main, other_healer]
        with patch.object(self.main, 'switch_other_char') as sw:
            self.combat.switch_healer()
        sw.assert_called_once_with(allow_auto_combat=True)
        self.main.switch_other_char(allow_auto_combat=True)
        self.assertEqual(sent, ['3'])

        # Once awake, Lily is targeted again.
        sent.clear()
        current_idx[0] = 1
        self.main.is_current_char = True
        self.lily.is_current_char = False
        self.combat.chars = self.task.chars = [self.lily, self.main, self.sub]
        self.cast(50.1)
        self.combat.switch_healer()
        self.assertEqual(sent, ['1'])

    def test_switch_other_char_skips_sleeping_lily(self):
        self.lily.is_current_char = False
        self.main.is_current_char = True
        current_idx = [1]
        sent = self._wire_switch_mock(current_idx)
        self.cast(40)
        self.main.switch_other_char(allow_auto_combat=True)
        self.assertEqual(sent, ['3'])

        # Even when Lily is the immediate next slot after current_char, wrap past her.
        sent.clear()
        current_idx[0] = 2
        self.main.is_current_char = False
        self.sub.is_current_char = True
        self.sub.switch_other_char(allow_auto_combat=True)
        self.assertEqual(sent, ['2'])

        # If every teammate returns NO, fall back to the next slot rather than hanging.
        sent.clear()
        self.combat.chars = self.task.chars = [self.lily, self.sub]
        self.sub.index = 1
        current_idx[0] = 1
        self.sub.switch_other_char(allow_auto_combat=True)
        self.assertEqual(sent, ['1'])

    def test_no_deadlock_between_25s_and_30s_when_teammate_also_blocks(self):
        class _BlockedMain(BaseChar):
            def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
                return SwitchPriority.NO

        blocked = _BlockedMain(self.task, 1, char_type=CharType.MAIN_DPS)
        self.combat.chars = self.task.chars = [self.lily, blocked, self.sub]
        self.lily.set_buff_time(30)
        self.cast(29)
        self.lily.last_buff_time = self.task.now - 29
        self.assertTrue(self.lily.has_buff())
        self.assertIs(self.choose(self.sub, True), self.lily)

    def test_unbuffed_sleeping_lily_does_not_steal_must_or_high_intro(self):
        class _HighMain(BaseChar):
            def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
                return SwitchPriority.HIGH

        class _MustMain(BaseChar):
            def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
                return SwitchPriority.MUST

        self.cast(31)
        high_main = _HighMain(self.task, 1, char_type=CharType.MAIN_DPS)
        self.combat.chars = self.task.chars = [self.lily, high_main, self.sub]
        self.assertIs(self.choose(self.sub, True), high_main)

        must_main = _MustMain(self.task, 1, char_type=CharType.MAIN_DPS)
        must_main.last_switch_in_time = self.task.now - 5
        self.combat.chars = self.task.chars = [self.lily, must_main, self.sub]
        self.assertIs(self.choose(self.sub, True), must_main)

    def _wire_full_switch_combat(self, in_team_fn, send_key_fn, check_combat_fn=None):
        self.combat.in_team = in_team_fn
        self.combat.send_key = send_key_fn
        self.combat.click = Mock()
        self.combat.sleep = Mock()
        self.combat.next_frame = Mock()
        self.combat.log_debug = Mock()
        self.combat.update_lib_portrait_icon = Mock()
        self.combat.add_freeze_duration = Mock()
        self.combat.check_combat = check_combat_fn or Mock()
        self.combat.switch_char_time_out = 5
        self.combat.support_chain_without_intro = 0
        self.combat.in_liberation = False

    def test_switch_next_char_debounces_con_full_refresh(self):
        self.cast(34)
        self.lily.last_buff_time = self.task.now - 34
        self.sub.is_current_char = True
        self.sub.get_current_con = Mock(return_value=0.625)
        self.sub.f_break = Mock(return_value=False)

        # Part A: single-frame spike must NOT hijack target to Lily.
        spike_frames = iter([True, False, False])
        self.sub.is_con_full = Mock(side_effect=lambda: next(spike_frames, False))
        team_reads = [0]
        sent = []

        def send_key_a(key):
            sent.append(int(key) - 1)

        def in_team_a():
            team_reads[0] += 1
            if team_reads[0] >= 6 and sent:
                return (True, sent[-1], 3)
            return (True, self.sub.index, 3)

        self._wire_full_switch_combat(in_team_a, send_key_a)
        self.combat.switch_next_char(self.sub)
        self.assertTrue(self.main.is_current_char)
        self.assertFalse(self.lily.is_current_char)
        self.assertFalse(self.main.has_intro)

        # Part B: 2 consecutive True frames genuinely refresh to Lily with Intro.
        self.setUp()
        self.cast(34)
        self.lily.last_buff_time = self.task.now - 34
        self.sub.is_current_char = True
        self.sub.get_current_con = Mock(return_value=0.625)
        self.sub.f_break = Mock(return_value=False)
        real_frames = iter([True, True])
        self.sub.is_con_full = Mock(side_effect=lambda: next(real_frames, True))
        reads_b = [0]
        sent_b = []

        def send_key_b(key):
            sent_b.append(int(key) - 1)

        def in_team_b():
            reads_b[0] += 1
            if reads_b[0] >= 4 and sent_b:
                return (True, sent_b[-1], 3)
            return (True, self.sub.index, 3)

        self._wire_full_switch_combat(in_team_b, send_key_b)
        self.combat.switch_next_char(self.sub)
        self.assertTrue(self.lily.is_current_char)
        self.assertTrue(self.lily.has_intro)

    def test_switch_next_char_skips_stale_combat_check_once_target_is_on_field(self):
        self.cast(34)
        self.lily.last_buff_time = self.task.now - 34
        self.sub.is_current_char = True
        self.sub.f_break = Mock(return_value=False)
        state = {'reads': 0}
        sent = []

        def in_team():
            state['reads'] += 1
            # Iteration 1: top check (1) + bottom check (2) stay on sub;
            # Iteration 2: top check (3) sees Lily already on field.
            if state['reads'] <= 2:
                return (True, self.sub.index, 3)
            return (True, self.lily.index, 3)

        def send_key(key):
            sent.append(key)

        def check_combat():
            if state['reads'] >= 3:
                raise AssertionError('check_combat called after Lily was on field')

        cb_mock = Mock(side_effect=check_combat)
        self._wire_full_switch_combat(in_team, send_key, check_combat_fn=cb_mock)
        self.combat.switch_next_char(self.sub, free_intro=True)
        self.assertTrue(self.lily.is_current_char)
        self.assertEqual(cb_mock.call_count, 1)
        self.assertEqual(len(sent), 1)
