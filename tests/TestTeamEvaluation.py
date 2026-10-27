import importlib.util
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


source = Path(__file__).resolve().parents[1] / '.agents/skills/evaluate-team/scripts/evaluate_team.py'
spec = importlib.util.spec_from_file_location('evaluate_team', source)
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)


def box(text, x=100, y=100, width=100, height=30):
    return SimpleNamespace(name=text, x=x, y=y, width=width, height=height, confidence=0.99)


class TestAbyssMetrics(unittest.TestCase):
    def test_source_of_unregistered_dynamic_team_module(self):
        namespace = {'__name__': 'unregistered_team_module'}
        exec(compile('class Roccia:\n    def do_perform(self):\n        pass\n', 'team/Roccia.py', 'exec'), namespace)
        self.assertEqual(evaluation.character_source(namespace['Roccia']()), 'team/Roccia.py')

    def test_c6_build_with_stale_sub_dps_override_is_rejected(self):
        with self.assertRaisesRegex(AssertionError, 'loaded class reports SubDps'):
            evaluation.validate_team_roles([{'name': 'Roccia', 'role': 'SubDps'}], {'Roccia C6': True})
        evaluation.validate_team_roles([{'name': 'Roccia', 'role': 'MainDps'}], {'Roccia C6': True})

    def test_countdown_formats_from_hud(self):
        for text, expected in [('01:57:18', 117.18), ('01:43.46', 103.46), ('０２：００', 120), ('00:00:00', 0), ('1:02', 62)]:
            with self.subTest(text=text):
                self.assertEqual(evaluation.parse_remaining_time(text), expected)
        for text in ('18476/18476', '12:99', '01:02:345', 'score 01:25', '10.8'):
            with self.subTest(text=text):
                self.assertIsNone(evaluation.parse_remaining_time(text))

    def test_score_requires_a_result_label(self):
        self.assertIsNone(evaluation.read_final_score([box('705024113'), box('90')]))
        self.assertEqual(evaluation.read_final_score([box('本次积分'), box('12,345', x=220)]), 12345)
        self.assertEqual(evaluation.read_final_score([box('Final Score: 12,345')]), 12345)
        self.assertEqual(evaluation.read_final_score([box('积分'), box('0', y=145)]), 0)

    def test_best_score_and_ambiguous_scores_are_not_benchmarks(self):
        self.assertIsNone(evaluation.read_final_score([box('历史最高积分：99999')]))
        self.assertIsNone(evaluation.read_final_score([box('本次积分'), box('123', x=220), box('456', y=145)]))

    def test_current_team_score_has_priority_over_cumulative_total(self):
        self.assertEqual(evaluation.read_final_score([box('队伍得分'), box('5125', y=145),
                                                     box('当前总积分', y=350), box('10000', x=220, y=350)]), 5125)
        self.assertEqual(evaluation.read_final_score([box('Team Score'), box('△4717', y=145)]), 4717)
        self.assertIsNone(evaluation.read_final_score([box('队伍得分'), box('unreadable', y=145),
                                                      box('当前总积分', y=350), box('10000', x=220, y=350)]))

    def test_timer_ranking_requires_success_and_fresh_reading(self):
        self.assertTrue(evaluation.valid_result('remaining_time', 'success', 62.3, 0.5))
        self.assertFalse(evaluation.valid_result('remaining_time', 'ended', 62.3, 0.5))
        self.assertFalse(evaluation.valid_result('remaining_time', 'success', 62.3, 12.9))
        self.assertTrue(evaluation.valid_result('remaining_time', 'success', 62.3, 3.9, disappearance_gap=.6))
        self.assertFalse(evaluation.valid_result('remaining_time', 'success', 62.3, 3.9, disappearance_gap=3.5))
        self.assertFalse(evaluation.valid_result('remaining_time', 'success', None, 0.5))
        self.assertTrue(evaluation.valid_result('score', 'ended', 0, 12.9, 'NotInCombatException: ended'))
        self.assertFalse(evaluation.valid_result('score', 'ended', 5125, 0.5, 'CharDeadException: dead'))
        self.assertFalse(evaluation.valid_result('score', 'failure', 5125, 0.5))

    def test_summary_does_not_fabricate_missing_values(self):
        self.assertEqual(evaluation.summarize([]), {'count': 0})
        self.assertEqual(evaluation.summarize([123])['sample_stdev'], None)
        result = evaluation.summarize([100, 200, 300])
        self.assertEqual((result['mean'], result['median'], result['range']), (200, 200, 200))


class TestRecorder(unittest.TestCase):
    def test_idle_character_with_active_timer_fails_before_any_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            task = SimpleNamespace(frame='frame', in_liberation=False)
            recorder = evaluation.Recorder(task, Path(directory))
            recorder.start = 90
            recorder.last_input_at = 90
            recorder.last_timer_at = 99
            recorder.last_timer = 200
            recorder.rotation_char = 'Mortefi'
            try:
                with patch.object(evaluation.time, 'monotonic', return_value=100), patch.object(evaluation.cv2, 'imwrite') as capture:
                    with self.assertRaisesRegex(evaluation.CombatStallError, 'Mortefi sent no input'):
                        recorder.sample()
                capture.assert_called_once()
                self.assertEqual(recorder.stalls[0]['char'], 'Mortefi')
            finally:
                recorder.events.close()

    def test_failed_tuple_return_is_not_counted_as_a_cast(self):
        with tempfile.TemporaryDirectory() as directory:
            recorder = evaluation.Recorder(None, Path(directory))
            try:
                char = SimpleNamespace(name='support')
                self.assertEqual(recorder.action_wrapper(char, 'resonance', lambda: (False, 0, False))(), (False, 0, False))
                self.assertEqual(recorder.actions, {})
                recorder.action_wrapper(char, 'resonance', lambda: (True, 0.5, False))()
                self.assertEqual(recorder.actions['support.resonance'], 1)
            finally:
                recorder.events.close()

    def test_instrumentation_is_removed_after_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            char = SimpleNamespace(perform=lambda: None, switch_out=lambda: None,
                                   click_liberation=lambda: False, click_resonance=lambda: (False, 0, False), click_echo=lambda: False)
            task = SimpleNamespace(next_frame=lambda: None, chars=[char])
            before = dict(vars(char))
            original_frame = task.next_frame
            recorder = evaluation.Recorder(task, Path(directory))
            with self.assertRaises(RuntimeError):
                with ExitStack() as stack:
                    recorder.install(stack)
                    raise RuntimeError('interrupted combat')
            self.assertEqual(vars(char), before)
            self.assertIs(task.next_frame, original_frame)
            self.assertTrue(recorder.events.closed)

    def test_instrumentation_is_removed_after_completion_or_cancellation(self):
        for cancellation in (False, True):
            with self.subTest(cancellation=cancellation), tempfile.TemporaryDirectory() as directory:
                char = SimpleNamespace(perform=lambda: None, switch_out=lambda: None,
                                       click_liberation=lambda: False, click_resonance=lambda: (False, 0, False), click_echo=lambda: False)
                task = SimpleNamespace(next_frame=lambda: None, chars=[char], click=lambda: None)
                original_char, original_task = dict(vars(char)), dict(vars(task))
                recorder = evaluation.Recorder(task, Path(directory))
                try:
                    with ExitStack() as stack:
                        recorder.install(stack)
                        if cancellation:
                            raise KeyboardInterrupt('cancelled evaluation')
                except KeyboardInterrupt:
                    pass
                self.assertEqual(vars(char), original_char)
                self.assertEqual(vars(task), original_task)
                self.assertTrue(recorder.events.closed)

    def test_missing_or_impossible_timer_keeps_last_good_frame(self):
        with tempfile.TemporaryDirectory() as directory:
            task = SimpleNamespace(frame=SimpleNamespace(copy=lambda: 'last-good-frame'))
            recorder = evaluation.Recorder(task, Path(directory))
            try:
                with patch.object(evaluation, 'read_remaining_time', side_effect=[117.18, None, 777]), patch.object(evaluation, 'SAMPLE_INTERVAL', 0):
                    recorder.sample()
                    recorder.sample()
                    recorder.sample()
                self.assertEqual(recorder.last_timer, 117.18)
                self.assertEqual(recorder.last_timer_frame, 'last-good-frame')
                self.assertEqual(recorder.timer_anomalies, 1)
            finally:
                recorder.events.close()

    def test_success_seen_inside_rotation_freezes_last_pre_success_timer(self):
        with tempfile.TemporaryDirectory() as directory:
            task = SimpleNamespace(frame=SimpleNamespace(copy=lambda: 'frame'),
                                   box_of_screen=lambda *args: None,
                                   ocr=lambda **kwargs: [box('挑战成功')])
            recorder = evaluation.Recorder(task, Path(directory))
            try:
                with patch.object(evaluation, 'read_remaining_time', side_effect=[62.3, None, 0]) as read, patch.object(evaluation, 'METRIC', 'remaining_time'), patch.object(evaluation, 'SAMPLE_INTERVAL', 0):
                    recorder.sample()
                    recorder.sample()
                    recorder.sample()
                self.assertIsNotNone(recorder.success_at)
                self.assertEqual(recorder.last_timer, 62.3)
                self.assertEqual(read.call_count, 2)
            finally:
                recorder.events.close()


if __name__ == '__main__':
    unittest.main()
