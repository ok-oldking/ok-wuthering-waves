import time
import unittest
from config import config
from ok.test.TaskTestCase import TaskTestCase
from src.Labels import Labels
from src.char.BaseChar import BaseChar, CharType, get_default_buff_time
from src.char.CharFactory import _get_buff_time, _get_char_type, char_dict
from src.char.Aemeath import Aemeath
from src.char.Chisa import Chisa
from src.char.Ciaccona import Ciaccona
from src.char.Phrolova import Phrolova
from src.task.AutoCombatTask import AutoCombatTask

config['debug'] = True


def return_true():
    return True


class BlockedChar(BaseChar):
    def can_switch(self, current_char=None, has_intro=False, target_low_con=False):
        return False


class ForcedChar(BaseChar):
    def must_switch(self, current_char=None, has_intro=False, target_low_con=False):
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
        self.assertEqual(char_dict[Labels.char_chisa]['buff_time'], 12)
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
        healer.last_buff_time = time.time() - 10
        self.assertEqual(combat._choose_switch_target(current, False), healer)

        combat.chars = [current, healer, sub_dps]
        healer.last_switch_in_time = 1
        sub_dps.last_switch_in_time = 2
        healer.last_buff_time = -1
        self.assertEqual(combat._choose_switch_target(current, False), healer)

        combat.chars = [current, healer, sub_dps, main_dps]
        current.set_char_type(CharType.SUB_DPS)
        self.assertEqual(combat._choose_switch_target(current, False), healer)
        self.assertEqual(combat._choose_switch_target(current, True), main_dps)

        current.last_perform = time.time()
        healer.last_buff_time = -1
        self.assertEqual(combat._choose_switch_target(current, False), healer)
        current.last_perform = 0

        current.set_char_type(CharType.HEALER)
        self.assertEqual(combat._choose_switch_target(current, False), healer)

        current.last_perform = time.time()
        healer.last_buff_time = time.time()
        sub_dps.last_buff_time = -1
        self.assertEqual(combat._choose_switch_target(current, False), sub_dps)
        self.assertEqual(combat._choose_switch_target(current, True), main_dps)
        current.last_perform = 0

        current.last_perform = time.time()
        self.assertTrue(current.need_fast_perform())
        current.last_perform = 0
        self.assertFalse(current.need_fast_perform())

        current.set_char_type(CharType.MAIN_DPS)
        healer.last_buff_time = -1
        self.assertEqual(combat._choose_switch_target(current, True), main_dps)

        healer.last_buff_time = time.time()
        sub_dps.last_buff_time = -1
        self.assertEqual(combat._choose_switch_target(current, True), main_dps)

        combat.chars = [current, healer, sub_dps]
        self.assertEqual(combat._choose_switch_target(current, True), sub_dps)
        combat.chars = [current, healer, sub_dps, main_dps]

        combat._apply_intro_flags(sub_dps, current, True)
        self.assertTrue(current.has_intro)
        self.assertTrue(current.has_sub_dps_intro)

        combat._apply_intro_flags(healer, current, True)
        self.assertTrue(current.has_intro)
        self.assertFalse(current.has_sub_dps_intro)

    def test_chisa_support_intro_records_buff_and_switches_immediately(self):
        class Task:
            char_config = {'Chisa DPS': False}

        class TrackingChisa(Chisa):
            def __init__(self, task):
                super().__init__(task, 0)
                self.actions = []

            def click_echo(self, **kwargs):
                self.actions.append(('echo', kwargs))

            def click_liberation(self):
                self.actions.append(('liberation', {}))
                return True

            def click_resonance(self, **kwargs):
                self.actions.append(('resonance', kwargs))

            def switch_next_char(self):
                self.actions.append(('switch', {}))

        chisa = TrackingChisa(Task())
        chisa.has_intro = True
        chisa.do_perform()

        self.assertGreater(chisa.last_buff_time, 0)
        self.assertEqual(chisa.actions, [('echo', {'time_out': 0}), ('switch', {})])

    def test_chisa_support_liberation_records_buff_without_dps_sequence(self):
        class Task:
            char_config = {'Chisa DPS': False}

        class TrackingChisa(Chisa):
            def __init__(self, task):
                super().__init__(task, 0)
                self.actions = []

            def flying(self):
                return False

            def click_echo(self, **kwargs):
                self.actions.append(('echo', kwargs))

            def click_liberation(self):
                self.actions.append(('liberation', {}))
                return True

            def click_resonance(self, **kwargs):
                self.actions.append(('resonance', kwargs))

            def switch_next_char(self):
                self.actions.append(('switch', {}))

        chisa = TrackingChisa(Task())
        chisa.do_perform()

        self.assertGreater(chisa.last_buff_time, 0)
        self.assertEqual(chisa.actions, [
            ('echo', {'time_out': 0}),
            ('liberation', {}),
            ('switch', {}),
        ])

    def test_chisa_support_outro_does_not_invent_skill_buff(self):
        class Task:
            char_config = {'Chisa DPS': False}

        chisa = Chisa(Task(), 0, char_type=CharType.HEALER, buff_time=12)
        chisa.switch_out(con_full=True)
        self.assertEqual(chisa.last_buff_time, -1)

        chisa.record_support_buff()
        buff_time = chisa.last_buff_time
        chisa.switch_out(con_full=True)
        self.assertEqual(chisa.last_buff_time, buff_time)

    def test_chisa_dps_config_keeps_dps_rotation(self):
        class Task:
            char_config = {'Chisa DPS': True}

        class TrackingChisa(Chisa):
            def __init__(self, task):
                super().__init__(task, 0)
                self.called = False

            def do_dps_perform(self):
                self.called = True

        chisa = TrackingChisa(Task())
        chisa.do_perform()
        self.assertTrue(chisa.called)

    def test_aemeath_heavy_liberation_requires_ten_seconds_and_is_consumed(self):
        class Task:
            def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
                if start < 0:
                    return 10000
                return time.time() - start

        class TrackingAemeath(Aemeath):
            def __init__(self, task):
                super().__init__(task, 0)
                self.liberation_casts = 0
                self.breaks = 0

            def click_liberation(self, **kwargs):
                self.liberation_casts += 1
                return True

            def f_break(self):
                self.breaks += 1

        aemeath = TrackingAemeath(Task())
        aemeath.last_liber = time.time()
        self.assertFalse(aemeath.lib())
        self.assertEqual(aemeath.liberation_casts, 0)

        aemeath.record_heavy_liberation()
        aemeath.heavy_liberation_time = time.time() - 9.9
        self.assertFalse(aemeath.lib())

        aemeath.heavy_liberation_time = time.time() - 10
        self.assertTrue(aemeath.lib())
        self.assertEqual(aemeath.heavy_liberation_time, -1)
        self.assertEqual(aemeath.liberation_casts, 1)
        self.assertEqual(aemeath.breaks, 1)
        self.assertGreater(aemeath.last_liber, 0)
        self.assertFalse(aemeath.lib())
        self.assertEqual(aemeath.liberation_casts, 1)

    def test_aemeath_liberation_casts_without_trigger_after_twenty_seconds(self):
        class Task:
            def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
                if start < 0:
                    return 10000
                return time.time() - start

        class TrackingAemeath(Aemeath):
            def __init__(self, task):
                super().__init__(task, 0)
                self.liberation_casts = 0

            def click_liberation(self, **kwargs):
                self.liberation_casts += 1
                return True

            def f_break(self):
                pass

        aemeath = TrackingAemeath(Task())
        aemeath.last_liber = time.time() - 19.9
        self.assertFalse(aemeath.lib())

        aemeath.last_liber = time.time() - 20
        self.assertTrue(aemeath.lib())
        self.assertEqual(aemeath.liberation_casts, 1)

    def test_aemeath_heavy_state_persists_until_liberation_cast(self):
        class Task:
            def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
                if start < 0:
                    return 10000
                return time.time() - start

        class TrackingAemeath(Aemeath):
            def has_long_action(self):
                return True

            def heavy_wait_highlight_down(self):
                return True

            def click_liberation(self, **kwargs):
                return True

            def f_break(self):
                pass

        aemeath = TrackingAemeath(Task(), 0)
        self.assertTrue(aemeath.handle_heavy())
        self.assertGreater(aemeath.heavy_liberation_time, 0)

        aemeath.switch_out()
        self.assertGreater(aemeath.heavy_liberation_time, 0)

        aemeath.reset_state()
        self.assertGreater(aemeath.heavy_liberation_time, 0)

        aemeath.last_liber = time.time()
        aemeath.heavy_liberation_time = time.time() - 10
        self.assertTrue(aemeath.lib())
        self.assertEqual(aemeath.heavy_liberation_time, -1)

    def test_aemeath_intro_unlocks_after_fifteen_seconds_and_is_not_consumed(self):
        class Task:
            def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
                if start < 0:
                    return 10000
                return time.time() - start

        class TrackingAemeath(Aemeath):
            def __init__(self, task):
                super().__init__(task, 0)
                self.liberation_casts = 0

            def click_liberation(self, **kwargs):
                self.liberation_casts += 1
                return True

            def f_break(self):
                pass

        aemeath = TrackingAemeath(Task())
        aemeath.last_liber = time.time()
        aemeath.record_intro_liberation()
        aemeath.intro_liberation_time = time.time() - 14.9
        self.assertFalse(aemeath.lib())

        aemeath.intro_liberation_time = time.time() - 15
        self.assertTrue(aemeath.lib())
        intro_liberation_time = aemeath.intro_liberation_time
        aemeath.last_liber = time.time()
        self.assertTrue(aemeath.lib())
        self.assertEqual(aemeath.intro_liberation_time, intro_liberation_time)
        self.assertEqual(aemeath.liberation_casts, 2)

    def test_aemeath_intro_records_persistent_liberation_state(self):
        class Task:
            def wait_until(self, *args, **kwargs):
                return False

        class TrackingAemeath(Aemeath):
            def check_outro(self):
                return 'null'

            def perform_everything(self):
                pass

            def switch_next_char(self):
                pass

        aemeath = TrackingAemeath(Task(), 0)
        aemeath.has_intro = True
        aemeath.do_perform()
        intro_liberation_time = aemeath.intro_liberation_time
        self.assertGreater(intro_liberation_time, 0)

        aemeath.reset_state()
        self.assertEqual(aemeath.intro_liberation_time, intro_liberation_time)

    def test_switch_can_and_must_hooks(self):
        class Task:
            def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
                if start < 0:
                    return 10000
                return time.time() - start

        task = Task()
        combat = AutoCombatTask.__new__(AutoCombatTask)
        current = BaseChar(task, 0, char_type=CharType.MAIN_DPS)
        healer = BlockedChar(task, 1, char_type=CharType.HEALER)
        sub_dps = BaseChar(task, 2, char_type=CharType.SUB_DPS)
        forced = ForcedChar(task, 3, char_type=CharType.SUB_DPS)
        combat.chars = [current, healer, sub_dps, forced]

        self.assertTrue(current.can_switch())
        self.assertFalse(current.must_switch())
        self.assertEqual(combat._choose_switch_target(current, False), forced)

        combat.chars = [current, healer, sub_dps]
        self.assertEqual(combat._choose_switch_target(current, False), sub_dps)

        sub_dps = BlockedChar(task, 2, char_type=CharType.SUB_DPS)
        combat.chars = [current, healer, sub_dps]
        self.assertEqual(combat._choose_switch_target(current, False), current)

        main_dps = BaseChar(task, 4, char_type=CharType.MAIN_DPS)
        combat.chars = [current, main_dps, forced]
        self.assertEqual(combat._choose_switch_target(current, True), forced)

        blocked_main_dps = BlockedChar(task, 4, char_type=CharType.MAIN_DPS)
        allowed_sub_dps = BaseChar(task, 2, char_type=CharType.SUB_DPS)
        combat.chars = [current, blocked_main_dps, allowed_sub_dps]
        self.assertEqual(combat._choose_switch_target(current, True), allowed_sub_dps)

    def test_non_main_char_can_chain_to_an_unbuffed_other_buffer(self):
        class Task:
            def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
                if start < 0:
                    return 10000
                return time.time() - start

        task = Task()
        combat = AutoCombatTask.__new__(AutoCombatTask)
        main_dps = BaseChar(task, 0, char_type=CharType.MAIN_DPS)
        healer = BaseChar(task, 1, char_type=CharType.HEALER)
        sub_dps = BaseChar(task, 2, char_type=CharType.SUB_DPS)
        combat.chars = [main_dps, healer, sub_dps]

        self.assertEqual(combat._choose_switch_target(healer, False), sub_dps)
        self.assertEqual(combat._choose_switch_target(healer, True), main_dps)
        self.assertEqual(combat._choose_switch_target(sub_dps, False), healer)
        self.assertEqual(combat._choose_switch_target(sub_dps, True), main_dps)

        healer.last_buff_time = time.time()
        self.assertEqual(combat._choose_switch_target(healer, False), sub_dps)
        self.assertEqual(combat._choose_switch_target(sub_dps, False), main_dps)

    def test_main_dps_prefers_lowest_buff_remaining_eligible_buffer(self):
        class Task:
            def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
                if start < 0:
                    return 10000
                return time.time() - start

        task = Task()
        combat = AutoCombatTask.__new__(AutoCombatTask)
        main_dps = BaseChar(task, 0, char_type=CharType.MAIN_DPS)
        healer = BaseChar(task, 1, char_type=CharType.HEALER)
        sub_dps = BaseChar(task, 2, char_type=CharType.SUB_DPS)
        combat.chars = [main_dps, healer, sub_dps]

        healer.last_buff_time = time.time() - 15
        sub_dps.last_buff_time = time.time() - 1
        self.assertEqual(combat._choose_switch_target(main_dps, False), healer)

        healer.last_buff_time = time.time()
        sub_dps.last_buff_time = -1
        self.assertEqual(combat._choose_switch_target(main_dps, True), sub_dps)

        sub_dps.last_switch_time = time.time()
        self.assertEqual(combat._choose_switch_target(main_dps, False), healer)

    def test_non_main_chain_does_not_target_char_in_switch_cd(self):
        class Task:
            def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
                if start < 0:
                    return 10000
                return time.time() - start

        task = Task()
        combat = AutoCombatTask.__new__(AutoCombatTask)
        main_dps = BaseChar(task, 0, char_type=CharType.MAIN_DPS)
        healer = BaseChar(task, 1, char_type=CharType.HEALER)
        sub_dps = BaseChar(task, 2, char_type=CharType.SUB_DPS)
        combat.chars = [main_dps, healer, sub_dps]

        sub_dps.last_switch_time = time.time()
        self.assertEqual(combat._choose_switch_target(healer, False), main_dps)

    def test_intro_switches_to_main_dps_ignoring_target_switch_cd(self):
        class Task:
            def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
                if start < 0:
                    return 10000
                return time.time() - start

        task = Task()
        combat = AutoCombatTask.__new__(AutoCombatTask)
        healer = BaseChar(task, 0, char_type=CharType.HEALER)
        sub_dps = BaseChar(task, 1, char_type=CharType.SUB_DPS)
        main_dps = BaseChar(task, 2, char_type=CharType.MAIN_DPS)
        combat.chars = [healer, sub_dps, main_dps]

        main_dps.last_switch_time = time.time()
        self.assertEqual(combat._choose_switch_target(healer, False), sub_dps)
        self.assertEqual(combat._choose_switch_target(healer, True), main_dps)

    def test_priority_compat_hooks_for_ciaccona_and_phrolova(self):
        class Task:
            name = None

            def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
                if start < 0:
                    return 10000
                return time.time() - start

        task = Task()
        current = BaseChar(task, 0, char_name=Labels.char_cantarella)

        ciaccona = Ciaccona(task, 1)
        ciaccona.attribute = 2
        ciaccona.in_liberation = True
        ciaccona.last_liberation = time.time() - 5
        self.assertFalse(ciaccona.can_switch(current_char=current, has_intro=False))

        phrolova = Phrolova(task, 2)
        phrolova.last_liberation = time.time() - 5
        self.assertFalse(phrolova.can_switch(current_char=current, has_intro=False))

        phrolova.last_liberation = time.time() - 15
        self.assertTrue(phrolova.must_switch(current_char=current, has_intro=True))
        self.assertTrue(phrolova.can_switch(current_char=current, has_intro=True))

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
