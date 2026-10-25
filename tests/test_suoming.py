import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from src.Labels import Labels
from src.char.BaseChar import CharType, get_default_buff_time
from src.char.Suoming import Suoming


class TestSuoming(unittest.TestCase):
    def setUp(self):
        self.task = SimpleNamespace(char_config={}, mouse_down=Mock(), mouse_up=Mock())
        self.char = Suoming(self.task, 0, char_type=CharType.SUB_DPS, buff_time=8)
        self.char.click_echo = Mock()
        self.char.click_liberation = Mock(return_value=False)
        self.char.click_resonance = Mock(return_value=(False, 0, False))
        self.char.perform_forte = Mock()
        self.char.continues_normal_attack = Mock()
        self.char.continues_click_until = Mock(return_value=True)
        self.char.switch_next_char = Mock()

    def test_dps_config_changes_role_and_buff_time_dynamically(self):
        self.assertFalse(self.char.is_dps_config())
        self.assertEqual(self.char.char_type, CharType.SUB_DPS)
        self.assertEqual(self.char.buff_time, 8)

        self.task.char_config['Suoming DPS'] = True
        self.assertEqual(self.char.char_type, CharType.MAIN_DPS)
        self.assertEqual(self.char.buff_time, get_default_buff_time(CharType.MAIN_DPS))

        self.task.char_config['Suoming DPS'] = False
        self.assertEqual(self.char.char_type, CharType.SUB_DPS)
        self.assertEqual(self.char.buff_time, 8)

    def test_dps_casts_resonance_after_liberation_and_continues_attacking(self):
        self.task.char_config['Suoming DPS'] = True
        self.char.click_liberation.return_value = True
        actions = Mock()
        actions.attach_mock(self.char.click_liberation, 'liberation')
        actions.attach_mock(self.char.click_resonance, 'resonance')
        actions.attach_mock(self.char.perform_forte, 'forte')

        self.char.do_perform()

        self.assertEqual([call[0] for call in actions.mock_calls],
                         ['liberation', 'resonance', 'forte'])
        self.char.click_resonance.assert_called_once_with(send_click=False, time_out=1)
        self.char.switch_next_char.assert_called_once_with()

    def test_liberation_passes_unison_without_consuming_it_with_resonance(self):
        self.char.click_liberation.return_value = True

        self.char.do_perform()

        self.char.switch_next_char.assert_called_once_with(free_intro=True)
        self.char.click_resonance.assert_not_called()
        self.char.perform_forte.assert_not_called()
        self.task.mouse_down.assert_not_called()

    def test_no_intro_uses_normal_attacks_when_liberation_unavailable(self):
        self.char.has_intro = False
        self.char.do_perform()

        self.char.continues_normal_attack.assert_called_once_with(1.1)
        self.char.switch_next_char.assert_called_once_with()
        self.char.click_resonance.assert_not_called()

    def test_boolean_intro_dispatches_to_configured_role(self):
        for dps in (False, True):
            with self.subTest(dps=dps):
                self.setUp()
                self.task.char_config['Suoming DPS'] = dps
                self.char.has_intro = True

                self.char.do_perform()

                self.char.perform_forte.assert_called_once_with()
                if dps:
                    self.char.click_resonance.assert_called_once_with(send_click=False, time_out=1)
                else:
                    self.char.click_resonance.assert_not_called()
                self.char.continues_normal_attack.assert_called_once_with(duration=1.6)
                self.char.switch_next_char.assert_called_once_with()

    def test_forte_waits_for_prompt_before_holding_resonance(self):
        actions = Mock()
        actions.attach_mock(self.char.continues_click_until, 'attacks')
        self.char.hold_forte_resonance = Mock()
        actions.attach_mock(self.char.hold_forte_resonance, 'hold')

        Suoming.perform_forte(self.char)

        self.char.continues_click_until.assert_called_once_with(self.char.forte_available, time_out=15)
        self.assertEqual([call[0] for call in actions.mock_calls], ['attacks', 'hold'])

    def test_forte_detection_uses_suoming_feature(self):
        self.task.find_one = Mock(side_effect=[object(), None])

        self.assertTrue(self.char.forte_available())
        self.assertFalse(self.char.forte_available())
        self.task.find_one.assert_called_with(Labels.suoming_forte_e)


if __name__ == '__main__':
    unittest.main()
