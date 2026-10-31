import unittest
from unittest.mock import patch

import src.task.BaseWWTask as base_module
from ok import Box
from src.task.BaseWWTask import BaseWWTask, find_native_button

BUTTON = 0x1035
DIALOG = 0x32770


class FakeLoginTask:
    click_login = BaseWWTask.click_login
    _native_login_button = BaseWWTask._native_login_button

    def __init__(self, button=BUTTON, hwnd=None):
        self._native_login_attempts = {}
        self.button = button
        self.hwnd = hwnd
        self.clicks = []

    def log_info(self, *args):
        pass

    def log_debug(self, *args):
        pass

    def sleep(self, *args):
        pass

    def click(self, target, after_sleep=0):
        self.clicks.append(target)
        return True


class FakeLookupTask(FakeLoginTask):

    def _native_login_button(self, box):
        return self.button


class TestLoginButton(unittest.TestCase):

    def setUp(self):
        self.posted = []
        patches = [
            patch.object(base_module.win32gui, 'PostMessage', lambda *args: self.posted.append(args)),
            patch.object(base_module.win32gui, 'GetParent', lambda hwnd: DIALOG),
            patch.object(base_module.win32gui, 'GetDlgCtrlID', lambda hwnd: 1035),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def test_native_button_gets_bn_clicked_without_mouse(self):
        task = FakeLookupTask()
        login = [Box(100, 100, 50, 20, name='登录')]

        task.click_login(login)

        # WM_COMMAND, wParam = MAKEWPARAM(id, BN_CLICKED), lParam = 按钮句柄
        self.assertEqual([(DIALOG, base_module.win32con.WM_COMMAND, 1035, BUTTON)], self.posted)
        self.assertEqual([], task.clicks)

    def test_same_button_alternates_with_mouse_click(self):
        task = FakeLookupTask()
        login = [Box(100, 100, 50, 20, name='登录')]

        for _ in range(4):
            task.click_login(login)

        self.assertEqual(2, len(self.posted))
        self.assertEqual([login, login], task.clicks)

    def test_new_login_dialog_starts_with_bn_clicked_again(self):
        task = FakeLookupTask()
        login = [Box(100, 100, 50, 20, name='登录')]
        task.click_login(login)
        task.click_login(login)

        task.button = BUTTON + 1  # 切号后登录框重建，按钮句柄不同
        task.click_login(login)

        self.assertEqual(BUTTON + 1, self.posted[-1][3])
        self.assertEqual(1, len(task.clicks))

    def test_falls_back_to_click_without_native_button(self):
        task = FakeLookupTask(button=None)
        login = Box(100, 100, 50, 20, name='点击连接')

        task.click_login(login)

        self.assertEqual([], self.posted)
        self.assertEqual([login], task.clicks)

    def test_lookup_skipped_without_game_window(self):
        task = FakeLoginTask(hwnd=None)

        self.assertIsNone(task._native_login_button(Box(0, 0, 10, 10)))

    def test_lookup_maps_box_center_to_screen(self):
        class FakeHwnd:
            hwnd = 0x100

            @staticmethod
            def get_abs_cords(x, y):
                return x + 1000, y + 500

        task = FakeLoginTask(hwnd=FakeHwnd())
        with patch.object(base_module, 'find_native_button', return_value=BUTTON) as finder:
            self.assertEqual(BUTTON, task._native_login_button(Box(100, 100, 50, 20)))
        finder.assert_called_once_with(0x100, 1125, 610)


class TestFindNativeButton(unittest.TestCase):
    GAME, OTHER_DIALOG = 0x100, 0x400

    windows = {
        GAME: ('UnrealWindow', 1, True, True, None),
        DIALOG: ('#32770', 1, True, True, None),
        OTHER_DIALOG: ('#32770', 2, True, True, None),
        BUTTON: ('Button', 1, True, True, (1591, 1110, 2247, 1198)),
        0x201: ('Button', 1, True, True, (2190, 853, 2262, 925)),
        0x202: ('Button', 1, False, True, (1591, 1110, 2247, 1198)),
        0x401: ('Button', 2, True, True, (1591, 1110, 2247, 1198)),
    }
    children = {DIALOG: [0x202, 0x201, BUTTON], OTHER_DIALOG: [0x401]}

    def find(self, x, y):
        w = self.windows
        with patch.multiple(
                base_module.win32gui,
                IsWindow=lambda h: h in w,
                GetClassName=lambda h: w[h][0],
                IsWindowVisible=lambda h: w[h][2],
                IsWindowEnabled=lambda h: w[h][3],
                GetWindowRect=lambda h: w[h][4],
                # 另一个进程的对话框排在最前，它的按钮和登录按钮位置重叠，应该被跳过
                EnumWindows=lambda cb, extra: [cb(h, extra) for h in (self.OTHER_DIALOG, DIALOG, self.GAME)],
                EnumChildWindows=lambda parent, cb, extra: [cb(h, extra) for h in self.children.get(parent, [])],
        ), patch.object(base_module.win32process, 'GetWindowThreadProcessId', lambda h: (0, w[h][1])):
            return find_native_button(self.GAME, x, y)

    def test_finds_visible_button_of_game_process_under_point(self):
        self.assertEqual(BUTTON, self.find(1919, 1154))

    def test_returns_none_when_no_button_under_point(self):
        self.assertIsNone(self.find(100, 100))

    def test_returns_none_for_invalid_game_window(self):
        with patch.object(base_module.win32gui, 'IsWindow', lambda h: False):
            self.assertIsNone(find_native_button(0x999, 1919, 1154))


if __name__ == '__main__':
    unittest.main()
