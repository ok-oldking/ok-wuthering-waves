import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

import numpy as np

from src.char.Douling import Douling


class TestDoulingGuaxiang(unittest.TestCase):
    def make_char(self):
        char = Douling.__new__(Douling)
        char.task = SimpleNamespace(
            frame=np.zeros((4, 4, 3), dtype=np.uint8),
            in_team=Mock(return_value=(True, 1, 3)),
            screenshot=Mock(),
            debug=False,
            check_combat=Mock(),
        )
        char.logger = Mock()
        char._waiting_for_guaxiang = False
        char.clock = [0.0]
        timer = patch('src.char.Douling.time.monotonic', side_effect=lambda: char.clock[0])
        timer.start()
        self.addCleanup(timer.stop)
        char.sleep = Mock(side_effect=lambda duration: char.clock.__setitem__(0, char.clock[0] + duration))
        char.normal_attack = Mock()
        return char

    def test_entry_recognition_runs_once_for_each_segment(self):
        for segment in (1, 2):
            with self.subTest(segment=segment):
                char = self.make_char()
                char._segment = segment
                char.recognize_guaxiang = Mock()
                branch = Mock()
                setattr(char, f'_do_segment{segment}', branch)

                char.do_perform()

                char.recognize_guaxiang.assert_called_once_with('entry')
                branch.assert_called_once_with()

    def test_gate_attacks_until_four_gua_and_then_returns(self):
        char = self.make_char()
        char.task.next_frame = Mock(side_effect=[char.task.frame] * 4)
        char.recognize_guaxiang = Mock(
            side_effect=[[], ['蓝'], None, ['黄', '蓝', '蓝', '蓝']])
        char.normal_attack = Mock()

        self.assertTrue(char._normal_attack_until_four_guaxiang())

        self.assertEqual(char.normal_attack.call_count, 1)
        self.assertEqual(char.sleep.call_count, 3)
        self.assertAlmostEqual(char.clock[0], .3)
        self.assertEqual(char.recognize_guaxiang.call_args_list,
                         [call('before_heavy')] * 4)
        self.assertFalse(char._waiting_for_guaxiang)

    def test_capture_failure_does_not_accept_stale_four_gua(self):
        char = self.make_char()
        char.task.next_frame = Mock(side_effect=[None, char.task.frame])
        char.recognize_guaxiang = Mock(return_value=['蓝'] * 4)
        char.normal_attack = Mock()

        self.assertTrue(char._normal_attack_until_four_guaxiang())

        char.normal_attack.assert_called_once_with()
        char.recognize_guaxiang.assert_called_once_with('before_heavy')

    def test_four_gua_returns_before_next_attack_is_due(self):
        for ready_at in (0, .1):
            with self.subTest(ready_at=ready_at):
                char = self.make_char()
                char.task.next_frame = Mock(return_value=char.task.frame)
                char.recognize_guaxiang = Mock(
                    side_effect=lambda _: ['蓝'] * 4 if char.clock[0] >= ready_at else [])
                self.assertTrue(char._normal_attack_until_four_guaxiang())
                self.assertAlmostEqual(char.clock[0], ready_at)
                self.assertEqual(char.normal_attack.call_count, int(ready_at > 0))

    def test_slow_work_does_not_catch_up_attacks_or_polls(self):
        for stage in ('frame', 'recognition', 'attack'):
            for delay in (.04, .45):
                with self.subTest(stage=stage, delay=delay):
                    char = self.make_char()
                    polls, attacks = [], []

                    def advance():
                        char.clock[0] += delay

                    def refresh():
                        polls.append(char.clock[0])
                        if stage == 'frame':
                            advance()
                        return char.task.frame

                    def recognize(_):
                        if stage == 'recognition':
                            advance()
                        return None

                    def attack():
                        attacks.append(char.clock[0])
                        if stage == 'attack':
                            advance()

                    char.task.next_frame = Mock(side_effect=refresh)
                    char.recognize_guaxiang = Mock(side_effect=recognize)
                    char.normal_attack = Mock(side_effect=attack)
                    self.assertFalse(char._normal_attack_until_four_guaxiang())
                    self.assertGreater(len(attacks), 1)
                    self.assertTrue(all(b - a >= .3 - 1e-9 for a, b in zip(attacks, attacks[1:])))
                    self.assertTrue(all(b - a >= .1 - 1e-9 for a, b in zip(polls, polls[1:])))
                    self.assertTrue(all(t < 3 for t in attacks))
                    self.assertLessEqual(len(polls), 30)
                    if delay == .04 and stage != 'attack':
                        self.assertAlmostEqual(polls[1], .1)

    def test_sleep_is_clipped_to_deadline(self):
        char = self.make_char()
        char.GUAXIANG_WAIT_TIMEOUT = .05
        char.task.next_frame = Mock(return_value=char.task.frame)
        char.recognize_guaxiang = Mock(return_value=[])
        self.assertFalse(char._normal_attack_until_four_guaxiang())
        char.sleep.assert_called_once_with(.05)
        self.assertAlmostEqual(char.clock[0], .05)

    def test_stop_during_poll_sleep_propagates(self):
        from ok.task.exceptions import TaskDisabledException
        char = self.make_char()
        char.task.next_frame = Mock(return_value=char.task.frame)
        char.recognize_guaxiang = Mock(return_value=[])
        char.sleep.side_effect = TaskDisabledException()
        with self.assertRaises(TaskDisabledException):
            char._normal_attack_until_four_guaxiang()
        self.assertFalse(char._waiting_for_guaxiang)

    def test_gate_propagates_combat_end_and_clears_waiting_state(self):
        char = self.make_char()
        char.task.next_frame = Mock(return_value=char.task.frame)
        char.task.check_combat.side_effect = RuntimeError('combat ended')
        char.recognize_guaxiang = Mock()
        char.normal_attack = Mock()

        with self.assertRaisesRegex(RuntimeError, 'combat ended'):
            char._normal_attack_until_four_guaxiang()

        char.recognize_guaxiang.assert_not_called()
        char.normal_attack.assert_not_called()
        self.assertFalse(char._waiting_for_guaxiang)

    def test_segment_two_gates_before_heavy_and_preserves_followup_order(self):
        char = self.make_char()
        events = []
        char.check_combat = lambda: events.append('check_combat')
        char.task.jump = lambda after_sleep: events.append(('jump', after_sleep))
        char.sleep = lambda duration: events.append(('sleep', duration))
        char.flying = lambda: False
        char.wait_down = lambda: events.append('wait_down')
        char._normal_attack_until_four_guaxiang = lambda: events.append('gua_gate') or True
        char._heavy_attack_hold = lambda duration: events.append(('heavy', duration))
        char.click_echo = lambda time_out: events.append(('echo', time_out))
        char.click_liberation = lambda: events.append('liberation')
        char.switch_next_char = lambda: events.append('switch')

        char._do_segment2()

        self.assertEqual(events, [
            'check_combat',
            ('jump', .01),
            ('sleep', .05),
            'check_combat',
            'wait_down',
            'check_combat',
            'gua_gate',
            ('heavy', 2.5),
            ('echo', 0),
            'liberation',
            'switch',
        ])

    def test_timeout_switches_without_followup_skills(self):
        for sequence, has_frame in (([], True), (None, True), (['蓝'] * 4, False)):
            with self.subTest(sequence=sequence, has_frame=has_frame):
                char = self.make_char()
                char._segment = 2
                char.task.jump = Mock()
                char.sleep = Mock(side_effect=lambda duration: clock.__setitem__(0, clock[0] + 1.0))
                char.flying = Mock(return_value=False)
                char.wait_down = Mock()
                char.task.next_frame = Mock(return_value=char.task.frame if has_frame else None)
                char.recognize_guaxiang = Mock(return_value=sequence)
                char._heavy_attack_hold = Mock()
                char.click_echo = Mock()
                char.click_liberation = Mock()
                char.switch_next_char = Mock()
                clock = [0.0]

                char.normal_attack = Mock()
                with patch('src.char.Douling.time.monotonic', side_effect=lambda: clock[0]):
                    char._do_segment2()

                self.assertEqual(char.task.next_frame.call_count, 3)
                char._heavy_attack_hold.assert_not_called()
                char.click_echo.assert_not_called()
                char.click_liberation.assert_not_called()
                char.switch_next_char.assert_called_once_with()
                self.assertEqual(char._segment, 1)
                self.assertFalse(char._waiting_for_guaxiang)
                char.logger.warning.assert_called_once()
                self.assertIn('reason=timeout', char.logger.warning.call_args.args[0])
                if not has_frame:
                    char.recognize_guaxiang.assert_not_called()

    def test_attempt_limit_bounds_recognition_without_screenshots(self):
        char = self.make_char()
        char.task.next_frame = Mock(return_value=char.task.frame)
        char.normal_attack = Mock()
        detector = Mock(return_value=SimpleNamespace(sequence=None, reason='low_confidence'))
        with patch('src.char.Douling.detect_guaxiang', detector):
            self.assertFalse(char._normal_attack_until_four_guaxiang())
        self.assertEqual(detector.call_count, 30)
        char.task.screenshot.assert_not_called()
        self.assertLessEqual(char.normal_attack.call_count, 10)
        self.assertFalse(char._waiting_for_guaxiang)
        char.logger.warning.assert_called_once()
        self.assertIn('reason=max_attempts', char.logger.warning.call_args.args[0])

    def test_deadline_checked_after_frame_and_recognition(self):
        for stage in ('frame', 'recognition'):
            for elapsed in (2.999, 3.0, 3.1):
                with self.subTest(stage=stage, elapsed=elapsed):
                    char = self.make_char()
                    clock = [0.0]

                    def refresh():
                        if stage == 'frame':
                            clock[0] = elapsed
                        return char.task.frame

                    def recognize(_):
                        if stage == 'recognition':
                            clock[0] = elapsed
                        return ['蓝'] * 4

                    char.task.next_frame = Mock(side_effect=refresh)
                    char.recognize_guaxiang = Mock(side_effect=recognize)
                    char.normal_attack = Mock()
                    with patch('src.char.Douling.time.monotonic', side_effect=lambda: clock[0]):
                        self.assertEqual(char._normal_attack_until_four_guaxiang(), elapsed < 3)
                    char.normal_attack.assert_not_called()
                    self.assertFalse(char._waiting_for_guaxiang)
                    if stage == 'frame' and elapsed >= 3:
                        char.recognize_guaxiang.assert_not_called()

    def test_task_stop_propagates_and_clears_waiting_state(self):
        from ok.task.exceptions import TaskDisabledException
        char = self.make_char()
        char.task.next_frame = Mock(side_effect=TaskDisabledException())
        char.recognize_guaxiang = Mock()
        with self.assertRaises(TaskDisabledException):
            char._normal_attack_until_four_guaxiang()
        char.recognize_guaxiang.assert_not_called()
        self.assertFalse(char._waiting_for_guaxiang)

    def test_entry_recognition_uses_frame_copy_and_logs_without_screenshots(self):
        char = self.make_char()
        detector = Mock(return_value=SimpleNamespace(
            sequence=['黄', '蓝'],
            reason='ok',
            region=None,
            detections=[],
        ))

        with patch.dict(Douling.recognize_guaxiang.__globals__,
                        {'detect_guaxiang': detector}):
            self.assertEqual(char.recognize_guaxiang('entry'), ['黄', '蓝'])

        detector.assert_called_once()
        self.assertIsNot(detector.call_args.args[0], char.task.frame)
        np.testing.assert_array_equal(detector.call_args.args[0], char.task.frame)
        char.task.screenshot.assert_not_called()
        char.logger.info.assert_called_once_with(
            '[DoulingRecognition] point=entry count=2 sequence=黄,蓝')


if __name__ == '__main__':
    unittest.main()
