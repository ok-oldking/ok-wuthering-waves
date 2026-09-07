import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(sys.platform != 'darwin', reason='Darwin import isolation check')
def test_all_okww_runtime_modules_import_without_win32():
    script = textwrap.dedent(
        """
        import importlib
        from pathlib import Path
        import sys

        root = Path('.')
        modules = [
            'config',
            'main',
            'main_debug',
            'main_web',
            'main_web_debug',
            'src.gui.CharacterCodeTab',
        ]
        for folder in ('src/task', 'src/combat', 'src/scene'):
            modules.extend(
                str(path.with_suffix('')).replace('/', '.')
                for path in sorted((root / folder).glob('*.py'))
                if path.name != '__init__.py'
            )

        failures = []
        for module_name in modules:
            try:
                importlib.import_module(module_name)
            except Exception as error:
                failures.append(
                    (module_name, type(error).__name__, str(error))
                )

        forbidden = sorted(
            name for name in sys.modules
            if name.startswith(('win32', 'pythoncom', 'pywintypes', 'ok.rotypes'))
        )
        if failures:
            raise SystemExit(f'import failures: {failures!r}')
        if forbidden:
            raise SystemExit(f'forbidden modules loaded: {forbidden!r}')
        """
    )
    env = os.environ.copy()
    env.setdefault('QT_QPA_PLATFORM', 'offscreen')
    result = subprocess.run(
        [sys.executable, '-c', script],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
