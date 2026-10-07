"""One editable queue, a task picker and the original native parameter widgets."""
from collections.abc import MutableMapping
from copy import deepcopy
import json
from pathlib import Path
import uuid

from PySide6.QtCore import QMimeData, Qt, QTimer
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QHBoxLayout, QListWidget,
                              QListWidgetItem, QScrollArea, QVBoxLayout)
from qfluentwidgets import BodyLabel, FluentIcon, PrimaryPushButton, PushButton, SubtitleLabel, isDarkTheme
from ok import og
from ok.ui.qt.tasks.ConfigCard import ConfigCard
from ok.ui.qt.widget.CustomTab import CustomTab
from src.task.OrchestratorPlan import (CATALOG, CONTROL_STEPS, PLAN_KEY, entry_id,
                                       task_key, executor_busy, transfer_plan, validate_plan)
from src.task.OrchestratorTask import OrchestratorTask

STATUS_TEXT = {'pending': 'Pending', 'running': 'Running', 'success': 'Completed', 'failed': 'Failed', 'skipped': 'Skipped'}
TASK_MIME = 'application/x-okww-orchestrator-task'
OWN_FIELDS = {
    'FarmStamina': ['Which to Farm', 'Which Tacet Suppression to Farm', 'Which Forgery Challenge to Farm', 'Material Selection'],
    'NightmareNest': ['Nightmare Nest Mode'], 'Farm4CEcho': ['Extra Boss Run Limit'],
}
CHILD_TASKS = {'NightmareNest': 'NightmareNestTask', 'WeeklyGarden': 'GardenTask',
               'MergeEcho': 'MergeEchoTask', 'Farm4CEcho': 'FarmEchoTask'}


class PlanList(QListWidget):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setDropIndicatorShown(True)
        self.setSpacing(6)
        color, bg = ('#f1f3f5', '#25292f') if isDarkTheme() else ('#20252b', '#ffffff')
        self.setStyleSheet('QListWidget { color: ' + color + '; background: ' + bg +
            '; border: 1px solid #77818b; border-radius: 10px; padding: 10px; } '
            'QListWidget::item { padding: 14px; border-radius: 7px; } '
            'QListWidget::item:selected { background: #206aa4; color: white; } '
            'QListWidget::item:hover:!selected { background: rgba(120,140,160,40); }')

    def task_mime(self, identity):
        mime = QMimeData()
        mime.setData(TASK_MIME, json.dumps({'token': self.owner._drag_token, 'key': identity, 'source': 'queue'}).encode('utf-8'))
        return mime

    def read_drag(self, mime):
        if not self.owner.editing_allowed() or not mime.hasFormat(TASK_MIME):
            return None
        try:
            data = json.loads(bytes(mime.data(TASK_MIME)))
            if not isinstance(data, dict) or data.get('token') != self.owner._drag_token or data.get('source') != 'queue':
                return None
            transfer_plan(self.owner.plan(), data.get('key'), 'queue', 'queue')
            return data
        except (ValueError, TypeError, KeyError):
            return None

    def startDrag(self, supported_actions):
        item = self.currentItem()
        if item is None or not self.owner.editing_allowed():
            return
        drag = QDrag(self)
        drag.setMimeData(self.task_mime(entry_id(item.data(Qt.UserRole))))
        drag.setPixmap(self.viewport().grab(self.visualItemRect(item)))
        drag.exec(Qt.MoveAction)

    def dragEnterEvent(self, event):
        if self.read_drag(event.mimeData()):
            event.setDropAction(Qt.MoveAction)
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        self.dragEnterEvent(event)

    def dropEvent(self, event):
        data = self.read_drag(event.mimeData())
        if data is None:
            event.ignore()
            return
        point = event.position().toPoint()
        row = self.indexAt(point).row()
        if row < 0:
            row = self.count()
        elif point.y() > self.visualItemRect(self.item(row)).center().y():
            row += 1
        if self.owner.transfer(data['key'], 'queue', 'queue', row):
            event.setDropAction(Qt.MoveAction)
            event.accept()
        else:
            event.ignore()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.owner.remove_selected()
            event.accept()
        else:
            super().keyPressEvent(event)


class RoutedConfig(MutableMapping):
    """One native form routes writes to the original task configs, not copies."""
    def __init__(self, owner, sources, defaults):
        self.owner, self.sources, self.defaults = owner, sources, defaults

    def __getitem__(self, key):
        return self.sources[key][key]

    def __setitem__(self, key, value):
        if self.owner.editing_allowed():
            self.sources[key][key] = deepcopy(value)

    def __delitem__(self, key):
        raise TypeError('Task parameters cannot be deleted')

    def __iter__(self):
        return iter(self.sources)

    def __len__(self):
        return len(self.sources)

    def get_default(self, key):
        return self.defaults.get(key)

    def has_user_config(self):
        return bool(self.sources)


class WaitConfig(MutableMapping):
    def __init__(self, owner, identity):
        self.owner, self.identity = owner, identity

    def __getitem__(self, key):
        if key != 'Wait seconds':
            raise KeyError(key)
        return next(entry['seconds'] for entry in self.owner.plan() if entry_id(entry) == self.identity)

    def __setitem__(self, key, value):
        if not self.owner.editing_allowed():
            return
        if key != 'Wait seconds' or type(value) is not int or not 0 <= value <= 86400:
            raise ValueError('Wait seconds must be an integer from 0 to 86400')
        selected = self.owner.plan()
        for entry in selected:
            if entry_id(entry) == self.identity:
                entry['seconds'] = value
                self.owner.commit_plan(selected, self.identity)
                return
        raise ValueError('This wait step was removed')

    def __delitem__(self, key):
        raise TypeError('Wait parameters cannot be deleted')

    def __iter__(self):
        return iter(['Wait seconds'])

    def __len__(self):
        return 1

    def get_default(self, key):
        return 30

    def has_user_config(self):
        return True


class EntryConfigCard(ConfigCard):
    def reset_clicked(self):
        for key, value in self.default_config.items():
            self.config[key] = deepcopy(value)
        self.update_config()


class TaskPicker(QDialog):
    def __init__(self, owner):
        super().__init__(owner)
        self.setWindowTitle(self.tr('Add task'))
        self.resize(580, 600)
        self.setAttribute(Qt.WA_DeleteOnClose)
        layout = QVBoxLayout(self)
        layout.addWidget(SubtitleLabel(self.tr('Select a step')))
        layout.addWidget(BodyLabel(self.tr('Control steps can repeat; business tasks can be added once.')))
        self.options = QListWidget()
        self.options.setSpacing(4)
        self.options.setStyleSheet('QListWidget::item { padding: 12px; }')
        chosen = {task_key(entry) for entry in owner.plan()}
        for key, (title, description) in CATALOG.items():
            if key in chosen and (key not in CONTROL_STEPS or key == 'ExitScript'):
                continue
            category = self.tr('Control' if key in CONTROL_STEPS else ('Extra' if key in CHILD_TASKS else 'Daily'))
            item = QListWidgetItem(f'[{category}]  {self.tr(title)}\n{self.tr(description)}')
            item.setData(Qt.UserRole, key)
            self.options.addItem(item)
        layout.addWidget(self.options)
        actions = QHBoxLayout()
        actions.addStretch()
        self.add_button = PrimaryPushButton(self.tr('Add to queue'))
        cancel = PushButton(self.tr('Cancel'))
        actions.addWidget(cancel)
        actions.addWidget(self.add_button)
        layout.addLayout(actions)
        cancel.clicked.connect(self.reject)
        self.add_button.clicked.connect(lambda: self.select(owner))
        self.options.itemDoubleClicked.connect(lambda item: self.select(owner))
        self.options.currentItemChanged.connect(lambda item: self.add_button.setEnabled(item is not None))
        self.add_button.setEnabled(False)

    def select(self, owner):
        item = self.options.currentItem()
        if item is not None and owner.add_key(item.data(Qt.UserRole)):
            self.accept()


class OrchestratorTab(CustomTab):
    def __init__(self):
        super().__init__()
        self.task = None
        self._loaded = self._loading = self._save_error = self._launch_requested = self._stop_requested = False
        self._drag_token = uuid.uuid4().hex
        self._dialog = self._picker = self._card = None
        self._launch_error = ''
        self.view.setStyleSheet('QWidget#view { background: ' + ('#20242b' if isDarkTheme() else '#f5f6f8') + '; }')
        header = QHBoxLayout()
        header.addWidget(SubtitleLabel(self.tr('Orchestrator')))
        header.addStretch()
        self.start_button = PrimaryPushButton(self.tr('Start plan'))
        self.pause_button = PushButton(self.tr('Pause'))
        self.stop_button = PushButton(self.tr('Stop'))
        for button in (self.start_button, self.pause_button, self.stop_button):
            header.addWidget(button)
        self.addLayout(header)
        self.notice = BodyLabel(self.tr('1. Add steps → 2. Drag to reorder → 3. Click for settings → Start'))
        self.notice.setWordWrap(True)
        self.add_widget(self.notice)
        self.summary = BodyLabel(self.tr('Loading plan…'))
        self.add_widget(self.summary)
        self.queue = PlanList(self)
        self.queue.setMinimumHeight(460)
        self.add_widget(self.queue)
        actions = QHBoxLayout()
        self.add_button = PrimaryPushButton(self.tr('＋ Add'))
        self.remove_button = PushButton(self.tr('Remove selected'))
        actions.addWidget(self.add_button)
        actions.addWidget(self.remove_button)
        actions.addStretch()
        self.addLayout(actions)
        foot = BodyLabel(self.tr('Game lifecycle is explicit here. App startup preferences remain unchanged. For cleanup add Close game → Wait → Exit assistant.'))
        foot.setWordWrap(True)
        self.add_widget(foot)
        self.start_button.clicked.connect(self.start_plan)
        self.pause_button.clicked.connect(self.pause_plan)
        self.stop_button.clicked.connect(self.stop_plan)
        self.add_button.clicked.connect(self.open_picker)
        self.remove_button.clicked.connect(self.remove_selected)
        self.queue.itemClicked.connect(lambda item: self.show_details(entry_id(item.data(Qt.UserRole))))
        self.queue.currentRowChanged.connect(lambda row: self.remove_button.setEnabled(self.editing_allowed() and row >= 0))
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_state)
        self.timer.start(500)

    @property
    def name(self):
        return self.tr('Orchestrator')

    @property
    def icon(self):
        return FluentIcon.LIBRARY

    @property
    def add_after_default_tabs(self):
        return False

    def plan(self):
        return [deepcopy(self.queue.item(i).data(Qt.UserRole)) for i in range(self.queue.count())]

    def populate_queue(self, selected, current=None):
        self._loading = True
        try:
            self.queue.clear()
            for entry in selected:
                item = QListWidgetItem(self.tr(CATALOG[task_key(entry)][0]))
                item.setData(Qt.UserRole, deepcopy(entry))
                self.queue.addItem(item)
                if entry_id(entry) == current:
                    self.queue.setCurrentItem(item)
        finally:
            self._loading = False

    def load_task(self):
        if self._loaded or self.executor is None:
            return
        self.task = self.get_task(OrchestratorTask)
        if self.task is None:
            self.summary.setText(self.tr('Orchestrator is not registered; restart the assistant.'))
            return
        try:
            selected = validate_plan(self.task.config.get(PLAN_KEY, []), allow_empty=True)
            self.populate_queue(selected)
            self._loaded = True
            if getattr(self.task, '_migration_notice', ''):
                self.notice.setText(self.task._migration_notice)
        except Exception as exc:
            self.summary.setText(self.tr('Load failed: ') + str(exc))

    def editing_allowed(self):
        return self._loaded and self.task is not None and not self._launch_requested and not executor_busy(
            self.executor, og.app.start_controller)

    def commit_plan(self, selected, current=None):
        if not self.editing_allowed():
            return False
        previous = deepcopy(self.task.config.get(PLAN_KEY, []))
        try:
            wanted = validate_plan(selected, allow_empty=True)
            self.task.config[PLAN_KEY] = wanted
            config_file = getattr(self.task.config, 'config_file', None)
            if config_file:
                with Path(config_file).open(encoding='utf-8-sig') as stream:
                    if json.load(stream).get(PLAN_KEY) != wanted:
                        raise OSError('Saved plan readback does not match')
            self.populate_queue(wanted, current)
            self.task.step_status, self.task.step_elapsed = {}, {}
            self._save_error = self._stop_requested = False
            self._launch_error = ''
            self.refresh_state()
            return True
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            self._save_error = True
            self.task.config[PLAN_KEY] = previous
            self.populate_queue(previous, current)
            self.summary.setText(self.tr('Save failed: ') + str(exc))
            return False

    def transfer(self, identity, source, target, index=None):
        try:
            selected = transfer_plan(self.plan(), identity, source, target, index)
            return self.commit_plan(selected, identity)
        except (ValueError, TypeError) as exc:
            self.summary.setText(self.tr('Edit failed: ') + str(exc))
            return False

    def add_key(self, key):
        selected = self.plan()
        index = next((i for i, entry in enumerate(selected) if task_key(entry) == 'ExitScript'), len(selected))
        return self.transfer(key, 'library', 'queue', index)

    def open_picker(self):
        if not self.editing_allowed():
            return
        if self._picker is not None:
            self._picker.raise_()
            return
        picker = self._picker = TaskPicker(self)
        picker.finished.connect(lambda result: setattr(self, '_picker', None))
        picker.open()

    def remove_selected(self):
        if self.editing_allowed() and self.queue.currentItem() is not None:
            if self._dialog:
                self._dialog.close()
            self.transfer(entry_id(self.queue.currentItem().data(Qt.UserRole)), 'queue', 'library')

    def show_details(self, identity):
        entry = next((entry for entry in self.plan() if entry_id(entry) == identity), None)
        if entry is None:
            return
        if self._dialog:
            self._dialog.close()
        key = task_key(entry)
        dialog = self._dialog = QDialog(self)
        dialog.setWindowTitle(self.tr(CATALOG[key][0]))
        dialog.setAttribute(Qt.WA_DeleteOnClose)
        dialog.resize(660, 580)
        layout = QVBoxLayout(dialog)
        description = BodyLabel(self.tr(CATALOG[key][1]))
        description.setWordWrap(True)
        layout.addWidget(description)
        defaults, descriptions, types, sources = {}, {}, {}, {}
        for field in OWN_FIELDS.get(key, []):
            defaults[field], sources[field] = self.task.default_config[field], self.task.config
            descriptions[field] = self.task.config_description.get(field, '')
            if field in self.task.config_type:
                types[field] = deepcopy(self.task.config_type[field])
        child = self.executor.get_task_by_class_name(CHILD_TASKS[key]) if key in CHILD_TASKS else None
        if child:
            for field, value in child.default_config.items():
                if field.startswith('_') or field in ('Exit After Task', 'Repeat Farm Count'):
                    continue
                defaults[field], sources[field] = deepcopy(value), child.config
                descriptions[field] = child.config_description.get(field, '')
                if field in child.config_type:
                    types[field] = deepcopy(child.config_type[field])
        if key == 'Wait':
            defaults = {'Wait seconds': 30}
            types = {'Wait seconds': {'min': 0, 'max': 86400}}
            config = WaitConfig(self, identity)
        else:
            config = RoutedConfig(self, sources, defaults)
        self._card = None
        if defaults:
            card = self._card = EntryConfigCard(self.task, self.tr(CATALOG[key][0]), config, '', defaults, descriptions, types, FluentIcon.SETTING)
            card.setExpand(True)
            card.setEnabled(self.editing_allowed())
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(card)
            layout.addWidget(scroll)
        else:
            layout.addWidget(BodyLabel(self.tr('This step has no additional parameters.')))
            layout.addStretch()
        close = PushButton(self.tr('Done'))
        close.clicked.connect(dialog.accept)
        layout.addWidget(close, alignment=Qt.AlignRight)
        dialog.finished.connect(lambda result: self._close_details(dialog))
        dialog.open()

    def _close_details(self, dialog):
        if self._dialog is dialog:
            self._dialog = self._card = None

    def start_plan(self):
        if not self.editing_allowed() or self._save_error:
            return
        try:
            validate_plan(self.plan(), execution=True)
            self.task.step_status, self.task.step_elapsed = {}, {}
            self._stop_requested = False
            self._launch_error = ''
            self._launch_requested = True
            self.task.queue_run()
        except Exception as exc:
            self._launch_error = self.tr('Start failed: ') + str(exc)
        finally:
            self._launch_requested = False
        self.refresh_state()

    def pause_plan(self):
        if self.task and self.task.enabled and self.executor.current_task is self.task:
            self.task.unpause() if self.task.paused else self.task.pause()
            self.refresh_state()

    def stop_plan(self):
        if self.task and self.task.enabled:
            self._stop_requested = True
            self.task.disable()
            self.task.unpause()
            self.refresh_state()

    def refresh_state(self):
        self.load_task()
        if not self._loaded:
            for button in (self.start_button, self.pause_button, self.stop_button, self.add_button, self.remove_button):
                button.setEnabled(False)
            return
        busy = self._launch_requested or executor_busy(self.executor, og.app.start_controller)
        editable = not busy
        self.queue.setDragEnabled(editable)
        self.queue.setAcceptDrops(editable)
        self.add_button.setEnabled(editable)
        self.remove_button.setEnabled(editable and self.queue.currentItem() is not None)
        if self._card:
            self._card.setEnabled(editable)
        if self._picker:
            self._picker.options.setEnabled(editable)
            self._picker.add_button.setEnabled(editable and self._picker.options.currentItem() is not None)
        invalid = ''
        try:
            validate_plan(self.plan(), execution=True)
        except ValueError as exc:
            invalid = str(exc)
        self.start_button.setEnabled(editable and not invalid and not self._save_error)
        self.pause_button.setEnabled(bool(self.task.enabled and self.executor.current_task is self.task))
        self.stop_button.setEnabled(bool(self.task.enabled))
        self.pause_button.setText(self.tr('Resume' if self.task.paused else 'Pause'))
        statuses, elapsed = getattr(self.task, 'step_status', {}), getattr(self.task, 'step_elapsed', {})
        for index, entry in enumerate(self.plan()):
            key, identity = task_key(entry), entry_id(entry)
            category = self.tr('Control' if key in CONTROL_STEPS else ('Extra' if key in CHILD_TASKS else 'Daily'))
            status = self.tr(STATUS_TEXT.get(statuses.get(identity), 'Pending'))
            timing = f' · {elapsed[identity]:g}s' if identity in elapsed else ''
            description = self.tr('Wait {seconds}s without a game frame').format(seconds=entry['seconds']) if key == 'Wait' else self.tr(CATALOG[key][1])
            self.queue.item(index).setText(f'{index + 1:02d}    {self.tr(CATALOG[key][0])}    [{category}]    {status}{timing}\n{description}')
        if self.task.enabled:
            running = ' → '.join(self.tr(CATALOG[task_key(entry)][0]) for entry in self.plan() if statuses.get(entry_id(entry)) == 'running')
            self.summary.setText(self.tr('Paused') if self.task.paused else self.tr('Running · ') + (running or self.tr('Waiting for executor')))
        elif self._stop_requested and not busy:
            self.summary.setText(self.tr('Stopped · remaining steps were not run'))
        elif busy:
            self.summary.setText(self.tr('Another task is running · editing is locked'))
        elif self._save_error:
            pass
        elif self._launch_error:
            self.summary.setText(self._launch_error)
        elif statuses:
            failures = sum(status == 'failed' for status in statuses.values())
            self.summary.setText(self.tr('Plan finished') + (self.tr(' · {count} failed; check logs').format(count=failures) if failures else self.tr(' · selected steps completed')))
        else:
            self.summary.setText(invalid if self.queue.count() and invalid else (
                self.tr('Ready · {count} steps · top to bottom').format(count=self.queue.count()) if self.queue.count() else self.tr('Empty plan · click Add to select steps')))
