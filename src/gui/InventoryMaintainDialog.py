"""Editable ordered stock targets; historical numbers never authorize farming."""
from copy import deepcopy
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QHBoxLayout,
                              QListWidgetItem, QVBoxLayout)
from qfluentwidgets import BodyLabel, ComboBox, ListWidget, PrimaryPushButton, PushButton, SpinBox, isDarkTheme
from src.task.InventoryMaintain import (PLAN_KEY, HISTORY_KEY, PENDING_KEY, ROUTES,
    material_options, validate_targets, store_value)


class InventoryMaintainDialog(QDialog):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner, self.loading = owner, False
        self.options = material_options()
        self.setWindowTitle('库存保持')
        self.setObjectName('InventoryMaintainDialog')
        background = '#202020' if isDarkTheme() else '#f9f9f9'
        self.setStyleSheet(f'QDialog#InventoryMaintainDialog {{ background-color: {background}; }}')
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.resize(730, 570)
        layout = QVBoxLayout(self)
        hint = BodyLabel('按列表顺序补齐材料；每刷一场重新查库存。达标或自然波片不足即结束，不补充体力。')
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.rows = ListWidget()
        self.rows.setDragDropMode(QAbstractItemView.InternalMove)
        self.rows.setDefaultDropAction(Qt.MoveAction)
        self.rows.setSpacing(5)
        foreground = '#ffffff' if isDarkTheme() else '#202020'
        self.rows.setStyleSheet(
            f'QListWidget {{ background-color: {background}; color: {foreground}; border: 1px solid #707070; }}'
            'QListWidget::item { padding: 12px; }'
            'QListWidget::item:selected { background-color: #0078d4; color: white; }')
        layout.addWidget(self.rows)
        for row in owner.task.config.get(PLAN_KEY, []):
            item = QListWidgetItem()
            item.setData(Qt.UserRole, deepcopy(row))
            self.rows.addItem(item)
        controls = QHBoxLayout()
        self.add_button, self.remove_button = PushButton('＋ 新增材料'), PushButton('移除此材料')
        controls.addWidget(self.add_button)
        controls.addWidget(self.remove_button)
        controls.addStretch()
        layout.addLayout(controls)
        fields = QHBoxLayout()
        self.material, self.target = ComboBox(), SpinBox()
        for row in self.options:
            self.material.addItem(row['name'], userData=row['id'])
        self.target.setRange(0, 10_000_000)
        fields.addWidget(self.material)
        fields.addWidget(BodyLabel('目标数量'))
        fields.addWidget(self.target)
        layout.addLayout(fields)
        self.detail, self.message = BodyLabel(''), BodyLabel('拖动排序；显示的是上次库存，运行时会重新识别。')
        self.detail.setWordWrap(True)
        self.message.setWordWrap(True)
        layout.addWidget(self.detail)
        layout.addWidget(self.message)
        actions = QHBoxLayout()
        actions.addStretch()
        self.cancel_button, self.save_button = PushButton('取消'), PrimaryPushButton('保存')
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.save_button)
        layout.addLayout(actions)
        self.rows.currentItemChanged.connect(lambda *_: self.load_row())
        self.material.currentIndexChanged.connect(self.update_row)
        self.target.valueChanged.connect(self.update_row)
        self.add_button.clicked.connect(self.add_row)
        self.remove_button.clicked.connect(self.remove_row)
        self.save_button.clicked.connect(self.save)
        self.cancel_button.clicked.connect(self.reject)
        self.repaint_rows()
        self.rows.setCurrentRow(0)
        self.load_row()
        if owner.task.config.get(PENDING_KEY):
            self.message.setText('上次扣波片尚未核实，补刷已锁定；请先检查日志，不会自动重刷。')

    def plan(self):
        return [deepcopy(self.rows.item(i).data(Qt.UserRole)) for i in range(self.rows.count())]

    def repaint_rows(self):
        history = self.owner.task.config.get(HISTORY_KEY, {})
        history = history if isinstance(history, dict) else {}
        observed = {row.get('id'): row for row in history.get('materials', []) if isinstance(row, dict)}
        for i in range(self.rows.count()):
            item = self.rows.item(i)
            row = item.data(Qt.UserRole)
            stock = observed.get(row['id'], {})
            number = stock.get('quantity')
            number = str(number) if stock.get('status') == 'confirmed' and type(number) is int else '未知'
            item.setText(f'{row["name"]}: {number}/{row["target"]}')

    def load_row(self):
        item = self.rows.currentItem()
        editable = self.owner.editing_allowed()
        for widget in (self.material, self.target, self.remove_button):
            widget.setEnabled(item is not None and editable)
        self.rows.setDragEnabled(editable)
        self.rows.setAcceptDrops(editable)
        self.add_button.setEnabled(editable)
        self.save_button.setEnabled(editable)
        if item is None:
            self.detail.setText('只提供已接入识别和刷取入口的材料；数量不明确时不刷。')
            return
        self.loading = True
        try:
            row = item.data(Qt.UserRole)
            ids = [option['id'] for option in self.options]
            self.material.setCurrentIndex(ids.index(row['id']) if row['id'] in ids else -1)
            self.target.setValue(row['target'])
            route = ROUTES.get(row['route'], {})
            history = self.owner.task.config.get(HISTORY_KEY, {})
            observed = history.get('observed_at', '尚未识别') if isinstance(history, dict) else '尚未识别'
            self.detail.setText(f'刷取：{route.get("name", "入口尚未接入")} · 单倍{route.get("cost", "?")}波片\n'
                                f'上次检测：{observed}')
            self.detail.setText(self.detail.text() + '\n试用识别：运行时核对名称和数量；未识别时不刷。')
        finally:
            self.loading = False

    def update_row(self, *_):
        if self.loading or not self.owner.editing_allowed() or self.rows.currentItem() is None:
            return
        identity = self.material.currentData()
        option = next((row for row in self.options if row['id'] == identity), None)
        if option is None:
            return
        if any(row['id'] == identity for i, row in enumerate(self.plan()) if i != self.rows.currentRow()):
            self.message.setText('该材料已在列表中，不必重复添加。')
            self.load_row()
            return
        self.rows.currentItem().setData(Qt.UserRole, dict(option, target=self.target.value()))
        self.repaint_rows()
        self.load_row()

    def add_row(self):
        if not self.owner.editing_allowed():
            return
        seen = {row['id'] for row in self.plan()}
        option = next((row for row in self.options if row['id'] not in seen), None)
        if option is None:
            self.message.setText('所有已接入材料都已加入。')
            return
        item = QListWidgetItem()
        item.setData(Qt.UserRole, dict(option, target=20))
        self.rows.addItem(item)
        self.repaint_rows()
        self.rows.setCurrentItem(item)

    def remove_row(self):
        if self.owner.editing_allowed() and self.rows.currentRow() >= 0:
            self.rows.takeItem(self.rows.currentRow())
            self.load_row()

    def save(self):
        if not self.owner.editing_allowed():
            self.message.setText('任务正在运行，不能修改目标。')
            return
        try:
            selected = validate_targets(self.plan())
            store_value(self.owner.task, PLAN_KEY, selected)
        except Exception as exc:
            self.message.setText('保存失败：' + str(exc))
            return
        self.accept()
