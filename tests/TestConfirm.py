import unittest
from config import config
from ok.test.TaskTestCase import TaskTestCase
from src.task.FiveToOneTask import FiveToOneTask


class TestConfirm(TaskTestCase):
    task_class = FiveToOneTask
    # Template matching does not need the background OCR model initialization.
    config = {**config, 'debug': True, 'ocr': None}

    def test_confirm(self):
        self.task.do_reset_to_false()
        self.set_image('tests/images/confirm_highlight.png')
        confirm_btn_hcenter_vcenter = self.task.find_one('confirm_btn_hcenter_vcenter')
        self.task.log_debug(f'confirm_btn_hcenter_vcenter {confirm_btn_hcenter_vcenter}')
        self.assertIsNotNone(confirm_btn_hcenter_vcenter)


if __name__ == '__main__':
    unittest.main()
