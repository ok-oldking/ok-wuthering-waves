import re

from qfluentwidgets import FluentIcon

from ok import Logger, TaskDisabledException
from src.task.BaseWWTask import number_re
from src.task.FarmEchoTask import FarmEchoTask
from src.task.ForgeryTask import ForgeryTask
from src.task.GardenTask import GardenTask
from src.task.NightmareNestTask import NightmareNestTask
from src.task.TacetTask import TacetTask
from src.task.SimulationTask import SimulationTask
from src.task.WWOneTimeTask import WWOneTimeTask
from src.task.BaseCombatTask import BaseCombatTask

logger = Logger.get_logger(__name__)


class DailyTask(WWOneTimeTask, BaseCombatTask):
    TACET_TASK = "Tacet Suppression"
    FORGERY_TASK = "Forgery Challenge"
    SIMULATION_TASK = "Simulation Challenge"
    DAILY_PRIORITY_MODE = "Complete Daily 180"
    CLAIM_PRIORITY_MODE = "Finish Planned Claims"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Daily Task"
        self.group_name = "Daily"
        self.group_icon = FluentIcon.CALENDAR
        self.icon = FluentIcon.CAR
        self.support_schedule_task = True
        self.support_tasks = [self.TACET_TASK, self.FORGERY_TASK, self.SIMULATION_TASK]
        self.default_config = {
            'Which to Farm': [self.support_tasks[0]],
            'Which Tacet Suppression to Farm': 1,  # starts with 1
            'Tacet Suppression Runs': 3,
            'Which Forgery Challenge to Farm': 1,  # starts with 1
            'Forgery Challenge Runs': 5,
            'Material Selection': 'Shell Credit',
            'Simulation Challenge Runs': 5,
            'Farm Goal': self.DAILY_PRIORITY_MODE,
            'Auto Farm all Nightmare Nest': False,
            'Farm Nightmare Nest for Daily Echo': True,
            'Check Weekly Garden': True,
            'Continue Farm After Daily': False,
        }
        self.config_description = {
            'Which to Farm': 'Select one or more tasks to rotate through for daily stamina spending. Runs mean reward claims. The task auto-uses double rewards when possible. If planned claims are not enough, the last selected task continues until daily stamina is complete.',
            'Which Tacet Suppression to Farm': 'The Tacet Suppression number in the F2 list.',
            'Which Forgery Challenge to Farm': 'The Forgery Challenge number in the F2 list.',
            'Material Selection': 'Resonator EXP / Weapon EXP / Shell Credit',
            'Farm Goal': 'Stop at daily 180, or finish every planned reward claim.',
            'Farm Nightmare Nest for Daily Echo': 'Farm 1 Echo from Nightmare Nest to complete Daily Task when needed.',
            'Check Weekly Garden': 'After claiming daily rewards, check weekly Garden progress and run Garden Task '
                                   'if 6000 points has not been reached.',
            'Continue Farm After Daily': 'After completing daily activity, continue farming stamina until depleted.'
        }
        material_option_list = ['Resonator EXP', 'Weapon EXP', 'Shell Credit']
        self.config_type = {
            'Which to Farm': {
                'type': "multi_selection",
                'options': self.support_tasks,
                'sub_configs': {
                    self.TACET_TASK: ['Which Tacet Suppression to Farm', 'Tacet Suppression Runs'],
                    self.FORGERY_TASK: ['Which Forgery Challenge to Farm', 'Forgery Challenge Runs'],
                    self.SIMULATION_TASK: ['Material Selection', 'Simulation Challenge Runs'],
                },
            },
            'Material Selection': {
                'type': 'drop_down',
                'options': material_option_list
            },
            'Farm Goal': {
                'type': 'drop_down',
                'options': [self.DAILY_PRIORITY_MODE, self.CLAIM_PRIORITY_MODE],
            },
            'Tacet Suppression Runs': {'min': 0},
            'Forgery Challenge Runs': {'min': 0},
            'Simulation Challenge Runs': {'min': 0},
        }
        self.add_exit_after_config()
        self.description = "Login, claim monthly card, farm echo, and claim daily reward"

    def run(self):
        WWOneTimeTask.run(self)
        self.logged_in = False
        self.ensure_main(time_out=180)
        selected_tasks = self._normalize_selected_tasks(self.config.get('Which to Farm'))

        condition1 = self.config.get('Auto Farm all Nightmare Nest')
        condition2 = self.config.get('Farm Nightmare Nest for Daily Echo')

        used_stamina, daily_reward_ready = self.open_daily()
        need_stamina = not daily_reward_ready and used_stamina < 180
        need_nightmare = condition1 or (
                condition2
                and not daily_reward_ready
                and self.TACET_TASK not in selected_tasks
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
                self.log_error("NightmareNestTask Failed", e)
                self.screenshot('NightmareNestTask')
                self.ensure_main(time_out=180)
            finally:
                # 还原 ensure_main，防范实例状态污染
                self.get_task_by_class(NightmareNestTask).__dict__.pop('ensure_main', None)

        continue_farm = self.config.get('Continue Farm After Daily', False)

        if need_stamina or continue_farm:
            self.run_daily_farm_rotation(selected_tasks, used_stamina, continue_until_depleted=continue_farm)

        self.claim_daily()

        self.claim_mail()
        self.sleep(1)
        self.claim_battle_pass()
        self.check_weekly_garden()
        self.log_info('Task completed', notify=True)

    def check_weekly_garden(self):
        if not self.config.get('Check Weekly Garden', True):
            return
        self.info_set('current task', 'check weekly garden')
        self.log_info('check weekly garden')
        try:
            garden_task = self.get_task_by_class(GardenTask)
            garden_task.open_garden_weekly_page()
            if garden_task.is_weekly_garden_completed():
                self.log_info('weekly garden already completed')
                return
            self.log_info('weekly garden not completed, run GardenTask')
            self.run_task_by_class(GardenTask)
        except TaskDisabledException:
            raise
        except Exception as e:
            self.log_error("GardenTask Failed", e)
            self.screenshot('GardenTask')
            self.ensure_main(time_out=180)

    def claim_battle_pass(self):
        self.log_info('battle pass')
        self.send_key_down('alt')
        self.sleep(0.05)
        self.click_relative(0.86, 0.05)
        self.send_key_up('alt')
        if not self.wait_ocr(0.2, 0.13, 0.32, 0.22, match=re.compile(r'\d+'), settle_time=1, raise_if_not_found=False):
            self.log_error('can not battle pass, maybe ended')
        else:
            self.click(0.04, 0.3, after_sleep=1)
            self.click(0.68, 0.91, after_sleep=3)
            self.click(0.04, 0.17, after_sleep=2)
            self.click(0.68, 0.91, after_sleep=2)
            self.wait_ocr(0.2, 0.13, 0.32, 0.22, match=re.compile(r'\d+'),
                          post_action=lambda: self.click(0.68, 0.91, after_sleep=1), settle_time=1,
                          raise_if_not_found=False)
        self.ensure_main()

    def open_daily(self):
        self.log_info('open_daily')
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
            self.log_info('no_boss_proceed, click claim')
            # Click [Guidebook] in [Terminal] interface
            self.click(0.885, 0.250, after_sleep=2)
        self.log_info(f'claim daily reward via  coordinate')
        self.click(0.930, 0.882, after_sleep=1)
        self.ensure_main(time_out=10)

    def claim_mail(self):
        self.info_set('current task', 'claim mail')
        self.back(after_sleep=1.5)
        self.click(0.64, 0.95, after_sleep=1)
        self.click(0.14, 0.9, after_sleep=1)
        self.ensure_main(time_out=10)

    def _normalize_selected_tasks(self, selected_tasks):
        if isinstance(selected_tasks, str):
            selected_tasks = [selected_tasks]
        elif not selected_tasks:
            selected_tasks = [self.support_tasks[0]]
        normalized = [task for task in self.support_tasks if task in selected_tasks]
        return normalized or [self.support_tasks[0]]

    def _get_run_count(self, task_name, config=None):
        if config is None:
            config = self.config
        run_count_keys = {
            self.TACET_TASK: 'Tacet Suppression Runs',
            self.FORGERY_TASK: 'Forgery Challenge Runs',
            self.SIMULATION_TASK: 'Simulation Challenge Runs',
        }
        count = config.get(run_count_keys[task_name], 0)
        try:
            count = int(count)
        except (TypeError, ValueError):
            count = 0
        return max(0, count)

    def _build_claim_actions(self, claim_count):
        actions = []
        while claim_count >= 2:
            actions.append(2)
            claim_count -= 2
        if claim_count == 1:
            actions.append(1)
        return actions

    def _build_farm_plan(self, selected_tasks, config=None):
        if config is None:
            config = self.config
        remaining = {}
        for task in selected_tasks:
            count = self._get_run_count(task, config=config)
            if count > 0:
                remaining[task] = self._build_claim_actions(count)
        if not remaining:
            return [(selected_tasks[0], 1)]
        plan = []
        while remaining:
            progressed = False
            for task in selected_tasks:
                actions = remaining.get(task)
                if not actions:
                    continue
                plan.append((task, actions.pop(0)))
                progressed = True
                if not actions:
                    remaining.pop(task, None)
            if not progressed:
                break
        return plan or [(selected_tasks[0], 1)]

    def _get_task_stamina_cost(self, task_name, claim_count):
        return claim_count * {
            self.TACET_TASK: self.get_task_by_class(TacetTask).stamina_once,
            self.FORGERY_TASK: self.get_task_by_class(ForgeryTask).stamina_once,
            self.SIMULATION_TASK: self.get_task_by_class(SimulationTask).stamina_once,
        }[task_name]

    def _get_goal_mode(self):
        mode = self.config.get('Farm Goal', self.DAILY_PRIORITY_MODE)
        if mode not in [self.DAILY_PRIORITY_MODE, self.CLAIM_PRIORITY_MODE]:
            return self.DAILY_PRIORITY_MODE
        return mode

    def _get_claim_count_for_remaining(self, target, remaining_stamina, goal_mode):
        stamina_once = self._get_task_stamina_cost(target, 1)
        if remaining_stamina >= stamina_once * 2:
            return 2
        if goal_mode == self.CLAIM_PRIORITY_MODE:
            if remaining_stamina >= stamina_once:
                return 1
            return 0
        if remaining_stamina > 0:
            return 1
        return 0

    def _resolve_claim_count(self, target, remaining_stamina, planned_claim_count, goal_mode):
        allowed_claim_count = self._get_claim_count_for_remaining(target, remaining_stamina, goal_mode)
        if allowed_claim_count <= 0:
            return 0
        return min(planned_claim_count, allowed_claim_count)

    def _run_daily_farm_target(self, target, remaining_stamina, claim_count):
        kwargs = {
            'config': self.config,
            'must_use': remaining_stamina,
            'max_claims': claim_count,
            'allow_double': claim_count >= 2,
        }
        if target == self.TACET_TASK:
            return self.get_task_by_class(TacetTask).farm_tacet(**kwargs)
        if target == self.FORGERY_TASK:
            return self.get_task_by_class(ForgeryTask).farm_forgery(**kwargs)
        return self.get_task_by_class(SimulationTask).farm_simulation(**kwargs)

    def run_daily_farm_rotation(self, selected_tasks, used_stamina, continue_until_depleted=False):
        goal_mode = self._get_goal_mode()
        plan = self._build_farm_plan(selected_tasks, config=self.config)
        planned_stamina = sum(self._get_task_stamina_cost(task, claim_count) for task, claim_count in plan)
        remaining_daily_stamina = max(0, 180 - used_stamina)
        remaining_plan_stamina = planned_stamina
        remaining_stamina = remaining_daily_stamina if goal_mode == self.DAILY_PRIORITY_MODE else remaining_plan_stamina
        self.log_info(f'daily farm plan: {plan}')
        if goal_mode == self.DAILY_PRIORITY_MODE and planned_stamina < remaining_stamina:
            self.log_info(
                f'planned stamina {planned_stamina} is below remaining target {remaining_stamina}, '
                f'will continue with {plan[-1][0]} until daily stamina is complete'
            )

        for target, claim_count in plan:
            if remaining_stamina <= 0:
                break
            claim_count = self._resolve_claim_count(target, remaining_stamina, claim_count, goal_mode)
            if claim_count <= 0:
                self.log_info(f'{target} skipped because remaining stamina is below one claim')
                break
            used = self._run_daily_farm_target(target, remaining_stamina, claim_count)
            if used <= 0:
                self.log_info(f'{target} stopped early, end daily farm rotation')
                return
            used_stamina += used
            remaining_daily_stamina = max(0, 180 - used_stamina)
            remaining_plan_stamina = max(0, remaining_plan_stamina - used)
            remaining_stamina = (
                remaining_daily_stamina if goal_mode == self.DAILY_PRIORITY_MODE else remaining_plan_stamina
            )
            self.info_set('current daily progress', used_stamina)
            self.sleep(4)

        fallback_target = plan[-1][0]
        if goal_mode == self.CLAIM_PRIORITY_MODE and not continue_until_depleted:
            return

        while remaining_daily_stamina > 0 and goal_mode == self.DAILY_PRIORITY_MODE:
            claim_count = self._get_claim_count_for_remaining(
                fallback_target,
                remaining_daily_stamina,
                self.DAILY_PRIORITY_MODE,
            )
            used = self._run_daily_farm_target(fallback_target, remaining_stamina, claim_count)
            if used <= 0:
                self.log_info(f'{fallback_target} stopped early during fallback, end daily farm rotation')
                return
            used_stamina += used
            remaining_daily_stamina = max(0, 180 - used_stamina)
            remaining_stamina = remaining_daily_stamina
            self.info_set('current daily progress', used_stamina)
            self.sleep(4)

        if not continue_until_depleted:
            return

        while True:
            used = self._run_daily_farm_target(fallback_target, 0, 2)
            if used <= 0:
                single_used = self._run_daily_farm_target(fallback_target, 0, 1)
                if single_used <= 0:
                    self.log_info(f'{fallback_target} stopped early while continuing farm after daily')
                    return
                used = single_used
            used_stamina += used
            self.info_set('current daily progress', used_stamina)
            self.sleep(4)


from ok import run_task
from config import config

if __name__ == "__main__":
    run_task(config, task=DailyTask, debug=True)
