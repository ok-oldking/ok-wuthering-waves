import time
import unittest
from config import config
from ok.test.TaskTestCase import TaskTestCase
from src.Labels import Labels
from src.char.BaseChar import BaseChar, CharType, Elements, SwitchPriority, get_default_buff_time
from src.char.CharFactory import _get_buff_time, _get_char_type, char_dict, char_names, get_char_by_pos
from src.char.Aemeath import Aemeath
from src.char.Chisa import Chisa
from src.char.Ciaccona import Ciaccona
from src.char.Denia import Denia
from src.char.Iuno import Iuno
from src.char.Lynae import Lynae
from src.char.Lucilla import Lucilla
from src.char.Lucy import Lucy
from src.char.Phrolova import Phrolova
from src.char.Qingxiao import Qingxiao
from src.char.Rebecca import Rebecca
from src.char.Shorekeeper import Shorekeeper
from src.char.Suisui import Suisui
from src.char.Verina import Verina
from src.char.YangyangXuanling import YangyangXuanling
from src.task.BaseCombatTask import BaseCombatTask, NotInCombatException
from src.task.AutoCombatTask import AutoCombatTask
from src.task.FarmEchoTask import FarmEchoTask

config['debug'] = True


def return_true():
    return True


class BlockedChar(BaseChar):
    def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
        return SwitchPriority.NO


class ForcedChar(BaseChar):
    def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
        return SwitchPriority.MUST


class TestChar(TaskTestCase):
    task_class = AutoCombatTask
    config = config

    def test_healer_disables_f_check_on_switch_by_default(self):
        self.assertFalse(BaseChar(None, 0, char_type=CharType.HEALER).check_f_on_switch)
        self.assertTrue(BaseChar(None, 0, char_type=CharType.MAIN_DPS).check_f_on_switch)

    def test_combat_once_switches_to_healer_before_and_after_combat(self):
        combat = BaseCombatTask.__new__(BaseCombatTask)
        events = []
        combat.switch_healer_enabled = lambda: True
        combat.info = {}
        combat.wait_combat = lambda **kwargs: events.append('wait_combat') or True
        combat.load_chars = lambda: events.append('load_chars')
        combat.switch_healer = lambda: events.append('switch_healer')
        combat.in_combat = lambda: False
        combat.combat_end = lambda: events.append('combat_end')
        combat.wait_in_team_and_world = lambda **kwargs: events.append('wait_in_team')

        self.assertTrue(combat.combat_once(wait_combat_time=1))
        self.assertEqual(events, [
            'wait_combat',
            'load_chars',
            'switch_healer',
            'combat_end',
            'switch_healer',
            'wait_in_team',
        ])

    def test_combat_once_skips_healer_setup_when_disabled(self):
        combat = BaseCombatTask.__new__(BaseCombatTask)
        events = []
        combat.switch_healer_enabled = lambda: False
        combat.info = {}
        combat.wait_combat = lambda **kwargs: True
        combat.load_chars = lambda: events.append('load_chars')
        combat.switch_healer = lambda: events.append('switch_healer')
        combat.in_combat = lambda: False
        combat.combat_end = lambda: events.append('combat_end')
        combat.wait_in_team_and_world = lambda **kwargs: events.append('wait_in_team')

        self.assertTrue(combat.combat_once(wait_combat_time=1))
        self.assertEqual(events, ['combat_end', 'wait_in_team'])

    def test_auto_combat_switches_to_healer_before_and_after_combat(self):
        combat = AutoCombatTask.__new__(AutoCombatTask)
        events = []
        combat.scene = type('Scene', (), {'in_team': lambda self, check: True})()
        combat.in_team_and_world = lambda: True
        combat.config = {
            'Use Liberation': True,
            'Switch to Healer before and after Combat': True,
        }
        combat.warm_up_char_features = lambda: None
        combat.in_world = lambda: True
        combat.switch_healer = lambda: events.append('switch_healer')
        combat.combat_end = lambda: events.append('combat_end')
        in_combat_results = iter((True, False))
        combat.in_combat = lambda: next(in_combat_results)
        current = type('CurrentChar', (), {'perform': lambda self: events.append('perform')})()
        combat.get_current_char = lambda: current

        self.assertTrue(combat.run())
        self.assertEqual(events, [
            'switch_healer',
            'perform',
            'combat_end',
            'switch_healer',
        ])

    def test_switch_healer_does_nothing_when_team_has_no_healer(self):
        combat = BaseCombatTask.__new__(BaseCombatTask)
        combat.switch_healer_enabled = lambda: True
        current = BaseChar(None, 0, char_type=CharType.MAIN_DPS)
        teammate = BaseChar(None, 1, char_type=CharType.SUB_DPS)
        combat.chars = [current, teammate]
        combat.get_current_char = lambda: current
        switched = []
        current.switch_other_char = lambda **kwargs: switched.append(kwargs)

        combat.switch_healer()

        self.assertEqual(switched, [])

    def test_other_combat_tasks_use_auto_combat_healer_config(self):
        combat = BaseCombatTask.__new__(BaseCombatTask)
        auto_combat = AutoCombatTask.__new__(AutoCombatTask)
        auto_combat.config = {'Switch to Healer before and after Combat': False}
        combat.get_task_by_class = lambda cls: auto_combat

        self.assertFalse(combat.switch_healer_enabled())

        auto_combat.config['Switch to Healer before and after Combat'] = True
        self.assertTrue(combat.switch_healer_enabled())

    def test_farm_echo_uses_its_own_healer_config(self):
        farm_echo = FarmEchoTask.__new__(FarmEchoTask)
        farm_echo.config = {'Switch to Healer before and after Combat': False}
        farm_echo.get_task_by_class = lambda cls: self.fail('Farm Echo should not read Auto Combat config')

        self.assertFalse(farm_echo.switch_healer_enabled())

        farm_echo.config['Switch to Healer before and after Combat'] = True
        self.assertTrue(farm_echo.switch_healer_enabled())

    def test_char_type_config(self):
        class Task:
            char_config = {}

        task = Task()
        self.assertEqual(BaseChar(None, 0).char_type, CharType.MAIN_DPS)
        self.assertEqual(BaseChar(None, 0).buff_time, get_default_buff_time(CharType.MAIN_DPS))
        self.assertEqual(BaseChar(None, 0, char_type=CharType.HEALER).buff_time,
                         get_default_buff_time(CharType.HEALER))
        self.assertEqual(BaseChar(None, 0, char_type=CharType.SUB_DPS, buff_time=11).buff_time, 11)
        self.assertEqual(char_dict[Labels.char_mortefi]['char_type'], CharType.SUB_DPS)
        self.assertEqual(char_dict[Labels.char_mortefi]['buff_time'], get_default_buff_time(CharType.SUB_DPS))
        self.assertEqual(char_dict[Labels.char_chisa]['buff_time'], 20)
        self.assertEqual(char_dict[Labels.char_chisa2]['cls'], Chisa)
        self.assertEqual(char_dict[Labels.char_chisa2]['buff_time'], 20)

        self.assertEqual(char_dict[Labels.char_linnai2]['cls'], Lynae)
        self.assertEqual(char_dict[Labels.char_linnai2]['char_type'], CharType.SUB_DPS)
        self.assertEqual(char_dict[Labels.char_linnai2]['canonical_name'], Labels.char_linnai)
        self.assertEqual(
            char_dict[Labels.char_linnai2]['template_names'],
            (Labels.char_linnai, Labels.char_linnai2),
        )
        self.assertEqual(char_dict[Labels.char_lucilla]['cls'], Lucilla)
        self.assertEqual(char_dict[Labels.char_lucilla]['char_type'], CharType.SUB_DPS)
        self.assertTrue(char_dict[Labels.char_lucilla]['target_box_short_combat_check'])
        self.assertEqual(char_dict[Labels.char_lucy]['cls'], Lucy)
        self.assertEqual(char_dict[Labels.char_lucy]['char_type'], CharType.MAIN_DPS)
        self.assertEqual(char_dict[Labels.char_rebecca]['cls'], Rebecca)
        self.assertEqual(char_dict[Labels.char_rebecca]['char_type'], CharType.SUB_DPS)
        self.assertEqual(char_dict[Labels.char_suisui]['cls'], Suisui)
        self.assertEqual(char_dict[Labels.char_suisui]['char_type'], CharType.HEALER)
        self.assertEqual(char_dict[Labels.yangyang_sp]['cls'], YangyangXuanling)
        self.assertEqual(char_dict[Labels.yangyang_sp]['char_type'], CharType.MAIN_DPS)
        self.assertEqual(_get_char_type(task, char_dict[Labels.char_iuno]), CharType.SUB_DPS)
        self.assertEqual(_get_buff_time(task, char_dict[Labels.char_iuno]), get_default_buff_time(CharType.SUB_DPS))
        self.assertEqual(_get_buff_time(task, dict(char_dict[Labels.char_mortefi], buff_time=12)), 12)

        chisa = Chisa(task, 0, char_type=char_dict[Labels.char_chisa]['char_type'],
                      buff_time=char_dict[Labels.char_chisa]['buff_time'])
        self.assertEqual(chisa.char_type, CharType.HEALER)
        self.assertEqual(chisa.buff_time, 20)

        task.char_config = {'Chisa DPS': True}
        self.assertEqual(chisa.char_type, CharType.MAIN_DPS)
        self.assertEqual(chisa.buff_time, get_default_buff_time(CharType.MAIN_DPS))

        task.char_config = {'Iuno C6': True}
        iuno = Iuno(task, 0, char_type=char_dict[Labels.char_iuno]['char_type'],
                    buff_time=char_dict[Labels.char_iuno]['buff_time'])
        self.assertEqual(iuno.char_type, CharType.MAIN_DPS)
        self.assertEqual(iuno.buff_time, get_default_buff_time(CharType.MAIN_DPS))

        task.char_config = {'Iuno C6': False}
        self.assertEqual(iuno.char_type, CharType.SUB_DPS)
        self.assertEqual(iuno.buff_time, get_default_buff_time(CharType.SUB_DPS))

        suisui = Suisui(task, 0)
        self.assertEqual(suisui.FORTE3_SWITCH_LOCKOUT, 16.0)
        self.assertEqual(suisui.MAIN_DPS_FORTE3_SWITCH_LOCKOUT, 32)
        self.assertFalse(hasattr(Suisui, 'attack_once'))
        suisui.time_elapsed_accounting_for_freeze = lambda start: time.time() - start
        suisui._lock_after_switch = True
        suisui.switch_out(con_full=True)
        self.assertEqual(suisui.get_switch_priority(), SwitchPriority.NO)
        suisui.last_forte3_switch = -1
        self.assertEqual(suisui.get_switch_priority(), SwitchPriority.MUST)

    def test_has_all_buff_requires_intro_and_two_active_timed_buffs(self):
        class Task:
            def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
                return time.time() - start

        task = Task()
        current = BaseChar(task, 0)
        healer = BaseChar(task, 1, char_type=CharType.HEALER)
        sub_dps = BaseChar(task, 2, char_type=CharType.SUB_DPS)
        task.chars = [current, healer, sub_dps]
        healer.last_buff_time = time.time()
        sub_dps.last_buff_time = time.time()

        self.assertFalse(current.has_all_buff())
        current.has_intro = True
        self.assertTrue(current.has_all_buff())

        sub_dps.last_buff_time = time.time() - sub_dps.buff_time
        self.assertFalse(current.has_all_buff())

    def test_yangyang_sp_releases_and_settles_long_press_before_switching(self):
        actions = []

        class Task:
            skip_combat_check = False

            def mouse_down(self):
                actions.append('mouse_down')

            def mouse_up(self):
                actions.append('mouse_up')

            def sleep(self, duration):
                actions.append(('sleep', duration))

        class TrackingYangyangXuanling(YangyangXuanling):
            def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
                return self.PERFORM_DURATION

            def switch_next_char(self, *args, **kwargs):
                actions.append('switch')

        yangyang = TrackingYangyangXuanling(Task(), 0)
        yangyang.do_perform()

        self.assertEqual(actions, [
            'mouse_down',
            'mouse_up',
            ('sleep', YangyangXuanling.LONG_PRESS_RELEASE_DELAY),
            'switch',
        ])

    def test_yangyang_sp_uses_echo_once_and_sleeps_between_polls(self):
        actions = []

        class Task:
            skip_combat_check = False
            poll_count = 0

            def mouse_down(self):
                actions.append('mouse_down')

            def mouse_up(self):
                actions.append('mouse_up')

            def sleep(self, duration):
                actions.append(('sleep', duration))
                if duration == 0.05:
                    self.poll_count += 1

        class TrackingYangyangXuanling(YangyangXuanling):
            def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
                return 0 if self.task.poll_count < 3 else self.PERFORM_DURATION

            def click_echo(self, **kwargs):
                actions.append(('echo', kwargs))
                return True

            def liberation_available(self):
                return False

            def resonance_available(self):
                return False

            def switch_next_char(self, *args, **kwargs):
                actions.append('switch')

        yangyang = TrackingYangyangXuanling(Task(), 0)
        yangyang.do_perform()

        self.assertEqual(actions.count(('echo', {'time_out': 0})), 1)
        self.assertEqual(actions.count(('sleep', 0.05)), 3)

    def test_yangyang_sp_releases_mouse_when_poll_sleep_raises(self):
        actions = []

        class Task:
            skip_combat_check = False

            def mouse_down(self):
                actions.append('mouse_down')

            def mouse_up(self):
                actions.append('mouse_up')

            def sleep(self, duration):
                actions.append(('sleep', duration))
                if not self.skip_combat_check:
                    raise RuntimeError('combat check failed')

        class TrackingYangyangXuanling(YangyangXuanling):
            def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
                return 0

            def click_echo(self, **kwargs):
                return False

            def liberation_available(self):
                return False

            def resonance_available(self):
                return False

        yangyang = TrackingYangyangXuanling(Task(), 0)
        with self.assertRaisesRegex(RuntimeError, 'combat check failed'):
            yangyang.do_perform()

        self.assertEqual(actions, [
            'mouse_down',
            ('sleep', 0.05),
            'mouse_up',
            ('sleep', YangyangXuanling.LONG_PRESS_RELEASE_DELAY),
        ])

    def test_suisui_switch_priority_with_main_dps(self):
        class Task:
            chars = []

        task = Task()
        main_dps = BaseChar(task, 0, char_type=CharType.MAIN_DPS)
        suisui = Suisui(task, 1, char_type=CharType.HEALER)
        sub_dps = BaseChar(task, 2, char_type=CharType.SUB_DPS)
        elapsed = [0]
        suisui.time_elapsed_accounting_for_freeze = lambda start: elapsed[0]
        task.chars = [main_dps, suisui, sub_dps]

        elapsed[0] = 15.9
        self.assertEqual(
            suisui.get_switch_priority(current_char=main_dps, has_intro=True),
            SwitchPriority.NO,
        )

        elapsed[0] = 16.0
        self.assertEqual(
            suisui.get_switch_priority(current_char=main_dps, has_intro=True),
            SwitchPriority.MUST,
        )
        self.assertEqual(
            suisui.get_switch_priority(current_char=main_dps, has_intro=False),
            SwitchPriority.NORMAL,
        )
        self.assertEqual(
            suisui.get_switch_priority(current_char=sub_dps, has_intro=True),
            SwitchPriority.NORMAL,
        )

        task.chars = [suisui, sub_dps]
        elapsed[0] = 39.9
        self.assertEqual(
            suisui.get_switch_priority(current_char=sub_dps, has_intro=False),
            SwitchPriority.NORMAL,
        )
        elapsed[0] = 40.1
        self.assertEqual(
            suisui.get_switch_priority(current_char=sub_dps, has_intro=False),
            SwitchPriority.MUST,
        )

    def test_combat_end_resets_suisui_state_when_another_character_is_current(self):
        class Task:
            chars = []

        task = Task()
        current = BaseChar(task, 0, char_type=CharType.MAIN_DPS)
        suisui = Suisui(task, 1, char_type=CharType.HEALER)
        suisui.last_forte3_switch = time.time()

        combat = AutoCombatTask.__new__(AutoCombatTask)
        combat.chars = [current, suisui]
        combat.get_current_char = lambda raise_exception=False: current
        combat.combat_end()

        self.assertEqual(suisui.last_forte3_switch, -1)

    def test_click_liberation_send_click_false_disables_wait_click(self):
        class Task:
            use_liberation = True
            in_liberation = False

            def __init__(self):
                self.wait_post_action = object()

            def wait_until(self, condition, time_out=0, post_action=None):
                self.wait_post_action = post_action
                return True

            def in_team(self):
                return True, 0, 3

            def next_frame(self):
                pass

            def add_freeze_duration(self, start, duration=-1.0, freeze_time=0.1):
                pass

        class TestBaseChar(BaseChar):
            def __init__(self, task):
                super().__init__(task, 0)
                self.available_checks = 0

            def liberation_available(self, check_color=True):
                self.available_checks += 1
                return self.available_checks == 1

            def send_liberation_key(self, after_sleep=0, interval=-1, down_time=0.01):
                pass

        task = Task()
        char = TestBaseChar(task)

        self.assertTrue(char.click_liberation(send_click=False, wait_if_cd_ready=0))
        self.assertIsNone(task.wait_post_action)

    def test_click_liberation_clicks_f_during_animation_after_min_duration(self):
        class Clock:
            def __init__(self):
                self.now = 1.0

            def time(self):
                return self.now

            def advance(self, seconds):
                self.now += seconds

        class Task:
            use_liberation = True

            def __init__(self, clock):
                self.clock = clock
                self.in_liberation = True
                self.animation_start = clock.now
                self.sent_keys = []

            def in_team(self):
                return self.clock.now - self.animation_start >= 0.55, 0, 3

            def next_frame(self):
                self.clock.advance(0.05)

            def send_key(self, key):
                self.sent_keys.append((key, self.clock.now))

            def add_freeze_duration(self, start, duration=-1.0, freeze_time=0.1):
                pass

        base_char_globals = BaseChar.click_liberation.__globals__
        original_time = base_char_globals['time']
        try:
            clock = Clock()
            base_char_globals['time'] = clock
            task = Task(clock)
            self.assertTrue(BaseChar(task, 0).click_liberation(animation_min_duration=0.2))

            f_times = [sent_at for key, sent_at in task.sent_keys if key == 'f']
            self.assertGreaterEqual(len(f_times), 2)
            self.assertGreaterEqual(f_times[0] - task.animation_start, 0.2)
            self.assertTrue(all(later - earlier >= 0.1 for earlier, later in zip(f_times, f_times[1:])))

            clock = Clock()
            base_char_globals['time'] = clock
            task = Task(clock)
            self.assertTrue(BaseChar(task, 0).click_liberation(click_f=False))
            self.assertNotIn('f', [key for key, _ in task.sent_keys])
        finally:
            base_char_globals['time'] = original_time

    def test_click_resonance_clicks_f_during_animation_after_min_duration(self):
        class Clock:
            now = 1.0

            def time(self):
                return self.now

            def advance(self, seconds):
                self.now += seconds

        class Task:
            in_liberation = False
            skip_combat_check = False

            def __init__(self, clock):
                self.clock = clock
                self.animation_started = False
                self.animation_start = 0
                self.sent_keys = []

            def in_team(self):
                if not self.animation_started:
                    return True, 0, 3
                return self.clock.now - self.animation_start >= 0.55, 0, 3

            def next_frame(self):
                self.clock.advance(0.05)

            def sleep(self, seconds):
                self.clock.advance(seconds)

            def send_key(self, key):
                self.sent_keys.append((key, self.clock.now))

        class TestBaseChar(BaseChar):
            def __init__(self, task):
                super().__init__(task, 0)
                self.resonance_ready = True

            def check_combat(self):
                pass

            def resonance_available(self):
                return self.resonance_ready

            def record_resonance_use(self):
                pass

            def send_resonance_key(self, *args, **kwargs):
                self.resonance_ready = False
                self.task.animation_started = True
                self.task.animation_start = self.task.clock.now + 0.2

            def add_freeze_duration(self, *args, **kwargs):
                pass

        clock = Clock()
        task = Task(clock)
        char = TestBaseChar(task)
        base_char_globals = BaseChar.click_resonance.__globals__
        original_time = base_char_globals['time']
        base_char_globals['time'] = clock
        try:
            result = char.click_resonance(
                has_animation=True,
                animation_min_duration=0.2,
                time_out=2,
            )
        finally:
            base_char_globals['time'] = original_time

        f_times = [sent_at for key, sent_at in task.sent_keys if key == 'f']
        self.assertTrue(result[2])
        self.assertGreaterEqual(len(f_times), 2)
        self.assertGreaterEqual(f_times[0] - task.animation_start, 0.2)
        self.assertTrue(all(later - earlier >= 0.1 for earlier, later in zip(f_times, f_times[1:])))

    def test_click_resonance_click_f_can_be_disabled(self):
        class Task:
            in_liberation = False
            skip_combat_check = False

            def __init__(self):
                self.frames = 0
                self.sent_keys = []

            def in_team(self):
                return self.frames != 1, 0, 3

            def next_frame(self):
                self.frames += 1

            def sleep(self, seconds):
                pass

            def send_key(self, key):
                self.sent_keys.append(key)

        class TestBaseChar(BaseChar):
            def __init__(self, task):
                super().__init__(task, 0)

            def check_combat(self):
                pass

            def resonance_available(self):
                return True

            def record_resonance_use(self):
                pass

            def send_resonance_key(self, *args, **kwargs):
                pass

            def add_freeze_duration(self, *args, **kwargs):
                pass

        task = Task()
        TestBaseChar(task).click_resonance(has_animation=True, click_f=False, time_out=1)

        self.assertNotIn('f', task.sent_keys)

    def test_factory_normalizes_alternate_template_to_canonical_name(self):
        class FoundChar:
            name = Labels.char_linnai2
            confidence = 0.99

        class Task:
            debug = False

            def __init__(self):
                self.searches = []

            def find_best_match_in_box(self, box, names, threshold=0.6):
                self.searches.append(tuple(names))
                return FoundChar()

            def log_info(self, *args, **kwargs):
                pass

        task = Task()
        char = get_char_by_pos(task, None, 0, None)

        self.assertIsInstance(char, Lynae)
        self.assertEqual(char.char_name, Labels.char_linnai)

        char = get_char_by_pos(task, None, 0, char)

        self.assertEqual(char.char_name, Labels.char_linnai)
        self.assertEqual(
            task.searches[-1],
            (Labels.char_linnai, Labels.char_linnai2),
        )

    def test_auto_combat_warms_char_features_only_once(self):
        task = AutoCombatTask.__new__(AutoCombatTask)
        task.char_features_warmed_up = False
        loaded = []
        task.get_feature_by_name = loaded.append

        task.warm_up_char_features()
        task.warm_up_char_features()

        self.assertTrue(task.char_features_warmed_up)
        self.assertEqual(loaded, list(char_names))

    def test_load_chars_reports_only_when_team_changes(self):
        from importlib import import_module

        base_combat_task_module = import_module('src.task.BaseCombatTask')
        original_get_char_by_pos = base_combat_task_module.get_char_by_pos

        class CharA(BaseChar):
            pass

        class CharB(BaseChar):
            pass

        class CharC(BaseChar):
            pass

        class CharD(BaseChar):
            pass

        task = AutoCombatTask.__new__(AutoCombatTask)
        task.chars = [None, None, None]
        task.load_hotkey = lambda: None
        task.in_team = lambda: (True, 0, 3)
        task.get_box_by_name = lambda name: name
        task._app = None
        task.tr = lambda text: text
        info_sets = []
        logs = []
        task.info_set = lambda key, value: info_sets.append((key, value))
        task.log_info = logs.append
        team = [(CharA, 'char_a'), (CharB, 'char_b'), (CharC, 'char_c')]

        def get_char_by_pos(task_arg, box, index, old_char):
            char_cls, char_name = team[index]
            return char_cls(task_arg, index, char_name=char_name, confidence=0.9)

        base_combat_task_module.get_char_by_pos = get_char_by_pos
        try:
            self.assertTrue(task.load_chars())
            self.assertEqual(info_sets, [('Chars', 'CharA, CharB, CharC')])
            self.assertEqual(len(logs), 3)

            self.assertTrue(task.load_chars())
            self.assertEqual(len(info_sets), 1)
            self.assertEqual(len(logs), 3)

            team[1] = (CharD, 'char_d')
            self.assertTrue(task.load_chars())
            self.assertEqual(info_sets[-1], ('Chars', 'CharA, CharD, CharC'))
            self.assertEqual(len(info_sets), 2)
            self.assertEqual(len(logs), 6)
        finally:
            base_combat_task_module.get_char_by_pos = original_get_char_by_pos

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
        self.assertEqual(combat._choose_switch_target(current, False), sub_dps)

        combat.chars = [current, healer, sub_dps]
        healer.last_switch_in_time = 1
        sub_dps.last_switch_in_time = 2
        healer.last_buff_time = -1
        self.assertEqual(combat._choose_switch_target(current, False), healer)

        combat.chars = [current, healer, sub_dps, main_dps]
        current.set_char_type(CharType.SUB_DPS)
        self.assertEqual(combat._choose_switch_target(current, False), healer)
        self.assertEqual(combat._choose_switch_target(current, True), healer)

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
        self.assertEqual(combat._choose_switch_target(current, True), sub_dps)
        current.last_perform = 0

        forced = ForcedChar(task, 4, char_type=CharType.MAIN_DPS)
        task.chars = [current, healer, sub_dps, main_dps, forced]
        self.assertTrue(current.need_fast_perform())
        task.chars = [current, healer, sub_dps, main_dps]
        self.assertFalse(current.need_fast_perform())

        current.set_char_type(CharType.MAIN_DPS)
        healer.last_buff_time = -1
        self.assertEqual(combat._choose_switch_target(current, True), healer)

        healer.last_buff_time = time.time()
        sub_dps.last_buff_time = -1
        self.assertEqual(combat._choose_switch_target(current, True), sub_dps)

        combat.chars = [current, healer, sub_dps]
        self.assertEqual(combat._choose_switch_target(current, True), sub_dps)
        combat.chars = [current, healer, sub_dps, main_dps]

        combat._apply_intro_flags(sub_dps, current, True)
        self.assertTrue(current.has_intro)
        self.assertTrue(current.has_sub_dps_intro)

        combat._apply_intro_flags(healer, current, True)
        self.assertTrue(current.has_intro)
        self.assertFalse(current.has_sub_dps_intro)

    def _make_support_chisa(self, has_intro, buffed=False):
        class Task:
            char_config = {'Chisa DPS': False}

        class TrackingChisa(Chisa):
            def __init__(self, task):
                super().__init__(task, 0)
                self.actions = []
                self.elapsed = 0
                self.buffed = buffed
                self.resonance_ready = True
                self.liberation_ready = True
                self.con_full_at = None

            def has_buff(self):
                return self.buffed

            def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
                return self.elapsed

            def cycle_start(self):
                pass

            def cycle_sleep(self, min_sleep=0.1):
                self.elapsed += min_sleep

            def flying(self):
                return False

            def is_con_full(self):
                return self.con_full_at is not None and self.elapsed >= self.con_full_at

            def click_echo(self, **kwargs):
                self.actions.append(('echo', kwargs))

            def click_liberation(self, **kwargs):
                self.actions.append(('liberation', kwargs))
                self.liberation_ready = False
                return True

            def click_resonance(self, **kwargs):
                self.actions.append(('resonance', kwargs))
                self.resonance_ready = False
                return True, None

            def switch_next_char(self, *args, **kwargs):
                self.actions.append(('switch', {}))

            def resonance_available(self):
                return self.resonance_ready

            def liberation_available(self):
                return self.liberation_ready

            def is_forte_full(self):
                return False

            def continues_normal_attack(self, duration, **kwargs):
                self.actions.append(('normal', duration))

            def click(self, *args, **kwargs):
                self.actions.append(('click', {}))

        chisa = TrackingChisa(Task())
        chisa.has_intro = has_intro
        return chisa

    def test_chisa_support_intro_without_buff_uses_long_actions(self):
        chisa = self._make_support_chisa(has_intro=True)
        chisa.do_perform()

        self.assertEqual(chisa.last_buff_time, -1)
        self.assertGreaterEqual(chisa.elapsed, Chisa.SUPPORT_LONG_ACTION_DURATION)
        self.assertEqual(chisa.actions[:2], [('normal', 2.0), ('echo', {'time_out': 0})])
        self.assertIn(('liberation', {'wait_if_cd_ready': 0}), chisa.actions)
        self.assertIn(('resonance', {'time_out': 0}), chisa.actions)
        self.assertEqual(chisa.actions[-1], ('switch', {}))

    def test_verina_heavy_attack_has_eight_second_interval(self):
        class Task:
            def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
                return time.time() - start

            def wait_until(self, condition, time_out=0, **kwargs):
                return condition()

            def in_team(self):
                return True, None

            def sleep(self, sec):
                pass

            def jump(self, after_sleep=0.01):
                pass

        class TrackingVerina(Verina):
            def __init__(self, task):
                super().__init__(task, 0)
                self.heavy_count = 0

            def is_con_full(self):
                return False

            def continues_normal_attack(self, duration, **kwargs):
                pass

            def resonance_available(self):
                return False

            def liberation_available(self):
                return False

            def echo_available(self):
                return False

            def is_mouse_forte_full(self):
                return True

            def heavy_attack(self, duration=0.6):
                self.heavy_count += 1

        verina = TrackingVerina(Task())
        verina.perform_combat()
        self.assertEqual(verina.heavy_count, 1)

        verina.perform_combat()
        self.assertEqual(verina.heavy_count, 1)

        verina.last_heavy = time.time() - verina.HEAVY_ATTACK_INTERVAL
        verina.perform_combat()
        self.assertEqual(verina.heavy_count, 2)

    def test_chisa_support_liberation_without_intro_does_not_record_buff(self):
        chisa = self._make_support_chisa(has_intro=False)
        chisa.do_perform()

        self.assertEqual(chisa.last_buff_time, -1)
        self.assertGreaterEqual(chisa.elapsed, Chisa.SUPPORT_ACTION_DURATION)
        self.assertLess(chisa.elapsed, Chisa.SUPPORT_LONG_ACTION_DURATION)
        self.assertNotIn(('normal', 2.0), chisa.actions)
        self.assertIn(('liberation', {'wait_if_cd_ready': 0}), chisa.actions)
        self.assertEqual(chisa.actions[-1], ('switch', {}))

    def test_chisa_support_intro_with_active_buff_uses_short_actions(self):
        chisa = self._make_support_chisa(has_intro=True, buffed=True)
        chisa.do_perform()

        self.assertGreaterEqual(chisa.elapsed, Chisa.SUPPORT_ACTION_DURATION)
        self.assertLess(chisa.elapsed, Chisa.SUPPORT_LONG_ACTION_DURATION)
        self.assertEqual(chisa.actions[:2], [('normal', 2.0), ('echo', {'time_out': 0})])
        self.assertEqual(chisa.actions[-1], ('switch', {}))

    def test_chisa_support_switches_early_when_concerto_is_full(self):
        chisa = self._make_support_chisa(has_intro=True)
        chisa.con_full_at = 0.2
        chisa.do_perform()

        self.assertEqual(chisa.elapsed, 0.2)
        self.assertLess(chisa.elapsed, Chisa.SUPPORT_LONG_ACTION_DURATION)
        self.assertEqual(chisa.actions[-1], ('switch', {}))

    def test_chisa_uses_default_outro_buff_tracking(self):
        class Task:
            char_config = {'Chisa DPS': False}

        chisa = Chisa(Task(), 0, char_type=CharType.HEALER, buff_time=12)
        chisa.switch_out(con_full=False)
        self.assertEqual(chisa.last_buff_time, -1)

        chisa.switch_out(con_full=True)
        self.assertGreater(chisa.last_buff_time, 0)

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

    def test_aemeath_lib_tracks_lib2_cast_for_current_turn(self):
        class Task:
            lib2 = False

            def find_one(self, template, threshold=None):
                return self.lib2 and template == 'aemeath_lib2'

        class TrackingAemeath(Aemeath):
            def click_liberation(self, **kwargs):
                return True

        task = Task()
        aemeath = TrackingAemeath(task, 0)
        self.assertTrue(aemeath.lib())
        self.assertFalse(aemeath.lib2_cast_this_turn)

        task.lib2 = True
        self.assertTrue(aemeath.lib())
        self.assertTrue(aemeath.lib2_cast_this_turn)

    def test_aemeath_required_actions_are_cleared_by_enhance_e_and_lib2(self):
        aemeath = Aemeath(None, 0)
        aemeath.has_intro = True
        aemeath.must_cast_lib2_this_turn = True

        self.assertTrue(aemeath.required_action_pending())
        aemeath.record_enhance_e()
        self.assertTrue(aemeath.required_action_pending())
        aemeath.lib2_cast_this_turn = True
        self.assertFalse(aemeath.required_action_pending())

    def test_aemeath_rotation_casts_available_lib2_first(self):
        class Task:
            chars = []

            def find_one(self, template, threshold=None):
                return template in {'aemeath_e1', 'aemeath_lib2'}

            def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
                return time.time() - start

            def next_frame(self):
                pass

        class TrackingAemeath(Aemeath):
            def __init__(self, task):
                super().__init__(task, 0)
                self.actions = []

            def click_resonance(self, **kwargs):
                self.actions.append('enhance_e')
                return True, None

            def click_echo(self, **kwargs):
                pass

            def click_liberation(self, **kwargs):
                self.actions.append('lib2')
                return True

            def f_break(self):
                pass

            def handle_heavy(self):
                return False

            def cycle_start(self):
                pass

        task = Task()
        aemeath = TrackingAemeath(task)
        healer = BaseChar(task, 1, char_type=CharType.HEALER)
        sub_dps = BaseChar(task, 2, char_type=CharType.SUB_DPS)
        task.chars = [aemeath, healer, sub_dps]
        aemeath.has_intro = True
        healer.last_buff_time = time.time()
        sub_dps.last_buff_time = time.time()

        aemeath.perform_everything()

        self.assertEqual(aemeath.actions, ['lib2'])
        self.assertTrue(aemeath.lib2_cast_this_turn)

    def test_aemeath_skips_full_rotation_without_intro_and_all_buffs(self):
        class TrackingAemeath(Aemeath):
            def __init__(self):
                super().__init__(None, 0)
                self.actions = []

            def has_long_action(self):
                return False

            def perform_everything(self):
                self.actions.append('perform')

            def switch_next_char(self):
                self.actions.append('switch')

        aemeath = TrackingAemeath()
        aemeath.do_perform()
        self.assertEqual(aemeath.actions, ['switch'])

    def test_aemeath_handle_heavy_uses_highlight_wait(self):
        class TrackingAemeath(Aemeath):
            def __init__(self):
                super().__init__(None, 0)
                self.waited = False

            def has_long_action(self):
                return True

            def heavy_wait_highlight_down(self):
                self.waited = True
                return True

        aemeath = TrackingAemeath()
        self.assertTrue(aemeath.handle_heavy())
        self.assertTrue(aemeath.waited)

    def test_aemeath_switches_immediately_after_lib2(self):
        class Task:
            def find_one(self, template, threshold=None):
                return template == 'aemeath_lib2'

            def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
                return time.time() - start

        class TrackingAemeath(Aemeath):
            def __init__(self, task):
                super().__init__(task, 0)
                self.actions = []

            def perform_everything(self):
                self.lib()

            def has_all_buff(self):
                return True

            def continues_normal_attack(self, duration):
                pass

            def click_liberation(self, **kwargs):
                self.actions.append('lib2')
                return True

            def f_break(self):
                pass

            def switch_next_char(self):
                self.actions.append('switch')

        aemeath = TrackingAemeath(Task())
        aemeath.has_intro = True
        aemeath.do_perform()
        self.assertEqual(aemeath.actions, ['lib2', 'switch'])

    def test_aemeath_continue_after_action_waits_for_required_actions(self):
        class TrackingAemeath(Aemeath):
            def has_long_action(self):
                return False

        aemeath = TrackingAemeath(None, 0)
        aemeath.has_intro = True
        start = time.time()

        self.assertEqual(aemeath.continue_after_action(start), start)
        aemeath.record_enhance_e()
        self.assertIsNone(aemeath.continue_after_action(start))

    def test_aemeath_all_buff_intro_runs_rotation_then_switches(self):
        class TrackingAemeath(Aemeath):
            def __init__(self):
                super().__init__(None, 0)
                self.actions = []

            def has_all_buff(self):
                return True

            def continues_normal_attack(self, duration):
                self.actions.append(('normal', duration))

            def perform_everything(self):
                self.actions.append('perform')

            def switch_next_char(self):
                self.actions.append('switch')

        aemeath = TrackingAemeath()
        aemeath.has_intro = True
        aemeath.do_perform()

        self.assertEqual(aemeath.actions, [('normal', 2.1), 'perform', 'switch'])
        self.assertTrue(aemeath.must_cast_lib2_this_turn)

    def test_aemeath_rotation_falls_back_to_enhance_e_when_liberation_fails(self):
        class Task:
            def find_one(self, template, threshold=None):
                return template == 'aemeath_e1'

            def next_frame(self):
                pass

        class TrackingAemeath(Aemeath):
            def __init__(self, task):
                super().__init__(task, 0)
                self.actions = []
                self.cycles = 0
                self.liberation_attempts = 0

            def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
                return 100 if self.cycles >= 2 else time.time() - start

            def click_liberation(self, **kwargs):
                self.actions.append('lib1')
                self.liberation_attempts += 1
                return self.liberation_attempts > 1

            def click_resonance(self, **kwargs):
                self.actions.append('enhance_e')
                return True, None

            def click_echo(self, **kwargs):
                return False

            def liberation_available(self):
                return True

            def handle_heavy(self):
                return False

            def has_long_action(self):
                return False

            def cycle_start(self):
                pass

            def cycle_sleep(self):
                self.cycles += 1

            def f_break(self):
                pass

        aemeath = TrackingAemeath(Task())
        aemeath.perform_everything()
        self.assertEqual(aemeath.actions, ['lib1', 'enhance_e', 'lib1'])

    def test_qingxiao_full_rotation_finishes_h2_with_liberation_then_switches(self):
        class TrackingQingxiao(Qingxiao):
            def __init__(self):
                super().__init__(None, 0)
                self.actions = []
                self.heavy_count = 0

            def has_all_buff(self):
                return True

            def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
                return 0

            def click_liberation(self, **kwargs):
                self.actions.append('liberation')
                return True

            def cast_enhanced_resonance(self):
                self.actions.append('enhanced_resonance')
                return True

            def handle_heavy(self):
                self.heavy_count += 1
                if self.heavy_count == 1:
                    self.actions.append('heavy_h2')
                    return Labels.qingxiao_h2
                return False

            def f_break(self):
                self.actions.append('f_break')

            def switch_next_char(self):
                self.actions.append('switch')

        qingxiao = TrackingQingxiao()
        qingxiao.has_intro = True
        qingxiao.do_perform()

        self.assertTrue(qingxiao.must_cast_lib_this_turn)
        self.assertEqual(qingxiao.actions, ['heavy_h2', 'f_break', 'liberation', 'switch'])

    def test_qingxiao_short_rotation_uses_e_then_switches(self):
        class TrackingQingxiao(Qingxiao):
            def __init__(self):
                super().__init__(None, 0)
                self.actions = []

            def has_all_buff(self):
                return False

            def click_liberation(self, **kwargs):
                self.actions.append('liberation')

            def cast_enhanced_resonance(self):
                self.actions.append('enhanced_resonance')
                return True

            def handle_heavy(self):
                self.actions.append('heavy')

            def switch_next_char(self):
                self.actions.append('switch')

        qingxiao = TrackingQingxiao()
        qingxiao.has_intro = True
        qingxiao.do_perform()

        self.assertFalse(qingxiao.must_cast_lib_this_turn)
        self.assertEqual(qingxiao.actions, ['enhanced_resonance', 'switch'])

    def test_qingxiao_heavy_holds_until_both_indicators_disappear(self):
        class Task:
            # 图标熄灭后,去抖确认窗还会再取一帧复核,故暗帧需要两帧
            indicators = [Labels.qingxiao_h1, Labels.qingxiao_h2, None, None]

            def __init__(self):
                self.frame = 0
                self.actions = []

            def find_one(self, template, threshold=None):
                if template == self.indicators[self.frame]:
                    return template
                return None

            def mouse_down(self):
                self.actions.append('mouse_down')

            def mouse_up(self):
                self.actions.append('mouse_up')

            def next_frame(self):
                self.frame += 1

            def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
                return time.time() - start

            def sleep(self, sec):
                pass

        task = Task()
        qingxiao = Qingxiao(task, 0)

        self.assertTrue(qingxiao.handle_heavy())
        self.assertEqual(task.actions, ['mouse_down', 'mouse_up'])
        self.assertEqual(task.frame, 3)

    def test_qingxiao_is_registered_as_wind_main_dps(self):
        info = char_dict[Labels.char_qingxiao]

        self.assertIs(info['cls'], Qingxiao)
        self.assertEqual(info['char_type'], CharType.MAIN_DPS)
        self.assertEqual(info['ring_index'], Elements.WIND)

    def test_switch_priority_hooks(self):
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

        self.assertEqual(current.get_switch_priority(), SwitchPriority.NORMAL)
        self.assertEqual(combat._choose_switch_target(current, False), forced)

        forced.last_switch_time = time.time()
        self.assertEqual(combat._choose_switch_target(current, False), forced)
        forced.last_switch_time = -1

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

    def test_healer_full_con_switch_has_default_sixteen_second_lockout(self):
        class Task:
            def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
                return time.time() - start

        task = Task()
        healer = BaseChar(task, 0, char_type=CharType.HEALER)

        healer.switch_out(con_full=True)
        self.assertEqual(healer.HEALER_FULL_CON_SWITCH_LOCKOUT, 16.0)
        self.assertEqual(healer.get_switch_priority(), SwitchPriority.NO)

        healer.last_full_con_switch_time = time.time() - 16.01
        self.assertEqual(healer.get_switch_priority(), SwitchPriority.NORMAL)

        healer_without_outro = BaseChar(task, 1, char_type=CharType.HEALER)
        healer_without_outro.switch_out(con_full=False)
        self.assertEqual(healer_without_outro.get_switch_priority(), SwitchPriority.NORMAL)

        main_dps = BaseChar(task, 2, char_type=CharType.MAIN_DPS)
        main_dps.switch_out(con_full=True)
        self.assertEqual(main_dps.get_switch_priority(), SwitchPriority.NORMAL)

    def test_healer_full_con_lockout_overrides_character_must_priority(self):
        class Task:
            def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
                return time.time() - start

        task = Task()
        combat = AutoCombatTask.__new__(AutoCombatTask)
        current = BaseChar(task, 0, char_type=CharType.MAIN_DPS)
        healer = ForcedChar(task, 1, char_type=CharType.HEALER)
        sub_dps = BaseChar(task, 2, char_type=CharType.SUB_DPS)
        combat.chars = [current, healer, sub_dps]

        healer.switch_out(con_full=True)

        self.assertEqual(combat._choose_switch_target(current, True), sub_dps)

    def test_qingxiao_switches_to_denia_while_full_con_healer_is_locked(self):
        class Task:
            chars = []

            def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
                return time.time() - start

        task = Task()
        combat = AutoCombatTask.__new__(AutoCombatTask)
        qingxiao = Qingxiao(task, 0, char_type=CharType.MAIN_DPS)
        denia = Denia(task, 1, char_type=CharType.SUB_DPS)
        healer = BaseChar(task, 2, char_type=CharType.HEALER)
        combat.chars = task.chars = [qingxiao, denia, healer]

        healer.switch_out(con_full=True)

        self.assertEqual(combat._choose_switch_target(qingxiao, True), denia)

    def test_denia_accepts_intro_as_deadlock_recovery(self):
        class Task:
            def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
                return time.time() - start

        task = Task()
        combat = AutoCombatTask.__new__(AutoCombatTask)
        aemeath = Aemeath(task, 0, char_type=CharType.MAIN_DPS)
        denia = Denia(task, 1, char_type=CharType.SUB_DPS)
        healer = BlockedChar(task, 2, char_type=CharType.HEALER)
        combat.chars = task.chars = [aemeath, denia, healer]

        self.assertEqual(combat._choose_switch_target(aemeath, True), denia)

        denia.last_buff_time = time.time()
        self.assertEqual(combat._choose_switch_target(aemeath, True), denia)

        denia.last_buff_time = -1
        other_main_dps = BaseChar(task, 0, char_type=CharType.MAIN_DPS)
        combat.chars = task.chars = [other_main_dps, denia, healer]
        self.assertEqual(combat._choose_switch_target(other_main_dps, True), denia)

    def test_switch_priority_integer_bands_and_offsets(self):
        self.assertEqual(
            [SwitchPriority.NO, SwitchPriority.LOW, SwitchPriority.NORMAL,
             SwitchPriority.HIGH, SwitchPriority.MUST],
            [0, 100, 200, 300, 400],
        )
        self.assertGreater(SwitchPriority.HIGH + 1, SwitchPriority.HIGH)
        self.assertLess(SwitchPriority.HIGH + 1, SwitchPriority.MUST)
        self.assertLess(SwitchPriority.LOW - 1, SwitchPriority.LOW)
        self.assertGreater(SwitchPriority.LOW - 1, SwitchPriority.NO)

        class PriorityChar(BaseChar):
            def __init__(self, task, index, priority, char_type):
                super().__init__(task, index, char_type=char_type)
                self.priority = priority

            def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
                return self.priority

        class Task:
            def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
                return 10000

        task = Task()
        combat = AutoCombatTask.__new__(AutoCombatTask)
        current = BaseChar(task, 0, char_type=CharType.MAIN_DPS)
        high = PriorityChar(task, 1, SwitchPriority.HIGH, CharType.MAIN_DPS)
        boosted_high = PriorityChar(task, 2, SwitchPriority.HIGH + 1, CharType.SUB_DPS)
        low = PriorityChar(task, 3, SwitchPriority.LOW - 1, CharType.HEALER)
        combat.chars = [current, high, boosted_high, low]

        self.assertEqual(combat._choose_switch_target(current, True), boosted_high)

        boosted_high.priority = SwitchPriority.NO
        self.assertEqual(combat._choose_switch_target(current, True), high)

    def test_intro_refresh_reselects_must_target_before_switch_key_is_sent(self):
        class Task:
            def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
                if start < 0:
                    return 10000
                return time.time() - start

            def get_current_con(self):
                return 0

            def is_con_full(self):
                return True

        class IntroBlockedChar(BaseChar):
            def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
                return SwitchPriority.NO if has_intro else SwitchPriority.NORMAL

        class IntroForcedChar(BaseChar):
            def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
                return SwitchPriority.MUST if has_intro else SwitchPriority.NORMAL

        task = Task()
        combat = AutoCombatTask.__new__(AutoCombatTask)
        current = BaseChar(task, 0, char_type=CharType.MAIN_DPS)
        blocked = IntroBlockedChar(task, 1, char_type=CharType.HEALER)
        forced = IntroForcedChar(task, 2, char_type=CharType.MAIN_DPS)
        combat.chars = [current, blocked, forced]
        actions = []
        combat.sent_keys = []
        combat.in_liberation = False
        combat.update_lib_portrait_icon = lambda: None
        combat.check_combat = lambda: None
        combat.log_debug = lambda *args, **kwargs: None
        combat.click = lambda: None
        combat.sleep = lambda *args, **kwargs: None
        combat.add_freeze_duration = lambda *args, **kwargs: None
        current.f_break = lambda **kwargs: actions.append('f_break')

        def send_key(key):
            actions.append('switch_key')
            combat.sent_keys.append(key)

        combat.send_key = send_key
        combat.in_team = lambda: (True, combat.sent_keys[-1] - 1 if combat.sent_keys else current.index, 3)

        combat.switch_next_char(current)

        self.assertEqual(combat.sent_keys, [forced.index + 1])
        self.assertEqual(actions, ['f_break', 'switch_key'])
        self.assertTrue(forced.has_intro)
        self.assertGreater(current.last_outro_time, 0)

    def test_intro_refresh_does_not_switch_to_newly_blocked_only_target(self):
        class Task:
            def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
                if start < 0:
                    return 10000
                return time.time() - start

            def get_current_con(self):
                return 0

            def is_con_full(self):
                return True

        class IntroBlockedChar(BaseChar):
            def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
                return SwitchPriority.NO if has_intro else SwitchPriority.NORMAL

        task = Task()
        combat = AutoCombatTask.__new__(AutoCombatTask)
        current = BaseChar(task, 0, char_type=CharType.MAIN_DPS)
        blocked = IntroBlockedChar(task, 1, char_type=CharType.HEALER)
        combat.chars = [current, blocked]
        combat.sent_keys = []
        combat.update_lib_portrait_icon = lambda: None
        combat.check_combat = lambda: None
        combat.in_team = lambda: (True, current.index, 2)
        combat.send_key = lambda key: combat.sent_keys.append(key)
        combat.sleep = lambda *args, **kwargs: None
        current.f_break = lambda **kwargs: None
        current.continues_normal_attack = lambda *args, **kwargs: None

        combat.switch_next_char(current)

        self.assertEqual(combat.sent_keys, [])

    def test_non_intro_switch_breaks_after_success_before_switch_time_is_recorded(self):
        class Task:
            def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
                if start < 0:
                    return 10000
                return time.time() - start

            def get_current_con(self):
                return 0

            def is_con_full(self):
                return False

        task = Task()
        combat = AutoCombatTask.__new__(AutoCombatTask)
        current = BaseChar(task, 0, char_type=CharType.MAIN_DPS)
        target = BaseChar(task, 1, char_type=CharType.HEALER)
        combat.chars = [current, target]
        actions = []
        switched = []
        f_break_time = []
        combat.in_liberation = False
        combat.update_lib_portrait_icon = lambda: None
        combat.check_combat = lambda: None
        combat.log_debug = lambda *args, **kwargs: None
        combat.click = lambda: None
        combat.sleep = lambda *args, **kwargs: None

        def f_break(**kwargs):
            actions.append('f_break')
            f_break_time.append(time.time())

        def send_key(key):
            actions.append('switch_key')
            switched.append(key)

        current.f_break = f_break
        combat.send_key = send_key
        combat.in_team = lambda: (True, target.index if switched else current.index, 2)

        combat.switch_next_char(current)

        self.assertEqual(switched, [target.index + 1])
        self.assertEqual(actions, ['switch_key', 'f_break'])
        self.assertGreaterEqual(current.last_switch_time, f_break_time[0])

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
        self.assertEqual(combat._choose_switch_target(healer, True), sub_dps)
        self.assertEqual(combat._choose_switch_target(sub_dps, False), healer)
        self.assertEqual(combat._choose_switch_target(sub_dps, True), healer)

        healer.last_buff_time = time.time()
        self.assertEqual(combat._choose_switch_target(healer, False), sub_dps)
        self.assertEqual(combat._choose_switch_target(sub_dps, False), main_dps)

    def test_non_intro_current_action_time_does_not_override_buff_rotation(self):
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

        sub_dps.last_perform = time.time()
        healer.last_buff_time = time.time()
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

    def test_intro_prefers_unbuffed_supports_before_main_dps(self):
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

        self.assertEqual(combat._choose_switch_target(current, True), healer)

        healer.last_buff_time = time.time()
        self.assertEqual(combat._choose_switch_target(current, True), sub_dps)

        sub_dps.last_buff_time = time.time()
        self.assertEqual(combat._choose_switch_target(current, True), main_dps)

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

    def test_ciaccona_can_switch_after_liberation_when_only_target_has_switch_cd(self):
        class Task:
            name = None

            def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
                if start < 0:
                    return 10000
                return time.time() - start

        task = Task()
        combat = AutoCombatTask.__new__(AutoCombatTask)
        ciaccona = Ciaccona(task, 0, char_type=CharType.SUB_DPS)
        main_dps = BaseChar(task, 1, char_type=CharType.MAIN_DPS)
        combat.chars = [ciaccona, main_dps]

        ciaccona.in_liberation = True
        ciaccona.last_liberation = time.time()
        main_dps.last_switch_time = time.time()
        self.assertEqual(combat._choose_switch_target(ciaccona, False), main_dps)

    def test_intro_switches_from_healer_to_unbuffed_sub_dps(self):
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

        self.assertEqual(combat._choose_switch_target(healer, False), sub_dps)
        main_dps.last_switch_time = time.time()
        self.assertEqual(combat._choose_switch_target(healer, True), sub_dps)

    def test_intro_switch_target_order_and_blocked_targets_are_respected(self):
        class Task:
            def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
                if start < 0:
                    return 10000
                return time.time() - start

        task = Task()
        combat = AutoCombatTask.__new__(AutoCombatTask)
        current = BaseChar(task, 0, char_type=CharType.HEALER)
        healer = BaseChar(task, 1, char_type=CharType.HEALER)
        sub_dps = BaseChar(task, 2, char_type=CharType.SUB_DPS)
        main_dps = BaseChar(task, 3, char_type=CharType.MAIN_DPS)
        forced = ForcedChar(task, 4, char_type=CharType.HEALER)

        for char in (healer, sub_dps, main_dps, forced):
            char.last_switch_time = time.time()
        combat.chars = [current, healer, sub_dps, main_dps, forced]
        self.assertEqual(combat._choose_switch_target(current, True), forced)

        combat.chars = [current, healer, sub_dps, main_dps]
        self.assertEqual(combat._choose_switch_target(current, True), healer)

        blocked_main_dps = BlockedChar(task, 3, char_type=CharType.MAIN_DPS)
        combat.chars = [current, healer, sub_dps, blocked_main_dps]
        self.assertEqual(combat._choose_switch_target(current, True), healer)

        blocked_sub_dps = BlockedChar(task, 2, char_type=CharType.SUB_DPS)
        combat.chars = [current, healer, blocked_sub_dps, main_dps]
        self.assertEqual(combat._choose_switch_target(current, True), healer)

        combat.chars = [current, healer, blocked_sub_dps, blocked_main_dps]
        self.assertEqual(combat._choose_switch_target(current, True), healer)

        blocked_healer = BlockedChar(task, 1, char_type=CharType.HEALER)
        combat.chars = [current, blocked_healer, blocked_sub_dps, blocked_main_dps]
        self.assertEqual(combat._choose_switch_target(current, True), current)

    def test_priority_hooks_for_ciaccona_and_phrolova(self):
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
        self.assertEqual(ciaccona.get_switch_priority(current_char=current, has_intro=False), SwitchPriority.NO)

        phrolova = Phrolova(task, 2)
        phrolova.last_liberation = time.time() - 5
        self.assertEqual(phrolova.get_switch_priority(current_char=current, has_intro=False), SwitchPriority.NO)

        phrolova.last_liberation = time.time() - 15
        self.assertEqual(phrolova.get_switch_priority(current_char=current, has_intro=True), SwitchPriority.MUST)
        self.assertEqual(phrolova.get_switch_priority(current_char=current, has_intro=False), SwitchPriority.NO)

        phrolova.last_liberation = time.time() - 25
        self.assertEqual(phrolova.get_switch_priority(current_char=current, has_intro=True), SwitchPriority.MUST)

    def test_linnai_waits_after_resonance_kick(self):
        class Task:
            def wait_until(self, condition, post_action=None, time_out=0, **kwargs):
                return condition()

            def jump(self):
                pass

        class TestLynae(Lynae):
            def __init__(self):
                super().__init__(Task(), 0)
                self.actions = []
                self.resonance_clicks = 0

            def check_res(self):
                return True

            def is_color_full(self):
                return True

            def is_forte_full(self):
                return False

            def is_con_full(self):
                return False

            def click_resonance(self, **kwargs):
                self.resonance_clicks += 1
                return True, 0, False

            def click_liberation(self, **kwargs):
                return False

            def click(self, *args, **kwargs):
                pass

            def sleep(self, sec, check_combat=True):
                self.actions.append(('sleep', sec))

            def wait_down(self, click=True):
                self.actions.append(('wait_down', click))

        lynae = TestLynae()
        self.assertTrue(lynae.perform_under_intro())
        self.assertEqual(lynae.resonance_clicks, 2)
        self.assertEqual(lynae.actions, [('sleep', 0.3), ('wait_down', True),
                                          ('sleep', 0.3), ('wait_down', True)])

    def test_linnai_waits_longer_after_aemeath_outro(self):
        class Task:
            def __init__(self):
                self.wait_time_out = None

            def wait_until(self, condition, post_action=None, time_out=0, **kwargs):
                self.wait_time_out = time_out
                return condition()

        class TestLynae(Lynae):
            def __init__(self, task):
                super().__init__(task, 0)
                self.has_intro = True
                self.check_count = 0

            def check_res(self):
                self.check_count += 1
                return self.check_count >= 2

            def check_outro(self):
                return 'char_aemeath'

            def click_with_interval(self, interval=0.1):
                pass

        task = Task()
        lynae = TestLynae(task)
        self.assertTrue(lynae.wait_for_accelerate_ready())
        self.assertEqual(task.wait_time_out, lynae.AEMEATH_INTRO_RES_WAIT)

    def test_linnai_check_res_falls_back_to_long_target_box(self):
        class Box:
            def __init__(self, name):
                self.name = name

        class Match:
            name = 'has_target'

        class Task:
            def in_team_and_world(self):
                return True

            def get_target_names(self):
                return 'has_target', 'no_target'

            def get_box_by_name(self, name):
                return Box(name)

            def find_best_match_in_box(self, box, names, threshold=0.6):
                if box.name == 'box_target_enemy_long':
                    return Match()
                return None

            def find_one(self, *args, **kwargs):
                return None

            def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
                return 999

        lynae = Lynae(Task(), 0)
        self.assertTrue(lynae.check_res())

    def test_intro_does_not_switch_to_phrolova_during_liberation_lock(self):
        class Task:
            name = None

            def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
                if start < 0:
                    return 10000
                return time.time() - start

        task = Task()
        combat = AutoCombatTask.__new__(AutoCombatTask)
        current = BaseChar(task, 0, char_name='char_shorekeeper', char_type=CharType.HEALER)
        phrolova = Phrolova(task, 1, char_type=CharType.MAIN_DPS)
        phrolova.last_liberation = time.time() - 5
        combat.chars = [current, phrolova]

        self.assertEqual(phrolova.get_switch_priority(current_char=current, has_intro=True), SwitchPriority.NO)
        self.assertEqual(combat._choose_switch_target(current, True), current)

    def test_phrolova_nightmare_nest_does_not_cancel_liberation(self):
        class Task:
            name = "Nightmare Nest Task"

            def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
                if start < 0:
                    return 10000
                return time.time() - start

        class TestPhrolova(Phrolova):
            def __init__(self):
                super().__init__(Task(), 0)
                self.actions = []

            def flying(self):
                return False

            def liberation_available(self, check_color=True):
                return True

            def click_liberation(self, **kwargs):
                self.actions.append(('liberation', kwargs))
                return True

            def continues_click(self, key, duration, interval=0.1):
                self.actions.append(('continues_click', key, duration))

            def switch_next_char(self, *args, **kwargs):
                self.actions.append(('switch', {}))

        phrolova = TestPhrolova()
        phrolova.do_perform()

        self.assertEqual(phrolova.actions, [
            ('liberation', {'wait_if_cd_ready': 0}),
            ('switch', {}),
        ])

    def test_check_combat_respects_skip_flag(self):
        combat = AutoCombatTask.__new__(AutoCombatTask)
        combat._in_combat = True
        combat.skip_combat_check = True
        combat.in_combat = lambda: False

        def raise_not_in_combat(message):
            raise NotInCombatException(message)

        combat.raise_not_in_combat = raise_not_in_combat

        combat.check_combat()

    def test_shorekeeper_intro_restores_skip_flag_on_error(self):
        class Task:
            skip_combat_check = False
            name = None

            def in_team_and_world(self):
                return False

            def wait_in_team_and_world(self, **kwargs):
                raise RuntimeError('intro wait failed')

        shorekeeper = Shorekeeper(Task(), 0)
        shorekeeper.has_intro = True

        with self.assertRaises(RuntimeError):
            shorekeeper.do_perform()

        self.assertFalse(shorekeeper.task.skip_combat_check)

    def test_shorekeeper_skips_combat_check_during_intro_or_airborne(self):
        class Task:
            has_lavitator = False

        shorekeeper = Shorekeeper(Task(), 0)
        shorekeeper.has_intro = True
        self.assertTrue(shorekeeper.skip_combat_check())

        shorekeeper.has_intro = False
        shorekeeper.flying = lambda: True
        self.assertTrue(shorekeeper.skip_combat_check())

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
        self.assertEqual(self.task.chars[0].name, 'LuukHerssen')

        has_cd = self.task.chars[0].has_cd('liberation')
        time.sleep(1)
        self.task.screenshot('click_liberation', show_box=True)
        self.assertTrue(has_cd)


if __name__ == '__main__':
    unittest.main()
