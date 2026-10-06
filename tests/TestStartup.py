import runpy
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import psutil

from src.startup import close_system_informer


ENTRY_POINTS = ('main.py', 'main_debug.py', 'main_web.py', 'main_web_debug.py')
PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TestStartup(unittest.TestCase):
    def test_closes_all_matching_processes_only(self):
        processes = [Mock(info={'name': name}) for name in (
            'SystemInformer.exe', 'SYSTEMINFORMER.EXE', 'TrafficMonitor.exe',
            'SystemInformer.exe.backup', None,
        )]
        with patch('src.startup.psutil.process_iter', return_value=processes) as process_iter:
            close_system_informer()

        process_iter.assert_called_once_with(['name'])
        for process in processes[:2]:
            process.kill.assert_called_once_with()
            process.wait.assert_called_once_with(timeout=5)
        for process in processes[2:]:
            process.kill.assert_not_called()
            process.wait.assert_not_called()

    def test_does_nothing_when_not_running(self):
        with patch('src.startup.psutil.process_iter', return_value=[]):
            close_system_informer()

    def test_disappearing_process_does_not_skip_other_instances(self):
        for operation in ('kill', 'wait'):
            with self.subTest(operation=operation):
                exited = Mock(info={'name': 'SystemInformer.exe'})
                getattr(exited, operation).side_effect = psutil.NoSuchProcess(123)
                running = Mock(info={'name': 'SystemInformer.exe'})
                with patch('src.startup.psutil.process_iter', return_value=[exited, running]):
                    close_system_informer()
                running.kill.assert_called_once_with()
                running.wait.assert_called_once_with(timeout=5)

    def test_reports_failure_to_close(self):
        for operation, error in (
                ('kill', psutil.AccessDenied(123)),
                ('wait', psutil.TimeoutExpired(5, pid=123))):
            with self.subTest(operation=operation):
                process = Mock(pid=123, info={'name': 'SystemInformer.exe'})
                getattr(process, operation).side_effect = error
                with patch('src.startup.psutil.process_iter', return_value=[process]):
                    with self.assertRaisesRegex(RuntimeError, 'SystemInformer.exe.*PID 123') as raised:
                        close_system_informer()
                self.assertIs(raised.exception.__cause__, error)

    def test_all_entry_points_close_before_initializing_app(self):
        for entry_point in ENTRY_POINTS:
            with self.subTest(entry_point=entry_point):
                events = []
                app = Mock()
                app.start.side_effect = lambda: events.append('start')
                factory = Mock(side_effect=lambda config: events.append('init') or app)
                modules = {'config': SimpleNamespace(config={}), 'ok': SimpleNamespace(OK=factory)}
                with patch.dict('sys.modules', modules), patch.dict('os.environ'):
                    with patch('src.startup.close_system_informer',
                               side_effect=lambda: events.append('close')):
                        runpy.run_path(str(PROJECT_ROOT / entry_point), run_name='__main__')
                self.assertEqual(['close', 'init', 'start'], events)

    def test_all_entry_points_stop_when_close_fails(self):
        for entry_point in ENTRY_POINTS:
            with self.subTest(entry_point=entry_point):
                factory = Mock()
                with patch.dict('sys.modules', {'ok': SimpleNamespace(OK=factory)}):
                    with patch.dict('os.environ'), patch('src.startup.close_system_informer',
                                                        side_effect=RuntimeError('close failed')):
                        with self.assertRaisesRegex(RuntimeError, 'close failed'):
                            runpy.run_path(str(PROJECT_ROOT / entry_point), run_name='__main__')
                factory.assert_not_called()


if __name__ == '__main__':
    unittest.main()
