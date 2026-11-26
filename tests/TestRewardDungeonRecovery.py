"""云鸣潮战斗奖励副本出错后「现场续打」的回归测试.

覆盖：出错时是否在副本的探测、浏览器重启后续打/脱战/按 F 领奖、成功后
跳过 ensure_main 的重进路径，以及用户配置可关闭该功能。
"""

import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load_from_root(relative: str, name: str):
    """按文件路径加载被测模块，避免其他测试把 src.* 缓存指向 working 目录。"""
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rdr = _load_from_root('src/reward_dungeon_recovery.py', '_reward_dungeon_recovery_test')


class FakeTask:
    """最小任务替身：只实现续打模块用到的只读探测与按键接口。"""

    def __init__(self, **state):
        self.calls = []
        self.logs = []
        self.browser = state.get('browser', True)
        self.realm = state.get('realm', True)
        self.world = state.get('world', False)
        self.combat = state.get('combat', False)
        self.health = state.get('health', False)
        self.claim_text = state.get('claim_text', False)
        self.treasure = state.get('treasure', False)
        self.f_prompt = state.get('f_prompt', False)
        self.stamina_sign = state.get('stamina_sign', False)

    # --- 探测 ---
    def is_browser(self):
        return self.browser

    def in_realm(self):
        return self.realm

    def in_world(self):
        return self.world

    def in_combat(self):
        return self.combat

    def check_health_bar(self):
        return self.health

    def find_f_with_claim_text(self):
        return self.claim_text

    def find_treasure_icon(self):
        return self.treasure

    def find_f_with_text(self):
        return self.f_prompt

    def has_claim_stamina(self):
        return self.stamina_sign

    # --- 动作 ---
    def sleep(self, seconds):
        self.calls.append(('sleep', seconds))

    def next_frame(self):
        self.calls.append(('next_frame',))

    def combat_once(self, **kwargs):
        self.calls.append(('combat_once', kwargs))
        self.combat = False
        self.health = False

    def send_key(self, key, **kwargs):
        self.calls.append(('send_key', key))

    def pick_f(self, **kwargs):
        self.calls.append(('pick_f', kwargs))

    def walk_to_treasure(self, **kwargs):
        self.calls.append(('walk_to_treasure', kwargs))
        self.calls.append(('send_key', 'f'))

    def wait_click_feature(self, *args, **kwargs):
        self.calls.append(('wait_click_feature', args))

    def wait_in_team_and_world(self, **kwargs):
        self.calls.append(('wait_in_team_and_world', kwargs))
        self.realm = False
        self.world = True

    def log_info(self, message, notify=False):
        self.logs.append(('info', message))

    def log_warning(self, message, notify=False):
        self.logs.append(('warning', message))


class ProbeTest(unittest.TestCase):

    def test_non_cloud_device_never_resumes(self):
        task = FakeTask(browser=False, combat=True)
        self.assertFalse(rdr.in_reward_dungeon(task))
        self.assertFalse(rdr.resume_reward_dungeon(task, settle_timeout=0.1))

    def test_realm_without_combat_or_loot_is_not_a_reward_dungeon(self):
        self.assertFalse(rdr.in_reward_dungeon(FakeTask(realm=True)))
        self.assertFalse(rdr.in_reward_dungeon(FakeTask(realm=False, combat=True)))

    def test_combat_health_claim_and_treasure_all_count(self):
        for state in ({'combat': True}, {'health': True}, {'claim_text': True},
                      {'treasure': True}, {'f_prompt': True}, {'stamina_sign': True}):
            with self.subTest(state=state):
                self.assertTrue(rdr.in_reward_dungeon(FakeTask(realm=True, **state)))

    def test_wait_gives_up_when_back_in_open_world(self):
        task = FakeTask(realm=False, world=True)
        self.assertFalse(rdr.wait_for_dungeon(task, timeout=5))
        self.assertNotIn('next_frame', [call[0] for call in task.calls])

    def test_wait_times_out_without_hanging(self):
        task = FakeTask(realm=False)
        self.assertFalse(rdr.wait_for_dungeon(task, timeout=0.2))


class ResumeTest(unittest.TestCase):

    def test_resume_combat_wait_end_claim_and_leave(self):
        task = FakeTask(combat=True, claim_text=True)
        result = rdr.resume_reward_dungeon(
            task, settle_timeout=0.1, combat_timeout=1, reward_timeout=0.5)

        self.assertTrue(result)
        names = [call[0] for call in task.calls]
        self.assertIn('combat_once', names)
        self.assertIn('send_key', names)
        self.assertIn('wait_click_feature', names)
        self.assertIn('wait_in_team_and_world', names)
        self.assertLess(names.index('combat_once'), names.index('send_key'))
        self.assertFalse(task.realm)
        self.assertTrue(any('按 F 领取奖励' in message for _, message in task.logs))

    def test_resume_only_claims_when_combat_already_over(self):
        task = FakeTask(treasure=True)
        self.assertTrue(rdr.resume_reward_dungeon(
            task, settle_timeout=0.1, reward_timeout=0.5))
        names = [call[0] for call in task.calls]
        self.assertNotIn('combat_once', names)
        self.assertIn('walk_to_treasure', names)
        self.assertIn(('send_key', 'f'), task.calls)

    def test_plain_f_prompt_picks_up_without_claim_text(self):
        task = FakeTask(f_prompt=True)
        self.assertTrue(rdr.resume_reward_dungeon(task, settle_timeout=0.1))
        self.assertIn(('pick_f', {'handle_claim': False}), task.calls)

    def test_leave_failure_still_returns_true(self):
        """领奖后即使没成功退出，也算接管过现场，上层不应再重进。"""
        task = FakeTask(combat=True)
        task.wait_in_team_and_world = lambda **kw: task.calls.append(('no_exit',))
        self.assertTrue(rdr.resume_reward_dungeon(
            task, settle_timeout=0.1, combat_timeout=1, reward_timeout=0.3))
        self.assertTrue(any('未能确认退出副本' in message for _, message in task.logs))


class RecoveryIntegrationTest(unittest.TestCase):
    """cloud_recovery 在出错重启后必须先走续打，再决定是否重跑任务。"""

    def _load_recovery(self, reward_module):
        exceptions = types.ModuleType('ok.task.exceptions')
        exceptions.FinishedException = type('FinishedException', (Exception,), {})
        exceptions.TaskDisabledException = type('TaskDisabledException', (Exception,), {})
        src_pkg = types.ModuleType('src')
        src_pkg.__path__ = [str(ROOT / 'src')]
        src_pkg.cloud_browser = types.SimpleNamespace(
            resolve_account=lambda: None,
            restart_browser=lambda *a, **kw: True,
            restart_page=lambda *a: True,
            reload_page=lambda *a: True,
        )
        src_pkg.reward_dungeon_recovery = reward_module
        with patch.dict(sys.modules, {
            'ok': types.ModuleType('ok'),
            'ok.task': types.ModuleType('ok.task'),
            'ok.task.exceptions': exceptions,
            'src': src_pkg,
            'src.cloud_browser': src_pkg.cloud_browser,
            'src.reward_dungeon_recovery': reward_module,
        }):
            return _load_from_root('src/cloud_recovery.py', '_cloud_recovery_reward_test')

    @staticmethod
    def _task(**config):
        return types.SimpleNamespace(
            name='测试账号', config=config, is_browser=lambda: True,
            log_warning=lambda *a, **kw: None, log_error=lambda *a, **kw: None,
            log_info=lambda *a, **kw: None, info_set=lambda *a, **kw: None,
            tr=lambda text: text, sleep=lambda *_: None, next_frame=lambda: None,
            ensure_main=Mock(), logged_in=True,
        )

    def test_error_in_dungeon_resumes_and_skips_ensure_main(self):
        reward = types.SimpleNamespace(in_reward_dungeon=Mock(return_value=True),
                                       resume_reward_dungeon=Mock(return_value=True))
        recovery = self._load_recovery(reward)
        task = self._task()
        runner = Mock(side_effect=[RuntimeError('识别失败'), 'done'])

        with patch.object(recovery.cloud_browser, 'restart_browser', return_value=True):
            self.assertEqual(recovery.run_with_cloud_recovery(task, runner), 'done')

        self.assertEqual(runner.call_count, 2)
        reward.resume_reward_dungeon.assert_called_once()
        task.ensure_main.assert_not_called()  # 没被 ensure_main 踢出副本
        self.assertTrue(task._cloud_reward_resumed)

    def test_error_outside_dungeon_keeps_original_flow(self):
        reward = types.SimpleNamespace(in_reward_dungeon=Mock(return_value=False),
                                       resume_reward_dungeon=Mock(return_value=False))
        recovery = self._load_recovery(reward)
        task = self._task()
        runner = Mock(side_effect=[RuntimeError('识别失败'), 'done'])

        with patch.object(recovery.cloud_browser, 'restart_browser', return_value=True):
            self.assertEqual(recovery.run_with_cloud_recovery(task, runner), 'done')

        reward.resume_reward_dungeon.assert_not_called()
        task.ensure_main.assert_called_once()
        self.assertFalse(task._cloud_reward_resumed)

    def test_config_can_disable_dungeon_resume(self):
        reward = types.SimpleNamespace(in_reward_dungeon=Mock(return_value=True),
                                       resume_reward_dungeon=Mock(return_value=True))
        recovery = self._load_recovery(reward)
        task = self._task(**{'Cloud Resume Reward Dungeon': False})
        runner = Mock(side_effect=[RuntimeError('识别失败'), 'done'])

        with patch.object(recovery.cloud_browser, 'restart_browser', return_value=True):
            self.assertEqual(recovery.run_with_cloud_recovery(task, runner), 'done')

        reward.in_reward_dungeon.assert_not_called()
        reward.resume_reward_dungeon.assert_not_called()
        task.ensure_main.assert_called_once()

    def test_work_does_not_wait_again_after_resume(self):
        """MultiAccountDailyTask.work 在续打成功后不能重复 ensure_main。"""
        source = (ROOT / 'src/task/MultiAccountDailyTask.py').read_text(encoding='utf-8')
        self.assertIn("if getattr(self, '_cloud_reward_resumed', False):", source)
        self.assertIn("wait_cloud_ready(self, time_out=600)", source)

    def test_same_error_three_times_stops_instead_of_restarting(self):
        """同一个错误连续出现 3 次必须提前停止，而不是无限刷新页面。"""
        reward = types.SimpleNamespace(in_reward_dungeon=Mock(return_value=False),
                                       resume_reward_dungeon=Mock(return_value=False))
        recovery = self._load_recovery(reward)
        task = self._task()
        runner = Mock(side_effect=[RuntimeError('同一处失败')] * 3)

        with patch.object(recovery.cloud_browser, 'restart_browser', return_value=True):
            with self.assertRaises(RuntimeError):
                recovery.run_with_cloud_recovery(task, runner)

        self.assertEqual(runner.call_count, 3)

    def test_different_errors_reset_repeat_counter(self):
        """不同错误交替出现时不触发"相同错误"提前停止，走重启次数上限。"""
        reward = types.SimpleNamespace(in_reward_dungeon=Mock(return_value=False),
                                       resume_reward_dungeon=Mock(return_value=False))
        recovery = self._load_recovery(reward)
        task = self._task()
        runner = Mock(side_effect=[RuntimeError('错误A'), RuntimeError('错误B'),
                                   RuntimeError('错误A')])

        with patch.object(recovery.cloud_browser, 'restart_browser', return_value=True):
            with self.assertRaises(RuntimeError):
                recovery.run_with_cloud_recovery(task, runner, max_restarts=2)

        self.assertEqual(runner.call_count, 3)


if __name__ == '__main__':
    unittest.main(verbosity=2)
