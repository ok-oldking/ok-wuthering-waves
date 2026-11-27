"""多账号任务的云鸣潮模式测试.

验证「以官方为基线 + 云端定制」后的行为:
1. 云游戏设备下自动走云分支, 不再点游戏内登录框;
2. 「保存登录状态 / 切换账号」是两个按钮, 合并进多账号任务, 且只在云设备下出现;
3. PC 客户端下配置面板与官方完全一致(没有云按钮)。
"""

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.task.MultiAccountDailyTask import (  # noqa: E402
    ACCOUNT_CONFIGURATION, CLOUD_ACCOUNT_ACTIONS, CLOUD_SAVE_BUTTON, CLOUD_SWITCH_BUTTON,
    PER_ACCOUNT_CONFIGURATION, MultiAccountDailyTask,
)


def make_task(cloud):
    task = MultiAccountDailyTask.__new__(MultiAccountDailyTask)
    task._config_type = {
        PER_ACCOUNT_CONFIGURATION: {'sub_configs': {True: [ACCOUNT_CONFIGURATION]}},
        ACCOUNT_CONFIGURATION: {'type': 'button', 'text': 'Configure Accounts'},
        CLOUD_ACCOUNT_ACTIONS: {'buttons': []},
    }
    task._is_cloud_device = lambda: cloud
    return task


def config_type_of(task):
    return MultiAccountDailyTask.config_type.fget(task)


class CloudConfigTypeTest(unittest.TestCase):

    def test_cloud_shows_cloud_buttons(self):
        types = config_type_of(make_task(True))
        self.assertIn(CLOUD_ACCOUNT_ACTIONS, types)
        texts = [button['text'] for button in types[CLOUD_ACCOUNT_ACTIONS]['buttons']]
        self.assertEqual(texts, [CLOUD_SAVE_BUTTON, CLOUD_SWITCH_BUTTON])

    def test_cloud_hides_per_account_flag(self):
        """云游戏用账号列表就够了, 那个"分别配置"开关没有意义, 隐藏掉避免误解。"""
        types = config_type_of(make_task(True))
        self.assertTrue(types[PER_ACCOUNT_CONFIGURATION].get('hidden'))
        self.assertNotIn('sub_configs', types[PER_ACCOUNT_CONFIGURATION])

    def test_cloud_account_config_is_standalone_button(self):
        types = config_type_of(make_task(True))
        self.assertEqual(types[ACCOUNT_CONFIGURATION].get('type'), 'button')
        self.assertNotIn(ACCOUNT_CONFIGURATION, types[PER_ACCOUNT_CONFIGURATION].get('sub_configs', {})
                         .get(True, []))

    def test_pc_hides_cloud_buttons_and_keeps_official_layout(self):
        types = config_type_of(make_task(False))
        self.assertNotIn(CLOUD_ACCOUNT_ACTIONS, types)
        self.assertEqual(types[PER_ACCOUNT_CONFIGURATION]['sub_configs'], {True: [ACCOUNT_CONFIGURATION]})

    def test_config_type_getter_does_not_expose_shared_dict(self):
        task = make_task(False)
        types = config_type_of(task)
        types[CLOUD_ACCOUNT_ACTIONS] = {'buttons': []}
        self.assertNotIn(CLOUD_ACCOUNT_ACTIONS, config_type_of(task))

    def test_is_cloud_device_without_executor(self):
        task = MultiAccountDailyTask.__new__(MultiAccountDailyTask)
        self.assertFalse(MultiAccountDailyTask._is_cloud_device(task))

    # --- First entry: the device list may not be refreshed yet, so the saved
    # --- device identifier decides (never browser_config: config.py defines it
    # --- for every installation, including pure PC ones).

    @staticmethod
    def _manager(preferred, browser_config, saved_preferred=''):
        import types
        return types.SimpleNamespace(
            get_preferred_device=lambda: preferred,
            browser_config=browser_config,
            config={'preferred': saved_preferred},
        )

    def _assert_cloud_device(self, preferred, browser_config, expected, saved_preferred=''):
        import types
        from unittest.mock import patch
        executor = types.SimpleNamespace(
            device_manager=self._manager(preferred, browser_config, saved_preferred))
        task = MultiAccountDailyTask.__new__(MultiAccountDailyTask)
        with patch.object(MultiAccountDailyTask, 'executor', new=executor):
            self.assertEqual(MultiAccountDailyTask._is_cloud_device(task), expected)

    def test_pc_user_with_browser_config_is_not_cloud(self):
        """PC 用户也有 browser 段: 设备没刷新时不能因此被当成云游戏。"""
        self._assert_cloud_device(None, {'url': 'https://x'}, False, saved_preferred='')

    def test_pc_device_saved_preferred_is_not_cloud(self):
        self._assert_cloud_device(None, {'url': 'https://x'}, False, saved_preferred='ABC123')

    def test_cloud_device_first_entry_falls_back_to_saved_preferred(self):
        self._assert_cloud_device(None, {'url': 'https://x'}, True, saved_preferred='browser')

    def test_cloud_device_preferred_browser(self):
        self._assert_cloud_device({'device': 'browser'}, {}, True)

    def test_cloud_device_preferred_windows_hides_buttons(self):
        self._assert_cloud_device({'device': 'windows'}, {'url': 'https://x'}, False,
                                  saved_preferred='browser')

    def test_cloud_device_no_browser_config_no_buttons(self):
        self._assert_cloud_device(None, None, False)

    def test_manager_without_config_is_not_cloud(self):
        import types
        from unittest.mock import patch
        manager = types.SimpleNamespace(get_preferred_device=lambda: None,
                                        browser_config={'url': 'https://x'})
        executor = types.SimpleNamespace(device_manager=manager)
        task = MultiAccountDailyTask.__new__(MultiAccountDailyTask)
        with patch.object(MultiAccountDailyTask, 'executor', new=executor):
            self.assertFalse(MultiAccountDailyTask._is_cloud_device(task))


class CloudRunDispatchTest(unittest.TestCase):

    def test_run_uses_cloud_branch(self):
        calls = []
        task = MultiAccountDailyTask.__new__(MultiAccountDailyTask)
        task._is_cloud_device = lambda: True
        task._run_cloud = lambda: calls.append('cloud')
        MultiAccountDailyTask.run(task)
        self.assertEqual(calls, ['cloud'])

    def test_run_uses_pc_branch(self):
        calls = []
        task = MultiAccountDailyTask.__new__(MultiAccountDailyTask)
        task._is_cloud_device = lambda: False
        task._run_cloud = lambda: calls.append('cloud')
        task.config = {PER_ACCOUNT_CONFIGURATION: True}
        task.run_task_by_class = lambda cls: calls.append(getattr(cls, '__name__', cls))
        MultiAccountDailyTask.run(task)
        self.assertEqual(calls, ['MultiAccountConfigTask'])


class CloudAccountRunTest(unittest.TestCase):
    """逐账号执行语义: 没配置任务 = 只登录, 一个账号都没配置 = 跑默认日常."""

    def _run_account(self, account, resolved=None):
        from contextlib import contextmanager
        from types import SimpleNamespace
        from unittest.mock import Mock, patch

        import src.task.MultiAccountDailyTask as module
        from src.task.DailyTask import DailyTask

        state = {'calls': [], 'isolated': None, 'config': None}
        task = MultiAccountDailyTask.__new__(MultiAccountDailyTask)
        task._cloud_reward_resumed = False
        task.log_info = Mock()
        task.tr = lambda text: text
        task._switch_cloud_profile = Mock()
        task.ensure_main = Mock()
        task.run_task_by_class = Mock(side_effect=state['calls'].append)
        task._executor = SimpleNamespace(get_all_tasks=lambda: ['all-tasks'])

        @contextmanager
        def isolated(tasks):
            state['isolated'] = tasks
            yield

        @contextmanager
        def account_config(saved_task, config):
            state['config'] = (saved_task, config)
            yield

        def run_recovery(_task, work, **_kwargs):
            return work()

        with patch.object(module, 'resolve_task', return_value=resolved) as resolve, \
                patch.object(module, 'run_with_cloud_recovery', side_effect=run_recovery), \
                patch.object(module, 'wait_cloud_ready', return_value=True), \
                patch.object(module, 'isolated_task_configs', isolated), \
                patch.object(module, 'account_task_config', account_config):
            MultiAccountDailyTask._run_cloud_account(task, account)
        state['DailyTask'] = DailyTask
        return state, resolve

    def test_configured_none_task_only_logs_in(self):
        state, resolve = self._run_account({'account_key': 'acc-a', 'task': None, 'config': {}})
        self.assertEqual(state['calls'], [])
        self.assertEqual(state['isolated'], ['all-tasks'])
        self.assertIsNone(state['config'])

    def test_no_accounts_runs_default_daily(self):
        state, resolve = self._run_account(None)
        self.assertEqual(state['calls'], [state['DailyTask']])
        resolve.assert_not_called()

    def test_account_task_runs_with_its_own_config(self):
        from types import SimpleNamespace
        resolved = SimpleNamespace(config={})
        state, resolve = self._run_account(
            {'account_key': 'acc-b', 'task': {'module': 'm', 'class': 'C'}, 'config': {'x': 1}},
            resolved=resolved)
        self.assertEqual(state['calls'], [SimpleNamespace])
        self.assertEqual(state['config'], (resolved, {'x': 1}))
        self.assertEqual(state['isolated'], ['all-tasks'])

    def test_cancel_is_recorded_as_cancelled(self):
        from types import SimpleNamespace
        from unittest.mock import Mock, patch

        import src.task.MultiAccountDailyTask as module
        from ok.task.exceptions import TaskDisabledException

        records = []

        class FakeStore:
            def load(self):
                return [{'account_key': 'acc-c', 'enabled': True, 'task': None, 'config': {}}]

            def record_result(self, account, status, message=''):
                records.append(status)

        task = MultiAccountDailyTask.__new__(MultiAccountDailyTask)
        task.log_info = Mock()
        task.log_warning = Mock()
        task.tr = lambda text: text
        task.info_set = Mock()
        task._executor = SimpleNamespace()
        task._account_store = Mock(return_value=FakeStore())
        task._run_cloud_account = Mock(side_effect=TaskDisabledException())

        with patch.object(module.WWOneTimeTask, 'run', lambda _self: None):
            with self.assertRaises(TaskDisabledException):
                MultiAccountDailyTask._run_cloud(task)
        self.assertEqual(records, ['cancelled'])


class CloudButtonGuardTest(unittest.TestCase):

    def _task(self, cloud):
        task = MultiAccountDailyTask.__new__(MultiAccountDailyTask)
        task._is_cloud_device = lambda: cloud
        task.messages = []
        task._cloud_message = lambda text, blocking=True: task.messages.append(text)
        return task

    def test_save_button_rejects_pc_device(self):
        task = self._task(False)
        MultiAccountDailyTask.save_cloud_login_state(task)
        self.assertTrue(task.messages)
        self.assertIn('云游戏', task.messages[0])

    def test_switch_button_rejects_pc_device(self):
        task = self._task(False)
        MultiAccountDailyTask.choose_cloud_account(task)
        self.assertIn('云游戏', task.messages[0])

    def test_save_button_without_browser(self):
        task = self._task(True)
        import src.task.MultiAccountDailyTask as module
        original = module.cloud_browser.get_browser_capture
        module.cloud_browser.get_browser_capture = lambda _task: None
        try:
            MultiAccountDailyTask.save_cloud_login_state(task)
        finally:
            module.cloud_browser.get_browser_capture = original
        self.assertIn('浏览器', task.messages[0])


class CloudButtonsRenderTest(unittest.TestCase):
    """按钮最终要由框架的 ButtonsEditor 渲染, 这里验证 spec 形状能被识别并真的生成按钮."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_cloud_actions_spec_resolves_to_button(self):
        from ok.core.config_schema import resolve_config_type
        types = config_type_of(make_task(True))
        self.assertEqual(resolve_config_type(types[CLOUD_ACCOUNT_ACTIONS], None), 'button')

    def test_cloud_actions_render_two_clickable_buttons(self):
        from PySide6.QtWidgets import QPushButton
        from ok.ui.qt.tasks.config_editors import ButtonsEditor

        clicked = []
        spec = {'buttons': [
            {'text': CLOUD_SAVE_BUTTON, 'callback': lambda: clicked.append('save')},
            {'text': CLOUD_SWITCH_BUTTON, 'callback': lambda: clicked.append('switch')},
        ]}
        editor = ButtonsEditor({CLOUD_ACCOUNT_ACTIONS: '账号操作'}, CLOUD_ACCOUNT_ACTIONS, spec['buttons'])
        buttons = editor.widget().findChildren(QPushButton) if hasattr(editor, 'widget') else []
        if not buttons:
            buttons = editor.findChildren(QPushButton)
        texts = [button.text() for button in buttons]
        self.assertIn(CLOUD_SAVE_BUTTON, texts)
        self.assertIn(CLOUD_SWITCH_BUTTON, texts)
        buttons[texts.index(CLOUD_SAVE_BUTTON)].click()
        self.assertEqual(clicked, ['save'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
