import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from ok import CannotFindException
from ok.core.events import communicate
from src.Labels import Labels
from src.task.BaseWWTask import BaseWWTask, CONNECT_TEXT, LOGIN_CLICK_SETTLE_TIME, LOGIN_TEXTS


class TextBox:
    def __init__(self, name):
        self.name = name


class FakeLoginTask:
    """Drives BaseWWTask.wait_login with scripted OCR frames.

    Each entry in frames is the list of TextBox returned by one ocr() call,
    so a frame sequence like [[login], []] simulates a login button that
    disappears while the game's own auto login is running (#1356).
    """

    def __init__(self, frames):
        self.frames = list(frames)
        self.logged_in = False
        self.debug = False
        self.clicked = []
        self.slept = []

    def in_team_and_world(self):
        return False

    def handle_monthly_card(self):
        return False

    def find_one(self, *args, **kwargs):
        return None

    def box_of_screen(self, *args, **kwargs):
        return args

    def ocr(self, log=False):
        return self.frames.pop(0) if self.frames else []

    def find_boxes(self, texts, boundary=None, match=None):
        if not texts:
            return None
        if match == LOGIN_TEXTS:
            return [b for b in texts
                    if 'log' in b.name.lower() or '登录' in b.name or '登入' in b.name] or None
        if match == "+86":
            return [b for b in texts if '+86' in b.name] or None
        return None

    def click(self, target, after_sleep=0):
        self.clicked.append([b.name for b in target])

    def sleep(self, timeout):
        self.slept.append(timeout)

    def log_info(self, *args, **kwargs):
        pass

    def tr(self, message):
        return message

    def log_debug(self, *args, **kwargs):
        pass


class TestWaitLogin(unittest.TestCase):

    def test_transient_login_button_is_not_clicked(self):
        # Global server auto login: the login button disappears by itself,
        # clicking it would pop up the account/password dialog (#1356).
        task = FakeLoginTask(frames=[[TextBox('Log In')], []])

        result = BaseWWTask.wait_login(task)

        self.assertFalse(result)
        self.assertEqual(task.clicked, [])
        self.assertEqual(task.slept, [LOGIN_CLICK_SETTLE_TIME])

    def test_persistent_login_button_is_clicked(self):
        # No saved credentials: the login button stays, so it must be clicked.
        task = FakeLoginTask(frames=[[TextBox('Log In')], [TextBox('Log In')]])

        result = BaseWWTask.wait_login(task)

        self.assertFalse(result)
        self.assertEqual(task.clicked, [['Log In']])

    def test_no_click_and_no_settle_when_phone_login_is_already_shown(self):
        # +86 phone login present on the first frame: the pre-existing guard
        # must skip both the click and the settle wait entirely.
        task = FakeLoginTask(frames=[[TextBox('登录'), TextBox('+86 手机号')]])

        result = BaseWWTask.wait_login(task)

        self.assertFalse(result)
        self.assertEqual(task.clicked, [])
        self.assertEqual(task.slept, [])

    def test_no_click_when_phone_login_appears_after_settle(self):
        # CN phone-number login screen (+86) must never be auto clicked,
        # even when it only shows up on the confirmation frame.
        task = FakeLoginTask(frames=[[TextBox('登录')],
                                     [TextBox('登录'), TextBox('+86 手机号')]])

        result = BaseWWTask.wait_login(task)

        self.assertFalse(result)
        self.assertEqual(task.clicked, [])

    def test_connect_screen_retries_without_pressing_escape(self):
        connect = TextBox('点击连接')
        task = FakeLoginTask(frames=[[connect]])
        task.find_one = lambda label, **kwargs: label == Labels.switch_account
        task.find_boxes = lambda texts, boundary=None, match=None: (
            texts if match is CONNECT_TEXT or boundary == (0.37, 0.63, 0.63, 0.99) else None
        )
        task.wait_login = lambda: BaseWWTask.wait_login(task)
        task.click_relative = Mock()
        task.back = Mock()

        self.assertFalse(BaseWWTask.is_main(task))

        task.click_relative.assert_called_once()
        task.back.assert_not_called()

    def test_login_timeout_only_queues_exit_for_exit_after_task(self):
        for exit_after in (True, False):
            with self.subTest(exit_after=exit_after):
                executor = Mock()
                executor.current_task.exit_after_task = exit_after
                task = SimpleNamespace(tr=str, info_set=Mock(), executor=executor, logged_in=False)

                def wait_for_world(*args, **kwargs):
                    task.login_screen_visible = True
                    return False

                task.wait_until = Mock(side_effect=wait_for_world)
                with self.assertRaisesRegex(CannotFindException, 'Timed out on the game login screen'):
                    BaseWWTask.ensure_main(task)

                if exit_after:
                    task.executor.submit.assert_called_once_with(communicate.quit.emit, name='quit after login timeout')
                else:
                    task.executor.submit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
