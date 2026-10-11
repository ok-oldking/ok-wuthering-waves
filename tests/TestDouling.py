import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

from ok.task.exceptions import TaskDisabledException
from src.char.Douling import Douling
from src.task.BaseCombatTask import BaseCombatTask, NotInCombatException
from src.utils.douling_energy import recognize_energy
from tests.TestDoulingEnergy import SAMPLES as ENERGY_SAMPLES, read_image


class TestDouling(unittest.TestCase):
    def make_char(self, readings=None):
        clock, events = [0.0], []
        task = SimpleNamespace(frame=np.zeros((4, 4, 3), np.uint8), _in_combat=True,
                               in_team=Mock(return_value=(True, 1, 3)), check_combat=Mock(), jump=Mock())
        task.next_frame = Mock(side_effect=lambda: task.frame)
        task.mouse_down = Mock(side_effect=lambda: events.append(('down', clock[0])))
        task.mouse_up = Mock(side_effect=lambda: events.append(('up', clock[0])))
        char = Douling(task, 1)
        char.clock, char.events, char.logger = clock, events, Mock()
        char.sleep = Mock(side_effect=lambda duration: clock.__setitem__(0, clock[0] + duration))
        char.normal_attack = Mock(side_effect=lambda: events.append(('attack', clock[0])))
        char.flying, char.wait_down = Mock(return_value=False), Mock()
        char.click_echo = Mock(side_effect=lambda **kwargs: events.append(('echo', clock[0])))
        char.click_liberation = Mock(side_effect=lambda: events.append(('liberation', clock[0])))
        char.switch_next_char = Mock(side_effect=lambda: events.append(('switch', clock[0])))
        timer = patch('src.char.Douling.time.monotonic', side_effect=lambda: clock[0])
        timer.start()
        self.addCleanup(timer.stop)
        self.addCleanup(char._cancel_post_heavy_observation)
        if readings is not None:
            char.recognize_guaxiang = Mock(side_effect=readings)
        return char

    def test_entry_four_energy_states_and_same_copied_frame(self):
        for segment in (1, 2):
            for name, state in ENERGY_SAMPLES.items():
                with self.subTest(segment=segment, state=state):
                    char = self.make_char()
                    char._segment, char.task.frame = segment, read_image(name)
                    branch = Mock(side_effect=lambda: self.assertEqual(char._energy_state, state))
                    setattr(char, f'_do_segment{segment}', branch)
                    with patch('src.char.Douling.detect_guaxiang') as gua, \
                            patch('src.char.Douling.detect_energy', wraps=recognize_energy) as energy:
                        gua.return_value = SimpleNamespace(sequence=[], reason='ok')
                        char.do_perform()
                    branch.assert_called_once()
                    gua.assert_called_once()
                    energy.assert_called_once()
                    self.assertIs(gua.call_args.args[0], energy.call_args.args[0])
                    self.assertIsNot(gua.call_args.args[0], char.task.frame)
                    np.testing.assert_array_equal(gua.call_args.args[0], char.task.frame)
                    char.task.next_frame.assert_not_called()
                    self.assertEqual(char.logger.info.call_count, 2)

    def test_hidden_hud_and_recognition_failures_clear_energy(self):
        for team in ((False, -1, 1), (True, 0, 3)):
            char = self.make_char()
            char.task.frame, char.task.in_team.return_value = read_image('shaoyang'), team
            char._energy_state = 'both'
            char.recognize_guaxiang('entry', require_current_char=True)
            self.assertIsNone(char._energy_state)
            self.assertIn('status=uncertain', char.logger.info.call_args.args[0])
        for stage in ('in_team', 'detect_energy', 'detect_guaxiang'):
            with self.subTest(stage=stage):
                char = self.make_char()
                char.task.frame, char._energy_state = read_image('shaoyang'), 'both'
                target = patch.object(char.task, stage) if stage == 'in_team' else patch('src.char.Douling.' + stage)
                with target as failed:
                    failed.side_effect = RuntimeError('unavailable')
                    char.recognize_guaxiang('entry')
                self.assertEqual(char._energy_state, 'shaoyang' if stage == 'detect_guaxiang' else None)
                char.logger.warning.assert_called_once()

    def test_gate_polls_until_four_without_extra_attacks(self):
        for readings, attacks in (([['蓝'] * 4], 0), ([[], ['蓝'] * 4], 1),
                                   ([[], ['蓝'], None, ['蓝'] * 5, ['黄', '蓝', '蓝', '蓝']], 2)):
            with self.subTest(readings=readings):
                char = self.make_char()
                char.task.frame = read_image('shaoyin_and_shaoyang')
                with patch('src.char.Douling.detect_guaxiang', side_effect=[
                        SimpleNamespace(sequence=sequence, reason='ok') for sequence in readings]):
                    self.assertTrue(char._normal_attack_until_four_guaxiang())
                self.assertEqual(char._energy_state, 'both')
                self.assertEqual(char.normal_attack.call_count, attacks)
                self.assertEqual(char.task.next_frame.call_count, len(readings))
                self.assertAlmostEqual(char.clock[0], (len(readings) - 1) * .1)
                self.assertFalse(char._waiting_for_guaxiang)
                char.logger.info.assert_called_once()

    def test_failed_capture_rejects_stale_gua_and_energy(self):
        char = self.make_char([['蓝'] * 4])
        char.task.next_frame.side_effect = [None, char.task.frame]
        self.assertTrue(char._normal_attack_until_four_guaxiang())
        char.recognize_guaxiang.assert_called_once_with('before_heavy')
        char.normal_attack.assert_called_once()
        char = self.make_char()
        char._energy_state, char.GUAXIANG_MAX_ATTEMPTS = 'both', 1
        char.task.next_frame = Mock(return_value=None)
        with patch('src.char.Douling.detect_energy') as energy:
            self.assertFalse(char._normal_attack_until_four_guaxiang())
        energy.assert_not_called()
        self.assertIsNone(char._energy_state)

    def test_gate_limits_and_deadlines(self):
        for reason in ('timeout', 'max_attempts'):
            char = self.make_char()
            char.recognize_guaxiang = Mock(return_value=None)
            char.GUAXIANG_WAIT_TIMEOUT = .05 if reason == 'timeout' else 3
            char.GUAXIANG_MAX_ATTEMPTS = 30 if reason == 'timeout' else 2
            self.assertFalse(char._normal_attack_until_four_guaxiang())
            self.assertIn('reason=' + reason, char.logger.warning.call_args.args[0])
            self.assertEqual(char.task.next_frame.call_count, 1 if reason == 'timeout' else 2)
            self.assertFalse(char._waiting_for_guaxiang)
            if reason == 'timeout':
                char.sleep.assert_called_once_with(.05)
        for stage in ('frame', 'recognition'):
            for elapsed in (2.999, 3.0):
                char = self.make_char()
                def slow(*args):
                    char.clock[0] = elapsed
                    return char.task.frame if stage == 'frame' else ['蓝'] * 4
                char.task.next_frame = Mock(side_effect=slow if stage == 'frame' else None,
                                            return_value=char.task.frame)
                char.recognize_guaxiang = Mock(side_effect=slow if stage == 'recognition' else None,
                                               return_value=['蓝'] * 4)
                self.assertEqual(char._normal_attack_until_four_guaxiang(), elapsed < 3)
                char.normal_attack.assert_not_called()

    def test_slow_capture_does_not_catch_up_attacks(self):
        char = self.make_char()
        def refresh():
            char.clock[0] += .45
            return char.task.frame
        char.task.next_frame.side_effect = refresh
        char.recognize_guaxiang = Mock(return_value=[])
        self.assertFalse(char._normal_attack_until_four_guaxiang())
        attacks = [at for event, at in char.events if event == 'attack']
        self.assertGreater(len(attacks), 1)
        self.assertTrue(all(b - a >= .3 for a, b in zip(attacks, attacks[1:])))
        self.assertTrue(all(at < 3 for at in attacks))

    def test_gate_interruptions_clear_waiting_state(self):
        for stage, error in (('next_frame', TaskDisabledException()), ('check_combat', NotInCombatException()),
                             ('sleep', TaskDisabledException())):
            char = self.make_char()
            char.recognize_guaxiang = Mock(return_value=[])
            getattr(char if stage == 'sleep' else char.task, stage).side_effect = error
            with self.assertRaises(type(error)):
                char._normal_attack_until_four_guaxiang()
            self.assertFalse(char._waiting_for_guaxiang)

    def test_second_segment_gates_heavy_and_preserves_followup_order(self):
        for sequence in (['黄', '蓝', '蓝', '蓝'], [], None):
            char = self.make_char()
            char.recognize_guaxiang = Mock(return_value=sequence)
            char.GUAXIANG_MAX_ATTEMPTS = 1
            char._heavy_attack_hold = lambda duration: char.events.append(('heavy', duration))
            char._do_segment2()
            expected = ['heavy', 'echo', 'liberation', 'switch'] if sequence else ['switch']
            self.assertEqual([event for event, _ in char.events], expected)
            if sequence:
                self.assertEqual(char.events[0][1], 2.5)
            self.assertEqual(char._segment, 1)

    def test_heavy_sampling_rejects_empty_frames_and_uses_one_copy(self):
        char = self.make_char()
        char.task.frame = read_image('shaoyin_and_shaoyang')
        char.task.next_frame.side_effect = [char.task.frame, None, char.task.frame]
        original = char.task.next_frame
        with patch('src.char.Douling.detect_guaxiang') as gua, \
                patch('src.char.Douling.detect_energy', wraps=recognize_energy) as energy:
            gua.return_value = SimpleNamespace(sequence=['蓝'] * 4, reason='ok')
            char._heavy_attack_hold(.4)
            self.assertEqual([event for event, _ in char.events], ['down', 'up'])
            self.assertAlmostEqual(char.events[-1][1], .4)
            self.assertIsNone(char._energy_state)
            char.clock[0] = .4
            char.task.next_frame()
        self.assertEqual(original.call_count, 3)
        self.assertEqual(energy.call_count, 2)
        for gua_call, energy_call in zip(gua.call_args_list, energy.call_args_list):
            self.assertIs(gua_call.args[0], energy_call.args[0])
        self.assertIsNone(char._energy_state)
        self.assertIn('reason=capture_failed', char.logger.info.call_args_list[1].args[0])

    def test_heavy_interruptions_release_mouse_and_retries_are_bounded(self):
        for stage, error in (('next_frame', TaskDisabledException()), ('sleep', TaskDisabledException()),
                             ('check_combat', NotInCombatException())):
            char = self.make_char()
            failure = getattr(char if stage == 'sleep' else char.task, stage)
            failure.side_effect = [None, error] if stage == 'check_combat' else error
            with self.assertRaises(type(error)):
                char._heavy_attack_hold(.4)
            self.assertEqual([event for event, _ in char.events], ['down', 'up'])
            self.assertIsNone(char._post_heavy_observer)
        for always in (False, True):
            char = self.make_char()
            char.flying.side_effect = lambda: always or char.task.mouse_down.call_count == 1
            char._heavy_attack_hold(.4)
            self.assertEqual(char.task.mouse_down.call_count, 3 if always else 2)
            self.assertEqual(char.task.mouse_up.call_count, char.task.mouse_down.call_count)
            if always:
                char.task.next_frame.assert_not_called()
            else:
                self.assertIn('attempt=2', char.logger.info.call_args.args[0])

    def test_recognition_errors_do_not_block_heavy_release(self):
        char = self.make_char()
        with patch('src.char.Douling.detect_energy', side_effect=RuntimeError()), \
                patch('src.char.Douling.detect_guaxiang', side_effect=RuntimeError()):
            char._heavy_attack_hold(.4)
        self.assertEqual([event for event, _ in char.events], ['down', 'up'])
        self.assertAlmostEqual(char.clock[0], .4)
        self.assertIsNone(char._energy_state)

    def test_followup_starts_immediately_and_observation_expires(self):
        char = self.make_char()
        char._normal_attack_until_four_guaxiang = Mock(return_value=True)
        original = char.task.next_frame
        char._do_segment2()
        self.assertEqual([event for event, _ in char.events], ['down', 'up', 'echo', 'liberation', 'switch'])
        np.testing.assert_allclose([at for _, at in char.events[1:]], [2.55] * 4)
        self.assertIsNotNone(char._post_heavy_observer)
        char._energy_state = 'both'
        char.logger.reset_mock()
        original.reset_mock()
        for offset in (.100001, .15, .300002, .400001):
            char.clock[0] = char.events[1][1] + offset
            char.task.next_frame()
            self.assertEqual(char._energy_state, 'both')
        self.assertEqual(original.call_count, 4)
        self.assertEqual(char.logger.info.call_count, 2)
        self.assertIs(char.task.next_frame, original)
        self.assertIsNone(char._post_heavy_observer)

    def test_observation_failures_restore_frame_method(self):
        for stage in ('capture', 'observer', 'combat_end', 'followup'):
            with self.subTest(stage=stage):
                char = self.make_char()
                original = char.task.next_frame
                if stage == 'followup':
                    char._normal_attack_until_four_guaxiang = Mock(return_value=True)
                    char.click_echo.side_effect = TaskDisabledException()
                    with self.assertRaises(TaskDisabledException):
                        char._do_segment2()
                    char.click_liberation.assert_not_called()
                else:
                    char._heavy_attack_hold(.4)
                    char._energy_state = 'both'
                    if stage == 'capture':
                        original.side_effect = TaskDisabledException()
                        with self.assertRaises(TaskDisabledException):
                            char.task.next_frame()
                    elif stage == 'observer':
                        with patch.object(char, '_record_heavy_recognition', side_effect=RuntimeError()):
                            self.assertIs(char.task.next_frame(), char.task.frame)
                    else:
                        char.task._in_combat = False
                        char.logger.reset_mock()
                        char.task.next_frame()
                        char.logger.info.assert_not_called()
                    self.assertEqual(char._energy_state, 'both')
                self.assertIs(char.task.next_frame, original)
                self.assertIsNone(char._post_heavy_observer)
                char.task.mouse_up.assert_called_once()

    def test_observation_restores_inherited_method_and_only_wraps_one_task(self):
        char = self.make_char()
        task, other = BaseCombatTask.__new__(BaseCombatTask), BaseCombatTask.__new__(BaseCombatTask)
        task._in_combat, task.in_team = True, Mock(return_value=(True, 1, 3))
        char.task = task
        original = task.next_frame.__func__
        executor = SimpleNamespace(frame=np.zeros((4, 4, 3), np.uint8), next_frame=Mock())
        executor.next_frame.return_value = executor.frame
        with patch.object(BaseCombatTask, 'executor', executor):
            char._start_post_heavy_observation(1, 0, 0, 0)
            self.assertIs(other.next_frame.__func__, original)
            other.next_frame()
            char.logger.info.assert_not_called()
            task.next_frame()
            char.logger.info.assert_called_once()
            char.clock[0] = .4
            task.next_frame()
        self.assertIs(task.next_frame.__func__, original)
        self.assertNotIn('next_frame', vars(task))


if __name__ == '__main__':
    unittest.main()
