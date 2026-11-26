import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from config import config
from ok.test.TaskTestCase import TaskTestCase
from src.Labels import Labels
from src.char.BaseChar import BaseChar, CharType, Elements, SwitchPriority
from src.char.CharFactory import get_char_by_pos
from src.char.Lily import Lily
from src.task.AutoCombatTask import AutoCombatTask


ROOT = Path(__file__).resolve().parents[1]


class TestLily(TaskTestCase):
    task_class = AutoCombatTask
    config = {**config, 'template_matching': dict(config['template_matching'])}

    def lily(self):
        char = Lily(self.task, 0, char_name=Labels.char_lily,
                    ring_index=Elements.SPECTRO, char_type=CharType.HEALER)
        char.is_current_char = True
        self.task.chars = [char, None, None]
        return char

    def test_portrait_registration_and_other_slot_negative(self):
        for image in ('lily-start.png', 'lily-heavy.png', 'lily-slumberland.png', 'lily-validation.png'):
            with self.subTest(image=image):
                self.set_image(str(ROOT / 'ok_templates' / image))
                char = get_char_by_pos(self.task, self.task.get_box_by_name('box_char_1'), 0, None)
                self.assertIsInstance(char, Lily)
                self.assertEqual(char.char_type, CharType.HEALER)
                self.assertEqual(char.ring_index, Elements.SPECTRO)
                self.assertEqual(char.buff_time, 30)
                self.assertIsNone(self.task.find_one(
                    Labels.char_lily, box=self.task.get_box_by_name('box_char_2'), threshold=0.6))

    def test_ready_channel_and_slumberland_are_distinct(self):
        char = self.lily()
        for image, full, channel, slumberland, liberation in (
            ('lily-start.png', False, False, False, True),
            ('lily-ready.png', True, False, False, True),
            ('lily-heavy.png', False, True, False, True),
            ('lily-validation.png', False, True, False, True),
            ('lily-slumberland.png', False, False, True, False),
        ):
            with self.subTest(image=image):
                self.set_image(str(ROOT / 'ok_templates' / image))
                self.assertEqual(bool(char.is_mouse_forte_full()), full)
                self.assertEqual(char.heavy_in_progress(), channel)
                self.assertEqual(char.in_slumberland(), slumberland)
                self.assertEqual(char.skip_combat_check(), slumberland)
                self.assertEqual(bool(char.liberation_available()), liberation)

    def test_slumberland_hands_off_without_cancelling_it(self):
        self.set_image(str(ROOT / 'ok_templates/lily-slumberland.png'))
        char = self.lily()
        with (
            patch.object(char, 'click_echo') as echo,
            patch.object(char, 'build_forte') as forte,
            patch.object(char, 'click_liberation') as liberation,
            patch.object(char, 'switch_next_char') as switch,
        ):
            char.do_perform()
        echo.assert_not_called()
        forte.assert_not_called()
        liberation.assert_not_called()
        switch.assert_called_once()

    def test_optional_abyss_character_info_from_screenshot(self):
        self.set_image(str(ROOT / 'ok_templates/lily-help.png'))
        with patch.object(self.task, 'click') as click, patch.object(self.task, 'next_frame'):
            self.assertTrue(self.task.dismiss_abyss_character_info())
        click.assert_called_once_with(0.942, 0.058, after_sleep=0.5)

        self.set_image(str(ROOT / 'ok_templates/lily-start.png'))
        with patch.object(self.task, 'click') as click:
            self.assertFalse(self.task.dismiss_abyss_character_info())
        click.assert_not_called()


class TestLilyLogic(unittest.TestCase):
    def test_rotation_tops_up_full_concerto_when_liberation_is_unavailable(self):
        char = Lily(SimpleNamespace(use_liberation=True), 0)
        with patch.multiple(char, in_slumberland=Mock(return_value=False),
                            click_echo=Mock(), build_forte=Mock(),
                            is_mouse_forte_full=Mock(return_value=True), perform_heavy=Mock(),
                            liberation_available=Mock(return_value=False),
                            fill_concerto=Mock(), click_liberation=Mock(return_value=False),
                            switch_next_char=Mock()):
            char.do_perform()
            char.fill_concerto.assert_called_once_with(1)
            char.switch_next_char.assert_called_once()

    def test_failed_liberation_tops_up_its_missing_concerto_before_switching(self):
        char = Lily(SimpleNamespace(use_liberation=True), 0)
        with patch.multiple(char, in_slumberland=Mock(return_value=False),
                            click_echo=Mock(), build_forte=Mock(),
                            is_mouse_forte_full=Mock(return_value=True), perform_heavy=Mock(),
                            liberation_available=Mock(return_value=True),
                            fill_concerto=Mock(), click_liberation=Mock(return_value=False),
                            switch_next_char=Mock()):
            char.do_perform()
            self.assertEqual([call.args for call in char.fill_concerto.call_args_list], [(0.8,), ()])

    def test_heavy_releases_mouse_when_channel_start_times_out(self):
        task = SimpleNamespace(check_combat=Mock(), mouse_down=Mock(), mouse_up=Mock(),
                               wait_until=Mock(return_value=False))
        self.assertFalse(Lily(task, 0).perform_heavy())
        task.mouse_down.assert_called_once()
        task.mouse_up.assert_called_once()

    def test_heavy_releases_mouse_on_cancellation(self):
        task = SimpleNamespace(check_combat=Mock(), mouse_down=Mock(), mouse_up=Mock(),
                               wait_until=Mock(side_effect=RuntimeError('cancelled')))
        with self.assertRaisesRegex(RuntimeError, 'cancelled'):
            Lily(task, 0).perform_heavy()
        task.mouse_up.assert_called_once()

    def dreamer(self, since_cast=None):
        task = SimpleNamespace(use_liberation=True, now=time.time(), freeze=0.0)
        task.time_elapsed_accounting_for_freeze = lambda start, *args: task.now - start - task.freeze
        char = Lily(task, 0)
        if since_cast is not None:
            char.arm_slumberland_block(char.SLUMBERLAND_DURATION)
            task.now = char.slumberland_start + since_cast
        return char, task

    def rotation(self, char):
        return patch.multiple(char, click_echo=Mock(), build_forte=Mock(),
                              is_mouse_forte_full=Mock(return_value=True), perform_heavy=Mock(),
                              liberation_available=Mock(return_value=True),
                              fill_concerto=Mock(), switch_next_char=Mock())

    def cast(self, char, recognised=True):
        with (
            self.rotation(char),
            patch.object(char, 'in_slumberland', return_value=False),
            patch.object(char, 'click_liberation', return_value=recognised),
        ):
            char.do_perform()

    def test_cast_refuses_every_switch_in_then_only_intros(self):
        char, task = self.dreamer()
        self.cast(char)
        self.assertEqual(char.slumberland_block, char.SLUMBERLAND_DURATION)
        for elapsed, has_intro, expected in (
                (5, False, SwitchPriority.NO), (24.9, True, SwitchPriority.NO),
                (25.1, True, SwitchPriority.NORMAL), (49.9, False, SwitchPriority.NO),
                (50.1, False, SwitchPriority.NORMAL), (50.1, True, SwitchPriority.NORMAL)):
            with self.subTest(elapsed=elapsed, has_intro=has_intro):
                task.now = char.slumberland_start + elapsed
                self.assertEqual(char.get_switch_priority(has_intro=has_intro), expected)

    def test_intro_lockout_can_be_turned_off(self):
        char, task = self.dreamer()
        char.SLUMBERLAND_INTRO_LOCKOUT = 0
        self.cast(char)
        task.now = char.slumberland_start + 1
        self.assertEqual(char.get_switch_priority(has_intro=True), SwitchPriority.NORMAL)
        self.assertEqual(char.get_switch_priority(has_intro=False), SwitchPriority.NO)

    def test_time_stops_do_not_use_the_window_up(self):
        char, task = self.dreamer()
        self.cast(char)
        task.freeze = 3
        task.now = char.slumberland_start + 49
        self.assertEqual(char.get_switch_priority(has_intro=False), SwitchPriority.NO)
        task.now = char.slumberland_start + 26
        self.assertEqual(char.get_switch_priority(has_intro=True), SwitchPriority.NO)
        task.now = char.slumberland_start + 53.1
        self.assertEqual(char.get_switch_priority(has_intro=False), SwitchPriority.NORMAL)
        task.now = char.slumberland_start + 28.1
        self.assertEqual(char.get_switch_priority(has_intro=True), SwitchPriority.NORMAL)

    def test_unrecognised_liberation_does_not_start_a_window(self):
        char, _ = self.dreamer()
        self.cast(char, recognised=False)
        self.assertEqual(char.slumberland_start, 0.0)
        self.assertEqual(char.get_switch_priority(has_intro=False), SwitchPriority.NORMAL)

    def test_found_asleep_without_a_window_only_blocks_briefly(self):
        char, task = self.dreamer()
        with (
            patch.object(char, 'in_slumberland', return_value=True),
            patch.object(char, 'click_echo') as echo,
            patch.object(char, 'switch_next_char') as switch,
        ):
            char.do_perform()
        echo.assert_not_called()
        switch.assert_called_once()
        self.assertEqual(char.slumberland_block, char.SLUMBERLAND_SIGHTING_BLOCK)
        self.assertLess(char.slumberland_block, char.SLUMBERLAND_DURATION)
        self.assertEqual(char.get_switch_priority(has_intro=False), SwitchPriority.NO)
        self.assertEqual(char.get_switch_priority(has_intro=True), SwitchPriority.NO)
        task.now = char.slumberland_start + char.SLUMBERLAND_SIGHTING_BLOCK + 0.1
        self.assertEqual(char.get_switch_priority(has_intro=False), SwitchPriority.NORMAL)
        self.assertEqual(char.get_switch_priority(has_intro=True), SwitchPriority.NORMAL)

    def test_found_asleep_inside_a_running_window_keeps_its_end(self):
        char, _ = self.dreamer(since_cast=40)
        start = char.slumberland_start
        with (
            patch.object(char, 'in_slumberland', return_value=True),
            patch.object(char, 'switch_next_char') as switch,
        ):
            char.do_perform()
        switch.assert_called_once()
        self.assertEqual(char.slumberland_start, start)
        self.assertEqual(char.get_switch_priority(has_intro=False), SwitchPriority.NO)

    def test_found_awake_on_field_clears_the_window(self):
        char, _ = self.dreamer(since_cast=40)
        self.cast(char, recognised=False)
        self.assertEqual(char.slumberland_start, 0.0)
        self.assertEqual(char.get_switch_priority(has_intro=False), SwitchPriority.NORMAL)

    def test_intro_entry_is_given_time_to_wake_up(self):
        char, _ = self.dreamer(since_cast=30)
        char.has_intro = True
        calls = []
        with (
            patch.object(char, 'in_slumberland', side_effect=lambda: calls.append('look') or False),
            patch.object(char, 'continues_normal_attack',
                         side_effect=lambda *args: calls.append('wait')) as attack,
            self.rotation(char),
            patch.object(char, 'click_liberation', return_value=False),
        ):
            char.do_perform()
        attack.assert_called_once_with(0.8)
        self.assertEqual(calls, ['wait', 'look'])
        self.assertEqual(char.slumberland_start, 0.0)

    def test_intro_entry_still_asleep_hands_off_and_blocks_briefly(self):
        char, _ = self.dreamer()
        char.has_intro = True
        with (
            patch.object(char, 'in_slumberland', return_value=True),
            patch.object(char, 'continues_normal_attack') as attack,
            patch.object(char, 'click_echo') as echo,
            patch.object(char, 'switch_next_char') as switch,
        ):
            char.do_perform()
        attack.assert_called_once_with(0.8)
        echo.assert_not_called()
        switch.assert_called_once()
        self.assertEqual(char.slumberland_block, char.SLUMBERLAND_SIGHTING_BLOCK)

    def healer(self, since_cast=None):
        char, task = self.dreamer(since_cast)
        char.set_char_type(CharType.HEALER)
        return char, task

    def handed_off(self):
        """Record what the base hand-off sees, without running the real switch."""
        seen = []

        def switch(char, post_action=None, free_intro=False, target_low_con=False):
            off = getattr(char.task, 'skip_combat_check', False)
            seen.append((off, post_action, free_intro, target_low_con))
            return 'handed off'

        return patch.object(BaseChar, 'switch_next_char', switch), seen

    def test_hand_off_inside_the_window_skips_the_combat_check(self):
        char, task = self.healer(since_cast=0.05)
        task.skip_combat_check = False
        recorder, seen = self.handed_off()
        with recorder:
            self.assertEqual(
                char.switch_next_char(post_action='post', free_intro=True, target_low_con=True),
                'handed off')
        self.assertEqual(seen, [(True, 'post', True, True)])
        self.assertFalse(task.skip_combat_check)

    def test_hand_off_outside_the_window_keeps_the_combat_check(self):
        char, task = self.healer()
        task.skip_combat_check = False
        recorder, seen = self.handed_off()
        with recorder:
            char.switch_next_char(post_action='post', free_intro=True, target_low_con=True)
        self.assertEqual(seen, [(False, 'post', True, True)])
        self.assertFalse(task.skip_combat_check)

    def test_hand_off_outside_the_window_leaves_a_task_without_the_flag_alone(self):
        char, task = self.healer()
        recorder, seen = self.handed_off()
        with recorder:
            char.switch_next_char()
        self.assertEqual([entry[0] for entry in seen], [False])
        self.assertFalse(hasattr(task, 'skip_combat_check'))

    def test_hand_off_restores_the_combat_check_when_the_switch_fails(self):
        char, task = self.healer(since_cast=1)
        task.skip_combat_check = False

        def switch(char, *args, **kwargs):
            raise RuntimeError('not in combat')

        with (patch.object(BaseChar, 'switch_next_char', switch),
              self.assertRaisesRegex(RuntimeError, 'not in combat')):
            char.switch_next_char()
        self.assertFalse(task.skip_combat_check)

    def test_hand_off_restores_a_check_that_was_already_off(self):
        char, task = self.healer(since_cast=1)
        task.skip_combat_check = True
        recorder, seen = self.handed_off()
        with recorder:
            char.switch_next_char()
        self.assertEqual([entry[0] for entry in seen], [True])
        self.assertTrue(task.skip_combat_check)

    def test_hand_off_after_a_sighting_skips_the_combat_check(self):
        char, task = self.healer()
        task.skip_combat_check = False
        recorder, seen = self.handed_off()
        with (recorder, patch.object(char, 'in_slumberland', return_value=True)):
            char.do_perform()
        self.assertEqual([entry[0] for entry in seen], [True])
        self.assertFalse(task.skip_combat_check)

    def test_hand_off_after_the_cast_skips_the_combat_check(self):
        char, task = self.healer()
        task.skip_combat_check = False
        hand_off = char.switch_next_char
        recorder, seen = self.handed_off()
        asleep = patch.object(char, 'in_slumberland', return_value=False)
        with (recorder, self.rotation(char), asleep,
              patch.object(char, 'click_liberation', return_value=True),
              patch.object(char, 'switch_next_char', hand_off)):
            char.do_perform()
        self.assertEqual([entry[0] for entry in seen], [True])
        self.assertFalse(task.skip_combat_check)

    def test_on_combat_end_switches_off_sleeping_lily(self):
        char, _ = self.healer(since_cast=2)
        with (patch.object(char, 'in_slumberland', return_value=False),
              patch.object(char, 'switch_other_char') as switch):
            char.on_combat_end([])
        switch.assert_called_once_with()

        awake, _ = self.healer()
        with (patch.object(awake, 'in_slumberland', return_value=True),
              patch.object(awake, 'switch_other_char') as switch):
            awake.on_combat_end([])
        switch.assert_called_once_with()

        with (patch.object(awake, 'in_slumberland', return_value=False),
              patch.object(awake, 'switch_other_char') as switch):
            awake.on_combat_end([])
        switch.assert_not_called()

    def heavy_task(self, results, **extra):
        defaults = dict(check_combat=Mock(), mouse_down=Mock(), mouse_up=Mock(),
                        sleep=Mock(), wait_until=Mock(side_effect=results),
                        in_team=Mock(return_value=(True, 0, 3)))
        defaults.update(extra)
        return SimpleNamespace(**defaults)

    def test_heavy_flower_form_completes_normally(self):
        task = self.heavy_task(['flower', True])
        char = Lily(task, 0)
        with patch.object(char.logger, 'info') as info:
            self.assertTrue(char.perform_heavy())
        task.mouse_down.assert_called_once()
        task.mouse_up.assert_called_once()
        task.sleep.assert_called_once_with(0.7)
        info.assert_called_once_with('Lily heavy finisher completed')

    def test_heavy_alternate_form_holds_when_prompt_disappears_on_field(self):
        clock = [100.0]
        task = self.heavy_task([])
        char = Lily(task, 0)
        prompt = [False]
        flower = [False]

        def wait_until(cond, time_out=0, **kwargs):
            for _ in range(100):
                res = cond()
                if res:
                    return res
                clock[0] += 0.1
            return False

        task.wait_until = wait_until
        with (patch('src.char.Lily.time.time', side_effect=lambda: clock[0]),
              patch.object(char, 'heavy_in_progress', side_effect=lambda: flower[0]),
              patch.object(char, 'is_mouse_forte_full', side_effect=lambda: prompt[0]),
              patch.object(char.logger, 'info') as info):
            self.assertTrue(char.perform_heavy())
        self.assertGreaterEqual(clock[0] - 100.0, Lily.HEAVY_ALT_HOLD)
        task.mouse_down.assert_called_once()
        task.mouse_up.assert_called_once()
        task.sleep.assert_called_once_with(0.7)
        info.assert_called_once_with('Lily heavy finisher completed (alternate form)')

    def test_heavy_late_flower_upgrades_alternate_wait_to_flower_finish(self):
        task = self.heavy_task(['alt', 'flower', True])
        char = Lily(task, 0)
        with patch.object(char.logger, 'info') as info:
            self.assertTrue(char.perform_heavy())
        self.assertEqual(task.wait_until.call_count, 3)
        info.assert_called_once_with('Lily heavy finisher completed')

    def test_heavy_presses_again_with_gap_when_prompt_is_still_up(self):
        task = self.heavy_task([False, True, 'flower', True])
        char = Lily(task, 0)
        self.assertTrue(char.perform_heavy())
        self.assertEqual(task.mouse_down.call_count, 2)
        self.assertEqual(task.mouse_up.call_count, 2)
        self.assertEqual([c.args for c in task.sleep.call_args_list],
                         [(Lily.HEAVY_RETRY_GAP,), (0.7,)])
        retry = task.wait_until.call_args_list[1]
        self.assertEqual(retry.args[0].__name__, 'heavy_still_ready')
        self.assertEqual(retry.kwargs, {'time_out': Lily.HEAVY_RETRY_CHECK})

    def test_heavy_second_press_that_does_not_start_still_fails(self):
        task = self.heavy_task([False, True, False])
        char = Lily(task, 0)
        with patch.object(char.logger, 'warning') as warning:
            self.assertFalse(char.perform_heavy())
        self.assertEqual(task.mouse_down.call_count, 2)
        self.assertEqual(task.mouse_up.call_count, 2)
        warning.assert_called_once_with('Lily heavy channel did not start')

    def test_heavy_does_not_press_again_when_prompt_is_gone(self):
        task = self.heavy_task([False, False])
        char = Lily(task, 0)
        with patch.object(char.logger, 'warning') as warning:
            self.assertFalse(char.perform_heavy())
        task.mouse_down.assert_called_once()
        task.mouse_up.assert_called_once()
        warning.assert_called_once_with('Lily heavy channel did not start')

    def test_heavy_retry_and_alt_require_lily_on_field_with_visible_team(self):
        clock = [100.0]
        task = self.heavy_task([])
        char = Lily(task, 0)
        for prompt, team_state, presses, started in (
                (True, (True, 0, 3), 2, True),
                (True, (True, 1, 3), 1, False),
                (True, (False, -1, 1), 1, False),
                (False, (True, 1, 3), 1, False),
                (False, (False, -1, 1), 1, False)):
            with self.subTest(prompt=prompt, team_state=team_state):
                task.mouse_down.reset_mock()
                task.mouse_up.reset_mock()
                task.in_team.return_value = team_state
                clock[0] = 100.0

                def wait_until(cond, time_out=0, **kwargs):
                    res = cond()
                    if res:
                        return res
                    if time_out >= 1:
                        clock[0] += 0.5
                        return cond()
                    return False

                task.wait_until = wait_until
                with (patch('src.char.Lily.time.time', side_effect=lambda: clock[0]),
                      patch.object(char, 'heavy_in_progress',
                                   side_effect=[False, False, True, False]),
                      patch.object(char, 'is_mouse_forte_full', return_value=prompt)):
                    self.assertEqual(char.perform_heavy(), started)
                self.assertEqual(task.mouse_down.call_count, presses)
                self.assertEqual(task.mouse_up.call_count, presses)

    def test_heavy_releases_mouse_cleanly_on_cancel_at_any_stage(self):
        task = self.heavy_task([False, True, RuntimeError('cancelled')])
        with self.assertRaisesRegex(RuntimeError, 'cancelled'):
            Lily(task, 0).perform_heavy()
        self.assertEqual(task.mouse_down.call_count, 2)
        self.assertEqual(task.mouse_up.call_count, 2)

        task2 = self.heavy_task([False, True], sleep=Mock(side_effect=RuntimeError('paused')))
        with self.assertRaisesRegex(RuntimeError, 'paused'):
            Lily(task2, 0).perform_heavy()
        self.assertEqual(task2.mouse_down.call_count, 1)
        self.assertEqual(task2.mouse_up.call_count, 1)

    def test_log_tells_a_drained_liberation_from_one_that_is_off(self):
        char, task = self.dreamer()
        for available, enabled, expected in ((False, True, 'not ready'), (True, True, None),
                                             (False, False, 'off')):
            with self.subTest(available=available, enabled=enabled):
                task.use_liberation = enabled
                with (self.rotation(char), patch.object(char, 'in_slumberland', return_value=False),
                      patch.object(char, 'liberation_available', return_value=available),
                      patch.object(char, 'click_liberation', return_value=False),
                      patch.object(char.logger, 'info') as info):
                    char.do_perform()
                lines = [call.args[0] for call in info.call_args_list
                         if 'Liberation is' in call.args[0]]
                expected_line = None if expected is None else f'Lily Liberation is {expected}'
                self.assertEqual(lines, [] if expected_line is None else [expected_line])
