import unittest
from unittest.mock import MagicMock, patch

from ok import TriggerTask

from src.task.MouseResetTask import MouseResetTask


def parent_disable(self):
    self._enabled = False


def parent_enable(self):
    self._enabled = True


class FakeHandler:
    """Records handler.post calls instead of scheduling them on a thread."""

    def __init__(self):
        self.posts = []

    def post(self, task, delay=0, remove_existing=False, skip_if_running=False):
        self.posts.append((task, delay))
        return True

    def pop(self):
        return self.posts.pop(0)[0]


class TestMouseResetTask(unittest.TestCase):

    def make_task(self):
        task = MouseResetTask(MagicMock(), None)
        task._handler = FakeHandler()
        task._enabled = True
        return task

    def test_run_starts_loop_once(self):
        task = self.make_task()
        task.run()
        self.assertTrue(task.running_reset)
        self.assertEqual(len(task.handler.posts), 1)
        task.run()
        self.assertEqual(len(task.handler.posts), 1)

    def test_run_while_disabled_does_nothing(self):
        task = self.make_task()
        task._enabled = False
        task.run()
        self.assertFalse(task.running_reset)
        self.assertEqual(len(task.handler.posts), 0)

    def test_disable_then_enable_restarts_loop(self):
        task = self.make_task()
        task.run()
        first_callback = task.handler.pop()

        with patch.object(TriggerTask, 'disable', parent_disable):
            task.disable()
        self.assertFalse(task.running_reset)
        self.assertIsNone(task.mouse_pos)

        # a callback queued before the disable must not revive the loop
        first_callback()
        self.assertEqual(len(task.handler.posts), 0)

        with patch.object(TriggerTask, 'enable', parent_enable):
            task.enable()
        self.assertTrue(task.running_reset)
        self.assertEqual(len(task.handler.posts), 1)
        second_callback = task.handler.pop()

        # the restarted loop keeps rescheduling itself
        with patch('src.task.MouseResetTask.win32api') as win32api:
            win32api.GetCursorPos.return_value = (100, 100)
            second_callback()
        self.assertEqual(len(task.handler.posts), 1)

        # the callback from the stopped loop is still dead
        first_callback()
        self.assertEqual(len(task.handler.posts), 1)

    def test_disable_without_loop_is_safe(self):
        task = self.make_task()
        with patch.object(TriggerTask, 'disable', parent_disable):
            task.disable()
        self.assertFalse(task.running_reset)
        self.assertEqual(len(task.handler.posts), 0)

    def test_exception_keeps_loop_alive(self):
        task = self.make_task()
        task.run()
        callback = task.handler.pop()
        with patch('src.task.MouseResetTask.win32api') as win32api:
            win32api.GetCursorPos.side_effect = OSError('boom')
            callback()
        self.assertTrue(task.running_reset)
        self.assertEqual(len(task.handler.posts), 1)
        self.assertEqual(task.handler.posts[0][1], 1)

    def test_browser_mode_reposts_slowly(self):
        task = self.make_task()
        task.run()
        callback = task.handler.pop()
        task.executor.device_manager.get_preferred_device.return_value = {'device': 'browser'}
        with patch('src.task.MouseResetTask.win32api') as win32api:
            callback()
            win32api.GetCursorPos.assert_not_called()
        self.assertEqual(len(task.handler.posts), 1)
        self.assertEqual(task.handler.posts[0][1], 1)


if __name__ == '__main__':
    unittest.main()
