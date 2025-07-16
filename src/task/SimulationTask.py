import re

from qfluentwidgets import FluentIcon

from ok import Logger
from src.task.DomainTask import DomainTask

logger = Logger.get_logger(__name__)


class SimulationTask(DomainTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.icon = FluentIcon.FLAG
        self.name = 'Simulation Challenge'
        self.description = 'Farms the selected Simulation Challenge. Must be able to teleport (F2).'
        self.default_config = {
            'Material Selection': 'Shell Credit',
            'Simulation Challenge Count': 20,  # starts with 20
        }
        material_option_list = ['Resonator EXP', 'Weapon EXP', 'Shell Credit']
        self.config_type['Material Selection'] = {'type': 'drop_down', 'options': material_option_list}
        self.config_description = {
            'Material Selection': 'Resonator EXP / Weapon EXP / Shell Credit',
            'Simulation Challenge Count': 'Number of times to farm the Simulation Challenge (40 stamina per run). Set a large number to use all stamina.',
        }
        self.stamina_once = 40

    def run(self):
        super().run()
        self.make_sure_in_world()
        self.farm_simulation()

    def farm_simulation(self):
        total_counter = self.config.get('Simulation Challenge Count', 20)
        if total_counter <= 0:
            self.log_info('0 time(s) farmed, 0 stamina used')
            return
        current, back_up = self.open_F2_book_and_get_stamina()
        if (current + back_up < self.stamina_once):
            self.back()
            return
        self.teleport_into_domain(self.config.get('Material Selection', 'Shell Credit'))
        self.sleep(1)
        self.farm_in_domain(total_counter=total_counter, current=current, back_up=back_up)

    def teleport_into_domain(self, selection):
        self.click_relative(0.18, 0.28, after_sleep=1)
        self.info_set('Teleport to Simulation Challenge', selection)
        self.click_relative(0.88, 494 / 1440, after_sleep=1)
        self.wait_click_travel()
        self.wait_in_team_and_world(time_out=self.teleport_timeout)
        self.sleep(1)
        self.walk_until_f(time_out=1)
        self.pick_f()
        if selection == 'Resonator EXP':
            index = 0
        elif selection == 'Weapon EXP':
            index = 1
        else:  # selection == 'Shell Credit'
            index = 2
        self.click_relative(0.22, 0.17 + index * 0.08, after_sleep=1)
        self.click_relative(0.93, 0.90, after_sleep=1)
        self.click_relative(0.93, 0.90, after_sleep=1)
        self.wait_in_team_and_world(time_out=self.teleport_timeout)
