"""离屏检查真实设置窗口，不启动游戏或执行任务。"""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

os.environ['QT_QPA_PLATFORM'] = 'offscreen'


class NativeUiTests(unittest.TestCase):
    def test_settings_save_order_and_busy_guard(self):
        from PySide6.QtWidgets import QApplication, QWidget
        from src.gui.InventoryMaintainDialog import InventoryMaintainDialog
        from src.task.InventoryMaintain import PLAN_KEY, PENDING_KEY, HISTORY_KEY
        from test_native_adapter import SavedConfig

        app = QApplication.instance() or QApplication([])
        with TemporaryDirectory() as temporary:
            owner = QWidget()
            owner.task = SimpleNamespace(config=SavedConfig(Path(temporary) / 'targets.json', {
                PLAN_KEY: [], PENDING_KEY: {}, HISTORY_KEY: {},
            }))
            owner.editing_allowed = lambda: True
            view = InventoryMaintainDialog(owner)
            self.assertEqual(len(view.options), 49)
            view.add_row()
            view.target.setValue(31)
            view.add_row()
            view.target.setValue(42)
            item = view.rows.takeItem(1)
            view.rows.insertItem(0, item)
            view.save()
            saved = owner.task.config[PLAN_KEY]
            self.assertEqual([row['target'] for row in saved], [42, 31])
            owner.editing_allowed = lambda: False
            view.save()
            self.assertEqual(owner.task.config[PLAN_KEY], saved)
            owner.close()
            app.processEvents()


if __name__ == '__main__':
    unittest.main()
