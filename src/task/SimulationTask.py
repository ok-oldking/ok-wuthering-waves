import re

from qfluentwidgets import FluentIcon

from ok import Logger
from src.task.TacetTask import TacetTask
from src.task.BaseCombatTask import BaseCombatTask
from src.task.WWOneTimeTask import WWOneTimeTask

logger = Logger.get_logger(__name__)


class SimulationTask(TacetTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.icon = FluentIcon.FLAG
        self.name = '⭐ Simulation Challenge'
        self.description = 'Farm selected Simulation Challenge, you need to be able to teleport'
        self.default_config = {
            'Teleport Timeout': 10,
            'Material Selection': 'Shell Credit',
            'Simulation Challenge Count': 0, # starts with 0
        }
        material_option_list = ['Resonator EXP', 'Weapon EXP', 'Shell Credit']
        self.config_type['Material Selection'] = {'type': 'drop_down', 'options': material_option_list}
        self.config_description = {
            'Teleport Timeout': 'the timeout of second for teleport',
            'Material Selection': 'Resonator EXP / Weapon EXP / Shell Credit, on current screen of F2',
            'Simulation Challenge Count': 'farm Simulation Challenge N time(s), 40 stamina per time, set a large number to use all stamina',
        }
        self.stamina_once = 40
    
    def run(self):
        super(BaseCombatTask,self).run()
        super(WWOneTimeTask,self).run()
        timeout_second = self.config.get('Teleport Timeout', 10)
        self.wait_in_team_and_world(esc=True, time_out=timeout_second)
        self.farm_simulation()

    def farm_simulation(self):
        timeout_second = self.config.get('Teleport Timeout', 10)
        total_counter = self.config.get('Simulation Challenge Count', 0)
        if total_counter <= 0:
            self.log_info(f'0 time(s) farmed, 0 stamina used')
            return
        self.sleep(1)
        gray_book_boss = self.openF2Book('gray_book_boss')
        self.click_box(gray_book_boss, after_sleep=1)
        current, back_up = self.get_stamina()
        if current == -1:
            self.click_relative(0.04, 0.4, after_sleep=1)
            current, back_up = self.get_stamina()
        if current + back_up < self.stamina_once:
            self.log_info(f'not enough stamina, 0 stamina used')
            return
        self.click_relative(0.18, 0.28, after_sleep=1)
        self.teleport_to_simulation(self.config.get('Material Selection', 'Shell Credit'))
        #
        counter = total_counter
        remaining_total = 0
        total_used = 0
        while True: 
            self.sleep(max(5, timeout_second / 5))
            self.walk_until_f(time_out=4, backward_time=0, raise_if_not_found=True)
            self.combat_once()
            self.sleep(3)
            self.walk_to_treasure()
            used, remaining_total, remaining_current, used_back_up = self.ensure_stamina(self.stamina_once, self.stamina_once)
            total_used += used
            # self.click(0.75, 0.32, after_sleep=2) # click fork of dialog (for debug)
            self.wait_click_ocr(0.2, 0.56, 0.75, 0.69, match=[str(used), '确认', 'Confirm'], raise_if_not_found=True, log=True) # click use stamina of dialog
            self.sleep(4)
            counter -= 1
            if counter <= 0:
                self.log_info(f'{total_counter} time(s) farmed, {total_used} stamina used')
                break
            if remaining_total < self.stamina_once:
                self.log_info(f'not enough stamina, {total_used} stamina used')
                break
            self.click(0.68, 0.84, after_sleep=2) # farm again
        #
        self.click(0.42, 0.84, after_sleep=2) # back to world
        self.wait_in_team_and_world(time_out=timeout_second)

    def teleport_to_simulation(self, selection):
        self.info_set('Teleport to Simulation Challenge', selection)
        if self.ocr(0.3, 0.2, 0.36, 0.27, match=[re.compile('UP', re.IGNORECASE)]):
            logger.info('tacet double up')
            y = 0.325
        else:
            y = 0.32
        self.click_relative(0.88, y, after_sleep=1)
        self.wait_click_travel()
        timeout_second = self.config.get('Teleport Timeout', 10)
        self.wait_in_team_and_world(time_out=timeout_second)
        self.sleep(max(5, timeout_second / 10))
        self.walk_until_f(time_out=1)
        if selection == 'Resonator EXP':
            index = 0
        elif selection == 'Weapon EXP':
            index = 1
        else: # selection == 'Shell Credit'
            index = 2
        self.click_relative(0.22, 0.17 + index * 0.08, after_sleep=1)
        self.click_relative(0.93, 0.90, after_sleep=1)
        self.click_relative(0.93, 0.90, after_sleep=1)

            
echo_color = {
    'r': (200, 255),  # Red range
    'g': (150, 220),  # Green range
    'b': (130, 170)  # Blue range
}
