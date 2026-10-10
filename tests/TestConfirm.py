import unittest
from config import config
from ok.test.TaskTestCase import TaskTestCase
from src.task.FiveToOneTask import FiveToOneTask

config['debug'] = True


class TestConfirm(TaskTestCase):
    task_class = FiveToOneTask
    config = config

    def test_confirm(self):
        self.task.do_reset_to_false()
        self.set_image('tests/images/confirm_highlight.png')
        confirm_btn_hcenter_vcenter = self.task.find_one('confirm_btn_hcenter_vcenter')
        self.task.log_debug(f'confirm_btn_hcenter_vcenter {confirm_btn_hcenter_vcenter}')
        self.assertIsNotNone(confirm_btn_hcenter_vcenter)


if __name__ == '__main__':
    unittest.main()
