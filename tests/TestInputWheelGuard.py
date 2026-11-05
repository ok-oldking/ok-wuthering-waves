import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QEvent, QPoint, QPointF, QTime, Qt
from PySide6.QtGui import QKeyEvent, QWheelEvent
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QLineEdit,
    QRadioButton, QScrollArea, QSpinBox, QTimeEdit, QVBoxLayout, QWidget,
)

from ok.ui.qt.kit.inputs import ComboBox, NumberBox
from ok.ui.qt.kit.switch import Switch
from ok.ui.qt.tasks.config_editors import config_editor
from ok.util.config import Config
from config import basic_config_option
from src.globals import Globals
from src.gui.input_wheel_guard import install_input_wheel_guard


class TestInputWheelGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = QWidget()
        self.layout = QVBoxLayout(self.window)
        self.focus_anchor = QLineEdit(self.window)
        self.layout.addWidget(self.focus_anchor)
        # Exercise the same hook used by the Qt application's startup.
        Globals(None).on_show_main_window(self.window)

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def show_control(self, widget):
        self.layout.addWidget(widget)
        self.window.show()
        self.window.activateWindow()
        self.focus_anchor.setFocus()
        self.app.processEvents()
        self.assertTrue(self.focus_anchor.hasFocus())

    def wheel(self, widget, delta=-120):
        local = QPointF(widget.rect().center())
        event = QWheelEvent(
            local, QPointF(widget.mapToGlobal(local.toPoint())), QPoint(), QPoint(0, delta),
            Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase, False,
        )
        self.app.sendEvent(widget, event)
        self.app.processEvents()
        return event

    def controls(self):
        integer = QSpinBox()
        integer.setValue(5)
        decimal = QDoubleSpinBox()
        decimal.setValue(5.5)
        time = QTimeEdit(QTime(12, 30))
        combo = QComboBox()
        combo.addItems(['CPU', 'DirectML', 'OpenVINO'])
        combo.setCurrentIndex(1)
        editable = ComboBox(['CPU', 'DirectML', 'OpenVINO'])
        editable.setEditable(True)
        editable.setCurrentIndex(1)
        return [
            (integer, integer, integer.value),
            (decimal, decimal, decimal.value),
            (time, time, time.time),
            (combo, combo, combo.currentIndex),
            (editable, editable, editable.currentIndex),
            *[(box, box.spin_box, box.value) for box in (
                NumberBox(5), NumberBox(5.5, decimals=1),
            )],
        ]

    def test_hover_does_not_change_unfocused_inputs_or_take_focus(self):
        for widget, control, value in self.controls():
            with self.subTest(control=type(control).__name__, wrapper=type(widget).__name__):
                self.show_control(widget)
                before = value()
                self.assertEqual(control.focusPolicy(), Qt.FocusPolicy.StrongFocus)
                for target in (control, control.lineEdit()):
                    if target is not None:
                        for delta in (-120, 120):
                            self.wheel(target, delta)
                            self.assertEqual(value(), before)
                            self.assertTrue(self.focus_anchor.hasFocus())

    def test_focused_inputs_still_accept_wheel_and_keyboard(self):
        for widget, control, value in self.controls():
            with self.subTest(control=type(control).__name__, wrapper=type(widget).__name__):
                self.show_control(widget)
                control.setFocus(Qt.FocusReason.MouseFocusReason)
                self.app.processEvents()
                self.assertTrue(control.hasFocus())
                before = value()
                self.wheel(control)
                self.assertNotEqual(value(), before)
                after_wheel = value()
                event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Up, Qt.KeyboardModifier.NoModifier)
                self.app.sendEvent(control, event)
                self.assertNotEqual(value(), after_wheel)

    def test_hover_scrolls_parent_without_saving_a_new_value(self):
        scroll = QScrollArea()
        content = QWidget()
        content_layout = QVBoxLayout(content)
        fields = [NumberBox(5), ComboBox(['CPU', 'DirectML', 'OpenVINO'])]
        fields[1].setCurrentIndex(1)
        changes = []
        fields[0].valueChanged.connect(changes.append)
        fields[1].currentIndexChanged.connect(changes.append)
        for field in fields:
            content_layout.addWidget(field)
        content_layout.addStretch()
        content.setMinimumHeight(1500)
        scroll.setWidget(content)
        scroll.setWidgetResizable(True)
        self.show_control(scroll)
        self.window.resize(500, 350)
        self.app.processEvents()
        for target in (fields[0].spin_box, fields[0].spin_box.lineEdit(), fields[1]):
            with self.subTest(target=type(target).__name__):
                scroll.verticalScrollBar().setValue(0)
                self.wheel(target)
                self.assertGreater(scroll.verticalScrollBar().value(), 0)
                self.assertEqual(changes, [])

    def test_buttons_checkboxes_radios_and_switches_keep_their_behavior(self):
        box = NumberBox(5)
        self.show_control(box)
        box.plus_button.click()
        self.assertEqual(box.value(), 6)
        box.minus_button.click()
        self.assertEqual(box.value(), 5)
        for control in (QCheckBox(), QRadioButton(), Switch()):
            with self.subTest(control=type(control).__name__):
                self.show_control(control)
                self.wheel(control)
                self.assertFalse(control.isChecked())
                control.click()
                self.assertTrue(control.isChecked())
                self.focus_anchor.setFocus()
                self.wheel(control)
                self.assertTrue(control.isChecked())

    def test_real_settings_do_not_save_hover_changes(self):
        option = basic_config_option
        with tempfile.TemporaryDirectory() as folder:
            config = Config('Basic Options', option.default_config, folder=folder)
            path = Path(config.config_file)
            original = path.read_bytes()
            for key in ('Use DirectML', 'Start/Stop', 'Blur Algorithm', 'Trigger Interval'):
                with self.subTest(key=key):
                    editor = config_editor(
                        option.config_type, option.config_description, config, key, config[key], None,
                    )
                    self.show_control(editor)
                    control = editor.combo_box if hasattr(editor, 'combo_box') else editor.spin_box.spin_box
                    self.wheel(control)
                    self.assertEqual(config[key], option.default_config[key])
                    self.assertEqual(path.read_bytes(), original)
                    control.setFocus(Qt.FocusReason.MouseFocusReason)
                    self.app.processEvents()
                    self.wheel(control, 120)
                    self.assertNotEqual(config[key], option.default_config[key])
                    config[key] = option.default_config[key]
                    original = path.read_bytes()

    def test_open_dropdown_list_still_scrolls(self):
        combo = ComboBox([str(i) for i in range(100)])
        combo.setMaxVisibleItems(5)
        self.show_control(combo)
        combo.showPopup()
        self.app.processEvents()
        try:
            view = combo.view()
            before = view.verticalScrollBar().value()
            self.wheel(view.viewport())
            self.assertGreater(view.verticalScrollBar().value(), before)
        finally:
            combo.hidePopup()

    def test_installation_covers_existing_widgets_and_is_idempotent(self):
        guard = install_input_wheel_guard()
        for control in (QSpinBox(), QComboBox()):
            control.setFocusPolicy(Qt.FocusPolicy.WheelFocus)
            self.layout.addWidget(control)
        # Reinstall on a fresh application lifecycle, with fields already present.
        self.app.removeEventFilter(guard)
        del self.app._input_wheel_guard
        guard.deleteLater()
        replacement = install_input_wheel_guard()
        for control in (self.layout.itemAt(i).widget() for i in (1, 2)):
            self.assertEqual(control.focusPolicy(), Qt.FocusPolicy.StrongFocus)
        self.assertIs(replacement, install_input_wheel_guard())


if __name__ == '__main__':
    unittest.main()
