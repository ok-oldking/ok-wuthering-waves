import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


RUNNER = Path(__file__).resolve().parents[1] / '.github/scripts/run_tests.py'


class TestCIRunner(unittest.TestCase):
    def run_fixture(self, source, *extra_paths):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'test_fixture.py').write_text(source, encoding='utf-8')
            return subprocess.run(
                [sys.executable, str(RUNNER), '--timeout', '2',
                 'test_fixture.py', *extra_paths],
                cwd=directory, capture_output=True, text=True, timeout=10,
            )

    def test_success(self):
        result = self.run_fixture(
            'import unittest\n'
            'class Example(unittest.TestCase):\n'
            '    def test_pass(self): self.assertTrue(True)\n'
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Ran 1 test', result.stderr)

    def test_failure_stops_before_next_file(self):
        result = self.run_fixture(
            'import unittest\n'
            'class Example(unittest.TestCase):\n'
            '    def test_fail(self): self.fail("expected failure")\n',
            'should_not_run.py',
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn('expected failure', result.stderr)
        self.assertNotIn('should_not_run.py', result.stdout + result.stderr)

    def test_hang_after_ok_is_failure_with_traceback(self):
        result = self.run_fixture(
            'import threading, unittest\n'
            'class Example(unittest.TestCase):\n'
            '    def test_pass(self):\n'
            '        threading.Thread(target=threading.Event().wait).start()\n'
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn('OK', result.stderr)
        self.assertIn('Timed out after', result.stderr)
        self.assertIn('test_fixture.py', result.stderr)
        self.assertIn('Timeout (', result.stderr)
        self.assertIn('_shutdown', result.stderr)


if __name__ == '__main__':
    unittest.main()
