# 验证插件窗口钩子的故障隔离、变更快照和 GUI 生命周期。
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PySide6.QtCore import QCoreApplication, QEvent, QThread
from PySide6.QtWidgets import QApplication, QWidget

from ok.core.events import EventSignal
from ok.core.task_manager import TaskManager
from src.globals import Globals
from src.gui import plugin_window_hooks


class Task:
    def __init__(self, callback):
        self.on_main_window = callback
        self.disable = Mock()


class PluginWindowHook(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.events = SimpleNamespace(task_list_updated=EventSignal("window-hook-test"))
        self.manager = SimpleNamespace(imported_scripts={}, task_map={})
        self.globals_state = SimpleNamespace(task_manager=self.manager)
        self.enterContext(patch.object(plugin_window_hooks, "og", self.globals_state))
        self.enterContext(patch.object(plugin_window_hooks, "communicate", self.events))
        self.globals = Globals(None)
        self.window = self.new_window()

    def new_window(self):
        window = QWidget()
        self.addCleanup(self.destroy_window, window)
        return window

    @staticmethod
    def destroy_window(window):
        from shiboken6 import isValid

        if isValid(window):
            window.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def register(self, name, *tasks):
        self.manager.imported_scripts[name] = {"tasks": list(tasks)}
        self.manager.task_map.update({task: ("synthetic.py", "") for task in tasks})

    def drain(self):
        # Queued signal delivery followed by the coalescing zero timer.
        for _ in range(4):
            self.app.processEvents()

    def test_callback_failure_is_isolated_and_not_retried_on_task_notifications(self):
        bad = Task(Mock(side_effect=RuntimeError("synthetic plugin failure")))
        good = Task(Mock())
        self.register("first", bad)
        self.register("second", object(), good)
        with self.assertLogs("ok", level="ERROR") as logs:
            self.globals.on_show_main_window(self.window)
        self.assertIn("first/Task", "\n".join(logs.output))
        good.on_main_window.assert_called_once_with(self.window)
        self.globals.on_show_main_window(self.window)
        self.events.task_list_updated.emit()
        self.drain()
        self.assertEqual(1, bad.on_main_window.call_count)
        self.assertEqual(1, good.on_main_window.call_count)

    def test_callback_registry_mutation_skips_unloaded_tasks_and_defers_new_tasks(self):
        removed = Task(Mock())
        added = Task(Mock())

        def change_registry(window):
            self.manager.imported_scripts.pop("second")
            self.manager.task_map.pop(removed)
            self.manager.imported_scripts["first"]["tasks"].clear()
            self.manager.task_map.pop(first)
            self.register("new", added)
            self.events.task_list_updated.emit()

        first = Task(change_registry)
        self.register("first", first)
        self.register("second", removed)
        self.globals.on_show_main_window(self.window)
        removed.on_main_window.assert_not_called()
        added.on_main_window.assert_not_called()
        self.drain()
        added.on_main_window.assert_called_once_with(self.window)
        self.assertEqual(
            {id(added)}, set(self.window._okww_plugin_window_hooks._delivered)
        )

    def test_runtime_import_reload_and_unload_follow_gui_thread_and_instance_identity(
        self,
    ):
        self.globals_state.task_manager = None
        self.globals.on_show_main_window(self.window)
        manager = TaskManager.__new__(TaskManager)
        manager.imported_scripts, manager.task_map = {}, {}
        manager.task_executor = SimpleNamespace(onetime_tasks=[], trigger_tasks=[])
        manager._update_debug_watched_files = Mock()
        self.globals_state.task_manager = manager
        threads, calls = [], []

        def callback(window):
            threads.append(QThread.currentThread())
            calls.append(window)

        created = []

        def load(*_args, **_kwargs):
            task = Task(callback)
            created.append(task)
            manager.task_map[task] = ("synthetic.py", "")
            manager.task_executor.onetime_tasks.append(task)
            return task

        manager.load_single_user_task = load
        entry = dict(
            folder=".",
            file_name="synthetic",
            script_name="synthetic",
            has_features=False,
        )
        with (
            patch("ok.core.task_manager.communicate", self.events),
            patch("ok.core.task_manager.glob.glob", return_value=["synthetic.py"]),
        ):
            worker = threading.Thread(target=manager._load_import_entry, args=(entry,))
            worker.start()
            worker.join(timeout=2)
            self.assertFalse(worker.is_alive())
            self.assertEqual([], calls)
            self.drain()
            self.assertEqual([self.window], calls)
            self.events.task_list_updated.emit()
            self.drain()
            self.assertEqual(1, len(calls))
            manager.unload_task(created[0])
            manager._load_import_entry(entry)
            self.drain()
            self.assertEqual(2, len(calls))
            manager.unload_task(created[1])
            self.drain()
        self.assertTrue(all(thread is self.app.thread() for thread in threads))
        self.assertEqual({}, self.window._okww_plugin_window_hooks._delivered)

    def test_each_window_is_independent_and_destruction_disconnects_notifications(self):
        task = Task(Mock())
        self.register("plugin", task)
        signal = self.events.task_list_updated
        with patch.object(signal, "disconnect", wraps=signal.disconnect) as disconnect:
            self.globals.on_show_main_window(self.window)
            other = self.new_window()
            self.globals.on_show_main_window(other)
            self.assertEqual(
                [self.window, other],
                [c.args[0] for c in task.on_main_window.call_args_list],
            )
            self.events.task_list_updated.emit()
            self.destroy_window(other)
            self.drain()
            disconnect.assert_called_once()
            self.assertEqual(2, task.on_main_window.call_count)
            self.destroy_window(self.window)
            self.assertEqual(2, disconnect.call_count)
            self.events.task_list_updated.emit()
            self.drain()
            self.assertEqual(2, task.on_main_window.call_count)
