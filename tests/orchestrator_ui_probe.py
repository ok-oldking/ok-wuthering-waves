"""Hidden native Qt smoke test. Uses temporary configs; never starts a game."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
from unittest.mock import patch

parser = argparse.ArgumentParser()
parser.add_argument('--framework', required=True, help='Checkout of the paired ok-script draft')
parser.add_argument('--preview', help='Optional PNG preview path')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(args.framework).resolve()))
sys.path.insert(0, str(root))
preview = Path(args.preview).resolve() if args.preview else None
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QEvent, QMimeData, QPoint, QPointF, Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QFont, QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog
from qfluentwidgets import FluentWindow, Theme, setTheme
from ok import og
from ok.util.config import Config
from ok.ui.qt import resources

app = QApplication([])
# Offscreen Windows builds may have no default font database.
font_file = Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'Fonts/segoeui.ttf'
if font_file.is_file():
    QFontDatabase.addApplicationFont(str(font_file))
    app.setFont(QFont('Segoe UI', 10))
setTheme(Theme.DARK)
calls = []
controller = SimpleNamespace(starting=False,
    start=lambda task: (_ for _ in ()).throw(AssertionError('Implicit game startup')))
og.app = SimpleNamespace(tr=lambda text: text, start_controller=controller)
executor = SimpleNamespace(scene=None,
    global_config=SimpleNamespace(get_config=lambda key: {}, get_config_desc=lambda key: {}),
    text_fix={}, current_task=None, trigger_tasks=[], onetime_tasks=[],
    exit_event=threading.Event(), supports_frame_independent_tasks=True)
og.executor = executor

from src.task.OrchestratorPlan import task_key, PLAN_KEY
from src.task.OrchestratorTask import OrchestratorTask
from src.gui.OrchestratorTab import OrchestratorTab, TASK_MIME, OWN_FIELDS
from src.task.FarmEchoTask import FarmEchoTask
from src.task.GardenTask import GardenTask
from src.task.MergeEchoTask import MergeEchoTask
from src.task.NightmareNestTask import NightmareNestTask

with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
    original_folder = Config.config_folder
    Config.config_folder = str(Path(folder) / 'configs')
    try:
        task = OrchestratorTask(executor=executor, app=og.app)
        task.load_config()
        assert task.config[PLAN_KEY] == []  # Never imports/replaces the native daily plan.
        children = [cls(executor=executor, app=og.app)
                    for cls in (FarmEchoTask, GardenTask, MergeEchoTask, NightmareNestTask)]
        for child in children:
            child.load_config()
        executor.onetime_tasks = [task] + children
        executor.get_task_by_class = lambda cls: next((t for t in executor.onetime_tasks if isinstance(t, cls)), None)
        executor.get_task_by_class_name = lambda name: next((t for t in executor.onetime_tasks if type(t).__name__ == name), None)
        executor.remove_onetime_task = lambda task: None
        executor._wake_executor = lambda: None
        executor.enqueue_onetime_task = lambda queued: calls.append(queued) or True
        executor.start = lambda: calls.append('executor-start')
        executor.pause = lambda task=None: calls.append('pause')
        executor.is_executor_thread = lambda: False
        page = OrchestratorTab()
        page.executor = executor
        shell = FluentWindow()
        shell.addSubInterface(page, page.icon, page.name)
        shell.resize(1250, 1000)
        page.resize(1080, 1000)
        page.ensurePolished()
        page.view.adjustSize()
        QTest.qWait(700)
        assert page._loaded and not page.start_button.isEnabled()
        assert not hasattr(page, 'library') and not hasattr(page, 'up_button')
        for key in ('FarmStamina', 'ClaimDaily', 'ClaimMail'):
            assert page.add_key(key)
        assert page.start_button.isEnabled()
        trigger = SimpleNamespace(enabled=True)
        executor.trigger_tasks, executor.current_task = [trigger], trigger
        QTest.qWait(700)
        assert page.editing_allowed()
        executor.current_task = None
        with patch.object(QDialog, 'open', lambda dialog: None):
            page.add_button.click()
            picker = page._picker
            keys = [picker.options.item(i).data(Qt.UserRole) for i in range(picker.options.count())]
            assert all(k in keys for k in ('OpenGame', 'CloseGame', 'Wait', 'ExitScript'))
            assert 'ClaimDaily' not in keys
            picker.options.setCurrentRow(keys.index('MergeEcho'))
            picker.add_button.click()
            assert page.plan()[-1] == 'MergeEcho'
            rect = page.queue.visualItemRect(page.queue.item(0))
            point = QPoint(rect.center().x(), rect.top() + 1)
            mime = page.queue.task_mime('MergeEcho')
            enter = QDragEnterEvent(point, Qt.MoveAction, mime, Qt.LeftButton, Qt.NoModifier)
            QApplication.sendEvent(page.queue.viewport(), enter)
            drop = QDropEvent(QPointF(point), Qt.MoveAction, mime, Qt.LeftButton, Qt.NoModifier)
            QApplication.sendEvent(page.queue.viewport(), drop)
            assert enter.isAccepted() and drop.isAccepted() and page.plan()[0] == 'MergeEcho'
            bad = QMimeData()
            bad.setData(TASK_MIME, b'{"token":"other","key":"MergeEcho","source":"queue"}')
            assert page.queue.read_drag(bad) is None
            page.show_details('FarmStamina')
            card = page._card
            assert set(card.config_widget_by_key) == set(OWN_FIELDS['FarmStamina'])
            card.config_widget_by_key['Which Tacet Suppression to Farm'].spin_box.setValue(4)
            assert task.config['Which Tacet Suppression to Farm'] == 4
            before = page.plan()
            card.reset_clicked()
            assert page.plan() == before
            page._dialog.accept()
            for key in ('Wait', 'Wait', 'ExitScript', 'CloseGame'):
                assert page.add_key(key)
            waits = [entry for entry in page.plan() if task_key(entry) == 'Wait']
            assert len(waits) == 2 and waits[0]['id'] != waits[1]['id']
            page.show_details(waits[0]['id'])
            page._card.config_widget_by_key['Wait seconds'].spin_box.setValue(180)
            assert [entry['seconds'] for entry in page.plan() if task_key(entry) == 'Wait'] == [180, 30]
            page._dialog.accept()
            assert [task_key(entry) for entry in page.plan()][-2:] == ['CloseGame', 'ExitScript']
            terminal = page.plan()[-1]
            page.transfer(terminal['id'], 'queue', 'queue', 0)
            assert not page.start_button.isEnabled()
            page.transfer(terminal['id'], 'queue', 'queue', len(page.plan()))
            saved = json.loads(Path(task.config.config_file).read_text(encoding='utf-8'))
            assert saved[PLAN_KEY] == page.plan()
            page.start_button.click()
            assert calls == [task, 'executor-start']
            assert not page.editing_allowed()
            assert not page.transfer('ClaimMail', 'queue', 'library')
            executor.current_task, task.running = task, True
            page.refresh_state()
            page.pause_button.click()
            assert task.paused
            page.pause_button.click()
            assert not task.paused
            page.stop_button.click()
            assert not task.enabled
            executor.current_task, task.running = None, False
            page.refresh_state()
            assert 'Stopped' in page.summary.text()
            while page.queue.count():
                page.queue.setCurrentRow(0)
                page.refresh_state()
                page.remove_button.click()
            assert page.plan() == [] and not page.start_button.isEnabled()
            for key in ('OpenGame', 'NightmareNest', 'FarmStamina', 'ClaimDaily',
                        'ClaimMail', 'ClaimBattlePass', 'CloseGame', 'Wait', 'ExitScript'):
                assert page.add_key(key)
            page.refresh_state()
            shell.navigationInterface.panel.collapse()
            shell.layout().activate()
            app.processEvents()
            QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            if preview:
                assert shell.grab().save(str(preview))
            assert not shell.isVisible()
        page.timer.stop()
        shell.close()
        print('HIDDEN_NATIVE_QT_PASS: loading, picker, drag, parameters, reset, waits, persistence, guards, pause, stop')
    finally:
        Config.config_folder = original_folder
