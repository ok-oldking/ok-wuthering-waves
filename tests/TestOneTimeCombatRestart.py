import unittest
from unittest.mock import Mock

from ok import TaskDisabledException
from src.char.BaseChar import BaseChar
from src.scene.WWScene import WWScene
from src.task.FarmEchoTask import FarmEchoTask
from src.task.GardenTask import GardenTask
from src.task.WWOneTimeTask import WWOneTimeTask


class TestOneTimeCombatRestart(unittest.TestCase):
    def setUp(self):
        self.scene = WWScene()
        self.executor = Mock(scene=self.scene, debug=False, interaction=None)
        self.task = FarmEchoTask(self.executor, None)
        self.task.scene = self.scene
        self.task.config = dict(self.task.default_config)
        self.task._enabled = True
        self.task.next_frame = Mock()
        self.task.in_combat = Mock(return_value=False)
        self.task.wait_feature = Mock(return_value=None)
        # Exercise the startup sleep's real combat check without capture or input.
        self.task.sleep = Mock(side_effect=lambda seconds: self.task.sleep_check())

    def stop_during_combat(self, skip_combat_check=False):
        char = BaseChar(self.task, 0, char_name='previous_team')
        char.is_current_char = True

        def interrupt_rotation():
            self.task.chars = [char, None, None]
            self.task._in_combat = True
            self.task.skip_combat_check = skip_combat_check
            self.task.in_liberation = True
            self.task.cds = {'resonance': 12}
            self.task.freeze_durations = [(1, 2, 0.1)]
            self.scene.set_in_combat()
            self.task.disable()
            raise TaskDisabledException()

        self.task.do_run = Mock(side_effect=interrupt_rotation)
        self.task.run()
        self.assertFalse(self.task.enabled)
        self.assertIs(self.task.chars[0], char)

    def test_restart_after_stop_reaches_farming_outside_combat(self):
        self.stop_during_combat()
        self.task._enabled = True
        self.task.do_run = Mock(return_value=True)

        # Before the fix, stale _in_combat raises NotInCombatException in startup.
        self.assertTrue(self.task.run())

        self.task.do_run.assert_called_once()

    def test_restart_drops_previous_rotation_before_startup_sleep(self):
        self.stop_during_combat(skip_combat_check=True)
        self.task._enabled = True

        def check_startup_state(seconds):
            self.assertFalse(self.task._in_combat)
            self.assertFalse(self.task.in_liberation)
            self.assertFalse(self.task.skip_combat_check)
            self.assertIsNone(self.task.get_current_char())
            self.assertEqual(self.task.cds, {})
            self.assertEqual(self.task.freeze_durations, [])
            self.assertFalse(self.scene.in_combat())
            self.task.sleep_check()

        self.task.sleep.side_effect = check_startup_state
        self.task.do_run = Mock(return_value=True)

        self.assertTrue(self.task.run())

        self.task.sleep.assert_called_with(0.5)
        self.task.do_run.assert_called_once()

    def test_noncombat_task_keeps_normal_startup(self):
        task = GardenTask(self.executor, None)
        task.sleep = Mock()

        WWOneTimeTask.run(task)

        task.sleep.assert_called_once_with(0.5)


if __name__ == '__main__':
    unittest.main()
