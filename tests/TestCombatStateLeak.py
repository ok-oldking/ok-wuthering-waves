import threading
import unittest
from unittest.mock import MagicMock, patch

from ok import TaskDisabledException
from src.scene.WWScene import WWScene
from src.task.AutoCombatTask import AutoCombatTask
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

    def test_reset_combat_state_clears_all_fields(self):
        task = DummyCombatTask(self.executor, self.app)
        task._in_combat = True
        task.chars = ["Char1", "Char2", "Char3"]
        task.freeze_durations = [(100.0, 0.5, 0.1)]

        task.reset_combat_state("test")

        self.assertFalse(task._in_combat)
        self.assertEqual(task.chars, [None, None, None])
        self.assertEqual(task.freeze_durations, [])
        self.scene.set_not_in_combat.assert_called()

    def test_disable_does_not_mutate_chars_on_calling_thread(self):
        """Calling disable() on UI thread must only mark task disabled, leaving chars intact for in-flight executor."""
        task = DummyCombatTask(self.executor, self.app)
        task.chars = ["Char1", "Char2", "Char3"]
        task.disable()

        self.assertFalse(task.enabled)
        self.assertEqual(task.chars, ["Char1", "Char2", "Char3"])

    def test_concurrent_disable_during_active_rotation(self):
        """Disabling AutoCombatTask mid-rotation must raise TaskDisabledException, never AttributeError, and clean up on unwind."""
        scene = WWScene()
        executor = MagicMock(scene=scene, debug=False)
        task = AutoCombatTask(executor, None)
        task.scene = scene
        task.config = {'Switch to Healer before and after Combat': True}
        task.warm_up_char_features = MagicMock()
        task.in_team_and_world = MagicMock(return_value=True)
        task.in_world = MagicMock(return_value=True)
        task.check_scene = MagicMock()
        task.check_combat = MagicMock(return_value=True)

        mock_char = MagicMock()
        mock_char.is_current_char = True
        def mock_perform():
            if not task.enabled:
                raise TaskDisabledException()
        mock_char.perform.side_effect = mock_perform
        task.chars = [mock_char, None, None]
        task.active_char = 0
        task._in_combat = True
        scene.set_in_combat()

        pause_event = threading.Event()
        resume_event = threading.Event()

        def custom_switch_healer():
            pause_event.set()
            resume_event.wait(timeout=2.0)

        task.switch_healer = custom_switch_healer

        def worker():
            try:
                task.run()
            except Exception as e:
                task._worker_exception = e

        task._worker_exception = None
        t = threading.Thread(target=worker)
        t.start()

        self.assertTrue(pause_event.wait(timeout=2.0))
        # UI thread invokes disable() while worker is paused in switch_healer
        task.disable()
        resume_event.set()
        t.join(timeout=2.0)

        # Worker must raise TaskDisabledException, NEVER AttributeError
        self.assertIsInstance(task._worker_exception, TaskDisabledException)
        # On unwind, reset_auto_combat resets chars to None
        self.assertEqual(task.chars, [None, None, None])
        self.assertFalse(task._reset_combat_on_run)

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
        self.assertFalse(task.enabled)

        # Catching TaskDisabledException during execution resets combat state
        try:
            raise TaskDisabledException()
        except TaskDisabledException:
            task.reset_combat_state('farm echo task disabled')
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
