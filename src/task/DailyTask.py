import re


from ok import Logger, TaskDisabledException
from src.task.BaseWWTask import number_re
from src.task.CultivationTask import CultivationTask
from src.task.FarmEchoTask import FarmEchoTask
from src.task.ForgeryTask import ForgeryTask
from src.task.GardenTask import GardenTask
from src.task.MergeEchoTask import MergeEchoTask
from src.task.NightmareNestTask import NightmareNestTask
from src.task.TacetTask import TacetTask
from src.task.SimulationTask import SimulationTask
from src.task.WWOneTimeTask import WWOneTimeTask
from src.task.BaseCombatTask import BaseCombatTask
from src.task.task_icons import task_icon

logger = Logger.get_logger(__name__)

CHECK_WEEKLY_GARDEN = 'Check Weekly Garden'
AUTO_FARM_NIGHTMARE_NEST = 'Auto Farm all Nightmare Nest'
MERGE_ECHO_IF_DISCARDED_OVER_1000 = 'Merge Echo If discarded > 1000'
TELEPORT_AND_FARM_4C_ECHO = 'Teleport and Farm 4C Echo'
ADDITIONAL_TASKS = 'Additional Tasks to Run After Daily Task'
CULTIVATION_TARGET = 'Cultivation Target'


class DailyTask(WWOneTimeTask, BaseCombatTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "📅 Daily Task"
        self.icon = task_icon('daily')
        self.group_name = 'Daily Activities'
        self.group_icon = task_icon('category-daily')
        self.support_schedule_task = True
        self.support_tasks = ["Tacet Suppression", "Forgery Challenge", "Simulation Challenge", CULTIVATION_TARGET]
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
            'Which to Farm': 'Cultivation Target follows the Guidebook cultivation target and the '
                             'Cultivation Resource Farm task settings (Simplified Chinese, 16:9).',
            'Material Selection': 'Resonator EXP / Weapon EXP / Shell Credit',
            'Farm Nightmare Nest for Daily Echo': 'Farm 1 Echo from Nightmare Nest to complete Daily Task when needed.',
            ADDITIONAL_TASKS: 'Nightmare Nest runs after stamina farming. If Tacet Suppression yielded rewards, '
                              'daily rewards are claimed before Nightmare Nest.',
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
                    CULTIVATION_TARGET: [],
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
        self.validate_additional_tasks()

        WWOneTimeTask.run(self)
        self.logged_in = False
        self.ensure_main(time_out=180)

        # 每日开始前先确认活跃度; 读不到时保守跳过体力, 不按 0 处理.
        used_stamina, daily_reward_ready = self.open_daily()
        points_unknown = getattr(self, '_daily_points_unknown', False)
        need_stamina = not daily_reward_ready and not points_unknown and used_stamina < 180
        target = self.config.get('Which to Farm', self.support_tasks[0])
        additional_tasks = self.config.get(ADDITIONAL_TASKS) or []
        farm_all_nests = AUTO_FARM_NIGHTMARE_NEST in additional_tasks
        cultivation_task = self.get_task_by_class(CultivationTask) if target == CULTIVATION_TARGET else None
        farm_daily_echo = (
            self.config.get('Farm Nightmare Nest for Daily Echo')
            and not daily_reward_ready
            and not points_unknown
            and target != self.support_tasks[0]
            # The cultivation target already clears its echo set Nightmare Nest when it runs.
            and not (cultivation_task and need_stamina and cultivation_task.nightmare_enabled())
        )

        tacet_farmed = False
        if need_stamina:
            if target == self.support_tasks[0]:
                spent = self.get_task_by_class(TacetTask).farm_tacet(
                    daily=True, used_stamina=used_stamina, config=self.config)
                tacet_farmed = spent > 0
            elif target == CULTIVATION_TARGET:
                try:
                    spent = cultivation_task.farm_cultivation(daily=True, used_stamina=used_stamina)
                    tacet_farmed = spent > 0
                except TaskDisabledException:
                    raise
                except Exception as e:
                    self.log_error(self.tr('CultivationTask Failed'), e)
                    self.ensure_main(time_out=180)
            elif target == self.support_tasks[1]:
                self.get_task_by_class(ForgeryTask).farm_forgery(daily=True, used_stamina=used_stamina,
                                                                 config=self.config)
            else:
                self.get_task_by_class(SimulationTask).farm_simulation(daily=True, used_stamina=used_stamina,
                                                                       config=self.config)
            self.sleep(4)

        if tacet_farmed:
            self.claim_daily()

        if farm_all_nests or farm_daily_echo:
            nightmare_task = self.get_task_by_class(NightmareNestTask)
            try:
                if not tacet_farmed:
                    # Keep the guidebook open for the daily reward claim.
                    nightmare_task.ensure_main = lambda *args, **kwargs: None
                if farm_all_nests:
                    self.log_debug('Auto Farm all Nightmare Nest')
                    self.run_task_by_class(NightmareNestTask)
                else:
                    self.log_debug('Farm Nightmare Nest for Daily Echo')
                    nightmare_task.run_capture_mode()
            except TaskDisabledException:
                raise
            except Exception as e:
                self.log_error(self.tr('NightmareNestTask Failed'), e)
                self.screenshot('NightmareNestTask')
                self.ensure_main(time_out=180)
            finally:
                if not tacet_farmed:
                    nightmare_task.__dict__.pop('ensure_main', None)

        if not tacet_farmed:
            self.claim_daily()

        self.claim_mail()
        self.sleep(1)
        self.claim_battle_pass()
        self.run_additional_tasks()
        self.log_info(self.tr('Daily Task Completed'), notify=True)

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

    def _battle_pass_opened(self) -> bool:
        return bool(self.wait_ocr(0.2, 0.13, 0.32, 0.22, match=re.compile(r'\d+'),
                                  settle_time=1, time_out=2, raise_if_not_found=False))

    def _open_battle_pass(self) -> bool:
        """唤起先约电台界面.

        原版靠 Alt + 点击右上角图标, 但云游戏浏览器会吞掉 Alt (Windows 菜单),
        导致界面始终打不开. 浏览器模式下直接点击入口, 并准备多个候选坐标;
        最后再走一次 Esc 主终端的文字入口作为兜底.
        """
        browser = self.is_browser()
        positions = [(0.86, 0.05)] if not browser else [(0.86, 0.05), (0.90, 0.05), (0.95, 0.05)]
        for x, y in positions:
            if not browser:
                self.send_key_down('alt')
                self.sleep(0.05)
            self.click_relative(x, y, after_sleep=1)
            if not browser:
                self.send_key_up('alt')
            if self._battle_pass_opened():
                return True

        try:
            self.back(after_sleep=1.5)
            boxes = self.ocr(0, 0, 1, 1, match=re.compile('先约电台'))
            if boxes:
                self.click(boxes[0], after_sleep=2)
                if self._battle_pass_opened():
                    return True
        except Exception as error:
            self.log_debug(f'terminal battle pass fallback failed: {error}')
        return False

    def claim_battle_pass(self):
        self.log_info(self.tr('battle pass'))
        self.ensure_main()
        if not self._open_battle_pass():
            self.log_error(self.tr('can not battle pass, maybe ended'))
            self.ensure_main()
            return
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
        self._daily_points_unknown = False
        points = self.get_total_daily_points()
        # 识别失败绝不能当成 0, 否则活跃度已满还会白刷一遍体力.
        daily_reward_ready = points is not None and points >= 100
        return current, daily_reward_ready
        # 请注意：如果任务【累计消耗180点结晶波片】已完成，current 也可能为 0，因为翻页后也有可能识别不到已用体力。

    def get_total_daily_points(self):
        """读取当前每日活跃度; 识别不到返回 None 而不是 0.

        云游戏下 OCR 偶尔读不到活跃度数字 (日志里出现过 120 被读成 0), 单次
        失败就直接当成 0 会误判成"活跃度未满"并重复消耗体力. 这里换多个区域、
        重试几次, 仍读不到就明确标记未知, 让调用方保守跳过体力任务.
        """
        regions = [(0.19, 0.8, 0.30, 0.93), (0.15, 0.75, 0.35, 0.95)]
        for _ in range(3):
            for x, y, to_x, to_y in regions:
                points_boxes = self.ocr(x, y, to_x, to_y, match=number_re)
                if not points_boxes:
                    continue
                try:
                    points = int(re.sub(r'\D', '', points_boxes[0].name))
                except (TypeError, ValueError):
                    continue
                if 0 <= points <= 200:
                    self.info_set('total daily points', points)
                    return points
            self.sleep(0.5)

        self._daily_points_unknown = True
        self.info_set('total daily points', self.tr('未识别'))
        self.log_warning(self.tr('无法确认当前活跃度，为避免浪费体力将跳过体力刷取。'))
        return None

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
