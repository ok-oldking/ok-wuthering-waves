import time
import unittest
from config import config
from ok.test.TaskTestCase import TaskTestCase
from src.Labels import Labels
from src.char.BaseChar import BaseChar, CharType, get_default_buff_time
from src.char.CharFactory import _get_buff_time, _get_char_type, char_dict
from src.task.AutoCombatTask import AutoCombatTask

config['debug'] = True


def return_true():
    return True


class TestChar(TaskTestCase):
    task_class = AutoCombatTask
    config = config

    def test_char_type_config(self):
        class Task:
            char_config = {}

        task = Task()
        self.assertEqual(BaseChar(None, 0).char_type, CharType.MAIN_DPS)
        self.assertEqual(BaseChar(None, 0).buff_time, 0)
        self.assertEqual(BaseChar(None, 0, char_type=CharType.HEALER).buff_time,
                         get_default_buff_time(CharType.HEALER))
        self.assertEqual(BaseChar(None, 0, char_type=CharType.SUB_DPS, buff_time=11).buff_time, 11)
        self.assertEqual(char_dict[Labels.char_mortefi]['char_type'], CharType.SUB_DPS)
        self.assertEqual(char_dict[Labels.char_mortefi]['buff_time'], get_default_buff_time(CharType.SUB_DPS))
        self.assertEqual(_get_char_type(task, char_dict[Labels.char_iuno]), CharType.SUB_DPS)
        self.assertEqual(_get_buff_time(task, char_dict[Labels.char_iuno]), get_default_buff_time(CharType.SUB_DPS))
        self.assertEqual(_get_buff_time(task, dict(char_dict[Labels.char_mortefi], buff_time=12)), 12)

        task.char_config = {'Iuno C6': True}
        self.assertEqual(_get_char_type(task, char_dict[Labels.char_iuno]), CharType.MAIN_DPS)
        self.assertEqual(_get_buff_time(task, char_dict[Labels.char_iuno]), 0)

    def test_switch_priority_rules(self):
        class Task:
            def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
                if start < 0:
                    return 10000
                return time.time() - start

        task = Task()
        combat = AutoCombatTask.__new__(AutoCombatTask)
        current = BaseChar(task, 0, char_type=CharType.MAIN_DPS)
        healer = BaseChar(task, 1, char_type=CharType.HEALER)
        sub_dps = BaseChar(task, 2, char_type=CharType.SUB_DPS)
        main_dps = BaseChar(task, 3, char_type=CharType.MAIN_DPS)
        combat.chars = [current, healer, sub_dps, main_dps]

        self.assertEqual(combat._choose_switch_target(current, False), healer)

        healer.last_buff_time = time.time()
        self.assertEqual(combat._choose_switch_target(current, False), sub_dps)

        sub_dps.last_buff_time = time.time()
        self.assertEqual(combat._choose_switch_target(current, False), main_dps)

        combat.chars = [current, healer, sub_dps]
        healer.last_switch_in_time = 1
        sub_dps.last_switch_in_time = 2
        self.assertEqual(combat._choose_switch_target(current, False), sub_dps)

        combat.chars = [current, healer, sub_dps, main_dps]
        current.set_char_type(CharType.SUB_DPS)
        self.assertEqual(combat._choose_switch_target(current, False), main_dps)
        self.assertEqual(combat._choose_switch_target(current, True), main_dps)

        current.last_perform = time.time()
        healer.last_buff_time = -1
        self.assertEqual(combat._choose_switch_target(current, False), healer)
        current.last_perform = 0

        current.set_char_type(CharType.HEALER)
        self.assertEqual(combat._choose_switch_target(current, False), main_dps)

        current.last_perform = time.time()
        healer.last_buff_time = time.time()
        sub_dps.last_buff_time = -1
        self.assertEqual(combat._choose_switch_target(current, False), sub_dps)
        current.last_perform = 0

        current.last_perform = time.time()
        self.assertTrue(current.need_fast_perform())
        current.last_perform = 0
        self.assertFalse(current.need_fast_perform())

        current.set_char_type(CharType.MAIN_DPS)
        healer.last_buff_time = -1
        self.assertEqual(combat._choose_switch_target(current, True), healer)

        healer.last_buff_time = time.time()
        sub_dps.last_buff_time = -1
        self.assertEqual(combat._choose_switch_target(current, True), sub_dps)

        combat._apply_intro_flags(sub_dps, current, True)
        self.assertTrue(current.has_intro)
        self.assertTrue(current.has_sub_dps_intro)

        combat._apply_intro_flags(healer, current, True)
        self.assertTrue(current.has_intro)
        self.assertFalse(current.has_sub_dps_intro)

    def test_aemeath_lib(self):
        self.task.do_reset_to_false()
        self.set_image('tests/images/aemeath_lib.png')
        in_combat = self.task.in_combat()
        self.assertTrue(in_combat)
        liberation_available = self.task.available('liberation')
        self.assertTrue(liberation_available)

    def test_switch_cd(self):
        self.task.do_reset_to_false()
        self.set_image('tests/images/combat_has_cd.png')
        self.task.load_chars()
        self.assertTrue(len(self.task.chars) > 0)
        self.assertEqual(self.task.chars[0].name, 'Aemeath')

        self.set_image('ok_templates/char_iuno.png')
        self.task.load_chars()
        self.assertTrue(len(self.task.chars) > 0)
        self.assertEqual(self.task.chars[0].name, 'Iuno')

    def test_luhesi_cd(self):
        self.task.do_reset_to_false()
        self.set_image('tests/images/luhesi_lib_in_cd.png')
        self.task.load_chars()
        self.assertTrue(len(self.task.chars) > 0)
        self.assertEqual(self.task.chars[0].name, 'Luhesi')

        has_cd = self.task.chars[0].has_cd('liberation')
        time.sleep(1)
        self.task.screenshot('click_liberation', show_box=True)
        self.assertTrue(has_cd)


if __name__ == '__main__':
    unittest.main()
