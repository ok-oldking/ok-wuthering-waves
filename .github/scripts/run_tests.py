"""Run each test file in a fresh process, including a deadline for shutdown."""

import argparse
from pathlib import Path
import subprocess
import sys


CHILD_CODE = """
import faulthandler
import runpy
import sys

faulthandler.enable()
faulthandler.dump_traceback_later(float(sys.argv.pop(1)), repeat=True)
sys.argv[0] = 'unittest'
runpy.run_module('unittest', run_name='__main__')
"""


def run_test(path, timeout):
    print(f'Running tests in {path}', flush=True)
    # Keep the watchdog active during interpreter shutdown, after unittest OK.
    with subprocess.Popen([
        sys.executable, '-u', '-c', CHILD_CODE, str(timeout * 0.75), str(path),
    ]) as process:
        try:
            return_code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            print(f'Timed out after {timeout}s in {path} (including process shutdown)',
                  file=sys.stderr, flush=True)
            return False
    if return_code != 0:
        print(f'Tests failed in {path}: exit code {return_code}', file=sys.stderr, flush=True)
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--timeout', type=float, default=120)
    parser.add_argument('paths', nargs='*', type=Path)
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error('--timeout must be positive')
    paths = args.paths or sorted(Path('tests').glob('*.py'))
    if not paths:
        parser.error('No test files found')
    for path in paths:
        if not run_test(path, args.timeout):
            return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
