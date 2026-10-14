"""只读库存入口；未识别不是零库存。"""
from copy import deepcopy
from datetime import datetime, timezone
from src.task.BaseWWTask import BaseWWTask
from src.task.InventoryInspection import run_inventory_inspection


class InventoryInspectionTask(BaseWWTask):
    requires_initial_frame = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = '仓库检查'
        self.description = '只读取当前库存，不刷本、不补充体力；需要已进入游戏。'
        self.default_config = {}
        self.exit_after_task = False
        self.support_schedule_task = False

    def run(self):
        from src.task.InventoryMaintainTask import InventoryMaintainTask
        from src.task.InventoryMaintain import PLAN_KEY, HISTORY_KEY, store_value
        owner = self.executor.get_task_by_class(InventoryMaintainTask)
        selected = [row['id'] for row in owner.config.get(PLAN_KEY, [])] if owner else []
        result = run_inventory_inspection(self, selected_ids=selected or None)
        if owner:
            store_value(owner, HISTORY_KEY, {'observed_at': datetime.now(timezone.utc).isoformat(),
                'materials': deepcopy(result['materials'])})
        self.info_set('仓库检查', f'已核实{sum(r["status"] == "confirmed" for r in result["materials"])}项；非完整仓库')
        return result
