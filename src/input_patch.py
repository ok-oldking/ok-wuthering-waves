import ctypes
import time
from PySide6.QtCore import Qt, QObject, QEvent
from PySide6.QtWidgets import QApplication
from ok import Logger

logger = Logger.get_logger(__name__)

# Windows API constants for mouse simulation
user32 = ctypes.windll.user32
XBUTTON1 = 0x0001
XBUTTON2 = 0x0002
MOUSEEVENTF_XDOWN = 0x0080
MOUSEEVENTF_XUP = 0x0100

WM_XBUTTONDOWN = 0x020B
WM_XBUTTONUP = 0x020C
MK_XBUTTON1 = 0x0020
MK_XBUTTON2 = 0x0040

MOUSE_BUTTON_MAP = {
    'mouse4': XBUTTON1,
    'xbutton1': XBUTTON1,
    'mouse5': XBUTTON2,
    'xbutton2': XBUTTON2,
}


def is_mouse_button(key: str) -> bool:
    if not isinstance(key, str):
        return False
    return key.strip().lower() in MOUSE_BUTTON_MAP


def send_mouse_button_event(key: str, interaction=None, down=True, up=True, down_time=0.02):
    btn = MOUSE_BUTTON_MAP.get(str(key).strip().lower())
    if btn is None:
        return False

    # If running with PostMessage backend, post directly to game window to prevent affecting other apps
    if interaction is not None and hasattr(interaction, 'post') and hasattr(interaction, 'hwnd'):
        import win32api
        pos = getattr(interaction, 'mouse_pos', (0, 0))
        lparam = win32api.MAKELONG(pos[0], pos[1])
        if down:
            mk = MK_XBUTTON1 if btn == XBUTTON1 else MK_XBUTTON2
            wparam = win32api.MAKELONG(mk, btn)
            interaction.post(WM_XBUTTONDOWN, wparam, lparam)
        if down and up:
            time.sleep(down_time)
        if up:
            wparam = win32api.MAKELONG(0, btn)
            interaction.post(WM_XBUTTONUP, wparam, lparam)
        return True

    # Fallback to system mouse event
    if down:
        user32.mouse_event(MOUSEEVENTF_XDOWN, 0, 0, btn, 0)
    if down and up:
        time.sleep(down_time)
    if up:
        user32.mouse_event(MOUSEEVENTF_XUP, 0, 0, btn, 0)
    return True


class GlobalMouseButtonFilter(QObject):
    """
    Application-level event filter for XButton1 / XButton2.
    Routes mouse4/mouse5 exclusively to the widget that currently holds keyboard focus
    (the active cursor/focused box), regardless of where the mouse pointer is hovering.
    Also consumes mouse events to prevent Windows / Qt default back/forward navigation.
    """

    def eventFilter(self, watched, event):
        evt_type = event.type()
        if evt_type in (
            QEvent.Type.MouseButtonPress,
            QEvent.Type.MouseButtonRelease,
            QEvent.Type.MouseButtonDblClick,
            QEvent.Type.NonClientAreaMouseButtonPress,
            QEvent.Type.NonClientAreaMouseButtonRelease,
        ):
            btn = event.button()
            if btn in (Qt.MouseButton.XButton1, Qt.MouseButton.XButton2):
                focused = QApplication.focusWidget()
                if focused is not None and getattr(focused, '_is_hotkey_input', False):
                    if evt_type == QEvent.Type.MouseButtonPress:
                        key_name = 'mouse4' if btn == Qt.MouseButton.XButton1 else 'mouse5'
                        focused.setText(key_name)
                        focused.setFocus(Qt.FocusReason.MouseFocusReason)
                    event.accept()
                    return True
        return super().eventFilter(watched, event)


_global_mouse_filter = None


def ensure_global_filter():
    global _global_mouse_filter
    app = QApplication.instance()
    if app is not None and _global_mouse_filter is None:
        _global_mouse_filter = GlobalMouseButtonFilter(app)
        app.installEventFilter(_global_mouse_filter)
        logger.info("GlobalMouseButtonFilter installed on QApplication")


def apply_patches():
    """Apply monkey patches to ok-script to support mouse4 and mouse5."""
    try:
        import ok.task.task as tt
        # Allow mouse4/mouse5 in key validation
        tt.VALID_NAMED_KEYS.update(['mouse4', 'mouse5', 'xbutton1', 'xbutton2'])
        logger.info("ok.task.task.VALID_NAMED_KEYS updated with mouse buttons")
    except Exception as e:
        logger.warning(f"Failed to update VALID_NAMED_KEYS: {e}")

    try:
        import ok.ui.qt.tasks.LabelAndLineEdit as l
        original_init = l.LabelAndLineEdit.__init__

        def patched_init(self, config_desc, config, key: str, options=None):
            original_init(self, config_desc, config, key, options)
            # Mark this line_edit as an active hotkey input field
            self.line_edit._is_hotkey_input = True
            ensure_global_filter()

        l.LabelAndLineEdit.__init__ = patched_init
        logger.info("ok.ui.qt.tasks.LabelAndLineEdit patched with _is_hotkey_input marker")
    except Exception as e:
        logger.warning(f"Failed to patch LabelAndLineEdit: {e}")

    try:
        ensure_global_filter()
    except Exception as e:
        logger.warning(f"Failed to install GlobalMouseButtonFilter: {e}")
