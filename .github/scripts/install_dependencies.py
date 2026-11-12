"""Install release dependencies, allowing fresh PyPI releases to propagate."""

import subprocess
import sys
import time


def pip_install(arguments, attempts=10, retry_delay=30):
    command = [sys.executable, '-m', 'pip', 'install', '--no-cache-dir', *arguments]
    for attempt in range(1, attempts + 1):
        result = subprocess.run(command)
        if result.returncode == 0:
            return 0
        if attempt == attempts:
            return result.returncode
        print(f'Dependency installation failed (attempt {attempt}/{attempts}); '
              f'retrying in {retry_delay}s without the pip cache.', flush=True)
        time.sleep(retry_delay)


def main():
    result = pip_install(['-r', 'requirements.txt'])
    if result:
        return result
    return pip_install(['.[dev]'])


if __name__ == '__main__':
    sys.exit(main())
