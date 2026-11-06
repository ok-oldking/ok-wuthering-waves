import re


from ok import Logger, TaskDisabledException
from src.task.BaseWWTask import number_re
from src.task.FarmEchoTask import FarmEchoTask
from src.task.ForgeryTask import ForgeryTask
from src.task.GardenTask import GardenTask
from src.task.MergeEchoTask import MergeEchoTask
from src.task.NightmareNestTask import NightmareNestTask
from src.task.TacetTask import TacetTask
from src.task.SimulationTask import SimulationTask
from src.task.WWOneTimeTask import WWOneTimeTask
from src.task.BaseCombatTask import BaseCombatTask
from src.task.DoubleDropRules import (
    DOUBLE_DROP_BADGE_ROIS,
    DOUBLE_DROP_CONFIG_KEYS,
    DOUBLE_DROP_DEFAULTS,
    DOUBLE_DROP_FORGERY_COUNT,
    DOUBLE_DROP_FORGERY_NUMBER,
    DOUBLE_DROP_RULES,
    DOUBLE_DROP_SIMULATION_COUNT,
    DOUBLE_DROP_SIMULATION_MATERIAL,
    DOUBLE_DROP_TACET_COUNT,
    DOUBLE_DROP_TACET_NUMBER,
    FORGERY,
    MODE_ORDER,
    SIMULATION,
    TACET,
    UP_GOLD,
    UP_PATTERN,
    build_double_drop_plan as create_double_drop_plan,
    is_non_negative_int,
    is_up_badge,
    validate_double_drop_config,
)
from src.task.task_icons import task_icon

logger = Logger.get_logger(__name__)

CHECK_WEEKLY_GARDEN = 'Check Weekly Garden'
AUTO_FARM_NIGHTMARE_NEST = 'Auto Farm all Nightmare Nest'
MERGE_ECHO_IF_DISCARDED_OVER_1000 = 'Merge Echo If discarded > 1000'
TELEPORT_AND_FARM_4C_ECHO = 'Teleport and Farm 4C Echo'
ADDITIONAL_TASKS = 'Additional Tasks to Run After Daily Task'


class DailyTask(WWOneTimeTask, BaseCombatTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "📅 Daily Task"
        self.icon = task_icon('daily')
        self.group_name = 'Daily Activities'
        self.group_icon = task_icon('category-daily')
        self.support_schedule_task = True
        self.support_tasks = ["Tacet Suppression", "Forgery Challenge", "Simulation Challenge"]
        self.default_config = {
            'Which to Farm': self.support_tasks[0],
            'Which Tacet Suppression to Farm': 1,  # starts with 1
            'Which Forgery Challenge to Farm': 1,  # starts with 1
            'Material Selection': 'Shell Credit',
            'Farm Nightmare Nest for Daily Echo': True,
            **DOUBLE_DROP_DEFAULTS,
            ADDITIONAL_TASKS: [CHECK_WEEKLY_GARDEN],
        }
        self.config_description = {
            'Which Tacet Suppression to Farm': 'The Tacet Suppression number in the F2 list.',
            'Which Forgery Challenge to Farm': 'The Forgery Challenge number in the F2 list.',
            'Material Selection': 'Resonator EXP / Weapon EXP / Shell Credit',
            'Farm Nightmare Nest for Daily Echo': 'Farm 1 Echo from Nightmare Nest to complete Daily Task when needed.',
            DOUBLE_DROP_RULES: 'Detect the UP event badge on the Material Acquisition page and farm those domains '
                               'first. The original "Which to Farm" setting is not changed.',
            DOUBLE_DROP_SIMULATION_COUNT: 'Simulation Challenge runs during the event, 0-3. Simulation + Forgery '
                                          'cannot exceed 3 in total.',
            DOUBLE_DROP_SIMULATION_MATERIAL: 'Material type for Simulation Challenge.',
            DOUBLE_DROP_FORGERY_COUNT: 'Forgery Challenge runs during the event, 0-3. Simulation + Forgery cannot '
                                       'exceed 3 in total.',
            DOUBLE_DROP_FORGERY_NUMBER: 'The Forgery Challenge number in the F2 list.',
            DOUBLE_DROP_TACET_COUNT: 'Tacet Suppression runs during the event, 0-3.',
            DOUBLE_DROP_TACET_NUMBER: 'The Tacet Suppression number in the F2 list.',
            ADDITIONAL_TASKS: 'Select optional tasks. Nightmare Nest runs before stamina farming to help complete '
                              'the daily task; the other tasks run afterward.',
        }
        material_option_list = ['Resonator EXP', 'Weapon EXP', 'Shell Credit']
        self.config_type = {
            'Which to Farm': {
                'type': "drop_down",
                'options': self.support_tasks,
                'sub_configs': {
                    'Tacet Suppression': ['Which Tacet Suppression to Farm'],
                    'Forgery Challenge': ['Which Forgery Challenge to Farm'],
                    'Simulation Challenge': [
                        'Material Selection'],
                }
            },
            'Material Selection': {
                'type': 'drop_down',
                'options': material_option_list
            },
            DOUBLE_DROP_RULES: {
                'sub_configs': {
                    True: list(DOUBLE_DROP_CONFIG_KEYS),
                },
            },
            DOUBLE_DROP_SIMULATION_MATERIAL: {
                'type': 'drop_down',
                'options': material_option_list,
            },
            DOUBLE_DROP_SIMULATION_COUNT: {'min': 0, 'max': 3},
            DOUBLE_DROP_FORGERY_COUNT: {'min': 0, 'max': 3},
            DOUBLE_DROP_TACET_COUNT: {'min': 0, 'max': 3},
            DOUBLE_DROP_FORGERY_NUMBER: {'min': 1},
            DOUBLE_DROP_TACET_NUMBER: {'min': 1},
            ADDITIONAL_TASKS: {
                'type': 'multi_selection',
                'options': [
                    CHECK_WEEKLY_GARDEN,
                    AUTO_FARM_NIGHTMARE_NEST,
                    MERGE_ECHO_IF_DISCARDED_OVER_1000,
                    TELEPORT_AND_FARM_4C_ECHO,
                ],
            },
        }
        self.add_exit_after_config()
        self.description = "Login, claim monthly card, farm echo, and claim daily reward"

    def run(self):
        self.validate_additional_tasks()

        WWOneTimeTask.run(self)
        self.logged_in = False
        self.ensure_main(time_out=180)

        additional_tasks = self.config.get(ADDITIONAL_TASKS) or []
        condition1 = AUTO_FARM_NIGHTMARE_NEST in additional_tasks
        condition2 = self.config.get('Farm Nightmare Nest for Daily Echo')

        used_stamina, daily_reward_ready = self.open_daily()
        need_stamina = not daily_reward_ready and used_stamina < 180
        need_nightmare = condition1 or (
                condition2
                and not daily_reward_ready
                and self.config.get('Which to Farm', self.support_tasks[0]) != self.support_tasks[0]
        )

        if need_nightmare:
            try:
                # 劫持 NightmareNestTask.ensure_main 避免梦魇打完关书
                self.get_task_by_class(NightmareNestTask).ensure_main = lambda *args, **kwargs: None

                if condition1:
                    self.log_debug('Auto Farm all Nightmare Nest')
                    self.run_task_by_class(NightmareNestTask)
                elif condition2:
                    self.log_debug('Farm Nightmare Nest for Daily Echo')
                    self.get_task_by_class(NightmareNestTask).run_capture_mode()
            except TaskDisabledException:
                raise
            except Exception as e:
                self.log_error(self.tr('NightmareNestTask Failed'), e)
                self.screenshot('NightmareNestTask')
                self.ensure_main(time_out=180)
            finally:
                # 还原 ensure_main，防范实例状态污染
                self.get_task_by_class(NightmareNestTask).__dict__.pop('ensure_main', None)

        if need_stamina:
            self.run_stamina_farming(used_stamina)
            self.sleep(4)

        self.claim_daily()

        self.claim_mail()
        self.sleep(1)
        self.claim_battle_pass()
        self.run_additional_tasks()
        self.log_info(self.tr('Daily Task Completed'), notify=True)

    def validate_config(self, key, value):
        return validate_double_drop_config(key, value, self.config or {})

    def run_stamina_farming(self, used_stamina):
        plan = self.build_double_drop_plan_for_daily()
        if plan:
            plan_used = self.run_double_drop_plan(plan)
            try:
                recheck_used, daily_reward_ready = self.open_daily()
                used_stamina = recheck_used if recheck_used > 0 else used_stamina + plan_used
            except TaskDisabledException:
                raise
            except Exception as e:
                daily_reward_ready = False
                used_stamina += plan_used
                self.log_error('Double drop: failed to recheck daily stamina, use calculated usage', e)
            self.info_set('used stamina after double drop', used_stamina)
            if daily_reward_ready or used_stamina >= 180:
                self.log_info('Double drop plan completed, daily stamina requirement is met')
                return
            self.log_info(f'Double drop plan completed, continue original farming at {used_stamina}/180')
        self.farm_original(used_stamina)

    def build_double_drop_plan_for_daily(self):
        if not self.config.get(DOUBLE_DROP_RULES):
            return []
        counts = [self.config.get(key, 0) for key in (
            DOUBLE_DROP_SIMULATION_COUNT, DOUBLE_DROP_FORGERY_COUNT, DOUBLE_DROP_TACET_COUNT)]
        if not any(is_non_negative_int(count) and count > 0 for count in counts):
            self.log_info('Double drop rules enabled but every count is 0, keep original daily logic')
            return []
        for key in DOUBLE_DROP_CONFIG_KEYS:
            error = validate_double_drop_config(key, self.config.get(key), self.config)
            if error:
                self.log_error(f'Invalid double drop config: {error} Keep original daily logic')
                return []
        activities = self.read_double_drop_activities()
        try:
            plan = create_double_drop_plan(self.config, activities)
        except ValueError as e:
            self.log_error(f'Invalid double drop plan: {e} Keep original daily logic')
            return []
        if plan:
            self.log_info('Double drop plan: ' + ', '.join(f'{item.mode} x{item.count}' for item in plan))
        return plan

    def read_double_drop_activities(self):
        activities = {mode: False for mode in MODE_ORDER}
        try:
            self.openF2Book('gray_book_boss')
            self.next_frame()
            self.screenshot('double_drop_activity_badges')
            activities = self.detect_double_drop_activities_from_frame()
            if not any(activities.values()):
                self.log_info('Double drop: no activity badge detected, keep original daily logic')
            return activities
        except TaskDisabledException:
            raise
        except Exception as e:
            self.log_error('Double drop recognition failed, keep original daily logic', e)
            self.screenshot('double_drop_recognition_failed')
            return activities
        finally:
            try:
                self.ensure_main(time_out=60)
            except TaskDisabledException:
                raise
            except Exception as e:
                self.log_error('Double drop: failed to return to main after recognition', e)

    def detect_double_drop_activities_from_frame(self):
        activities = {}
        for mode in MODE_ORDER:
            try:
                box = self.box_of_screen(*DOUBLE_DROP_BADGE_ROIS[mode], name=f'double_drop_{mode}')
                texts = self.ocr(box=box, match=UP_PATTERN, log=getattr(self, 'debug', False))
                gold_ratio = self.calculate_color_percentage(UP_GOLD, box)
                activities[mode] = is_up_badge([text.name for text in texts], gold_ratio)
                self.log_info(f'Double drop {mode}: UP={bool(texts)} gold={gold_ratio:.4f} '
                              f'active={activities[mode]}')
            except TaskDisabledException:
                raise
            except Exception as e:
                activities[mode] = False
                self.log_error(f'Double drop {mode} recognition failed, treat as inactive', e)
        return activities

    def run_double_drop_plan(self, plan):
        total_used = 0
        for item in plan:
            task = None
            used_before = 0
            try:
                task = self.get_double_drop_task(item.mode)
                if task is None:
                    raise RuntimeError(f'{item.mode} task is not registered')
                used_before = max(0, int(task.info.get('used stamina', 0) or 0))
                self.info_set('current task', f'double drop {item.mode}')
                self.log_info(f'Double drop farming {item.mode} x{item.count}, config={item.config}')
                plan_used_stamina = max(0, 180 - item.count * task.stamina_once)
                if item.mode == SIMULATION:
                    task.farm_simulation(daily=True, used_stamina=plan_used_stamina,
                                         config=item.config, max_runs=item.count)
                elif item.mode == FORGERY:
                    task.farm_forgery(daily=True, used_stamina=plan_used_stamina,
                                      config=item.config, max_runs=item.count)
                elif item.mode == TACET:
                    task.farm_tacet(daily=True, used_stamina=plan_used_stamina,
                                    config=item.config, max_runs=item.count)
            except TaskDisabledException:
                raise
            except Exception as e:
                self.log_error(f'Double drop {item.mode} failed', e)
                self.screenshot('double_drop_failed_' + item.mode.replace(' ', '_'))
                self.ensure_main(time_out=180)
            finally:
                if task is not None:
                    used_after = max(0, int(task.info.get('used stamina', 0) or 0))
                    total_used += max(0, used_after - used_before)
        return total_used

    def get_double_drop_task(self, mode):
        if mode == SIMULATION:
            return self.get_task_by_class(SimulationTask)
        if mode == FORGERY:
            return self.get_task_by_class(ForgeryTask)
        if mode == TACET:
            return self.get_task_by_class(TacetTask)
        return None

    def farm_original(self, used_stamina):
        target = self.config.get('Which to Farm', self.support_tasks[0])
        if target == self.support_tasks[0]:
            self.get_task_by_class(TacetTask).farm_tacet(daily=True, used_stamina=used_stamina,
                                                         config=self.config)
        elif target == self.support_tasks[1]:
            self.get_task_by_class(ForgeryTask).farm_forgery(daily=True, used_stamina=used_stamina,
                                                             config=self.config)
        else:
            self.get_task_by_class(SimulationTask).farm_simulation(daily=True, used_stamina=used_stamina,
                                                                   config=self.config)

    def validate_additional_tasks(self):
        additional_tasks = self.config.get(ADDITIONAL_TASKS) or []
        if TELEPORT_AND_FARM_4C_ECHO in additional_tasks:
            farm_echo_task = self.get_task_by_class(FarmEchoTask)
            if farm_echo_task.config.get('Teleport to Boss', 'No') == 'No':
                raise Exception(
                    self.tr(
                        'Teleport and Farm 4C Echo requires "Teleport to Boss" to be enabled in Farm Echo Task.'
                    )
                )
        if AUTO_FARM_NIGHTMARE_NEST in additional_tasks:
            nightmare_task = self.get_task_by_class(NightmareNestTask)
            if not nightmare_task.config.get('Which to Farm'):
                raise Exception(
                    self.tr(
                        'Auto Farm all Nightmare Nest requires at least one "Which to Farm" option.'
                    )
                )
        return True

    def run_additional_tasks(self):
        additional_tasks = self.config.get(ADDITIONAL_TASKS) or []
        if CHECK_WEEKLY_GARDEN in additional_tasks:
            self.check_weekly_garden()
        if MERGE_ECHO_IF_DISCARDED_OVER_1000 in additional_tasks:
            self.check_discarded_echo()
        if TELEPORT_AND_FARM_4C_ECHO in additional_tasks:
            self.log_info(self.tr('Daily task completed, start teleport to farm 4C echo'), notify=True)
            self.run_task_by_class(FarmEchoTask)

    def check_weekly_garden(self):
        self.info_set('current task', 'check weekly garden')
        self.log_info(self.tr('check weekly garden'))
        try:
            garden_task = self.get_task_by_class(GardenTask)
            garden_task.open_garden_weekly_page()
            if garden_task.is_weekly_garden_completed():
                self.log_info(self.tr('weekly garden already completed'))
                return
            self.log_info(self.tr('weekly garden not completed, run GardenTask'))
            self.run_task_by_class(GardenTask)
        except TaskDisabledException:
            raise
        except Exception as e:
            self.log_error(self.tr('GardenTask Failed'), e)
            self.screenshot('GardenTask')
            self.ensure_main(time_out=180)

    def check_discarded_echo(self):
        self.info_set('current task', 'check discarded echo')
        self.log_info(self.tr('check discarded echo'))
        merge_echo_task = self.get_task_by_class(MergeEchoTask)
        old_notify_if_not_enough = merge_echo_task.notify_if_not_enough
        try:
            merge_echo_task.notify_if_not_enough = False
            self.run_task_by_class(MergeEchoTask)
        except TaskDisabledException:
            raise
        except Exception as e:
            self.log_error(self.tr('MergeEchoTask Failed'), e)
            self.screenshot('MergeEchoTask')
            self.ensure_main(time_out=180)
        finally:
            merge_echo_task.notify_if_not_enough = old_notify_if_not_enough

    def claim_battle_pass(self):
        self.log_info(self.tr('battle pass'))
        self.send_key_down('alt')
        self.sleep(0.05)
        self.click_relative(0.86, 0.05)
        self.send_key_up('alt')
        if not self.wait_ocr(0.2, 0.13, 0.32, 0.22, match=re.compile(r'\d+'), settle_time=1, raise_if_not_found=False):
            self.log_error(self.tr('can not battle pass, maybe ended'))
        else:
            self.click_relative(0.04, 0.3, after_sleep=1)
            self.click_relative(0.68, 0.91, hcenter=True, after_sleep=3)
            self.click_relative(0.04, 0.17, after_sleep=2)
            self.click_relative(0.68, 0.91, hcenter=True, after_sleep=2)
            self.wait_ocr(0.2, 0.13, 0.32, 0.22, match=re.compile(r'\d+'),
                          post_action=lambda: self.click(0.68, 0.91, after_sleep=1), settle_time=1,
                          raise_if_not_found=False)
        self.ensure_main()

    def open_daily(self):
        self.log_info(self.tr('open_daily'))
        self.openF2Book("gray_book_quest")
        self.click(0.17, 0.12, after_sleep=1)
        progress = self.ocr(0.1, 0.1, 0.5, 0.75, match=re.compile(r'^(\d+)/180$'))
        if not progress:
            self.click(0.974, 0.6, after_sleep=1)
            progress = self.ocr(0.1, 0.1, 0.5, 0.75, match=re.compile(r'^(\d+)/180$'))
        if progress:
            current = int(progress[0].name.split('/')[0])
        else:
            current = 0
        self.info_set('current daily progress', current)
        return current, self.get_total_daily_points() >= 100
        # 请注意：如果任务【累计消耗180点结晶波片】已完成，current 也可能为 0，因为翻页后也有可能识别不到已用体力。

    def get_total_daily_points(self):
        points_boxes = self.ocr(0.19, 0.8, 0.30, 0.93, match=number_re)
        if points_boxes:
            try:
                points = int(re.sub(r'\D', '', points_boxes[0].name))
            except Exception:
                points = 0
        else:
            points = 0
        self.info_set('total daily points', points)
        return points

    def claim_daily(self):
        self.info_set('current task', 'claim daily')
        self.openF2Book('gray_book_quest')
        if not self.find_one('boss_proceed', box=self.box_of_screen(0.803, 0.189, 0.960, 0.312)):
            self.log_info(self.tr('no_boss_proceed, click claim'))
            # Click [Guidebook] in [Terminal] interface
            self.click(0.885, 0.250, after_sleep=2)
        self.log_info(self.tr('claim daily reward via  coordinate'))
        self.click(0.930, 0.882, after_sleep=1)
        self.ensure_main(time_out=10)

    def claim_mail(self):
        self.info_set('current task', 'claim mail')
        self.back(after_sleep=1.5)
        self.click(0.64, 0.95, after_sleep=1)
        self.click(0.14, 0.9, after_sleep=1)
        self.ensure_main(time_out=10)


from ok import run_task
from config import config

if __name__ == "__main__":
    run_task(config, task=DailyTask, debug=True)
