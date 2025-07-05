import re

from qfluentwidgets import FluentIcon

from ok import Logger
from src.task.DomainTask import DomainTask

logger = Logger.get_logger(__name__)


class SimulationTask(DomainTask):

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
        self.teleport_timeout = 60
        self.stamina_once = 40
    
    def run(self):
        super().run()
        self.teleport_timeout = self.config.get('Teleport Timeout', 10)
        self.make_sure_in_world()
        self.farm_simulation()

    def farm_simulation(self):
        total_counter = self.config.get('Simulation Challenge Count', 0)
        if total_counter <= 0:
            self.log_info(f'0 time(s) farmed, 0 stamina used')
            return
        self.sleep(1)
        current, back_up = self.open_F2_book_and_get_stamina()
        if (current + back_up < self.stamina_once):
            self.back()
        self.teleport_into_domain(self.config.get('Material Selection', 'Shell Credit'))
        self.farm_in_domain(total_counter=total_counter, current=current, back_up=back_up)

    def teleport_into_domain(self, selection):
        self.click_relative(0.18, 0.28, after_sleep=1)
        self.info_set('Teleport to Simulation Challenge', selection)
        if self.ocr(0.3, 0.2, 0.36, 0.27, match=[re.compile('UP', re.IGNORECASE)]):
            logger.info('tacet double up')
            y = 0.325
        else:
            y = 0.32
        self.click_relative(0.88, y, after_sleep=1)
        self.wait_click_travel()
        self.wait_in_team_and_world(time_out=self.teleport_timeout)
        self.sleep(max(5, self.teleport_timeout / 10))
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
        self.wait_in_team_and_world(time_out = self.teleport_timeout)

            
echo_color = {
    'r': (200, 255),  # Red range
    'g': (150, 220),  # Green range
    'b': (130, 170)  # Blue range
}
