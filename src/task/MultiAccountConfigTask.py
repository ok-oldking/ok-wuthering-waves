import win32api

from ok import PostMessageInteraction
from ok.task.exceptions import TaskDisabledException, WaitFailedException

from src.task.BaseWWTask import LOGIN_TEXTS
from src.task.MouseResetTask import MouseResetTask
from src.task.MultiAccountDailyTask import (
    MultiAccountDailyTask, combo_items, combo_selected_item, select_combo_item,
)
from src.task.WWOneTimeTask import WWOneTimeTask
from src.task.account.MultiAccountConfigStore import (
    MultiAccountConfigStore, account_key_from_ocr, display_account,
    resolve_task, validate_accounts,
)
from src.task.account.RuntimeTaskConfig import account_task_config, isolated_task_configs


class MultiAccountConfigTask(MultiAccountDailyTask):
    """Read account data from local configs/MultiAccountConfig.json only.

    Account identifiers and per-account task settings must not be embedded here.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = 'Multi Account Config Task'
        self.description = 'Log in to accounts in card order and run tasks with independent configurations'
        self.default_config = {}
        self.config_description = {}
        self.visible = False

    def click(self, x=-1, y=-1, *args, **kwargs):
        # Box and relative clicks are resolved by the framework and re-enter
        # this method with capture-pixel coordinates. Keep both coordinates
        # identical so the native login dialog receives a real hover before
        # its background button messages (WM_MOUSEMOVE alone is insufficient).
        if (getattr(self, '_login_cursor_active', False)
                and isinstance(x, (int, float)) and isinstance(y, (int, float))
                and x >= 1 and y >= 1
                and isinstance(self.executor.interaction, PostMessageInteraction)):
            position = self.executor.interaction.capture.get_abs_cords(x, y)
            win32api.SetCursorPos((int(position[0]), int(position[1])))
            self.sleep(0.2)
        return super().click(x, y, *args, **kwargs)

    def run(self):
        store = MultiAccountConfigStore(self.executor.config_folder)
        accounts = store.load()
        validate_accounts(accounts, self.executor)
        if not accounts:
            raise ValueError('请先添加账号并保存配置。')
        # Resolve the entire plan before sending any game input.
        plan = [(account, resolve_task(self.executor, account['task'])) for account in accounts
                if account.get('enabled', True)]
        self.info_set('全部配置账号', [display_account(a['account_key']) for a in accounts])
        if not plan:
            self.info_set('状态', '没有启用的账号')
            return

        def record_result(account, status, message=''):
            try:
                store.record_result(account, status, message)
            except (OSError, ValueError) as error:
                self.log_warning(f'保存账号运行记录失败：{error}')
        completed = []
        self.info_set('状态', '执行中')
        self.info_set('已完成', completed.copy())
        try:
            # Reset for every account, including configs of indirectly called tasks.
            for index, (account, task) in enumerate(plan):
                try:
                    self._target_account_key = account['account_key']
                    with isolated_task_configs(self.executor.get_all_tasks()):
                        if index == 0:
                            WWOneTimeTask.run(self)
                            self.ensure_main(time_out=100)
                            self._switch_to_login()
                        self.info_set('当前账号', display_account(account['account_key']))
                        self.info_set('执行任务', self.tr(task.name) if task else '无')
                        self._login_target_account(account['account_key'])
                        if task is None:
                            self.log_info('登录成功；执行任务为“无”，跳过任务。')
                        else:
                            with account_task_config(task, account['config']):
                                self.run_task_by_class(type(task))
                        self.ensure_main(time_out=100)
                        self._switch_to_login()
                except TaskDisabledException:
                    record_result(account, 'cancelled', '任务已停止')
                    raise
                except Exception as error:
                    record_result(account, 'failed', str(error))
                    raise
                record_result(account, 'success')
                completed.append(display_account(account['account_key']))
                self.info_set('已完成', completed.copy())
            self.info_set('状态', '全部完成')
        except TaskDisabledException:
            self.info_set('状态', '已停止')
            raise
        except Exception as error:
            self.info_set('状态', '执行失败')
            self.info_set('Error', str(error))
            raise

    def _find_target_account(self, account_key):
        matches = [box for box in self.ocr()
                   if account_key_from_ocr(box.name) == account_key]
        if matches:
            # The dropdown can repeat the currently displayed account above the
            # selectable row. Prefer the lowest matching OCR box, regardless of OCR order.
            self.click(max(matches, key=lambda box: box.y + box.height / 2), after_sleep=2)
            return True
        return False

    def do_find_account_drop_down(self):
        texts = self.ocr()
        target = getattr(self, '_target_account_key', None)
        accounts = [box for box in texts if '*' in box.name or '@' in box.name
                    or (target and account_key_from_ocr(box.name) == target)]
        if len(accounts) == 1 and self.find_boxes(texts, LOGIN_TEXTS):
            return accounts[0]
        return None

    def _detect_current_account_from_login(self):
        if not getattr(self, '_ocr_account_selection', False):
            if combo := self._login_combo():
                return combo_selected_item(combo)
        box = self.do_find_account_drop_down()
        return box.name if box else None

    def _select_target_account(self, account_key):
        self._target_account_key = account_key
        self.sleep(1)
        try:
            if combo := self._login_combo():
                matches = [index for index, text in enumerate(combo_items(combo))
                           if account_key_from_ocr(text) == account_key]
                if not matches:
                    raise WaitFailedException(f'账号列表中未找到 {display_account(account_key)}')
                # Consistent with OCR: prefer the lower entry for duplicate labels.
                if not select_combo_item(combo, matches[-1]):
                    raise WaitFailedException('ComboBox 账号选择未生效。')
                self.sleep(1)
                if account_key_from_ocr(combo_selected_item(combo)) != account_key:
                    raise WaitFailedException('ComboBox 当前账号与目标不一致。')
                return
        except TaskDisabledException:
            raise
        except Exception as error:
            self.log_warning(f'ComboBox 切号失败，回退 OCR：{type(error).__name__}')
        previous_ocr_mode = getattr(self, '_ocr_account_selection', False)
        try:
            self._ocr_account_selection = True
            for attempt in range(5):
                self.sleep(1)
                self.click(self.find_account_drop_down(), after_sleep=2)
                if self.do_find_account_drop_down():
                    continue
                if not self.wait_until(lambda: self._find_target_account(account_key),
                                       time_out=10, raise_if_not_found=False):
                    raise WaitFailedException(f'账号列表中未找到 {display_account(account_key)}')
                self.sleep(1)
                current = self._detect_current_account_from_login()
                if account_key_from_ocr(current) == account_key:
                    break
                self.log_info(f'账号确认不匹配，重试 {attempt + 1}/5')
            else:
                raise WaitFailedException(f'无法确认目标账号 {display_account(account_key)}，停止登录。')
        finally:
            self._ocr_account_selection = previous_ocr_mode


    def _login_target_account(self, account_key):
        mouse_reset = self.executor.get_task_by_class(MouseResetTask)
        was_enabled = mouse_reset.enabled if mouse_reset else False
        try:
            if was_enabled:
                mouse_reset.disable()
            MultiAccountConfigTask._select_target_account(self, account_key)
            previous_cursor_mode = getattr(self, '_login_cursor_active', False)
            try:
                self._login_cursor_active = True
                self.sleep(4)
                login = self.find_boxes(self.ocr(), boundary=self.box_of_screen(0.3, 0.3, 0.7, 0.8),
                                        match=LOGIN_TEXTS)
                if login:
                    self.click(login, after_sleep=3)
                else:
                    self.click_relative(0.5, 0.568, hcenter=True, vcenter=True, after_sleep=3)
                self.logged_in = False
                self.ensure_main(time_out=180)
                self.log_info(f'{display_account(account_key)} 登录成功')
            finally:
                self._login_cursor_active = previous_cursor_mode
        finally:
            if was_enabled:
                mouse_reset.enable()
