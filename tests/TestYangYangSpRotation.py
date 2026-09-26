import unittest
from unittest.mock import patch

from src.char.YangYangSp import YangYangSp
from src.char.YangYangSpVision import YangYangSpState as State


class RotationTask:
    skip_combat_check = False
    use_liberation = True

    def __init__(self, fail_after=None):
        self.now = 100.0
        self.actions = []
        self.fail_after = fail_after

    def mouse_down(self):
        self.actions.append(('down', self.now))

    def mouse_up(self):
        self.actions.append(('up', self.now))

    def sleep(self, duration):
        self.now += duration
        if self.fail_after is not None and self.now >= self.fail_after and not self.skip_combat_check:
            raise RuntimeError('combat ended')

    def next_frame(self):
        pass


class RotationChar(YangYangSp):
    def __init__(self, task, states, q=False, con=False):
        super().__init__(task, 0)
        self.states = states
        self.q = q
        self.con = con

    def observe_state(self):
        return self.states(self.task.now - 100)

    def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
        return self.task.now - start

    def echo_available(self):
        return self.q

    def is_con_full(self):
        return self.con

    def check_combat(self):
        pass

    def click(self, **kwargs):
        self.task.actions.append(('normal', self.task.now))

    def send_resonance_key(self, **kwargs):
        self.task.actions.append(('E', self.task.now))

    def record_resonance_use(self):
        pass

    def click_liberation(self, **kwargs):
        self.task.actions.append(('R', self.task.now))
        return True

    def click_echo(self, **kwargs):
        self.task.actions.append(('Q', self.task.now))
        return True

    def switch_next_char(self):
        self.task.actions.append(('switch', self.task.now))


class TestYangYangSpRotation(unittest.TestCase):
    def run_rotation(self, char):
        with patch('src.char.YangYangSp.time.time', side_effect=lambda: char.task.now), \
                patch('src.char.YangYangSp.time.monotonic', side_effect=lambda: char.task.now):
            char.do_perform()

    def test_no_periodic_release_during_multistage_heavy(self):
        def states(t):
            if t < 1:
                return State('feather', True, 'feather', True)
            if t < 2:
                return State('air', False, 'feather', True)
            if t < 3:
                return State('followup', False, 'feather', True)
            return State('feather')
        task = RotationTask()
        self.run_rotation(RotationChar(task, states, con=True))
        self.assertEqual([a for a, _ in task.actions], ['down', 'up', 'up', 'switch'])
        self.assertGreaterEqual(task.actions[1][1] - task.actions[0][1], 3.0)

    def test_e_and_r_never_interrupt_followup(self):
        task = RotationTask()
        def states(t):
            if t < 2:
                return State('followup', False, 'feather', True)
            return State('feather', False, 'feather', True)
        self.run_rotation(RotationChar(task, states))
        actions = [a for a, _ in task.actions]
        first_up = actions.index('up')
        self.assertNotIn('E', actions[:first_up])
        self.assertNotIn('R', actions[:first_up])
        self.assertEqual(actions.count('E'), 2)
        self.assertEqual(actions.count('R'), 1)
        self.assertLess(task.now, 121)

    def test_normal_only_state_clicks_and_never_holds_or_e(self):
        task = RotationTask()
        self.run_rotation(RotationChar(task, lambda t: State('sword'), q=True))
        actions = [a for a, _ in task.actions]
        self.assertNotIn('down', actions)
        self.assertNotIn('E', actions)
        self.assertIn('normal', actions)
        self.assertEqual(actions.count('Q'), 1)
        self.assertEqual(actions[-2:], ['up', 'switch'])

    def test_combat_exit_releases_held_mouse_without_switch(self):
        task = RotationTask(fail_after=101)
        char = RotationChar(task, lambda t: State('azure', True))
        with self.assertRaisesRegex(RuntimeError, 'combat ended'):
            self.run_rotation(char)
        self.assertEqual([a for a, _ in task.actions], ['down', 'up'])
        self.assertFalse(char.left_held)

    def test_observation_exception_releases_mouse(self):
        task = RotationTask()
        def states(t):
            if t > .4:
                raise ValueError('capture failed')
            return State('feather', True)
        char = RotationChar(task, states)
        with self.assertRaisesRegex(ValueError, 'capture failed'):
            self.run_rotation(char)
        self.assertEqual([a for a, _ in task.actions], ['down', 'up'])
        self.assertFalse(char.left_held)

    def test_unknown_state_is_bounded_without_skill_guessing(self):
        task = RotationTask()
        self.run_rotation(RotationChar(task, lambda t: State()))
        actions = [a for a, _ in task.actions]
        self.assertNotIn('E', actions)
        self.assertNotIn('R', actions)
        self.assertNotIn('down', actions)
        self.assertLess(task.now, 121)


if __name__ == '__main__':
    unittest.main()
