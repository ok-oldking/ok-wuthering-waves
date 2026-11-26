"""云鸣潮账号浏览器 profile 隔离测试.

覆盖把「每个账号一份 Chromium profile」落到 okww 侧的目录切换实现:
- 切换账号时旧账号的登录态必须完整搬回它自己的目录, 不能丢;
- 换回来时登录态要原样回到 cache/playwright;
- 首次升级时浏览器里已登录的那份 profile 要被"认领", 而不是被空目录顶掉。
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import cloud_browser as cb  # noqa: E402


class CloudProfileSwapTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._cwd = os.getcwd()
        os.chdir(self.tmp.name)
        cb.LIVE_PROFILE = Path('cache') / 'playwright'

    def tearDown(self):
        os.chdir(self._cwd)
        self.tmp.cleanup()

    def _write_cookie(self, profile: Path, value: str):
        profile.mkdir(parents=True, exist_ok=True)
        (profile / 'Cookies').write_text(value, encoding='utf-8')

    def _read_cookie(self, profile: Path):
        return (profile / 'Cookies').read_text(encoding='utf-8')

    def test_first_prepare_creates_live_profile(self):
        swapped = cb.prepare_live_profile('acc-a')
        self.assertFalse(swapped)
        self.assertTrue(cb.LIVE_PROFILE.is_dir())
        self.assertEqual(cb.live_profile_account(), 'acc-a')
        self.assertEqual(cb.get_active_account(), 'acc-a')
        self.assertTrue(cb.profile_matches('acc-a'))

    def test_switch_keeps_previous_login_state(self):
        cb.prepare_live_profile('acc-a')
        self._write_cookie(cb.LIVE_PROFILE, 'a-cookie')

        cb.prepare_live_profile('acc-b')
        # 旧账号的 profile 被整体搬到自己的目录, 不是删掉。
        self.assertEqual(self._read_cookie(cb.profile_dir('acc-a')), 'a-cookie')
        self.assertEqual(cb.live_profile_account(), 'acc-b')
        self.assertFalse((cb.LIVE_PROFILE / 'Cookies').exists())

        # 换回来时登录态原样回到 live 目录。
        cb.prepare_live_profile('acc-a')
        self.assertEqual(self._read_cookie(cb.LIVE_PROFILE), 'a-cookie')
        self.assertEqual(cb.live_profile_account(), 'acc-a')

    def test_prepare_same_account_does_not_swap(self):
        cb.prepare_live_profile('acc-a')
        self._write_cookie(cb.LIVE_PROFILE, 'keep-me')
        self.assertTrue(cb.prepare_live_profile('acc-a'))
        self.assertEqual(self._read_cookie(cb.LIVE_PROFILE), 'keep-me')

    def test_adopt_unmarked_profile_only_once(self):
        self._write_cookie(cb.LIVE_PROFILE, 'logged-in')
        self.assertTrue(cb.adopt_live_profile('acc-a'))
        self.assertTrue(cb.profile_matches('acc-a'))
        # 已经有归属的 profile 不能被别的账号再次认领。
        self.assertFalse(cb.adopt_live_profile('acc-b'))
        self.assertTrue(cb.profile_matches('acc-a'))

    def test_adopt_requires_live_profile(self):
        self.assertFalse(cb.adopt_live_profile('acc-a'))

    def test_active_account_roundtrip(self):
        cb.set_active_account('acc-x')
        self.assertEqual(cb.get_active_account(), 'acc-x')
        self.assertTrue(cb.profile_dir('acc-x').is_dir())
        cb.set_active_account(None)
        self.assertIsNone(cb.get_active_account())

    def test_safe_account_name_is_unique(self):
        names = {cb.safe_account_name(key) for key in ('a/b', 'a\\b', 'a:b', 'a b', 'a_b')}
        self.assertEqual(len(names), 5)
        self.assertTrue(cb.safe_account_name('').startswith('account-'))

    def test_save_without_browser_returns_false(self):
        self.assertFalse(cb.save_current(None))

    def test_restart_without_device_manager_returns_false(self):
        class FakeTask:
            executor = None

        self.assertFalse(cb.restart_browser(FakeTask()))

    def test_migrate_legacy_moves_live_profile(self):
        self._write_cookie(cb.LIVE_PROFILE, 'old-login')
        target = cb.migrate_legacy_profile('acc-m')
        self.assertEqual(self._read_cookie(target), 'old-login')
        # 迁移 = 把当前登录态收进账号目录, live 目录交给下次切换重建。
        self.assertFalse(cb.LIVE_PROFILE.exists())
        cb.prepare_live_profile('acc-m')
        self.assertEqual(self._read_cookie(cb.LIVE_PROFILE), 'old-login')
        self.assertTrue(cb.profile_matches('acc-m'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
