from copy import deepcopy
from unittest.mock import patch

from config import config
from ok.test.TaskTestCase import TaskTestCase
from src.task.FarmEchoTask import FarmEchoTask


class TestCloudDisconnect(TaskTestCase):
    task_class = FarmEchoTask
    config = deepcopy(config)

    def test_detects_idle_disconnect_dialog(self):
        with patch.object(self.task, 'is_browser', return_value=True):
            self.set_image('tests/images/cloud_disconnect_1020.png')
            exit_game = self.task.find_cloud_disconnect()
            self.assertTrue(exit_game)
            self.assertIn('退出游戏', exit_game[0].name)

    def test_ignores_launcher_home(self):
        with patch.object(self.task, 'is_browser', return_value=True):
            self.set_image('tests/images/cloud_launcher_home.png')
            self.assertIsNone(self.task.find_cloud_disconnect())

    def test_skipped_outside_cloud(self):
        with patch.object(self.task, 'is_browser', return_value=False):
            self.set_image('tests/images/cloud_disconnect_1020.png')
            self.assertIsNone(self.task.find_cloud_disconnect())

    def test_detects_idle_disconnect_dialog_with_confirm_button(self):
        with patch.object(self.task, 'is_browser', return_value=True):
            self.set_image('tests/images/cloud_disconnect_4012.png')
            confirm = self.task.find_cloud_disconnect()
            self.assertTrue(confirm)
            self.assertEqual('确定', confirm[0].name)
