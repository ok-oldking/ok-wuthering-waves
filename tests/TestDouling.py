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
        char.sleep = Mock()

        char._normal_attack_until_four_guaxiang()

        self.assertEqual(char.normal_attack.call_count, 3)
        self.assertEqual(char.sleep.call_args_list, [call(.3)] * 3)
        self.assertEqual(char.recognize_guaxiang.call_args_list,
                         [call('before_heavy')] * 4)
        self.assertFalse(char._waiting_for_guaxiang)

    def test_capture_failure_does_not_accept_stale_four_gua(self):
        char = self.make_char()
        char.task.next_frame = Mock(side_effect=[None, char.task.frame])
        char.recognize_guaxiang = Mock(return_value=['蓝'] * 4)
        char._tap_normal = Mock()

        char._normal_attack_until_four_guaxiang()

        char._tap_normal.assert_called_once_with()
        char.recognize_guaxiang.assert_called_once_with('before_heavy')

    def test_gate_propagates_combat_end_and_clears_waiting_state(self):
        char = self.make_char()
        char.task.next_frame = Mock(return_value=char.task.frame)
        char.task.check_combat.side_effect = RuntimeError('combat ended')
        char.recognize_guaxiang = Mock()
        char._tap_normal = Mock()

        with self.assertRaisesRegex(RuntimeError, 'combat ended'):
            char._normal_attack_until_four_guaxiang()

        char.recognize_guaxiang.assert_not_called()
        char._tap_normal.assert_not_called()
        self.assertFalse(char._waiting_for_guaxiang)

    def test_segment_two_gates_before_heavy_and_preserves_followup_order(self):
        char = self.make_char()
        events = []
        char.check_combat = lambda: events.append('check_combat')
        char.task.jump = lambda after_sleep: events.append(('jump', after_sleep))
        char.sleep = lambda duration: events.append(('sleep', duration))
        char.flying = lambda: False
        char.wait_down = lambda: events.append('wait_down')
        char._normal_attack_until_four_guaxiang = lambda: events.append('gua_gate')
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

    def test_recognition_logs_and_screenshots_the_same_frame(self):
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
        screenshot = char.task.screenshot.call_args
        self.assertIs(screenshot.kwargs['frame'], detector.call_args.args[0])
        self.assertFalse(screenshot.kwargs['show_box'])
        self.assertTrue(screenshot.args[0].startswith('guaxiang/entry_'))
        self.assertIn('point=entry', char.logger.info.call_args.args[0])


if __name__ == '__main__':
    unittest.main()
