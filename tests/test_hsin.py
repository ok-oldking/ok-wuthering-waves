import unittest
from threading import Event
from types import SimpleNamespace
from unittest.mock import create_autospec, patch

import cv2
import numpy as np

from ok.feature.FeatureSet import FeatureSet
from ok.task.TaskExecutor import TaskExecutor
from src.Labels import Labels
from src.char.BaseChar import BaseChar
from src.char.Hsin import Hsin
from src.combat.CombatCheck import CombatCheck
from src.task.BaseCombatTask import BaseCombatTask, NotInCombatException
from src.task.BaseWWTask import binarize_for_matching
from src.task.process_feature import process_feature


class _Clock:
    def __init__(self):
        self.now = 100.0

    def time(self):
        return self.now

    def advance(self, duration):
        self.now += max(0, duration)


class _Task(TaskExecutor):
    use_liberation = False
    in_liberation = False

    def __init__(self, clock: _Clock):
        self.clock = clock
        self.exit_event = Event()
        self.wait_scene_timeout = 1
        self.wait_until_settle_time = 0
        self.features = lambda: set()
        self.mouse_start: float | None = None
        self.down_at: list[float] = []
        self.up_at: list[float] = []
        self.frames = 0
        self.fail_frame = False
        self.pressed = False

    def reset_scene(self, check_enabled=True):
        pass

    def next_frame(self, time_out=6):
        self.frames += 1
        if self.frames >= 3000:
            raise AssertionError('unbounded rotation')
        if self.fail_frame:
            raise RuntimeError('combat ended')
        self.clock.advance(0.05)

    def wait_until(self, condition, **kwargs):
        return TaskExecutor.wait_condition(self, condition, **kwargs)

    def find_one(self, label, **kwargs):
        return label in self.features()

    def mouse_down(self):
        self.pressed = True
        self.mouse_start = self.clock.time()
        self.down_at.append(self.mouse_start)

    def mouse_up(self):
        self.pressed = False
        self.up_at.append(self.clock.time())

    def send_key(self, key):
        pass

    def check_combat(self):
        pass

    def in_team(self):
        return True, None


class _Hsin(Hsin):
    def __init__(self, clock: _Clock):
        super().__init__(_Task(clock), 0, char_name='Hsin')
        self.clock = clock
        self.freeze: list[tuple[float, float]] = []
        self.casts: list[tuple[int, float]] = []
        self.echoes = 0
        self.normals = 0
        self.resonances = 0
        self.lib_success = True
        self.e_ready = False

    def send_resonance_key(self, *args, **kwargs):
        self.resonances += 1

    def check_combat(self):
        pass

    def sleep(self, sec, check_combat=True):
        self.clock.advance(sec)

    def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
        return self.clock.time() - start - sum(d for s, d in self.freeze if s > start)

    def cycle_sleep(self, duration=0.1):
        self.sleep(duration)

    def liberation_available(self, check_color=True) -> bool:
        return True

    def click_liberation(self, *args, **kwargs) -> bool:
        is_lib2 = self.task.find_one(Labels.hsin_lib2) or self.h2_completed
        self.casts.append((2 if is_lib2 else 1, self.clock.time()))
        if self.lib_success:
            self.freeze.append((self.clock.time() + 0.01, 4))
            self.sleep(4)
        return self.lib_success

    def resonance_available(self):
        return self.e_ready

    def is_e_forte_full(self):
        return self.e_ready

    def click_resonance(self, *args, **kwargs):
        self.resonances += 1
        self.sleep(0.55)
        self.e_ready = False
        return True, 0.55, False

    def click_echo(self, *args, **kwargs):
        self.echoes += 1
        return False

    def click(self, *args, **kwargs):
        self.normals += 1


class HsinRotationTest(unittest.TestCase):
    def setUp(self):
        self.clock = _Clock()
        timer = patch('src.char.Hsin.time.time', self.clock.time)
        timer.start()
        self.addCleanup(timer.stop)
        self.char = _Hsin(self.clock)

    def finishing(self):
        self.char.finisher_start = self.clock.time()

    def h2_until_consumed(self):
        char = self.char
        char.task.features = lambda: ({Labels.hsin_h2}
                                     if char.task.mouse_start is None
                                     or self.clock.time() - char.task.mouse_start < 0.4 else set())

    def lost_target_checks(self, lost_before_hold=False):
        char = self.char
        retargets = []
        checker = create_autospec(
            BaseCombatTask, instance=True,
            skip_combat_check=False, _in_combat=True, in_liberation=False,
            scene=SimpleNamespace(in_combat=lambda: None, set_in_combat=lambda: True),
            check_f_break=lambda: None, get_current_char=lambda: char,
            on_combat_check=lambda: True, combat_end_condition=None,
            has_target=lambda: not lost_before_hold and char.task.mouse_start is None,
            should_check_monthly_card=lambda: False)

        def retarget(wait=True, **kwargs):
            retargets.append(self.clock.now)
            self.clock.advance(3)
            return False

        def reset(reason=''):
            checker._in_combat = False
            return False

        def abort(message):
            raise NotInCombatException(message)

        checker.target_enemy = retarget
        checker.reset_to_false = reset
        checker.raise_not_in_combat = abort
        checker.in_combat = lambda: CombatCheck.do_check_in_combat(checker, False)
        char.task.check_combat = lambda: BaseCombatTask.check_combat(checker)
        char.check_combat = lambda: BaseChar.check_combat(char)
        return retargets

    def test_h2_lost_target_during_animation_still_reaches_delayed_r2(self):
        char = self.char
        self.finishing()
        self.h2_until_consumed()
        retargets = self.lost_target_checks()
        char.liberation_available = lambda check_color=True: (char.task.mouse_start is not None
                                                             and self.clock.now - char.task.mouse_start >= 2.8)

        def cycle_sleep(duration=0.1):
            self.clock.advance(duration)
            char.check_combat()

        char.cycle_sleep = cycle_sleep
        char.perform_everything()
        self.assertEqual([stage for stage, _ in char.casts], [2])
        self.assertEqual(retargets, [])
        self.assertFalse(char.skip_combat_check())
        self.assertFalse(char.task.pressed)
        with self.assertRaises(NotInCombatException):
            char.check_combat()

    def test_h2_guard_expires_if_r2_never_becomes_available(self):
        char = self.char
        self.h2_until_consumed()
        retargets = self.lost_target_checks()
        char.liberation_available = lambda check_color=True: False

        def cycle_sleep(duration=0.1):
            self.clock.advance(duration)
            char.check_combat()

        char.cycle_sleep = cycle_sleep
        with self.assertRaises(NotInCombatException):
            char.do_perform()
        self.assertEqual(len(retargets), 1)
        self.assertTrue(4 <= retargets[0] - char.task.down_at[0] < 4.2)
        self.assertFalse(char.skip_combat_check())
        self.assertFalse(char.task.pressed)
        self.assertEqual(char.casts, [])

    def test_failure_after_confirmed_h2_clears_protection_on_exit(self):
        char = self.char
        self.h2_until_consumed()

        def fail_liberation(**kwargs):
            raise RuntimeError('liberation failed')

        char.click_liberation = fail_liberation
        with self.assertRaisesRegex(RuntimeError, 'liberation failed'):
            char.do_perform()
        self.assertFalse(char.task.pressed)
        self.assertFalse(char.skip_combat_check())

    def test_h1_does_not_get_h2_target_loss_protection(self):
        self.char.task.features = lambda: {Labels.hsin_h1}
        retargets = self.lost_target_checks()
        with self.assertRaises(NotInCombatException):
            self.char.handle_heavy(1)
        self.assertEqual(len(retargets), 1)
        self.assertFalse(self.char.task.pressed)
        self.assertFalse(self.char.skip_combat_check())

    def test_h2_checks_combat_before_starting_protection(self):
        self.h2_until_consumed()
        retargets = self.lost_target_checks(lost_before_hold=True)
        with self.assertRaises(NotInCombatException):
            self.char.handle_heavy(2)
        self.assertEqual(len(retargets), 1)
        self.assertEqual(self.char.task.down_at, [])
        self.assertFalse(self.char.skip_combat_check())

    def test_reappearing_prompt_after_consumption_retries_e(self):
        char = self.char
        self.finishing()
        keys = []
        # The first key is swallowed; a visual gap lasts longer than the settle time.
        char.enhanced_e_ready = lambda: (self.clock.now < 100.1
                                        or (self.clock.now >= 100.8 and len(keys) < 2))
        char.send_resonance_key = lambda **kwargs: keys.append(self.clock.now)
        char.task.features = lambda: ({Labels.hsin_h2}
                                     if len(keys) == 2 and self.clock.now - keys[-1] >= 0.5
                                     and (char.task.mouse_start is None
                                          or self.clock.now - char.task.mouse_start < 0.4) else set())
        char.perform_everything()
        self.assertEqual(len(keys), 2)
        self.assertGreaterEqual(keys[1], 100.8)
        self.assertTrue(char.h2_completed and char.lib2_cast_this_turn)

    def test_delayed_enhanced_e_cannot_be_locked_by_ordinary_availability(self):
        char = self.char
        self.finishing()
        char.resonance_available = lambda: True
        keys = []
        char.enhanced_e_ready = lambda: self.clock.now >= 102 and not keys
        char.send_resonance_key = lambda **kwargs: keys.append(self.clock.now)
        char.task.features = lambda: ({Labels.hsin_h2}
                                     if keys and self.clock.now - keys[0] >= 1
                                     and (char.task.mouse_start is None
                                          or self.clock.now - char.task.mouse_start < 0.4) else set())
        char.perform_everything()
        self.assertEqual(len(keys), 1)
        self.assertGreaterEqual(keys[0], 102)
        self.assertTrue(char.finisher_e_sent and char.lib2_cast_this_turn)
        self.assertGreater(char.normals, 0)

    def test_swallowed_e_retries_only_while_prompt_is_present(self):
        char = self.char
        keys = []
        char.send_resonance_key = lambda **kwargs: keys.append(self.clock.now)
        char.enhanced_e_ready = lambda: len(keys) < 2
        self.assertTrue(char.cast_enhanced_e())
        self.assertEqual(len(keys), 2)
        self.assertGreaterEqual(keys[1] - keys[0], 0.25)
        self.assertTrue(char.finisher_e_sent)

    def test_brief_prompt_disappearance_does_not_confirm_consumption(self):
        char = self.char
        keys = []
        char.enhanced_e_ready = lambda: not 100.09 < self.clock.now < 100.19 and self.clock.now < 100.6
        def send(**kwargs):
            self.assertTrue(char.enhanced_e_ready())
            keys.append(self.clock.now)
        char.send_resonance_key = send
        self.assertTrue(char.cast_enhanced_e())
        self.assertGreaterEqual(self.clock.now, 100.85)
        self.assertTrue(all(stamp < 100.6 for stamp in keys))

    def test_absent_prompt_does_not_send_or_confirm_e(self):
        char = self.char
        self.assertFalse(char.cast_enhanced_e())
        self.assertFalse(char.finisher_e_sent)
        self.assertEqual(char.resonances, 0)

    def test_no_prompt_uses_normals_and_exits_without_ordinary_e(self):
        char = self.char
        self.finishing()
        char.resonance_available = lambda: True
        char.perform_everything()
        self.assertEqual(char.resonances, 0)
        self.assertGreater(char.normals, 0)
        self.assertFalse(char.finisher_e_sent)
        self.assertTrue(118 <= self.clock.now < 118.2)

    def test_ordinary_e_is_retained_before_r1(self):
        self.char.e_ready = True
        self.char.perform_everything()
        self.assertEqual(self.char.resonances, 1)
        self.assertFalse(self.char.finisher_e_sent)

    def test_persistent_e_failure_is_bounded_and_not_success(self):
        self.char.e_ready = True
        self.assertFalse(self.char.cast_enhanced_e())
        self.assertFalse(self.char.finisher_e_sent)
        self.assertGreater(self.char.resonances, 1)
        self.assertTrue(101.5 <= self.clock.now < 101.7)

    def test_h2_is_prioritized_after_e_consumption(self):
        self.finishing()
        self.char.finisher_e_sent = True
        self.char.e_ready = True
        self.h2_until_consumed()
        self.char.perform_everything()
        self.assertTrue(self.char.lib2_cast_this_turn)
        self.assertEqual(self.char.resonances, 0)

    def test_delayed_generic_r2_survives_first_probe(self):
        char = self.char
        self.finishing()
        char.finisher_e_sent = True
        self.h2_until_consumed()
        char.liberation_available = lambda check_color=True: (char.task.mouse_start is not None
                                                             and self.clock.now - char.task.mouse_start >= 3)
        char.perform_everything()
        self.assertEqual([stage for stage, _ in char.casts], [2])
        self.assertGreaterEqual(char.casts[0][1] - char.task.down_at[0], 3)
        self.assertEqual(char.resonances, 0)
        self.assertEqual(char.echoes, 0)

    def test_unavailable_r2_after_h2_never_returns_to_e_or_q(self):
        char = self.char
        self.finishing()
        char.finisher_e_sent = True
        char.e_ready = True
        self.h2_until_consumed()
        char.liberation_available = lambda check_color=True: False
        char.perform_everything()
        self.assertTrue(char.h2_completed)
        self.assertFalse(char.lib2_cast_this_turn)
        self.assertEqual(char.resonances, 0)
        self.assertEqual(char.echoes, 0)
        self.assertTrue(118 <= self.clock.now < 118.2)

    def test_heavy_transient_loss_requires_stable_disappearance(self):
        char = self.char
        char.task.features = lambda: ({Labels.hsin_h1}
                                     if self.clock.now < 100.4 and not 100.09 < self.clock.now < 100.14 else set())
        self.assertTrue(char.heavy_wait_highlight_down(1.2))
        self.assertGreaterEqual(char.task.up_at[0], 100.65)
        self.assertFalse(char.task.pressed)

    def test_heavy_timeout_is_failure_and_releases_mouse(self):
        self.char.task.features = lambda: {Labels.hsin_h2}
        self.assertFalse(self.char.handle_heavy())
        self.assertFalse(self.char.h2_completed)
        self.assertFalse(self.char.task.pressed)
        self.assertFalse(self.char.skip_combat_check())
        self.assertEqual(len(self.char.task.up_at), 1)

    def test_combat_exception_releases_mouse(self):
        self.char.task.features = lambda: {Labels.hsin_h2}
        self.char.task.fail_frame = True
        with self.assertRaisesRegex(RuntimeError, 'combat ended'):
            self.char.handle_heavy()
        self.assertFalse(self.char.task.pressed)
        self.assertFalse(self.char.skip_combat_check())

    def test_late_heavy_keeps_full_hold_window(self):
        self.char.task.features = lambda: {Labels.hsin_h1} if self.clock.now >= 105.8 else set()
        self.char.perform_everything()
        self.assertEqual(len(self.char.task.down_at), 1)
        self.assertGreaterEqual(self.char.task.up_at[0] - self.char.task.down_at[0], 1.2)

    def test_opening_budgets_are_six_or_twelve_seconds(self):
        for intro, duration in ((False, 6), (True, 12)):
            with self.subTest(intro=intro):
                char = _Hsin(self.clock)
                char.has_intro = intro
                start = self.clock.now
                char.perform_everything()
                self.assertTrue(duration <= self.clock.now - start < duration + 0.2)

    def test_r1_near_deadline_starts_finishing_budget_once(self):
        char = self.char
        def features():
            if char.finisher_start is None:
                return {Labels.hsin_lib1} if self.clock.now >= 105.7 else set()
            if self.clock.now - char.finisher_start < 10:
                return set()
            if char.task.mouse_start is None or self.clock.now - char.task.mouse_start < 0.4:
                return {Labels.hsin_h2}
            return set()
        char.task.features = features
        char.perform_everything()
        self.assertEqual([stage for stage, _ in char.casts], [1, 2])
        assert char.finisher_start is not None
        self.assertGreaterEqual(char.casts[1][1] - char.finisher_start, 10)

    def test_failed_r1_and_r2_cannot_mark_success(self):
        char = self.char
        char.lib_success = False
        char.task.features = lambda: {Labels.hsin_lib1}
        self.assertFalse(char.lib())
        self.assertIsNone(char.finisher_start)
        char.task.features = lambda: {Labels.hsin_lib2}
        self.assertFalse(char.lib())
        self.assertFalse(char.lib2_cast_this_turn)

    def test_r1_budget_is_not_restarted(self):
        self.char.task.features = lambda: {Labels.hsin_lib1}
        self.assertTrue(self.char.lib())
        start = self.char.finisher_start
        self.assertTrue(self.char.lib())
        self.assertEqual(self.char.finisher_start, start)

    def test_ready_r2_takes_priority_over_e_and_heavy(self):
        char = self.char
        char.e_ready = True
        char.task.features = lambda: {Labels.hsin_lib2, Labels.hsin_h2}
        char.perform_everything()
        self.assertTrue(char.lib2_cast_this_turn)
        self.assertEqual(char.resonances, 0)
        self.assertEqual(char.task.down_at, [])

    def test_visible_but_unavailable_r2_does_not_starve_opening_attacks(self):
        char = self.char
        char.e_ready = True
        char.task.features = lambda: {Labels.hsin_lib2}
        char.liberation_available = lambda check_color=True: False
        char.perform_everything()
        self.assertEqual(char.resonances, 1)
        self.assertGreater(char.normals, 0)

    def test_generic_r2_fallback_requires_confirmed_heavy(self):
        self.assertFalse(self.char.lib())
        self.assertEqual(self.char.casts, [])

    def test_real_liberation_helper_requires_animation(self):
        for animation in (True, False):
            with self.subTest(animation=animation):
                char = _Hsin(self.clock)
                char.task.use_liberation = True
                sent = []
                char.send_liberation_key = lambda *args, **kwargs: sent.append(self.clock.now)
                char.liberation_available = lambda check_color=True: not sent
                char.task.in_team = lambda: (not (animation and sent and self.clock.now - sent[0] < 0.6), None)
                char.record_liberation_use = lambda: None
                char.add_freeze_duration = lambda start, duration=-1, freeze_time=0.1: char.freeze.append((start, duration))
                char.click_liberation = lambda **kwargs: BaseChar.click_liberation(char, **kwargs)
                self.assertEqual(char.wait_for_lib2(after_heavy=True), animation)
                self.assertEqual(char.lib2_cast_this_turn, animation)
                self.assertEqual(len(sent), 1)

    def test_new_turn_resets_all_finishing_state(self):
        char = self.char
        self.finishing()
        char.lib2_cast_this_turn = char.finisher_e_sent = char.h2_completed = True
        self.h2_until_consumed()
        self.assertTrue(char.handle_heavy(2))
        self.assertTrue(char.skip_combat_check())
        switched = []
        char.switch_next_char = lambda *args, **kwargs: switched.append(self.clock.now)
        char.do_perform()
        self.assertIsNone(char.finisher_start)
        self.assertFalse(char.lib2_cast_this_turn or char.finisher_e_sent or char.h2_completed)
        self.assertFalse(char.skip_combat_check())
        self.assertEqual(len(switched), 1)


class HsinEnhancedTemplateTest(unittest.TestCase):
    @staticmethod
    def detector_task(frame):
        feature_set = FeatureSet(False, 'assets/coco_annotations.json', 0.002, 0.002,
                                 0.8, process_feature, hcenter_features=['e_forte'])
        return SimpleNamespace(
            frame=frame,
            find_e_forte=lambda: feature_set.find_one_feature(
                frame, 'e_forte', horizontal_variance=0.025, threshold=0.6,
                frame_processor=lambda image: binarize_for_matching(image, 220)))

    def test_existing_prompt_controls_readiness_without_marking_cast_success(self):
        frame = cv2.imread('assets/images/31.png')
        self.assertIsNotNone(frame)
        task = self.detector_task(frame)
        self.assertTrue(task.find_e_forte())
        char = Hsin(task, 0)
        self.assertTrue(char.enhanced_e_ready())
        self.assertFalse(char.finisher_e_sent)

    def test_black_and_broad_gold_background_have_no_prompt(self):
        for color in ((0, 0, 0), (80, 190, 220)):
            frame = np.full((1080, 1920, 3), color, np.uint8)
            self.assertFalse(Hsin(self.detector_task(frame), 0).enhanced_e_ready())


if __name__ == '__main__':
    unittest.main()
