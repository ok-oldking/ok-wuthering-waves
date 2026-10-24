"""Safe selected-process cleanup and capture-independent waits."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('controls',
    Path(__file__).resolve().parents[1] / 'src/task/OrchestratorControl.py')
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)


class Stopped(Exception):
    pass


class Gone(Exception):
    pass


class Timeout(Exception):
    pass


class ControlTests(unittest.TestCase):
    def clock_task(self, pause_calls=()):
        state = SimpleNamespace(now=0.0, calls=0)
        task = SimpleNamespace(enabled=True, paused=False, executor=SimpleNamespace(paused=False))
        def wait(delay):
            state.calls += 1
            state.now += delay
            task.paused = state.calls in pause_calls
        task.executor.exit_event = SimpleNamespace(is_set=lambda: False, wait=wait)
        return task, state

    def test_wait_with_no_game_frame(self):
        task, state = self.clock_task()
        with patch.dict('sys.modules', {'ok': SimpleNamespace(TaskDisabledException=Stopped)}):
            control.wait_seconds(task, 0, clock=lambda: state.now)
            self.assertEqual(state.calls, 0)
            control.wait_seconds(task, .25, clock=lambda: state.now)
        self.assertGreaterEqual(state.now, .25)

    def test_pause_freezes_wait_budget(self):
        task, state = self.clock_task(pause_calls=(1, 2, 3, 4, 5))
        with patch.dict('sys.modules', {'ok': SimpleNamespace(TaskDisabledException=Stopped)}):
            control.wait_seconds(task, .3, clock=lambda: state.now)
        self.assertGreaterEqual(state.now, .8)

    def test_stop_and_shutdown_propagate(self):
        for shutdown in (False, True):
            task, state = self.clock_task()
            if shutdown:
                task.executor.exit_event.is_set = lambda: True
            else:
                task.enabled = False
            with patch.dict('sys.modules', {'ok': SimpleNamespace(TaskDisabledException=Stopped)}), self.assertRaises(Stopped):
                control.wait_seconds(task, 60, clock=lambda: state.now)

    def game(self, exe='C:/Game/Client-Win64-Shipping.exe', actual=None, timeout=False, gone=False):
        calls = []
        process = SimpleNamespace(create_time=lambda: 100, exe=lambda: actual or exe, is_running=lambda: True,
            terminate=lambda: calls.append('terminate'), wait=lambda **kw: calls.append('wait'))
        if timeout:
            process.wait = lambda **kw: (_ for _ in ()).throw(Timeout())
        manager = SimpleNamespace(hwnd_window=SimpleNamespace(hwnd=12, exe_full_path=exe),
                                  do_refresh=lambda value: calls.append('refresh'))
        proc = (lambda pid: (_ for _ in ()).throw(Gone())) if gone else (lambda pid: process)
        modules = {'psutil': SimpleNamespace(Process=proc, NoSuchProcess=Gone, TimeoutExpired=Timeout,
                                            process_iter=lambda attrs: []),
                   'win32process': SimpleNamespace(GetWindowThreadProcessId=lambda hwnd: (1, 23))}
        return manager, calls, modules

    def test_close_only_selected_process_and_wait_for_exit(self):
        manager, calls, modules = self.game()
        with patch.dict('sys.modules', modules):
            control.close_selected_game(manager)
        self.assertEqual(calls, ['terminate', 'wait', 'refresh'])

    def test_wrong_exe_or_changed_path_never_killed(self):
        for exe, actual in [('C:/Other.exe', None),
                            ('C:/Game/Client-Win64-Shipping.exe', 'C:/Other/Client-Win64-Shipping.exe')]:
            manager, calls, modules = self.game(exe, actual)
            with patch.dict('sys.modules', modules), self.assertRaises(RuntimeError):
                control.close_selected_game(manager)
            self.assertNotIn('terminate', calls)

    def test_timeout_is_not_success_and_no_broad_kill(self):
        manager, calls, modules = self.game(timeout=True)
        with patch.dict('sys.modules', modules), self.assertRaisesRegex(RuntimeError, 'timed out'):
            control.close_selected_game(manager)
        self.assertEqual(calls, ['terminate'])

    def test_already_gone_is_idempotent(self):
        manager, calls, modules = self.game(gone=True)
        with patch.dict('sys.modules', modules):
            control.close_selected_game(manager)
            manager.hwnd_window = None
            control.close_selected_game(manager)
        self.assertEqual(calls, [])

    def test_live_game_without_verified_window_is_unknown(self):
        manager, calls, modules = self.game()
        manager.hwnd_window = None
        modules['psutil'].process_iter = lambda attrs: [SimpleNamespace(info={'name': 'Client-Win64-Shipping.exe'})]
        with patch.dict('sys.modules', modules), self.assertRaisesRegex(RuntimeError, 'still running'):
            control.close_selected_game(manager)
        self.assertEqual(calls, [])


if __name__ == '__main__':
    unittest.main()
