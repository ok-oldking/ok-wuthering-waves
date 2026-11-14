import copy
import tempfile
import unittest

from ok.util.config import Config
from src.task.BaseWWTask import BaseWWTask
from src.task.DailyTask import DailyTask
from src.task.DomainTask import DomainTask
from src.task.TacetTask import TacetTask
from src.task.DoubleDropRules import (
    DOUBLE_DROP_DEFAULTS,
    DOUBLE_DROP_FORGERY_COUNT,
    DOUBLE_DROP_FORGERY_NUMBER,
    DOUBLE_DROP_RULES,
    DOUBLE_DROP_SIMULATION_COUNT,
    DOUBLE_DROP_SIMULATION_MATERIAL,
    DOUBLE_DROP_TACET_COUNT,
    DOUBLE_DROP_TACET_NUMBER,
    FORGERY,
    SIMULATION,
    TACET,
    build_double_drop_plan,
)


def rule_config(**overrides):
    config = copy.deepcopy(DOUBLE_DROP_DEFAULTS)
    config.update(overrides)
    return config


class FakeFarmTask:
    def __init__(self, stamina_once=40):
        self.stamina_once = stamina_once
        self.info = {'used stamina': 0}
        self.calls = []

    def _farm(self, name, daily, used_stamina, config, max_runs):
        self.calls.append({'name': name, 'config': copy.deepcopy(config), 'max_runs': max_runs})
        self.info['used stamina'] = self.info.get('used stamina', 0) + max_runs * self.stamina_once

    def farm_simulation(self, **kwargs):
        self._farm(SIMULATION, **kwargs)

    def farm_forgery(self, **kwargs):
        self._farm(FORGERY, **kwargs)

    def farm_tacet(self, **kwargs):
        self._farm(TACET, **kwargs)


class FakeDailyTask:
    build_double_drop_plan_for_daily = DailyTask.build_double_drop_plan_for_daily
    run_stamina_farming = DailyTask.run_stamina_farming
    tr_double_drop_error = DailyTask.tr_double_drop_error

    def __init__(self, config, activities=None, recheck=(0, False), recheck_error=False):
        self.config = config
        self.activities = activities or {mode: False for mode in (SIMULATION, FORGERY, TACET)}
        self.recheck = recheck
        self.recheck_error = recheck_error
        self.width, self.height = 1920, 1080
        self.tr = str
        self.plan_calls = 0
        self.activity_reads = 0
        self.original_calls = []
        self.tasks = {mode: FakeFarmTask() for mode in (SIMULATION, FORGERY, TACET)}
        self.logs = []

    def read_double_drop_activities(self):
        self.activity_reads += 1
        return dict(self.activities)

    def run_double_drop_plan(self, plan):
        self.plan_calls += 1
        return DailyTask.run_double_drop_plan(self, plan)

    def open_daily(self):
        if self.recheck_error:
            raise RuntimeError('recheck failed')
        return self.recheck

    def farm_original(self, used_stamina):
        self.original_calls.append(used_stamina)

    def get_double_drop_task(self, mode):
        return self.tasks[mode]

    def info_set(self, *args, **kwargs):
        pass

    def log_info(self, message, *args, **kwargs):
        self.logs.append(('info', message))

    def log_error(self, message, *args, **kwargs):
        self.logs.append(('error', message))

    def screenshot(self, *args, **kwargs):
        pass

    def ensure_main(self, *args, **kwargs):
        pass


class FakeValidatorTask:
    validate = DailyTask.validate
    validate_config = DailyTask.validate_config
    tr_double_drop_error = DailyTask.tr_double_drop_error

    def __init__(self):
        self.config = {}
        self.tr = str


class FakeStaminaTask:
    def __init__(self, current=240):
        self.current = current
        self.clicked = []

    def sleep(self, *args):
        pass

    def get_stamina(self):
        return self.current, 0, self.current

    def click_dialog_right_button(self):
        self.clicked.append('right')

    def click_dialog_left_button(self):
        self.clicked.append('left')

    def wait_feature(self, *args, **kwargs):
        return False


class TestDoubleDropRules(unittest.TestCase):
    def test_force_single_uses_one_run_even_with_full_stamina(self):
        fake = FakeStaminaTask(current=240)
        can_continue, used = BaseWWTask.use_stamina(fake, once=40, must_use=80, force_single=True)
        self.assertEqual(used, 40)
        self.assertEqual(fake.clicked, ['left'])
        self.assertTrue(can_continue)

    def test_invalid_value_is_blocked_and_valid_value_persists(self):
        with tempfile.TemporaryDirectory() as folder:
            fake = FakeValidatorTask()
            config = Config('DoubleDropTest', copy.deepcopy(DOUBLE_DROP_DEFAULTS),
                            folder=folder, validator=fake.validate)
            fake.config = config

            config[DOUBLE_DROP_SIMULATION_COUNT] = 2
            config[DOUBLE_DROP_FORGERY_COUNT] = 2
            self.assertEqual(config[DOUBLE_DROP_FORGERY_COUNT], 0)

            reloaded = Config('DoubleDropTest', copy.deepcopy(DOUBLE_DROP_DEFAULTS),
                              folder=folder, validator=FakeValidatorTask().validate)
            self.assertEqual(reloaded[DOUBLE_DROP_SIMULATION_COUNT], 2)
            self.assertEqual(reloaded[DOUBLE_DROP_FORGERY_COUNT], 0)

    def test_only_active_domains_enter_plan_in_fixed_order(self):
        config = rule_config(**{
            DOUBLE_DROP_SIMULATION_COUNT: 2,
            DOUBLE_DROP_SIMULATION_MATERIAL: 'Weapon EXP',
            DOUBLE_DROP_FORGERY_COUNT: 0,
            DOUBLE_DROP_FORGERY_NUMBER: 4,
            DOUBLE_DROP_TACET_COUNT: 3,
            DOUBLE_DROP_TACET_NUMBER: 2,
        })
        plan = build_double_drop_plan(config, {SIMULATION: True, FORGERY: True, TACET: True})
        self.assertEqual([(item.mode, item.count) for item in plan], [(SIMULATION, 2), (TACET, 3)])
        self.assertEqual(plan[0].config, {'Material Selection': 'Weapon EXP'})
        self.assertEqual(plan[1].config, {'Which Tacet Suppression to Farm': 2})

    def test_plan_rejects_combined_limit_overflow(self):
        config = rule_config(**{DOUBLE_DROP_SIMULATION_COUNT: 3, DOUBLE_DROP_FORGERY_COUNT: 3})
        with self.assertRaises(ValueError):
            build_double_drop_plan(config, {SIMULATION: True, FORGERY: True, TACET: False})

    def test_disabled_keeps_original_logic_without_recognition(self):
        config = rule_config(**{DOUBLE_DROP_RULES: False, DOUBLE_DROP_SIMULATION_COUNT: 2})
        fake = FakeDailyTask(config, {SIMULATION: True, FORGERY: True, TACET: True})
        fake.run_stamina_farming(20)
        self.assertEqual(fake.original_calls, [20])
        self.assertEqual(fake.activity_reads, 0)

    def test_non_16_9_keeps_original_logic_without_recognition(self):
        config = rule_config(**{DOUBLE_DROP_RULES: True, DOUBLE_DROP_TACET_COUNT: 2})
        fake = FakeDailyTask(config, {SIMULATION: False, FORGERY: False, TACET: True})
        fake.width, fake.height = 1920, 1200
        fake.run_stamina_farming(20)
        self.assertEqual(fake.original_calls, [20])
        self.assertEqual(fake.activity_reads, 0)

    def test_invalid_persisted_config_falls_back_to_original(self):
        config = rule_config(**{
            DOUBLE_DROP_RULES: True,
            DOUBLE_DROP_SIMULATION_COUNT: 3,
            DOUBLE_DROP_FORGERY_COUNT: 3,
        })
        fake = FakeDailyTask(config, {SIMULATION: True, FORGERY: True, TACET: True})
        fake.run_stamina_farming(0)
        self.assertEqual(fake.activity_reads, 0)
        self.assertEqual(fake.original_calls, [0])
        self.assertTrue(any(level == 'error' for level, _ in fake.logs))

    def test_enabled_without_matching_activity_keeps_original_logic(self):
        config = rule_config(**{DOUBLE_DROP_RULES: True, DOUBLE_DROP_SIMULATION_COUNT: 2})
        fake = FakeDailyTask(config)
        fake.run_stamina_farming(40)
        self.assertEqual(fake.original_calls, [40])
        self.assertEqual(fake.plan_calls, 0)

    def test_plan_runs_first_then_original_farms_remaining_stamina(self):
        config = rule_config(**{
            DOUBLE_DROP_RULES: True,
            DOUBLE_DROP_SIMULATION_COUNT: 2,
            DOUBLE_DROP_FORGERY_COUNT: 1,
            DOUBLE_DROP_FORGERY_NUMBER: 5,
        })
        fake = FakeDailyTask(config, {SIMULATION: True, FORGERY: True, TACET: True},
                             recheck=(120, False))
        fake.run_stamina_farming(0)
        self.assertEqual(fake.tasks[SIMULATION].calls[0]['max_runs'], 2)
        self.assertEqual(fake.tasks[FORGERY].calls[0]['max_runs'], 1)
        self.assertEqual(fake.tasks[FORGERY].calls[0]['config'], {'Which Forgery Challenge to Farm': 5})
        self.assertEqual(fake.tasks[TACET].calls, [])
        self.assertEqual(fake.original_calls, [120])

    def test_no_original_farm_when_plan_reaches_daily_target(self):
        config = rule_config(**{DOUBLE_DROP_RULES: True, DOUBLE_DROP_TACET_COUNT: 3})
        fake = FakeDailyTask(config, {SIMULATION: False, FORGERY: False, TACET: True},
                             recheck=(180, False))
        fake.run_stamina_farming(60)
        self.assertEqual(fake.plan_calls, 1)
        self.assertEqual(fake.original_calls, [])

    def test_no_original_farm_when_daily_reward_already_ready(self):
        config = rule_config(**{DOUBLE_DROP_RULES: True, DOUBLE_DROP_FORGERY_COUNT: 1})
        fake = FakeDailyTask(config, {SIMULATION: False, FORGERY: True, TACET: False},
                             recheck=(40, True))
        fake.run_stamina_farming(0)
        self.assertEqual(fake.plan_calls, 1)
        self.assertEqual(fake.original_calls, [])

    def test_unreadable_recheck_uses_calculated_usage(self):
        config = rule_config(**{DOUBLE_DROP_RULES: True, DOUBLE_DROP_TACET_COUNT: 2})
        for recheck, recheck_error in (((0, False), False), ((0, False), True)):
            with self.subTest(recheck_error=recheck_error):
                fake = FakeDailyTask(config, {SIMULATION: False, FORGERY: False, TACET: True},
                                     recheck=recheck, recheck_error=recheck_error)
                fake.run_stamina_farming(20)
                self.assertEqual(fake.original_calls, [100])

    def test_plan_uses_only_stamina_delta_from_each_task(self):
        config = rule_config(**{DOUBLE_DROP_RULES: True, DOUBLE_DROP_TACET_COUNT: 1})
        fake = FakeDailyTask(config)
        fake.tasks[TACET].stamina_once = 60
        fake.tasks[TACET].info['used stamina'] = 100
        plan = build_double_drop_plan(config, {SIMULATION: False, FORGERY: False, TACET: True})
        self.assertEqual(DailyTask.run_double_drop_plan(fake, plan), 60)

    def test_domain_farm_stops_at_max_runs_and_forces_last_single(self):
        task = DomainTask.__new__(DomainTask)
        task.stamina_once = 40
        task.teleport_timeout = 100
        task.info = {'used stamina': 0}
        task._domain_runs_completed = 0
        task.tr = str
        task.use_stamina_calls = []
        task.exit_clicks = []
        noop = lambda *args, **kwargs: None
        for name in ('walk_until_f', 'pick_f', 'combat_once', 'sleep', 'walk_to_treasure',
                     'wait_in_team_and_world', 'make_sure_in_world', 'log_info'):
            setattr(task, name, noop)
        task.info_incr = lambda key, inc=0: task.info.__setitem__(key, task.info.get(key, 0) + inc)
        task.wait_feature = noop
        task.click = lambda *args, **kwargs: task.exit_clicks.append(args[:2])

        def use_stamina(once, must_use, force_single=False):
            task.use_stamina_calls.append(force_single)
            return True, 80 if len(task.use_stamina_calls) == 1 else 40

        task.use_stamina = use_stamina
        finished, _ = DomainTask.farm_in_domain(task, must_use=120, max_runs=3)
        self.assertTrue(finished)
        self.assertEqual(task.info['used stamina'], 120)
        self.assertEqual(task.use_stamina_calls, [False, True])
        self.assertIn((0.42, 0.84), task.exit_clicks)

    def test_tacet_farm_stops_at_max_runs(self):
        task = TacetTask.__new__(TacetTask)
        task.stamina_once = 60
        task.info = {'used stamina': 0}
        task.tr = str
        task.use_stamina_calls = []
        task.exit_clicks = []
        noop = lambda *args, **kwargs: None
        for name in ('sleep', 'openF2Book', 'open_boss_book', 'click_team_challenge',
                     'wait_in_team_and_world', 'walk_to_treasure', 'pick_f',
                     'wait_click_skip_dialog_confirm', 'teleport_to_tacet', 'log_info'):
            setattr(task, name, noop)
        task.info_incr = lambda key, inc=0: task.info.__setitem__(key, task.info.get(key, 0) + inc)
        task.get_stamina = lambda: (240, 0, 240)
        task.has_claim_stamina = lambda: True
        task.combat_once = lambda *args, **kwargs: True
        task.click_relative = lambda *args, **kwargs: task.exit_clicks.append(args[:2])

        def use_stamina(once, must_use, force_single=False):
            task.use_stamina_calls.append(force_single)
            return True, 120

        task.use_stamina = use_stamina
        task.farm_tacet(config={'Which Tacet Suppression to Farm': 1}, max_runs=2)
        self.assertEqual(task.info['used stamina'], 120)
        self.assertEqual(task.use_stamina_calls, [False])
        self.assertIn((0.365, 0.853), task.exit_clicks)


if __name__ == '__main__':
    unittest.main()
