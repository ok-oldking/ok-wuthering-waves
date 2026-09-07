import ast
import importlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.mark.parametrize('name', ['ChangeEchoTask', 'EnhanceEchoTask'])
def test_completed_task_opens_screenshots_via_framework_service(name, monkeypatch):
    module = importlib.import_module('src.task.' + name)
    opened = Mock()
    monkeypatch.setattr(module, 'open_path', opened)
    if name == 'EnhanceEchoTask':
        monkeypatch.setattr(module, 'clear_folder', Mock())
    task = SimpleNamespace(info_set=Mock(), info_get=lambda key: 1,
                           find_echo_enhance=lambda: True, is_0_level=lambda: False,
                           debug=False, log_info=Mock(), log_error=Mock())
    getattr(module, name).run(task)
    opened.assert_called_once_with('screenshots')
    task.log_error.assert_not_called()


def test_task_modules_do_not_call_windows_startfile():
    root = Path(__file__).resolve().parents[1] / 'src' / 'task'
    for source in root.rglob('*.py'):
        tree = ast.parse(source.read_text(encoding='utf-8'))
        assert not any(isinstance(node, ast.Attribute) and node.attr == 'startfile'
                       for node in ast.walk(tree)), source.name
