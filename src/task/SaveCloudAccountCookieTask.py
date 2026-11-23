"""Manually save the current cloud-game browser login state for an account.

Use this after logging into an account in the browser, or to refresh an
account's cookie profile without running the whole multi-account task.
"""

from src import cloud_browser
from src.task.BaseCombatTask import BaseCombatTask
from src.task.WWOneTimeTask import WWOneTimeTask
from src.task.task_icons import task_icon

ACCOUNT_KEY = '账号 ID（留空=当前账号）'


class SaveCloudAccountCookieTask(WWOneTimeTask, BaseCombatTask):
    """Save the live browser cookies/localStorage into an account profile."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = '💾 保存云鸣潮账号 Cookie'
        self.group_name = 'Multi-account'
        self.group_icon = task_icon('multi-account')
        self.icon = task_icon('multi-account')
        self.description = (
            '把当前云游戏浏览器的登录态保存到指定账号（多账号配置里的账号 ID）。'
            '留空则保存到当前活动账号。'
        )
        self.default_config = {ACCOUNT_KEY: ''}
        self.config_description = {
            ACCOUNT_KEY: '多账号配置中的账号 ID；留空表示当前活动账号。',
        }

    def run(self):
        if not self.is_browser():
            raise ValueError(self.tr('请先选择「云游戏」设备后运行此任务。'))

        key = str(self.config.get(ACCOUNT_KEY, '') or '').strip()
        if key:
            cloud_browser.set_active_account(key)
        account = cloud_browser.get_active_account()
        if not account:
            raise ValueError(self.tr('尚未选择账号，请在任务配置中填写账号 ID。'))

        if not cloud_browser.save_current(self):
            raise RuntimeError(self.tr('没有检测到运行中的云游戏浏览器，无法保存 Cookie。'))

        path = cloud_browser.storage_state_path(account)
        self.log_info(self.tr('已保存账号 {account} 的 Cookie 到 {path}').format(
            account=account, path=path), notify=True)
        self.info_set('账号', account)
        self.info_set('Cookie 文件', str(path))


from ok import run_task  # noqa: E402
from config import config  # noqa: E402

if __name__ == '__main__':
    run_task(config, task=SaveCloudAccountCookieTask, debug=True)
