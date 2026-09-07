import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.task.MouseResetTask import MouseResetTask
from src.task.WWOneTimeTask import WWOneTimeTask


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
        cursor_service = MagicMock()
        cursor_service.available = True
        cursor_service.get_position.return_value = (100, 100)
        task.executor.device_manager.cursor_service = cursor_service
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

        callback()

        self.assertEqual(len(task.handler.posts), 1)
        self.assertEqual(task.handler.posts[0][1], 0.002)

    def test_unavailable_cursor_service_does_not_start_loop(self):
        task = self.make_task()
        task.executor.device_manager.cursor_service.available = False

        self.assertFalse(task.run())
        self.assertEqual(len(task.handler.posts), 0)

    def test_browser_mode_does_not_start_loop(self):
        task = self.make_task()
        task.executor.device_manager.get_preferred_device.return_value = {'device': 'browser'}

        task.run()

        self.assertEqual(len(task.handler.posts), 0)

    def test_one_time_task_skips_incompatible_mouse_reset(self):
        mouse_reset = MagicMock()
        mouse_reset.is_device_compatible.return_value = False
        interaction = SimpleNamespace(activate=MagicMock())
        owner = SimpleNamespace(
            executor=SimpleNamespace(
                get_task_by_class=MagicMock(return_value=mouse_reset),
                interaction=interaction,
            ),
            sleep=MagicMock(),
        )

        WWOneTimeTask.run(owner)

        mouse_reset.run.assert_not_called()
        interaction.activate.assert_called_once_with()
        owner.sleep.assert_called_once_with(0.5)

    def test_one_time_task_preserves_compatible_mouse_reset_behavior(self):
        mouse_reset = MagicMock()
        mouse_reset.is_device_compatible.return_value = True
        owner = SimpleNamespace(
            executor=SimpleNamespace(
                get_task_by_class=MagicMock(return_value=mouse_reset),
                interaction=SimpleNamespace(),
            ),
            sleep=MagicMock(),
        )

        WWOneTimeTask.run(owner)

        mouse_reset.run.assert_called_once_with()
        owner.sleep.assert_called_once_with(0.5)


if __name__ == '__main__':
    unittest.main()
