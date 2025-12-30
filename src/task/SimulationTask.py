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
        current, back_up, total = self.open_F2_book_and_get_stamina()
        if total < self.stamina_once or total < must_use or (must_use == 0 and current < self.stamina_once):
            self.log_info(f'not enough stamina', notify=True)
            self.back()
            return
        self.teleport_into_domain(config.get('Material Selection', 'Shell Credit'))
        self.sleep(1)
        self.farm_in_domain(must_use=must_use)

    def teleport_into_domain(self, selection):
        self.click_relative(0.18, 0.28, after_sleep=1)
        self.info_set('Teleport to Simulation Challenge', selection)
        self.click_relative(0.980, 0.875, after_sleep=1)
        btns = self.find_feature('boss_proceed', box=self.box_of_screen(0.94, 0.26, 0.97, 0.88), threshold=0.8)
        if btns is None:
            raise Exception("can't find boss_proceed")
        top_btn = min(btns, key=lambda box: box.y)
        self.click_box(top_btn, after_sleep=1)
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
