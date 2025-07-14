import re
import subprocess

from qfluentwidgets import FluentIcon

from ok import Logger
from src.task.BaseWWTask import number_re
from src.task.TacetTask2 import TacetTask2
from src.task.ForgeryTask import ForgeryTask
from src.task.SimulationTask import SimulationTask
from src.task.WWOneTimeTask import WWOneTimeTask

logger = Logger.get_logger(__name__)


class DailyTask2(TacetTask2, ForgeryTask, SimulationTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.icon = FluentIcon.CAR
        self.name = '⭐ Daily Task'
        self.description = 'open game, login, monthly card, mail, farm, activity, radio'
        self.default_config = {
            'Teleport Timeout': 10,
            'Tacet Suppression Serial Number': 1, # starts with 1
            'Tacet Suppression Count': 0, # starts with 0
            'Forgery Suppression Serial Number': 1, # starts with 1
            'Forgery Challenge Count': 0, # starts with 0
            'Material Selection': 'Shell Credit',
            'Simulation Challenge Count': 0, # starts with 0
            'Exit with Error': True,
        }
        self.config_description = {
            'Teleport Timeout': 'the timeout of second for teleport',
            'Tacet Suppression Serial Number': 'the Nth number in the list of Tacet Suppression list (in F2 menu)',
            'Tacet Suppression Count': 'farm Tacet Suppression N time(s), 60 stamina per time, set a large number to use all stamina',
            'Forgery Suppression Serial Number': 'the Nth number in the list of Forgery Suppression list (in F2 menu)',
            'Forgery Challenge Count': 'farm Forgery Challenge N time(s), 40 stamina per time, set a large number to use all stamina',
            'Material Selection': 'Resonator EXP / Weapon EXP / Shell Credit, on current screen of F2',
            'Simulation Challenge Count': 'farm Simulation Challenge N time(s), 40 stamina per time, set a large number to use all stamina',
            'Exit with Error': 'exit game and app with exception raised when option [Exit After Task] checked'
        }
        self.show_create_shortcut = True
        self.add_exit_after_config()

    def run(self):
        try:
            #
            current_task = 'login'
            WWOneTimeTask.run(self)
            self.ensure_main(time_out=180)
            #
            current_task = 'claim_mail'
            self.make_sure_in_world()
            self.claim_mail()
            #
            current_task = 'farm_tacet'
            self.tacet_serial_number = self.config.get('Tacet Suppression Serial Number', 1)
            self.stamina_once = 60
            try:
                self.farm_tacet()
            except:
                # retry next tacet
                tacet_index = self.tacet_serial_number - 1
                tacet_index = (tacet_index + 1) % self.total_number
                self.tacet_serial_number = tacet_index + 1
                self.farm_tacet()
            #
            current_task = 'farm_forgery'
            self.stamina_once = 40
            try:
                self.farm_forgery()
            except:
                self.farm_forgery()
            #
            current_task = 'farm_simulation'
            self.stamina_once = 40
            try:
                self.farm_simulation()
            except:
                self.farm_simulation()
            #
            current_task = 'teleport_to_safe_place'
            self.teleport_to_tacet(index=tacet_index) # teleport to safe place (of tacet entry)
            #
            current_task = 'claim_daily'
            self.make_sure_in_world()
            self.claim_daily()
            current_task = 'claim_millage'
            self.claim_millage()
            self.log_info('Task completed', notify=True)
        except Exception as e:
            self.log_error(f'一条龙错误 | {current_task} | {str(e)}')
            if self.config.get('Exit with Error', True) and self.config.get('Exit After Task', False):
                subprocess.run(['pwsh', '-c', 'Stop-Process -Force -Name Client-Win64-Shipping'])
                exit()
            else:
                raise e

    def claim_millage(self):
        self.log_info('open_millage')
        self.send_key_down('alt')
        self.sleep(0.05)
        self.click_relative(0.86, 0.05)
        self.send_key_up('alt')
        self.wait_ocr(0.2, 0.13, 0.32, 0.22, match=re.compile(r'\d+'), settle_time=1, raise_if_not_found=True, log=True)
        self.click(0.04, 0.3, after_sleep=1)
        self.click(0.68, 0.91, after_sleep=1)
        self.click(0.04, 0.16, after_sleep=1)
        self.click(0.68, 0.91, after_sleep=1)
        self.ensure_main()

    def claim_daily(self):
        self.info_set('current task', 'claim daily')
        self.ensure_main(time_out=5)
        self.openF2Book()
        gray_book_quest = self.openF2Book('gray_book_quest')
        self.click_box(gray_book_quest, after_sleep=1.5)
        #
        try:
            total_points = int(self.ocr(0.19, 0.8, 0.30, 0.93, match=number_re)[0].name) # throw exception with activity 0
        except:
            total_points = 0
        self.info_set('daily points', total_points)
        if total_points >= 100:
            self.click(0.89, 0.85, after_sleep=1)
            self.ensure_main(time_out=5)
            return
        #
        while True:
            boxes = self.ocr(0.23, 0.16, 0.31, 0.69, match=re.compile(r'^[1-9]\d*/\d+$'))
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

        total_points = int(self.ocr(0.19, 0.8, 0.30, 0.93, match=number_re)[0].name)
        self.info_set('daily points', total_points)
        if total_points < 100:
            self.log_error("Can't complete daily task, may need to increase stamina manually!", notify=True)
        else:
            self.click(0.89, 0.85, after_sleep=1)
        self.ensure_main(time_out=5)

    def claim_mail(self):
        self.info_set('current task', 'claim mail')
        self.back(after_sleep=1.5)
        self.click(0.64, 0.95, after_sleep=1)
        self.click(0.14, 0.9, after_sleep=1)
        self.ensure_main(time_out=5)


echo_color = {
    'r': (200, 255),  # Red range
    'g': (150, 220),  # Green range
    'b': (130, 170)  # Blue range
}
