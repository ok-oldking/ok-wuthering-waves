import unittest
from unittest.mock import Mock, patch

from src.char.BaseChar import CharType, Elements
from src.char.Rover import Rover


class RoverInitializationTest(unittest.TestCase):
    def test_wind_team_state_initializes_when_form_is_already_known(self):
        class Task:
            _app = None

            def has_char(self, char_class):
                return char_class.__name__ in {'Cartethyia', 'Phoebe'}

        task = Task()
        rover = Rover(task, 0, ring_index=Elements.WIND)

        rover.init()

        self.assertTrue(rover.use_skyfall_severance)


class _Clock:
    def __init__(self):
        self.now = 1000.0

    def advance(self, seconds):
        self.now += seconds

    def wait_until(self, condition, time_out, settle_time=0, pre_action=None):
        start, settled = self.now, None
        while True:
            if pre_action:
                pre_action()
            self.advance(0.05)
            if condition():
                if settled is None:
                    settled = self.now
                if self.now - settled > settle_time:
                    return True
            else:
                settled = None
            if self.now - start > time_out:
                return None


class RoverElectricTest(unittest.TestCase):
    def make_rover(self):
        task = Mock()
        rover = Rover(task, 0, ring_index=Elements.ELECTRIC)
        for name, result in [('wait_down', None), ('click_echo', True), ('liberation_available', False),
                             ('click_liberation', False), ('resonance_available', False),
                             ('click_resonance', (True, 0.1, False)), ('electric_skill_ready', True),
                             ('short_electric_skill', True), ('is_con_full', True), ('click', None),
                             ('continues_normal_attack', None), ('switch_next_char', None)]:
            setattr(rover, name, Mock(return_value=result))
        return rover

    def test_electric_form_is_named_and_uses_support_rotation(self):
        rover = self.make_rover()
        rover.perform_electric_routine = Mock()
        rover.do_perform()
        self.assertEqual(rover.display_name, 'Rover: Electro')
        self.assertEqual(rover.char_type, CharType.SUB_DPS)
        rover.perform_electric_routine.assert_called_once()
        getattr(rover, 'switch_next_char').assert_called_once()

    def test_unknown_and_reset_forms_keep_support_role_until_reidentified(self):
        rover = Rover(Mock(), 0, char_type=CharType.MAIN_DPS, buff_time=14)
        self.assertTrue(rover.is_sub_dps)
        for form in (Elements.ELECTRIC, Elements.SPECTRO, Elements.WIND, Elements.HAVOC):
            with self.subTest(form=form):
                expected = CharType.SUB_DPS if form == Elements.ELECTRIC else CharType.MAIN_DPS
                rover.ring_index = form
                for _ in range(2):
                    rover.reset_state()
                    rover.set_char_type(CharType.MAIN_DPS)
                    rover.set_buff_time(14)
                    self.assertEqual(rover.ring_index, -1)
                    self.assertEqual(rover.char_type, expected)
                    self.assertEqual(rover.buff_time, 14)
        rover.ring_index = Elements.ELECTRIC
        rover.reset_state()
        rover.task._app = None
        rover.task.chars = [rover]
        rover.task._ensure_ring_index.side_effect = lambda: setattr(rover, 'ring_index', Elements.SPECTRO)
        rover.init()
        self.assertTrue(rover.is_main_dps)
        self.assertEqual(rover.display_name, 'Rover: Spectro')

    def test_existing_form_dispatch_and_havoc_early_return(self):
        for form, routine in [(Elements.SPECTRO, 'perform_spectro_routine'),
                              (Elements.WIND, 'perform_wind_routine'),
                              (Elements.HAVOC, 'perform_havoc_routine'), (-1, 'perform_basic_routine')]:
            with self.subTest(form=form):
                rover = self.make_rover()
                rover.ring_index = form
                rover.init = Mock()
                action = Mock(return_value=False)
                setattr(rover, routine, action)
                rover.do_perform()
                action.assert_called_once()
                getattr(rover, 'switch_next_char').assert_called_once()
        rover = self.make_rover()
        rover.ring_index = Elements.HAVOC
        rover.perform_havoc_routine = Mock(return_value=True)
        rover.do_perform()
        getattr(rover, 'switch_next_char').assert_not_called()

    def test_echo_uses_default_helper_and_opening_liberation_is_preserved(self):
        rover = self.make_rover()
        getattr(rover, 'click_liberation').return_value = True
        rover.perform_electric_routine()
        getattr(rover, 'click_echo').assert_called_once_with()
        getattr(rover, 'click_liberation').assert_called_once_with(click_f=False)
        getattr(rover, 'continues_normal_attack').assert_not_called()

    def test_partial_gauge_cannot_be_ready_just_because_e_hint_matches(self):
        rover = Rover(Mock(), 0, ring_index=Elements.ELECTRIC)
        rover.is_forte_full = Mock(return_value=False)
        rover.is_e_forte_full = Mock(return_value=True)
        self.assertFalse(rover.electric_skill_ready())
        rover.is_forte_full.return_value = True
        self.assertTrue(rover.electric_skill_ready())
        rover.is_e_forte_full.return_value = False
        self.assertFalse(rover.electric_skill_ready())

    def test_charge_timeout_is_bounded_and_switches_out(self):
        for intro, limit in [(False, 12), (True, 8)]:
            with self.subTest(intro=intro):
                rover, clock = self.make_rover(), _Clock()
                rover.has_intro = intro
                getattr(rover, 'electric_skill_ready').return_value = False
                rover.sleep = Mock(side_effect=clock.advance)
                rover.task.time_elapsed_accounting_for_freeze.side_effect = lambda start, intro_motion_freeze=False: clock.now - start
                with patch('src.char.Rover.time.time', side_effect=lambda: clock.now):
                    rover.do_perform()
                self.assertGreaterEqual(clock.now - 1000, limit)
                self.assertLess(clock.now - 1000, limit + 0.2)
                getattr(rover, 'click').assert_called()
                getattr(rover, 'short_electric_skill').assert_not_called()
                getattr(rover, 'switch_next_char').assert_called_once()

    def test_failed_e_skips_post_skill_liberation_and_normal_attacks(self):
        rover = self.make_rover()
        getattr(rover, 'short_electric_skill').return_value = False
        rover.perform_electric_routine()
        getattr(rover, 'click_liberation').assert_called_once_with(click_f=False)
        getattr(rover, 'continues_normal_attack').assert_not_called()

    def test_post_e_liberation_fills_concerto_without_extra_attacks(self):
        rover, events = self.make_rover(), []
        getattr(rover, 'short_electric_skill').side_effect = lambda: events.append('E2') or True
        getattr(rover, 'is_con_full').side_effect = [False, True]
        getattr(rover, 'click_liberation').side_effect = lambda **kwargs: events.append('R') or True
        rover.perform_electric_routine()
        self.assertEqual(events, ['R', 'E2', 'R'])
        self.assertEqual(getattr(rover, 'click_liberation').call_count, 2)
        self.assertEqual(getattr(rover, 'click_liberation').call_args.kwargs, {'click_f': False})
        getattr(rover, 'continues_normal_attack').assert_not_called()

    def test_unavailable_liberation_falls_back_to_normal_attacks(self):
        rover = self.make_rover()
        getattr(rover, 'is_con_full').return_value = False
        rover.perform_electric_routine()
        self.assertEqual(getattr(rover, 'click_liberation').call_count, 2)
        getattr(rover, 'continues_normal_attack').assert_called_once_with(2, until_con_full=True)

    def test_failed_or_incomplete_liberation_precedes_normal_attacks(self):
        for success in (False, True):
            with self.subTest(liberation_success=success):
                rover, events = self.make_rover(), []
                getattr(rover, 'is_con_full').return_value = False
                getattr(rover, 'click_liberation').side_effect = lambda **kwargs: events.append('R') or success
                getattr(rover, 'continues_normal_attack').side_effect = lambda *args, **kwargs: events.append('attack')
                rover.perform_electric_routine()
                self.assertEqual(events, ['R', 'R', 'attack'])
                getattr(rover, 'continues_normal_attack').assert_called_once_with(2, until_con_full=True)

    def test_dim_opening_r_uses_real_helper_retry_instead_of_skipping(self):
        rover, clock = self.make_rover(), _Clock()
        rover.click_liberation = Rover.click_liberation.__get__(rover)
        rover.task.use_liberation = True
        rover.task.in_liberation = False
        rover.has_cd = Mock(side_effect=lambda name: rover.task.send_key.called)
        rover.task.get_liberation_key.return_value = 'r'
        rover.task.send_key.side_effect = lambda key, **kwargs: clock.advance(kwargs.get('after_sleep', 0))
        rover.task.next_frame.side_effect = lambda: clock.advance(0.05)
        rover.task.in_team.side_effect = [(False, 0, 3), (False, 0, 3), (True, 0, 3)]
        rover.task.wait_until.side_effect = lambda condition, **kwargs: condition()
        with patch('src.char.Rover.time.time', side_effect=lambda: clock.now):
            rover.perform_electric_routine()
        getattr(rover, 'liberation_available').assert_called()
        self.assertFalse(getattr(rover, 'liberation_available').return_value)
        self.assertTrue(rover.task.send_key.called)
        self.assertTrue(all(call.args[0] == 'r' for call in rover.task.send_key.call_args_list))
        self.assertGreater(rover.last_liberation, 0)
        getattr(rover, 'continues_normal_attack').assert_not_called()

    def test_real_liberation_helper_skips_cooldown_or_disabled_setting(self):
        for enabled, cooldown in [(True, True), (False, False)]:
            with self.subTest(enabled=enabled, cooldown=cooldown):
                rover = self.make_rover()
                rover.click_liberation = Rover.click_liberation.__get__(rover)
                rover.task.use_liberation = enabled
                rover.task.in_liberation = False
                rover.has_cd = Mock(return_value=cooldown)
                rover.perform_electric_routine()
                rover.task.send_key.assert_not_called()

    def test_real_helper_no_energy_retry_is_short_and_does_not_block_e(self):
        rover, clock = self.make_rover(), _Clock()
        rover.click_liberation = Rover.click_liberation.__get__(rover)
        rover.task.use_liberation = True
        rover.task.in_liberation = False
        rover.has_cd = Mock(return_value=False)
        rover.task.get_liberation_key.return_value = 'r'
        rover.task.send_key.side_effect = lambda key, **kwargs: clock.advance(kwargs.get('after_sleep', 0))
        rover.task.wait_until.return_value = None
        with patch('src.char.Rover.time.time', side_effect=lambda: clock.now):
            rover.perform_electric_routine()
        self.assertLessEqual(clock.now - 1000, 0.2)
        getattr(rover, 'short_electric_skill').assert_called_once()
        self.assertEqual(rover.last_liberation, -1)

    def run_enhanced_e(self, clear_after_attempt: int | None = 1, flicker=False, hint_only=False, ready=True):
        rover, clock = Rover(Mock(), 0, ring_index=Elements.ELECTRIC), _Clock()
        attempts = []
        rover.electric_skill_ready = Mock(return_value=ready)
        rover.send_resonance_key = Mock(side_effect=lambda **kwargs: attempts.append(clock.now))
        rover.record_resonance_use = Mock()
        rover.check_combat = Mock()
        rover.task.is_con_full.return_value = True
        rover.task.wait_until.side_effect = clock.wait_until
        rover.task.time_elapsed_accounting_for_freeze.side_effect = lambda start, intro_motion_freeze=False: clock.now - start

        def cleared():
            if not attempts:
                return False
            if flicker and 1.6 <= clock.now - attempts[0] < 1.7:
                return True
            return clear_after_attempt is not None and len(attempts) >= clear_after_attempt and clock.now - attempts[-1] >= 2.1

        rover.is_forte_full = Mock(side_effect=lambda: hint_only or not cleared())
        rover.is_e_forte_full = Mock(side_effect=lambda: not cleared())
        with patch('src.char.Rover.time.time', side_effect=lambda: clock.now):
            consumed = rover.short_electric_skill()
        return rover, clock.now - 1000, attempts, consumed

    def test_enhanced_e_waits_for_tail_even_if_concerto_is_full(self):
        rover, elapsed, attempts, consumed = self.run_enhanced_e()
        self.assertTrue(consumed)
        self.assertEqual(len(attempts), 1)
        self.assertGreaterEqual(elapsed, 2.3)
        self.assertLess(elapsed, 2.6)
        getattr(rover, 'send_resonance_key').assert_called_once_with(down_time=0.05)
        getattr(rover, 'record_resonance_use').assert_called_once()
        getattr(rover, 'check_combat').assert_called()

    def test_missed_enhanced_e_can_retry_once(self):
        rover, elapsed, attempts, consumed = self.run_enhanced_e(clear_after_attempt=2)
        self.assertTrue(consumed)
        self.assertEqual(len(attempts), 2)
        self.assertLess(elapsed, 5.5)
        getattr(rover, 'record_resonance_use').assert_called_once()

    def test_flicker_or_hint_only_disappearance_does_not_confirm_consumption(self):
        for clear_after, flicker, hint_only in [(None, False, False), (None, True, False), (1, False, True)]:
            with self.subTest(clear_after=clear_after, flicker=flicker, hint_only=hint_only):
                rover, elapsed, attempts, consumed = self.run_enhanced_e(clear_after, flicker, hint_only)
                self.assertFalse(consumed)
                self.assertEqual(len(attempts), 2)
                self.assertLess(elapsed, 5.5)
                getattr(rover, 'record_resonance_use').assert_not_called()

    def test_not_ready_enhanced_e_does_not_send_a_key(self):
        rover, elapsed, attempts, consumed = self.run_enhanced_e(ready=False)
        self.assertFalse(consumed)
        self.assertEqual(attempts, [])
        self.assertEqual(elapsed, 0)
        getattr(rover, 'record_resonance_use').assert_not_called()


if __name__ == '__main__':
    unittest.main()
