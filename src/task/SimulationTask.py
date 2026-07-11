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
        self.info_set('Teleport to Simulation Challenge', selection)
        self.click_relative(0.980, 0.875, after_sleep=1)
        btns = self.find_feature('boss_proceed', box=self.box_of_screen(0.94, 0.26, 0.97, 0.88), threshold=0.8)
        if not btns:
            raise Exception("can't find boss_proceed")
        top_btn = min(btns, key=lambda box: box.y)
        self.click_box(top_btn, after_sleep=2)
        # 点击[单人挑战]
        self.click_relative(2270/2560, 1300/1440, after_sleep=2)
        # 确认配队
        self.click_relative(2270/2560, 1300/1440, after_sleep=2)
        self.wait_in_team_and_world(time_out=self.teleport_timeout)
