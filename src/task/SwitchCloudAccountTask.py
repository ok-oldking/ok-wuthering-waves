"""Manually switch the active 云鸣潮 account and launch its own browser.

The cloud game keeps a live session in the page, so merely overwriting cookies
in a running browser is unreliable.  This task saves the current account and
starts a fresh browser instance with the selected account's cookie profile.
"""

from src import cloud_browser
from src.cloud_recovery import FatalTaskError
from src.task.BaseCombatTask import BaseCombatTask
from src.task.WWOneTimeTask import WWOneTimeTask
from src.task.task_icons import task_icon

ACCOUNT_KEY = '要切换到的账号 ID'


class SwitchCloudAccountTask(WWOneTimeTask, BaseCombatTask):
    """Switch cookie profile and start a dedicated cloud-game browser."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = '🔄 切换云鸣潮账号（重启浏览器）'
        self.group_name = 'Multi-account'
        self.group_icon = task_icon('multi-account')
        self.icon = task_icon('multi-account')
        self.description = (
            '填写多账号配置里的账号 ID，保存当前账号后关闭旧浏览器，'
            '用该账号独立的 Cookie 登录态重新启动一个云游戏浏览器。'
            '使用前请先选择「云游戏」设备。'
        )
        self.default_config = {ACCOUNT_KEY: ''}
        self.config_description = {
            ACCOUNT_KEY: '多账号配置中的账号 ID；切换后会自动启动该账号的独立浏览器。',
        }

    def run(self):
        key = str(self.config.get(ACCOUNT_KEY, '') or '').strip()
        if not key:
            raise ValueError(self.tr('请先在任务配置中填写要切换到的账号 ID。'))

        current = cloud_browser.get_active_account()
        target = cloud_browser.profile_dir(key)
        self.info_set('当前账号', current or '(未设置)')
        self.info_set('目标账号', key)

        if not self.is_browser():
            # Still persist the pointer so the next cloud-device start uses it.
            cloud_browser.set_active_account(key)
            self.log_warning(self.tr(
                '当前不是云游戏设备：已切换账号配置，请切换为「云游戏」设备后重新连接。'))
            self.info_set('状态', '已切换配置，等待选择云游戏设备')
            return

        if current and current != key:
            if not cloud_browser.save_current(self):
                self.log_warning(self.tr('保存上一个账号的 Cookie 失败，仍将继续切换。'))

        if not cloud_browser.restart_browser(self, account_key=key):
            raise RuntimeError(self.tr(
                '使用账号 {account} 的 Cookie 启动浏览器失败，请检查浏览器/网络后重试。'
            ).format(account=key))

        # 新浏览器需要重新排队进入云游戏大世界。
        self.logged_in = False
        self.wait_cloud_game_ready(time_out=600)
        self.log_info(self.tr('已切换到账号 {account} 并进入云游戏。').format(account=key), notify=True)
        self.info_set('状态', '已切换并进入游戏')
        self.info_set('Cookie 目录', str(target))


from ok import run_task  # noqa: E402
from config import config  # noqa: E402

if __name__ == '__main__':
    run_task(config, task=SwitchCloudAccountTask, debug=True)
