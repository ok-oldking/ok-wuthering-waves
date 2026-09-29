import os
import tempfile
import time
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication, QTableWidgetItem
from ok import BaseTask, Box, PostMessageInteraction, og
from ok.task.exceptions import TaskDisabledException, WaitFailedException
from ok.ui.qt.tasks.ConfigCard import ConfigCard
from ok.util.config import Config
from qfluentwidgets import FluentIcon

from src.gui.MultiAccountConfigTab import AccountStatusTable, AccountTaskCard, MultiAccountConfigTab
from src.task.DailyTask import DailyTask
from src.task.MultiAccountConfigTask import MultiAccountConfigTask
from src.task.WWOneTimeTask import WWOneTimeTask
from src.task.account.MultiAccountConfigStore import (
    MultiAccountConfigStore, account_key_from_ocr, collect_available_tasks,
    display_account, resolve_task, task_reference, validate_accounts,
)
from src.task.account.RuntimeTaskConfig import (
    RuntimeTaskConfig, account_task_config, effective_config, isolated_task_configs,
)


class ExampleTask:
    __module__ = 'src.task.ExampleTask'

    def __init__(self):
        self.name = '📅 Example Task'
        self.description = 'Example description'
        self.default_config = {'Count': 1, 'Items': ['base'], 'New Feature': True}
        self.config = deepcopy(self.default_config)
        self.config_description = {'Count': 'How many'}
        self.config_type = {}
        self.show_create_shortcut = False
        self.info = {}
        self.visible = True


class ExampleTrigger(ExampleTask):
    __module__ = 'src.task.ExampleTrigger'


def account(key='1231234', task=None, values=None):
    return {'account_key': key, 'task': task_reference(task) if task else None,
            'config': values or {}}


def executor_for(tasks, folder='configs'):
    return SimpleNamespace(
        config_folder=folder, get_all_tasks=lambda: tasks,
        onetime_tasks=[task for task in tasks if not isinstance(task, ExampleTrigger)],
        get_task_by_class=lambda cls: next((task for task in tasks if isinstance(task, cls)), None),
    )


class TestMultiAccountConfig(unittest.TestCase):
    def test_login_click_moves_real_cursor_before_background_button_message(self):
        import win32con

        capture = SimpleNamespace(get_abs_cords=lambda x, y: (x + 300, y + 100))
        interaction = PostMessageInteraction(capture, SimpleNamespace())
        interaction.update_mouse_pos = Mock(return_value=0)
        cursor = [0, 0]
        delivered = []

        def post(message, *args):
            if message == win32con.WM_LBUTTONDOWN:
                delivered.append(tuple(cursor))

        interaction.post = post
        runner = object.__new__(MultiAccountConfigTask)
        runner._executor = SimpleNamespace(interaction=interaction, reset_scene=Mock())
        runner._login_cursor_active = True
        runner.sleep = Mock()
        runner.logger = Mock()
        # Exercise real Box -> task.click -> PostMessage.click, mocking only OS I/O.
        with patch('win32api.SetCursorPos', side_effect=lambda pos: cursor.__setitem__(slice(None), pos)), \
                patch('ok.device.interaction_methods.post_message.time.sleep'):
            runner.click([Box(1259, 782, 40, 20, name='登录')])
        self.assertEqual(delivered, [(1579, 892)])
        runner.sleep.assert_any_call(0.2)

    def test_background_click_outside_login_does_not_move_real_cursor(self):
        interaction = PostMessageInteraction(SimpleNamespace(), SimpleNamespace())
        interaction.click = Mock()
        runner = object.__new__(MultiAccountConfigTask)
        runner._executor = SimpleNamespace(interaction=interaction, reset_scene=Mock())
        with patch('win32api.SetCursorPos') as move:
            runner.click(1279, 792)
        move.assert_not_called()
        interaction.click.assert_called_once()

    def test_login_relative_fallback_uses_converted_desktop_coordinates(self):
        capture = SimpleNamespace(get_abs_cords=lambda x, y: (x + 300, y + 100))
        interaction = PostMessageInteraction(capture, SimpleNamespace())
        interaction.click = Mock()
        runner = object.__new__(MultiAccountConfigTask)
        runner._executor = SimpleNamespace(interaction=interaction, reset_scene=Mock(),
                                           method=SimpleNamespace(width=2560, height=1440))
        runner._login_cursor_active = True
        runner.out_of_ratio = lambda: False
        runner.sleep = Mock()
        with patch('win32api.SetCursorPos') as move:
            runner.click_relative(0.5, 0.568, hcenter=True, vcenter=True)
        move.assert_called_once_with((1580, 917))

    def test_login_cursor_mode_restores_after_cancellation_during_wait_main(self):
        mouse = SimpleNamespace(enabled=True, disable=Mock(), enable=Mock())
        runner = SimpleNamespace(
            executor=SimpleNamespace(get_task_by_class=lambda cls: mouse),
            _login_combo=lambda: None,
            sleep=Mock(), click=Mock(), find_account_drop_down=lambda: 'dropdown',
            do_find_account_drop_down=lambda: None,
            _find_target_account=lambda key: True,
            wait_until=lambda callback, **kwargs: callback(),
            _detect_current_account_from_login=lambda: '123****1234',
            ocr=Mock(return_value=[]), find_boxes=Mock(return_value=['login']),
            box_of_screen=Mock(),
        )

        def wait_main(**kwargs):
            self.assertTrue(runner._login_cursor_active)
            raise TaskDisabledException()

        runner.ensure_main = wait_main
        with self.assertRaises(TaskDisabledException):
            MultiAccountConfigTask._login_target_account(runner, '1231234')
        self.assertFalse(runner._login_cursor_active)
        mouse.enable.assert_called_once()

    def test_account_keys(self):
        self.assertEqual(account_key_from_ocr('123****1234'), '1231234')
        self.assertEqual(display_account('1231234'), '1231234')
        for value in ('', '***', '123*1234', ' name', 'name ', 'a\nb'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_accounts([account(value)])
        for text, key in [('123***1234', '1231234'), ('Ab****12@outlook.com', 'Ab12@outlook.com'),
                          ('Some Name', 'Some Name'), ('*a*b**', 'ab'), ('1234', '1234')]:
            self.assertEqual(account_key_from_ocr(text), key)
            validate_accounts([account(key)])
        self.assertNotEqual(account_key_from_ocr('A0****12'), account_key_from_ocr('ao****12'))

    def test_combo_selects_configured_email_or_name_without_ocr_clicks(self):
        module = 'src.task.MultiAccountConfigTask.'
        for target, displayed in [('Ab12@outlook.com', 'Ab****12@outlook.com'),
                                  ('Some Name', 'Some Name'), ('1231234', '123**1234')]:
            with self.subTest(target=target):
                runner = SimpleNamespace(_login_combo=lambda: 42, sleep=Mock(),
                                         ocr=Mock(side_effect=AssertionError('unexpected OCR')),
                                         click=Mock(side_effect=AssertionError('unexpected click')))
                with patch(module + 'combo_items', return_value=['Other', displayed, displayed]), \
                        patch(module + 'select_combo_item', return_value=True) as select, \
                        patch(module + 'combo_selected_item', return_value=displayed):
                    MultiAccountConfigTask._select_target_account(runner, target)
                select.assert_called_once_with(42, 2)
                runner.ocr.assert_not_called()
                runner.click.assert_not_called()

    def test_combo_failure_never_logs_in_or_falls_back_and_restores_mouse(self):
        module = 'src.task.MultiAccountConfigTask.'
        for items, selected, current in [(['Other'], True, 'Other'),
                                         (['Ab**12@outlook.com'], False, 'Ab**12@outlook.com'),
                                         (['Ab**12@outlook.com'], True, 'Other')]:
            with self.subTest(items=items, selected=selected, current=current):
                mouse = SimpleNamespace(enabled=True, disable=Mock(), enable=Mock())
                runner = SimpleNamespace(executor=SimpleNamespace(get_task_by_class=lambda cls: mouse),
                                         _login_combo=lambda: 42, sleep=Mock(), ocr=Mock(), click=Mock(),
                                         find_account_drop_down=Mock(), ensure_main=Mock())
                with patch(module + 'combo_items', return_value=items), \
                        patch(module + 'select_combo_item', return_value=selected), \
                        patch(module + 'combo_selected_item', return_value=current), \
                        self.assertRaises(WaitFailedException):
                    MultiAccountConfigTask._login_target_account(runner, 'Ab12@outlook.com')
                runner.ocr.assert_not_called()
                runner.click.assert_not_called()
                runner.find_account_drop_down.assert_not_called()
                runner.ensure_main.assert_not_called()
                mouse.enable.assert_called_once()

    def test_ocr_matches_email_and_name_after_removing_every_star(self):
        for text, target in [('Ab*1**2@outlook.com', 'Ab12@outlook.com'), ('Some Name', 'Some Name')]:
            with self.subTest(text=text):
                box = SimpleNamespace(name=text, y=100, height=30)
                runner = SimpleNamespace(ocr=lambda: [box], click=Mock(),
                                         _target_account_key=target, find_boxes=Mock(return_value=['login']))
                self.assertTrue(MultiAccountConfigTask._find_target_account(runner, target))
                runner.click.assert_called_once_with(box, after_sleep=2)
                self.assertIs(MultiAccountConfigTask.do_find_account_drop_down(runner), box)

    def test_email_and_name_configs_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            store = MultiAccountConfigStore(folder)
            values = [account('Ab12@outlook.com'), account('Some Name'), account('1231234')]
            store.save(values)
            self.assertEqual(store.load(), values)

    def test_atomic_save_validation_and_order(self):
        with tempfile.TemporaryDirectory() as folder:
            store = MultiAccountConfigStore(folder)
            self.assertEqual(store.load(), [])
            accounts = [account('2342345'), account('1231234')]
            store.save(accounts)
            original = store.path.read_bytes()
            self.assertEqual(store.load(), accounts)
            with self.assertRaisesRegex(ValueError, '重复'):
                store.save([account(), account()])
            self.assertEqual(store.path.read_bytes(), original)
            with patch('os.replace', side_effect=OSError('disk error')):
                with self.assertRaises(OSError):
                    store.save([account()])
            self.assertEqual(store.path.read_bytes(), original)
            self.assertEqual(list(Path(folder).glob('*.tmp')), [])

    def test_corrupt_file_is_not_silently_reset(self):
        with tempfile.TemporaryDirectory() as folder:
            store = MultiAccountConfigStore(folder)
            store.path.write_text('{broken', encoding='utf-8')
            with self.assertRaises(ValueError):
                store.load()
            self.assertEqual(store.path.read_text(encoding='utf-8'), '{broken')

    def test_registry_only_includes_visible_onetime_project_tasks(self):
        one, trigger, external = ExampleTask(), ExampleTrigger(), SimpleNamespace()
        hidden = ExampleTask()
        hidden.visible = False
        executor = executor_for([one, trigger, external, hidden])
        self.assertEqual(collect_available_tasks(executor), [one])
        self.assertIs(resolve_task(executor, task_reference(one)), one)
        with self.assertRaises(ValueError):
            resolve_task(executor, task_reference(trigger))
        with self.assertRaisesRegex(ValueError, '未注册'):
            resolve_task(executor, {'module': 'src.task.Removed', 'class': 'Removed'})

    def test_both_multi_account_runners_are_rejected(self):
        for name in ('MultiAccountDailyTask', 'MultiAccountConfigTask'):
            entry = account()
            entry['task'] = {'module': f'src.task.{name}', 'class': name}
            with self.assertRaisesRegex(ValueError, '多账号执行器'):
                validate_accounts([entry])

    def test_schema_merge_and_deepcopy(self):
        task = ExampleTask()
        task.config['Count'] = 2
        saved = {'Items': ['account']}
        runtime = effective_config(task, saved)
        self.assertEqual(runtime['Count'], 2)
        self.assertTrue(runtime['New Feature'])
        runtime['Items'].append('changed')
        self.assertEqual(saved['Items'], ['account'])
        self.assertEqual(task.config['Items'], ['base'])
        runtime.reset_to_default()
        runtime['Items'].append('reset change')
        self.assertEqual(task.default_config['Items'], ['base'])

    def test_config_and_nested_configs_restore_on_failure(self):
        first, nested = ExampleTask(), ExampleTrigger()
        originals = [first.config, nested.config]
        with self.assertRaisesRegex(RuntimeError, 'failed'):
            with isolated_task_configs([first, nested]):
                with account_task_config(first, {'Count': 7}):
                    self.assertEqual(first.config['Count'], 7)
                    nested.config['Items'].append('temporary')
                    raise RuntimeError('failed')
        self.assertIs(first.config, originals[0])
        self.assertIs(nested.config, originals[1])
        self.assertEqual(nested.config['Items'], ['base'])

    def make_runner(self, executor):
        runner = SimpleNamespace(executor=executor, info={}, config={}, default_config={})
        runner.info_set = lambda key, value: runner.info.__setitem__(key, value)
        runner.tr = lambda text: text
        runner.log_info = Mock()
        runner.log_error = Mock()
        runner.ensure_main = Mock()
        runner._switch_to_login = Mock()
        runner._login_target_account = Mock()
        runner.get_task_by_class = executor.get_task_by_class
        runner.run_task_by_class = lambda cls: BaseTask.run_task_by_class(runner, cls)
        return runner

    def test_runner_account_configs_none_nested_tasks_and_disk_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            task, nested = ExampleTask(), ExampleTrigger()
            for item in (task, nested):
                item.config = Config(type(item).__name__, item.default_config, folder=folder)
            originals = [task.config, nested.config]
            files = {path: path.read_bytes() for path in Path(folder).glob('*.json')}
            accounts = [account(task=task, values={'Count': 11}), account('2342345'),
                        account('3453456', task, {'Count': 22})]
            MultiAccountConfigStore(folder).save(accounts)
            executor = executor_for([task, nested], folder)
            runner = self.make_runner(executor)
            observed = []

            def run():
                observed.append((task.config['Count'], list(nested.config['Items'])))
                task.config['Count'] = 999
                nested.config['Items'].append('runtime')
                nested.config.save_file()
                task.info['current daily progress'] = 100

            task.run = run
            with patch.object(WWOneTimeTask, 'run'):
                MultiAccountConfigTask.run(runner)
            self.assertEqual(observed, [(11, ['base']), (22, ['base'])])
            self.assertEqual([call.args[0] for call in runner._login_target_account.call_args_list],
                             ['1231234', '2342345', '3453456'])
            self.assertEqual(runner._switch_to_login.call_count, 4)
            self.assertEqual(runner.info['状态'], '全部完成')
            self.assertEqual(runner.info['current daily progress'], 100)
            self.assertEqual(len(runner.info['已完成']), 3)
            self.assertIs(task.config, originals[0])
            self.assertIs(nested.config, originals[1])
            self.assertEqual(task.info, {})
            for path, content in files.items():
                self.assertEqual(path.read_bytes(), content)

    def test_runner_failure_and_cancellation_restore_and_stop(self):
        for error in (RuntimeError('failed'), TaskDisabledException()):
            with self.subTest(error=type(error)), tempfile.TemporaryDirectory() as folder:
                task = ExampleTask()
                original = task.config
                task.run = Mock(side_effect=error)
                executor = executor_for([task], folder)
                runner = self.make_runner(executor)
                MultiAccountConfigStore(folder).save([account(task=task), account('2342345')])
                with patch.object(WWOneTimeTask, 'run'), self.assertRaises(type(error)):
                    MultiAccountConfigTask.run(runner)
                self.assertIs(task.config, original)
                self.assertEqual(runner._login_target_account.call_count, 1)
                self.assertEqual(runner.info['已完成'], [])
                result = MultiAccountConfigStore(folder).load_results()['1231234']
                self.assertEqual(result['status'], 'cancelled' if isinstance(error, TaskDisabledException) else 'failed')
                self.assertTrue(result['finished_at'])

    def test_disabled_accounts_skip_login_and_keep_previous_result(self):
        with tempfile.TemporaryDirectory() as folder:
            store = MultiAccountConfigStore(folder)
            disabled = account('2342345')
            disabled['enabled'] = False
            enabled = account()  # Older saved accounts default to enabled.
            store.save([disabled, enabled])
            store.record_result(disabled, 'success')
            previous = store.load_results()['2342345']
            runner = self.make_runner(executor_for([], folder))
            with patch.object(WWOneTimeTask, 'run'):
                MultiAccountConfigTask.run(runner)
            runner._login_target_account.assert_called_once_with('1231234')
            self.assertEqual(runner._switch_to_login.call_count, 2)
            results = store.load_results()
            self.assertEqual(results['2342345'], previous)
            self.assertEqual(results['1231234']['status'], 'success')
            self.assertTrue(results['1231234']['finished_at'])
            # Saving an older UI draft must not discard fresh execution results.
            store.save([disabled, enabled])
            self.assertEqual(store.load_results(), results)

    def test_all_disabled_accounts_send_no_game_input(self):
        with tempfile.TemporaryDirectory() as folder:
            disabled = account()
            disabled['enabled'] = False
            store = MultiAccountConfigStore(folder)
            store.save([disabled])
            runner = self.make_runner(executor_for([], folder))
            with patch.object(WWOneTimeTask, 'run') as prepare:
                MultiAccountConfigTask.run(runner)
            prepare.assert_not_called()
            runner.ensure_main.assert_not_called()
            runner._login_target_account.assert_not_called()
            self.assertEqual(store.load_results(), {})

    def test_invalid_plan_fails_before_game_input(self):
        with tempfile.TemporaryDirectory() as folder:
            removed = ExampleTask()
            MultiAccountConfigStore(folder).save([account(task=removed)])
            runner = self.make_runner(executor_for([], folder))
            with self.assertRaises(ValueError):
                MultiAccountConfigTask.run(runner)
            runner.ensure_main.assert_not_called()

    def test_find_target_matches_exactly_and_prefers_lowest_duplicate(self):
        boxes = [SimpleNamespace(name=name, y=index * 100, height=30)
                 for index, name in enumerate(('123****1234', '234****2345', '345****3456'))]
        runner = SimpleNamespace(ocr=lambda **_: boxes, click=Mock())
        self.assertTrue(MultiAccountConfigTask._find_target_account(runner, '3453456'))
        runner.click.assert_called_once_with(boxes[2], after_sleep=2)
        self.assertFalse(MultiAccountConfigTask._find_target_account(runner, '1112222'))
        lowest = SimpleNamespace(name='345****3456', y=400, height=30)
        boxes.insert(0, lowest)  # OCR order must not determine the selected row.
        self.assertTrue(MultiAccountConfigTask._find_target_account(runner, '3453456'))
        runner.click.assert_called_with(lowest, after_sleep=2)

    def test_failed_dropdown_never_attempts_login_and_restores_mouse(self):
        mouse = SimpleNamespace(enabled=True, disable=Mock(), enable=Mock())
        runner = SimpleNamespace(
            executor=SimpleNamespace(get_task_by_class=lambda cls: mouse),
            _login_combo=lambda: None,
            sleep=Mock(), click=Mock(), find_account_drop_down=Mock(return_value='dropdown'),
            do_find_account_drop_down=Mock(return_value=True), ocr=Mock(),
        )
        with self.assertRaises(WaitFailedException):
            MultiAccountConfigTask._login_target_account(runner, '1231234')
        runner.ocr.assert_not_called()
        self.assertEqual(runner.click.call_count, 5)
        mouse.disable.assert_called_once()
        mouse.enable.assert_called_once()

    def test_login_confirms_target_before_clicking_login(self):
        for displayed in ('123****1234', '234****2345'):
            with self.subTest(displayed=displayed):
                mouse = SimpleNamespace(enabled=True, disable=Mock(), enable=Mock())
                runner = SimpleNamespace(
                    executor=SimpleNamespace(get_task_by_class=lambda cls: mouse),
                    _login_combo=lambda: None,
                    sleep=Mock(), click=Mock(), find_account_drop_down=Mock(return_value='dropdown'),
                    do_find_account_drop_down=Mock(return_value=None),
                    _find_target_account=Mock(return_value=True),
                    wait_until=lambda callback, **kwargs: callback(),
                    _detect_current_account_from_login=lambda: displayed,
                    log_info=Mock(), ocr=Mock(return_value=[]),
                    find_boxes=Mock(return_value=['login']), box_of_screen=Mock(),
                    ensure_main=Mock(),
                )
                if displayed.startswith('123'):
                    MultiAccountConfigTask._login_target_account(runner, '1231234')
                    runner.click.assert_any_call(['login'], after_sleep=3)
                    runner.ensure_main.assert_called_once_with(time_out=180)
                    self.assertFalse(runner.logged_in)
                    self.assertFalse(runner._login_cursor_active)
                else:
                    with self.assertRaises(WaitFailedException):
                        MultiAccountConfigTask._login_target_account(runner, '1231234')
                    runner.find_boxes.assert_not_called()
                    runner.ensure_main.assert_not_called()
                mouse.enable.assert_called_once()

    def test_mouse_config_never_writes_during_account_selection(self):
        with tempfile.TemporaryDirectory() as folder:
            mouse = ExampleTrigger()
            mouse.default_config = {'_enabled': True}
            mouse.config = Config('MouseResetTask', mouse.default_config, folder=folder)
            mouse.enabled = True
            original = mouse.config
            path = Path(original.config_file)
            before = path.read_bytes()
            mouse.disable = lambda: mouse.config.__setitem__('_enabled', False)
            mouse.enable = lambda: mouse.config.__setitem__('_enabled', True)
            runner = SimpleNamespace(
                executor=SimpleNamespace(get_task_by_class=lambda cls: mouse),
                _login_combo=lambda: None,
                sleep=Mock(side_effect=TaskDisabledException()),
            )
            with self.assertRaises(TaskDisabledException), isolated_task_configs([mouse]):
                MultiAccountConfigTask._login_target_account(runner, '1231234')
            self.assertIs(mouse.config, original)
            self.assertEqual(path.read_bytes(), before)


class TestMultiAccountConfigUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.app_patch = patch.object(og, 'app', SimpleNamespace(tr=lambda text: text,
                                                               start_controller=Mock()))
        self.app_patch.start()

    def tearDown(self):
        self.app.processEvents()
        self.app_patch.stop()

    def test_log_table_fits_multiline_values_and_reflows_on_resize(self):
        table = AccountStatusTable()
        table.setColumnCount(2)
        table.setRowCount(2)
        table.setItem(0, 0, QTableWidgetItem('Log'))
        table.setItem(0, 1, QTableWidgetItem('login completed'))
        table.setItem(1, 0, QTableWidgetItem('Details'))
        table.setItem(1, 1, QTableWidgetItem('first line\nsecond line\n' + 'long log value ' * 50))
        try:
            table.resize(900, 100)
            table.show()
            for _ in range(3):
                self.app.processEvents()
            wide_height = table.height()
            self.assertGreater(table.rowHeight(1), table.rowHeight(0))
            self.assertGreaterEqual(table.viewport().height(), table.verticalHeader().length())
            table.resize(450, table.height())
            for _ in range(3):
                self.app.processEvents()
            self.assertGreater(table.height(), wide_height)
            self.assertGreaterEqual(table.viewport().height(), table.verticalHeader().length())
            table.item(1, 1).setText('short')
            table.schedule_fit()
            self.app.processEvents()
            self.assertLess(table.height(), wide_height)
        finally:
            table.close()
            table.deleteLater()

    def test_account_cards_stay_at_top_with_fixed_small_gap(self):
        tab = MultiAccountConfigTab()
        tab.executor = executor_for([])
        tab.loaded = True
        try:
            tab.add_account(account())
            tab.add_account(account('2342345'))
            tab.resize(1100, 1100)
            tab.show()
            for _ in range(3):
                self.app.processEvents()
            first, second = tab.cards
            self.assertEqual(first.y(), 0)
            self.assertEqual(second.y() - (first.y() + first.height()), 6)
            self.assertLessEqual(tab.accounts_widget.height(), first.height() + second.height() + 6)
        finally:
            tab.close()
            tab.deleteLater()

    def test_account_editor_accepts_email_and_display_name(self):
        card = AccountTaskCard(account(), [], lambda: None)
        for value in ('Ab12@outlook.com', 'Some Name'):
            card.account_edit.setText(value)
            self.assertEqual(card.account_edit.text(), value)
        card.deleteLater()

    def test_task_name_and_account_edit_isolation(self):
        task, trigger = ExampleTask(), ExampleTrigger()
        tasks = collect_available_tasks(executor_for([task, trigger]))
        cards = [AccountTaskCard(account(task=task), tasks, Mock()) for _ in range(2)]
        try:
            card, other = cards
            self.assertEqual(card.task_combo.itemText(1), og.app.tr(task.name))
            self.assertEqual(card.task_combo.count(), 2)
            card.values['Count'] = 7
            self.assertEqual(other.values['Count'], 1)
            self.assertEqual(task.config['Count'], 1)
            card.task_combo.setCurrentIndex(0)
            self.assertIsNone(card.snapshot()['task'])
            card.task_combo.setCurrentIndex(1)
            self.assertEqual(card.values['Count'], 7)
        finally:
            for card in cards:
                card.deleteLater()

    def test_account_switch_result_and_expanded_task_resize(self):
        task = ExampleTask()
        task.default_config.update({f'Option {i}': i for i in range(12)})
        task.config = deepcopy(task.default_config)
        card = AccountTaskCard(account(task=task), [task], Mock())
        try:
            card.resize(1100, card.height())
            card.show()
            card.setExpand(True)
            for _ in range(3):
                self.app.processEvents()
            tall_height = card.height()
            self.assertTrue(card.enabled_switch.isChecked())
            card.enabled_switch.setChecked(False)
            self.assertFalse(card.snapshot()['enabled'])
            self.assertEqual(card.result_label.text(), '未运行')
            card.update_result({'status': 'success', 'finished_at': '2026-09-25T22:00:00+08:00'})
            self.assertTrue(card.result_label.text().startswith('✓'))
            self.assertIn('2026-09-25', card.result_label.text())
            card.update_result({'status': 'failed', 'finished_at': '2026-09-25T22:00:00+08:00', 'message': '失败原因'})
            self.assertTrue(card.result_label.text().startswith('✗'))
            self.assertIn('失败原因', card.result_label.toolTip())
            for _ in range(3):
                card.task_combo.setCurrentIndex(0)
                self.app.processEvents()
                self.assertTrue(card.isExpand)
                self.assertLess(card.height(), tall_height)
                self.assertEqual(card.height(), card.card.height() + card.viewLayout.sizeHint().height())
                card.task_combo.setCurrentIndex(1)
                self.app.processEvents()
                self.assertEqual(card.height(), tall_height)
            card.setExpand(False)
            card.task_combo.setCurrentIndex(0)
            self.app.processEvents()
            self.assertFalse(card.isExpand)
            self.assertEqual(card.height(), card.card.height())
        finally:
            card.close()
            card.deleteLater()

    def test_real_daily_config_uses_identical_widgets_and_subconfig_rules(self):
        executor = SimpleNamespace(scene=None, text_fix={},
                                   global_config=SimpleNamespace(get_config=lambda name: {}))
        task = DailyTask(executor, None)
        task.config = RuntimeTaskConfig(task.default_config, task.default_config)
        card = AccountTaskCard(account(task=task), [task], Mock())
        original = ConfigCard(task, task.name, task.config, task.description, task.default_config,
                              task.config_description, task.config_type, FluentIcon.INFO)
        try:
            content = card.content
            self.assertIs(content.default_config, task.default_config)
            self.assertIs(content.config_description, task.config_description)
            self.assertIs(content.config_type, task.config_type)
            self.assertEqual(content.config_keys, original.config_keys)
            self.assertEqual([type(w) for w in content.config_widgets],
                             [type(w) for w in original.config_widgets])
            self.assertEqual(content.sub_configs_rules, original.sub_configs_rules)
            for key in content.config_keys:
                self.assertEqual(content.config_widget_by_key[key].isHidden(),
                                 original.config_widget_by_key[key].isHidden())
            self.assertIsNot(content.config, task.config)
        finally:
            card.deleteLater()
            original.deleteLater()

    def test_tab_load_save_start_uses_controller_and_preserves_status(self):
        with tempfile.TemporaryDirectory() as folder:
            task = ExampleTask()
            runner = MultiAccountConfigTask(SimpleNamespace(
                scene=None, text_fix={}, global_config=SimpleNamespace(get_config=lambda name: {})), None)
            runner.info = {'当前账号': '123****1234', 'Log': 'Login successful', '已完成': []}
            og.app.tr = lambda text: text if text else 'CATALOG METADATA'
            tab = MultiAccountConfigTab()
            tab.executor = executor_for([task, runner], folder)
            MultiAccountConfigStore(folder).save([account(task=task)])
            try:
                tab.show()
                self.app.processEvents()
                self.assertTrue(tab.loaded)
                self.assertEqual(len(tab.cards), 1)
                tab.store.record_result(account(task=task), 'success')
                tab.refresh_status()
                self.assertTrue(tab.cards[0].result_label.text().startswith('✓'))
                self.assertTrue(tab.status_card.isHidden())
                self.assertLess(tab.vBoxLayout.indexOf(tab.status_card),
                                tab.vBoxLayout.indexOf(tab.accounts_widget))
                tab.start_clicked()
                og.app.start_controller.start.assert_called_once_with(runner)
                # Scheduling alone is not a running task yet.
                self.assertTrue(tab.status_card.isHidden())
                runner.start_time = time.time() - 65
                runner._enabled = True
                tab.refresh_status()
                self.assertFalse(tab.status_card.isHidden())
                self.assertIn('Running:', tab.status_card.titleLabel.text())
                self.assertIn('0h 1m', tab.status_card.titleLabel.text())
                self.assertEqual(tab.status_table.rowCount(), 3)
                self.assertEqual(tab.status_table.item(2, 1).text(), '')
                self.assertEqual(MultiAccountConfigStore(folder).load()[0]['config'], task.config)
                runner._enabled = True
                tab.refresh_status()
                self.assertFalse(tab.accounts_widget.isEnabled())
                self.assertTrue(tab.stop_button.isEnabled())
                runner._enabled = False
                tab.refresh_status()
                self.assertFalse(tab.status_card.isHidden())
                self.assertIn('Completed:', tab.status_card.titleLabel.text())
                tab.close_task_info()
                tab.refresh_status()
                self.assertTrue(tab.status_card.isHidden())
                runner.start_time = time.time()
                runner._enabled = True
                tab.refresh_status()
                self.assertFalse(tab.status_card.isHidden())
            finally:
                tab.close()
                tab.deleteLater()

    def test_unavailable_task_remains_visible_and_cannot_be_saved(self):
        removed = ExampleTask()
        card = AccountTaskCard(account(task=removed), [], Mock())
        try:
            self.assertEqual(card.task_combo.currentIndex(), -1)
            self.assertEqual(card.task_combo.count(), 1)  # Only “none”, no stale task option.
            self.assertEqual(card.snapshot()['task'], task_reference(removed))
            with self.assertRaises(ValueError):
                validate_accounts([card.snapshot()], executor_for([]))
        finally:
            card.deleteLater()


if __name__ == '__main__':
    unittest.main()
