import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import call, patch


SCRIPT = Path(__file__).resolve().parents[1] / '.github/scripts/install_dependencies.py'
spec = importlib.util.spec_from_file_location('install_dependencies', SCRIPT)
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class TestInstallDependencies(unittest.TestCase):
    def test_retries_transient_index_failure_without_cache(self):
        with patch.object(installer.subprocess, 'run', side_effect=[
            subprocess.CompletedProcess([], 1), subprocess.CompletedProcess([], 0),
        ]) as run, patch.object(installer.time, 'sleep') as sleep:
            self.assertEqual(0, installer.pip_install(['ok-script==3.0.0'], attempts=3))
        command = [sys.executable, '-m', 'pip', 'install', '--no-cache-dir', 'ok-script==3.0.0']
        self.assertEqual([call(command), call(command)], run.call_args_list)
        sleep.assert_called_once_with(30)

    def test_returns_failure_after_bounded_attempts(self):
        with patch.object(installer.subprocess, 'run', return_value=subprocess.CompletedProcess([], 7)) as run, \
                patch.object(installer.time, 'sleep') as sleep:
            self.assertEqual(7, installer.pip_install(['missing-package'], attempts=3))
        self.assertEqual(3, run.call_count)
        self.assertEqual(2, sleep.call_count)

    def test_does_not_continue_after_requirements_fail(self):
        with patch.object(installer, 'pip_install', return_value=1) as install:
            self.assertEqual(1, installer.main())
        install.assert_called_once_with(['-r', 'requirements.txt'])

    def test_installs_project_after_requirements_and_preserves_its_failure(self):
        with patch.object(installer, 'pip_install', side_effect=[0, 2]) as install:
            self.assertEqual(2, installer.main())
        self.assertEqual([call(['-r', 'requirements.txt']), call(['.[dev]'])], install.call_args_list)


if __name__ == '__main__':
    unittest.main()
