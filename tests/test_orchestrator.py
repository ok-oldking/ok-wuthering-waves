"""Test the actual queue and pipeline, replacing game operations with doubles."""
import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Stopped(Exception):
    pass


with patch.dict('sys.modules', {'ok': SimpleNamespace(TaskDisabledException=Stopped,
        Logger=SimpleNamespace(get_logger=lambda name: SimpleNamespace(info=lambda *a: None, warning=lambda *a: None)))}):
    pipeline = load('steps', 'src/task/StepPipeline.py')
plan = load('plan', 'src/task/OrchestratorPlan.py')
control = load('control', 'src/task/OrchestratorControl.py')


class NativeDouble:
    def __init__(self):
        self.config = {plan.PLAN_KEY: [], 'Nightmare Nest Mode': 'Daily'}
        self.events = []
        self.executor = SimpleNamespace(_frame=None)
        self.log_info = self.log_error = self.info_set = lambda *a, **kw: None
        self.screenshot = lambda *a, **kw: None


tree = ast.parse((ROOT / 'src/task/OrchestratorTask.py').read_text(encoding='utf-8'))
node = next(n for n in tree.body if isinstance(n, ast.ClassDef))
namespace = {'StepPipeline': pipeline.StepPipeline, 'DailyTask': NativeDouble,
             'PLAN_KEY': plan.PLAN_KEY, 'CONTROL_STEPS': plan.CONTROL_STEPS,
             'validate_plan': plan.validate_plan, 'boss_run_limit': plan.boss_run_limit,
             'task_key': plan.task_key, 'entry_id': plan.entry_id,
             'wait_seconds': lambda task, seconds: task.events.append(('Wait', seconds)) if seconds else None,
             'NightmareNestTask': type('Nest', (), {}), 'FarmEchoTask': type('Boss', (), {}),
             'GardenTask': type('Garden', (), {}), 'MergeEchoTask': type('Merge', (), {}),
             'WWOneTimeTask': SimpleNamespace(run=lambda task: None)}
exec(compile(ast.Module(body=[node], type_ignores=[]), '<orchestrator>', 'exec'), namespace)
Task = namespace['OrchestratorTask']


class OrchestratorTests(unittest.TestCase):
    def task(self, selected):
        task = Task.__new__(Task)
        NativeDouble.__init__(task)
        task.config[plan.PLAN_KEY] = selected
        for key, method in [('FarmStamina', '_step_stamina'), ('ClaimDaily', 'claim_daily'),
                            ('ClaimMail', 'claim_mail'), ('ClaimBattlePass', 'claim_battle_pass'),
                            ('WeeklyGarden', '_step_garden'), ('MergeEcho', '_step_merge'),
                            ('Farm4CEcho', '_step_boss')]:
            setattr(task, method, lambda k=key: task.events.append(k))
        task._step_nightmare = lambda mode: task.events.append('NightmareNest')
        task._prepare_gameplay = lambda: task.events.append('Login')
        task._open_game = lambda: task.events.append('OpenGame')
        task._close_game = lambda: task.events.append('CloseGame')
        return task

    def test_subset_runs_exact_order_without_hidden_tasks(self):
        task = self.task(['ClaimMail', 'ClaimDaily', 'FarmStamina'])
        task.run()
        self.assertEqual(task.events, ['Login', 'ClaimMail', 'ClaimDaily', 'FarmStamina'])

    def test_removed_claim_never_runs(self):
        task = self.task(['FarmStamina'])
        task.run()
        self.assertEqual(task.events, ['Login', 'FarmStamina'])

    def test_controls_repeat_and_no_implicit_login(self):
        first, second = plan.new_entry('Wait'), plan.new_entry('Wait')
        second['seconds'] = 180
        task = self.task([plan.new_entry('CloseGame'), first, second])
        task.run()
        self.assertEqual(task.events, ['CloseGame', ('Wait', 30), ('Wait', 180)])

    def test_failed_login_still_runs_cleanup(self):
        task = self.task(['ClaimMail', plan.new_entry('CloseGame')])
        task._prepare_gameplay = lambda: (_ for _ in ()).throw(RuntimeError('login'))
        with self.assertRaisesRegex(RuntimeError, 'Login'):
            task.run()
        self.assertEqual(task.events, ['CloseGame'])
        self.assertEqual(task.step_status['ClaimMail'], 'skipped')

    def test_required_failure_remains_failure_after_cleanup(self):
        task = self.task(['FarmStamina', plan.new_entry('CloseGame')])
        task._step_stamina = lambda: (_ for _ in ()).throw(RuntimeError('stamina'))
        with self.assertRaisesRegex(RuntimeError, 'FarmStamina'):
            task.run()
        self.assertEqual(task.events, ['Login', 'CloseGame'])

    def test_optional_failure_remains_visible_but_continues(self):
        task = self.task(['MergeEcho', 'ClaimMail'])
        task._step_merge = lambda: (_ for _ in ()).throw(RuntimeError('merge'))
        task.run()
        self.assertEqual(task.step_status['MergeEcho'], 'failed')
        self.assertIn('ClaimMail', task.events)

    def test_stop_propagates_without_later_tasks(self):
        task = self.task(['ClaimMail', 'ClaimDaily'])
        task.claim_mail = lambda: (_ for _ in ()).throw(Stopped())
        with self.assertRaises(Stopped):
            task.run()
        self.assertNotIn('ClaimDaily', task.events)

    def test_exit_last_and_no_hidden_game_close(self):
        signal = SimpleNamespace(emit=lambda: calls.append('quit'))
        calls = []
        task = self.task([plan.new_entry('ExitScript')])
        with patch.dict('sys.modules', {'ok.core.events': SimpleNamespace(communicate=SimpleNamespace(quit=signal))}):
            task.run()
        self.assertEqual(calls, ['quit'])
        self.assertEqual(task.events, [])
        with self.assertRaises(ValueError):
            plan.validate_plan([plan.new_entry('ExitScript'), 'ClaimMail'], execution=True)

    def test_invalid_plan_never_starts_game(self):
        for selected in ([], None, ['Unknown'], ['ClaimDaily', 'ClaimDaily'], [3]):
            task = self.task(selected)
            with self.subTest(selected=selected), self.assertRaises(ValueError):
                task.run()
            self.assertEqual(task.events, [])

    def test_wait_bounds_and_control_identity(self):
        for seconds in (-1, True, 1.5, 86401, None):
            wait = plan.new_entry('Wait')
            wait['seconds'] = seconds
            with self.subTest(seconds=seconds), self.assertRaises(ValueError):
                plan.validate_plan([wait])
        wait = plan.new_entry('Wait')
        with self.assertRaises(ValueError):
            plan.validate_plan([wait, wait])
        self.assertNotEqual(plan.new_entry('Wait')['id'], wait['id'])

    def test_drag_transaction_reorders_and_removes(self):
        selected = ['ClaimMail', 'ClaimDaily']
        added = plan.transfer_plan(selected, 'FarmStamina', 'library', 'queue', 1)
        self.assertEqual(added, ['ClaimMail', 'FarmStamina', 'ClaimDaily'])
        self.assertEqual(selected, ['ClaimMail', 'ClaimDaily'])
        self.assertEqual(plan.transfer_plan(added, 'ClaimDaily', 'queue', 'queue', 0),
                         ['ClaimDaily', 'ClaimMail', 'FarmStamina'])
        self.assertEqual(plan.transfer_plan(added, 'FarmStamina', 'queue', 'library'), selected)

    def test_stale_drag_duplicate_and_bad_index_rejected(self):
        for key, source, target, index in [('Unknown', 'library', 'queue', 0),
                ('ClaimMail', 'library', 'queue', 0), ('ClaimDaily', 'queue', 'queue', 0),
                ('ClaimMail', 'queue', 'queue', True), ('ClaimMail', 'queue', 'queue', 8)]:
            with self.subTest(key=key, index=index), self.assertRaises(ValueError):
                plan.transfer_plan(['ClaimMail'], key, source, target, index)

    def test_busy_gameplay_blocks_but_trigger_poll_does_not(self):
        trigger = SimpleNamespace()
        executor = SimpleNamespace(current_task=trigger, trigger_tasks=[trigger], onetime_tasks=[])
        controller = SimpleNamespace(starting=False)
        self.assertFalse(plan.executor_busy(executor, controller))
        executor.current_task = SimpleNamespace()
        self.assertTrue(plan.executor_busy(executor, controller))
        executor.current_task = trigger
        controller.starting = True
        self.assertTrue(plan.executor_busy(executor, controller))

    def test_boss_bounds_strict(self):
        for count in (0, 101, True, '3'):
            with self.assertRaises(ValueError):
                plan.boss_run_limit(count)
        self.assertEqual(plan.boss_run_limit(100), 100)


if __name__ == '__main__':
    unittest.main()
