import re

from qfluentwidgets import FluentIcon

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

logger = Logger.get_logger(__name__)

CHECK_WEEKLY_GARDEN = 'Check Weekly Garden'
AUTO_FARM_NIGHTMARE_NEST = 'Auto Farm all Nightmare Nest'
MERGE_ECHO_IF_DISCARDED_OVER_1000 = 'Merge Echo If discarded > 1000'
TELEPORT_AND_FARM_4C_ECHO = 'Teleport and Farm 4C Echo'
ADDITIONAL_TASKS = 'Additional Tasks to Run After Daily Task'


class DailyTask(WWOneTimeTask, BaseCombatTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Daily Task"
        self.group_name = "Daily"
        self.group_icon = FluentIcon.CALENDAR
        self.icon = FluentIcon.CAR
        self.support_schedule_task = True
        self.support_tasks = ["Tacet Suppression", "Forgery Challenge", "Simulation Challenge"]
        self.default_config = {
            'Which to Farm': self.support_tasks[0],
            'Which Tacet Suppression to Farm': 1,  # starts with 1
            'Which Forgery Challenge to Farm': 1,  # starts with 1
            'Material Selection': 'Shell Credit',
            'Farm Nightmare Nest for Daily Echo': True,
            ADDITIONAL_TASKS: [CHECK_WEEKLY_GARDEN],
        }
        self.config_description = {
            'Which Tacet Suppression to Farm': 'The Tacet Suppression number in the F2 list.',
            'Which Forgery Challenge to Farm': 'The Forgery Challenge number in the F2 list.',
            'Material Selection': 'Resonator EXP / Weapon EXP / Shell Credit',
            'Farm Nightmare Nest for Daily Echo': 'Farm 1 Echo from Nightmare Nest to complete Daily Task when needed.',
            ADDITIONAL_TASKS: 'Select optional tasks to run after the daily task is complete.',
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
        if not self.validate_additional_tasks():
            return

        WWOneTimeTask.run(self)
        self.logged_in = False
        self.ensure_main(time_out=180)

        condition2 = self.config.get('Farm Nightmare Nest for Daily Echo')

        used_stamina, daily_reward_ready = self.open_daily()
        need_stamina = not daily_reward_ready and used_stamina < 180
        need_nightmare = (
                condition2
                and not daily_reward_ready
                and self.config.get('Which to Farm', self.support_tasks[0]) != self.support_tasks[0]
        )

        if need_nightmare:
            try:
                # 劫持 NightmareNestTask.ensure_main 避免梦魇打完关书
                self.get_task_by_class(NightmareNestTask).ensure_main = lambda *args, **kwargs: None

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

        if need_stamina:
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
            self.sleep(4)

        self.claim_daily()

        self.claim_mail()
        self.sleep(1)
        self.claim_battle_pass()
        self.run_additional_tasks()
        self.log_info('Task completed', notify=True)

    def validate_additional_tasks(self):
        additional_tasks = self.config.get(ADDITIONAL_TASKS) or []
        if TELEPORT_AND_FARM_4C_ECHO in additional_tasks:
            farm_echo_task = self.get_task_by_class(FarmEchoTask)
            if farm_echo_task.config.get('Teleport to Boss', 'No') == 'No':
                self.log_error(
                    self.tr(
                        'Teleport and Farm 4C Echo requires "Teleport to Boss" to be enabled in Farm Echo Task.'
                    ),
                    notify=True,
                )
                return False
        if AUTO_FARM_NIGHTMARE_NEST in additional_tasks:
            nightmare_task = self.get_task_by_class(NightmareNestTask)
            if not nightmare_task.config.get('Which to Farm'):
                self.log_error(
                    self.tr(
                        'Auto Farm all Nightmare Nest requires at least one "Which to Farm" option.'
                    ),
                    notify=True,
                )
                return False
        return True

    def run_additional_tasks(self):
        additional_tasks = self.config.get(ADDITIONAL_TASKS) or []
        if CHECK_WEEKLY_GARDEN in additional_tasks:
            self.check_weekly_garden()
        if AUTO_FARM_NIGHTMARE_NEST in additional_tasks:
            self.run_task_by_class(NightmareNestTask)
        if MERGE_ECHO_IF_DISCARDED_OVER_1000 in additional_tasks:
            self.check_discarded_echo()
        if TELEPORT_AND_FARM_4C_ECHO in additional_tasks:
            self.run_task_by_class(FarmEchoTask)

    def check_weekly_garden(self):
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

    def check_discarded_echo(self):
        self.info_set('current task', 'check discarded echo')
        self.log_info('check discarded echo')
        try:
            self.run_task_by_class(MergeEchoTask)
        except TaskDisabledException:
            raise
        except Exception as e:
            self.log_error("MergeEchoTask Failed", e)
            self.screenshot('MergeEchoTask')
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


from ok import run_task
from config import config

if __name__ == "__main__":
    run_task(config, task=DailyTask, debug=True)
