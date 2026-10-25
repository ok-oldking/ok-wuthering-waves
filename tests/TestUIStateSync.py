import os
import unittest
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from qfluentwidgets import FluentIcon
from ok import og
from ok.core.events import communicate
from ok.task.TaskExecutor import TaskExecutor
from ok.task.task import BaseTask
from ok.util.handler import ExitEvent
import src.ui_patch  # Ensures patch is active


class DummyTask(BaseTask):
    def __init__(self, executor=None):
        self._executor = executor
        self._app = MagicMock()
        self.name = "DummyTask"
        self.description = "Dummy Description"
        self._enabled = True
        self.running = False
        self._paused = False
        self.instructions = None
        self.first_run_alert = None
        self.show_create_shortcut = False
        self.sleep_check_interval = -1
        self.config = {}
        self.default_config = {}
        self.config_description = {}
        self.config_type = {}
        self.icon = None


class TestUIStateSync(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.exit_event = ExitEvent()
        self.device_manager = MagicMock()
        self.device_manager.get_preferred_device.return_value = None
        self.global_config = MagicMock()
        self.global_config.get_config.return_value = {
            'Start/Stop': 'F9',
            'Stop Task': 'F10',
        }
        self.executor = TaskExecutor(
            device_manager=self.device_manager,
            exit_event=self.exit_event,
            global_config=self.global_config,
            config={'locale': 'en_US'}
        )
        og.executor = self.executor
        og.app = MagicMock()
        og.app.title = "OK-WW"
        og.app.version = "1.0.0"
        og.app.tr = lambda text, *args, **kwargs: str(text)
        og.config = {'gui_icon': FluentIcon.INFO}
        og.device_manager = self.device_manager

    def tearDown(self):
        self.exit_event.set()

    def test_executor_pause_propagates_to_running_task(self):
        task = DummyTask(executor=self.executor)
        task.running = True
        self.executor.current_task = task
        self.executor.paused = False

        task_signals = []
        communicate.task.connect(lambda t: task_signals.append(t))

        self.executor.pause()

        self.assertTrue(self.executor.paused)
        self.assertTrue(task._paused)
        self.assertIn(task, task_signals)

    def test_executor_start_unpauses_running_task(self):
        task = DummyTask(executor=self.executor)
        task.running = True
        task._paused = True
        self.executor.current_task = task
        self.executor.paused = True

        task_signals = []
        communicate.task.connect(lambda t: task_signals.append(t))

        self.executor.start()

        self.assertFalse(self.executor.paused)
        self.assertFalse(task._paused)
        self.assertIn(task, task_signals)

    def test_task_pause_propagates_to_executor(self):
        task = DummyTask(executor=self.executor)
        task.running = True
        self.executor.current_task = task
        self.executor.paused = False

        executor_signals = []
        communicate.executor_paused.connect(lambda p: executor_signals.append(p))

        # When task.pause() is called, it invokes executor.pause(task)
        self.executor.pause(task)

        self.assertTrue(self.executor.paused)
        self.assertIn(True, executor_signals)

    def test_stop_current_task_disables_and_unpauses(self):
        task = DummyTask(executor=self.executor)
        task.running = True
        task._paused = True
        task.disable = MagicMock()
        task.unpause = MagicMock()
        self.executor.current_task = task

        self.executor.stop_current_task()

        task.disable.assert_called_once()
        task.unpause.assert_called_once()

    def test_task_card_reflects_executor_pause(self):
        from ok.ui.qt.tasks.TaskCard import TaskCard

        task = DummyTask(executor=self.executor)
        task.running = True
        task._paused = False
        self.executor.current_task = task
        self.executor.paused = True

        card = TaskCard(task, onetime=True)
        # Executor is paused, so TaskCard button must show Resume (or its translation)
        self.assertEqual(card.start_button.text(), card.tr("Resume"))
        self.assertFalse(card.start_button.isHidden())
        self.assertTrue(card.pause_button.isHidden())
        self.assertFalse(card.stop_button.isHidden())

        # Unpause executor
        self.executor.paused = False
        communicate.executor_paused.emit(False)
        self.assertTrue(card.start_button.isHidden())
        self.assertFalse(card.pause_button.isHidden())
        self.assertFalse(card.stop_button.isHidden())

    def test_start_card_has_stop_button_and_rescan_window(self):
        from ok.ui.qt.start.StartCard import StartCard

        start_card = StartCard(self.exit_event)
        self.assertTrue(hasattr(start_card, 'stop_button'))
        self.assertIn(start_card.tr("Stop"), start_card.stop_button.text())
        self.assertIn("F10", start_card.stop_button.text())

        # Check Rescan Window label
        self.assertEqual(start_card.refresh_button.text(), start_card.tr("Rescan Window"))

        # When a task is running, refresh_button is disabled
        task = DummyTask(executor=self.executor)
        task.running = True
        self.executor.current_task = task
        start_card.update_status()

        self.assertFalse(start_card.refresh_button.isEnabled())
        self.assertEqual(
            start_card.refresh_button.toolTip(),
            start_card.tr("Cannot rescan window while a task is running")
        )

        # When task finishes running, refresh_button is re-enabled
        task.running = False
        self.executor.current_task = None
        start_card.update_status()
        self.assertTrue(start_card.refresh_button.isEnabled())

    def test_start_card_stop_button_triggers_executor_stop(self):
        from ok.ui.qt.start.StartCard import StartCard

        start_card = StartCard(self.exit_event)
        task = DummyTask(executor=self.executor)
        task.running = True
        self.executor.current_task = task
        self.executor.paused = False

        start_card.stop_clicked()
        self.assertFalse(task._enabled)
        self.assertFalse(task.running)
        self.assertIsNone(self.executor.current_task)
        self.assertTrue(self.executor.paused)
        self.assertEqual(start_card.start_button.text(), f"{start_card.tr('Start')}(F9)")
        self.assertFalse(start_card.stop_button.isEnabled())
        self.assertTrue(start_card.status_bar.isHidden())

    def test_task_card_stop_button_disables_without_unpausing_executor(self):
        from ok.ui.qt.tasks.TaskCard import TaskCard

        task = DummyTask(executor=self.executor)
        task.running = True
        task._paused = True
        self.executor.current_task = task
        self.executor.paused = True

        card = TaskCard(task, onetime=True)
        card.stop_clicked()

        self.assertFalse(task._enabled)
        self.assertFalse(task.running)
        self.assertFalse(task._paused)
        self.assertIsNone(self.executor.current_task)
        self.assertTrue(self.executor.paused)


if __name__ == '__main__':
    unittest.main()
