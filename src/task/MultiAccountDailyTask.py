import ctypes
import re
from ctypes import wintypes

import win32con
import win32gui
import win32process

from ok import Box
from ok.task.exceptions import WaitFailedException
from src.task.DailyTask import DailyTask
from src.task.WWOneTimeTask import WWOneTimeTask
from src.task.BaseCombatTask import BaseCombatTask
from src.task.BaseWWTask import LOGIN_TEXTS
from src.task.MouseResetTask import MouseResetTask

account_pattern = re.compile(r'\*\*\*\*')

CB_GETCOUNT, CB_GETCURSEL, CB_GETLBTEXT, CB_GETLBTEXTLEN, CB_SETCURSEL = 0x146, 0x147, 0x148, 0x149, 0x14E
CBN_SELCHANGE = 1
_SendMessageW = ctypes.windll.user32.SendMessageW
_SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
_SendMessageW.restype = ctypes.c_ssize_t


def normalize_account_name(account):
    if not account:
        return account
    return account.lower().replace('0', 'o').replace('.con', '.com')


def find_login_combo(game_hwnd):
    """国际服 KRSDK 登录框是原生 #32770 对话框，账号列表是标准 ComboBox。
    后台模式下点击下拉列表项后选择会被撤销（#1316 #1678），所以能找到时直接读写 ComboBox。找不到返回 None。"""
    if not game_hwnd or not win32gui.IsWindow(game_hwnd):
        return None
    _, game_pid = win32process.GetWindowThreadProcessId(game_hwnd)
    combos = []

    def on_child(child, _):
        if (win32gui.GetClassName(child) == 'ComboBox' and win32gui.IsWindowVisible(child)
                and _SendMessageW(child, CB_GETCOUNT, 0, 0) > 0):
            combos.append(child)

    def on_top(hwnd, _):
        if (win32gui.GetClassName(hwnd) == '#32770' and win32gui.IsWindowVisible(hwnd)
                and win32process.GetWindowThreadProcessId(hwnd)[1] == game_pid):
            win32gui.EnumChildWindows(hwnd, on_child, None)

    win32gui.EnumWindows(on_top, None)
    return combos[0] if combos else None


def combo_items(combo):
    items = []
    for i in range(_SendMessageW(combo, CB_GETCOUNT, 0, 0)):
        buf = ctypes.create_unicode_buffer(max(_SendMessageW(combo, CB_GETLBTEXTLEN, i, 0), 0) + 1)
        _SendMessageW(combo, CB_GETLBTEXT, i, ctypes.addressof(buf))
        items.append(buf.value)
    return items


def combo_selected_item(combo):
    index = _SendMessageW(combo, CB_GETCURSEL, 0, 0)
    items = combo_items(combo)
    return items[index] if 0 <= index < len(items) else None


def select_combo_item(combo, index):
    """选中后通知父窗口 CBN_SELCHANGE，和用户手动选择一样让登录框更新当前账号。"""
    _SendMessageW(combo, CB_SETCURSEL, index, 0)
    parent = win32gui.GetParent(combo)
    _SendMessageW(parent, win32con.WM_COMMAND, (CBN_SELCHANGE << 16) | win32gui.GetDlgCtrlID(combo), combo)
    return _SendMessageW(combo, CB_GETCURSEL, 0, 0) == index


class MultiAccountDailyTask(WWOneTimeTask, BaseCombatTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "👥 Multi Account Daily Task"
        self.description = "Automatically switch accounts and run Daily Task for each account"
        self.add_exit_after_config()
        self.done_set = set()
        self.all_accounts = set()
        self.support_schedule_task = True

    def _mark_done(self, account):
        normalized = normalize_account_name(account)
        if normalized:
            self.done_set.add(normalized)

    def _is_done(self, account):
        return normalize_account_name(account) in self.done_set

    def _same_account(self, left, right):
        return normalize_account_name(left) == normalize_account_name(right)

    def run(self):
        WWOneTimeTask.run(self)
        self.done_set.clear()
        self.all_accounts.clear()

        self.run_task_by_class(DailyTask)
        self.ensure_main(time_out=100)
        self._switch_to_login()
        detected = self._detect_current_account_from_login()
        self._mark_done(detected)

        self.info_set('Completed', self.done_set)

        while next_account := self._select_and_login_account():
            self.info_set('Completed', self.done_set)
            self.run_task_by_class(DailyTask)
            self._mark_done(next_account)
            self.ensure_main(time_out=100)
            self._switch_to_login()

    def _click_center_offset(self, offset_x, offset_y, after_sleep=0.5):
        h, w = self.frame.shape[:2]
        rel_x = 0.5 + offset_x / w
        rel_y = 0.5 + offset_y / h
        self.click_relative(rel_x, rel_y, after_sleep=after_sleep)

    def _switch_to_login(self):
        self.log_info(self.tr('Switching back to login screen'))
        self.send_key('esc', after_sleep=1.5)
        self.wait_feature('esc_setting')
        self.click_relative(0.04, 0.96, after_sleep=1)
        self.click_confirm(timeout=10)
        # 登录框显示的账号没有 **** 时（非邮箱/手机号账号）OCR 等不到下拉框，原生 ComboBox 也算回到登录界面
        self.wait_until(lambda: self._login_combo() or self.do_find_account_drop_down(),
                        time_out=60, settle_time=2, raise_if_not_found=True)
        self.log_info(self.tr('Back at login screen'))

    def _login_combo(self):
        return find_login_combo(self.hwnd.hwnd if self.hwnd else 0)

    def _select_account_by_combo(self, combo):
        accounts = combo_items(combo)
        for name in accounts:
            self.all_accounts.add(normalize_account_name(name))
        self.info_set('All Accounts', self.all_accounts)
        for index, name in enumerate(accounts):
            if self._is_done(name):
                continue
            if not select_combo_item(combo, index):
                raise Exception(self.tr('Failed to switch account'))
            self.log_info(self.tr('Confirmed selected account: {account}').format(account=name))
            return name
        return None

    def _detect_current_account_from_login(self):
        if combo := self._login_combo():
            if account := combo_selected_item(combo):
                self.log_info(self.tr('Current account: {account}').format(account=account))
                return account
        texts = self.ocr(match=account_pattern)
        if texts:
            self.log_info(self.tr('Current account: {account}').format(account=texts[0]))
            return texts[0].name
        return None

    def _click_account_in_list(self):
        accounts = self.ocr(match=account_pattern)
        next_account = None
        # self.screenshot('_click_account_in_list')
        for account in accounts:
            self.all_accounts.add(normalize_account_name(account.name))
            self.info_set('All Accounts', self.all_accounts)
            if next_account is None and not self._is_done(account.name):
                next_account = account.name
                self.click(account, after_sleep=2)
        self.log_info(self.tr('Click next account: {account}').format(account=next_account))
        return next_account

    def _select_and_login_account(self):
        current_account = None
        mouse_reset_task = self.executor.get_task_by_class(MouseResetTask)
        mouse_reset_was_enabled = mouse_reset_task.enabled if mouse_reset_task else False
        if mouse_reset_was_enabled:
            mouse_reset_task.disable()
        try:
            combo = self._login_combo()
            if combo:
                current_account = self._select_account_by_combo(combo)
                if not current_account:
                    self.log_info(self.tr('No remaining account to run; finishing multi-account daily task'))
                    return None
            # 找不到原生 ComboBox 时（如其他登录界面）走原有的 OCR + 点击流程
            max_retries = 0 if combo else 5
            for attempt in range(1, max_retries + 1):
                # self.ensure_in_front()
                # self.update_capture({
                #     'windows': {
                #         'interaction': 'Pynput',
                #         'capture_method': 'ForegroundBitBlt',
                #     }
                # })
                self.sleep(1)
                drop_down = self.find_account_drop_down()
                if drop_down:
                    self.click(drop_down, after_sleep=2)
                if self.do_find_account_drop_down():
                    self.log_error('click drop down no effect')
                    self.screenshot('multi')
                    continue
                account = self.wait_until(
                    lambda: self._click_account_in_list(),
                    time_out=10, raise_if_not_found=False
                )
                if not account:
                    # _click_account_in_list() returns None once every account the login
                    # screen offers is already in done_set.  That is the normal end of a
                    # multi-account sweep, so let run()'s while loop stop instead of
                    # raising and failing the whole run after the work is already done.
                    if self.all_accounts and all(self._is_done(name) for name in self.all_accounts):
                        self.log_info(self.tr('No remaining account to run; finishing multi-account daily task'))
                        return None
                    # Nothing readable in the account list: keep the original failure signal.
                    raise WaitFailedException()
                self.sleep(1)
                current_account = self._detect_current_account_from_login()
                self.log_info(self.tr('Selected account: {selected}, displayed account: {displayed}').format(
                    selected=account, displayed=current_account))
                if self._same_account(account, current_account):
                    self.log_info(self.tr('Confirmed selected account: {account}').format(account=account))
                    break
                if attempt < max_retries:
                    self.log_info(self.tr('Account display does not match, retrying ({attempt}/{max_retries})').format(
                        attempt=attempt, max_retries=max_retries))
                else:
                    self.log_error(self.tr(
                        'Account selection failed after {max_retries} retries; {account} is still not displayed. Continuing login attempt'
                    ).format(max_retries=max_retries, account=account))
                    raise Exception(self.tr('Failed to switch account'))
            self.sleep(4)
            texts = self.ocr()
            login_btn = self.find_boxes(texts, boundary=self.box_of_screen(0.3, 0.3, 0.7, 0.8),
                                        match=LOGIN_TEXTS)
            if login_btn:
                self.click_login(login_btn, after_sleep=3)
            else:
                self.click_relative(0.5, 0.568, hcenter=True, vcenter=True, after_sleep=3)
            self.logged_in = False
            # self.update_capture({
            #     'windows': {
            #         'interaction': 'PostMessage',
            #         'capture_method': ['WGC', 'BitBlt_RenderFull'],
            #     }
            # })
            self.ensure_main(time_out=180)
            self.log_info(self.tr('Login successful'))
            return current_account
        finally:
            if mouse_reset_was_enabled:
                mouse_reset_task.enable()

    def find_account_drop_down(self):
        return self.wait_until(self.do_find_account_drop_down, time_out=60, settle_time=2, raise_if_not_found=True)

    def do_find_account_drop_down(self) -> Box | None:
        texts = self.ocr()
        account_boxes = self.find_boxes(texts, account_pattern)
        login_boxes = self.find_boxes(texts, LOGIN_TEXTS)
        if len(account_boxes) == 1 and login_boxes:
            return account_boxes[0]
        return None


from ok import run_task
from config import config

if __name__ == "__main__":
    run_task(config, task=MultiAccountDailyTask, debug=True)
