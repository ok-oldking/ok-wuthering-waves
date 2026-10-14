import time
import unittest
from config import config
from ok.test.TaskTestCase import TaskTestCase
from src.char.BaseChar import BaseChar
from src.Labels import Labels
from src.char.CharFactory import get_char_by_pos
from src.task.AutoCombatTask import AutoCombatTask

config['debug'] = True


def return_true():
    return True


class TestCombatCheck(TaskTestCase):
    task_class = AutoCombatTask
    config = config

    def test_in_combat_check(self):
        self.task.ensure_levitator = return_true
        self.task.do_reset_to_false()
        self.set_image('tests/images/in_combat.png')
        in_combat = self.task.in_combat()
        # self.task.screenshot('in_combat.png', show_box=True)
        # time.sleep(1)
        self.assertTrue(in_combat)

    def test_4k_combat_check(self):
        self.task.ensure_levitator = return_true
        self.task.do_reset_to_false()
        self.set_image("ok_templates/57d8d801-BitBlt_True_3840x2160_1759986393607.1733_original.png")
        in_combat = self.task.in_combat()
        # self.task.screenshot('in_combat4k.png', show_box=True)
        # time.sleep(1)
        self.assertTrue(in_combat)

    def test_not_in_combat_check(self):
        self.task.ensure_levitator = return_true
        self.task.do_reset_to_false()
        self.set_image('tests/images/in_combat3.png')
        in_combat = self.task.in_combat()
        self.assertFalse(in_combat)

    def test_target_box_short(self):
        self.set_image('ok_templates/25.png')
        self.task.chars = [BaseChar(self.task, 0)]
        self.task.chars[0].is_current_char = True
        self.assertFalse(self.task.has_target())

        self.task.chars[0].target_box_short_combat_check = True
        self.assertTrue(self.task.has_target())
        self.assertTrue(BaseChar(self.task, 0).has_short_action())

    def test_lucilla_enables_target_box_short_combat_check_from_char_factory(self):
        class Box:
            def __init__(self, name):
                self.name = name

        class Match:
            def __init__(self, name):
                self.name = name
                self.confidence = 0.95

        class Task:
            char_config = {}

            def find_one(self, name, box=None, threshold=0.6):
                return Match(name) if name == Labels.char_lucilla else None

            def find_best_match_in_box(self, box, names, threshold=0.6):
                return Match(Labels.char_lucilla)

            def log_info(self, *args, **kwargs):
                pass

        lucilla = get_char_by_pos(Task(), Box('box_char_1'), 0, None)

        self.assertTrue(lucilla.target_box_short_combat_check)

    def test_enter_combat_loads_chars_before_target_check(self):
        task = AutoCombatTask.__new__(AutoCombatTask)
        task._in_combat = False
        task.in_liberation = False
        task.chars = [None, None, None]
        task.config = {'Auto Target': True}
        task.target_enemy_error_notified = False
        task.find_one = lambda *args, **kwargs: False
        task.log_info = lambda *args, **kwargs: None
        order = []

        class Char:
            is_current_char = True

        def load_chars():
            order.append('load_chars')
            task.chars = [Char()]
            return True

        def has_target():
            order.append(('has_target', task.get_current_char() is not None))
            return True

        task.load_chars = load_chars
        task.has_target = has_target

        self.assertTrue(task.do_check_in_combat(False))
        self.assertEqual(order, ['load_chars', ('has_target', True)])

    def test_in_combat_retarget_with_health_bar_extends_timeout(self):
        task = AutoCombatTask.__new__(AutoCombatTask)
        task._in_combat = True
        task.in_liberation = False
        task.scene = type('Scene', (), {'in_combat': lambda *args, **kwargs: None, 'set_in_combat': lambda *args, **kwargs: True})()
        task.check_f_break = lambda: None
        task.get_current_char = lambda: None
        task.on_combat_check = lambda: True
        task.has_target = lambda: False
        task.combat_end_condition = None
        task.check_health_bar = lambda: True
        task.target_enemy_time_out = 3

        calls = []
        task.target_enemy = lambda wait, time_out, check_health: calls.append((wait, time_out, check_health)) or True

        result = task.do_check_in_combat(False)
        self.assertTrue(result)
        self.assertEqual(calls, [(True, 30, True)])

    def test_in_combat_retarget_without_health_bar_uses_default_timeout(self):
        task = AutoCombatTask.__new__(AutoCombatTask)
        task._in_combat = True
        task.in_liberation = False
        task.scene = type('Scene', (), {'in_combat': lambda *args, **kwargs: None, 'set_in_combat': lambda *args, **kwargs: True})()
        task.check_f_break = lambda: None
        task.get_current_char = lambda: None
        task.on_combat_check = lambda: True
        task.has_target = lambda: False
        task.combat_end_condition = None
        task.check_health_bar = lambda: False
        task.target_enemy_time_out = 3
        task.should_check_monthly_card = lambda: False
        task.reset_to_false = lambda reason: False

        calls = []
        task.target_enemy = lambda wait, time_out, check_health: calls.append((wait, time_out, check_health)) or False

        result = task.do_check_in_combat(False)
        self.assertFalse(result)
        self.assertEqual(calls, [(True, 3, False)])

    def test_target_enemy_breaks_early_when_health_bar_disappears(self):
        task = AutoCombatTask.__new__(AutoCombatTask)
        task.has_target = lambda: False
        task.middle_click = lambda **kwargs: None
        task.next_frame = lambda: None
        task.combat_end_condition = None
        task.target_enemy_time_out = 30
        task.check_health_bar = lambda: False

        start = time.time()
        result = task.target_enemy(wait=True, time_out=30, check_health=True)
        elapsed = time.time() - start

        self.assertFalse(result)
        self.assertLess(elapsed, 3.0)


if __name__ == '__main__':
    unittest.main()
