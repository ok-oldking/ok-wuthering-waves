"""Import/guard regressions without loading the desktop framework or moving a cursor."""
import importlib.util
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch


class TestMouseResetImport(unittest.TestCase):
    def load_task(self):
        logger = Mock()
        framework = ModuleType('ok')
        framework.TriggerTask = type('TriggerTask', (), {})
        framework.Logger = SimpleNamespace(get_logger=lambda name: logger)
        path = Path(__file__).resolve().parents[1] / 'src/task/MouseResetTask.py'
        spec = importlib.util.spec_from_file_location('_mouse_reset_import_test', path)
        module = importlib.util.module_from_spec(spec)
        # None forces ModuleNotFoundError even when pywin32 is installed locally.
        with patch.dict('sys.modules', {'ok': framework, 'win32api': None}):
            spec.loader.exec_module(module)
        task = module.MouseResetTask()
        task.enabled = True
        task.is_browser = Mock(return_value=False)
        task.mouse_pos = None
        task.hwnd = None
        task.handler = SimpleNamespace(post=Mock())
        return task, logger

    def test_module_import_does_not_require_win32api(self):
        self.load_task()

    def test_browser_guards_do_not_import_or_schedule(self):
        task, logger = self.load_task()
        task.is_browser.return_value = True
        with patch.dict('sys.modules', {'win32api': None}):
            task.run()
            task.mouse_reset()
        task.handler.post.assert_not_called()
        logger.error.assert_not_called()

    def test_disabled_guards_do_not_import_or_schedule(self):
        task, logger = self.load_task()
        task.enabled = False
        with patch.dict('sys.modules', {'win32api': None}):
            task.run()
            task.mouse_reset()
        task.handler.post.assert_not_called()
        logger.error.assert_not_called()

    def test_native_cursor_read_keeps_existing_short_delay(self):
        task, _ = self.load_task()
        api = SimpleNamespace(GetCursorPos=Mock(return_value=(100, 100)), SetCursorPos=Mock())
        with patch.dict('sys.modules', {'win32api': api}):
            task.mouse_reset()
        self.assertEqual(task.mouse_pos, (100, 100))
        api.GetCursorPos.assert_called_once_with()
        api.SetCursorPos.assert_not_called()
        task.handler.post.assert_called_once_with(task.mouse_reset, 0.002, remove_existing=True)

    def test_native_center_jump_still_restores_previous_position(self):
        task, _ = self.load_task()
        task.mouse_pos = (10, 10)
        task.hwnd = SimpleNamespace(exists=True, visible=False)
        task.width_of_screen = Mock(return_value=500)
        task.height_of_screen = Mock(return_value=500)
        capture = SimpleNamespace(get_abs_cords=Mock(return_value=(500, 500)))
        task.executor = SimpleNamespace(interaction=SimpleNamespace(capture=capture))
        api = SimpleNamespace(GetCursorPos=Mock(return_value=(500, 500)), SetCursorPos=Mock())
        with patch.dict('sys.modules', {'win32api': api}):
            task.mouse_reset()
        api.SetCursorPos.assert_called_once_with((10, 10))
        self.assertEqual(task.mouse_pos, (10, 10))
        task.handler.post.assert_called_once_with(task.mouse_reset, 1, remove_existing=True)

    def test_native_api_exception_uses_existing_error_handler(self):
        task, logger = self.load_task()
        error = RuntimeError('cursor unavailable')
        api = SimpleNamespace(GetCursorPos=Mock(side_effect=error))
        with patch.dict('sys.modules', {'win32api': api}):
            task.mouse_reset()
        logger.error.assert_called_once_with('mouse_reset exception', error)
        task.handler.post.assert_not_called()

    def test_missing_native_dependency_uses_existing_error_handler(self):
        task, logger = self.load_task()
        with patch.dict('sys.modules', {'win32api': None}):
            task.mouse_reset()
        self.assertIsInstance(logger.error.call_args.args[1], ModuleNotFoundError)
        task.handler.post.assert_not_called()


if __name__ == '__main__':
    unittest.main()
