import time
import unittest

import numpy as np

from src.char.BaseChar import BaseChar, CharType
from src.task.AutoCombatTask import AutoCombatTask
from src.task.BaseCombatTask import CharDeadException


class TestDeathRecovery(unittest.TestCase):

    @staticmethod
    def _make_chars():
        class Task:
            @staticmethod
            def time_elapsed_accounting_for_freeze(start, intro_motion_freeze=False):
                if start < 0:
                    return 10000
                return time.time() - start

        task = Task()
        return (
            BaseChar(task, 0, char_type=CharType.MAIN_DPS),
            BaseChar(task, 1, char_type=CharType.HEALER),
            BaseChar(task, 2, char_type=CharType.SUB_DPS),
        )

    def test_portrait_liveness_distinguishes_gray_and_color(self):
        class Combat(AutoCombatTask):
            @property
            def frame(self):
                return self.test_frame

        class Box:
            def __init__(self, frame):
                self.frame = frame

            def crop_frame(self, _frame):
                return self.frame

        combat = Combat.__new__(Combat)
        combat.test_frame = np.zeros((20, 20, 3), dtype=np.uint8)
        char = BaseChar(None, 0, char_type=CharType.MAIN_DPS)

        gray = np.full((20, 20, 3), 120, dtype=np.uint8)
        combat.get_box_by_name = lambda *_: Box(gray)
        self.assertEqual(combat._char_portrait_liveness(char), (True, False))

        color = np.zeros((20, 20, 3), dtype=np.uint8)
        color[:, :, 2] = 180
        combat.get_box_by_name = lambda *_: Box(color)
        self.assertEqual(combat._char_portrait_liveness(char), (False, True))

    def test_alive_state_requires_two_consecutive_votes(self):
        class Combat(AutoCombatTask):
            @property
            def frame(self):
                return self.test_frame

        combat = Combat.__new__(Combat)
        current, target, _ = self._make_chars()
        combat.test_frame = np.zeros((1, 1, 3), dtype=np.uint8)
        combat.chars = [current, target]
        combat.reset_char_alive_states()
        combat.char_alive_check_interval = 0
        combat.in_team = lambda: (True, current.index, 2)
        combat._char_portrait_liveness = lambda char: (True, False)

        combat.update_char_alive_states()
        self.assertTrue(combat.is_char_alive(target))
        combat.update_char_alive_states()
        self.assertFalse(combat.is_char_alive(target))

        combat._char_portrait_liveness = lambda char: (False, True)
        combat.update_char_alive_states()
        self.assertFalse(combat.is_char_alive(target))
        combat.update_char_alive_states()
        self.assertTrue(combat.is_char_alive(target))

    def test_switch_target_skips_dead_char_and_allows_recovered_char(self):
        current, healer, sub_dps = self._make_chars()
        combat = AutoCombatTask.__new__(AutoCombatTask)
        combat.chars = [current, healer, sub_dps]
        combat.char_alive_state = [True, False, True]
        combat.char_dead_votes = [0, 0, 0]
        combat.char_alive_votes = [0, 0, 0]

        self.assertEqual(combat._choose_switch_target(current, False), sub_dps)

        combat.set_char_alive(healer, True)
        self.assertEqual(combat._choose_switch_target(current, False), healer)

    def test_close_revive_prompt_waits_and_confirms_closed(self):
        combat = AutoCombatTask.__new__(AutoCombatTask)
        state = {'visible': True}
        observed_timeouts = []

        def wait_feature(*args, **kwargs):
            observed_timeouts.append(kwargs['time_out'])
            return state['visible']

        def send_key(key, **kwargs):
            self.assertEqual(key, 'esc')
            state['visible'] = False

        combat.wait_feature = wait_feature
        combat.send_key = send_key
        combat.find_one = lambda *args, **kwargs: state['visible']
        combat.wait_until = lambda condition, **kwargs: condition()

        self.assertTrue(combat.close_revive_prompt())
        self.assertEqual(observed_timeouts, [1.0])
        self.assertFalse(state['visible'])

    def test_dead_character_switch_retries_dropped_key(self):
        class Scene:
            def __init__(self):
                self.in_combat = False

            def set_in_combat(self):
                self.in_combat = True

        current, target, _ = self._make_chars()
        combat = AutoCombatTask.__new__(AutoCombatTask)
        combat.chars = [current, target]
        combat.char_alive_state = [True, True]
        combat.char_dead_votes = [0, 0]
        combat.char_alive_votes = [0, 0]
        combat.scene = Scene()
        combat.has_alive_switch_target = lambda *_: True
        combat.close_revive_prompt = lambda *args, **kwargs: True
        combat._choose_switch_target = lambda *args, **kwargs: target
        combat.wait_feature = lambda *args, **kwargs: False
        state = {'current_index': current.index, 'keys': 0}

        def send_key(key, **kwargs):
            self.assertEqual(key, target.index + 1)
            state['keys'] += 1
            if state['keys'] >= 2:
                state['current_index'] = target.index

        def wait_until(condition, post_action=None, **kwargs):
            for _ in range(3):
                if condition():
                    return True
                post_action()
            return condition()

        combat.send_key = send_key
        combat.in_team = lambda: (True, state['current_index'], 2)
        combat.wait_until = wait_until

        self.assertTrue(combat.try_continue_after_char_dead(current))
        self.assertEqual(state['keys'], 2)
        self.assertTrue(target.is_current_char)
        self.assertTrue(combat.scene.in_combat)

    def test_dead_character_switch_skips_another_dead_target(self):
        class Scene:
            @staticmethod
            def set_in_combat():
                pass

        current, dead_target, live_target = self._make_chars()
        combat = AutoCombatTask.__new__(AutoCombatTask)
        combat.chars = [current, dead_target, live_target]
        combat.char_alive_state = [True, True, True]
        combat.char_dead_votes = [0, 0, 0]
        combat.char_alive_votes = [0, 0, 0]
        combat.scene = Scene()
        combat.has_alive_switch_target = lambda *_: True
        combat.log_info = lambda *args, **kwargs: None
        state = {'current_index': current.index, 'prompt': False}

        def choose_target(*args, excluded_indices=None, **kwargs):
            excluded_indices = excluded_indices or set()
            if dead_target.index not in excluded_indices:
                return dead_target
            if live_target.index not in excluded_indices:
                return live_target
            return current

        def send_key(key, **kwargs):
            if key == dead_target.index + 1:
                state['prompt'] = True
            elif key == live_target.index + 1:
                state['current_index'] = live_target.index

        def wait_until(condition, post_action=None, **kwargs):
            if condition():
                return True
            post_action()
            return condition()

        combat._choose_switch_target = choose_target
        combat.send_key = send_key
        combat.in_team = lambda: (True, state['current_index'], 3)
        combat.wait_until = wait_until
        combat.wait_feature = lambda *args, **kwargs: state['prompt']
        combat.close_revive_prompt = lambda *args, **kwargs: state.update(prompt=False) or True

        self.assertTrue(combat.try_continue_after_char_dead(current))
        self.assertFalse(combat.char_alive_state[dead_target.index])
        self.assertTrue(live_target.is_current_char)

    def test_regular_switch_reselects_after_dead_target_popup(self):
        current, dead_target, live_target = self._make_chars()
        combat = AutoCombatTask.__new__(AutoCombatTask)
        combat.chars = [current, dead_target, live_target]
        combat.char_alive_state = [True, True, True]
        combat.char_dead_votes = [0, 0, 0]
        combat.char_alive_votes = [0, 0, 0]
        combat.close_revive_prompt = lambda: True
        combat.log_info = lambda *args, **kwargs: None

        selected = combat.handle_dead_switch_target(current, dead_target, has_intro=False)

        self.assertEqual(selected, live_target)
        self.assertFalse(combat.is_char_alive(dead_target))

    def test_all_dead_revive_clicks_button_and_resets_states(self):
        class Scene:
            def __init__(self):
                self.not_in_combat = False

            def set_not_in_combat(self):
                self.not_in_combat = True

        combat = AutoCombatTask.__new__(AutoCombatTask)
        combat.scene = Scene()
        combat.char_alive_state = [False, False, False]
        combat.char_dead_votes = [2, 2, 2]
        combat.char_alive_votes = [0, 0, 0]
        combat.clicks = []
        combat.info = []
        combat.wait_feature = lambda *args, **kwargs: True
        combat.in_team_and_world = lambda: False
        combat.click = lambda x, y, **kwargs: combat.clicks.append((x, y))
        combat.wait_in_team_and_world = lambda **kwargs: True
        combat.log_info = lambda *args, **kwargs: None
        combat.info_set = lambda key, value: combat.info.append((key, value))

        self.assertTrue(combat.revive_all_dead_characters())
        self.assertEqual(combat.clicks, [combat.team_revive_button])
        self.assertEqual(combat.char_alive_state, [True, True, True])
        self.assertTrue(combat.scene.not_in_combat)
        self.assertIn(('Revive', 'Success'), combat.info)

    def test_auto_combat_revives_after_last_character_dies(self):
        class Scene:
            @staticmethod
            def in_team(check):
                return True

        class CurrentChar:
            @staticmethod
            def perform():
                raise CharDeadException('dead')

        combat = AutoCombatTask.__new__(AutoCombatTask)
        combat.scene = Scene()
        combat.config = {'Use Liberation': True}
        combat.warm_up_char_features = lambda: None
        combat.in_world = lambda: True
        combat.in_combat = lambda: True
        combat.in_team_and_world = lambda: True
        combat.get_current_char = lambda: CurrentChar()
        combat.try_continue_after_char_dead = lambda current: False
        combat.revive_calls = 0

        def revive():
            combat.revive_calls += 1
            return True

        combat.revive_all_dead_characters = revive
        combat.log_info = lambda *args, **kwargs: None
        combat.log_error = lambda *args, **kwargs: None
        combat.combat_end_calls = 0
        combat.combat_end = lambda: setattr(combat, 'combat_end_calls', combat.combat_end_calls + 1)

        self.assertTrue(combat.run())
        self.assertEqual(combat.revive_calls, 1)
        self.assertEqual(combat.combat_end_calls, 0)


if __name__ == '__main__':
    unittest.main()
