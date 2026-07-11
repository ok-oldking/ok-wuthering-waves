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
        self.support_schedule_task = True
        self.default_config = {
            'Material Selection': 'Shell Credit',
        }
        material_option_list = ['Resonator EXP', 'Weapon EXP', 'Shell Credit']
        self.config_type['Material Selection'] = {'type': 'drop_down', 'options': material_option_list}
        self.config_description = {
            'Material Selection': 'Resonator EXP / Weapon EXP / Shell Credit',
        }
        self.stamina_once = 40

    def run(self):
        super().run()
        self.make_sure_in_world()
        self.farm_simulation()

    def farm_simulation(self, daily=False, used_stamina=0, config=None):
        if daily:
            must_use = 180 - used_stamina
        else:
            must_use = 0
        if config is None:
            config = self.config
        selection = config.get('Material Selection', 'Shell Credit')

        def teleport_once():
            self.teleport_into_domain(selection)

        self.farm_domain_with_recovery_loop(must_use, teleport_once)

    def teleport_into_domain(self, selection):
        self.open_boss_book('moni')
        self.info_set('Target Simulation Challenge', selection)
        if selection == 'Resonator EXP':
            index = 0
        elif selection == 'Weapon EXP':
            index = 1
        else:  # selection == 'Shell Credit'
            index = 2
        # go buttom
        self.click(0.9730, 0.8806, after_sleep=1)
        # click target
        self.click(0.898, 0.533 + index * 0.14, after_sleep=1)
        self.click_relative(0.93, 0.90, after_sleep=1)
        self.click_team_challenge()
