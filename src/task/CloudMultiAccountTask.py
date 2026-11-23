"""Cloud (browser) counterpart of the multi-account daily task.

The PC-client task logs into the next account through the native login dialog.
The cloud game stores its login state in browser cookies, so this task follows
the same run pattern as MultiAccountConfigTask (plan resolution, isolated
configs, per-account result tracking) but swaps the cookie profile and waits
for the cloud game to finish entering instead of clicking a login row.

Select the 云游戏 device before running this task.
"""

from ok.task.exceptions import TaskDisabledException

from src import cloud_browser
from src.cloud_recovery import FatalTaskError, run_with_cloud_recovery
from src.task.BaseCombatTask import BaseCombatTask
from src.task.MultiAccountDailyTask import (
    ACCOUNT_CONFIGURATION, PER_ACCOUNT_CONFIGURATION, MultiAccountDailyTask,
)
from src.task.WWOneTimeTask import WWOneTimeTask
from src.task.account.MultiAccountConfigStore import (
    MultiAccountConfigStore, display_account, resolve_task, validate_accounts,
)
from src.task.account.RuntimeTaskConfig import account_task_config, isolated_task_configs
from src.task.task_icons import task_icon

class CloudMultiAccountTask(MultiAccountDailyTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = '☁️ 多账号每日（云鸣潮）'
        self.group_name = 'Multi-account'
        self.group_icon = task_icon('multi-account')
        self.icon = task_icon('multi-account')
        self.description = (
            '云游戏专用：点「配置账号」为每个账号单独选择任务并设置各自的复选框开关，'
            '运行时按顺序切换各账号的浏览器 Cookie 登录态。请先选择云游戏设备。'
        )
        # 直接展开配置入口：用户反馈"不能自定义每账号配置"多半是因为按钮
        # 藏在这个默认关闭的开关后面。run() 已覆盖，此值仅控制 UI 显示。
        self.default_config[PER_ACCOUNT_CONFIGURATION] = True
        self.config_description[PER_ACCOUNT_CONFIGURATION] = (
            '显示「配置账号」按钮：为每个账号单独选择任务并设置各自的复选框开关。'
        )
        self.config_description[ACCOUNT_CONFIGURATION] = (
            '编辑账号顺序、启用的账号、每个账号的任务及该任务的全部开关。'
        )
        self.support_schedule_task = True

    def run(self):
        if not self.is_browser():
            raise FatalTaskError(self.tr('请先选择「云游戏」设备后运行此任务。'))

        store = MultiAccountConfigStore(self.executor.config_folder)
        accounts = store.load()
        validate_accounts(accounts, self.executor)
        if not accounts:
            raise ValueError(self.tr('请先在「分别配置账号」中添加并保存账号。'))
        # Resolve the whole plan before sending any input to the game.
        plan = [(account, resolve_task(self.executor, account['task']))
                for account in accounts if account.get('enabled', True)]
        self.info_set('全部配置账号', [display_account(a['account_key']) for a in accounts])
        if not plan:
            self.info_set('状态', '没有启用的账号')
            return

        def record_result(account, status, message=''):
            try:
                store.record_result(account, status, message)
            except (OSError, ValueError) as error:
                self.log_warning(self.tr('Failed to save account run history: {error}').format(error=error))

        completed = []
        self.info_set('状态', '执行中')
        self.info_set('已完成', completed.copy())
        try:
            # Reset for every account, including configs of indirectly called tasks.
            for index, (account, task) in enumerate(plan):
                key = account['account_key']
                try:
                    self._target_account_key = key
                    with isolated_task_configs(self.executor.get_all_tasks()):
                        if index == 0:
                            WWOneTimeTask.run(self)
                        self.info_set('当前账号', display_account(key))
                        self.info_set('执行任务', self.tr(task.name) if task else '无')

                        # 云游戏的会话留在页面内存里, 只替换 cookie 不会真正换号.
                        # 每个账号单独启动一个浏览器: 保存旧账号 → 关闭旧窗口 →
                        # 用该账号自己的 profile 重新打开, 才能避免"切换不成功".
                        if not cloud_browser.restart_browser(self, account_key=key):
                            raise RuntimeError(self.tr(
                                '无法为账号 {account} 启动独立浏览器，请检查浏览器是否可用。'
                            ).format(account=display_account(key)))

                        # Bind loop variables explicitly: a plain closure would
                        # see them change on the next iteration (S1515).
                        def execute_account(account=account, task=task):
                            # 出错后整个账号流程会重跑: 先等待云端真正进入游戏,
                            # 否则点击会落在加载页/云游戏首页上。
                            self.logged_in = False
                            self.wait_cloud_game_ready(time_out=600)

                            if task is None:
                                self.log_info(self.tr('Login successful; task is set to None, skipping.'))
                            else:
                                # 按每个账号自己勾选的配置执行(含刷梦魇巢穴/4C)。
                                with account_task_config(task, account['config']):
                                    self.run_task_by_class(type(task))

                            # Return to the cloud game home state before the next swap.
                            self.ensure_main(time_out=100)

                        # 云游戏出错时刷新页面、重新进入游戏并从头跑该账号,
                        # 不再因为一次识别失败而中断后面所有账号。
                        run_with_cloud_recovery(
                            self, execute_account, name=display_account(key),
                            wait_ready=False)
                except TaskDisabledException:
                    record_result(account, 'cancelled', '任务已停止')
                    raise
                except Exception as error:
                    record_result(account, 'failed', str(error))
                    raise
                record_result(account, 'success')
                completed.append(display_account(key))
                self.info_set('已完成', completed.copy())
            self.info_set('状态', '全部完成')
        except TaskDisabledException:
            self.info_set('状态', '已停止')
            raise
        except Exception as error:
            self.info_set('状态', '执行失败')
            self.info_set('Error', str(error))
            raise
        finally:
            cloud_browser.save_current(self)


from ok import run_task  # noqa: E402
from config import config  # noqa: E402

if __name__ == '__main__':
    run_task(config, task=CloudMultiAccountTask, debug=True)
