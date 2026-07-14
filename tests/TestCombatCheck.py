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

    def test_in_combat_cloud(self):
        self.task.ensure_levitator = return_true
        self.task.do_reset_to_false()
        self.task.is_browser = return_true
        self.set_image('tests/images/cloud_game_combat.png')
        in_combat = self.task.in_combat()
        self.assertTrue(in_combat)

    def test_in_combat_cloud2(self):
        self.task.ensure_levitator = return_true
        self.task.do_reset_to_false()
        self.task.is_browser = return_true
        self.set_image('ok_templates/browser_in_combat.png')
        in_combat = self.task.in_combat()
        self.assertTrue(in_combat)

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


if __name__ == '__main__':
    unittest.main()
