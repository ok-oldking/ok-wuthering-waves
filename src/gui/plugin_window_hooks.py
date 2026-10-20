# 在 GUI 线程向当前插件分发窗口钩子，并隔离失败和处理重载。
"""One delivery attempt per live task instance and window, including late imports."""

import weakref

from PySide6.QtCore import QObject, QTimer, Qt, Signal, Slot
from shiboken6 import isValid

from ok import Logger, og
from ok.core.events import communicate

logger = Logger.get_logger(__name__)


class PluginWindowHooks(QObject):
    _requested = Signal()

    def __init__(self, window):
        super().__init__(window)
        self._window = weakref.ref(window)
        self._delivered = {}
        self._dispatching = False
        self._closed = [False]
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.dispatch)
        self._requested.connect(self._schedule, Qt.ConnectionType.QueuedConnection)

        # Framework EventSignal is not a Qt signal. Bridge notifications, even
        # those emitted on a loader thread, to this window's QObject thread.
        owner = weakref.ref(self)
        closed = self._closed
        event = communicate.task_list_updated

        def notify(*_args, **_kwargs):
            bridge = owner()
            if bridge is not None and not closed[0]:
                try:
                    bridge._requested.emit()
                except RuntimeError:
                    pass  # The window may have been destroyed during emission.

        def dispose(*_args):
            closed[0] = True
            event.disconnect(notify)

        event.connect(notify)
        self.destroyed.connect(dispose)

    @Slot()
    def _schedule(self):
        if not self._closed[0] and not self._timer.isActive():
            self._timer.start(0)

    @staticmethod
    def _registered(manager, namespace, entry, task):
        return (
            getattr(og, "task_manager", None) is manager
            and manager.imported_scripts.get(namespace) is entry
            and task in manager.task_map
            and any(current is task for current in entry.get("tasks", ()))
        )

    @Slot()
    def dispatch(self):
        if self._closed[0]:
            return
        if self._dispatching:
            self._schedule()
            return
        window = self._window()
        if window is None or not isValid(window):
            return
        manager = getattr(og, "task_manager", None)
        if manager is None:
            self._delivered.clear()
            return
        # Both containers may change in a callback. Recheck registration before
        # each delivery so removed/replaced tasks in the snapshot are skipped.
        snapshot = tuple(
            (namespace, entry, task)
            for namespace, entry in tuple(manager.imported_scripts.items())
            for task in tuple(entry.get("tasks", ()))
        )
        live = {
            id(task): task
            for namespace, entry, task in snapshot
            if self._registered(manager, namespace, entry, task)
        }
        self._delivered = {
            identity: task
            for identity, task in self._delivered.items()
            if live.get(identity) is task
        }
        self._dispatching = True
        try:
            for namespace, entry, task in snapshot:
                if self._closed[0] or not isValid(window):
                    break
                if self._delivered.get(id(task)) is task:
                    continue
                if not self._registered(manager, namespace, entry, task):
                    continue
                try:
                    callback = getattr(task, "on_main_window", None)
                    if callable(callback):
                        # Mark before calling: nested notifications and failed
                        # partial UI initialization must not cause retry loops.
                        self._delivered[id(task)] = task
                        callback(window)
                except Exception as error:
                    self._delivered[id(task)] = task
                    logger.error(
                        f"Plugin window hook failed: {namespace}/{type(task).__name__}",
                        error,
                    )
        finally:
            self._dispatching = False


def install_plugin_window_hooks(window):
    hooks = getattr(window, "_okww_plugin_window_hooks", None)
    if hooks is None:
        hooks = PluginWindowHooks(window)
        window._okww_plugin_window_hooks = hooks
    hooks.dispatch()
