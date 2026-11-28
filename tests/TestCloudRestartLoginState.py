"""重启任务/错误恢复时不能把云鸣潮浏览器切到别的账号 profile.

事故场景: 活动账号是 1351840，任务出错后自动恢复调用 restart_browser 时
没带 account_key，代码就猜成 default —— 磁盘上恰好有一个旧的 default
登录态，结果"重启任务后账号掉了"。这里锁住这条路径，并覆盖 profile
目录被 Chromium 短暂锁住时不能再静默删文件。
"""

import asyncio
import errno
import importlib.util
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load_from_root(relative: str, name: str):
    """按文件路径加载被测模块，避免别的测试把 src.* 缓存指向 working 目录。"""
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cb = _load_from_root('src/cloud_browser.py', '_cloud_browser_restart_test')


class BrowserCaptureMethod:
    """最小替身：restart_browser / save_current 只用到这几个成员。"""

    def __init__(self, config=None, exit_event=None, global_config=None):
        self.config = config or {'url': 'https://example.test'}
        self.browser = FakeContext()
        self.closed = False
        self.started = False

    def close(self):
        self.closed = True

    def start_browser(self):
        self.started = True

    def connected(self):
        return True

    def run_in_loop(self, coroutine):
        return asyncio.run(coroutine)


class BrowserInteraction:
    def __init__(self, capture):
        self.capture = capture


class FakeContext:
    async def storage_state(self, path=None):
        Path(path).write_text('saved-state', encoding='utf-8')


def make_task(capture=None):
    manager = types.SimpleNamespace(
        capture_method=capture or BrowserCaptureMethod(),
        browser_config={'url': 'https://example.test'},
        exit_event=None,
        global_config=None,
        interaction=None,
    )
    return types.SimpleNamespace(executor=types.SimpleNamespace(device_manager=manager)), manager


class RestartLoginStateTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._cwd = os.getcwd()
        os.chdir(self.tmp.name)
        cb.LIVE_PROFILE = Path('cache') / 'playwright'

        # restart_browser 里是函数内 import，工作区不一定有完整的 ok 包，
        # 注入最小模块即可（不改变被测代码）。
        self._saved_modules = {}
        modules = {
            'ok': types.ModuleType('ok'),
            'ok.device': types.ModuleType('ok.device'),
            'ok.device.capture': types.ModuleType('ok.device.capture'),
            'ok.device.interaction': types.ModuleType('ok.device.interaction'),
        }
        modules['ok.device.capture'].BrowserCaptureMethod = BrowserCaptureMethod
        modules['ok.device.interaction'].BrowserInteraction = BrowserInteraction
        for name, module in modules.items():
            self._saved_modules[name] = sys.modules.get(name)
            sys.modules[name] = module

    def tearDown(self):
        for name, module in self._saved_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
        os.chdir(self._cwd)
        self.tmp.cleanup()

    @staticmethod
    def cookie(profile: Path) -> str:
        return (profile / 'Cookies').read_text(encoding='utf-8')

    @staticmethod
    def write_cookie(profile: Path, value: str) -> None:
        profile.mkdir(parents=True, exist_ok=True)
        (profile / 'Cookies').write_text(value, encoding='utf-8')

    def test_resolve_account_prefers_live_marker(self):
        cb.prepare_live_profile('acc-a')
        cb.set_active_account('acc-b')
        self.assertEqual(cb.resolve_account(), 'acc-a')
        self.assertEqual(cb.resolve_account('acc-c'), 'acc-c')

    def test_restart_without_account_keeps_active_profile(self):
        """错误恢复不带账号时，必须重启当前账号而不是 default。"""
        self.write_cookie(cb.LIVE_PROFILE, 'a-cookie')
        cb.prepare_live_profile('acc-a')
        self.write_cookie(cb.LIVE_PROFILE, 'a-cookie')
        cb.set_active_account('acc-a')
        # 真实环境里这个旧 profile 是存在的，不能误切过去。
        self.write_cookie(cb.profile_dir('default'), 'old-default-cookie')

        task, manager = make_task()
        self.assertTrue(cb.restart_browser(task, save_previous=False))

        self.assertEqual(cb.live_profile_account(), 'acc-a')
        self.assertEqual(cb.get_active_account(), 'acc-a')
        self.assertEqual(self.cookie(cb.LIVE_PROFILE), 'a-cookie')
        self.assertEqual(self.cookie(cb.profile_dir('default')), 'old-default-cookie')
        self.assertTrue(manager.capture_method.started)
        self.assertIsNotNone(manager.capture_method)

    def test_save_current_uses_live_owner_not_stale_active(self):
        """cloud_launch 可能先把 active 写成 X，此时 Cookie 仍属于 live 的 A。"""
        cb.prepare_live_profile('acc-a')
        cb.set_active_account('acc-b')
        capture = BrowserCaptureMethod()
        task, _ = make_task(capture)
        self.assertTrue(cb.save_current(task))
        self.assertTrue(cb.storage_state_path('acc-a').exists())
        self.assertFalse(cb.storage_state_path('acc-b').exists())

    def test_profile_swap_waits_for_lock_instead_of_deleting(self):
        """目录暂时被浏览器锁住时应重试，不能把 Cookie 文件删掉。"""
        cb.prepare_live_profile('acc-a')
        self.write_cookie(cb.LIVE_PROFILE, 'a-cookie')
        real_replace = os.replace
        attempts = {'n': 0}

        def flaky_replace(src, dst):
            if Path(src) == cb.LIVE_PROFILE and attempts['n'] < 2:
                attempts['n'] += 1
                error = OSError('profile still locked')
                error.errno = errno.EACCES
                raise error
            return real_replace(src, dst)

        with patch.object(cb.os, 'replace', side_effect=flaky_replace), \
             patch.object(cb.time, 'sleep', return_value=None):
            cb.prepare_live_profile('acc-b')

        self.assertGreaterEqual(attempts['n'], 2)
        self.assertEqual(cb.live_profile_account(), 'acc-b')
        self.assertEqual(self.cookie(cb.profile_dir('acc-a')), 'a-cookie')
        self.assertFalse(cb.LIVE_PROFILE.with_name('playwright.retired').exists())

    def test_profile_swap_fails_loudly_when_permanently_locked(self):
        """一直锁住时宁可报错，也不能用半个 profile 继续启动浏览器。"""
        cb.prepare_live_profile('acc-a')
        self.write_cookie(cb.LIVE_PROFILE, 'a-cookie')

        def locked(*_args, **_kwargs):
            error = OSError('profile locked')
            error.errno = errno.EACCES
            raise error

        with patch.object(cb.os, 'replace', side_effect=locked), \
             patch.object(cb.time, 'sleep', return_value=None):
            with self.assertRaises(RuntimeError):
                cb.prepare_live_profile('acc-b')

        self.assertEqual(cb.live_profile_account(), 'acc-a')
        self.assertEqual(self.cookie(cb.LIVE_PROFILE), 'a-cookie')


class RecoveryPassesAccountTest(unittest.TestCase):
    """cloud_recovery 的错误恢复必须把当前账号显式传给 restart_browser。"""

    def test_refresh_passes_resolved_account(self):
        exceptions = types.ModuleType('ok.task.exceptions')
        exceptions.FinishedException = type('FinishedException', (Exception,), {})
        exceptions.TaskDisabledException = type('TaskDisabledException', (Exception,), {})
        src_pkg = types.ModuleType('src')
        src_pkg.__path__ = [str(ROOT / 'src')]
        src_pkg.cloud_browser = cb

        with patch.dict(sys.modules, {
            'ok': types.ModuleType('ok'),
            'ok.task': types.ModuleType('ok.task'),
            'ok.task.exceptions': exceptions,
            'src': src_pkg,
            'src.cloud_browser': cb,
        }):
            recovery = _load_from_root('src/cloud_recovery.py', '_cloud_recovery_restart_test')
            task = types.SimpleNamespace(
                log_warning=lambda *a, **kw: None,
                log_error=lambda *a, **kw: None,
                tr=lambda text: text,
                sleep=lambda *_: None,
                next_frame=lambda: None,
                logged_in=True,
            )
            calls = []
            with patch.object(recovery.cloud_browser, 'resolve_account', return_value='acc-a'), \
                 patch.object(recovery.cloud_browser, 'restart_browser',
                              side_effect=lambda t, **kw: calls.append(kw) or True) as restart:
                recovery.refresh_cloud_game(task, wait_ready=False)

        restart.assert_called_once()
        self.assertEqual(calls[0]['account_key'], 'acc-a')
        self.assertFalse(calls[0]['save_previous'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
