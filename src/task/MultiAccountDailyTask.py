import ctypes
import re
from ctypes import wintypes

import win32con
import win32gui
import win32process

from ok import Box
from ok.task.exceptions import TaskDisabledException, WaitFailedException
from src import cloud_browser
from src.cloud_recovery import FatalTaskError, run_with_cloud_recovery, wait_cloud_ready
from src.task.DailyTask import DailyTask
from src.task.WWOneTimeTask import WWOneTimeTask
from src.task.BaseCombatTask import BaseCombatTask
from src.task.BaseWWTask import LOGIN_TEXTS
from src.task.MouseResetTask import MouseResetTask
from src.task.account.MultiAccountConfigStore import (
    MultiAccountConfigStore, display_account, resolve_task, validate_accounts,
)
from src.task.account.RuntimeTaskConfig import account_task_config, isolated_task_configs
from src.task.task_icons import task_icon

account_pattern = re.compile(r'\*\*\*\*')
PER_ACCOUNT_CONFIGURATION = 'Per-account Configuration'
ACCOUNT_CONFIGURATION = 'Account Configuration'
# 云鸣潮账号操作：只在云游戏设备下显示。云游戏把登录态存在浏览器 profile 里，
# 没有 PC 那种账号下拉框，所以"保存登录状态/切换账号"是独立于登录框的一套动作。
CLOUD_ACCOUNT_ACTIONS = '云鸣潮账号操作'
CLOUD_SAVE_BUTTON = '保存登录状态'
CLOUD_SWITCH_BUTTON = '切换账号'

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
        self.icon = task_icon('multi-account')
        self.group_name = 'Multi-account'
        self.group_icon = task_icon('multi-account')
        self.description = "Automatically switch accounts and run Daily Task for each account"
        self.add_exit_after_config()
        self.default_config[PER_ACCOUNT_CONFIGURATION] = False
        self.config_description.update({
            PER_ACCOUNT_CONFIGURATION: 'Configure tasks separately for each account. When disabled, run the original multi-account daily task.',
            ACCOUNT_CONFIGURATION: 'Edit account order, enabled accounts, tasks and task settings.',
        })
        self._config_type.update({
            PER_ACCOUNT_CONFIGURATION: {'sub_configs': {True: [ACCOUNT_CONFIGURATION]}},
            ACCOUNT_CONFIGURATION: {
                'type': 'button', 'text': 'Configure Accounts', 'callback': self.configure_accounts,
            },
        })
        # 云鸣潮专用按钮：和「配置账号」一样放在任务配置里，不单独占一个任务。
        # 只在云游戏设备下出现（见 config_type property）。
        self._config_type[CLOUD_ACCOUNT_ACTIONS] = {
            'buttons': [
                {'text': CLOUD_SAVE_BUTTON, 'callback': self.save_cloud_login_state},
                {'text': CLOUD_SWITCH_BUTTON, 'callback': self.choose_cloud_account},
            ],
        }
        self.config_description[CLOUD_ACCOUNT_ACTIONS] = (
            '云鸣潮专用：把当前浏览器的登录态保存到账号，或换一个账号重开浏览器。'
        )
        self._cloud_switch_bridge = None
        self.done_set = set()
        self.all_accounts = set()
        self.support_schedule_task = True

    # 配置项按设备类型动态显示：云游戏设备用浏览器 profile 保存登录态，PC 客户端
    # 走游戏自带账号下拉框，两者互不适用。config_type 在配置面板构建时被读取，
    # 这里按当前设备过滤 —— 不改框架，只改这个任务自己的配置表。
    @property
    def config_type(self):
        types = self._config_type
        if self._is_cloud_device():
            # 云游戏：账号列表始终来自「配置账号」，标志位无意义 -> 隐藏并直接显示按钮。
            types = dict(types)
            types[PER_ACCOUNT_CONFIGURATION] = {'hidden': True}
            types[ACCOUNT_CONFIGURATION] = self._configure_accounts_button()
            types[CLOUD_ACCOUNT_ACTIONS] = self._cloud_actions_buttons()
            return types
        types = dict(types)
        types.pop(CLOUD_ACCOUNT_ACTIONS, None)
        return types

    @config_type.setter
    def config_type(self, value):
        self._config_type = dict(value or {})

    def _configure_accounts_button(self):
        return {'type': 'button', 'text': 'Configure Accounts', 'callback': self.configure_accounts}

    def _cloud_actions_buttons(self):
        return {
            'buttons': [
                {'text': CLOUD_SAVE_BUTTON, 'callback': self.save_cloud_login_state},
                {'text': CLOUD_SWITCH_BUTTON, 'callback': self.choose_cloud_account},
            ],
        }

    def _is_cloud_device(self):
        # 设备列表刷新前 device_dict 里没有 'browser' 项, get_preferred_device() 返回
        # None（游戏没启动时也一样）。这时只能看「已保存的设备标识」：
        # config.py 给每个安装都定义了 browser 段, 用 browser_config 判断会把 PC
        # 用户也当成云游戏（隐藏逐账号配置、显示云按钮、run() 走 _run_cloud）。
        try:
            manager = self.executor.device_manager
        except Exception:
            return False
        try:
            preferred = manager.get_preferred_device()
        except Exception:
            preferred = None
        if preferred is not None:
            return preferred.get('device') == 'browser'
        config = getattr(manager, 'config', None)
        try:
            saved = config.get('preferred') if config is not None else None
        except Exception:
            saved = None
        return saved == 'browser'

    def _mark_done(self, account):
        normalized = normalize_account_name(account)
        if normalized:
            self.done_set.add(normalized)

    def _is_done(self, account):
        return normalize_account_name(account) in self.done_set

    def _same_account(self, left, right):
        return normalize_account_name(left) == normalize_account_name(right)

    def run(self):
        # 云游戏没有游戏内登录框：账号 = 一个浏览器 profile，切换要重开浏览器。
        # 设备类型在运行时判断，用户只选设备再执行同一个任务即可。
        if self._is_cloud_device():
            return self._run_cloud()
        if self.config.get(PER_ACCOUNT_CONFIGURATION, False):
            # Import lazily: the configured runner inherits the shared login helpers.
            from src.task.MultiAccountConfigTask import MultiAccountConfigTask
            return self.run_task_by_class(MultiAccountConfigTask)
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

    # --- 云鸣潮 (browser device) -------------------------------------------

    def _account_store(self):
        return MultiAccountConfigStore(self.executor.config_folder)

    def _run_cloud(self):
        """云鸣潮多账号：每个账号一个浏览器 profile，逐个换号执行每日任务."""
        WWOneTimeTask.run(self)
        store = self._account_store()
        accounts = store.load()
        validate_accounts(accounts, self.executor)
        enabled = [account for account in accounts if account.get('enabled', True)]
        self.info_set('全部配置账号', [display_account(a['account_key']) for a in accounts])
        if not enabled:
            self.log_warning(self.tr(
                '未配置账号：只执行当前已登录的云游戏账号。需要多账号请点「配置账号」。'))
            self._run_cloud_account(None)
            return

        completed = []
        self.info_set('状态', '执行中')
        self.info_set('已完成', completed.copy())
        for account in enabled:
            key = account['account_key']
            self.info_set('当前账号', display_account(key))
            try:
                self._run_cloud_account(account)
            except TaskDisabledException:
                # 用户主动停止: 与 PC 的逐账号流程一致, 记为 cancelled 后继续抛出。
                self._record_cloud_result(store, account, 'cancelled', '任务已停止')
                self.info_set('状态', '已停止')
                raise
            except Exception as error:
                self._record_cloud_result(store, account, 'failed', str(error))
                self.info_set('状态', '执行失败')
                self.info_set('Error', str(error))
                raise
            self._record_cloud_result(store, account, 'success')
            completed.append(display_account(key))
            self.info_set('已完成', completed.copy())
        self.info_set('状态', '全部完成')

    def _record_cloud_result(self, store, account, status, message=''):
        try:
            store.record_result(account, status, message)
        except (OSError, ValueError) as error:
            self.log_warning(self.tr('Failed to save account run history: {error}').format(error=error))

    def _switch_cloud_profile(self, key, label):
        """Point the live browser profile at ``key`` before its run starts."""
        active = cloud_browser.get_active_account()
        if cloud_browser.profile_matches(key):
            cloud_browser.set_active_account(key)
            return
        # 首次升级：浏览器里已经登录着活动账号，认领这份 profile，不必重开。
        if key == active and cloud_browser.adopt_live_profile(key):
            return
        self.log_info(self.tr('切换到账号 {account}（重开云游戏浏览器）').format(account=label))
        if not cloud_browser.restart_browser(self, account_key=key):
            raise FatalTaskError(self.tr(
                '无法为账号 {account} 启动云游戏浏览器，请检查浏览器是否可用。'
            ).format(account=label))

    def _run_cloud_account(self, account):
        """换到该账号的 profile 并跑它自己的任务（account 为 None 表示当前账号）.

        ``account`` 为 None 表示「一个账号都没配置」：沿用旧行为，对当前已登录的
        账号跑一次默认日常。``account['task']`` 为 None 表示「只登录不跑任务」，
        两者含义不同，不能都退化成 DailyTask。
        """
        has_account = account is not None
        key = account['account_key'] if has_account else None
        label = display_account(key) if key else self.tr('当前账号')
        task = resolve_task(self.executor, account['task']) if has_account else None

        if key:
            self._switch_cloud_profile(key, label)

        def work():
            # 副本现场恢复成功后云端仍停在（或刚离开）副本，不能再走
            # ensure_main：它在副本里会按 Esc 退出，等于白续打这一场。
            if getattr(self, '_cloud_reward_resumed', False):
                self.log_info(self.tr('副本现场已续打并领奖，接着执行本账号剩余任务。'))
            else:
                wait_cloud_ready(self, time_out=600)
            # 与 PC 逐账号流程一致：每个账号用独立的运行时配置，账号之间的
            # 任务配置（含被间接调用的任务）不会互相串。
            with isolated_task_configs(self.executor.get_all_tasks()):
                if not has_account:
                    self.run_task_by_class(DailyTask)
                elif task is None:
                    self.log_info(self.tr('Login successful; task is set to None, skipping.'))
                else:
                    # 按该账号自己勾选的配置执行（含刷梦魇巢穴/4C 等）。
                    with account_task_config(task, account['config']):
                        self.run_task_by_class(type(task))
            self.ensure_main(time_out=100)

        # 云游戏出错时刷新页面/重开浏览器并从头跑该账号, 不再因为一次识别失败中断所有账号.
        run_with_cloud_recovery(self, work, name=label, wait_ready=False)

    def save_cloud_login_state(self, *args):
        """按钮：把当前云游戏浏览器的登录态保存到指定账号."""
        if not self._is_cloud_device():
            self._cloud_message('请先把设备切换为「云游戏」并完成登录，再保存登录状态。')
            return
        if cloud_browser.get_browser_capture(self) is None:
            self._cloud_message('没有检测到运行中的云游戏浏览器，请先连接云游戏设备。')
            return
        key = self._pick_account('保存登录状态', cloud_browser.get_active_account())
        if not key:
            return
        if cloud_browser.save_current(self, key):
            cloud_browser.set_active_account(key)
            self.log_info(self.tr('已保存账号 {account} 的登录状态').format(account=key), notify=True)
            self._cloud_message(f'已保存账号 {key} 的登录状态。')
        else:
            self._cloud_message('保存失败：浏览器没有响应，请稍后重试。')

    def choose_cloud_account(self, *args):
        """按钮：切换到另一个云鸣潮账号（保存当前登录态后重开浏览器）."""
        if not self._is_cloud_device():
            self._cloud_message('请先把设备切换为「云游戏」，再切换账号。')
            return
        key = self._pick_account('切换云游戏账号', cloud_browser.get_active_account())
        if not key:
            return
        if cloud_browser.get_browser_capture(self) is None:
            cloud_browser.set_active_account(key)
            self._cloud_message(f'已记录账号 {key}，下次连接云游戏时生效。')
            return
        self._cloud_message(f'正在切换到账号 {key}，浏览器会重新打开，请稍候…', blocking=False)

        def done(ok, message):
            self._cloud_switch_bridge = None
            self._cloud_message(
                f'已切换到账号 {key}。' if ok else f'切换账号失败：{message or "未知错误"}')

        self._switch_in_background(key, done)

    def _pick_account(self, title, default=None):
        """让用户选/填账号 ID：配置里已有账号时给下拉，否则填文本框."""
        from PySide6.QtWidgets import QApplication, QInputDialog, QLineEdit
        parent = QApplication.activeWindow()
        keys = []
        try:
            keys = [a['account_key'] for a in self._account_store().load() if a.get('account_key')]
        except (OSError, ValueError):
            keys = []
        if keys:
            current = keys.index(default) if default in keys else 0
            item, ok = QInputDialog.getItem(parent, title, '账号：', keys, current, True)
            return item.strip() if ok and item and item.strip() else None
        text, ok = QInputDialog.getText(parent, title, '账号 ID：', QLineEdit.EchoMode.Normal,
                                        default or '')
        return text.strip() if ok and text and text.strip() else None

    def _switch_in_background(self, key, on_done):
        """在后台线程换号，避免重开浏览器时卡住 Qt 界面."""
        import threading

        from PySide6.QtCore import QObject, Signal

        if self._cloud_switch_bridge is not None:
            return

        class _Bridge(QObject):
            finished = Signal(bool, str)

        bridge = _Bridge()
        bridge.finished.connect(on_done)
        self._cloud_switch_bridge = bridge

        def worker():
            try:
                ok = cloud_browser.switch_account(self, key)
                message = '' if ok else '浏览器启动失败，请检查浏览器/网络后重试。'
            except Exception as error:  # pragma: no cover - depends on live browser
                ok, message = False, str(error)
            try:
                bridge.finished.emit(bool(ok), message)
            except RuntimeError:  # window already closed
                pass

        threading.Thread(target=worker, name='cloud-account-switch', daemon=True).start()

    def _cloud_message(self, text, blocking=True):
        from PySide6.QtWidgets import QApplication, QMessageBox
        parent = QApplication.activeWindow()
        if not blocking:
            self.log_info(text)
            return
        QMessageBox.information(parent, self.tr('云鸣潮账号'), text)

    def configure_accounts(self):
        # Config button callbacks run on the Qt thread; game work stays in run().
        from PySide6.QtWidgets import QApplication
        from src.gui.MultiAccountConfigDialog import MultiAccountConfigDialog

        dialog = MultiAccountConfigDialog(QApplication.activeWindow(), self)
        try:
            dialog.exec()
        finally:
            dialog.deleteLater()

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
                    self.log_error(self.tr('click drop down no effect'))
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
                self.click(login_btn, after_sleep=3)
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
