import re

from qfluentwidgets import FluentIcon

from ok import Logger
from src.task.DailyTask import DailyTask
from src.task.WWOneTimeTask import WWOneTimeTask
from src.task.BaseCombatTask import BaseCombatTask

logger = Logger.get_logger(__name__)


class MultiAccountDailyTask(WWOneTimeTask, BaseCombatTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "多账号一条龙"
        self.group_name = "Daily"
        self.group_icon = FluentIcon.CALENDAR
        self.icon = FluentIcon.PEOPLE
        self.supported_languages = ["zh_CN"]
        self.description = "多账号自动切换，依次执行每日一条龙任务"
        self.default_config = {
            '账号列表': '',
        }
        self.config_description = {
            '账号列表': '每行填写一个手机尾号（后4位），自动识别当前登录账号',
        }
        self.config_type = {
            '账号列表': {'type': 'text_edit'},
        }
        self.add_exit_after_config()

    def run(self):
        WWOneTimeTask.run(self)
        accounts = self._parse_account_list()

        self.run_task_by_class(DailyTask)

        if not accounts:
            return

        done_set = set()

        detected = self._switch_to_login_and_detect()
        if detected:
            done_set.add(detected)

        for i, suffix in enumerate(accounts):
            if suffix in done_set:
                self.log_info(f'跳过 ****{suffix}（已完成）')
                continue
            self._select_and_login_account(suffix)
            self.run_task_by_class(DailyTask)
            done_set.add(suffix)
            remaining = [a for a in accounts[i + 1:] if a not in done_set]
            if remaining:
                self._switch_to_login()

    def _parse_account_list(self):
        raw = self.config.get('账号列表', '')
        if not raw or not raw.strip():
            return []
        result = []
        for idx, line in enumerate(raw.splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            if not line.isdigit():
                self.log_error(f'账号列表第{idx}行格式错误（必须为纯数字）："{line}"')
                continue
            if len(line) != 4:
                self.log_error(f'账号列表第{idx}行格式错误（应为4位尾号）："{line}"')
                continue
            result.append(line)
        if not result:
            self.log_error('账号列表中没有有效账号，请每行填写一个4位手机尾号')
        return result

    def _make_masked_pattern(self, suffix):
        return re.compile(rf'\d+\*+{re.escape(suffix)}')

    def _click_center_offset(self, offset_x, offset_y, after_sleep=0.5):
        h, w = self.frame.shape[:2]
        rel_x = 0.5 + offset_x / w
        rel_y = 0.5 + offset_y / h
        self.click_relative(rel_x, rel_y, after_sleep=after_sleep)

    def _switch_to_login(self):
        self.log_info('正在返回登录界面')
        self.send_key('esc', after_sleep=1.5)
        self.wait_until(
            lambda: bool(self.find_boxes(self.ocr(), match='终端')),
            time_out=30, raise_if_not_found=False
        )
        self.click_relative(0.04, 0.96, after_sleep=1)
        self.wait_until(
            lambda: bool(self.find_boxes(self.ocr(), match='返回登录')),
            time_out=30, raise_if_not_found=False
        )
        texts = self.ocr()
        if btn := self.find_boxes(texts, match='返回登录'):
            self.click(btn, after_sleep=3)
        else:
            self.click_relative(0.67, 0.63, after_sleep=3)
        self.wait_until(
            lambda: bool(self.find_boxes(
                self.ocr(),
                boundary=self.box_of_screen(0.3, 0.3, 0.7, 0.8),
                match='其他登录方式')),
            time_out=60, raise_if_not_found=False
        )
        self.log_info('已返回登录界面')

    def _switch_to_login_and_detect(self):
        self._switch_to_login()
        suffix = self._detect_current_account_from_login()
        if suffix:
            self.log_info(f'检测到已完成账号：****{suffix}')
        else:
            self.log_info('无法识别当前登录账号')
        return suffix

    def _detect_current_account_from_login(self):
        texts = self.ocr()
        pattern = re.compile(r'\d{3}\*+(\d{4})')
        for box in texts:
            m = pattern.search(box.name)
            if m:
                return m.group(1)
        return None

    def _click_account_in_list(self, pattern):
        texts = self.ocr()
        if boxes := self.find_boxes(texts, boundary=self.box_of_screen(0.3, 0.3, 0.65, 0.9), match=pattern):
            self.click(boxes[0], after_sleep=0.5)
            return True
        return False

    def _select_and_login_account(self, suffix):
        pattern = self._make_masked_pattern(suffix)
        self.log_info(f'正在选择账号：****{suffix}')
        self._click_center_offset(270, -43, after_sleep=1)
        self.wait_until(
            lambda: self._click_account_in_list(pattern),
            time_out=10, raise_if_not_found=True
        )
        texts = self.ocr()
        login_btn = self.find_boxes(texts, boundary=self.box_of_screen(0.3, 0.3, 0.7, 0.8), match="登录")
        if login_btn:
            self.click(login_btn, after_sleep=3)
        else:
            self._click_center_offset(0, 95, after_sleep=3)
        self._logged_in = False
        self.ensure_main(time_out=180)
        self.log_info(f'登录成功：****{suffix}')

