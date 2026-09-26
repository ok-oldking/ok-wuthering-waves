import unittest

from src.char.YangYangSpPolicy import YangYangSpPolicy
from src.char.YangYangSpVision import YangYangSpState as State


class TestYangYangSpPolicy(unittest.TestCase):
    def test_heavy_wins_when_all_skills_are_ready(self):
        policy = YangYangSpPolicy()
        state = State('feather', True, 'feather', True)
        self.assertEqual(policy.choose(state, 0, can_q=True), 'wait')
        self.assertEqual(policy.choose(state, .15, can_q=True), 'hold')
        self.assertIsNone(policy.pending_e)
        self.assertFalse(policy.r_used)
        self.assertFalse(policy.q_used)

    def test_followup_can_be_resumed_without_ready_resources(self):
        policy = YangYangSpPolicy()
        state = State('followup', False, 'feather', True)
        policy.choose(state, 0)
        self.assertEqual(policy.choose(state, .15), 'hold')
        self.assertEqual(policy.reason, 'resume_followup')

    def test_combo_protects_unknown_frames_and_all_followup_stages(self):
        policy = YangYangSpPolicy()
        ready = State('feather', True)
        policy.choose(ready, 0)
        policy.choose(ready, .15)
        for elapsed, state in [(1, State('air', False, 'feather', True)),
                               (1.3, State()), (2, State('followup', False, 'crescent', True)),
                               (3, State('feather')), (3.2, State('feather'))]:
            self.assertEqual(policy.choose(state, elapsed, can_q=True), 'hold')
        self.assertEqual(policy.choose(State('feather'), 3.4), 'release')
        self.assertEqual(policy.heavy_ends, 1)

    def test_single_normal_frame_does_not_end_combo(self):
        policy = YangYangSpPolicy()
        ready = State('azure', True)
        policy.choose(ready, 0)
        policy.choose(ready, .15)
        policy.choose(State('sword'), 1)
        policy.choose(State(), 1.2)
        self.assertEqual(policy.choose(State('sword'), 1.4), 'hold')
        self.assertEqual(policy.choose(State('sword'), 1.6), 'hold')

    def test_active_combo_may_finish_after_soft_field_limit(self):
        policy = YangYangSpPolicy()
        ready = State('azure', True)
        policy.choose(ready, 19)
        policy.choose(ready, 19.2)
        self.assertEqual(policy.choose(ready, 20.5), 'hold')
        policy.choose(State('sword'), 21)
        self.assertEqual(policy.choose(State('sword'), 21.4), 'release')
        self.assertEqual(policy.choose(State('sword'), 21.5), 'switch')

    def test_stuck_hold_is_bounded_and_not_restarted_indefinitely(self):
        policy = YangYangSpPolicy()
        state = State('feather', True)
        policy.choose(state, 0)
        policy.choose(state, .15)
        self.assertEqual(policy.choose(state, 8.2), 'release')
        self.assertEqual(policy.heavy_ends, 0)
        self.assertNotEqual(policy.choose(state, 8.4), 'hold')
        self.assertEqual(policy.choose(state, 20), 'switch')

    def test_enhanced_e_beats_r_and_only_retries_twice(self):
        policy = YangYangSpPolicy()
        state = State('sword', False, 'crescent', True)
        policy.choose(state, 0)
        self.assertEqual(policy.choose(state, .15), 'E')
        self.assertEqual(policy.choose(state, .4), 'wait')
        self.assertEqual(policy.choose(state, 1.1), 'E')
        self.assertIn('NO_VISUAL_RESPONSE', policy.feedback)
        self.assertEqual(policy.choose(state, 2.1), 'R')
        self.assertNotIn(policy.choose(state, 2.3), ('E', 'R'))

    def test_e_visual_change_unlocks_next_state(self):
        policy = YangYangSpPolicy()
        e = State('sword', False, 'crescent')
        policy.choose(e, 0)
        policy.choose(e, .15)
        ready = State('feather', True)
        self.assertEqual(policy.choose(ready, .4), 'wait')
        self.assertIsNotNone(policy.pending_e)
        self.assertEqual(policy.choose(ready, .6), 'hold')
        self.assertIn('E_ICON_CHANGED', policy.feedback)

    def test_brief_e_flicker_does_not_reset_retry_limit(self):
        policy = YangYangSpPolicy()
        e = State('sword', False, 'crescent')
        policy.choose(e, 0)
        policy.choose(e, .15)
        policy.choose(State('sword'), .2)
        self.assertIsNotNone(policy.pending_e)
        self.assertEqual(policy.choose(e, .25), 'wait')
        self.assertEqual(policy.e_attempts, 1)

    def test_unknown_hud_never_uses_echo(self):
        policy = YangYangSpPolicy()
        policy.choose(State(), 0, can_q=True)
        self.assertEqual(policy.choose(State(), 1, can_q=True), 'normal')

    def test_normal_e_is_never_requested(self):
        policy = YangYangSpPolicy()
        normal = State('feather')
        for elapsed in (0, 1, 5, 10):
            self.assertEqual(policy.choose(normal, elapsed), 'normal')

    def test_disabled_liberation_does_not_block_attacks(self):
        policy = YangYangSpPolicy()
        state = State('feather', False, '', True)
        policy.choose(state, 0, can_r=False)
        self.assertEqual(policy.choose(state, 1, can_r=False), 'normal')
        self.assertFalse(policy.r_used)

    def test_echo_only_once_in_safe_window(self):
        policy = YangYangSpPolicy()
        normal = State('sword')
        policy.choose(normal, 0, can_q=True)
        self.assertEqual(policy.choose(normal, .15, can_q=True), 'Q')
        self.assertEqual(policy.choose(normal, 1, can_q=True), 'normal')

    def test_switch_requires_visual_end_not_merely_full_concerto(self):
        policy = YangYangSpPolicy()
        ready = State('feather', True)
        policy.choose(ready, 0, con_full=True)
        self.assertEqual(policy.choose(ready, .15, con_full=True), 'hold')
        policy.choose(State('feather'), 2, con_full=True)
        policy.choose(State('feather'), 2.4, con_full=True)
        self.assertEqual(policy.choose(State('feather'), 2.5, con_full=True), 'switch')


if __name__ == '__main__':
    unittest.main()
