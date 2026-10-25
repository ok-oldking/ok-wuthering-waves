"""
UI and State Machine synchronization patch for ok-script.

Fixes bi-directional state synchronization between StartCard (Capture tab)
and TaskCard (Tasks tab), introduces Stop button with F10 global hotkey,
and guards Rescan Window button during active task runs.
"""

from ctypes import windll, wintypes
import time
from _ctypes import byref

from ok import Logger
from ok.core.events import communicate
from ok.util.GlobalConfig import _basic_options_default, _basic_options_type, _basic_options_description

logger = Logger.get_logger(__name__)

# Register Stop Task hotkey option into GlobalConfig
if 'Stop Task' not in _basic_options_default:
    _basic_options_default['Stop Task'] = 'F10'
    _basic_options_type['Stop Task'] = {
        'type': 'drop_down',
        'options': ['None', 'F9', 'F10', 'F11', 'F12']
    }
    _basic_options_description['Stop Task'] = 'HotKey to Stop Active Task'


def apply_executor_patch():
    from ok.task.TaskExecutor import TaskExecutor
    from ok.task.task import BaseTask

    if getattr(TaskExecutor, '_ui_sync_patched', False):
        return

    orig_pause = TaskExecutor.pause
    orig_start = TaskExecutor.start

    def patched_pause(self, task=None):
        if task is not None:
            if self.current_task != task:
                raise Exception(f"Can only pause current task {self.current_task}")
            # When task explicitly requested pause from TaskCard
            if not self.paused:
                self.paused = True
                self._wake_executor()
                communicate.executor_paused.emit(self.paused)
                self.reset_scene(check_enabled=False)
                self.pause_start = time.time()
                return True
        elif not self.paused:
            self.paused = True
            if self.current_task is not None and getattr(self.current_task, '_enabled', False):
                self.current_task._paused = True
                communicate.task.emit(self.current_task)
            self._wake_executor()
            communicate.executor_paused.emit(self.paused)
            self.reset_scene(check_enabled=False)
            self.pause_start = time.time()
            return True

    def patched_start(self):
        if self.current_task is not None and getattr(self.current_task, '_paused', False):
            self.current_task._paused = False
            communicate.task.emit(self.current_task)
        return orig_start(self)

    TaskExecutor.pause = patched_pause
    TaskExecutor.start = patched_start
    TaskExecutor._ui_sync_patched = True
    logger.info("TaskExecutor state sync patch applied")


def apply_qt_patch():
    try:
        from PySide6.QtCore import Qt
        from qfluentwidgets import FluentIcon, PrimaryPushButton, PushButton
        from ok.ui.qt.common.OKIcon import OKIcon
        from ok.ui.qt.start.StartCard import StartCard
        from ok.ui.qt.tasks.TaskCard import TaskCard
        from ok import og
    except ImportError:
        logger.debug("Qt not available in current environment; skipping Qt UI patches")
        return

    if getattr(StartCard, '_ui_sync_patched', False):
        return

    # Patch TaskCard for executor pause awareness
    orig_task_card_init = TaskCard.__init__
    orig_task_card_update_buttons = TaskCard.update_buttons
    orig_task_card_start_clicked = TaskCard.start_clicked

    def patched_task_card_init(self, task, onetime):
        orig_task_card_init(self, task, onetime)
        self._executor_pause_handler = lambda _paused: self.update_buttons(self.task)
        communicate.executor_paused.connect(self._executor_pause_handler)

    def patched_task_card_dispose(self):
        try:
            if hasattr(self, '_executor_pause_handler'):
                communicate.executor_paused.disconnect(self._executor_pause_handler)
        except Exception:
            pass
        if hasattr(self, '_orig_dispose'):
            self._orig_dispose()

    def patched_task_card_update_buttons(self, task):
        if task == self.task or self.onetime:
            has_instructions = bool(getattr(self.task, 'instructions', None))
            self.instructions_button.setVisible(has_instructions)
            self.update_content()

            if self.onetime:
                is_task_paused = self.task.paused or (getattr(og.executor, 'paused', False) and self.task.running)
                if self.task.enabled:
                    if is_task_paused:
                        self.start_button.setText(self.tr("Resume"))
                        self.start_button.setVisible(True)
                        self.pause_button.setVisible(False)
                        self.stop_button.setVisible(True)
                    elif self.task.running:
                        self.start_button.setVisible(False)
                        self.stop_button.setVisible(True)
                        self.pause_button.setVisible(True)
                    else:
                        self.start_button.setVisible(False)
                        self.stop_button.setVisible(True)
                        self.pause_button.setVisible(False)
                else:
                    self.start_button.setText(self.tr("Start"))
                    self.start_button.setVisible(True)
                    self.pause_button.setVisible(False)
                    self.stop_button.setVisible(False)
            else:
                if self.enable_button:
                    self.enable_button.setChecked(task.enabled)

            self._rebuild_button_layout()

    def patched_task_card_start_clicked(self):
        self.setExpand(False)
        is_task_paused = self.task.paused or (getattr(og.executor, 'paused', False) and self.task.running)
        if self.task.enabled and is_task_paused:
            logger.info(f"resume paused task {self.task}")
            self.task.unpause()
            return
        orig_task_card_start_clicked(self)

    TaskCard.__init__ = patched_task_card_init
    if hasattr(TaskCard, 'dispose'):
        TaskCard._orig_dispose = TaskCard.dispose
        TaskCard.dispose = patched_task_card_dispose
    TaskCard.update_buttons = patched_task_card_update_buttons
    TaskCard.start_clicked = patched_task_card_start_clicked

    # Patch StartCard for Stop button, Rescan Window label/guard, and F10 hotkey
    orig_start_card_init = StartCard.__init__
    orig_start_card_update_status = StartCard.update_status
    orig_start_card_check_hotkey = StartCard.check_hotkey

    def patched_start_card_init(self, exit_event):
        orig_start_card_init(self, exit_event)

        # Rename Refresh to Rescan Window
        self.refresh_button.setText(self.tr("Rescan Window"))
        self.refresh_button.setToolTip(self.tr("Rescan and re-hook game window or device"))

        # Add Stop button right before Start button
        self.stop_button = PushButton(OKIcon.STOP, self.tr("Stop"), self)
        self.stop_button.clicked.connect(self.stop_clicked)
        # Re-order buttons in hBoxLayout: insert before start_button
        # Remove start_button and re-add stop_button then start_button
        self.hBoxLayout.removeWidget(self.start_button)
        self.hBoxLayout.addWidget(self.stop_button, 0, Qt.AlignRight)
        self.hBoxLayout.addSpacing(6)
        self.hBoxLayout.addWidget(self.start_button, 0, Qt.AlignRight)

        self.current_stop_hotkey = "UNINIT"
        self.update_status()

    def start_card_stop_clicked(self):
        logger.info("StartCard Stop button clicked")
        if og.executor.current_task:
            og.executor.stop_current_task()

    def patched_start_card_update_status(self, *args, **kwargs):
        orig_start_card_update_status(self)

        # Update Stop button hotkey suffix and availability
        stop_hotkey = self.basic_options.get('Stop Task', 'F10')
        suffix_stop = f'({stop_hotkey})' if stop_hotkey and stop_hotkey != 'None' else ''
        if hasattr(self, 'stop_button'):
            self.stop_button.setText(self.tr("Stop") + suffix_stop)
            has_running_task = bool(og.executor.current_task and og.executor.current_task.running)
            self.stop_button.setEnabled(has_running_task or not og.executor.paused)

        # Guard Rescan Window button while task is running
        if hasattr(self, 'refresh_button'):
            self.refresh_button.setText(self.tr("Rescan Window"))
            has_running_task = bool(og.executor.current_task and og.executor.current_task.running)
            if has_running_task:
                self.refresh_button.setEnabled(False)
                self.refresh_button.setToolTip(self.tr("Cannot rescan window while a task is running"))
            else:
                self.refresh_button.setEnabled(True)
                self.refresh_button.setToolTip(self.tr("Rescan and re-hook game window or device"))

    def rebind_stop_hotkey(self, hotkey):
        windll.user32.UnregisterHotKey(None, 998)
        vk_map = {'F9': 0x78, 'F10': 0x79, 'F11': 0x7A, 'F12': 0x7B}
        if hotkey and hotkey != 'None' and hotkey in vk_map:
            if not windll.user32.RegisterHotKey(None, 998, 0, vk_map[hotkey]):
                logger.error(f"Failed to register stop hotkey {hotkey}")
        else:
            logger.debug(f"Stop hotkey disabled or invalid: {hotkey}")

    def patched_start_card_check_hotkey(self):
        new_hotkey = self.basic_options.get('Start/Stop')
        if new_hotkey != self.current_hotkey:
            self.rebind_hotkey(new_hotkey)
            self.current_hotkey = new_hotkey
            self.hotkey_changed.emit()

        new_stop_hotkey = self.basic_options.get('Stop Task', 'F10')
        if new_stop_hotkey != getattr(self, 'current_stop_hotkey', 'UNINIT'):
            self.rebind_stop_hotkey(new_stop_hotkey)
            self.current_stop_hotkey = new_stop_hotkey
            self.hotkey_changed.emit()

        msg = wintypes.MSG()
        while windll.user32.PeekMessageW(byref(msg), None, 0, 0, 1):
            if msg.message == 0x0312:  # WM_HOTKEY
                logger.debug(f'hotkey pressed {msg}')
                if msg.wParam == 999:
                    self.clicked()
                elif msg.wParam == 998:
                    self.stop_clicked()

        self.handler.post(self.check_hotkey, 0.1)

    StartCard.__init__ = patched_start_card_init
    StartCard.stop_clicked = start_card_stop_clicked
    StartCard.update_status = patched_start_card_update_status
    StartCard.rebind_stop_hotkey = rebind_stop_hotkey
    StartCard.check_hotkey = patched_start_card_check_hotkey
    StartCard._ui_sync_patched = True
    logger.info("StartCard & TaskCard Qt state sync patch applied")


def patch_all():
    apply_executor_patch()
    apply_qt_patch()


# Automatically apply patches when module is imported
patch_all()
