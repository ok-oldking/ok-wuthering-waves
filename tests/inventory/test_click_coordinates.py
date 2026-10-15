"""原生点击白名单必须严格匹配，不因修复静态检查而放宽。"""
import math
from types import SimpleNamespace
import unittest
from src.inventory_support.inventory_entry_navigation import exact_coordinate, category_click_scope
from src.inventory_support.inventory_native_navigation import entry_module
from src.inventory_support.runtime import import_support
from unittest.mock import patch
from pathlib import Path
from src.inventory_support.inventory_entry_navigation import verify_forgery_selector


class CoordinateTests(unittest.TestCase):
    def test_real_resolver_reaches_guard_with_packaged_resources(self):
        from src.task.BaseWWTask import BaseWWTask
        from src.inventory_support import inventory_wuwa_destination as destination
        from src.inventory_support.inventory_wuwa_families import families
        task = SimpleNamespace()
        selector = BaseWWTask.click_on_book_target.__get__(task, BaseWWTask)
        names = [row['name'] for row in families()[0]['qualities']]
        def stop():
            raise RuntimeError('stop_before_input')
        with self.assertRaisesRegex(RuntimeError, 'stop_before_input'):
            destination.resolve(task, None, selector, names, stop)

    def test_current_native_selector_and_line_endings(self):
        from src.task.BaseWWTask import BaseWWTask
        task = SimpleNamespace()
        task.click_on_book_target = BaseWWTask.click_on_book_target.__get__(task, BaseWWTask)
        verify_forgery_selector(task)
        source = Path(__import__('inspect').getsourcefile(BaseWWTask.click_on_book_target))
        text = source.read_text(encoding='utf-8-sig')
        with patch.object(Path, 'read_text', return_value=text.replace('\n', '\r\n')):
            verify_forgery_selector(task)
        with patch.object(Path, 'read_text', return_value=text + '\ndef unrelated_challenge_fix():\n    return True\n'):
            verify_forgery_selector(task)
        with patch.object(Path, 'read_text', return_value=text.replace('bar_x = 0.9730', 'bar_x = 0.9720')), self.assertRaises(ValueError):
            verify_forgery_selector(task)

    def test_exact_values_only(self):
        for value in (0.24, 0.3, 0.8, 0.973):
            self.assertTrue(exact_coordinate(value, value))
            self.assertFalse(exact_coordinate(math.nextafter(value, math.inf), value))
        for invalid in (True, None, '0.24', math.nan, math.inf, -math.inf):
            self.assertFalse(exact_coordinate(invalid, .24))

    def test_category_click_restore_and_no_extra_input(self):
        calls = []
        original = lambda *args: calls.append(args)
        task = SimpleNamespace(click_relative=original)
        with category_click_scope(task, lambda: None):
            task.click_relative(.24, .3)
            with self.assertRaises(RuntimeError):
                task.click_relative(.24, .3)
        self.assertEqual(calls, [(.24, .3)])
        self.assertIs(task.click_relative, original)
        with self.assertRaises(RuntimeError), category_click_scope(task, lambda: None):
            task.click_relative(math.nextafter(.24, math.inf), .3)
        self.assertIs(task.click_relative, original)

    def test_foreign_game_adapter_rejected(self):
        self.assertEqual(entry_module({'game': 'wuwa'}).__name__.split('.')[-1], 'inventory_entry_navigation')
        with self.assertRaises(ValueError):
            entry_module({'game': 'zzz'})
        with self.assertRaises(ValueError):
            import_support('inventory-zzz-families.py')
