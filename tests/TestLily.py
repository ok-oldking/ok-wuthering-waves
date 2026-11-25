import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from config import config
from ok.test.TaskTestCase import TaskTestCase
from src.Labels import Labels
from src.char.BaseChar import CharType, Elements, SwitchPriority
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
