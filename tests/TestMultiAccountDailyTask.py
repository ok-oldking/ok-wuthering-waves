import unittest

from ok.task.exceptions import WaitFailedException
from src.task.BaseWWTask import LOGIN_TEXTS
from src.task.MultiAccountDailyTask import (
    MultiAccountDailyTask,
    account_pattern,
    normalize_account_name,
)


class TestMultiAccountDailyTask(unittest.TestCase):

    def test_account_dropdown_accepts_multiple_login_text_matches(self):
        account_box = object()

        class FakeTask:
            def ocr(self):
                return []

            def find_boxes(self, texts, match):
                if match == account_pattern:
                    return [account_box]
                if match == LOGIN_TEXTS:
                    return [object(), object()]
                return []

        self.assertIs(MultiAccountDailyTask.do_find_account_drop_down(FakeTask()), account_box)

    def test_account_name_normalization_groups_common_ocr_variants(self):
        self.assertEqual(
            normalize_account_name("cc****33@demo.com.hk"),
            normalize_account_name("cc****33@dem0.com.hk"),
        )
        self.assertEqual(
            normalize_account_name("bb****02@example.com"),
            normalize_account_name("bb****02@example.con"),
        )

    def test_click_account_list_selects_visible_third_account_after_first_two_are_done(self):
        class AccountBox:
            def __init__(self, name):
                self.name = name

        class FakeTask:
            def __init__(self):
                self.done_set = {
                    normalize_account_name("aa****01@example.com"),
                    normalize_account_name("bb****02@example.com"),
                }
                self.all_accounts = set()
                self.clicked = []

            _is_done = MultiAccountDailyTask._is_done

            def ocr(self, match=None):
                return [
                    AccountBox("aa****01@example.com"),
                    AccountBox("aa****01@example.com"),
                    AccountBox("bb****02@example.com"),
                    AccountBox("cc****03@example.com.hk"),
                ]

            def info_set(self, *args):
                pass

            def click(self, account, after_sleep=0):
                self.clicked.append(account.name)

            def log_info(self, *args):
                pass

            def tr(self, message):
                return message

        task = FakeTask()

        selected = MultiAccountDailyTask._click_account_in_list(task)

        self.assertEqual(selected, "cc****03@example.com.hk")
        self.assertEqual(task.clicked, ["cc****03@example.com.hk"])


if __name__ == "__main__":
    unittest.main()


    def test_selection_ends_the_sweep_once_every_detected_account_is_done(self):
        class AccountBox:
            def __init__(self, name):
                self.name = name

        class FakeExecutor:
            def get_task_by_class(self, task_class):
                return None

        class FakeTask:
            executor = FakeExecutor()

            def __init__(self):
                self.done_set = {normalize_account_name("aa****01@example.com")}
                self.all_accounts = set()
                self.clicked = []
                self.logs = []

            _is_done = MultiAccountDailyTask._is_done
            _click_account_in_list = MultiAccountDailyTask._click_account_in_list

            def ocr(self, match=None):
                return [AccountBox("aa****01@example.com")]

            def info_set(self, *args):
                pass

            def click(self, account, after_sleep=0):
                self.clicked.append(account.name)

            def log_info(self, *args):
                self.logs.append(args)

            def tr(self, message):
                return message

            def sleep(self, *args):
                pass

            def find_account_drop_down(self):
                return object()

            def do_find_account_drop_down(self):
                return None

            def wait_until(self, condition, time_out=0, raise_if_not_found=False, **_kwargs):
                value = condition()
                if not value and raise_if_not_found:
                    raise WaitFailedException()
                return value

        task = FakeTask()

        self.assertIsNone(MultiAccountDailyTask._select_and_login_account(task))
        self.assertEqual(task.clicked, [])

    def test_selection_still_fails_when_no_account_is_readable(self):
        class FakeExecutor:
            def get_task_by_class(self, task_class):
                return None

        class FakeTask:
            executor = FakeExecutor()

            def __init__(self):
                self.done_set = set()
                self.all_accounts = set()
                self.clicked = []

            _is_done = MultiAccountDailyTask._is_done
            _click_account_in_list = MultiAccountDailyTask._click_account_in_list

            def ocr(self, match=None):
                return []

            def info_set(self, *args):
                pass

            def click(self, account, after_sleep=0):
                self.clicked.append(account.name)

            def log_info(self, *args):
                pass

            def tr(self, message):
                return message

            def sleep(self, *args):
                pass

            def find_account_drop_down(self):
                return object()

            def do_find_account_drop_down(self):
                return None

            def wait_until(self, condition, time_out=0, raise_if_not_found=False, **_kwargs):
                value = condition()
                if not value and raise_if_not_found:
                    raise WaitFailedException()
                return value

        with self.assertRaises(WaitFailedException):
            MultiAccountDailyTask._select_and_login_account(FakeTask())
