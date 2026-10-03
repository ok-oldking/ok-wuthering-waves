import re
import unittest

from src.task.BaseWWTask import BaseWWTask, LOGIN_CLICK_SETTLE_TIME, LOGIN_TEXTS


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
        if isinstance(match, re.Pattern):
            # 与真实 ok.find_boxes 一致:re.Pattern 做 re.search 子串匹配
            return [b for b in texts if re.search(match, b.name)] or None
        return None

    def click(self, target, after_sleep=0):
        # 与真实 ok.BaseTask.click 兼容:接受单个 Box 或 Box 列表
        targets = target if isinstance(target, list) else [target]
        self.clicked.append([b.name for b in targets])

    def sleep(self, timeout):
        self.slept.append(timeout)

    def log_info(self, *args, **kwargs):
        pass

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

    def test_connect_button_is_clicked(self):
        # 3.6.x 连接界面按钮:regex 子串匹配,OCR 文本含多余字符也能命中;
        # 多匹配(如右下角重试图标)时排序后取第一个(主按钮)
        task = FakeLoginTask(frames=[[TextBox('点击连接'), TextBox('点击连接 :: 重试')]])

        result = BaseWWTask.wait_login(task)

        self.assertFalse(result)
        self.assertEqual(task.clicked, [['点击连接']])


if __name__ == "__main__":
    unittest.main()
