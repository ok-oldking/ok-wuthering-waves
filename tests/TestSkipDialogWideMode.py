import unittest
from unittest.mock import Mock

from config import config
from ok.test.TaskTestCase import TaskTestCase
from src.task.SkipDialogTask import AutoDialogTask

config['debug'] = True


class TestSkipDialogWideMode(TaskTestCase):
    task_class = AutoDialogTask
    config = config

    def test_finds_and_clicks_wide_mode_confirm_dialog(self):
        self.set_image('ok_templates/19.png')
        self.task.click = Mock()
        self.task.sleep = Mock()

        clicked = self.task.click_skip_dialog_confirm()

        self.assertTrue(clicked)
        self.assertEqual(2, self.task.click.call_count)


if __name__ == '__main__':
    unittest.main()
