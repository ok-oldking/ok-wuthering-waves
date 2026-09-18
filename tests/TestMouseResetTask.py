import unittest
from unittest.mock import MagicMock, patch

from src.task.MouseResetTask import MouseResetTask


class FakeHandler:

    def __init__(self):
        self.posts = []

    def post(self, task, delay=0, remove_existing=False, skip_if_running=False):
        if remove_existing:
            self.posts = [post for post in self.posts if post[0] != task]
        self.posts.append((task, delay))
        return True

    def pop(self):
        return self.posts.pop(0)[0]


class TestMouseResetTask(unittest.TestCase):

    def make_task(self):
        task = MouseResetTask(MagicMock(), None)
        task._handler = FakeHandler()
        task._enabled = True
        task.config = {}
        return task

    def test_run_keeps_only_one_callback(self):
        task = self.make_task()

        task.run()
        task.run()

        self.assertEqual(len(task.handler.posts), 1)

    def test_disabled_callback_stops_and_run_restarts_after_enable(self):
        task = self.make_task()
        task.run()
        callback = task.handler.pop()

        task.disable()
        callback()
        self.assertEqual(len(task.handler.posts), 0)

        task.enable()
        self.assertEqual(len(task.handler.posts), 1)

    def test_callback_continues_while_enabled(self):
        task = self.make_task()
        task.run()
        callback = task.handler.pop()

        with patch('src.task.MouseResetTask.win32api') as win32api:
            win32api.GetCursorPos.return_value = (100, 100)
            callback()

        self.assertEqual(len(task.handler.posts), 1)
        self.assertEqual(task.handler.posts[0][1], 0.002)

    def test_browser_mode_does_not_start_loop(self):
        task = self.make_task()
        task.executor.device_manager.get_preferred_device.return_value = {'device': 'browser'}

        task.run()

        self.assertEqual(len(task.handler.posts), 0)


if __name__ == '__main__':
    unittest.main()
