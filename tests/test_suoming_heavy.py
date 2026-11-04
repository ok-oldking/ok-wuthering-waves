import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from ok import TaskDisabledException
from src.char.Suoming import Suoming
from src.task.BaseCombatTask import NotInCombatException


class TestSuomingResonanceHold(unittest.TestCase):
    def setUp(self):
        self.elapsed = 0
        self.task = SimpleNamespace(
            char_config={}, skip_combat_check=False,
            send_key_down=Mock(), send_key_up=Mock(), check_combat=Mock(),
            get_resonance_key=Mock(return_value='e'),
        )
        self.task.sleep = Mock(side_effect=self.animation_sleep)
        self.task.wait_until = Mock(side_effect=self.animation_wait)
        self.char = Suoming(self.task, 0)
        self.char.forte_available = Mock(side_effect=[True, True, False])
        self.char.resonance_available = Mock(return_value=True)
        self.char.time_elapsed_accounting_for_freeze = lambda start: self.elapsed
        self.char.click_echo = Mock()

    def animation_sleep(self, duration):
        self.assertFalse(self.task.skip_combat_check)
        self.elapsed += duration

    def animation_wait(self, condition, **kwargs):
        self.assertFalse(self.task.skip_combat_check)
        kwargs['pre_action']()
        return condition()

    def test_repeated_holds_release_key_between_attempts_and_before_echo(self):
        actions = Mock()
        actions.attach_mock(self.task.send_key_down, 'down')
        actions.attach_mock(self.task.send_key_up, 'up')
        actions.attach_mock(self.char.click_echo, 'echo')

        self.char.hold_forte_resonance()

        self.assertEqual([call[0] for call in actions.mock_calls], ['down', 'up', 'down', 'up', 'echo'])
        self.task.send_key_down.assert_called_with('e')
        self.task.send_key_up.assert_called_with('e')
        self.char.resonance_available.assert_called_once_with()
        self.assertEqual(self.task.check_combat.call_count, 2)

    def test_persistent_prompt_stops_at_hold_timeout(self):
        self.char.forte_available.side_effect = None
        self.char.forte_available.return_value = True

        self.char.hold_forte_resonance()

        self.assertEqual(self.task.send_key_down.call_count, 3)
        self.assertEqual(self.task.send_key_up.call_count, 3)
        self.assertLess(self.elapsed, 10)

    def test_ready_wait_timeout_still_releases_key(self):
        self.task.wait_until.side_effect = None
        self.task.wait_until.return_value = None

        self.char.hold_forte_resonance()

        self.task.wait_until.assert_called_once_with(
            self.char.resonance_available, time_out=8, pre_action=self.char.check_combat)
        self.task.send_key_up.assert_called_with('e')

    def test_combat_end_cancellation_and_errors_release_key_and_propagate(self):
        for error in (NotInCombatException('combat ended'), TaskDisabledException(), RuntimeError('capture failed')):
            with self.subTest(error=type(error).__name__):
                self.setUp()
                self.task.wait_until.side_effect = error

                with self.assertRaises(type(error)) as raised:
                    self.char.hold_forte_resonance()

                self.assertIs(raised.exception, error)
                self.task.send_key_up.assert_called_with('e')
                self.char.click_echo.assert_not_called()
                self.assertFalse(self.task.skip_combat_check)

    def test_combat_end_during_hold_releases_key_immediately(self):
        self.task.sleep.side_effect = NotInCombatException('combat ended during hold')

        with self.assertRaises(NotInCombatException):
            self.char.hold_forte_resonance()

        self.task.send_key_down.assert_called_once_with('e')
        self.task.send_key_up.assert_called_once_with('e')
        self.task.wait_until.assert_not_called()

    def test_combat_end_detected_while_polling_releases_key(self):
        self.task.check_combat.side_effect = [None, NotInCombatException('combat ended while polling')]

        with self.assertRaises(NotInCombatException):
            self.char.hold_forte_resonance()

        self.task.send_key_up.assert_called_with('e')
        self.char.click_echo.assert_not_called()


if __name__ == '__main__':
    unittest.main()
