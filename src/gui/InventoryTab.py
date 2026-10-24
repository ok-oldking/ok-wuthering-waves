"""独立材料设置页，与编排器共用同一份任务配置。"""
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QHBoxLayout
from qfluentwidgets import BodyLabel, FluentIcon, PrimaryPushButton, PushButton
from ok.gui.widget.CustomTab import CustomTab
from src.gui.InventoryMaintainDialog import InventoryMaintainDialog
from src.task.InventoryMaintainTask import InventoryMaintainTask
from src.task.InventoryInspectionTask import InventoryInspectionTask


class InventoryTab(CustomTab):
    def __init__(self):
        super().__init__()
        self.task = None
        self.dialog = None
        self.summary = BodyLabel('先打开游戏进入大世界，再设置要保持的材料数量。')
        self.summary.setWordWrap(True)
        self.add_widget(self.summary)
        bar = QHBoxLayout()
        self.settings = PushButton('设置材料目标')
        self.inspect = PushButton('只查库存')
        self.start = PrimaryPushButton('补齐库存')
        self.stop = PushButton('停止')
        for button in (self.settings, self.inspect, self.start, self.stop):bar.addWidget(button)
        self.addLayout(bar)
        self.settings.clicked.connect(self.open_settings)
        self.inspect.clicked.connect(lambda: self.start_task(InventoryInspectionTask))
        self.start.clicked.connect(lambda: self.start_task(InventoryMaintainTask))
        self.stop.clicked.connect(self.stop_task)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(500)

    @property
    def name(self):return '库存保持'

    @property
    def icon(self):return FluentIcon.LIBRARY

    def editing_allowed(self):
        return (self.executor is not None and self.executor.current_task is None
                and not any(task.enabled for task in self.executor.onetime_tasks))

    def refresh(self):
        if self.executor is None:return
        self.task = self.get_task(InventoryMaintainTask)
        idle = self.editing_allowed() and self.task is not None
        for button in (self.settings,self.inspect,self.start):button.setEnabled(idle)
        current = self.executor.current_task
        self.stop.setEnabled(isinstance(current,(InventoryMaintainTask,InventoryInspectionTask)))
        if self.task:
            rows=self.task.config.get('Inventory Targets',[])
            self.summary.setText(f'已设置{len(rows)}项目标；按列表顺序补缺，不补体力。' +
                (' 上次扣波片尚未核实，补刷已锁定。' if self.task.config.get('_Inventory Farming Pending') else ''))

    def open_settings(self):
        self.refresh()
        if self.editing_allowed() and self.task:
            self.dialog = InventoryMaintainDialog(self)
            self.dialog.open()

    def start_task(self, cls):
        if self.editing_allowed():
            task=self.get_task(cls)
            if task:task.queue_run()

    def stop_task(self):
        current=self.executor.current_task if self.executor else None
        if isinstance(current,(InventoryMaintainTask,InventoryInspectionTask)):
            current.disable()
            current.unpause()
