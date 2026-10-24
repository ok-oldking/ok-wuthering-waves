"""独立库存保持入口，复用原生副本，不改变日常计划。"""
from src.task.BaseWWTask import BaseWWTask
from src.task.WWOneTimeTask import WWOneTimeTask
from src.task.InventoryMaintain import run_inventory_maintain


class InventoryMaintainTask(BaseWWTask):
    requires_initial_frame = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = '库存保持'
        self.description = '先设置材料目标；按列表补缺，达标或自然波片不足即结束。'
        self.default_config = {'Inventory Targets': [], '_Inventory Farming Pending': {},
                               '_Inventory Farming Stock': {}}
        self.exit_after_task = False
        self.support_schedule_task = False

    def _prepare_gameplay(self):
        manager = self.executor.device_manager
        manager.do_refresh(True)
        if not manager.capture_method or not manager.capture_method.connected():
            raise RuntimeError('请先打开游戏并进入大世界，再运行库存保持')
        WWOneTimeTask.run(self)
        if not self.in_team_and_world():
            raise RuntimeError('尚未进入大世界；不自动登录或修改其他任务')

    def run(self):
        return run_inventory_maintain(self)
