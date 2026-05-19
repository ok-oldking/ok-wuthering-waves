import re

from qfluentwidgets import FluentIcon

from ok import Box
from src.task.DailyTask import DailyTask
from src.task.WWOneTimeTask import WWOneTimeTask
from src.task.BaseCombatTask import BaseCombatTask
from src.task.MouseResetTask import MouseResetTask

account_pattern = re.compile(r'\*\*\*\*')


class MultiAccountDailyTask(WWOneTimeTask, BaseCombatTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Multi Account Daily Task"
        self.group_name = "Daily"
        self.group_icon = FluentIcon.CALENDAR
        self.icon = FluentIcon.PEOPLE
        self.description = "Automatically switch accounts and run Daily Task for each account"
        self.add_exit_after_config()
        self.done_set = set()
        self.all_accounts = set()
        self.support_schedule_task = True

    def run(self):
        WWOneTimeTask.run(self)
        self.done_set.clear()
        self.all_accounts.clear()

        self.run_task_by_class(DailyTask)
        # self.ensure_main(time_out=100)
        self._switch_to_login()
        detected = self._detect_current_account_from_login()
        if detected:
            self.done_set.add(detected)

        self.info_set('Completed', self.done_set)

        while next_account := self._select_and_login_account():
            self.info_set('Completed', self.done_set)
            self.run_task_by_class(DailyTask)
            self.done_set.add(next_account)

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
        self.find_account_drop_down()
        self.log_info(self.tr('Back at login screen'))

    def _detect_current_account_from_login(self):
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
            self.all_accounts.add(account.name)
            self.info_set('All Accounts', self.all_accounts)
            if next_account is None and account.name not in self.done_set:
                next_account = account.name
                self.click(account, after_sleep=1)
        self.log_info(self.tr('Click next account: {account}').format(account=next_account))
        return next_account

    def _select_and_login_account(self):
        current_account = None
        mouse_reset_task = self.executor.get_task_by_class(MouseResetTask)
        mouse_reset_was_enabled = mouse_reset_task.enabled if mouse_reset_task else False
        if mouse_reset_was_enabled:
            mouse_reset_task.disable()
        try:
            max_retries = 5
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
                account = self.wait_until(
                    lambda: self._click_account_in_list(),
                    time_out=10, raise_if_not_found=True
                )
                self.sleep(1)
                current_account = self._detect_current_account_from_login()
                self.log_info(self.tr('Selected account: {selected}, displayed account: {displayed}').format(
                    selected=account, displayed=current_account))
                if account == current_account:
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
                                        match=["登录", 'Login', '登入'])
            if login_btn:
                self.click(login_btn, after_sleep=3)
            else:
                self.click_relative(0.502, 0.568, after_sleep=3)
            self._logged_in = False
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
        return self.wait_until(self.do_find_account_drop_down, time_out=60, settle_time=2)

    def do_find_account_drop_down(self) -> Box | None:
        if self.find_one('account_close', horizontal_variance=0.05, vertical_variance=0.05):
            drop_down = self.find_one('account_drop_down', horizontal_variance=0.05, vertical_variance=0.05)
            return drop_down
        return None


from ok import run_task
from config import config

if __name__ == "__main__":
    run_task(config, task=MultiAccountDailyTask, debug=True)
