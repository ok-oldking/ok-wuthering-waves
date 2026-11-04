"""Require keyboard focus before wheel input can change a field's value."""

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QAbstractSpinBox, QApplication, QComboBox, QLineEdit


_WHEEL_INPUTS = (QAbstractSpinBox, QComboBox)


class InputWheelGuard(QObject):
    def eventFilter(self, watched, event):
        event_type = event.type()
        if event_type == QEvent.Type.Polish and isinstance(watched, _WHEEL_INPUTS):
            # WheelFocus would let hovering acquire focus before wheel delivery.
            watched.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        elif event_type == QEvent.Type.Wheel:
            control = watched
            if isinstance(watched, QLineEdit):
                control = watched.parentWidget()
            if isinstance(control, _WHEEL_INPUTS) and not control.hasFocus():
                # A filtered event bypasses Qt's normal parent propagation.
                # Forward it explicitly so hovering a field still scrolls the page.
                event.ignore()
                parent = control.parentWidget()
                while parent is not None:
                    forwarded = QWheelEvent(
                        parent.mapFromGlobal(event.globalPosition()), event.globalPosition(),
                        event.pixelDelta(), event.angleDelta(), event.buttons(), event.modifiers(),
                        event.phase(), event.inverted(), event.source(), event.pointingDevice(),
                    )
                    forwarded.setTimestamp(event.timestamp())
                    forwarded.ignore()
                    QApplication.sendEvent(parent, forwarded)
                    if forwarded.isAccepted():
                        event.accept()
                        break
                    parent = parent.parentWidget()
                return True
        return False


def install_input_wheel_guard():
    app = QApplication.instance()
    guard = getattr(app, '_input_wheel_guard', None)
    if guard is None:
        guard = InputWheelGuard(app)
        app._input_wheel_guard = guard
        app.installEventFilter(guard)
        for widget in app.allWidgets():
            if isinstance(widget, _WHEEL_INPUTS):
                widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    return guard
