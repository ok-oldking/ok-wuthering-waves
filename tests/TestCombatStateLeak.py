import unittest
from unittest.mock import MagicMock, patch

from src.task.BaseCombatTask import BaseCombatTask
from src.task.FarmEchoTask import FarmEchoTask
from src.task.WWOneTimeTask import WWOneTimeTask


class DummyCombatTask(WWOneTimeTask, BaseCombatTask):
    def __init__(self, executor=None, app=None):
        executor = executor or MagicMock()
        app = app or MagicMock()
        super().__init__(executor, app)
        self.name = "DummyCombatTask"
        self._enabled = True
        self.running = False
        self._paused = False
        self.instructions = None
        self.first_run_alert = None
        self.show_create_shortcut = False
        self.sleep_check_interval = -1
        self.config = {}
        self.default_config = {}
        self.config_description = {}
        self.config_type = {}
        self.icon = None
        self.scene = executor.scene

    def run(self):
        WWOneTimeTask.run(self)


class TestCombatStateLeak(unittest.TestCase):
    def setUp(self):
        self.executor = MagicMock()
        self.app = MagicMock()
        self.scene = MagicMock()
        self.executor.scene = self.scene

    def test_disable_clears_in_combat_state(self):
        task = DummyCombatTask(self.executor, self.app)
        task._in_combat = True
        task.chars = ["Char1", "Char2", "Char3"]
        task.freeze_durations = [(100.0, 0.5, 0.1)]

        task.disable()

        self.assertFalse(task._in_combat)
        self.assertEqual(task.chars, [None, None, None])
        self.assertEqual(task.freeze_durations, [])
        self.scene.set_not_in_combat.assert_called()

    def test_wwonetime_task_run_resets_combat_before_sleep(self):
        task = DummyCombatTask(self.executor, self.app)
        task._in_combat = True

        mock_mouse_task = MagicMock()
        self.executor.get_task_by_class.return_value = mock_mouse_task
        self.executor.interaction = None

        with patch.object(task, 'sleep') as mock_sleep:
            task.run()

            self.assertFalse(task._in_combat)
            mock_sleep.assert_called_once_with(0.5)

    def test_farm_echo_stop_then_restart_does_not_raise_not_in_combat(self):
        """Simulate user stopping FarmEchoTask mid-combat and restarting it."""
        task = FarmEchoTask.__new__(FarmEchoTask)
        task._executor = self.executor
        task._app = self.app
        task.name = "FarmEchoTask"
        task.info = {}
        task.config = {'Use Liberation': True}
        task.default_config = {}
        task.config_description = {}
        task.config_type = {}
        task._in_combat = True  # Simulating state left over before fix
        task.chars = [None, None, None]
        task.freeze_durations = []
        task.skip_combat_check = False
        task.in_sleep_check = False
        task.scene = self.scene

        mock_mouse_task = MagicMock()
        self.executor.get_task_by_class.return_value = mock_mouse_task
        self.executor.interaction = None

        # Simulate task.disable() when user hits Stop
        task.disable()
        self.assertFalse(task._in_combat)

        # Even if _in_combat was somehow True again, starting run() resets it before sleep
        task._in_combat = True
        with patch.object(task, 'sleep') as mock_sleep, patch.object(task, 'do_run') as mock_do_run:
            mock_do_run.return_value = True
            task.run()
            self.assertFalse(task._in_combat)
            mock_sleep.assert_called_once_with(0.5)


if __name__ == '__main__':
    unittest.main()
