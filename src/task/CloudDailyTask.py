"""云鸣潮单账号每日任务.

配置界面与 ``DailyTask`` 完全一致(继承其全部复选框开关与任务流程), 区别仅在
于运行在云游戏浏览器上: 启动时等待云端真正进入大世界, 并使用你自己勾选的
全部开关(包括刷梦魇巢穴/4C 声骸). 出错会自动重启浏览器并重跑.

Select the 云游戏 device before running this task.
"""

from src.cloud_recovery import FatalTaskError, run_with_cloud_recovery
from src.task.DailyTask import DailyTask
from src.task.task_icons import task_icon


class CloudDailyTask(DailyTask):
    """DailyTask running on the cloud-game browser, with identical switches."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = '☁️ 每日任务（云鸣潮）'
        self.group_name = 'Daily Activities'
        self.group_icon = task_icon('category-daily')
        self.description = (
            '云游戏专用：配置开关与每日任务完全一致，使用当前浏览器登录态跑每日+周常。'
            '刷梦魇巢穴/4C 等开关按你勾选的配置执行；启动时会等待云端进入游戏。'
            '请先选择「云游戏」设备。'
        )

    def run(self):
        if not self.is_browser():
            raise FatalTaskError(self.tr('请先选择「云游戏」设备后运行此任务。'))

        # 必须先把 super().run 绑出来: 嵌套函数里没有 self 形参,
        # 直接写零参数 super() 会抛 "super(): no arguments".
        daily_run = super().run

        def runner():
            # 出错重启后也会重新走一遍: 耐心等到云端真正进大世界,
            # 再执行与本地每日完全相同的任务流程 (DailyTask.run)。
            self.logged_in = False
            self.wait_cloud_game_ready(time_out=600)
            daily_run()

        # 云游戏出错通常是页面卡住/断线: 重启浏览器(失败则刷新页面)并从头重跑,
        # 而不是像本地客户端那样直接停止。runner 自己会等待进入游戏,
        # 所以这里不必再等一次。
        run_with_cloud_recovery(self, runner, name=self.name, wait_ready=False)


from ok import run_task  # noqa: E402
from config import config  # noqa: E402

if __name__ == '__main__':
    run_task(config, task=CloudDailyTask, debug=True)
