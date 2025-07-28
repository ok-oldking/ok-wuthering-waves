import re

from qfluentwidgets import FluentIcon

from ok import Logger
from src.task.BaseWWTask import number_re, stamina_re
from src.task.ForgeryTask import ForgeryTask
from src.task.TacetTask import TacetTask
from src.task.WWOneTimeTask import WWOneTimeTask
from src.task.BaseCombatTask import BaseCombatTask

logger = Logger.get_logger(__name__)


class DailyTask(WWOneTimeTask, BaseCombatTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Daily Task"
        # self.add_exit_after_config()
        self.icon = FluentIcon.CAR
        self.support_tasks = ["Tacet Suppression", "Forgery Challenge"]
        self.default_config = {
            'Which to Farm': self.support_tasks[0],
            'Which Tacet Suppression to Farm': 1,  # starts with 1
            'Which Forgery Challenge to Farm': 1,  # starts with 1
        }
        self.config_description = {
            'Which Tacet Suppression to Farm': 'The Tacet Suppression number in the F2 list.',
            'Which Forgery Challenge to Farm': 'The Forgery Challenge number in the F2 list.',
        }
        self.config_type['Which to Farm'] = {'type': "drop_down", 'options': self.support_tasks}
        self.description = "Login, claim monthly card, farm echo, and claim daily reward"

    def run(self):
        WWOneTimeTask.run(self)
        self.ensure_main(time_out=180)
        used_stamina, completed = self.open_daily()
        self.send_key('esc', after_sleep=1)
        if not completed:
            if used_stamina < 180:
                if self.config.get('Which to Farm', self.support_tasks[0]) == self.support_tasks[0]:
                    self.get_task_by_class(TacetTask).farm_tacet(daily=True, used_stamina=used_stamina, config=self.config)
                else:
                    self.get_task_by_class(ForgeryTask).farm_forgery(daily=True, used_stamina=used_stamina,
                                                                    config=self.config)
                    self.sleep(2)
                    self.get_task_by_class(ForgeryTask).purification_material()
                self.sleep(4)
            self.claim_daily()
        self.claim_mail()
        self.claim_millage()
        self.log_info('Task completed', notify=True)

    def claim_millage(self):
        self.log_info('open_millage')
        self.send_key_down('alt')
        self.sleep(0.05)
        self.click_relative(0.86, 0.05)
        self.send_key_up('alt')
        self.wait_ocr(0.2, 0.13, 0.32, 0.22, match=re.compile(r'\d+'), settle_time=1, raise_if_not_found=True, log=True)
        self.click(0.04, 0.3, after_sleep=1)
        self.click(0.68, 0.91, after_sleep=3)
        self.click(0.04, 0.17, after_sleep=1)
        self.click(0.68, 0.91, after_sleep=1)
        self.click(0.68, 0.91, after_sleep=1)
        self.ensure_main()

    def open_daily(self):
        self.log_info('open_daily')
        gray_book_quest = self.openF2Book("gray_book_quest")
        self.click_box(gray_book_quest, after_sleep=1.5)
        progress = self.ocr(0.1, 0.1, 0.5, 0.75, match=re.compile(r'^(\d+)/180$'))
        if not progress:
            self.click(0.96, 0.56, after_sleep=1)
            progress = self.ocr(0.1, 0.1, 0.5, 0.75, match=re.compile(r'^(\d+)/180$'))
        if progress:
            current = int(progress[0].name.split('/')[0])
        else:
            current = 0
        self.info_set('current daily progress', current)
        return current, self.get_total_daily_points() >= 100

    def get_total_daily_points(self):
        points_boxes = self.ocr(0.19, 0.8, 0.30, 0.93, match=number_re)
        if points_boxes:
            points = int(points_boxes[0].name)
        else:
            points = 0
        self.info_set('total daily points', points)
        return points

    def claim_daily(self):
        self.info_set('current task', 'claim daily')
        self.ensure_main(time_out=5)
        self.open_daily()
        while True:
            boxes = self.ocr(0.23, 0.16, 0.31, 0.69, match=re.compile(r"^[1-9]\d*/\d+$"))
            count = 0
            for box in boxes:
                parts = box.name.split('/')
                if len(parts) == 2 and parts[0] == parts[1]:
                    count += 1

            self.log_info(f'can claim count {count}')
            if count == 0:
                break
            for _ in range(count):
                self.click(0.87, 0.17, after_sleep=0.5)
            self.sleep(1)

        total_points = self.get_total_daily_points()
        self.info_set('daily points', total_points)
        if total_points < 100:
            raise Exception("Can't complete daily task, may need to increase stamina manually!")

        self.click(0.89, 0.85, after_sleep=1)
        self.ensure_main(time_out=10)

    def claim_mail(self):
        self.info_set('current task', 'claim mail')
        self.back(after_sleep=1.5)
        self.click(0.64, 0.95, after_sleep=1)
        self.click(0.14, 0.9, after_sleep=1)
        self.ensure_main(time_out=5)
