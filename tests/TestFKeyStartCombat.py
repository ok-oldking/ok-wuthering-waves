import time
import unittest
from unittest.mock import Mock

from src.combat.CombatCheck import CombatCheck
from src.combat.FKeyWatcher import FKeyWatcher
from src.scene.WWScene import WWScene
from src.task.AutoCombatTask import AutoCombatTask, F_KEY_EXPIRE


class TestFKeyStartCombat(unittest.TestCase):
    def setUp(self):
        self.scene = WWScene()
        self.executor = Mock(scene=self.scene, debug=False)
        self.task = AutoCombatTask(self.executor, None)
        self.task.scene = self.scene
        self.task.config = dict(self.task.default_config)
        self.task.config['Start Combat with F Key'] = True
        self.task.f_key_watcher.start = Mock()
        self.task.load_chars = Mock(return_value=True)
        self.task.find_one = Mock(return_value=None)
        self.task.middle_click = Mock()
        self.task.has_target = Mock(return_value=False)
        self.task.check_health_bar = Mock(return_value=False)
        self.task.is_open_world_auto_combat = Mock(return_value=False)

    def press_f(self, seconds_ago=0.0):
        self.task.f_key_watcher.last_press = time.time() - seconds_ago

    def leave_combat(self):
        self.task._in_combat = False
        self.scene.reset()

    def test_disabled_by_default(self):
        self.task.config = dict(self.task.default_config)
        self.press_f()

        self.assertFalse(self.task.do_check_in_combat(False))
        self.assertFalse(self.task._in_combat)
        self.task.f_key_watcher.start.assert_not_called()

    def test_f_press_starts_combat_once(self):
        self.press_f(0.1)

        self.assertTrue(self.task.do_check_in_combat(False))
        self.assertTrue(self.task._in_combat)
        self.assertTrue(self.scene.in_combat())
        self.task.middle_click.assert_called_once()
        self.task.has_target.assert_not_called()

        self.leave_combat()
        self.assertFalse(self.task.do_check_in_combat(False))
        self.assertFalse(self.task._in_combat)

    def test_waits_for_delay(self):
        self.task.config['F Key Start Delay'] = 2.0
        self.press_f(0.5)

        self.assertFalse(self.task.do_check_in_combat(False))
        self.assertFalse(self.task._in_combat)

        self.task.f_key_watcher.last_press -= 2.0
        self.assertTrue(self.task.do_check_in_combat(False))
        self.assertTrue(self.task._in_combat)

    def test_stale_press_is_dropped(self):
        self.press_f(F_KEY_EXPIRE + 1)

        self.assertFalse(self.task.do_check_in_combat(False))
        self.assertFalse(self.task._in_combat)
        self.assertEqual(self.task.f_key_handled, self.task.f_key_watcher.last_press)

    def test_press_waits_until_team_is_loaded(self):
        self.press_f(0.1)
        self.task.load_chars.return_value = None

        self.assertFalse(self.task.do_check_in_combat(False))
        self.assertFalse(self.task._in_combat)

        self.task.load_chars.return_value = True
        self.assertTrue(self.task.do_check_in_combat(False))
        self.assertTrue(self.task._in_combat)

    def test_auto_target_off_does_not_middle_click(self):
        self.task.config['Auto Target'] = False
        self.press_f(0.1)

        self.assertTrue(self.task.do_check_in_combat(False))
        self.task.middle_click.assert_not_called()

    def test_presses_before_combat_end_are_dropped(self):
        self.task.warm_up_char_features = Mock()
        self.task.in_team_and_world = Mock(return_value=True)
        self.task.in_world = Mock(return_value=True)
        self.task.switch_healer = Mock()
        self.task.combat_end = Mock()
        self.task.get_current_char = Mock()
        self.task.in_combat = Mock(side_effect=[True, False])
        self.press_f(0.1)

        self.assertTrue(self.task.run())
        self.assertFalse(self.task.should_start_combat_by_key())

    def test_open_world_press_is_dropped(self):
        self.task.is_open_world_auto_combat.return_value = True
        self.press_f(0.1)

        self.assertFalse(self.task.do_check_in_combat(False))
        self.assertFalse(self.task._in_combat)
        self.task.middle_click.assert_not_called()

        self.task.is_open_world_auto_combat.return_value = False
        self.assertFalse(self.task.do_check_in_combat(False))
        self.assertFalse(self.task._in_combat)

    def test_invalid_delay_falls_back_to_zero(self):
        self.task.config['F Key Start Delay'] = 'abc'
        self.press_f(0.1)

        self.assertTrue(self.task.do_check_in_combat(False))

    def test_toggle_drops_pending_press(self):
        self.task.run_auto_combat = Mock(return_value=False)
        self.press_f(0.1)
        self.task._enabled = True
        self.task.disable()

        self.task.run()

        self.task.f_key_watcher.start.assert_called_once()
        self.assertFalse(self.task.should_start_combat_by_key())

    def test_press_while_disabled_is_dropped(self):
        self.task.run_auto_combat = Mock(return_value=False)
        self.task.config['Start Combat with F Key'] = False
        self.press_f(0.1)
        self.task.run()

        self.task.config['Start Combat with F Key'] = True
        self.assertFalse(self.task.should_start_combat_by_key())

    def test_other_combat_tasks_ignore_f(self):
        self.assertFalse(CombatCheck.should_start_combat_by_key(Mock()))


class TestFKeyWatcher(unittest.TestCase):
    def test_records_rising_edge_only_in_foreground(self):
        foreground = Mock(return_value=True)
        watcher = FKeyWatcher(foreground)

        watcher.on_sample(True)
        first = watcher.last_press
        self.assertGreater(first, 0)

        watcher.on_sample(True)
        self.assertEqual(watcher.last_press, first)

        watcher.on_sample(False)
        foreground.return_value = False
        watcher.on_sample(True)
        self.assertEqual(watcher.last_press, first)

    def test_foreground_check_errors_are_ignored(self):
        watcher = FKeyWatcher(Mock(side_effect=RuntimeError))

        watcher.on_sample(True)
        self.assertEqual(watcher.last_press, 0.0)


if __name__ == '__main__':
    unittest.main()
